#!/usr/bin/env python3
"""
Główny punkt wejściowy systemu klienta JYN_OS dla statku SVL-364 Ebon Apex.

Uruchomienie w trybie interaktywnym:
    python3 main.py
    ./jyn_os

Uruchomienie w trybie pojedynczych poleceń CLI:
    python3 main.py status
    python3 main.py ssh "uname -a"
    python3 main.py telemetry
    python3 main.py ollama chat "Podaj raport gotowości"
    python3 main.py mcp ping
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Umożliwia bezpośrednie uruchomienie pliku lub import jako moduł
if __name__ == "__main__" and __package__ is None:
    current_dir = Path(__file__).resolve().parent
    sys.path.insert(0, str(current_dir.parent))
    from JYN_OS.config import JynOSConfig
    from JYN_OS.mcp_client import SvlMcpClient
    from JYN_OS.ollama_client import SvlOllamaClient
    from JYN_OS.shell import JynOSShell
    from JYN_OS.ssh_client import Svl364SshClient
    from JYN_OS.telemetry import SvlShipTelemetry
else:
    from .config import JynOSConfig
    from .mcp_client import SvlMcpClient
    from .ollama_client import SvlOllamaClient
    from .shell import JynOSShell
    from .ssh_client import Svl364SshClient
    from .telemetry import SvlShipTelemetry


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jyn_os",
        description="JYN_OS — System klienta i mostek operacyjny statku SVL-364 Ebon Apex (Operator: Mateusz Mitek)",
    )
    parser.add_argument(
        "--target",
        "-t",
        default=os.environ.get("SVL_SSH_TARGET", "Ship"),
        help="Profil lub alias OpenSSH docelowego statku (domyślnie: Ship)",
    )
    parser.add_argument(
        "--key",
        "-k",
        default=os.environ.get("SVL_SSH_KEY", str(Path.home() / ".ssh" / "svl364_ed25519")),
        help="Ścieżka do klucza prywatnego OpenSSH (domyślnie: ~/.ssh/svl364_ed25519)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Dostępne moduły poleceń JYN_OS")

    # shell
    subparsers.add_parser("shell", help="Uruchomienie interaktywnej powłoki JYN_OS TUI")

    # status
    subparsers.add_parser("status", help="Audyt stanu połączeń (SSH, MCP, Ollama :11435)")

    # telemetry
    subparsers.add_parser("telemetry", help="Pobranie i wyświetlenie telemetrii statku SVL-364")

    # ssh / exec
    ssh_p = subparsers.add_parser("ssh", help="Wykonanie polecenia lub sesja interaktywna na statku SVL-364")
    ssh_p.add_argument("cmd", nargs="?", default="", help="Polecenie powłoki zdalnej")

    exec_p = subparsers.add_parser("exec", help="Bezpośrednie wykonanie polecenia na statku przez SSH")
    exec_p.add_argument("cmd", help="Polecenie powłoki zdalnej")

    # ollama
    ollama_p = subparsers.add_parser("ollama", help="Interakcja z jednostką Ollama statku (:11435)")
    ollama_sub = ollama_p.add_subparsers(dest="ollama_action")
    ollama_sub.add_parser("status", help="Status węzła Ollama i zainstalowane modele")
    ollama_sub.add_parser("models", help="Katalog 13 modeli pokładowych SVL-364")
    ollama_sub.add_parser("list", help="Lista pobranych modeli na węźle statku")
    chat_p = ollama_sub.add_parser("chat", help="Wysłanie zapytania do modelu statku")
    chat_p.add_argument("prompt", help="Treść zapytania dla modelu AI")
    chat_p.add_argument("--model", "-m", default=None, help="Nazwa modelu (domyślnie: svl364-apex-uncensored:latest)")

    # mcp
    mcp_p = subparsers.add_parser("mcp", help="Komunikacja z federacją serwerów MCP")
    mcp_sub = mcp_p.add_subparsers(dest="mcp_action")
    mcp_sub.add_parser("ping", help="Ping serwerów MCP")
    mcp_sub.add_parser("list", help="Lista narzędzi w federacji MCP")
    call_p = mcp_sub.add_parser("call", help="Wywołanie narzędzia MCP")
    call_p.add_argument("tool", help="Nazwa narzędzia MCP")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    cfg = JynOSConfig.load_from_env()
    if args.target:
        cfg.ssh_profile = args.target
    if args.key:
        cfg.ssh_key_path = Path(args.key)

    # Domyślne uruchomienie powłoki, jeśli brak podkomendy
    if not args.command or args.command == "shell":
        shell = JynOSShell(cfg)
        try:
            shell.cmdloop()
            return 0
        except KeyboardInterrupt:
            print("\nRozłączono JYN_OS.")
            return 0

    shell = JynOSShell(cfg)

    if args.command == "status":
        shell.do_status("")
        return 0

    if args.command == "telemetry":
        shell.do_telemetry("")
        return 0

    if args.command in ("ssh", "exec"):
        cmd_text = getattr(args, "cmd", "")
        shell.do_ssh(cmd_text)
        return 0

    if args.command == "ollama":
        action = getattr(args, "ollama_action", "status") or "status"
        if action == "chat":
            prompt = getattr(args, "prompt", "")
            model = getattr(args, "model", None)
            if model:
                shell.config.ship_model = model
            shell.do_ollama(f"chat {prompt}")
        else:
            shell.do_ollama(action)
        return 0

    if args.command == "mcp":
        action = getattr(args, "mcp_action", "ping") or "ping"
        if action == "call":
            tool_name = getattr(args, "tool", "")
            shell.do_mcp(f"call {tool_name}")
        else:
            shell.do_mcp(action)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
