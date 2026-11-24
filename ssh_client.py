"""Klient OpenSSH dla statku SVL-364 (profil 'Ship', klucz ~/.ssh/svl364_ed25519)."""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from .config import JynOSConfig


@dataclass
class SshExecutionResult:
    success: bool
    command: str
    exit_code: int
    stdout: str
    stderr: str
    host: str


class Svl364SshClient:
    """Obsługuje bezpieczną komunikację SSH z pokładem statku SVL-364."""

    def __init__(self, config: Optional[JynOSConfig] = None):
        self.config = config or JynOSConfig.load_from_env()

    @property
    def ssh_binary(self) -> Optional[str]:
        return shutil.which("ssh")

    def check_key_exists(self) -> bool:
        return self.config.ssh_key_path.is_file()

    def get_key_status(self) -> Dict[str, Any]:
        key_path = self.config.ssh_key_path
        exists = key_path.is_file()
        pub_path = Path(str(key_path) + ".pub")
        pub_exists = pub_path.is_file()
        pub_content = ""
        if pub_exists:
            try:
                pub_content = pub_path.read_text(encoding="utf-8").strip()
            except Exception:
                pub_content = "[błąd odczytu klucza publicznego]"
        return {
            "key_path": str(key_path),
            "private_key_exists": exists,
            "public_key_exists": pub_exists,
            "public_key": pub_content,
        }

    def check_ssh_config_profile(self) -> Dict[str, Any]:
        """Sprawdza czy profil Ship lub SVL-364 jest zdefiniowany w konfiguracji OpenSSH."""
        binary = self.ssh_binary
        if binary:
            try:
                proc = subprocess.run(
                    [binary, "-G", self.config.ssh_profile],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=2.0,
                )
                if proc.returncode == 0:
                    matched = [
                        line.strip()
                        for line in proc.stdout.splitlines()
                        if line.startswith(("hostname ", "port ", "user ", "identityfile "))
                    ]
                    return {
                        "configured": True,
                        "profile": self.config.ssh_profile,
                        "config_file": "OpenSSH host database (Ship / SVL-364)",
                        "matched_lines": matched,
                    }
            except Exception:
                pass

        ssh_config_file = Path.home() / ".ssh" / "config"
        return {
            "configured": False,
            "profile": self.config.ssh_profile,
            "config_file": str(ssh_config_file),
            "matched_lines": [],
        }

    def test_tcp_connectivity(self, host: str = "127.0.0.1", port: Optional[int] = None, timeout: float = 1.0) -> bool:
        """Szybki test gniazda TCP na podany port."""
        target_port = port or self.config.ssh_port
        try:
            with socket.create_connection((host, target_port), timeout=timeout):
                return True
        except (OSError, socket.error):
            return False

    def execute_command(self, command: str, timeout: Optional[float] = None) -> SshExecutionResult:
        """Wykonuje polecenie przez OpenSSH na statku SVL-364."""
        binary = self.ssh_binary
        if not binary:
            return SshExecutionResult(
                success=False,
                command=command,
                exit_code=-1,
                stdout="",
                stderr="Błąd krytyczny: brak zainstalowanego klienta 'ssh' (OpenSSH) w bieżącym środowisku.",
                host=self.config.ssh_profile,
            )

        cmd_timeout = timeout or self.config.command_timeout

        ssh_args = [
            binary,
            "-o", "BatchMode=yes",
            "-o", f"ConnectTimeout={int(self.config.connect_timeout)}",
            "-o", "StrictHostKeyChecking=accept-new",
        ]

        if self.config.ssh_key_path.is_file():
            ssh_args.extend(["-i", str(self.config.ssh_key_path)])

        ssh_args.append(self.config.ssh_profile)
        ssh_args.append(command)

        try:
            proc = subprocess.run(
                ssh_args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=cmd_timeout,
            )
            return SshExecutionResult(
                success=(proc.returncode == 0),
                command=command,
                exit_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                host=self.config.ssh_profile,
            )
        except subprocess.TimeoutExpired:
            return SshExecutionResult(
                success=False,
                command=command,
                exit_code=124,
                stdout="",
                stderr=f"Przekroczono limit czasu oczekiwania ({cmd_timeout}s) na odpowiedź statku SVL-364.",
                host=self.config.ssh_profile,
            )
        except Exception as ex:
            return SshExecutionResult(
                success=False,
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Wyjątek podsystemu SSH: {ex}",
                host=self.config.ssh_profile,
            )

    def launch_interactive_shell(self) -> int:
        """Otwiera interaktywną powłokę terminalową ze statkiem SVL-364."""
        binary = self.ssh_binary
        if not binary:
            print("❌ Błąd: Brak klienta OpenSSH w systemie.")
            return 1

        ssh_args = [binary]
        if self.config.ssh_key_path.is_file():
            ssh_args.extend(["-i", str(self.config.ssh_key_path)])
        ssh_args.append(self.config.ssh_profile)

        print(f"🚀 [JYN_OS] Łączenie interaktywne z węzłem statku: {self.config.ssh_profile} ...")
        try:
            return subprocess.call(ssh_args)
        except KeyboardInterrupt:
            print("\nPrzerwano połączenie przez Operatora.")
            return 130
