# Sonobarr  

<p align="center">
  <img src="/src/static/sonobarr.png" alt="Sonobarr Logo">
</p>

**Sonobarr** is a music discovery tool that integrates with [**Lidarr**](https://lidarr.audio) and provides recommendations using [**Last.fm**](https://www.last.fm).  

---

## Features  

The app can:  
- Fetch artists from Lidarr  
- Let you select one or more artists to find similar artists (from Last.fm only)  
- Display artist biographies  
- Play YouTube videos to listen to artists directly    
- Load additional artists dynamically  

## Planned Features  

- [ ] Sorting options 
- [ ] More UI settings 
- [ ] AI-powered recommendations using [Deej-A.I.](https://deej-ai.online) or similar
- [ ] Manual artist search  
- [x] Pre-built Docker image on GitHub Container Registry (GHCR) ~~and/or Docker Hub mirror~~
- [x] User management
- …and more  

---

## Screenshots  

<p align="center">
  <img src="/src/static/fetch-from-lidarr.png" alt="Fetch from Lidarr" width="100%">
  <img src="/src/static/prehear-detail.png" alt="Prehear Detail" width="100%">
  <img src="/src/static/bio-detail.png" alt="Bio Detail" width="48%">
  <img src="/src/static/settings-detail.png" alt="Settings Detail" width="48%">
  <img src="/src/static/card-detail.png" alt="Card Detail" width="48%">
  <img src="/src/static/card-detail-added.png" alt="Card Detail Added" width="48%">
</p>  

---

## Running Sonobarr with Docker Compose

You can run Sonobarr using Docker Compose. There are two main setups:
- With a proxy (recommended) - if you already use something like NGINX Proxy Manager or Traefik (and ideally, a DNS tool like Technitium)
- With exposed ports (simpler, no proxy) - directly exposing Sonobarr's port on your host. 

### Preparation
1. Create a working directory on your host, e.g.: `mkdir sonobarr`
2. Set ownership (to ensure mounted volumes are writable): `sudo chown -R 1000:1000 sonobarr`
3. Move into the directory: `cd sonobarr`
4. Download the example Compose file and environment file:
```
wget https://raw.githubusercontent.com/Dodelidoo-Labs/sonobarr/main/docker-compose.yml -O docker-compose.yml
wget https://raw.githubusercontent.com/Dodelidoo-Labs/sonobarr/main/.sample-env -O .env
```
5. Edit the `.env` file with your Last.fm, Lidarr, and YouTube API keys (optional, but without it "prehear" feature wont' work)
6. Adjust `docker-compose.yml` as needed (see setup options below).
7. Run with `sudo docker compose up -d`

### Run with a proxy (recommended)
If you already use a reverse proxy like NGINX Proxy Manager or Traefik, you can keep the container internal and let the proxy handle external access.
```
services:
  sonobarr:
    image: ghcr.io/dodelidoo-labs/sonobarr:latest # or ghcr.io/dodelidoo-labs/sonobarr:0.1.0 for a specific version
    container_name: sonobarr
    volumes:
      - ./config:/sonobarr/config
      - /etc/localtime:/etc/localtime:ro
    restart: unless-stopped
    environment:
      - last_fm_api_key=${last_fm_api_key}
      - last_fm_api_secret=${last_fm_api_secret}
      - lidarr_address=${lidarr_address}
      - quality_profile_id=${quality_profile_id}
      - lidarr_api_key=${lidarr_api_key}
      - youtube_api_key=${youtube_api_key}
	  - sonobarr_superadmin_username=${sonobarr_superadmin_username}
      - sonobarr_superadmin_password=${sonobarr_superadmin_password}
      - sonobarr_superadmin_display_name=${sonobarr_superadmin_display_name}
      - sonobarr_superadmin_reset=${sonobarr_superadmin_reset}
    networks:
      npm_proxy:
        ipv4_address: 192.168.97.23 # change to an available IP on your proxy network

networks:
  npm_proxy:
    external: true
```

### Run with exposed ports (no proxy)
```
services:
  sonobarr:
    image: ghcr.io/dodelidoo-labs/sonobarr:latest # or ghcr.io/dodelidoo-labs/sonobarr:0.1.0 for a specific version
    container_name: sonobarr
    volumes:
      - ./config:/sonobarr/config
      - /etc/localtime:/etc/localtime:ro
    ports:
      - "5000:5000"
    restart: unless-stopped
    environment:
      - last_fm_api_key=${last_fm_api_key}
      - last_fm_api_secret=${last_fm_api_secret}
      - lidarr_address=${lidarr_address}
      - quality_profile_id=${quality_profile_id}
      - lidarr_api_key=${lidarr_api_key}
      - youtube_api_key=${youtube_api_key}
	  - sonobarr_superadmin_username=${sonobarr_superadmin_username}
      - sonobarr_superadmin_password=${sonobarr_superadmin_password}
      - sonobarr_superadmin_display_name=${sonobarr_superadmin_display_name}
      - sonobarr_superadmin_reset=${sonobarr_superadmin_reset}
```

### Notes
- Use `:latest` to always get the newest release, or pin to a specific version (e.g. `:0.1.0`) for stability.
- The `.env` file holds your secrets and config values — don't leak it!

---

## Configuration via Environment Variables  

- **PUID** – User ID (default: `1000`)  
- **PGID** – Group ID (default: `1000`)  
- **lidarr_address** – Lidarr URL (default: `http://192.168.1.1:8686`)  
- **lidarr_api_key** – API key for Lidarr  
- **root_folder_path** – Music root folder path (default: `/data/media/music/`). See [here](https://github.com/Dodelidoo-Labs/sonobarr/issues/2) how to find this path.  
- **fallback_to_top_result** – Use top result if no match is found (default: `False`)  
- **lidarr_api_timeout** – API timeout in seconds (default: `120`)  
- **quality_profile_id** – Quality profile ID (default: `1`). See [here](https://github.com/Dodelidoo-Labs/sonobarr/issues/1) how to find it.  
- **metadata_profile_id** – Metadata profile ID (default: `1`)  
- **search_for_missing_albums** – Start searching when adding artists (default: `False`)  
- **dry_run_adding_to_lidarr** – Run without adding artists (default: `False`)  
- **app_name** – Application name (default: `Sonobarr`)  
- **app_rev** – Application revision (default: `0.01`, Version string sent to MusicBrainz as part of the HTTP User-Agent)  
- **app_url** – Application URL (default: `Random URL`, Contact/project URL sent to MusicBrainz as part of the HTTP User-Agent)  
- **last_fm_api_key** – API key for Last.fm  
- **last_fm_api_secret** – API secret for Last.fm  
- **youtube_api_key** – API key for YouTube  
- **similar_artist_batch_size** – Batch size for similar artists (default: `10`)  
- **auto_start** – Run automatically at startup (default: `False`)  
- **auto_start_delay** – Delay in seconds for auto start (default: `60`)  
- **sonobarr_superadmin_username** - The Super Admin's username (first user, has admin rights, default `admin`)
- **sonobarr_superadmin_password** - The Super Admin's password (default `change-me`)
- **sonobarr_superadmin_display_name** - The Super Admin's nice name (default `Super Admin`)
- **sonobarr_superadmin_reset** - Reset the Super Admin log in details (set to `true` once, then to `false` again. Default `false`)

## Authentication & user management

- Sonobarr now requires a login. A built-in super admin account is created the first time the app starts.
- Configure the bootstrap admin via environment variables:
  - `SONOBARR_SUPERADMIN_USERNAME` (default: `admin`)
  - `SONOBARR_SUPERADMIN_PASSWORD` (if omitted, a secure password is generated and written to the container log on first boot)
  - `SONOBARR_SUPERADMIN_DISPLAY_NAME` (default: `Super Admin`)
- Admins can access **Settings** and **User management** from the profile menu (top-right of the app). Non-admins cannot view or change shared API settings.
- Use the **User management** page to create or delete accounts; Sonobarr ensures at least one admin remains.
- Every user can update their display name, avatar URL, and password from the **Profile** page.

---

## License  

This project is licensed under the MIT License.  
Original work © 2024 TheWicklowWolf.  
Modified by Dodelidoo Labs, © 2025.  
