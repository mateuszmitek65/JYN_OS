#!/usr/bin/env python3
"""Testy jednostkowe systemu klienta JYN_OS."""

import unittest
from pathlib import Path
import sys

# Dodaj główny katalog do ścieżki importu
current_dir = Path(__file__).resolve().parent
parent_dir = current_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from JYN_OS.config import JynOSConfig, SHIP_MODELS_CATALOG, resolve_auth_token
from JYN_OS.ssh_client import Svl364SshClient
from JYN_OS.ollama_client import SvlOllamaClient
from JYN_OS.mcp_client import SvlMcpClient
from JYN_OS.telemetry import SvlShipTelemetry


class TestJynOSClientSuite(unittest.TestCase):
    def setUp(self):
        self.cfg = JynOSConfig.load_from_env()

    def test_catalog_has_all_13_ship_models(self):
        self.assertEqual(len(SHIP_MODELS_CATALOG), 13)
        names = [m["name"] for m in SHIP_MODELS_CATALOG]
        self.assertIn("svl364-apex-uncensored:latest", names)
        self.assertIn("dolphin-mixtral:8x22b", names)
        self.assertIn("llama3.2-vision:90b", names)
        self.assertIn("llama3.2-vision:11b", names)
        self.assertIn("deepseek-r1:7b", names)
        self.assertIn("qwen2.5-coder:7b", names)

    def test_auth_token_resolver_finds_token(self):
        token = resolve_auth_token("http://127.0.0.1:3000/api/mcp/svl364")
        self.assertTrue(len(token) > 0, "Powinien odnaleźć poprawny token autoryzacji")

    def test_ssh_client_detects_ship_key_and_target(self):
        ssh = Svl364SshClient(self.cfg)
        status = ssh.get_key_status()
        self.assertTrue(status["private_key_exists"])
        self.assertEqual(ssh.config.ssh_profile, "Ship")

    def test_mcp_client_endpoints_defined(self):
        mcp = SvlMcpClient(self.cfg)
        endpoints = mcp.federated_endpoints
        self.assertIn("Universal MCP Hub (Ship 3334)", endpoints)
        self.assertIn("System MCP Gateway (3000/mcp/svl)", endpoints)
        self.assertIn("Ship MCP Gateway (3000/api/mcp/svl364)", endpoints)
        self.assertIn("Backend Python MCP (8085/mcp)", endpoints)

    def test_ollama_client_points_to_backup_ship_port(self):
        ollama = SvlOllamaClient(self.cfg)
        self.assertIn("11435", ollama.config.ship_ollama_url)
        self.assertEqual(ollama.config.ship_model, "svl364-apex-uncensored:latest")

    def test_local_ollama_and_vision_config(self):
        ollama = SvlOllamaClient(self.cfg)
        self.assertIn("11434", ollama.config.local_ollama_url)
        self.assertEqual(ollama.config.active_ollama_target, "local")
        self.assertEqual(ollama.config.get_active_ollama_url(), ollama.config.local_ollama_url)
        self.assertEqual(ollama.config.get_active_model(), "svl364-apex-uncensored:latest")

        ollama.config.set_active_target("ship")
        self.assertEqual(ollama.config.active_ollama_target, "ship")
        self.assertEqual(ollama.config.get_active_ollama_url(), ollama.config.ship_ollama_url)
        self.assertEqual(ollama.config.get_active_model(), "svl364-apex-uncensored:latest")


if __name__ == "__main__":
    unittest.main()
