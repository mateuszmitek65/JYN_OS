# JYN_OS — System Klienta Statku SVL-364 Ebon Apex

**Dedykowany dla:** Operator Mateusz Mitek  
**Rdzeń systemu:** Jyn Mitek (`System_SI_1`)  
**Repozytorium:** `Rush47/SVL_Core`  
**Lokalizacja:** `SVL_Core/JYN_OS/`

---

## 1. Przegląd i Architektura

**JYN_OS** to autonomiczny system klienta i mostek operacyjny umożliwiający bezpośrednie, bezpieczne łączenie się ze statkiem **SVL-364 Ebon Apex** jako autoryzowany klient. 

System integruje cztery kluczowe warstwy łączności pokładowej:
1. **Mostek OpenSSH (`Ship` · port 22)**: Wykonywanie poleceń w powłoce Linux z uprawnieniami ROOT na statku (`~/.ssh/svl364_ed25519`).
2. **Telemetria Czasu Rzeczywistego**: Odczyt obciążenia CPU, pamięci RAM, partycji dyskowych oraz interfejsów sieciowych statku SVL-364.
3. **Zapasowa Jednostka AI Ollama (port 11435)**: Tunelowane połączenie do silnika LLM statku SVL-364 z dostępem do pełnego katalogu **13 modeli pokładowych**, na czele z `svl364-apex-uncensored:latest` (70B).
4. **Federacja Serwerów MCP (Model Context Protocol)**: Bezpośrednia komunikacja JSON-RPC 2.0 z 4 węzłami MCP:
   - **Universal MCP Hub**: `http://127.0.0.1:3334/mcp` (31 narzędzi systemowych)
   - **System MCP Gateway**: `http://127.0.0.1:3000/mcp/svl` (25 narzędzi SVL Core)
   - **Ship MCP Gateway**: `http://127.0.0.1:3000/api/mcp/svl364` (20 narzędzi statku)
   - **Backend Python MCP**: `http://127.0.0.1:8085/api/py/svl364/mcp` (20 narzędzi telemetryczno-zarządczych)

---

## 2. Struktura Modułów

```text
JYN_OS/
├── README.md            # Niniejsza dokumentacja operacyjna
├── __init__.py          # Pakiet Pythona
├── config.py            # Konfiguracja adresów, portów, 13 modeli i tokenów
├── jyn_os               # Główny skrypt wykonywalny CLI/TUI (chmod +x)
├── main.py              # Punkt wejściowy parsera CLI i uruchamiania
├── mcp_client.py        # Klient federacji MCP (JSON-RPC 2.0 + Streamable HTTP)
├── ollama_client.py     # Klient pokładowego węzła Ollama (:11435)
├── shell.py             # Interaktywna powłoka JYN_OS Shell (cmd.Cmd)
├── ssh_client.py        # Klient OpenSSH dla profilu Ship / SVL-364
└── telemetry.py         # Analizator i agregator telemetrii jądra statku
```

---

## 3. Wymagania Wstępne

- **Python**: 3.9+ (zalecany Python 3.12, wbudowana biblioteka standardowa — brak zewnętrznych zależności pip).
- **OpenSSH Client**: `ssh` dostępny w zmiennej `$PATH`.
- **Klucz autoryzacyjny**: `~/.ssh/svl364_ed25519` oraz wpis hosta `Ship` w konfiguracji OpenSSH.
- **Aktywne usługi SVL CoreOS**:
  - Brama `server.ts` na porcie `3000`
  - Tunel zapasowej Ollamy SVL-364 na porcie `11435`
  - Universal MCP Hub na porcie `3334`

---

## 4. Sposób Uruchomienia

### Krok 1. Przejście do katalogu JYN_OS
```bash
cd /home/antigravity/Rush47/SVL_Core/JYN_OS
```

### Krok 2. Uruchomienie interaktywnej powłoki (TUI)
Możesz uruchomić system za pomocą pliku wykonywalnego `./jyn_os` lub przez `python3 main.py`:

```bash
./jyn_os
```
lub:
```bash
python3 main.py
```

Po uruchomieniu pojawi się interaktywny znak zachęty:
```text
╔════════════════════════════════════════════════════════════════════════╗
║                   JYN_OS · SVL-364 CLIENT CONSOLE                      ║
║            Mostek Operacyjny Klienta Statku SVL-364 Ebon Apex          ║
║               Zarządca: Jyn Mitek (System_SI_1) · ROOT                 ║
╚════════════════════════════════════════════════════════════════════════╝
JYN_OS (Ship:SVL-364) > 
```

Wpisz `help` lub `?`, aby wyświetlić listę wbudowanych poleceń:
- `status` — Kompletny audyt stanu (OpenSSH, 4 serwery MCP, Ollama :11435).
- `telemetry` — Aktualna telemetria techniczna (RAM, dysk, obciążenie, interfejsy).
- `ssh [komenda]` — Uruchomienie polecenia na statku lub wejście do sesji zdalnej.
- `exec <komenda>` — Bezpośrednie wykonanie polecenia bash na statku SVL-364.
- `ollama status` — Status węzła Ollama na statku i załadowane modele.
- `ollama catalog` — Wyświetlenie pełnego katalogu 13 modeli pokładowych.
- `ollama chat <zapytanie>` — Wysłanie zapytania do modelu `svl364-apex-uncensored:latest`.
- `mcp ping` — Skan stanu wszystkich 4 serwerów w federacji MCP.
- `mcp list` — Pobranie i wylistowanie wszystkich dostępnych narzędzi MCP.
- `mcp call <narzędzie>` — Wywołanie określonego narzędzia MCP.
- `clear` — Czyszczenie ekranu terminala.
- `exit` / `quit` — Bezpieczne odłączenie klienta JYN_OS.

---

### Krok 3. Uruchamianie w trybie pojedynczych poleceń CLI (Headless / Skrypty)

System JYN_OS może być również wywoływany w trybie wsadowym bez wchodzenia do powłoki interaktywnej:

#### 1. Pełny audyt stanu infrastruktury:
```bash
python3 main.py status
```

#### 2. Pobranie telemetrii statku SVL-364:
```bash
python3 main.py telemetry
```

#### 3. Wykonanie polecenia na statku SVL-364 przez OpenSSH:
```bash
python3 main.py ssh "uname -a && uptime"
# lub
python3 main.py exec "whoami && free -m"
```

#### 4. Wysłanie zapytania do pokładowego modelu AI:
```bash
python3 main.py ollama chat "Przedstaw status obrony i systemów łączności statku"
```

Wybranie innego z 13 modeli pokładowych:
```bash
python3 main.py ollama chat "Napisz skrypt w bashu do audytu portów" --model qwen2.5-coder:7b
```

#### 5. Przegląd katalogu 13 modeli pokładowych:
```bash
python3 main.py ollama models
```

#### 6. Weryfikacja serwerów federacji MCP:
```bash
python3 main.py mcp ping
```

#### 7. Pobranie listy narzędzi MCP ze wszystkich węzłów:
```bash
python3 main.py mcp list
```

---

## 5. Zmienne Środowiskowe (Opcjonalne)

JYN_OS automatycznie wykrywa klucze i tokeny z katalogu `data/` repozytorium `SVL_Core`. W razie potrzeby można nadpisać parametry zmiennymi środowiskowymi:

| Zmienna | Domyślna wartość | Opis |
| :--- | :--- | :--- |
| `SVL_SSH_TARGET` | `Ship` | Profil lub alias OpenSSH statku docelowego |
| `SVL_SSH_KEY` | `~/.ssh/svl364_ed25519` | Ścieżka do prywatnego klucza OpenSSH |
| `SVL_SHIP_OLLAMA_URL` | `http://127.0.0.1:11435` | Adres URL zapasowej Ollamy statku SVL-364 |
| `SVL_SHIP_MODEL` | `svl364-apex-uncensored:latest` | Domyślny model do zapytań czatu |
| `SVL_MCP_UNIVERSAL_HUB`| `http://127.0.0.1:3334/mcp` | Punkt końcowy Universal MCP Hub |
| `SVL_MCP_SYSTEM` | `http://127.0.0.1:3000/mcp/svl` | Punkt końcowy bramy System MCP |
| `SVL_MCP_SHIP` | `http://127.0.0.1:3000/api/mcp/svl364` | Punkt końcowy Ship MCP Gateway |
| `SVL_OPERATOR_TOKEN` | *Automatycznie z `data/`* | Główny token autoryzacyjny Operatora |
| `SVL_MCP_TOKEN` | *Automatycznie z `data/`* | Token do Universal MCP Hub |

---

## 6. Bezpieczeństwo i Integralność

- Komunikacja ze statkiem odbywa się wyłącznie za pośrednictwem kryptografii asymetrycznej Ed25519 oraz protokołu SSH-2.
- Żadne sekrety ani tokeny nie są na stałe wpisane do kodu źródłowego.
- Narzędzia klienta są w 100% zintegrowane ze środowiskiem `SVL_Core` i nie wpływają negatywnie na stabilność testów jądra.
