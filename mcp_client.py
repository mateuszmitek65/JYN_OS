"""Klient federacji serwerów MCP (Model Context Protocol JSON-RPC 2.0) dla JYN_OS."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from .config import JynOSConfig, resolve_auth_token


class SvlMcpClient:
    """Komunikuje się z federacją serwerów MCP statku SVL-364 oraz jądra SVL CoreOS."""

    def __init__(self, config: Optional[JynOSConfig] = None):
        self.config = config or JynOSConfig.load_from_env()

    @property
    def federated_endpoints(self) -> Dict[str, str]:
        return {
            "Universal MCP Hub (Ship 3334)": self.config.mcp_hub_url,
            "System MCP Gateway (3000/mcp/svl)": self.config.mcp_system_url,
            "Ship MCP Gateway (3000/api/mcp/svl364)": self.config.mcp_ship_url,
            "Backend Python MCP (8085/mcp)": self.config.mcp_backend_url,
        }

    def _send_rpc(self, endpoint_url: str, method: str, params: Optional[Dict[str, Any]] = None, timeout: float = 3.0) -> Dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": "jyn-os-req-1",
            "method": method,
            "params": params or {},
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream;q=0.9, */*;q=0.8",
            "User-Agent": "JYN_OS-Client/2.4.0",
        }
        token = resolve_auth_token(endpoint_url)
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(
            endpoint_url,
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                if "data:" in raw:
                    for line in raw.splitlines():
                        if line.startswith("data:"):
                            return json.loads(line[5:].strip())
                return json.loads(raw)
        except urllib.error.HTTPError as he:
            try:
                err_body = he.read().decode("utf-8")
                parsed = json.loads(err_body)
                return parsed
            except Exception:
                return {"error": {"code": he.code, "message": f"HTTP {he.code}: {he.reason}"}}
        except Exception as e:
            return {"error": {"code": -32000, "message": str(e)}}

    def ping_endpoint(self, endpoint_url: str) -> Dict[str, Any]:
        """Testuje dostępność punktu końcowego MCP."""
        try:
            res = self._send_rpc(endpoint_url, "tools/list", {}, timeout=2.5)
            if "result" in res and "tools" in res["result"]:
                count = len(res["result"]["tools"])
                return {"online": True, "status": f"ONLINE ({count} narzędzi MCP)"}
            if "error" in res:
                if res["error"].get("code") in (-32601, -32600):
                    return {"online": True, "status": "ONLINE (RPC active)"}
                return {"online": False, "status": f"OFFLINE ({res['error'].get('message')})"}
            return {"online": True, "status": "ONLINE (RPC active)"}
        except Exception as e:
            return {"online": False, "status": f"OFFLINE ({e})"}

    def probe_all_endpoints(self) -> Dict[str, Dict[str, Any]]:
        """Sprawdza stan wszystkich serwerów MCP w federacji."""
        results = {}
        for name, url in self.federated_endpoints.items():
            probe = self.ping_endpoint(url)
            results[name] = {
                "url": url,
                "online": probe["online"],
                "status": probe["status"],
            }
        return results

    def list_tools(self, endpoint_url: Optional[str] = None) -> List[Dict[str, Any]]:
        """Pobiera listę narzędzi z wybranego lub ze wszystkich serwerów MCP."""
        target_urls = [endpoint_url] if endpoint_url else list(self.federated_endpoints.values())
        collected_tools: List[Dict[str, Any]] = []

        for url in target_urls:
            try:
                res = self._send_rpc(url, "tools/list", {}, timeout=3.5)
                tools = res.get("result", {}).get("tools", [])
                for t in tools:
                    collected_tools.append({
                        **t,
                        "_endpoint": url,
                    })
            except Exception:
                pass
        return collected_tools

    def call_tool(self, tool_name: str, arguments: Optional[Dict[str, Any]] = None, endpoint_url: Optional[str] = None) -> Dict[str, Any]:
        """Wywołuje narzędzie na wybranym serwerze MCP lub przeszukuje federację."""
        target_urls = [endpoint_url] if endpoint_url else [
            self.config.mcp_ship_url,
            self.config.mcp_hub_url,
            self.config.mcp_system_url,
            self.config.mcp_backend_url,
        ]

        for url in target_urls:
            params = {
                "name": tool_name,
                "arguments": arguments or {},
            }
            res = self._send_rpc(url, "tools/call", params, timeout=15.0)
            if "result" in res:
                return {"success": True, "endpoint": url, "result": res["result"]}
            if "error" in res and res["error"].get("code") != -32601:
                return {"success": False, "endpoint": url, "error": res["error"]}

        return {
            "success": False,
            "error": f"Narzędzie '{tool_name}' nie zostało odnalezione na żadnym aktywnym punkcie MCP federacji.",
        }
