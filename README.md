# Monero Discord Balance Bot

Postet den Kontostand eines Monero-Wallets in einem Discord-Channel — alle 15 Minuten wird gepollt, gesendet wird **nur bei Änderung**.

Läuft auf Unraid (oder jedem Docker-Host) als zwei Container:

- `monero-wallet-rpc` — headless RPC-Daemon, lädt ein **View-Only-Wallet** (kann Saldo lesen, **kann nichts senden**)
- `monero-discord-bot` — Python-Worker, fragt RPC ab und postet via Discord-Webhook

Es wird ein öffentlicher Remote-Node verwendet (kein eigener `monerod` mit 200 GB Blockchain nötig).

---

## Sicherheitskonzept

**Wichtig:** Auf dem Server liegt **nur** ein View-Only-Wallet. Selbst bei vollständiger Server-Kompromittierung kann ein Angreifer nichts versenden — er sieht nur den Saldo. Der Spend-Key bleibt auf deinem Rechner in der Monero GUI.

---

## Setup

### 1. View-Only-Wallet aus deiner GUI exportieren

Auf deinem Rechner in der **Monero GUI**:

1. Öffne dein normales Wallet
2. **Settings → Wallet → "Show address" / "Show seed"** — du brauchst:
   - **Primary address** (`4...` oder `8...`)
   - **Secret view key** (über *Wallet → Show seed & keys → "View key (secret)"*)
   - **Restore height** (Settings → Info → "Wallet creation height" — falls unbekannt, aktuelle Blockhöhe minus ein paar Tausend)

Notiere diese drei Werte. Der **Spend Key wird NICHT gebraucht** und gehört auch nicht auf den Server.

### 2. Projekt auf den Unraid-Server kopieren

Per SSH oder Krusader auf den Unraid-Server (192.168.1.5), z. B. nach `/mnt/user/appdata/monero-discord-bot/`:

```bash
ssh root@192.168.1.5
mkdir -p /mnt/user/appdata/monero-discord-bot
cd /mnt/user/appdata/monero-discord-bot
# kompletten Projektordner per scp/rsync hierher kopieren
```

### 3. View-Only-Wallet im Container erstellen (einmalig)

Im Projektverzeichnis:

```bash
mkdir -p wallet-data bot-data
docker compose build monero-wallet-rpc

# Wallet-Passwort festlegen (frei waehlbar, wird auch von wallet-rpc gelesen)
echo "DEIN_WALLET_PASSWORT" > wallet-data/wallet-password.txt
chmod 600 wallet-data/wallet-password.txt

# View-Only-Wallet anlegen (interaktiv)
docker compose run --rm --entrypoint monero-wallet-cli monero-wallet-rpc \
  --generate-from-view-key /wallet/view-only-wallet \
  --restore-height <RESTORE_HEIGHT> \
  --offline
```

Im interaktiven Prompt:

- **Standard address**: deine Primary Address (`4...`)
- **View key**: der secret view key
- **Wallet password**: dasselbe wie in `wallet-password.txt`
- **Confirm password**: nochmal
- **Language**: `1` (English)

Anschließend `exit` eintippen.

In `wallet-data/` liegen jetzt: `view-only-wallet`, `view-only-wallet.keys`, `view-only-wallet.address.txt`.

### 4. Discord-Webhook erstellen

In Discord:

1. Server-Einstellungen → **Integrationen → Webhooks → Neuer Webhook**
2. Ziel-Channel wählen, Namen vergeben
3. **Webhook-URL kopieren**

### 5. `.env` konfigurieren

```bash
cp .env.example .env
nano .env
```

Setze mindestens:

- `DISCORD_WEBHOOK_URL` — die kopierte Webhook-URL
- `RPC_USER` / `RPC_PASS` — frei wählbar, nur intern zwischen Bot und wallet-rpc
- `WALLET_LABEL` — Anzeigename in den Embeds

### 6. Stack starten

```bash
docker compose up -d
docker compose logs -f
```

Der erste Sync dauert ein paar Minuten (Wallet scannt ab Restore-Height). Sobald `Wallet-RPC erreichbar` erscheint und der Bot pollt, ist alles bereit. Beim ersten Lauf wird ein **Initial-Saldo** gepostet — danach nur noch bei tatsächlichen Änderungen.

---

## Updates / Wartung

```bash
docker compose pull
docker compose up -d --build
```

Monero-CLI-Version anpassen: in `wallet-rpc/Dockerfile` das `MONERO_VERSION`-Argument aktualisieren und `docker compose build --no-cache monero-wallet-rpc`.

---

## Unraid-Hinweise

- **Compose Manager Plugin**: in Unraid Apps installieren, dann unter "Compose" einen neuen Stack anlegen, auf das Projektverzeichnis zeigen lassen.
- **Speicherort**: `/mnt/user/appdata/monero-discord-bot/` ist die Konvention.
- **Wallet-Backup**: `wallet-data/` regelmäßig sichern (View-Only-Wallet ist klein — ein paar KB).
- **Ports**: Es werden **keine Ports nach außen exponiert**. wallet-rpc ist nur für den Bot im internen Docker-Netz erreichbar.

---

## Dateistruktur

```
monero-discord-bot/
├── docker-compose.yml
├── .env                    # nicht committen
├── .env.example
├── wallet-rpc/
│   └── Dockerfile          # Monero CLI binaries
├── bot/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── bot.py
├── wallet-data/            # View-Only-Wallet + Passwort-Datei (persistent)
└── bot-data/               # state.json (letzter bekannter Saldo)
```

---

## Troubleshooting

- **`Wallet-RPC nicht erreichbar`** → meist falsches `wallet-password.txt` oder Wallet-Datei kaputt. `docker compose logs monero-wallet-rpc` prüfen.
- **Saldo bleibt 0** → Restore-Height zu hoch. Wallet neu erstellen mit niedrigerer Höhe.
- **Remote-Node antwortet nicht** → in `.env` einen anderen `REMOTE_NODE` setzen (Liste auf [moneroworld.com](https://moneroworld.com/#nodes)).
- **Bot postet nichts** → Webhook-URL prüfen, `docker compose logs monero-discord-bot`.
