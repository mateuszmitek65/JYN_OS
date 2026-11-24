"""Moduł agregacji i prezentacji telemetrii statku SVL-364 dla JYN_OS."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from .config import JynOSConfig
from .ssh_client import Svl364SshClient


class SvlShipTelemetry:
    """Odczytuje i formatuje parametry operacyjne i telemetrię statku SVL-364."""

    def __init__(self, config: Optional[JynOSConfig] = None, ssh_client: Optional[Svl364SshClient] = None):
        self.config = config or JynOSConfig.load_from_env()
        self.ssh_client = ssh_client or Svl364SshClient(self.config)

    def fetch_api_telemetry(self) -> Dict[str, Any]:
        """Pobiera zarejestrowany stan telemetryczny z bramy systemu (port 3000 lub 8085)."""
        endpoints = [
            f"{self.config.gateway_url}/api/telemetry",
            f"{self.config.backend_url}/api/telemetry",
        ]
        for url in endpoints:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "JYN_OS-Telemetry/2.4.0"})
                with urllib.request.urlopen(req, timeout=1.5) as r:
                    return {"source": url, "available": True, "data": json.loads(r.read().decode("utf-8"))}
            except Exception:
                continue
        return {"source": "none", "available": False, "data": {}}

    def fetch_live_ssh_telemetry(self) -> Dict[str, Any]:
        """Pobiera parametry jądra bezpośrednio z hosta SVL-364 przez OpenSSH."""
        # Bezpieczne polecenie inspekcji zasobów systemowych Linux
        command = (
            "echo '===UNAME==='; uname -a; "
            "echo '===UPTIME==='; uptime; "
            "echo '===LOAD==='; cat /proc/loadavg 2>/dev/null || true; "
            "echo '===MEM==='; free -m 2>/dev/null || true; "
            "echo '===DISK==='; df -h / 2>/dev/null || true; "
            "echo '===NET==='; ip -brief address 2>/dev/null || hostname -I 2>/dev/null || true"
        )
        res = self.ssh_client.execute_command(command, timeout=5.0)
        if not res.success:
            return {
                "available": False,
                "error": res.stderr.strip() or f"Kod wyjścia SSH: {res.exit_code}",
                "host": res.host,
            }

        sections: Dict[str, str] = {}
        current_sec = "raw"
        for line in res.stdout.splitlines():
            if line.startswith("===") and line.endswith("==="):
                current_sec = line.strip("=").lower()
                sections[current_sec] = ""
            else:
                sections[current_sec] = sections.get(current_sec, "") + line + "\n"

        return {
            "available": True,
            "host": res.host,
            "uname": sections.get("uname", "").strip(),
            "uptime": sections.get("uptime", "").strip(),
            "load": sections.get("load", "").strip(),
            "memory": sections.get("mem", "").strip(),
            "disk": sections.get("disk", "").strip(),
            "network": sections.get("net", "").strip(),
        }

    def generate_full_report(self) -> Dict[str, Any]:
        """Tworzy zunifikowany raport stanu technicznego statku SVL-364."""
        ssh_telemetry = self.fetch_live_ssh_telemetry()
        api_telemetry = self.fetch_api_telemetry()
        return {
            "ship_id": "SVL-364 Ebon Apex",
            "ssh_status": ssh_telemetry,
            "api_gateway_telemetry": api_telemetry,
        }
