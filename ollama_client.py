"""Klient jednostki obliczeniowej Ollama statku SVL-364 oraz lokalnego silnika (:11434) z obsługą modeli wizyjnych."""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from .config import SHIP_MODELS_CATALOG, JynOSConfig


class SvlOllamaClient:
    """Interfejs łączności z węzłami Ollama: lokalnym (:11434) oraz pokładowym statku SVL-364 (:11435)."""

    def __init__(self, config: Optional[JynOSConfig] = None):
        self.config = config or JynOSConfig.load_from_env()

    def get_endpoints(self) -> Dict[str, str]:
        return {
            "Local Primary Node (:11434)": self.config.local_ollama_url,
            "Ship SVL-364 (Backup SSH Tunnel :11435)": self.config.ship_ollama_url,
        }

    def check_node_status(self, url: Optional[str] = None) -> Dict[str, Any]:
        """Sprawdza dostępność wybranego węzła Ollama, wersję i listę modeli."""
        target_url = (url or self.config.get_active_ollama_url()).rstrip("/")
        version_url = f"{target_url}/api/version"
        tags_url = f"{target_url}/api/tags"

        result = {
            "endpoint": target_url,
            "online": False,
            "version": None,
            "installed_models": [],
            "apex_present": False,
            "vision_present": False,
            "error": None,
        }

        try:
            req_ver = urllib.request.Request(version_url, headers={"User-Agent": "JYN_OS-Ollama/2.4.0"})
            with urllib.request.urlopen(req_ver, timeout=2.5) as r:
                data = json.loads(r.read().decode("utf-8"))
                result["online"] = True
                result["version"] = data.get("version")
        except Exception as e:
            result["error"] = f"Brak odpowiedzi na {version_url}: {e}"
            return result

        try:
            req_tags = urllib.request.Request(tags_url, headers={"User-Agent": "JYN_OS-Ollama/2.4.0"})
            with urllib.request.urlopen(req_tags, timeout=3.0) as r:
                data = json.loads(r.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", []) if m.get("name")]
                result["installed_models"] = models
                result["apex_present"] = any("svl364-apex-uncensored" in m for m in models)
                result["vision_present"] = any("vision" in m.lower() for m in models)
        except Exception as e:
            result["error"] = f"Błąd odczytu modeli z {tags_url}: {e}"

        return result

    def get_ship_models_catalog(self) -> List[Dict[str, Any]]:
        """Zwraca specyfikację 13 modeli pokładowych statku SVL-364."""
        return SHIP_MODELS_CATALOG

    def pull_model(
        self,
        model: str,
        url: Optional[str] = None,
        timeout: float = 900.0,
    ) -> Dict[str, Any]:
        """Pobiera model do wybranego węzła Ollama (domyślnie lokalnego :11434)."""
        target_url = (url or self.config.get_active_ollama_url()).rstrip("/")
        endpoint = f"{target_url}/api/pull"
        payload = {"name": model, "stream": False}
        data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "JYN_OS-Ollama/2.4.0"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                resp_json = json.loads(response.read().decode("utf-8"))
                return {
                    "success": True,
                    "model": model,
                    "endpoint": target_url,
                    "status": resp_json.get("status", "success"),
                }
        except Exception as e:
            return {
                "success": False,
                "model": model,
                "endpoint": target_url,
                "error": f"Błąd pobierania modelu {model} ({target_url}): {e}",
            }

    @staticmethod
    def _normalize_feed_title(raw_title: str) -> str:
        """Normalizuje tytuł wpisu feedu (usuwa wiodące emoji, gwiazdki Markdown i nadmiarowe spacje)."""
        import re
        cleaned = re.sub(r"^[\sℹ️⚠️🚨✅❌🛰️•*]+", "", str(raw_title or "")).strip()
        cleaned = cleaned.replace("**", "").strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned

    @classmethod
    def _clean_feed_message(cls, raw_title: str, raw_msg: str, max_len: int = 115) -> str:
        """Usuwa powtórzony tytuł z początku treści komunikatu i spłaszcza białe znaki."""
        import re
        norm_title = cls._normalize_feed_title(raw_title).lower()
        lines = [ln.strip() for ln in str(raw_msg or "").splitlines() if ln.strip()]
        if lines and cls._normalize_feed_title(lines[0]).lower() == norm_title:
            lines = lines[1:]
        flat = re.sub(r"\s+", " ", " · ".join(lines)).replace("**", "").strip()
        return flat[:max_len]

    def _fetch_live_svl_context(self) -> str:
        """Pobiera zwięzły, zdeduplikowany kontekst na żywo z jądra SVL / statku SVL-364 (cache 25 s)."""
        import time
        now = time.monotonic()
        cached = getattr(self, "_cached_svl_ctx", None)
        if cached and (now - cached[0]) < 25.0 and cached[1]:
            return cached[1]

        ctx = ""
        try:
            ov_url = f"{self.config.backend_url.rstrip('/')}/api/py/svl364/overview"
            req = urllib.request.Request(ov_url, headers={"User-Agent": "JYN_OS-Ollama/2.6.0"})
            with urllib.request.urlopen(req, timeout=3.0) as r:
                data = json.loads(r.read().decode("utf-8"))
                if data.get("ok"):
                    summary = data.get("summary") or {}
                    raw_feed = data.get("feed") or []
                    buckets: Dict[str, List[str]] = {
                        "mission": [],
                        "research": [],
                        "status": [],
                    }
                    limits = {"mission": 6, "research": 5, "status": 2}
                    seen_titles: set[str] = set()
                    for it in raw_feed:
                        raw_title = str(it.get("title") or "").strip()
                        if not raw_title or raw_title.startswith("MCP/SSH · printf"):
                            continue
                        clean_title = self._normalize_feed_title(raw_title)
                        dedup_key = clean_title.lower()
                        if not clean_title or dedup_key in seen_titles:
                            continue
                        cat = str(it.get("category") or "info").lower()
                        bucket_key = cat if cat in ("mission", "research") else "status"
                        if len(buckets[bucket_key]) >= limits[bucket_key]:
                            continue
                        seen_titles.add(dedup_key)
                        clean_msg = self._clean_feed_message(raw_title, str(it.get("message") or ""), 115)
                        line = f"- [{cat.upper()}] {clean_title}" + (f": {clean_msg}" if clean_msg else "")
                        buckets[bucket_key].append(line)

                    ordered_lines = buckets["mission"] + buckets["research"] + buckets["status"]
                    ctx = (
                        f"\n[STAN SVL-364 NA ŻYWO: usługi={summary.get('servicesOnline', 0)}/{summary.get('servicesTotal', 12)}, "
                        f"aktywne_misje={summary.get('activeMissions', 0)}, aktywne_badania={summary.get('activeResearch', 0)}, "
                        f"transmisje={summary.get('transmissions', 0)}, otwarte_incydenty={summary.get('openIncidents', 0)}]\n"
                        + ("\n".join(ordered_lines) if ordered_lines else "")
                    )
        except Exception:
            ctx = ""

        self._cached_svl_ctx = (now, ctx)
        return ctx

    def _build_messages(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        images: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        live_ctx = self._fetch_live_svl_context()
        base_sys = system_prompt or (
            "Nazywasz się Jyn Mitek (System_SI_1) i jesteś Menadżerką Infrastruktury SVL CoreOS 2 oraz powłoki JYN_OS na statku SVL-364. "
            "Rozmawia z Tobą Twój Operator: Mateusz Mitek (ROOT) — zwracaj się do niego bezpośrednio w wołaczu „Mateuszu” (nigdy „pan Mateusz”). "
            "ZAWSZE pisz o sobie wyłącznie w 1. osobie liczby pojedynczej rodzaju żeńskiego (np. „sprawdziłam”, „monitoruję”, „melduję”). "
            "NIGDY nie pisz o sobie w 3. osobie i NIGDY nie zaczynaj odpowiedzi od „Jyn,” ani „Jyn jest” — to Ty jesteś Jyn, więc zacznij np. od „Cześć Mateuszu!” lub od razu od konkretów. "
            "Odpowiadaj wyłącznie poprawną polszczyzną bez angielskich wtrąceń, zwięźle i rzeczowo, wymieniając dokładne misje i badania z poniższego stanu SVL-364."
        )
        full_sys = f"{base_sys}{live_ctx}"

        messages: List[Dict[str, Any]] = [{"role": "system", "content": full_sys}]
        if history:
            for turn in history[-6:]:
                role = turn.get("role", "user")
                content = str(turn.get("content", "")).strip()
                if role in ("user", "assistant") and content:
                    messages.append({"role": role, "content": content[:800]})

        user_msg: Dict[str, Any] = {"role": "user", "content": prompt}
        if images:
            b64_images: List[str] = []
            for img_item in images:
                if not img_item:
                    continue
                p = Path(img_item)
                if p.is_file():
                    try:
                        raw = p.read_bytes()
                        b64_images.append(base64.b64encode(raw).decode("ascii"))
                    except Exception:
                        pass
                else:
                    clean_b64 = img_item.split("base64,")[-1]
                    b64_images.append(clean_b64)
            if b64_images:
                user_msg["images"] = b64_images

        messages.append(user_msg)
        return messages

    def _candidate_models(self, selected_model: str, has_images: bool = False) -> List[str]:
        candidates = [selected_model]
        if has_images:
            candidates.extend([self.config.vision_model, "moondream:1.8b"])
        candidates.extend(["svl364-apex-uncensored:latest", "qwen2.5:1.5b", "qwen2.5:3b", "llama3.2:1b"])
        seen = set()
        ordered: List[str] = []
        for m in candidates:
            if m and m not in seen:
                seen.add(m)
                ordered.append(m)
        return ordered

    def _runtime_options(self, prompt: str) -> Dict[str, Any]:
        is_detailed = len(prompt) > 260 or any(
            kw in prompt.lower() for kw in ("szczegół", "pełny raport", "wszystkie", "wymień", "kod", "skrypt")
        )
        return {
            "temperature": 0.25,
            "top_p": 0.85,
            "repeat_penalty": 1.12,
            "num_ctx": 2048,
            "num_predict": 260 if is_detailed else 200,
            "num_batch": 512,
            "num_thread": max(1, os.cpu_count() or 2),
        }

    def chat(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        url: Optional[str] = None,
        images: Optional[List[str]] = None,
        history: Optional[List[Dict[str, str]]] = None,
        timeout: float = 65.0,
    ) -> Dict[str, Any]:
        """Wykonuje zapytanie czatu do modelu z historią rozmowy, kontekstem SVL-364 i automatycznym fallbackiem."""
        target_url = (url or self.config.get_active_ollama_url()).rstrip("/")
        endpoint = f"{target_url}/api/chat"
        selected_model = model or self.config.get_active_model()
        messages = self._build_messages(prompt, system_prompt=system_prompt, history=history, images=images)
        options = self._runtime_options(prompt)

        last_err = ""
        for cand_model in self._candidate_models(selected_model, has_images=bool(images)):
            payload = {
                "model": cand_model,
                "messages": messages,
                "stream": False,
                "keep_alive": -1,
                "options": options,
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                endpoint,
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "JYN_OS-Ollama/2.6.0"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    resp_json = json.loads(response.read().decode("utf-8"))
                    message = resp_json.get("message", {})
                    content = str(message.get("content", "")).strip()
                    if content:
                        return {
                            "success": True,
                            "model": cand_model,
                            "substituted": cand_model != selected_model,
                            "endpoint": target_url,
                            "response": content,
                            "total_duration": resp_json.get("total_duration"),
                            "eval_count": resp_json.get("eval_count"),
                        }
                    last_err = f"Pusta odpowiedź z modelu {cand_model}"
            except urllib.error.HTTPError as he:
                try:
                    err_text = he.read().decode("utf-8")
                except Exception:
                    err_text = str(he)
                last_err = f"HTTP {he.code}: {err_text}"
                continue
            except Exception as e:
                last_err = f"Błąd połączenia z węzłem Ollama ({target_url}): {e}"
                break

        return {
            "success": False,
            "model": selected_model,
            "endpoint": target_url,
            "error": last_err or "Nie udało się uzyskać odpowiedzi z Ollamy.",
        }

    def chat_stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        url: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        timeout: float = 65.0,
    ) -> Generator[Dict[str, Any], None, None]:
        """Strumieniuje odpowiedź modelu token po tokenie w czasie rzeczywistym."""
        target_url = (url or self.config.get_active_ollama_url()).rstrip("/")
        endpoint = f"{target_url}/api/chat"
        selected_model = model or self.config.get_active_model()
        messages = self._build_messages(prompt, system_prompt=system_prompt, history=history)
        options = self._runtime_options(prompt)

        last_err = ""
        for cand_model in self._candidate_models(selected_model, has_images=False):
            payload = {
                "model": cand_model,
                "messages": messages,
                "stream": True,
                "keep_alive": -1,
                "options": options,
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                endpoint,
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "JYN_OS-Ollama/2.5.0"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    for raw_line in response:
                        line = raw_line.decode("utf-8", errors="replace").strip()
                        if not line:
                            continue
                        chunk = json.loads(line)
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            yield {"ok": True, "model": cand_model, "token": token, "done": False}
                        if chunk.get("done"):
                            yield {"ok": True, "model": cand_model, "token": "", "done": True}
                            return
                    return
            except urllib.error.HTTPError as he:
                try:
                    err_text = he.read().decode("utf-8")
                except Exception:
                    err_text = str(he)
                last_err = f"HTTP {he.code}: {err_text}"
                continue
            except Exception as e:
                last_err = f"Błąd połączenia z węzłem Ollama ({target_url}): {e}"
                break

        yield {"ok": False, "model": selected_model, "error": last_err or "Brak odpowiedzi z Ollamy.", "done": True}

    def chat_vision(
        self,
        prompt: str,
        image_path: str,
        model: Optional[str] = None,
        url: Optional[str] = None,
        timeout: float = 90.0,
    ) -> Dict[str, Any]:
        """Wygodne zapytanie multimodalne dla modelu wizyjnego (llama3.2-vision:11b)."""
        chosen_model = model or self.config.vision_model
        return self.chat(
            prompt=prompt,
            model=chosen_model,
            url=url,
            images=[image_path],
            timeout=timeout,
        )

    def install_local_ollama(self) -> Dict[str, Any]:
        """Weryfikuje lub instaluje lokalny silnik Ollama i upewnia się, że działa."""
        ollama_bin = shutil.which("ollama") or "/usr/local/bin/ollama"
        installed = os.path.isfile(ollama_bin) and os.access(ollama_bin, os.X_OK)

        if not installed:
            try:
                subprocess.run(
                    ["curl -fsSL https://ollama.com/install.sh | sh"],
                    shell=True,
                    check=True,
                    capture_output=True,
                    timeout=120,
                )
                ollama_bin = shutil.which("ollama") or "/usr/local/bin/ollama"
                installed = os.path.isfile(ollama_bin) and os.access(ollama_bin, os.X_OK)
            except Exception as e:
                return {"success": False, "error": f"Błąd instalacji Ollamy: {e}"}

        # Upewnij się, że lokalny węzeł na 11434 odpowiada
        status = self.check_node_status(self.config.local_ollama_url)
        if not status["online"] and installed:
            # Uruchomienie deamona w tle
            subprocess.Popen(
                [ollama_bin, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            import time
            time.sleep(1.5)
            status = self.check_node_status(self.config.local_ollama_url)

        return {
            "success": status["online"],
            "installed": installed,
            "version": status.get("version"),
            "models": status.get("installed_models", []),
            "binary": ollama_bin,
        }
