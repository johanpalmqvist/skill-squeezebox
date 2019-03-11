import gzip
import json
import re
from collections import defaultdict
from fuzzywuzzy.process import extractOne
from fuzzywuzzy.fuzz import QRatio
from fuzzywuzzy.utils import full_process
from mycroft.skills.core import intent_file_handler
from mycroft.util.log import LOG
from mycroft.skills.common_play_skill import CommonPlaySkill, CPSMatchLevel
from mycroft.util import play_wav
from os.path import dirname, join, abspath, isfile
from os import stat
from .lms_client import LMSClient

__author__ = "johanpalmqvist"


class SqueezeBoxMediaSkill(CommonPlaySkill):
    def __init__(self):
        super(SqueezeBoxMediaSkill, self).__init__("SqueezeBox Media Skill")

    def initialize(self):
        LOG.info("Initializing SqueezeBox Media skill")
        super().initialize()
        # Setup handlers for playback control messages
        self.add_event("mycroft.audio.service.next", self.handle_nexttrack)
        self.add_event("mycroft.audio.service.prev", self.handle_previoustrack)
        self.add_event("mycroft.audio.service.pause", self.handle_pause)
        self.add_event("mycroft.audio.service.resume", self.handle_resume)
        if not self.settings:
            raise ValueError("Could not load settings")
        LOG.debug("Settings: {}".format(self.settings))
        try:
            self.lms = LMSClient(
                self.settings["server"],
                self.settings["port"],
                self.settings["username"],
                self.settings["password"],
            )
        except Exception as e:
            LOG.error(
                "Could not load server configuration. Exception: {}".format(e)
            )
            raise ValueError("Could not load server configuration.")
        try:
            self.default_player_name = self.settings["default_player_name"]
        except Exception as e:
            LOG.error("Default player name not set. Exception: {}".format(e))
            raise ValueError("Default player name not set.")
        self.speak_dialog_enabled = self.settings.get(
            "speak_dialog_enabled", False
        )
        self.media_library_source_enabled = self.settings.get(
            "media_library_source_enabled", True
        )
        self.favorite_source_enabled = self.settings.get(
            "favorite_source_enabled", True
        )
        self.playlist_source_enabled = self.settings.get(
            "playlist_source_enabled", True
        )
        self.podcast_source_enabled = self.settings.get(
            "podcast_source_enabled", True
        )
        self.sources_cache_filename = join(
            abspath(dirname(__file__)), "sources_cache.json.gz"
        )
        self.library_cache_filename = join(
            abspath(dirname(__file__)), "library_cache.json.gz"
        )
        self.library_total_duration_state_filename = join(
            abspath(dirname(__file__)), "library_total_duration_state.json.gz"
        )
        self.scorer = QRatio
        self.processor = full_process
        self.get_sources("connecting...")

    # Get sources
    def get_sources(self, message):
        LOG.info("Loading content")
        self.sources = defaultdict(dict)
        LOG.debug("Selecting default backend")
        default_backend, default_playerid = self.get_playerid(None)

        # Album, Artist, Genre, Title sources (cache server response)
        if self.media_library_source_enabled:
            self.update_sources_cache()
            self.load_sources_cache()
        else:
            LOG.info("Media Library source disabled. Skipped.")

        # Favorite sources (query server)
        if self.favorite_source_enabled:
            self.sources["favorite"] = defaultdict(dict)
            favorites = self.lms.get_favorites()
            for favorite in favorites:
                try:
                    if not self.sources["favorite"][favorite["name"]]:
                        if (
                            "audio" in favorite["type"]
                            and favorite["isaudio"] == 1
                        ):
                            self.sources["favorite"][favorite["name"]][
                                "favorite_id"
                            ] = favorite["id"]
                            LOG.debug(
                                "Loaded favorite: {}".format(favorite["name"])
                            )
                except Exception as e:
                    LOG.warning(
                        "Failed to load favorite. Exception: {}".format(e)
                    )
            LOG.info("Loaded favorites")
        else:
            LOG.info("Favorite source disabled. Skipped.")

        # Playlist sources (query server)
        if self.playlist_source_enabled:
            self.sources["playlist"] = defaultdict(dict)
            playlists = self.lms.get_playlists()
            for playlist in playlists:
                try:
                    if not self.sources["playlist"][playlist["playlist"]]:
                        self.sources["playlist"][playlist["playlist"]][
                            "playlist_id"
                        ] = playlist["id"]
                        LOG.debug(
                            "Loaded playlist: {}".format(playlist["playlist"])
                        )
                except Exception as e:
                    LOG.warning(
                        "Failed to load playlist. Exception: {}".format(e)
                    )
            LOG.info("Loaded playlists")
        else:
            LOG.info("Playlist source disabled. Skipped.")

        # Podcast sources (query server)
        if self.podcast_source_enabled:
            self.sources["podcast"] = defaultdict(dict)
            podcasts = self.lms.get_podcasts(default_playerid)
            for podcast in podcasts:
                try:
                    if not self.sources["podcast"][podcast["name"]]:
                        if (
                            not podcast["hasitems"] == 0
                            and podcast["isaudio"] == 0
                        ):
                            self.sources["podcast"][podcast["name"]][
                                "podcast_id"
                            ] = podcast["id"]
                            LOG.debug(
                                "Loaded podcast: {}".format(podcast["name"])
                            )
                except Exception as e:
                    LOG.warning(
                        "Failed to load podcast. Exception: {}".format(e)
                    )
            LOG.info("Loaded podcasts")
        else:
            LOG.info("Podcast source disabled. Skipped.")

        LOG.info("Loaded content")

    # Get playerid matching input (fallback to default_player_name setting)
    def get_playerid(self, backend):
        if backend is None:
            backend = self.default_player_name.title()
        LOG.debug("Requested backend: {}".format(backend))
        players = self.lms.get_players()
        player_names = []
        for player in players:
            LOG.debug(
                "Playerid={}, Name={}".format(
                    player["playerid"], player["name"]
                )
            )
            player_names.append(player["name"])
        key, confidence = extractOne(
            backend,
            player_names,
            processor=self.processor,
            scorer=self.scorer,
            score_cutoff=0,
        )
        confidence = confidence / 100.0
        LOG.debug("Player confidence: {}".format(confidence))
        if confidence > 0.5:
            extracted_player_name = key
            LOG.debug("Extracted backend: {}".format(extracted_player_name))
        else:
            LOG.error("Couldn't find player matching: {}".format(backend))
            data = {"backend": backend}
            self.play_dialog("playernotfound.wav", "playernotfound", data)
            return None, None
        for player in players:
            if extracted_player_name == player["name"]:
                backend = player["name"]
                playerid = player["playerid"]
        return backend, playerid

    # Get backend name from phrase
    def get_backend(self, phrase):
        LOG.debug("Backend match phrase: {}".format(phrase))
        match = re.search(self.translate("backend_regex"), phrase)
        LOG.debug("Backend match regex: {}".format(match))
        if match:
            backend = match.group("backend")
            LOG.debug("Backend match found: {}".format(backend))
        else:
            backend = None
            LOG.debug("Backend match not found: {}".format(backend))
        return backend

    # Load library cache file
    def load_library_cache(self):
        LOG.info("Loading library cache")
        try:
            with gzip.GzipFile(self.library_cache_filename) as f:
                self.results = json.loads(f.read().decode("utf-8"))
            LOG.info("Loaded library cache")
        except Exception as e:
            LOG.error("Library cache not found. Exception: {}".format(e))

    # Get library total duration from state file
    def load_library_total_duration(self):
        LOG.info("Loading library total duration state")
        try:
            with gzip.GzipFile(
                self.library_total_duration_state_filename
            ) as f:
                library_total_duration = json.loads(f.read().decode("utf-8"))
            LOG.info("Loaded library total duration state")
            return library_total_duration
        except Exception as e:
            LOG.warning(
                "Creating missing duration file. Exception: {}".format(e)
            )
            self.save_library_total_duration()
            return self.lms.get_library_total_duration()

    # Load sources cache file
    def load_sources_cache(self):
        LOG.info("Loading sources cache")
        try:
            with gzip.GzipFile(self.sources_cache_filename) as f:
                self.sources = json.loads(f.read().decode("utf-8"))
            LOG.info("Loaded sources cache")
        except Exception as e:
            LOG.error("Sources cache does not exist. Exception: {}.".format(e))

    # Save library cache file
    def save_library_cache(self):
        LOG.info("Saving library cache")
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": ["query", ["titles", "0", "-1", "tags:aegilpstu"]],
        }
        with gzip.GzipFile(self.library_cache_filename, "w") as f:
            f.write(
                json.dumps(
                    self.lms.lms_request(payload)["result"]["titles_loop"],
                    sort_keys=True,
                    indent=4,
                    ensure_ascii=False,
                ).encode("utf-8")
            )
        LOG.info("Saved library cache")

    # Save library total duration to state file
    def save_library_total_duration(self):
        LOG.info("Saving library total duration state")
        with gzip.GzipFile(
            self.library_total_duration_state_filename, "w"
        ) as f:
            f.write(
                json.dumps(
                    self.lms.get_library_total_duration(),
                    sort_keys=True,
                    indent=4,
                    ensure_ascii=False,
                ).encode("utf-8")
            )
        LOG.info("Saved library total duration state")

    # Save sources cache file
    def save_sources_cache(self):
        self.update_library_cache()
        self.load_library_cache()

        # Artist sources
        self.sources["artist"] = defaultdict(dict)
        for result in self.results:
            try:
                if not self.sources["artist"][result["artist"]]:
                    self.sources["artist"][result["artist"]][
                        "artist_id"
                    ] = result["artist_id"]
                    self.sources["artist"][result["artist"]]["album"] = []
            except Exception as e:
                LOG.warning("Failed to load artist. Exception: {}".format(e))
        LOG.info("Loaded artists")

        # Album sources
        self.sources["album"] = defaultdict(dict)
        self.sources["title"] = defaultdict(dict)
        for result_albums in self.results:
            try:
                if not self.sources["album"][result_albums["album"]]:
                    self.sources["album"][result_albums["album"]][
                        "album_id"
                    ] = result_albums["album_id"]
                    self.sources["album"][result_albums["album"]]["title"] = []
                    self.sources["album"][
                        "{} by {}".format(
                            result_albums["album"], result_albums["artist"]
                        )
                    ]["album_id"] = result_albums["album_id"]
                    self.sources["album"][
                        "{} by {}".format(
                            result_albums["album"], result_albums["artist"]
                        )
                    ]["title"] = []
                    self.sources["artist"][result_albums["artist"]][
                        "album"
                    ].append(result_albums["album_id"])
                    # Title sources
                    for result_title in self.results:
                        try:
                            if (
                                result_title["album_id"]
                                == result_albums["album_id"]
                            ):
                                self.sources["title"][
                                    result_title["title"]
                                ] = {
                                    "title_id": result_title["id"],
                                    "url": result_title["url"],
                                }
                                artist_title = "{} by {}".format(
                                    result_title["title"],
                                    result_title["artist"],
                                )
                                self.sources["title"][artist_title] = {
                                    "title_id": result_title["id"],
                                    "url": result_title["url"],
                                }
                                self.sources["album"][result_albums["album"]][
                                    "title"
                                ].append(result_title["id"])
                                self.sources["album"][
                                    "{} by {}".format(
                                        result_albums["album"],
                                        result_albums["artist"],
                                    )
                                ]["title"].append(result_title["id"])
                        except Exception as e:
                            LOG.warning(
                                "Failed to load album. Exception: {}".format(e)
                            )
                    LOG.debug(
                        "Loaded titles for album: {}".format(
                            result_albums["album"]
                        )
                    )
            except Exception as e:
                LOG.warning("Failed to load album. Exception: {}".format(e))
        LOG.info("Loaded albums")

        # Genre sources
        self.sources["genre"] = defaultdict(dict)
        for result_genres in self.results:
            try:
                if not self.sources["genre"][result_genres["genre"]]:
                    self.sources["genre"][result_genres["genre"]][
                        "genre_id"
                    ] = result_genres["genre_id"]
                    LOG.debug(
                        "Loaded genre: {}".format(result_genres["genre"])
                    )
            except Exception as e:
                LOG.warning("Failed to load genre. Exception: {}".format(e))
        LOG.info("Loaded genres")

        LOG.info("Saving sources cache")
        with gzip.GzipFile(self.sources_cache_filename, "w") as f:
            f.write(
                json.dumps(
                    self.sources, sort_keys=True, indent=4, ensure_ascii=False
                ).encode("utf-8")
            )
        LOG.info("Saved sources cache")

    # Update library cache file if LMS library seems to differ depending on
    # library total duration
    def update_library_cache(self):
        library_cache = False
        if isfile(self.library_cache_filename):
            if stat(self.library_cache_filename).st_size > 26:
                library_cache = True
        if (
            self.lms.get_library_total_duration()
            == self.load_library_total_duration()
            and library_cache
        ):
            LOG.info("Library total duration unchanged. Not updating cache.")
            return False
        else:
            LOG.info("Library total duration changed. Updating cache.")
            self.save_library_cache()
            self.save_library_total_duration()
            return True

    # Update sources cache file if LMS library seems to differ depending on
    # library total duration
    def update_sources_cache(self):
        sources_cache = False
        if isfile(self.sources_cache_filename):
            if stat(self.sources_cache_filename).st_size > 26:
                sources_cache = True
        if (
            self.lms.get_library_total_duration()
            == self.load_library_total_duration()
            and sources_cache
        ):
            LOG.info("Library total duration unchanged. Not updating cache.")
            return False
        else:
            LOG.info("Library total duration changed. Updating cache.")
            self.save_sources_cache()
            self.save_library_total_duration()
            return True

    # Play speech dialogue or sound feedback
    # (fallback to speech if sound is None)
    def play_dialog(self, sound_dialog, speak_dialog_name, data):
        if self.speak_dialog_enabled == "True" or not sound_dialog:
            self.speak_dialog(speak_dialog_name, data=data)
        else:
            path = join(abspath(dirname(__file__)), sound_dialog)
            if isfile(path):
                play_wav(path)
            else:
                self.speak_dialog(speak_dialog_name, data=data)

    # Get best playlist match and confidence
    def get_best_playlist(self, playlist):
        LOG.debug("get_best_playlist: playlist={}".format(playlist))
        key, confidence = extractOne(
            playlist.lower(),
            self.sources["playlist"].keys(),
            processor=self.processor,
            scorer=self.scorer,
            score_cutoff=0,
        )
        confidence = confidence / 100.0
        LOG.debug(
            "get_best_playlist: Chose key={}, confidence={}".format(
                key, confidence
            )
        )
        return key, confidence

    # Get best album match and confidence
    def get_best_album(self, album):
        LOG.debug("get_best_album: album={}".format(album))
        key, confidence = extractOne(
            album.lower(),
            self.sources["album"].keys(),
            processor=self.processor,
            scorer=self.scorer,
            score_cutoff=0,
        )
        confidence = confidence / 100.0
        LOG.debug(
            "get_best_album: Chose key={}, confidence={}".format(
                key, confidence
            )
        )
        return key, confidence

    # Get best artist match and confidence
    def get_best_artist(self, artist):
        LOG.debug("get_best_artist: artist={}".format(artist))
        key, confidence = extractOne(
            artist.lower(),
            self.sources["artist"].keys(),
            processor=self.processor,
            scorer=self.scorer,
            score_cutoff=0,
        )
        confidence = confidence / 100.0
        LOG.debug(
            "get_best_artist: Chose key={}, confidence={}".format(
                key, confidence
            )
        )
        return key, confidence

    # Get best favorite match and confidence
    def get_best_favorite(self, favorite):
        LOG.debug("get_best_favorite: favorite={}".format(favorite))
        key, confidence = extractOne(
            favorite.lower(),
            self.sources["favorite"].keys(),
            processor=self.processor,
            scorer=self.scorer,
            score_cutoff=0,
        )
        confidence = confidence / 100.0
        LOG.debug(
            "get_best_favorite: Chose key={}, confidence={}".format(
                key, confidence
            )
        )
        return key, confidence

    # Get best genre match and confidence
    def get_best_genre(self, genre):
        LOG.debug("get_best_genre: genre={}".format(genre))
        key, confidence = extractOne(
            genre.lower(),
            self.sources["genre"].keys(),
            processor=self.processor,
            scorer=self.scorer,
            score_cutoff=0,
        )
        confidence = confidence / 100.0
        LOG.debug(
            "get_best_genre: Chose key={}, confidence={}".format(
                key, confidence
            )
        )
        return key, confidence

    # Get best podcast match and confidence
    def get_best_podcast(self, podcast):
        LOG.debug("get_best_podcast: podcast={}".format(podcast))
        key, confidence = extractOne(
            podcast.lower(),
            self.sources["podcast"].keys(),
            processor=self.processor,
            scorer=self.scorer,
            score_cutoff=0,
        )
        confidence = confidence / 100.0
        LOG.debug(
            "get_best_podcast: Chose key={}, confidence={}".format(
                key, confidence
            )
        )
        return key, confidence

    # Get best title match and confidence
    def get_best_title(self, title):
        LOG.debug("get_best_title: title={}".format(title))
        key, confidence = extractOne(
            title.lower(),
            self.sources["title"].keys(),
            processor=self.processor,
            scorer=self.scorer,
            score_cutoff=0,
        )
        confidence = confidence / 100.0
        LOG.debug(
            "get_best_title: Chose key={}, confidence={}".format(
                key, confidence
            )
        )
        return key, confidence

    ######################################################################
    # Intent handling
    def CPS_match_query_phrase(self, phrase):
        LOG.debug("CPS_match_query_phrase={}".format(phrase))

        match = re.search(self.translate("squeezebox_bonus_regex"), phrase)
        if match:
            LOG.debug(
                "CPS_match_query_phrase: bonus found, phrase={}".format(phrase)
            )
            bonus = 0.1
        else:
            LOG.debug(
                "CPS_match_query_phrase: bonus not found, phrase={}".format(
                    phrase
                )
            )
            bonus = 0

        LOG.debug(
            "CPS_match_query_phrase: on_squeezebox_regex={}".format(
                self.translate("on_squeezebox_regex")
            )
        )
        phrase = re.sub(
            self.translate("on_squeezebox_regex"), "", phrase
        ).strip()

        backend, playerid = self.get_playerid(self.get_backend(phrase))
        phrase = re.sub(self.translate("backend_regex"), "", phrase)

        confidence, data = self.continue_playback(phrase, bonus)
        if not data:
            confidence, data = self.specific_query(phrase, bonus)
            if not data:
                confidence, data = self.generic_query(phrase, bonus)
        if data:
            LOG.debug("CPS_match_query_phrase: data={}".format(data))
            LOG.debug(
                "CPS_match_query_phrase: confidence={}".format(confidence)
            )
            if confidence > 0.9:
                confidence = CPSMatchLevel.EXACT
            elif confidence > 0.7:
                confidence = CPSMatchLevel.MULTI_KEY
            elif confidence > 0.5:
                confidence = CPSMatchLevel.TITLE
            else:
                confidence = CPSMatchLevel.CATEGORY
            data["backend"] = backend
            data["playerid"] = playerid
            return phrase, confidence, data
        return None

    def continue_playback(self, phrase, bonus):
        LOG.debug(
            "continue_playback: phrase={}, bonus={}".format(phrase, bonus)
        )
        if phrase.strip() == "squeezebox":
            return (1.0, {"data": None, "name": None, "type": "continue"})
        else:
            return None, None

    def specific_query(self, phrase, bonus):
        LOG.debug("specific_query: phrase={}, bonus={}".format(phrase, bonus))

        # Check album
        match = re.match(self.translate("album_regex"), phrase)
        LOG.debug("album specific_query: match={}".format(match))
        if match:
            bonus += 0.1
            album = match.groupdict()["album"]
            LOG.debug("album specific_query: album={}".format(album))
            album, conf = self.get_best_album(album)
            if not album:
                LOG.debug("specific_query: album not found")
                return None, None
            confidence = min(conf + bonus, 1.0)
            LOG.debug("specific_query: album confidence={}".format(confidence))
            album_id = self.sources["album"][album]["album_id"]
            return (
                confidence,
                {"data": album_id, "name": album, "type": "album"},
            )

        # Check artist
        match = re.match(self.translate("artist_regex"), phrase)
        LOG.debug("artist specific_query: match={}".format(match))
        if match:
            bonus += 0.1
            artist = match.groupdict()["artist"]
            LOG.debug("artist specific_query: artist={}".format(artist))
            artist, conf = self.get_best_artist(artist)
            if not artist:
                LOG.debug("specific_query: artist not found")
                return None, None
            confidence = min(conf + bonus, 1.0)
            LOG.debug(
                "specific_query: artist confidence={}".format(confidence)
            )
            artist_id = self.sources["artist"][artist]["artist_id"]
            return (
                confidence,
                {"data": artist_id, "name": artist, "type": "artist"},
            )

        # Check title
        match = re.match(self.translate("title_regex"), phrase)
        LOG.debug("title specific_query: match={}".format(match))
        if match:
            title = match.groupdict()["title"]
            LOG.debug("title specific_query: title={}".format(title))
            title, conf = self.get_best_title(title)
            if not title:
                LOG.debug("specific_query: title not found")
                return None, None
            confidence = min(conf + bonus, 1.0)
            LOG.debug("specific_query: title confidence={}".format(confidence))
            url = self.sources["title"][title]["url"]
            return (confidence, {"data": url, "name": title, "type": "title"})

        # Check genre
        match = re.match(self.translate("genre_regex"), phrase)
        LOG.debug("genre specific_query: match={}".format(match))
        if match:
            bonus += 0.1
            genre = match.groupdict()["genre"]
            LOG.debug("genre specific_query: genre={}".format(genre))
            genre, conf = self.get_best_genre(genre)
            if not genre:
                LOG.debug("specific_query: genre not found")
                return None, None
            confidence = min(conf + bonus, 1.0)
            LOG.debug("specific_query: genre confidence={}".format(confidence))
            genre_id = self.sources["genre"][genre]["genre_id"]
            return (
                confidence,
                {"data": genre_id, "name": genre, "type": "genre"},
            )

        # Check playlist
        match = re.match(self.translate("playlist_regex"), phrase)
        LOG.debug("playlist specific_query: match={}".format(match))
        if match:
            bonus += 0.1
            playlist = match.groupdict()["playlist"]
            LOG.debug("playlist specific_query: playlist={}".format(playlist))
            playlist, conf = self.get_best_playlist(playlist)
            if not playlist:
                LOG.debug("specific_query: playlist not found")
                return None, None
            confidence = min(conf + bonus, 1.0)
            LOG.debug(
                "specific_query: playlist confidence={}".format(confidence)
            )
            return (
                confidence,
                {"data": playlist, "name": playlist, "type": "playlist"},
            )

        # Check favorite
        match = re.match(self.translate("favorite_regex"), phrase)
        LOG.debug("favorite specific_query: match={}".format(match))
        if match:
            bonus += 0.1
            favorite = match.groupdict()["favorite"]
            LOG.debug("favorite specific_query: favorite={}".format(favorite))
            favorite, conf = self.get_best_favorite(favorite)
            if not favorite:
                LOG.debug("specific_query: favorite not found")
                return None, None
            confidence = min(conf + bonus, 1.0)
            LOG.debug(
                "specific_query: favorite confidence={}".format(confidence)
            )
            favorite_id = self.sources["favorite"][favorite]["favorite_id"]
            return (
                confidence,
                {"data": favorite_id, "name": favorite, "type": "favorite"},
            )

        # Check podcast
        match = re.match(self.translate("podcast_regex"), phrase)
        LOG.debug("podcast specific_query: match={}".format(match))
        if match:
            bonus += 0.1
            podcast = match.groupdict()["podcast"]
            LOG.debug("podcast specific_query: podcast={}".format(podcast))
            podcast, conf = self.get_best_podcast(podcast)
            if not podcast:
                LOG.debug("specific_query: podcast not found")
                return None, None
            confidence = min(conf + bonus, 1.0)
            LOG.debug(
                "specific_query: podcast confidence={}".format(confidence)
            )
            podcast_id = self.sources["podcast"][podcast]["podcast_id"]
            return (
                confidence,
                {"data": podcast_id, "name": podcast, "type": "podcast"},
            )

        return None, None

    def generic_query(self, phrase, bonus):
        # Fallback to search all entries if type is unknown (slower)
        LOG.debug("generic_query: phrase={}, bonus={}".format(phrase, bonus))
        playlist, conf = self.get_best_playlist(phrase)
        if conf > 0.7:
            return (
                conf,
                {"data": playlist, "name": playlist, "type": "playlist"},
            )
        favorite, conf = self.get_best_favorite(phrase)
        if conf > 0.7:
            favorite_id = self.sources["favorite"][favorite]["favorite_id"]
            return (
                conf,
                {"data": favorite_id, "name": favorite, "type": "favorite"},
            )
        podcast, conf = self.get_best_podcast(phrase)
        if conf > 0.7:
            podcast_id = self.sources["podcast"][podcast]["podcast_id"]
            return (
                conf,
                {"data": podcast_id, "name": podcast, "type": "podcast"},
            )
        genre, conf = self.get_best_genre(phrase)
        if conf > 0.7:
            genre_id = self.sources["genre"][genre]["genre_id"]
            return (conf, {"data": genre_id, "name": genre, "type": "genre"})
        artist, conf = self.get_best_artist(phrase)
        if conf > 0.7:
            artist_id = self.sources["artist"][artist]["artist_id"]
            return (
                conf,
                {"data": artist_id, "name": artist, "type": "artist"},
            )
        album, conf = self.get_best_album(phrase)
        if conf > 0.7:
            album_id = self.sources["album"][album]["album_id"]
            return (conf, {"data": album_id, "name": album, "type": "album"})
        title, conf = self.get_best_title(phrase)
        if conf > 0.7:
            url = self.sources["title"][title]["url"]
            return (conf, {"data": url, "name": title, "type": "title"})

        return None, None

    def CPS_start(self, phrase, data):
        LOG.debug("CPS_start: phrase={}, data={}".format(phrase, data))
        LOG.info(
            "CPS_start: Playing {} ({}) on {} player".format(
                data["name"], data["type"], data["backend"]
            )
        )
        dialog_data = {
            "name": data["name"],
            "type": data["type"],
            "backend": data["backend"],
        }
        self.play_dialog("playingcontent.wav", "playing", dialog_data)

        if data["type"] == "continue":
            self.continue_current_playlist(None)
        elif data["type"] == "title":
            tracklist = []
            # Get title url
            url = self.sources["title"][data["name"]]["url"]
            tracklist.append(url)
            try:
                self.lms.play_tracklist(data["playerid"], tracklist)
            except Exception as e:
                self.log.exception()
        elif data["type"] == "album":
            # Get title url's for album
            album = self.sources["album"][data["name"]]["album_id"]
            try:
                self.lms.play_album(data["playerid"], album)
            except Exception as e:
                self.log.exception()
        elif data["type"] == "artist":
            # Get album's for artist
            artist = self.sources["artist"][data["name"]]["artist_id"]
            try:
                self.lms.play_artist(data["playerid"], artist)
            except Exception as e:
                self.log.exception()
        elif data["type"] == "favorite":
            # Get favorites
            favorite = self.sources["favorite"][data["name"]]["favorite_id"]
            try:
                self.lms.play_favorite(data["playerid"], favorite)
            except Exception as e:
                self.log.exception()
        elif data["type"] == "genre":
            # Get genres
            genre = self.sources["genre"][data["name"]]["genre_id"]
            try:
                self.lms.play_genre(data["playerid"], genre)
            except Exception as e:
                self.log.exception()
        elif data["type"] == "playlist":
            # Get playlists
            playlist = data["name"]
            try:
                self.lms.play_playlist(data["playerid"], playlist)
            except Exception as e:
                self.log.exception()
        elif data["type"] == "podcast":
            # Get podcasts
            podcast = self.sources["podcast"][data["name"]]["podcast_id"]
            try:
                self.lms.play_podcast(data["playerid"], podcast)
            except Exception as e:
                self.log.exception()

    def handle_pause(self, message):
        LOG.info("Handling pause request")
        backend, playerid = self.get_playerid(message.data.get("backend"))
        self.lms.pause_playlist(playerid)
        data = {}
        self.play_dialog("pause.wav", "pause", data)

    def handle_resume(self, message):
        LOG.info("Handling resume request")
        backend, playerid = self.get_playerid(message.data.get("backend"))
        self.lms.resume_playlist(playerid)
        data = {}
        self.play_dialog("resume.wav", "resume", data)

    def handle_nexttrack(self, message):
        LOG.info("Handling next track request")
        backend, playerid = self.get_playerid(message.data.get("backend"))
        self.lms.nexttrack_playlist(playerid)
        data = {}
        self.play_dialog("nexttrack.wav", "nexttrack", data)

    def handle_previoustrack(self, message):
        LOG.info("Handling previous track request")
        backend, playerid = self.get_playerid(message.data.get("backend"))
        self.lms.previoustrack_playlist(playerid)
        data = {}
        self.play_dialog("previoustrack.wav", "previoustrack", data)

    @intent_file_handler("Stop.intent")
    def handle_stop(self, message):
        LOG.info("Handling stop request")
        backend, playerid = self.get_playerid(message.data.get("backend"))
        self.lms.stop_playlist(playerid)
        data = {}
        self.play_dialog("stop.wav", "stop", data)

    @intent_file_handler("VolumeUp.intent")
    def handle_volumeup(self, message):
        LOG.info("Handling volume up request")
        backend, playerid = self.get_playerid(message.data.get("backend"))
        self.lms.volumeup(playerid)
        data = {"volume": self.lms.get_volume(playerid)}
        self.play_dialog("volumeup.wav", "volumeup", data)

    @intent_file_handler("VolumeDown.intent")
    def handle_volumedown(self, message):
        LOG.info("Handling volume down request")
        backend, playerid = self.get_playerid(message.data.get("backend"))
        self.lms.volumedown(playerid)
        data = {"volume": self.lms.get_volume(playerid)}
        self.play_dialog("volumedown.wav", "volumedown", data)

    @intent_file_handler("VolumeQuarter.intent")
    def handle_volumequarter(self, message):
        LOG.info("Handling volume quarter request")
        backend, playerid = self.get_playerid(message.data.get("backend"))
        self.lms.volumeset(playerid, 25)
        data = {"volume": self.lms.get_volume(playerid)}
        self.play_dialog("volumeset.wav", "volumeset", data)

    @intent_file_handler("VolumeHalf.intent")
    def handle_volumehalf(self, message):
        LOG.info("Handling volume half request")
        backend, playerid = self.get_playerid(message.data.get("backend"))
        self.lms.volumeset(playerid, 50)
        data = {"volume": self.lms.get_volume(playerid)}
        self.play_dialog("volumeset.wav", "volumeset", data)

    @intent_file_handler("VolumeThreeQuarters.intent")
    def handle_volumethreequarters(self, message):
        LOG.info("Handling volume threequarters request")
        backend, playerid = self.get_playerid(message.data.get("backend"))
        self.lms.volumeset(playerid, 75)
        data = {"volume": self.lms.get_volume(playerid)}
        self.play_dialog("volumeset.wav", "volumeset", data)

    @intent_file_handler("VolumeMax.intent")
    def handle_volumemax(self, message):
        LOG.info("Handling volume max request")
        backend, playerid = self.get_playerid(message.data.get("backend"))
        self.lms.volumeset(playerid, 100)
        data = {"volume": self.lms.get_volume(playerid)}
        self.play_dialog("volumeset.wav", "volumeset", data)

    @intent_file_handler("VolumeMute.intent")
    def handle_volumemute(self, message):
        LOG.info("Handling volume mute request")
        backend, playerid = self.get_playerid(message.data.get("backend"))
        self.lms.volumemute(playerid)
        data = {"volume": self.lms.get_volume(playerid)}
        self.play_dialog("volumemute.wav", "volumemute", data)

    @intent_file_handler("VolumeUnmute.intent")
    def handle_volumeunmute(self, message):
        LOG.info("Handling volume unmute request")
        backend, playerid = self.get_playerid(message.data.get("backend"))
        self.lms.volumeunmute(playerid)
        data = {"volume": self.lms.get_volume(playerid)}
        self.play_dialog("volumeunmute.wav", "volumeunmute", data)

    @intent_file_handler("IdentifyTrack.intent")
    def handle_identifytrack(self, message):
        LOG.info("Handling identify track request")
        backend, playerid = self.get_playerid(message.data.get("backend"))
        mode = self.lms.get_current_mode(playerid)
        if mode == "play":
            try:
                artist = self.lms.get_current_artist(playerid)
            except Exception as e:
                artist = None
            title = self.lms.get_current_title(playerid)
            if not artist:
                data = {"title": title}
                self.play_dialog(None, "identifynoartist", data)
            else:
                data = {"title": title, "artist": artist}
                self.play_dialog(None, "identify", data)
        else:
            data = {"backend": backend, "mode": mode}
            self.play_dialog(None, "identifynoplay", data)

    @intent_file_handler("UpdateCache.intent")
    def handle_updatecache(self, message):
        LOG.info("Handling update cache request")
        if self.update_library_cache():
            data = {}
            self.play_dialog("cacheupdated.wav", "cacheupdated", data)
        else:
            data = {}
            self.play_dialog("cachenotupdated.wav", "cachenotupdated", data)


def create_skill():
    return SqueezeBoxMediaSkill()
