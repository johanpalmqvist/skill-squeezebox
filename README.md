## logitech media server skill
A skill for controlling logitech media server and connected clients

## Description
This module controls streaming of content from a Logitech Media Server

## Examples
* "play electronic music"
* "play artist covenant"
* "play favorite slay radio"
* "pause music playback"
* "identify musical composition"
* "stop playback"

## Credits
Johan Palmqvist <johan.palmqvist-mycroft@kenkon.net>

## Configuring
Install this skill, then go to https://home.mycroft.ai and enter your Logitech Media Server details under Skills-\>Logitech Media Server Skill

## Current state
Working features:
  - play \<content\>
  - play \<content\> on \<player_name\>
  - play artist \<content\>
  - play favorite \<content\>
  - play genre \<content\>
  - play \<content\> music
  - play playlist \<content\>
  - play podcast \<content\>
  - play radio \<content\>
  - identify musical composition
  - stop music
  - pause music
  - resume music
  - next track
  - previous track
  - increase volume
  - decrease volume
  - maximum volume
  - mute volume
  - unmute volume
  - power off \<player_name\>
  - power on \<player_name\>

\<content\> can be:
  - \<song\>
  - \<song\> by \<artist\>
  - \<album\>
  - \<album\> by \<artist\>
  - \<artist\>
  - \<genre\>
  - \<favorite\>
  - \<playlist\>
  - \<podcast\>
  - \<radio\>

\<player_name\> can be the valid name of a destination client. You generally only need:
  - \<name of squeeze client\>

## Sound Effects:
To use sound effects as feedback add WAVE files to the skill sounds/ directory using the following names:
  - cachenotupdated.wav
  - cacheupdated.wav
  - nexttrack.wav
  - pause.wav
  - playernotfound.wav
  - playingcontent.wav
  - poweroff.wav
  - poweron.wav
  - previoustrack.wav
  - resume.wav
  - stop.wav
  - volumedown.wav
  - volumemute.wav
  - volumeset.wav
  - volumeunmute.wav
  - volumeup.wav

## Known issues:
  - If you have a large library it can take minutes to initialise, and then another chunk of time (tens of seconds) to determine what you specified as \<content\>.
    This can be mitigated to some degree by local caching of formatted content and verbally specifying source type when requesting playback of \<content\>.
  - Running the skill on devices with limited resources may cause out of memory issues if the library is too large (YMMV).
  - If the skill takes too long to respond the CommonPlay system skips the results. This is intermittent even with identical queries.
  - No default set of WAVE files included for sound effects (as alternative to spoken dialogue).
  - Pause/Resume/Next/Previous currently only works on default player

## TODO/IDEAS
  - fix bugs
  - better random selection
  - better playlist/radio/podcast handling (radio is currently handled as favorites, which actually seems to work quite well)
  - memory usage optimizations

## Action / Logic
When \<content\> computation matches:
  - song: a single song is played
  - artist: all of the music by the artist is put on randomly
  - album: the album is played in order (unless random mode is specified)
  - genre: all of the music tagged with that genre is put on randomly
