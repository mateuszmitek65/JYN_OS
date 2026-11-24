#!/usr/bin/env python3
"""
Automatyczny konfigurator i instalator środowiska dla JYN_OS (AI Studio & Devbox Ready).
Zapewnia natychmiastowe przygotowanie kluczy SSH, konfiguracji OpenSSH,
tokenów uwierzytelniających oraz uruchomienie zapasowej Ollamy SVL-364 w tle.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from JYN_OS.config import JynOSConfig
from JYN_OS.shell import JynOSShell


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.error):
        return False


def setup_ssh_environment() -> None:
    """Tworzy klucz Ed25519 dla statku SVL-364 oraz konfigurację OpenSSH."""
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    key_path = ssh_dir / "svl364_ed25519"
    pub_key_path = ssh_dir / "svl364_ed25519.pub"

    # 1. Generowanie pary kluczy, jeśli brak
    if not key_path.is_file():
        keygen = shutil.which("ssh-keygen")
        if keygen:
            print("🔑 Generowanie nowego klucza kryptograficznego Ed25519 dla SVL-364...")
            subprocess.run(
                [keygen, "-t", "ed25519", "-N", "", "-f", str(key_path), "-C", "jyn_os_svl364_root"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            key_path.chmod(0o600)
            if pub_key_path.is_file():
                pub_key_path.chmod(0o644)

    # 2. Dodanie do authorized_keys (umożliwia bezhasłowy dostęp loopback)
    auth_keys = ssh_dir / "authorized_keys"
    if pub_key_path.is_file():
        pub_content = pub_key_path.read_text(encoding="utf-8").strip()
        current_auth = auth_keys.read_text(encoding="utf-8") if auth_keys.is_file() else ""
        if pub_content and pub_content not in current_auth:
            with open(auth_keys, "a", encoding="utf-8") as f:
                f.write(f"\n{pub_content}\n")
            auth_keys.chmod(0o600)

    # 3. Konfiguracja profilu OpenSSH 'Ship' i 'SVL-364'
    config_file = ssh_dir / "config"
    config_d = ssh_dir / "config.d"
    config_d.mkdir(mode=0o700, parents=True, exist_ok=True)
    ship_conf = config_d / "svl-364.conf"

    ship_entry = (
        "# BEGIN SVL-364 (Ship)\n"
        "Host Ship SVL-364\n"
        "    HostName 127.0.0.1\n"
        "    Port 22\n"
        f"    User {os.environ.get('USER', 'root')}\n"
        f"    IdentityFile {key_path}\n"
        "    IdentitiesOnly yes\n"
        "    BatchMode yes\n"
        "    ConnectTimeout 10\n"
        "    ServerAliveInterval 15\n"
        "    ServerAliveCountMax 3\n"
        "    StrictHostKeyChecking accept-new\n"
        "# END SVL-364 (Ship)\n"
    )

    if not ship_conf.is_file():
        ship_conf.write_text(ship_entry, encoding="utf-8")
        ship_conf.chmod(0o600)

    # Upewnij się, że ~/.ssh/config zawiera Include config.d/*.conf
    existing_config = config_file.read_text(encoding="utf-8") if config_file.is_file() else ""
    if "Include config.d/*.conf" not in existing_config and "Host Ship" not in existing_config:
        with open(config_file, "a", encoding="utf-8") as f:
            f.write("Include config.d/*.conf\n\n" + ship_entry)
        config_file.chmod(0o600)


def setup_security_tokens() -> None:
    """Tworzy katalog data/ i niezbędne tokeny kryptograficzne jeśli ich brakuje."""
    data_dir = PROJECT_ROOT / "data"
    data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    operator_token_file = data_dir / "svl_operator_token.secret"
    if not operator_token_file.is_file():
        token = os.urandom(32).hex()
        operator_token_file.write_text(token, encoding="utf-8")
        operator_token_file.chmod(0o600)

    mcp_token_file = data_dir / "svl_mcp_token.secret"
    if not mcp_token_file.is_file():
        token = os.urandom(24).hex()
        mcp_token_file.write_text(token, encoding="utf-8")
        mcp_token_file.chmod(0o600)


def ensure_local_ollama_ready() -> None:
    """Weryfikuje lokalną instalację Ollamy (:11434) oraz obecność modelu wizyjnego."""
    ollama_bin = shutil.which("ollama") or "/usr/local/bin/ollama"
    if not os.path.isfile(ollama_bin):
        print("ℹ️  [JYN_OS] Brak binarki ollama w systemie. Możesz ją zainstalować komendą: curl -fsSL https://ollama.com/install.sh | sh")
        return

    if not is_port_open("127.0.0.1", 11434):
        print("⚡ [JYN_OS] Uruchamianie lokalnej usługi Ollama w tle (port 11434)...")
        subprocess.Popen(
            [ollama_bin, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        for _ in range(25):
            time.sleep(0.15)
            if is_port_open("127.0.0.1", 11434):
                break

    if is_port_open("127.0.0.1", 11434):
        print("🖥️  [JYN_OS] Lokalny węzeł Ollama (:11434) jest aktywny.")


def ensure_backup_ollama_running() -> None:
    """Uruchamia autonomiczny proces zapasowej Ollamy SVL-364 (:11435) jeśli port jest wolny."""
    if not is_port_open("127.0.0.1", 11435):
        print("⚡ [JYN_OS] Uruchamianie zapasowej instancji Ollama SVL-364 w tle (port 11435)...")
        script_path = PROJECT_ROOT / "JYN_OS" / "svl364_standalone_ollama.py"
        subprocess.Popen(
            [sys.executable, str(script_path), "11435"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        # Krótkie odczekanie na gniazdo
        for _ in range(20):
            time.sleep(0.15)
            if is_port_open("127.0.0.1", 11435):
                break


def main() -> int:
    print("\n" + "=" * 76)
    print(" 🛠️  [JYN_OS BOOTSTRAP] Automatyczna konfiguracja środowiska SVL-364...")
    print("=" * 76 + "\n")

    setup_ssh_environment()
    setup_security_tokens()
    ensure_local_ollama_ready()
    ensure_backup_ollama_running()

    cfg = JynOSConfig.load_from_env()
    shell = JynOSShell(cfg)
    shell.do_status("")

    print("\n✅ Środowisko JYN_OS jest w 100% gotowe.")
    print("👉 Uruchomienie konsoli:  ./jyn_os  lub  python3 main.py")
    print("👉 Uruchomienie audytu:   python3 main.py status\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
