# Sonobarr

> Music discovery for Lidarr power users, backed by Last.fm intelligence and a modern web UI.

[![Release](https://img.shields.io/github/v/release/Dodelidoo-Labs/sonobarr?label=Latest%20release&cacheSeconds=60)](https://github.com/Dodelidoo-Labs/sonobarr/releases)
[![Container](https://img.shields.io/badge/GHCR-sonobarr-blue?logo=github)](https://github.com/Dodelidoo-Labs/sonobarr/pkgs/container/sonobarr)
[![License](https://img.shields.io/github/license/Dodelidoo-Labs/sonobarr)](./LICENSE)

Sonobarr marries your existing Lidarr library with Last.fm’s discovery graph to surface artists you'll actually like. It runs as a Flask + Socket.IO application, ships with a polished Bootstrap UI, and includes admin tooling so folks can share a single instance safely.

<p align="center">
  <img src="/src/static/sonobarr.png" alt="Sonobarr logo">
</p>

---

## Table of contents

1. [Features at a glance](#features-at-a-glance)
2. [How it works](#how-it-works)
3. [Quick start (Docker)](#quick-start-docker)
4. [Environment reference](#environment-reference)
5. [Local development](#local-development)
6. [Using the app](#using-the-app)
7. [Screenshots](#screenshots)
8. [Troubleshooting & FAQ](#troubleshooting--faq)
9. [Contributing](#contributing)
10. [License](#license)

---

## Features at a glance

- 🔌 **Lidarr integration** – fetch and cache your monitored artists automatically.
- 🔍 **Smart discovery** – query Last.fm for related artists, with dedupe and similarity scoring.
- 🤖 **AI assistant** – describe moods, genres or artists in plain English and let OpenAI pick seed artists for you.
- 🎧 **Preview & bio panels** – jump straight into YouTube or iTunes previews and read artist bios.
- ⚡️ **Real-time UX** – Socket.IO pushes new cards, status updates, and toast notifications instantly.
- 👥 **Role-based access** – built-in authentication plus an admin-only settings & user management area.
- 🔒 **Secure forms** – CSRF protection and stricter cookie settings keep sessions and admin actions safe.
- 🔔 **Update awareness** – footer badge compares your container version with the latest GitHub release.
-- 🧱 **Zero touch migrations** – database schema managed byFlask-Migrate and applied automatically on boot.
- 🐳 **Docker-first deployment** – official image on GHCR, mountable config volume, healthy defaults.

---

## How it works

```text
┌──────────────────────┐        ┌──────────────────────┐
│ Lidarr (HTTP API)    │◀──────▶│ Sonobarr backend     │
│  - Artist catalogue  │        │  Flask + Socket.IO   │
│  - API key auth      │        │  Last.fm + Deezer    │
└──────────────────────┘        │  Worker threads      │
                                └─────────┬────────────┘
                                          │
                                          ▼
                                ┌──────────────────────┐
                                │ Sonobarr web client  │
                                │  Bootstrap + JS      │
                                │  Admin UX            │
                                └──────────────────────┘
```

1. Sonobarr spins up with a persistent SQLite database inside the `config/` volume.
2. Admins provide Lidarr + Last.fm credentials through the settings modal.
3. When a user starts a discovery session, Sonobarr pulls artists from Lidarr, fans out to Last.fm, and streams cards back to the browser.
4. Optional preview and biography data is enriched via YouTube/iTunes/MusicBrainz.

---

## Quick start (Docker)

> 🐳 **Requirements**: Docker Engine ≥ 24, Docker Compose plugin, Last.fm API key, Lidarr API key.

1. Clone or create a working directory and move into it:
   ```bash
   mkdir sonobarr && cd sonobarr
   ```
2. Download the sample configuration:
   ```bash
   curl -L https://raw.githubusercontent.com/Dodelidoo-Labs/sonobarr/develop/docker-compose.yml -o docker-compose.yml
   curl -L https://raw.githubusercontent.com/Dodelidoo-Labs/sonobarr/develop/.sample-env -o .env
   ```
3. Open `.env` and populate **at least** these keys:
   ```env
   secret_key=change-me-to-a-long-random-string
   lidarr_address=http://your-lidarr:8686
   lidarr_api_key=xxxxxxxxxxxxxxxxxxxxxxxx
   last_fm_api_key=xxxxxxxxxxxxxxxxxxxxxxxx
   last_fm_api_secret=xxxxxxxxxxxxxxxxxxxxxxxx
   # Optional – enables the AI assistant modal
   # openai_api_key=sk-...
   ```
   > All keys in `.env` are lowercase by convention; the app will happily accept uppercase equivalents if you prefer exporting variables.
4. Ensure the config directory is writable by the container UID/GID (defaults to `1000:1000`). For Linux hosts:
   ```bash
   mkdir -p config
   sudo chown -R 1000:1000 config
   ````
   > On first boot the container creates `/sonobarr/config/migrations`, seeds the database, and runs all migrations automatically.
5. Start Sonobarr:
   ```bash
   docker compose up -d
   ```
6. Browse to `http://localhost:5000` (or the host behind your reverse proxy) and sign in using the super-admin credentials defined in `.env`.

### Reverse proxy deployment

The provided `docker-compose.yml` attaches Sonobarr to an external `npm_proxy` network. Adjust the network name and static IP so it fits your proxy stack (NGINX Proxy Manager, Traefik, etc.). No additional `environment:` stanza is needed - everything comes from the `.env` file referenced in `env_file`.

### Running without a proxy

Expose port 5000 directly by adding `ports: - "5000:5000"` to the service while keeping the same `env_file` entry.

### Updating

```bash
docker compose pull
docker compose up -d
```

The footer indicator will show a green dot when you are on the newest release and red when an update is available.

---

## Environment reference

All variables can be supplied in lowercase (preferred for `.env`) or uppercase (useful for CI/CD systems). Defaults shown are the values Sonobarr falls back to when nothing is provided.

| Key | Default | Description |
| --- | --- | --- |
| `secret_key` (**required**) | – | Flask session signing key. Must be a long random string; store it in `.env` so sessions survive restarts. |
| `lidarr_address` | `http://192.168.1.1:8686` | Base URL of your Lidarr instance. |
| `lidarr_api_key` | – | Lidarr API key for artist lookups and additions. |
| `root_folder_path` | `/data/media/music/` | Default root path used when adding new artists in Lidarr. |
| `quality_profile_id` | `1` | Numeric profile ID from Lidarr (see [issue #1](https://github.com/Dodelidoo-Labs/sonobarr/issues/1)). |
| `metadata_profile_id` | `1` | Numeric metadata profile ID. |
| `search_for_missing_albums` | `false` | Toggle Lidarr’s “search for missing” flag when adding an artist. |
| `dry_run_adding_to_lidarr` | `false` | If `true`, Sonobarr will simulate additions without calling Lidarr. |
| `last_fm_api_key` | – | Last.fm API key for similarity lookups. |
| `last_fm_api_secret` | – | Last.fm API secret. |
| `youtube_api_key` | – | Enables YouTube previews in the “Listen” modal. Optional but recommended. |
| `openai_api_key` | – | Optional OpenAI key used by the AI Assist modal. Leave empty to disable the feature. |
| `openai_model` | `gpt-4o-mini` | Override the OpenAI model used for prompts. |
| `openai_max_seed_artists` | `5` | Maximum number of seed artists returned from each AI prompt. |
| `similar_artist_batch_size` | `10` | Number of cards sent per batch while streaming results. |
| `auto_start` | `false` | Automatically start a discovery session on load. |
| `auto_start_delay` | `60` | Delay (seconds) before auto-start kicks in. |
| `sonobarr_superadmin_username` | `admin` | Username of the bootstrap admin account. |
| `sonobarr_superadmin_password` | `change-me` | Password for the bootstrap admin. Set to a secure value before first launch. |
| `sonobarr_superadmin_display_name` | `Super Admin` | Friendly display name shown in the UI. |
| `sonobarr_superadmin_reset` | `false` | Set to `true` **once** to reapply the bootstrap credentials on next start. |
| `release_version` | `unknown` | Populated automatically inside the Docker image; shown in the footer. No need to set manually. |
| `sonobarr_config_dir` | `/sonobarr/config` | Override where Sonobarr writes `app.db`, `settings_config.json`, and migrations. |

> ℹ️ `secret_key` is mandatory. If missing, the app refuses to boot to prevent insecure session cookies. With Docker Compose, make sure the key exists in `.env` and that `.env` is declared via `env_file:` as shown above.

---

## Local development

See [CONTRIBUTING.md](https://github.com/Dodelidoo-Labs/sonobarr/blob/main/CONTRIBUTING.md)

### Tests

Currently relying on manual testing. Contributions adding pytest coverage, especially around the data handler and settings flows, are very welcome.

---

## Using the app

1. **Sign in** with the bootstrap admin credentials. Create additional users from the **User management** page (top-right avatar → *User management*).
2. **Configure integrations** via the **Settings** button (top bar gear icon). Provide your Lidarr endpoint/key and optional YouTube key (can both be set in .env or UI)
3. **Fetch Lidarr artists** with the left sidebar button. Select the artists you want to base discovery on.
4. Hit **Start**. Sonobarr queues batches of similar artists and streams them to the grid. Cards show genre, popularity, listeners, and a color-coded status LED as well as similarity (according to Last.fm)
5. Use **Bio** and **Listen** buttons for deeper context. Click **Add to Lidarr** to push the candidate back into your library; feedback appears on the card immediately.
6. Stop or resume discovery anytime. Toast notifications keep everyone informed when conflicts or errors occur.

### AI-powered prompts

- Click the **AI Assist** button on the top bar to open a prompt modal.
- Describe the mood, genres, or examples you're craving (e.g. “dreamy synth-pop like M83 but calmer”).
- Provide an OpenAI API key through the settings modal (or `.env`) to unlock the feature; without a key the assistant stays disabled.
- The assistant picks a handful of seed artists, kicks off a discovery session automatically, and keeps streaming cards just like a normal Lidarr-driven search.

The footer shows:
- GitHub repo shortcut.
- Current version.
- A red/green status dot indicating whether a newer release exists.

---

## Screenshots

<p align="center">
  <img src="/src/static/fetch-from-lidarr.png" alt="Fetching artists" width="95%">
  <img src="/src/static/prehear-detail.png" alt="Audio preview modal" width="95%">
  <img src="/src/static/bio-detail.png" alt="Artist biography" width="46%">
  <img src="/src/static/settings-detail.png" alt="Settings modal" width="46%">
  <img src="/src/static/card-detail.png" alt="Artist card" width="46%">
  <img src="/src/static/card-detail-added.png" alt="Artist added to Lidarr" width="46%">
</p>

---

## Troubleshooting & FAQ

### The container exits with "SECRET_KEY environment variable is required"
Ensure your Compose file references the `.env` file via `env_file:` and that `.env` contains a non-empty `secret_key`. Without it, Flask cannot sign sessions.

### UI says "Update available" even though I pulled latest
The footer compares your runtime `release_version` with the GitHub Releases API once per hour. If you built your own image, set `RELEASE_VERSION` at build time (`docker build --build-arg RELEASE_VERSION=custom-tag`).

### Artists fail to add to Lidarr
Check the container logs - Sonobarr prints the Lidarr error payload. Common causes are incorrect `root_folder_path`, missing write permissions on the Lidarr side, or duplicate artists already present.

---

## Contributing

See [CONTRIBUTING.md](https://github.com/Dodelidoo-Labs/sonobarr/blob/main/CONTRIBUTING.md)

---

## License

This project is released under the [MIT License](./LICENSE).

Original work © 2024 TheWicklowWolf. Adaptations and ongoing maintenance © 2025 Dodelidoo Labs.
