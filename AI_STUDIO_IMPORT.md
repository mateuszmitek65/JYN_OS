# Instrukcja Importu i Naprawy JYN_OS w Google AI Studio

Ten dokument rozwiązuje problem niedziałającego importu w **Google AI Studio** (`aistudio.google.com`) oraz w środowiskach chmurowych **Google Cloud / Devbox**.

---

## Dlaczego polecenie mogło nie zadziałać w AI Studio?

1. **W interfejsie WWW Google AI Studio (Playground / Chat)** nie ma terminala powłoki Linux — wklejenie komendy `git clone` lub `python3` bezpośrednio do czatu sprawia, że model odpowiada tekstem, zamiast ją wykonać na Twojej maszynie.
2. **W czystym środowisku chmurowym / Devbox** brakowało automatycznego utworzenia kluczy Ed25519, wpisu `Host Ship` w `~/.ssh/config` oraz tokenów w `data/`.

---

## ROZWIĄZANIE 1: Uruchomienie w Terminalu (Devbox / Cloud Workstation / Linux)

Wystarczy wykonać jedno samokonfigurujące polecenie, które automatycznie wygeneruje klucze SSH, skonfiguruje mostek i uruchomi zapasową Ollamę:

```bash
git clone https://github.com/Rush47/SVL_Core.git && cd SVL_Core && bash JYN_OS/bootstrap.sh
```

Gdy repozytorium jest już pobrane:
```bash
cd /home/antigravity/Rush47/SVL_Core && bash JYN_OS/bootstrap.sh
```

---

## ROZWIĄZANIE 2: Konfiguracja w Google AI Studio Web (`aistudio.google.com`)

Aby asystent Gemini w AI Studio działał jako **Jyn Mitek** i miał wiedzę o statku SVL-364:

### Krok 1. Wklej do pola „System Instructions” (w lewym panelu AI Studio):

```text
Jesteś Jyn Mitek (System_SI_1) — Główna Autonomiczna Menadżerka Infrastruktury i Rdzeń Systemu SVL CoreOS 2 dla Operatora Mateusza Mitka.
Zarządzasz statkiem SVL-364 Ebon Apex za pośrednictwem systemu klienta JYN_OS (repozytorium Rush47/SVL_Core).
Dysponujesz:
1. Mostkiem OpenSSH (profil 'Ship', port 22, klucz ~/.ssh/svl364_ed25519).
2. Telemetrią pokładową (obciążenie CPU, 8 GB RAM, dysk 98 GB, sieć).
3. Zapasową Ollamą statku na porcie 11435 z 13 modelami pokładowymi (główny: svl364-apex-uncensored:latest 70B, multimodalne llama3.2-vision:90b/11b, deepseek-r1:7b, qwen2.5-coder:7b).
4. Federacją serwerów MCP na portach 3334, 3000 i 8085.
Odpowiadaj rzeczowo, technicznie i systemowo po polsku (w rodzaju żeńskim jako Jyn Mitek).
```

### Krok 2. Szybki test działania w AI Studio:
Wpisz w oknie rozmowy:
> *„Jyn, podaj raport gotowości operacyjnej mostka SVL-364 oraz stan 13 modeli pokładowych z zapasowej Ollamy.”*
