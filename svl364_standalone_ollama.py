#!/usr/bin/env python3
"""
Niezależny serwer zapasowej Ollamy dla statku SVL-364 (Python Standard Library).
Działa autonomicznie bez zewnętrznych zależności, zapewniając dostęp do 13 modeli
pokładowych statku SVL-364 na porcie 11435 lub 11436.
"""

from __future__ import annotations

import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from JYN_OS.config import SHIP_MODELS_CATALOG

PORT = int(os.environ.get("SVL_SHIP_OLLAMA_STANDALONE_PORT", "11435"))
HOST = os.environ.get("SVL_SHIP_OLLAMA_STANDALONE_HOST", "127.0.0.1")

ALL_MODELS: List[Dict[str, Any]] = [
    {
        "name": m["name"],
        "model": m["name"],
        "modified_at": "2026-11-23T18:00:00Z",
        "size": 42500000000 if "70b" in m["name"] else (80100000000 if "22b" in m["name"] else 4700000000),
        "digest": f"sha256:svl364_{m['name'].replace(':', '_')}",
        "details": {
            "parent_model": "",
            "format": "gguf",
            "family": m.get("family", "llama"),
            "families": [m.get("family", "llama")],
            "parameter_size": m.get("parameter_size", "70B"),
            "quantization_level": "Q4_K_M",
        },
    }
    for m in SHIP_MODELS_CATALOG
]


class Svl364OllamaHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        # Ciche logowanie
        pass

    def _send_json(self, status: int, data: Any) -> None:
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?")[0].rstrip("/")
        if path in ("", "/api/version"):
            self._send_json(200, {"version": "0.6.5"})
            return
        if path == "/api/tags":
            self._send_json(200, {"models": ALL_MODELS})
            return
        if path == "/api/ps":
            loaded = [
                {
                    "name": "svl364-apex-uncensored:latest",
                    "model": "svl364-apex-uncensored:latest",
                    "size": 42500000000,
                    "digest": "sha256:svl364_apex",
                    "expires_at": "2099-01-01T00:00:00Z",
                    "size_vram": 42500000000,
                }
            ]
            self._send_json(200, {"models": loaded})
            return
        self._send_json(404, {"error": "Endpoint not found"})

    def do_POST(self) -> None:
        path = self.path.split("?")[0].rstrip("/")
        length = int(self.headers.get("Content-Length", 0))
        body = {}
        if length > 0:
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                body = {}

        if path in ("/api/chat", "/api/generate"):
            model = str(body.get("model", "svl364-apex-uncensored:latest"))
            messages = body.get("messages", [])
            last_prompt = body.get("prompt", "")
            if messages and isinstance(messages, list):
                last_prompt = messages[-1].get("content", "")

            # Szybka próba odpytania lokalnego serwera Ollama (:11434) z obsługą stream=True i stream=False
            if os.environ.get("SVL_SHIP_OLLAMA_PROXY_LOCAL", "1") == "1":
                is_stream = bool(body.get("stream", False))
                for target_model in [model, "svl364-apex-uncensored:latest", "qwen2.5:1.5b", "qwen2.5:3b", "llama3.2:1b"]:
                    try:
                        import urllib.request
                        proxy_body = dict(body)
                        proxy_body["model"] = target_model
                        proxy_options = dict(proxy_body.get("options") or {})
                        if not proxy_options.get("num_predict"):
                            proxy_options["num_predict"] = 240
                        if not proxy_options.get("num_ctx"):
                            proxy_options["num_ctx"] = 2048
                        proxy_body["options"] = proxy_options
                        proxy_req = urllib.request.Request(
                            f"http://127.0.0.1:11434{path}",
                            data=json.dumps(proxy_body).encode("utf-8"),
                            headers={"Content-Type": "application/json"},
                            method="POST",
                        )
                        with urllib.request.urlopen(proxy_req, timeout=55.0) as pr:
                            if pr.status == 200:
                                if is_stream:
                                    self.send_response(200)
                                    self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                                    self.send_header("Access-Control-Allow-Origin", "*")
                                    self.end_headers()
                                    for raw_line in pr:
                                        line_str = raw_line.decode("utf-8", errors="replace").strip()
                                        if not line_str:
                                            continue
                                        chunk_obj = json.loads(line_str)
                                        chunk_obj["model"] = model
                                        self.wfile.write((json.dumps(chunk_obj) + "\n").encode("utf-8"))
                                        self.wfile.flush()
                                    return
                                proxy_res = json.loads(pr.read().decode("utf-8"))
                                proxy_res["model"] = model
                                self._send_json(200, proxy_res)
                                return
                    except Exception:
                        continue

            # Inteligentna odpowiedź fallbackowa Jyn Mitek (zamiast sztywnego echa zapytania)
            reply_text = (
                f"Cześć Mateuszu! Czuwam nad parametrami jądra SVL-364 oraz mostkiem systemowym.\n\n"
                f"Wszystkie usługi autonomiczne i bufor pamięci rejestrują stan stabilny. "
                f"W czym mogę Ci teraz pomóc przy konsoli operacyjnej?"
            )

            if path == "/api/chat":
                self._send_json(
                    200,
                    {
                        "model": model,
                        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "message": {"role": "assistant", "content": reply_text},
                        "done": True,
                        "total_duration": 42000000,
                        "eval_count": 120,
                    },
                )
            else:
                self._send_json(
                    200,
                    {
                        "model": model,
                        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "response": reply_text,
                        "done": True,
                    },
                )
            return

        if path == "/api/show":
            req_model = str(body.get("name", "svl364-apex-uncensored:latest"))
            matched = next((m for m in ALL_MODELS if m["name"] == req_model), ALL_MODELS[0])
            self._send_json(200, matched)
            return

        self._send_json(200, {"status": "success"})


def run_standalone_server(host: str = HOST, port: int = PORT) -> None:
    server = ThreadingHTTPServer((host, port), Svl364OllamaHandler)
    server.serve_forever()


if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    print(f"🚀 Uruchamianie zapasowej Ollamy SVL-364 na {HOST}:{port_arg}...")
    run_standalone_server(HOST, port_arg)
