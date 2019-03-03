import requests

__author__ = "johanpalmqvist"

# Timeout time for LMS requests
TIMEOUT = 60


class LMSClient(object):
    def __init__(self, lms_server, lms_port, lms_username, lms_password):
        self.lms_server = lms_server
        self.lms_port = lms_port
        self.lms_username = lms_username
        self.lms_password = lms_password
        if self.lms_username and self.lms_password:
            self.lms_json_rpc_url = "http://{}:{}@{}:{}/jsonrpc.js".format(
                self.lms_username,
                self.lms_password,
                self.lms_server,
                self.lms_port,
            )
        else:
            self.lms_json_rpc_url = "http://{}:{}/jsonrpc.js".format(
                self.lms_server, self.lms_port
            )
        self.headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Content-type": "application/x-www-form-urlencoded",
        }

    # Send JSON-RPC request to LMS
    def lms_request(self, payload):
        try:
            response = requests.post(
                self.lms_json_rpc_url,
                json=payload,
                headers=self.headers,
                timeout=TIMEOUT,
            )
            return response.json()
        except Exception as e:
            raise Exception(
                "Could not connect to server {}: {}".format(
                    self.lms_json_rpc_url, e
                )
            )

    # Get players from LMS
    def get_players(self):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": ["", ["players", ""]],
        }
        players = self.lms_request(payload)["result"]["players_loop"]
        return_players = []
        for player in players:
            return_players.append(player)
        return return_players

    # Get favorites from LMS
    def get_favorites(self):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": ["", ["favorites", "items", 0, 1000]],
        }
        return self.lms_request(payload)["result"]["loop_loop"]

    # Get playlists from LMS
    def get_playlists(self):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": ["browselibrary", ["playlists", "items"]],
        }
        return self.lms_request(payload)["result"]["playlists_loop"]

    # Get podcasts from LMS
    def get_podcasts(self, playerid):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["podcasts", "items", 0, 1000]],
        }
        return self.lms_request(payload)["result"]["loop_loop"]

    # Get podcast episodes from LMS
    def get_podcasts_episodes(self, playerid, podcast_id):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [
                playerid,
                [
                    "podcasts",
                    "items",
                    0,
                    1000,
                    "item_id: {}".format(podcast_id),
                ],
            ],
        }
        return self.lms_request(payload)["result"]["loop_loop"]

    # Get latest podcast episode from LMS
    def get_podcasts_episodes_latest(self, playerid, podcast_id):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [
                playerid,
                ["podcasts", "items", 0, 1, "item_id: {}".format(podcast_id)],
            ],
        }
        return self.lms_request(payload)["result"]["loop_loop"]

    # Get albums from LMS
    def get_albums(self, playerid):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["albums", ""]],
        }
        return self.lms_request(payload)["result"]["albums_loop"]

    # Get artists from LMS
    def get_artists(self, playerid):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["artists", ""]],
        }
        return self.lms_request(payload)["result"]["artists_loop"]

    # Get genres from LMS
    def get_genres(self, playerid):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["genres", ""]],
        }
        return self.lms_request(payload)["result"]["genres_loop"]

    # Get titles from LMS
    def get_titles(self, playerid):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["titles", ""]],
        }
        return self.lms_request(payload)["result"]["titles_loop"]

    # Get library total duration from LMS
    def get_library_total_duration(self):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": ["query", ["info", "total", "duration", "?"]],
        }
        return self.lms_request(payload)["result"]["_duration"]

    # Add artist to playlist and start playback
    def play_artist(self, playerid, artist_id):
        self.playlist_shuffle(playerid, 1)
        self.playlist_repeat(playerid, 2)
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [
                playerid,
                [
                    "playlist",
                    "loadtracks",
                    "contributor.id={}".format(artist_id),
                ],
            ],
        }
        return self.lms_request(payload)

    # Add album to playlist and start playback
    def play_album(self, playerid, album_id):
        self.playlist_shuffle(playerid, 1)
        self.playlist_repeat(playerid, 2)
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [
                playerid,
                ["playlist", "loadtracks", "album.id={}".format(album_id)],
            ],
        }
        return self.lms_request(payload)

    # Add genre to playlist and start playback
    def play_genre(self, playerid, genre_id):
        self.playlist_shuffle(playerid, 1)
        self.playlist_repeat(playerid, 2)
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [
                playerid,
                ["playlist", "loadtracks", "genre.id={}".format(genre_id)],
            ],
        }
        return self.lms_request(payload)

    # Add tracklist to playlist and start playback
    def play_tracklist(self, playerid, tracklist):
        self.playlist_clear(playerid)
        self.playlist_shuffle(playerid, 1)
        self.playlist_repeat(playerid, 2)
        for track in tracklist:
            payload = {
                "id": 1,
                "method": "slim.request",
                "params": [playerid, ["playlist", "add", track]],
            }
            self.lms_request(payload)
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["play"]],
        }
        return self.lms_request(payload)

    # Add favorite to playlist and start playback
    def play_favorite(self, playerid, favorite_id):
        self.playlist_shuffle(playerid, 0)
        self.playlist_repeat(playerid, 0)
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [
                playerid,
                [
                    "favorites",
                    "playlist",
                    "play",
                    "item_id:{}".format(favorite_id),
                ],
            ],
        }
        return self.lms_request(payload)

    # Add podcast to playlist and start playback
    def play_podcast(self, playerid, podcast_id):
        self.playlist_shuffle(playerid, 0)
        self.playlist_repeat(playerid, 0)
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [
                playerid,
                [
                    "podcasts",
                    "playlist",
                    "play",
                    "item_id:{}".format(podcast_id),
                ],
            ],
        }
        return self.lms_request(payload)

    # Load playlist from server and start playback
    def play_playlist(self, playerid, playlist):
        self.playlist_shuffle(playerid, 1)
        self.playlist_repeat(playerid, 2)
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [
                playerid,
                [
                    "playlist",
                    "play",
                    "/var/lib/squeezeboxserver/playlists/{}.m3u".format(
                        playlist
                    ),
                ],
            ],
        }
        return self.lms_request(payload)

    # Load playlist from local file and start playback
    def play_local_playlist(self, playerid, playlist_file):
        import re

        fh = open(playlist_file, "r")
        data = fh.readlines()
        fh.close()
        tracklist = []
        for title in data:
            if not re.search("^#", title):
                tracklist.append(str.strip(title))
        return self.play_tracklist(playerid, tracklist)

    # Clear playlist
    def playlist_clear(self, playerid):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["playlist", "clear"]],
        }
        return self.lms_request(payload)

    # Pause playback
    def pause_playlist(self, playerid):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["pause"]],
        }
        return self.lms_request(payload)

    # Resume playback
    def resume_playlist(self, playerid):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["play"]],
        }
        return self.lms_request(payload)

    # Stop playback
    def stop_playlist(self, playerid):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["stop"]],
        }
        return self.lms_request(payload)

    # Play next track in playlist
    def nexttrack_playlist(self, playerid):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["playlist", "jump", "+1"]],
        }
        return self.lms_request(payload)

    # Play previous track in playlist
    def previoustrack_playlist(self, playerid):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["playlist", "jump", "-1"]],
        }
        return self.lms_request(payload)

    # Set playlist repeat
    def playlist_repeat(self, playerid, repeat):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["playlist", "repeat", repeat]],
        }
        return self.lms_request(payload)

    # Set playlist shuffle
    def playlist_shuffle(self, playerid, shuffle):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["playlist", "shuffle", shuffle]],
        }
        return self.lms_request(payload)

    # Increase volume
    def volumeup(self, playerid):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["mixer", "volume", "+5"]],
        }
        return self.lms_request(payload)

    # Decrease volume
    def volumedown(self, playerid):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["mixer", "volume", "-5"]],
        }
        return self.lms_request(payload)

    # Set volume
    def volumeset(self, playerid, volume):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["mixer", "volume", volume]],
        }
        return self.lms_request(payload)

    # Mute volume
    def volumemute(self, playerid):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["mixer", "muting", "1"]],
        }
        return self.lms_request(payload)

    # Unmute volume
    def volumeunmute(self, playerid):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["mixer", "muting", "0"]],
        }
        return self.lms_request(payload)

    # Get volume
    def get_volume(self, playerid):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["status"]],
        }
        return self.lms_request(payload)["result"]["mixer volume"]

    # Get artist currently playing
    def get_current_artist(self, playerid):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["artist", "?"]],
        }
        return self.lms_request(payload)["result"]["_artist"]

    # Get title currently playing
    def get_current_title(self, playerid):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["title", "?"]],
        }
        return self.lms_request(payload)["result"]["_title"]

    # Get current player mode status
    def get_current_mode(self, playerid):
        payload = {
            "id": 1,
            "method": "slim.request",
            "params": [playerid, ["status"]],
        }
        return self.lms_request(payload)["result"]["mode"]
