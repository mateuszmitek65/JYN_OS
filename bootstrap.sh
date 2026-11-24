#!/usr/bin/env bash
# ==============================================================================
# JYN_OS Universal Bootstrap Script (AI Studio, Devbox, Linux, Cloud Shell)
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$DIR/.." && pwd)"

echo "================================================================================"
echo " 🚀 [JYN_OS BOOTSTRAP] Inicjalizacja systemu klienta statku SVL-364 Ebon Apex"
echo "================================================================================"

chmod +x "$DIR/jyn_os" "$DIR/main.py" "$DIR/bootstrap.py" "$DIR/svl364_standalone_ollama.py" 2>/dev/null || true

# Uruchomienie skryptu konfiguracji środowiska
python3 "$DIR/bootstrap.py"
