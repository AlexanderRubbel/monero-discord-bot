# Monero Discord Balance Bot

Posts the balance of a Monero wallet to a Discord channel — polled every 15 minutes, posted **only on change**.

Runs on any Docker host (tested on Unraid) as two containers:

- `monero-wallet-rpc` — headless RPC daemon, loads a **view-only wallet** (can read balance, **cannot send anything**)
- `monero-discord-bot` — Python worker, queries the RPC and posts via Discord webhook

A public remote node is used by default (no need to run your own `monerod` with a 200 GB blockchain).

---

## Security model

**Important:** only a **view-only wallet** lives on the server. Even with full server compromise, an attacker can only read the balance — they cannot spend. The spend key never leaves the machine where you generated/imported the wallet (e.g. your Monero GUI).

---

## Requirements

- A Docker host with `docker` and `docker compose` (Linux, Unraid, Synology with Container Manager, a VPS, a Raspberry Pi, etc.)
- The address, secret view key, and restore height of the wallet you want to track
- A Discord channel where you can create webhooks

---

## Setup

### 1. Export view-only credentials from your wallet

In the **Monero GUI** on the machine that holds the wallet:

1. Open your normal wallet
2. Get the following three values:
   - **Primary address** (`4...` or `8...`) — *Receive* tab or *Settings → Wallet*
   - **Secret view key** — *Wallet → Show seed & keys → "View key (secret)"*
   - **Restore height** — *Settings → Info → "Wallet creation height" / "Restore height"*. If unknown, use a block height from shortly before the wallet was first used.

The **spend key is NOT needed** and must never be put on the server.

### 2. Get the project onto your Docker host

```bash
# Clone (recommended — makes future updates a single git pull)
git clone https://github.com/<your-fork>/monero-discord-bot.git
cd monero-discord-bot

# Or copy via scp/rsync from your workstation:
# rsync -av ./monero-discord-bot/ user@host:/path/to/monero-discord-bot/
```

Pick any directory you like. Common conventions:

- Linux server: `/opt/monero-discord-bot/` or `~/monero-discord-bot/`
- Unraid: `/mnt/user/appdata/monero-discord-bot/`
- Synology: `/volume1/docker/monero-discord-bot/`

### 3. Create the view-only wallet (one-time)

From the project directory:

```bash
mkdir -p wallet-data bot-data
chown -R 1000:1000 wallet-data bot-data    # match the non-root user in the container
docker compose build monero-wallet-rpc

# Set the wallet password (free choice, also read by wallet-rpc later).
# Use printf (NOT echo) to avoid a trailing newline in the file.
printf '%s' 'YOUR_WALLET_PASSWORD' > wallet-data/wallet-password.txt
chmod 600 wallet-data/wallet-password.txt
chown 1000:1000 wallet-data/wallet-password.txt

# Generate the view-only wallet (interactive)
docker compose run --rm --entrypoint monero-wallet-cli monero-wallet-rpc \
  --generate-from-view-key /wallet/view-only-wallet \
  --restore-height <RESTORE_HEIGHT> \
  --password-file /wallet/wallet-password.txt \
  --mnemonic-language English \
  --offline
```

At the interactive prompts:

- **Standard address:** your primary address (`4...`)
- **View key:** the secret view key
- *(password is read from the file, no prompt)*
- Background mining: `N`
- Then type `exit` to leave the wallet shell.

`wallet-data/` should now contain `view-only-wallet`, `view-only-wallet.keys`, and `view-only-wallet.address.txt`.

### 4. Create a Discord webhook

In Discord:

1. Server settings → **Integrations → Webhooks → New Webhook**
2. Choose the target channel, give it a name
3. **Copy the webhook URL** (looks like `https://discord.com/api/webhooks/...`)

### 5. Configure `.env`

```bash
cp .env.example .env
nano .env       # or vi/vim/your editor
```

Set at minimum:

- `DISCORD_WEBHOOK_URL` — the URL you just copied
- `RPC_USER` / `RPC_PASS` — free choice, only used between bot and wallet-rpc internally. Generate a strong random password, e.g. `openssl rand -base64 32`.
- `WALLET_LABEL` — display name in the Discord embeds

### 6. Start the stack

```bash
docker compose up -d
docker compose logs -f
```

The first sync takes a few minutes (the wallet scans from the restore height). Once `Wallet-RPC reachable` appears and the bot starts polling, it's ready. The first poll posts an **Initial Balance** message; from then on, only **balance changes** are posted.

---

## Updates / maintenance

```bash
git pull                              # if you cloned
docker compose up -d --build          # rebuild with latest code
```

To bump the Monero CLI version, edit `MONERO_VERSION` in `wallet-rpc/Dockerfile` and:

```bash
docker compose build --no-cache monero-wallet-rpc
docker compose up -d
```

To watch the live state:

```bash
docker compose ps
docker compose logs -f monero-discord-bot
```

---

## File layout

```
monero-discord-bot/
├── docker-compose.yml
├── .env                    # secrets — do not commit
├── .env.example
├── wallet-rpc/
│   └── Dockerfile          # Monero CLI binaries
├── bot/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── bot.py
├── wallet-data/            # view-only wallet + password file (persistent)
└── bot-data/               # state.json (last known balance)
```

The bot persists the last known balance in `bot-data/state.json`. Delete that file to force a fresh "Initial Balance" post on next poll.

---

## Networking & ports

The `docker-compose.yml` exposes **no ports to the host**. `monero-wallet-rpc` is reachable only from the `monero-discord-bot` container over an internal Docker network. The wallet-rpc connects outbound to a public Monero remote node (default: `node.sethforprivacy.com:18089`).

If the default node is unreachable, set `REMOTE_NODE` in `.env` to another node — see the list at [moneroworld.com](https://moneroworld.com/#nodes). Alternatives that are usually up:

- `xmr-node.cakewallet.com:18081`
- `nodes.hashvault.pro:18081`
- `node.monerodevs.org:18089`

---

## Platform notes

### Unraid

- Install the **Compose Manager** plugin from Apps if you want a UI; otherwise just `docker compose` from SSH works fine.
- Convention: `/mnt/user/appdata/monero-discord-bot/`
- The `chown 1000:1000` step on `wallet-data/` is required because Unraid's default ownership doesn't match the in-container `monero` user (uid 1000).

### Synology DSM

- Use Container Manager → Project → import this folder, or `docker compose` over SSH.
- Make sure the project lives on a volume that supports proper file permissions (not a network share).

### Generic Linux / VPS / Raspberry Pi

- Works as-is. On ARM64 (e.g. Raspberry Pi 4/5) you may need to update the Monero download URL in `wallet-rpc/Dockerfile` to the `linux-armv8` variant.

---

## Backup

`wallet-data/` is small (a few hundred KB) and contains:

- `view-only-wallet.keys` — the encrypted view key (cannot spend)
- `view-only-wallet` — cache of scanned blocks (regenerable)
- `wallet-password.txt` — the password protecting the keys file

Back up `view-only-wallet.keys` and `wallet-password.txt`. The cache (`view-only-wallet`) will rebuild itself on first sync.

You don't need to back up the bot's state — losing `bot-data/state.json` only causes one extra "Initial Balance" Discord post on next start.

---

## Troubleshooting

- **`wallet-rpc not reachable after 5 minutes`** → wrong `wallet-password.txt`, or wallet-rpc still doing the initial scan. Check `docker compose logs monero-wallet-rpc`. The RPC server only starts listening after the first refresh completes.
- **Balance stays at 0** → restore height is too high (after the wallet's first transaction). Recreate the wallet with a lower restore height.
- **Remote node not responding** → set a different `REMOTE_NODE` in `.env` and `docker compose up -d --force-recreate monero-wallet-rpc`.
- **Bot posts nothing** → check `DISCORD_WEBHOOK_URL` and `docker compose logs monero-discord-bot`.
- **Permission denied on wallet files** → ensure `wallet-data/` is owned by `1000:1000` (the container's `monero` user).

---

## License

Use at your own risk. View-only wallets cannot spend coins, but always understand what you're putting on a server before doing so.
