import json
import time
import logging
import os
import random
import string
import threading
import urllib.parse
from flask import Flask, render_template, request
from flask_socketio import SocketIO
import requests
import musicbrainzngs
from thefuzz import fuzz
from unidecode import unidecode
import pylast


class DataHandler:
    def __init__(self):
        logging.basicConfig(level=logging.INFO, format="%(message)s")
        self.sonobarr_logger = logging.getLogger()
        self.musicbrainzngs_logger = logging.getLogger("musicbrainzngs")
        self.musicbrainzngs_logger.setLevel("WARNING")
        self.pylast_logger = logging.getLogger("pylast")
        self.pylast_logger.setLevel("WARNING")

        app_name_text = os.path.basename(__file__).replace(".py", "")
        release_version = os.environ.get("RELEASE_VERSION", "unknown")
        self.sonobarr_logger.warning(f"{'*' * 50}\n")
        self.sonobarr_logger.warning(f"{app_name_text} Version: {release_version}\n")
        self.sonobarr_logger.warning(f"{'*' * 50}")

        self.search_in_progress_flag = False
        self.new_found_artists_counter = 0
        self.clients_connected_counter = 0
        self.config_folder = "config"
        self.recommended_artists = []
        self.lidarr_items = []
        self.cleaned_lidarr_items = []
        self.similar_artist_batch_size = ""
        self.stop_event = threading.Event()
        self.stop_event.set()
        if not os.path.exists(self.config_folder):
            os.makedirs(self.config_folder)
        self.load_environ_or_config_settings()
        if self.auto_start:
            try:
                auto_start_thread = threading.Timer(self.auto_start_delay, self.automated_startup)
                auto_start_thread.daemon = True
                auto_start_thread.start()

            except Exception as e:
                self.sonobarr_logger.error(f"Auto Start Error: {str(e)}")

        self.similar_artist_batch_pointer = 0
        self.similar_artist_candidates = []
        self.initial_batch_sent = False

    def load_environ_or_config_settings(self):
        # Defaults
        default_settings = {
            "lidarr_address": "http://192.168.1.1:8686",
            "lidarr_api_key": "",
            "root_folder_path": "/data/media/music/",
            "fallback_to_top_result": False,
            "lidarr_api_timeout": 120.0,
            "quality_profile_id": 1,
            "metadata_profile_id": 1,
            "search_for_missing_albums": False,
            "dry_run_adding_to_lidarr": False,
            "app_name": "Sonobarr",
            "app_rev": "0.10",
            "app_url": "http://" + "".join(random.choices(string.ascii_lowercase, k=10)) + ".com",
            "last_fm_api_key": "",
            "last_fm_api_secret": "",
            "auto_start": False,
            "auto_start_delay": 60,
            "youtube_api_key": "",
            "similar_artist_batch_size": 10,
        }

        # Load settings from environmental variables (which take precedence) over the configuration file.
        self.lidarr_address = os.environ.get("lidarr_address", "")
        self.lidarr_api_key = os.environ.get("lidarr_api_key", "")
        self.youtube_api_key = os.environ.get("youtube_api_key", "")
        self.root_folder_path = os.environ.get("root_folder_path", "")
        fallback_to_top_result = os.environ.get("fallback_to_top_result", "")
        self.fallback_to_top_result = fallback_to_top_result.lower() == "true" if fallback_to_top_result != "" else ""
        lidarr_api_timeout = os.environ.get("lidarr_api_timeout", "")
        self.lidarr_api_timeout = float(lidarr_api_timeout) if lidarr_api_timeout else ""
        quality_profile_id = os.environ.get("quality_profile_id", "")
        self.quality_profile_id = int(quality_profile_id) if quality_profile_id else ""
        metadata_profile_id = os.environ.get("metadata_profile_id", "")
        self.metadata_profile_id = int(metadata_profile_id) if metadata_profile_id else ""
        search_for_missing_albums = os.environ.get("search_for_missing_albums", "")
        self.search_for_missing_albums = search_for_missing_albums.lower() == "true" if search_for_missing_albums != "" else ""
        dry_run_adding_to_lidarr = os.environ.get("dry_run_adding_to_lidarr", "")
        self.dry_run_adding_to_lidarr = dry_run_adding_to_lidarr.lower() == "true" if dry_run_adding_to_lidarr != "" else ""
        self.app_name = os.environ.get("app_name", "")
        self.app_rev = os.environ.get("app_rev", "")
        self.app_url = os.environ.get("app_url", "")
        self.last_fm_api_key = os.environ.get("last_fm_api_key", "")
        self.last_fm_api_secret = os.environ.get("last_fm_api_secret", "")
        auto_start = os.environ.get("auto_start", "")
        self.auto_start = auto_start.lower() == "true" if auto_start != "" else ""
        auto_start_delay = os.environ.get("auto_start_delay", "")
        self.auto_start_delay = float(auto_start_delay) if auto_start_delay else ""

        # Load variables from the configuration file if not set by environmental variables.
        try:
            self.settings_config_file = os.path.join(self.config_folder, "settings_config.json")
            if os.path.exists(self.settings_config_file):
                self.sonobarr_logger.info(f"Loading Config via file")
                with open(self.settings_config_file, "r") as json_file:
                    ret = json.load(json_file)
                    for key in ret:
                        if getattr(self, key, "") == "":
                            setattr(self, key, ret[key])
        except Exception as e:
            self.sonobarr_logger.error(f"Error Loading Config: {str(e)}")

        # Load defaults if not set by an environmental variable or configuration file.
        for key, value in default_settings.items():
            if getattr(self, key) == "":
                setattr(self, key, value)

        # Validate and apply similar_artist_batch_size
        try:
            self.similar_artist_batch_size = int(self.similar_artist_batch_size)
        except (TypeError, ValueError):
            self.similar_artist_batch_size = default_settings["similar_artist_batch_size"]
        if self.similar_artist_batch_size <= 0:
            self.sonobarr_logger.warning("similar_artist_batch_size must be greater than zero; using default.")
            self.similar_artist_batch_size = default_settings["similar_artist_batch_size"]

        # Save config.
        self.save_config_to_file()

    def automated_startup(self):
        self.get_artists_from_lidarr(checked=True)
        artists = [x["name"] for x in self.lidarr_items]
        self.start(artists)

    def connection(self):
        if self.recommended_artists:
            socketio.emit("more_artists_loaded", self.recommended_artists)

        self.clients_connected_counter += 1

    def disconnection(self):
        self.clients_connected_counter = max(0, self.clients_connected_counter - 1)

    def start(self, data):
        try:
            socketio.emit("clear")
            self.new_found_artists_counter = 1
            self.artists_to_use_in_search = []
            self.recommended_artists = []
            self.similar_artist_batch_pointer = 0
            self.similar_artist_candidates = []
            self.initial_batch_sent = False

            for item in self.lidarr_items:
                item_name = item["name"]
                if item_name in data:
                    item["checked"] = True
                    self.artists_to_use_in_search.append(item_name)
                else:
                    item["checked"] = False

            if self.artists_to_use_in_search:
                self.stop_event.clear()
            else:
                self.stop_event.set()
                raise Exception("No Lidarr Artists Selected")

        except Exception as e:
            self.sonobarr_logger.error(f"Statup Error: {str(e)}")
            self.stop_event.set()
            ret = {"Status": "Error", "Code": str(e), "Data": self.lidarr_items, "Running": not self.stop_event.is_set()}
            socketio.emit("lidarr_sidebar_update", ret)

        else:
            self.prepare_similar_artist_candidates()
            self.load_similar_artist_batch()

    def prepare_similar_artist_candidates(self):
        # Only LastFM supported
        self.similar_artist_candidates = []
        lfm = pylast.LastFMNetwork(api_key=self.last_fm_api_key, api_secret=self.last_fm_api_secret)
        seen_candidates = set()
        for artist_name in self.artists_to_use_in_search:
            try:
                chosen_artist = lfm.get_artist(artist_name)
                related_artists = chosen_artist.get_similar()
                for related_artist in related_artists:
                    cleaned_artist = unidecode(related_artist.item.name).lower()
                    if cleaned_artist in self.cleaned_lidarr_items or cleaned_artist in seen_candidates:
                        continue
                    seen_candidates.add(cleaned_artist)
                    raw_match = getattr(related_artist, "match", None)
                    try:
                        match_score = float(raw_match) if raw_match is not None else None
                    except (TypeError, ValueError):
                        match_score = None
                    self.similar_artist_candidates.append({
                        "artist": related_artist,
                        "match": match_score,
                    })
            except Exception:
                continue
            if len(self.similar_artist_candidates) >= 500:
                break
        def sort_key(item):
            match_value = item["match"] if item["match"] is not None else -1.0
            return (-match_value, unidecode(item["artist"].item.name).lower())

        self.similar_artist_candidates.sort(key=sort_key)

    def load_similar_artist_batch(self):
        if self.stop_event.is_set():
            return
        batch_start = self.similar_artist_batch_pointer
        batch_size = max(1, int(self.similar_artist_batch_size))
        batch_end = batch_start + batch_size
        batch = self.similar_artist_candidates[batch_start:batch_end]

        lfm_network = pylast.LastFMNetwork(
            api_key=self.last_fm_api_key,
            api_secret=self.last_fm_api_secret
        )

        for candidate in batch:
            related_artist = candidate["artist"]
            similarity_score = candidate.get("match")
            try:
                artist_obj = lfm_network.get_artist(related_artist.item.name)

                genres = ", ".join([tag.item.get_name().title() for tag in artist_obj.get_top_tags()[:5]]) or "Unknown Genre"
                try:
                    listeners = artist_obj.get_listener_count() or 0
                except Exception:
                    listeners = 0
                try:
                    play_count = artist_obj.get_playcount() or 0
                except Exception:
                    play_count = 0

                # Fetch image (deezer)
                img_link = None
                try:
                    endpoint = "https://api.deezer.com/search/artist"
                    params = {"q": related_artist.item.name}
                    response = requests.get(endpoint, params=params)
                    data = response.json()
                    if "data" in data and data["data"]:
                        artist_info = data["data"][0]
                        img_link = artist_info.get(
                            "picture_xl",
                            artist_info.get("picture_large",
                            artist_info.get("picture_medium",
                            artist_info.get("picture", ""))))
                except Exception:
                    img_link = None

                if similarity_score is not None:
                    clamped_similarity = max(0.0, min(1.0, similarity_score))
                    similarity_label = f"Similarity: {clamped_similarity * 100:.1f}%"
                else:
                    clamped_similarity = None
                    similarity_label = None

                exclusive_artist = {
                    "Name": related_artist.item.name,
                    "Genre": genres,
                    "Status": "",
                    "Img_Link": img_link if img_link else "https://placehold.co/300x200",
                    "Popularity": f"Play Count: {self.format_numbers(play_count)}",
                    "Followers": f"Listeners: {self.format_numbers(listeners)}",
                    "SimilarityScore": clamped_similarity,
                    "Similarity": similarity_label,
                }

                # add to list + send immediately
                self.recommended_artists.append(exclusive_artist)
                socketio.emit("more_artists_loaded", [exclusive_artist])

            except Exception as e:
                self.sonobarr_logger.error(f"Error loading artist {related_artist.item.name}: {str(e)}")

        self.similar_artist_batch_pointer += len(batch)
        has_more = self.similar_artist_batch_pointer < len(self.similar_artist_candidates)
        if not self.initial_batch_sent:
            socketio.emit("initial_load_complete", {"hasMore": has_more})
            self.initial_batch_sent = True
        else:
            socketio.emit("load_more_complete", {"hasMore": has_more})

    def find_similar_artists(self):
        # Only batch loading for LastFM
        if self.stop_event.is_set() or self.search_in_progress_flag:
            return
        if self.similar_artist_batch_pointer < len(self.similar_artist_candidates):
            self.load_similar_artist_batch()
        else:
            socketio.emit("new_toast_msg", {"title": "No More Artists", "message": "No more similar artists to load."})

    def get_artists_from_lidarr(self, checked=False):
        try:
            self.sonobarr_logger.info(f"Getting Artists from Lidarr")
            self.lidarr_items = []
            endpoint = f"{self.lidarr_address}/api/v1/artist"
            headers = {"X-Api-Key": self.lidarr_api_key}
            response = requests.get(endpoint, headers=headers, timeout=self.lidarr_api_timeout)

            if response.status_code == 200:
                self.full_lidarr_artist_list = response.json()
                self.lidarr_items = [{"name": unidecode(artist["artistName"], replace_str=" "), "checked": checked} for artist in self.full_lidarr_artist_list]
                self.lidarr_items.sort(key=lambda x: x["name"].lower())
                self.cleaned_lidarr_items = [item["name"].lower() for item in self.lidarr_items]
                status = "Success"
                data = self.lidarr_items
            else:
                status = "Error"
                data = response.text

            ret = {"Status": status, "Code": response.status_code if status == "Error" else None, "Data": data, "Running": not self.stop_event.is_set()}

        except Exception as e:
            self.sonobarr_logger.error(f"Getting Artist Error: {str(e)}")
            ret = {"Status": "Error", "Code": 500, "Data": str(e), "Running": not self.stop_event.is_set()}

        finally:
            socketio.emit("lidarr_sidebar_update", ret)

    def add_artists(self, raw_artist_name):
        try:
            artist_name = urllib.parse.unquote(raw_artist_name)
            artist_folder = artist_name.replace("/", " ")
            musicbrainzngs.set_useragent(self.app_name, self.app_rev, self.app_url)
            mbid = self.get_mbid_from_musicbrainz(artist_name)
            if mbid:
                lidarr_url = f"{self.lidarr_address}/api/v1/artist"
                headers = {"X-Api-Key": self.lidarr_api_key}
                payload = {
                    "ArtistName": artist_name,
                    "qualityProfileId": self.quality_profile_id,
                    "metadataProfileId": self.metadata_profile_id,
                    "path": os.path.join(self.root_folder_path, artist_folder, ""),
                    "rootFolderPath": self.root_folder_path,
                    "foreignArtistId": mbid,
                    "monitored": True,
                    "addOptions": {"searchForMissingAlbums": self.search_for_missing_albums},
                }
                if self.dry_run_adding_to_lidarr:
                    response = requests.Response()
                    response.status_code = 201
                else:
                    response = requests.post(lidarr_url, headers=headers, json=payload)

                if response.status_code == 201:
                    self.sonobarr_logger.info(f"Artist '{artist_name}' added successfully to Lidarr.")
                    status = "Added"
                    self.lidarr_items.append({"name": artist_name, "checked": False})
                    self.cleaned_lidarr_items.append(unidecode(artist_name).lower())
                else:
                    self.sonobarr_logger.error(f"Failed to add artist '{artist_name}' to Lidarr.")
                    error_data = json.loads(response.content)
                    error_message = error_data[0].get("errorMessage", "No Error Message Returned") if error_data else "Error Unknown"
                    self.sonobarr_logger.error(error_message)
                    if "already been added" in error_message:
                        status = "Already in Lidarr"
                        self.sonobarr_logger.info(f"Artist '{artist_name}' is already in Lidarr.")
                    elif "configured for an existing artist" in error_message:
                        status = "Already in Lidarr"
                        self.sonobarr_logger.info(f"'{artist_folder}' folder already configured for an existing artist.")
                    elif "Invalid Path" in error_message:
                        status = "Invalid Path"
                        self.sonobarr_logger.info(f"Path: {os.path.join(self.root_folder_path, artist_folder, '')} not valid.")
                    else:
                        status = "Failed to Add"

            else:
                status = "Failed to Add"
                self.sonobarr_logger.info(f"No Matching Artist for: '{artist_name}' in MusicBrainz.")
                socketio.emit("new_toast_msg", {"title": "Failed to add Artist", "message": f"No Matching Artist for: '{artist_name}' in MusicBrainz."})

            for item in self.recommended_artists:
                if item["Name"] == artist_name:
                    item["Status"] = status
                    socketio.emit("refresh_artist", item)
                    break

        except Exception as e:
            self.sonobarr_logger.error(f"Adding Artist Error: {str(e)}")

    def get_mbid_from_musicbrainz(self, artist_name):
        result = musicbrainzngs.search_artists(artist=artist_name)
        mbid = None

        if "artist-list" in result:
            artists = result["artist-list"]

            for artist in artists:
                match_ratio = fuzz.ratio(artist_name.lower(), artist["name"].lower())
                decoded_match_ratio = fuzz.ratio(unidecode(artist_name.lower()), unidecode(artist["name"].lower()))
                if match_ratio > 90 or decoded_match_ratio > 90:
                    mbid = artist["id"]
                    self.sonobarr_logger.info(f"Artist '{artist_name}' matched '{artist['name']}' with MBID: {mbid}  Match Ratio: {max(match_ratio, decoded_match_ratio)}")
                    break
            else:
                if self.fallback_to_top_result and artists:
                    mbid = artists[0]["id"]
                    self.sonobarr_logger.info(f"Artist '{artist_name}' matched '{artists[0]['name']}' with MBID: {mbid}  Match Ratio: {max(match_ratio, decoded_match_ratio)}")

        return mbid

    def load_settings(self):
        try:
            data = {
                "lidarr_address": self.lidarr_address,
                "lidarr_api_key": self.lidarr_api_key,
                "root_folder_path": self.root_folder_path,
                "youtube_api_key": self.youtube_api_key,
                "similar_artist_batch_size": self.similar_artist_batch_size,
            }
            socketio.emit("settingsLoaded", data)
        except Exception as e:
            self.sonobarr_logger.error(f"Failed to load settings: {str(e)}")

    def update_settings(self, data):
        try:
            self.lidarr_address = data["lidarr_address"]
            self.lidarr_api_key = data["lidarr_api_key"]
            self.root_folder_path = data["root_folder_path"]
            self.youtube_api_key = data.get("youtube_api_key", "")
            batch_size = data.get("similar_artist_batch_size")
            if batch_size is not None:
                try:
                    batch_size = int(batch_size)
                except (TypeError, ValueError):
                    batch_size = self.similar_artist_batch_size
                if batch_size > 0:
                    self.similar_artist_batch_size = batch_size
        except Exception as e:
            self.sonobarr_logger.error(f"Failed to update settings: {str(e)}")

    def format_numbers(self, count):
        if count >= 1000000:
            return f"{count / 1000000:.1f}M"
        elif count >= 1000:
            return f"{count / 1000:.1f}K"
        else:
            return count

    def save_config_to_file(self):
        try:
            with open(self.settings_config_file, "w") as json_file:
                json.dump(
                    {
                        "lidarr_address": self.lidarr_address,
                        "lidarr_api_key": self.lidarr_api_key,
                        "root_folder_path": self.root_folder_path,
                        "fallback_to_top_result": self.fallback_to_top_result,
                        "lidarr_api_timeout": float(self.lidarr_api_timeout),
                        "quality_profile_id": self.quality_profile_id,
                        "metadata_profile_id": self.metadata_profile_id,
                        "search_for_missing_albums": self.search_for_missing_albums,
                        "dry_run_adding_to_lidarr": self.dry_run_adding_to_lidarr,
                        "app_name": self.app_name,
                        "app_rev": self.app_rev,
                        "app_url": self.app_url,
                        "last_fm_api_key": self.last_fm_api_key,
                        "last_fm_api_secret": self.last_fm_api_secret,
                        "auto_start": self.auto_start,
                        "auto_start_delay": self.auto_start_delay,
                        "youtube_api_key": self.youtube_api_key,
                        "similar_artist_batch_size": self.similar_artist_batch_size,
                    },
                    json_file,
                    indent=4,
                )

        except Exception as e:
            self.sonobarr_logger.error(f"Error Saving Config: {str(e)}")

    def preview(self, raw_artist_name):
        artist_name = urllib.parse.unquote(raw_artist_name)
        # Only LastFM supported
        try:
            preview_info = {}
            biography = None
            lfm = pylast.LastFMNetwork(api_key=self.last_fm_api_key, api_secret=self.last_fm_api_secret)
            search_results = lfm.search_for_artist(artist_name)
            artists = search_results.get_next_page()
            cleaned_artist_name = unidecode(artist_name).lower()
            for artist_obj in artists:
                match_ratio = fuzz.ratio(cleaned_artist_name, artist_obj.name.lower())
                decoded_match_ratio = fuzz.ratio(unidecode(cleaned_artist_name), unidecode(artist_obj.name.lower()))
                if match_ratio > 90 or decoded_match_ratio > 90:
                    biography = artist_obj.get_bio_content()
                    preview_info["artist_name"] = artist_obj.name
                    preview_info["biography"] = biography
                    break
            else:
                preview_info = f"No Artist match for: {artist_name}"
                self.sonobarr_logger.error(preview_info)

            if biography is None:
                preview_info = f"No Biography available for: {artist_name}"
                self.sonobarr_logger.error(preview_info)

        except Exception as e:
            preview_info = {"error": f"Error retrieving artist bio: {str(e)}"}
            self.sonobarr_logger.error(preview_info)

        finally:
            socketio.emit("lastfm_preview", preview_info, room=request.sid)

    def prehear(self, raw_artist_name, sid):
        import pylast
        import requests
        import time
        artist_name = urllib.parse.unquote(raw_artist_name)
        lfm = pylast.LastFMNetwork(api_key=self.last_fm_api_key, api_secret=self.last_fm_api_secret)
        yt_key = self.youtube_api_key
        if not yt_key:
            result = {"error": "YouTube API key missing"}
            socketio.emit("prehear_result", result, room=sid)
            return
        result = {"error": "No sample found"}
        try:
            top_tracks = []
            try:
                artist = lfm.get_artist(artist_name)
                top_tracks = artist.get_top_tracks(limit=10)
            except Exception as e:
                self.sonobarr_logger.error(f"LastFM error: {str(e)}")
            for track in top_tracks:
                track_name = track.item.title
                query = f"{artist_name} {track_name}"
                yt_url = (
                    f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={requests.utils.quote(query)}"
                    f"&key={yt_key}&type=video&maxResults=1"
                )
                yt_resp = requests.get(yt_url)
                yt_items = yt_resp.json().get("items", [])
                if yt_items:
                    video_id = yt_items[0]["id"]["videoId"]
                    result = {"videoId": video_id, "track": track_name, "artist": artist_name}
                    break
                time.sleep(0.2)
        except Exception as e:
            result = {"error": str(e)}
            self.sonobarr_logger.error(f"Prehear error: {str(e)}")
        socketio.emit("prehear_result", result, room=sid)


app = Flask(__name__)
app.secret_key = "secret_key"
socketio = SocketIO(app)
data_handler = DataHandler()


@app.route("/")
def home():
    return render_template("base.html")


@socketio.on("side_bar_opened")
def side_bar_opened():
    if data_handler.lidarr_items:
        ret = {"Status": "Success", "Data": data_handler.lidarr_items, "Running": not data_handler.stop_event.is_set()}
        socketio.emit("lidarr_sidebar_update", ret)


@socketio.on("get_lidarr_artists")
def get_lidarr_artists():
    thread = threading.Thread(target=data_handler.get_artists_from_lidarr, name="Lidarr_Thread")
    thread.daemon = True
    thread.start()


@socketio.on("finder")
def find_similar_artists(data):
    thread = threading.Thread(target=data_handler.find_similar_artists, args=(data,), name="Find_Similar_Thread")
    thread.daemon = True
    thread.start()


@socketio.on("adder")
def add_artists(data):
    thread = threading.Thread(target=data_handler.add_artists, args=(data,), name="Add_Artists_Thread")
    thread.daemon = True
    thread.start()


@socketio.on("connect")
def connection():
    data_handler.connection()


@socketio.on("disconnect")
def disconnection():
    data_handler.disconnection()


@socketio.on("load_settings")
def load_settings():
    data_handler.load_settings()


@socketio.on("update_settings")
def update_settings(data):
    data_handler.update_settings(data)
    data_handler.save_config_to_file()


@socketio.on("start_req")
def starter(data):
    data_handler.start(data)


@socketio.on("stop_req")
def stopper():
    data_handler.stop_event.set()


@socketio.on("load_more_artists")
def load_more_artists():
    thread = threading.Thread(target=data_handler.find_similar_artists, name="FindSimilar")
    thread.daemon = True
    thread.start()


@socketio.on("preview_req")
def preview(artist):
    data_handler.preview(artist)


@socketio.on("prehear_req")
def prehear_req(artist_name):
    thread = threading.Thread(target=data_handler.prehear, args=(artist_name, request.sid), name="PrehearThread")
    thread.daemon = True
    thread.start()


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
