"""Konfiguracja parametrów i węzłów sieciowych systemu klienta JYN_OS dla statku SVL-364."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


# Domyślny profil SSH oraz klucz kryptograficzny dedykowany dla statku SVL-364
DEFAULT_SSH_PROFILE = os.environ.get("SVL_SSH_TARGET", "Ship").strip() or "Ship"
def resolve_default_ssh_key() -> Path:
    if os.environ.get("SVL_SSH_KEY"):
        return Path(os.environ["SVL_SSH_KEY"])
    for p in (Path.home() / ".ssh" / "svl364_ed25519", Path("/home/antigravity/.ssh/svl364_ed25519"), Path("/root/.ssh/svl364_ed25519")):
        if p.is_file():
            return p
    return Path.home() / ".ssh" / "svl364_ed25519"

DEFAULT_SSH_PORT = int(os.environ.get("SVL_SSH_PORT", "22"))
DEFAULT_SSH_KEY_PATH = resolve_default_ssh_key()

# Domyślne adresy punktów końcowych MCP (Model Context Protocol JSON-RPC 2.0)
DEFAULT_MCP_UNIVERSAL_HUB = os.environ.get("SVL_MCP_UNIVERSAL_HUB", "http://127.0.0.1:3334/mcp")
DEFAULT_MCP_SYSTEM_GATEWAY = os.environ.get("SVL_MCP_SYSTEM", "http://127.0.0.1:3000/mcp/svl")
DEFAULT_MCP_SHIP_GATEWAY = os.environ.get("SVL_MCP_SHIP", "http://127.0.0.1:3000/api/mcp/svl364")
DEFAULT_MCP_BACKEND = os.environ.get("SVL_MCP_BACKEND", "http://127.0.0.1:8085/api/py/svl364/mcp")


def resolve_auth_token(endpoint_url: str = "") -> str:
    """Dynamicznie rozwiązuje token autoryzacyjny dla wybranego endpointu."""
    if "3334" in endpoint_url:
        token = os.environ.get("SVL_MCP_TOKEN") or os.environ.get("MCP_TOKEN")
        if token:
            return token.strip()
        fpath = Path(__file__).resolve().parent.parent / "data" / "svl_mcp_token.secret"
        if fpath.is_file():
            try:
                return fpath.read_text(encoding="utf-8").strip()
            except Exception:
                pass

    # Domyślny token dla bramy SVL / backendu
    token = os.environ.get("SVL_OPERATOR_TOKEN") or os.environ.get("MCP_TOKEN")
    if token:
        return token.strip()
    fpath = Path(__file__).resolve().parent.parent / "data" / "svl_operator_token.secret"
    if fpath.is_file():
        try:
            return fpath.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return ""

def _load_project_dotenv() -> None:
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.is_file():
        return
    try:
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            key = k.strip()
            val = v.strip().strip('"').strip("'")
            if key and key not in os.environ and val:
                os.environ[key] = val
    except Exception:
        pass


_load_project_dotenv()

DEFAULT_SHIP_OLLAMA_URL = os.environ.get("SVL_SHIP_OLLAMA_URL", "http://127.0.0.1:11435")
DEFAULT_LOCAL_OLLAMA_URL = os.environ.get("SVL_LOCAL_OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_SHIP_MODEL = os.environ.get("SVL_SHIP_MODEL", "svl364-apex-uncensored:latest")
DEFAULT_VISION_MODEL = os.environ.get("SVL_VISION_MODEL", "moondream:1.8b")
DEFAULT_LOCAL_MODEL = os.environ.get("SVL_LOCAL_MODEL", "svl364-apex-uncensored:latest")
DEFAULT_OLLAMA_TARGET = os.environ.get("SVL_OLLAMA_TARGET", "local")

# Brama API telemetrii i stanu SVL CoreOS
DEFAULT_GATEWAY_URL = os.environ.get("SVL_GATEWAY_URL", "http://127.0.0.1:3000")
DEFAULT_BACKEND_URL = os.environ.get("SVL_BACKEND_URL", "http://127.0.0.1:8085")

# Katalog 13 modeli pokładowych jednostki obliczeniowej statku SVL-364
SHIP_MODELS_CATALOG: List[Dict[str, Any]] = [
    {
        "name": "svl364-apex-uncensored:latest",
        "role": "Główny model Apex (Kwantyzacja Q4_K_M, kontekst 16k, niecenzurowany rdzeń)",
        "parameter_size": "70B",
        "family": "llama",
        "primary": True,
    },
    {
        "name": "dolphin-mixtral:8x22b",
        "role": "Wielkoformatowy model mieszaniny ekspertów (MoE, 141B)",
        "parameter_size": "141B",
        "family": "mixtral",
        "primary": False,
    },
    {
        "name": "dolphin-llama3:70b",
        "role": "Zaawansowany model analityczny i logiczny wysokiego rzędu",
        "parameter_size": "70B",
        "family": "llama",
        "primary": False,
    },
    {
        "name": "wizard-vicuna-uncensored:30b",
        "role": "Jednostka taktyczno-proceduralna do złożonych instrukcji",
        "parameter_size": "30B",
        "family": "llama",
        "primary": False,
    },
    {
        "name": "dolphin-mixtral:8x7b",
        "role": "Zbalansowany model MoE do szybkiego wnioskowania wielowątkowego",
        "parameter_size": "47B",
        "family": "mixtral",
        "primary": False,
    },
    {
        "name": "dolphin-llama3:8b-v2.9-q2_K",
        "role": "Ultralekki i zoptymalizowany model szybkiego reagowania",
        "parameter_size": "8B",
        "family": "llama",
        "primary": False,
    },
    {
        "name": "llama3.2-vision:90b",
        "role": "Multimodalny model wizyjny o dużej rozdzielczości sensorycznej",
        "parameter_size": "90B",
        "family": "mllama",
        "primary": False,
    },
    {
        "name": "llama3.2-vision:11b",
        "role": "Kompaktowa jednostka analizy obrazów, kamer i telemetrii optycznej",
        "parameter_size": "11B",
        "family": "mllama",
        "primary": False,
    },
    {
        "name": "deepseek-r1:7b",
        "role": "Jednostka łańcucha myślowego i głębokiego rozumowania (CoT)",
        "parameter_size": "7B",
        "family": "qwen2",
        "primary": False,
    },
    {
        "name": "qwen2.5:7b",
        "role": "Uniwersalny model wielojęzyczny do analizy dokumentacji i danych",
        "parameter_size": "7B",
        "family": "qwen2",
        "primary": False,
    },
    {
        "name": "qwen2.5-coder:7b",
        "role": "Specjalistyczny model do inżynierii oprogramowania i skryptów",
        "parameter_size": "7B",
        "family": "qwen2",
        "primary": False,
    },
    {
        "name": "llama3:8b",
        "role": "Standardowy zwinny model pomocniczy do zadań ogólnych",
        "parameter_size": "8B",
        "family": "llama",
        "primary": False,
    },
    {
        "name": "mistral:7b",
        "role": "Odporny silnik instrukcyjny do szybkiego routingu poleceń",
        "parameter_size": "7B",
        "family": "llama",
        "primary": False,
    },
]


@dataclass
class JynOSConfig:
    """Struktura parametrów środowiska uruchomieniowego klienta JYN_OS."""

    ssh_profile: str = DEFAULT_SSH_PROFILE
    ssh_port: int = DEFAULT_SSH_PORT
    ssh_key_path: Path = field(default_factory=lambda: DEFAULT_SSH_KEY_PATH)

    mcp_hub_url: str = DEFAULT_MCP_UNIVERSAL_HUB
    mcp_system_url: str = DEFAULT_MCP_SYSTEM_GATEWAY
    mcp_ship_url: str = DEFAULT_MCP_SHIP_GATEWAY
    mcp_backend_url: str = DEFAULT_MCP_BACKEND

    ship_ollama_url: str = DEFAULT_SHIP_OLLAMA_URL
    local_ollama_url: str = DEFAULT_LOCAL_OLLAMA_URL
    ship_model: str = DEFAULT_SHIP_MODEL
    local_model: str = DEFAULT_LOCAL_MODEL
    vision_model: str = DEFAULT_VISION_MODEL
    active_ollama_target: str = DEFAULT_OLLAMA_TARGET

    gateway_url: str = DEFAULT_GATEWAY_URL
    backend_url: str = DEFAULT_BACKEND_URL

    connect_timeout: float = 3.5
    command_timeout: float = 30.0

    def get_active_ollama_url(self) -> str:
        """Zwraca URL aktywnego węzła Ollama (domyślnie lokalny :11434 lub statku :11435)."""
        if self.active_ollama_target.lower() in ("ship", "remote", "11435"):
            return self.ship_ollama_url
        return self.local_ollama_url

    def get_active_model(self) -> str:
        """Zwraca domyślny model dla aktywnego węzła."""
        if self.active_ollama_target.lower() in ("ship", "remote", "11435"):
            return self.ship_model
        return self.local_model

    def set_active_target(self, target: str) -> None:
        """Przełącza aktywny cel Ollama pomiędzy 'local' a 'ship'."""
        cleaned = target.strip().lower()
        if cleaned in ("ship", "remote", "svl364", "11435"):
            self.active_ollama_target = "ship"
        else:
            self.active_ollama_target = "local"

    @classmethod
    def load_from_env(cls) -> "JynOSConfig":
        return cls()
