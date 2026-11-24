"""Interaktywna powłoka systemowa JYN_OS (JYN_OS Interactive Shell) dla statku SVL-364."""

from __future__ import annotations

import cmd
import json
import os
import sys
import urllib.request
from typing import Optional

from .config import JynOSConfig, resolve_auth_token
from .mcp_client import SvlMcpClient
from .ollama_client import SvlOllamaClient
from .ssh_client import Svl364SshClient
from .telemetry import SvlShipTelemetry


# Kolory terminalowe ANSI
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


class JynOSShell(cmd.Cmd):
    """Główna powłoka interaktywna klienta JYN_OS dedykowana Operatorowi Mateuszowi Mitkowi."""

    intro = f"""
{CYAN}{BOLD}================================================================================{RESET}
{MAGENTA}{BOLD}   ✦ JYN_OS · KLIENT SYSTEMOWY I MOSTEK STATKU SVL-364 EBON APEX ✦{RESET}
{CYAN}   Rdzeń AI: Jyn Mitek (System_SI_1) · Operator: Mateusz Mitek{RESET}
{DIM}   Wpisz '{BOLD}help{RESET}{DIM}' aby wyświetlić komendy lub '{BOLD}status{RESET}{DIM}' dla stanu połączeń.{RESET}
{CYAN}{BOLD}================================================================================{RESET}
"""
    prompt = f"{CYAN}{BOLD}JYN_OS [SVL-364]{RESET}{BOLD}❯{RESET} "

    def __init__(self, config: Optional[JynOSConfig] = None):
        super().__init__()
        self.config = config or JynOSConfig.load_from_env()
        self.ssh = Svl364SshClient(self.config)
        self.mcp = SvlMcpClient(self.config)
        self.ollama = SvlOllamaClient(self.config)
        self.telemetry = SvlShipTelemetry(self.config, self.ssh)
        self.chat_history: list[dict[str, str]] = []

    def do_status(self, arg: str) -> None:
        """status — Wyświetla pełny audyt połączeń ze statkiem SVL-364 (SSH, MCP, Ollama :11435)."""
        print(f"\n{BOLD}🔍 [AUDYT INFRASTRUKTURY SVL-364 / JYN_OS]{RESET}\n")

        # 1. SSH
        key_info = self.ssh.get_key_status()
        profile_info = self.ssh.check_ssh_config_profile()
        print(f"{CYAN}{BOLD}1. Mostek OpenSSH (Statek SVL-364):{RESET}")
        print(f"   • Profil docelowy : {BOLD}{self.config.ssh_profile}{RESET} (port: {self.config.ssh_port})")
        print(f"   • Klucz Ed25519   : {key_info['key_path']} [{'Zainstalowany' if key_info['private_key_exists'] else 'Brak pliku'}]")
        print(f"   • Konfiguracja SSH: {profile_info['config_file']} [{'Skonfigurowany' if profile_info['configured'] else 'Nieskonfigurowany'}]")
        
        # Szybki test SSH
        probe = self.ssh.execute_command("uname -r", timeout=2.5)
        if probe.success:
            print(f"   • Połączenie SSH  : {GREEN}ONLINE{RESET} (Kernel: {probe.stdout.strip()})")
        else:
            print(f"   • Połączenie SSH  : {YELLOW}Czeka na zestawienie / nieosiągalny{RESET} ({probe.stderr.strip() or 'brak odpowiedzi'})")

        # 2. Federacja MCP
        print(f"\n{CYAN}{BOLD}2. Federacja Serwerów MCP (Model Context Protocol):{RESET}")
        mcp_probes = self.mcp.probe_all_endpoints()
        for name, info in mcp_probes.items():
            st_color = GREEN if info["online"] else RED
            print(f"   • {name:38}: {st_color}{info['status']}{RESET} ({info['url']})")

        # 3. Silnik Ollama
        print(f"\n{CYAN}{BOLD}3. Jednostka Obliczeniowa AI Ollama:{RESET}")
        ship_ollama = self.ollama.check_node_status(self.config.ship_ollama_url)
        st_color = GREEN if ship_ollama["online"] else RED
        status_txt = f"ONLINE (v{ship_ollama['version']})" if ship_ollama["online"] else "OFFLINE"
        print(f"   • Pokładowa Ollama (:11435)        : {st_color}{status_txt}{RESET}")
        print(f"     └─ Model domyślny                : {BOLD}{self.config.ship_model}{RESET} [{'OBECNY' if ship_ollama['apex_present'] else 'Brak'}]")
        if ship_ollama["installed_models"]:
            print(f"     └─ Zainstalowane modele          : {', '.join(ship_ollama['installed_models'][:6])}")

        local_ollama = self.ollama.check_node_status(self.config.local_ollama_url)
        loc_color = GREEN if local_ollama["online"] else YELLOW
        loc_txt = f"ONLINE (v{local_ollama['version']})" if local_ollama["online"] else "OFFLINE"
        print(f"   • Lokalna Ollama (:11434)          : {loc_color}{loc_txt}{RESET}")
        if local_ollama["installed_models"]:
            print(f"     └─ Dostępne modele               : {', '.join(local_ollama['installed_models'])}")
            print(f"     └─ Model Vision ({self.config.vision_model}): {'✅ ZAINSTALOWANY I GOTOWY' if local_ollama['vision_present'] else 'Brak'}")
        print()

    def do_ssh(self, arg: str) -> None:
        """ssh [polecenie] — Wykonuje polecenie na statku SVL-364 lub otwiera interaktywną powłokę (gdy bez argumentu)."""
        cmd_text = arg.strip()
        if not cmd_text:
            print(f"{YELLOW}Uruchamianie bezpośredniej sesji terminalowej SSH ze statkiem...{RESET}")
            self.ssh.launch_interactive_shell()
            return

        print(f"{DIM}Wykonywanie na statku [{self.config.ssh_profile}]: {cmd_text}{RESET}")
        res = self.ssh.execute_command(cmd_text)
        if res.success:
            print(res.stdout, end="" if res.stdout.endswith("\n") else "\n")
        else:
            print(f"{RED}❌ Błąd wykonania (kod {res.exit_code}):{RESET}\n{res.stderr}")

    def do_exec(self, arg: str) -> None:
        """exec <polecenie> — Bezpośrednie wykonanie polecenia na statku SVL-364 przez SSH."""
        cmd_text = arg.strip()
        if not cmd_text:
            print(f"{YELLOW}Użycie: exec <komenda linux>{RESET}")
            return
        self.do_ssh(cmd_text)

    def do_telemetry(self, arg: str) -> None:
        """telemetry — Pobiera i wyświetla aktualną telemetrię techniczną statku SVL-364."""
        print(f"\n{CYAN}{BOLD}🛰️  [TELEMETRIA POKŁADOWA STATKU SVL-364 EBON APEX]{RESET}\n")
        live = self.telemetry.fetch_live_ssh_telemetry()
        if live["available"]:
            print(f"• Host     : {GREEN}{live['host']}{RESET}")
            print(f"• Kernel   : {live['uname']}")
            print(f"• Uptime   : {live['uptime']}")
            print(f"• Obciążenie: {live['load']}")
            print(f"\n{BOLD}Pamięć RAM:{RESET}\n{live['memory']}\n")
            print(f"{BOLD}Dysk główny (/):{RESET}\n{live['disk']}\n")
            print(f"{BOLD}Interfejsy sieciowe:{RESET}\n{live['network']}\n")
        else:
            print(f"{YELLOW}⚠️  Brak bezpośredniego odczytu z węzła SSH:{RESET} {live['error']}")
            print("Sprawdzam buforowaną telemetrię z bramy API...")
            api = self.telemetry.fetch_api_telemetry()
            if api["available"]:
                print(f"{GREEN}Pobrano dane telemetryczne z: {api['source']}{RESET}")
                print(api["data"])
            else:
                print(f"{RED}Brak dostępnych danych telemetrycznych.{RESET}")
        print()

    def do_ollama(self, arg: str) -> None:
        """ollama [status|target|model|vision|pull|install|chat|list|catalog] [argumenty] — Zarządzanie lokalną i pokładową Ollamą."""
        parts = arg.strip().split(maxsplit=1)
        subcmd = parts[0].lower() if parts else "status"
        extra = parts[1] if len(parts) > 1 else ""

        if subcmd == "status":
            target = extra.strip().lower() if extra else ""
            print(f"\n{CYAN}{BOLD}--- Stan węzłów obliczeniowych Ollama ---{RESET}")
            print(f"Aktywny cel JYN_OS: {BOLD}{self.config.active_ollama_target.upper()}{RESET} (domyślny model: {BOLD}{self.config.get_active_model()}{RESET})\n")

            if target in ("", "local", "11434"):
                loc_st = self.ollama.check_node_status(self.config.local_ollama_url)
                print(f"🖥️  {BOLD}Lokalny węzeł Ollama (:11434):{RESET}")
                print(f"   └─ Status        : {GREEN if loc_st['online'] else RED}{'ONLINE' if loc_st['online'] else 'OFFLINE'}{RESET}")
                if loc_st["online"]:
                    print(f"   └─ Wersja        : v{loc_st['version']}")
                    print(f"   └─ Modele        : {', '.join(loc_st['installed_models']) or 'brak zainstalowanych modeli'}")
                    print(f"   └─ Model Vision  : {'✅ Dostępny' if loc_st['vision_present'] else 'Brak (uruchom: ollama pull llama3.2-vision:11b)'}")
                else:
                    print(f"   └─ Diagnostyka   : {loc_st['error']} (uruchom: ollama install)")
                print()

            if target in ("", "ship", "11435"):
                ship_st = self.ollama.check_node_status(self.config.ship_ollama_url)
                print(f"🛰️  {BOLD}Węzeł pokładowy SVL-364 (:11435):{RESET}")
                print(f"   └─ Status        : {GREEN if ship_st['online'] else RED}{'ONLINE' if ship_st['online'] else 'OFFLINE'}{RESET}")
                if ship_st["online"]:
                    print(f"   └─ Wersja        : v{ship_st['version']}")
                    print(f"   └─ Modele        : {', '.join(ship_st['installed_models'][:6])} (łącznie: {len(ship_st['installed_models'])})")
                    print(f"   └─ Model Apex    : {'✅ Dostępny' if ship_st['apex_present'] else 'Brak'}")
                else:
                    print(f"   └─ Diagnostyka   : {ship_st['error']}")
                print()

        elif subcmd in ("target", "switch"):
            tgt = extra.strip().lower()
            if tgt in ("local", "11434"):
                self.config.set_active_target("local")
                print(f"\n{GREEN}✔ Przełączono aktywny węzeł Ollama na: LOKALNY (:11434){RESET}")
                print(f"Aktywny model: {self.config.get_active_model()}\n")
            elif tgt in ("ship", "11435", "remote"):
                self.config.set_active_target("ship")
                print(f"\n{GREEN}✔ Przełączono aktywny węzeł Ollama na: POKŁADOWY SVL-364 (:11435){RESET}")
                print(f"Aktywny model: {self.config.get_active_model()}\n")
            else:
                print(f"{YELLOW}Podaj cel przełączenia: ollama target local  LUB  ollama target ship{RESET}")

        elif subcmd in ("model", "use"):
            chosen = extra.strip()
            if not chosen:
                print(f"Bieżący aktywny model: {BOLD}{self.config.get_active_model()}{RESET}")
                print(f"Użycie: ollama model <nazwa_modelu> (np. ollama model llama3.2-vision:11b)")
                return
            if self.config.active_ollama_target == "local":
                self.config.local_model = chosen
            else:
                self.config.ship_model = chosen
            print(f"\n{GREEN}✔ Ustawiono aktywny model na: {BOLD}{chosen}{RESET}\n")

        elif subcmd == "install":
            print(f"\n{CYAN}⚡ Weryfikacja i instalacja lokalnego silnika Ollama...{RESET}")
            res = self.ollama.install_local_ollama()
            if res.get("success"):
                print(f"{GREEN}✔ Lokalny silnik Ollama jest aktywny i odpowiada na porcie 11434.{RESET}")
                print(f"Wersja: v{res.get('version')} | Plik binarny: {res.get('binary')}")
                print(f"Zainstalowane modele: {', '.join(res.get('models', [])) or 'brak'}\n")
            else:
                print(f"{RED}❌ Błąd podczas uruchamiania/instalacji lokalnej Ollamy:{RESET} {res.get('error')}\n")

        elif subcmd == "pull":
            model_to_pull = extra.strip() or self.config.vision_model
            print(f"\n{CYAN}⏳ Pobieranie modelu '{model_to_pull}' do lokalnego węzła Ollama (:11434)...{RESET}")
            res = self.ollama.pull_model(model_to_pull, url=self.config.local_ollama_url)
            if res.get("success"):
                print(f"{GREEN}✔ Model {model_to_pull} został pomyślnie zainstalowany i jest gotowy do pracy!{RESET}\n")
            else:
                print(f"{RED}❌ Błąd pobierania:{RESET} {res.get('error')}\n")

        elif subcmd in ("vision", "image"):
            vparts = extra.strip().split(maxsplit=1)
            if not vparts:
                print(f"{YELLOW}Użycie: ollama vision <ścieżka_do_obrazka> [pytanie]{RESET}")
                print(f"Przykład: ollama vision /home/antigravity/foto.jpg 'Co znajduje się na zdjęciu?'")
                return
            img_path = vparts[0]
            vprompt = vparts[1] if len(vparts) > 1 else "Przeanalizuj ten obraz ze statku i opisz szczegółowo co na nim widać."

            print(f"\n{CYAN}👁️ [Analiza multimodalna modelem: {self.config.vision_model} przez port 11434...]{RESET}\n")
            res = self.ollama.chat_vision(prompt=vprompt, image_path=img_path, url=self.config.local_ollama_url)
            if res.get("success"):
                print(f"{GREEN}{BOLD}✦ Raport Wizyjny [{res['model']}]:{RESET}\n{res['response']}\n")
            else:
                print(f"{RED}❌ Błąd analizy wizyjnej:{RESET} {res.get('error')}\n")

        elif subcmd in ("catalog", "models"):
            print(f"\n{CYAN}{BOLD}Katalog 13 modeli pokładowych statku SVL-364:{RESET}\n")
            catalog = self.ollama.get_ship_models_catalog()
            for i, m in enumerate(catalog, 1):
                flag = f"{GREEN}★ GŁÓWNY{RESET}" if m.get("primary") else ("👁️ VISION" if "vision" in m["name"] else "  ")
                print(f"{i:2}. {BOLD}{m['name']:32}{RESET} [{m['parameter_size']:4}] {flag}")
                print(f"    Rola: {m['role']}")
            print()

        elif subcmd in ("chat", "ask"):
            prompt = extra.strip()
            if not prompt:
                print(f"{YELLOW}Podaj treść zapytania, np.: ollama chat 'Raport gotowości statku'{RESET}")
                return
            self._run_streaming_chat(prompt)

        elif subcmd in ("clear", "reset-chat"):
            self.chat_history.clear()
            print(f"\n{GREEN}✔ Wyczyszczono historię rozmowy sesji JYN_OS.{RESET}\n")

        elif subcmd == "list":
            target = extra.strip().lower()
            url = self.config.local_ollama_url if target in ("local", "11434") else self.config.ship_ollama_url
            label = "Lokalny (:11434)" if target in ("local", "11434") else "Pokładowy SVL-364 (:11435)"
            st = self.ollama.check_node_status(url)
            if st["online"]:
                print(f"\nZainstalowane modele na węźle {label} ({len(st['installed_models'])}):")
                for m in st["installed_models"]:
                    print(f" • {m}")
                print()
            else:
                print(f"{RED}Węzeł Ollama {label} nie odpowiada: {st['error']}{RESET}")

        else:
            print(f"{YELLOW}Dostępne polecenia: status, target [local|ship], model [nazwa], vision <obraz> [tekst], install, pull [model], list, catalog, chat <tekst>, clear{RESET}")

    def do_mcp(self, arg: str) -> None:
        """mcp [ping|list|call <nazwa_narzędzia>] — Diagnostyka i sterowanie federacją serwerów MCP."""
        parts = arg.strip().split(maxsplit=1)
        subcmd = parts[0].lower() if parts else "ping"
        extra = parts[1] if len(parts) > 1 else ""

        if subcmd == "ping":
            print(f"\n{CYAN}{BOLD}Odpytywanie węzłów MCP:{RESET}")
            probes = self.mcp.probe_all_endpoints()
            for name, info in probes.items():
                col = GREEN if info["online"] else RED
                print(f" • {name:36}: {col}{info['status']}{RESET}")
            print()

        elif subcmd == "list":
            print(f"\n{CYAN}{BOLD}Wykrywanie narzędzi MCP w federacji...{RESET}")
            tools = self.mcp.list_tools()
            if not tools:
                print(f"{YELLOW}Brak aktywnych narzędzi (serwery MCP mogą być offline lub wymagać autoryzacji).{RESET}\n")
                return
            print(f"Odnaleziono {len(tools)} narzędzi:\n")
            for t in tools:
                print(f" • {BOLD}{t.get('name')}{RESET} ({t.get('_endpoint')})")
                print(f"   Opis: {t.get('description', 'Brak opisu')}")
            print()

        elif subcmd == "call":
            tool_name = extra.strip()
            if not tool_name:
                print(f"{YELLOW}Użycie: mcp call <nazwa_narzędzia>{RESET}")
                return
            print(f"Wywoływanie narzędzia MCP: {tool_name} ...")
            res = self.mcp.call_tool(tool_name)
            if res.get("success"):
                print(f"{GREEN}Wynik wywołania:{RESET}\n{res.get('result')}")
            else:
                print(f"{RED}Błąd:{RESET} {res.get('error')}")

        else:
            print(f"{YELLOW}Dostępne opcje mcp: ping, list, call <narzędzie>{RESET}")

    def do_reset(self, arg: str) -> None:
        """reset — Przywraca ustawienia fabryczne (Factory Reset) systemu SVL CoreOS 2 i JYN_OS."""
        parts = arg.strip().lower()
        if parts not in ("yes", "y", "tak", "force", "--force", "-f"):
            confirm = input(f"{YELLOW}⚠️  Czy na pewno chcesz przywrócić ustawienia fabryczne systemu SVL CoreOS 2? [t/N]: {RESET}").strip().lower()
            if confirm not in ("t", "tak", "y", "yes"):
                print("Anulowano przywracanie ustawień fabrycznych.")
                return

        print(f"\n{CYAN}⚙️  [JYN_OS] Wykonywanie procedury Factory Reset...{RESET}")
        token = resolve_auth_token(self.config.gateway_url)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "X-SVL-Operator-Token": token,
        }
        endpoints = [
            f"{self.config.gateway_url}/api/kernel/factory-reset",
            f"{self.config.backend_url}/api/py/kernel/factory-reset",
        ]
        success = False
        res_data = {}
        for url in endpoints:
            try:
                req = urllib.request.Request(url, data=json.dumps({"operatorToken": token}).encode(), headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=10.0) as r:
                    res_data = json.loads(r.read().decode())
                    if res_data.get("ok"):
                        success = True
                        break
            except Exception:
                continue

        if success:
            print(f"{GREEN}{BOLD}✅ Ustawienia fabryczne zostały pomyślnie przywrócone!{RESET}")
            print(f" • Status           : {res_data.get('status')}")
            print(f" • Nowa rewizja     : {res_data.get('serverRevision')}")
            print(f" • Zainicjalizowane : {res_data.get('modulesCount', 'komplet')} modułów systemowych")
            print(f"\nUruchamiam automatyczny audyt stanu po resecie:")
            self.do_status("")
        else:
            print(f"{RED}❌ Błąd podczas wykonywania Factory Reset przez API. Sprawdź działanie bramy i jądra.{RESET}")

    def do_factory_reset(self, arg: str) -> None:
        """factory-reset — Alias do polecenia reset."""
        self.do_reset(arg)

    def do_purge_buffer(self, arg: str) -> None:
        """purge_buffer [clean] — Oczyszcza zapchane bufory systemowe, outbox, historię terminali i pamięć podręczną."""
        print(f"\n{CYAN}🧹 [JYN_OS] Oczyszczanie i optymalizacja buforów systemowych...{RESET}")
        token = resolve_auth_token(self.config.gateway_url)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "X-SVL-Operator-Token": token,
        }
        endpoints = [
            f"{self.config.gateway_url}/api/system/buffer/purge",
            f"{self.config.backend_url}/api/py/kernel/buffer-purge",
        ]
        success = False
        res_data = {}
        for url in endpoints:
            try:
                req = urllib.request.Request(url, data=json.dumps({"operatorToken": token}).encode(), headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=10.0) as r:
                    res_data = json.loads(r.read().decode())
                    if res_data.get("ok"):
                        success = True
                        break
            except Exception:
                continue

        if success:
            stats = res_data.get("stats", {})
            print(f"{GREEN}{BOLD}✅ Bufory systemowe zostały pomyślnie oczyszczone!{RESET}")
            print(f" • Terminale usunięte: {stats.get('terminal_history_cleared', 0)} wpisów")
            print(f" • Zdarzenia usunięte: {stats.get('system_events_cleared', 0)} zdarzeń")
            print(f" • Outbox odciążony   : {stats.get('sync_outbox_cleared', 0)} rekordów")
            print(f" • Rewizja jądra     : {res_data.get('serverRevision')}")
        else:
            print(f"{RED}❌ Nie udało się oczyścić buforów przez API.{RESET}")

    def do_clean(self, arg: str) -> None:
        """clean — Alias do polecenia purge_buffer."""
        self.do_purge_buffer(arg)


    def do_clear(self, arg: str) -> None:
        """clear — Czyści ekran terminala."""
        os.system("clear" if os.name == "posix" else "cls")

    def do_exit(self, arg: str) -> bool:
        """exit — Zamyka powłokę klienta JYN_OS."""
        print(f"{CYAN}Rozłączono sesję klienta JYN_OS. Do usłyszenia, Operatorze Mateuszu.{RESET}")
        return True

    def do_quit(self, arg: str) -> bool:
        """quit — Zamyka powłokę klienta JYN_OS."""
        return self.do_exit(arg)

    def _run_streaming_chat(self, prompt: str) -> None:
        cleaned = prompt.strip().strip("'").strip('"')
        if not cleaned:
            return
        active_url = self.config.get_active_ollama_url()
        active_mod = self.config.get_active_model()
        print(f"\n{CYAN}[Jyn Mitek · {active_mod} ({active_url})]{RESET}")

        collected: list[str] = []
        used_model = active_mod
        header_printed = False

        for chunk in self.ollama.chat_stream(
            cleaned,
            model=active_mod,
            url=active_url,
            history=self.chat_history,
        ):
            if not chunk.get("ok"):
                print(f"{RED}❌ Błąd komunikacji z modelem:{RESET} {chunk.get('error')}\n")
                return
            used_model = chunk.get("model", used_model)
            tok = chunk.get("token", "")
            if tok:
                if not header_printed:
                    sys.stdout.write(f"{GREEN}{BOLD}✦ Jyn [{used_model}]:{RESET} ")
                    header_printed = True
                sys.stdout.write(tok)
                sys.stdout.flush()
                collected.append(tok)

        sys.stdout.write("\n\n")
        sys.stdout.flush()
        full_reply = "".join(collected).strip()
        if full_reply:
            self.chat_history.append({"role": "user", "content": cleaned})
            self.chat_history.append({"role": "assistant", "content": full_reply})
            if len(self.chat_history) > 20:
                self.chat_history = self.chat_history[-20:]

    def do_chat(self, arg: str) -> None:
        """chat <wiadomość> — Bezpośrednia rozmowa z Jyn Mitek (strumieniowanie na żywo + pamięć sesji)."""
        if not arg.strip():
            print(f"{YELLOW}Użycie: chat <wiadomość do Jyn>{RESET}")
            return
        self._run_streaming_chat(arg)

    def do_jyn(self, arg: str) -> None:
        """jyn <wiadomość> — Alias bezpośredniej rozmowy z Jyn Mitek."""
        self.do_chat(arg)

    def default(self, line: str) -> None:
        """Kieruje wypowiedzi w języku naturalnym bezpośrednio do czatu Jyn Mitek."""
        cleaned = line.strip()
        if not cleaned:
            return
        if " " in cleaned or cleaned.endswith("?"):
            self._run_streaming_chat(cleaned)
        else:
            print(f"{YELLOW}Nieznane polecenie '{cleaned}'. Wpisz 'help' lub zadaj pytanie dla Jyn (np. chat {cleaned}).{RESET}")

    def emptyline(self) -> bool:
        """Nie powtarzaj ostatniego polecenia po wciśnięciu Enter."""
        return False

