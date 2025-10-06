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

- Sorting options 
- More UI settings 
- AI-powered recommendations using [Deej-A.I.](https://deej-ai.online) or similar
- Manual artist search  
- Pre-built Docker image on GitHub Container Registry (GHCR) and/or Docker Hub mirror  
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

## Run using Docker Compose without opening ports 

_This setup assumes you already use Docker and have a network (for example, with NGINX Proxy Manager). Check the comments in the `docker-compose.yml` file if you prefer a simpler setup with exposed ports (not recommended but entirely functional)._  

1. Clone this repository  
2. Edit the `docker-compose.yml` file to match your environment  
3. Rename `.sample-env` to `.env` and adjust the values as needed  
4. Run <code>sudo docker compose up -d</code>  
   - This will **build the image locally** on first run, and then reuse the local image afterwards

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

---

## License  

This project is licensed under the MIT License.  
Original work © 2024 TheWicklowWolf.  
Forked and modified by Dodelidoo Labs, © 2025.  
