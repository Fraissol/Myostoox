#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Myostoox - AUDIO/vidéo player
# Copyright (C) 2026 O. Fraisse
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import os
import sys
import math
import random
import cairo
import re
import json
import time
import unicodedata
import gc
from collections import OrderedDict, deque
from functools import lru_cache
try:
    import ctypes
    _libc = ctypes.CDLL("libc.so.6")
    try: _libc.mallopt(-8, 2)
    except Exception: pass
except Exception:
    _libc = None

def trim_memory(force=False, full=False):
    """Libère de la mémoire process (glibc + GC).

    - force=False : au plus toutes les 30 s
    - full=False  : collect génération 0 seulement (rapide)
    - full=True   : collect complet + malloc_trim (changement de média, arrêt)
    """
    now = time.monotonic()
    last = getattr(trim_memory, "_last", 0.0)
    if not force and (now - last) < 30.0:
        return
    trim_memory._last = now
    try:
        if full:
            gc.collect()
        else:
            gc.collect(0)
    except Exception:
        pass
    try:
        if _libc is not None and (force or full):
            _libc.malloc_trim(0)
    except Exception:
        pass


import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gst", "1.0")
gi.require_version("GdkPixbuf", "2.0")
gi.require_version("GstVideo", "1.0")
try: gi.require_version("GstPbutils", "1.0")
except Exception: pass
try: gi.require_version("PangoCairo", "1.0")
except Exception: pass
from gi.repository import Gtk, Gdk, Gst, GdkPixbuf, GLib, Pango, GstVideo, Gio
try:
    from gi.repository import GdkX11
except Exception:
    GdkX11 = None
try:
    from gi.repository import PangoCairo
except Exception:
    PangoCairo = None
try:
    from gi.repository import GstPbutils
except Exception:
    GstPbutils = None
try:
    from mutagen import File as MutagenFile
    from mutagen.id3 import ID3, TIT2, TPE1, TALB, TDRC, ID3NoHeaderError
    from mutagen.flac import FLAC
    from mutagen.oggvorbis import OggVorbis
    from mutagen.oggopus import OggOpus
    from mutagen.mp4 import MP4
except ImportError:
    MutagenFile = None
    ID3 = TIT2 = TPE1 = TALB = TDRC = ID3NoHeaderError = None
import socket
import threading
import subprocess
import fcntl
import errno
import signal
import shutil


try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
    if _HERE and _HERE not in sys.path:
        sys.path.insert(0, _HERE)
except Exception:
    pass

_HAS_PLAYLIST_MOD = False
_HAS_METADATA_MOD = False
_HAS_SUBTITLES_MOD = False
_HAS_PLAYER_MOD = False
_HAS_THEMES_MOD = False
_HAS_MENUS_MOD = False
_menumod = None
_HAS_DIALOGS_MOD = False
_dialogsmod = None
_HAS_PLAYLIST_VIEW_MOD = False
_plviewmod = None
_HAS_SPECTRUM_MOD = False
_spectrummod = None
_HAS_COMPACT_MOD = False
_compactmod = None
_HAS_EQUALIZER_MOD = False
_eqmod = None
_HAS_MPRIS_MOD = False
_mprismod = None

try:
    from myostoox import playlist as _pl
    from myostoox.playlist import (
        is_stream as _pl_is_stream,
        is_cdda as _pl_is_cdda,
        is_dvd as _pl_is_dvd,
        is_bluray as _pl_is_bluray,
        is_special_source as _pl_is_special_source,
        path_to_uri as _pl_path_to_uri,
        atomic_write_json as _pl_atomic_write_json,
        is_audio_file as _pl_is_audio_file,
        is_pure_audio_file as _pl_is_pure_audio_file,
        is_video_file as _pl_is_video_file,
        AUDIO_EXTENSIONS as _PL_AUDIO_EXTENSIONS,
        VIDEO_EXTENSIONS as _PL_VIDEO_EXTENSIONS,
        STREAM_SCHEMES as _PL_STREAM_SCHEMES,
    )
    _HAS_PLAYLIST_MOD = True
except Exception as _pl_exc:
    print("myostoox.playlist:", _pl_exc, file=sys.stderr)

try:
    from myostoox import metadata as _md
    from myostoox.metadata import (
        format_time as _md_format_time,
        format_video_resolution as _md_format_video_resolution,
        format_video_fps as _md_format_video_fps,
        get_tag as _md_get_tag,
        load_external_cover as _md_load_external_cover,
        load_metadata as _md_load_metadata,
        parse_lrc_content as _md_parse_lrc_content,
        load_lyrics_for_file as _md_load_lyrics_for_file,
        SUBTITLE_FONT_DESC as _MD_SUBTITLE_FONT_DESC,
        SUBTITLE_EXTENSIONS as _MD_SUBTITLE_EXTENSIONS,
    )
    _HAS_METADATA_MOD = True
except Exception as _md_exc:
    print("myostoox.metadata:", _md_exc, file=sys.stderr)

try:
    from myostoox import subtitles as _st
    from myostoox.subtitles import (
        find_external_subtitles as _st_find_external_subtitles,
        guess_subtitle_encoding as _st_guess_subtitle_encoding,
        _discover_subtitle_languages as _st_discover_subtitle_languages,
        _discover_audio_track_labels as _st_discover_audio_track_labels,
        _disable_all_subtitles as _st_disable_all_subtitles,
        _prepare_external_subtitles_for as _st_prepare_external_subtitles_for,
        _register_external_subtitle_tracks as _st_register_external_subtitle_tracks,
        refresh_subtitle_tracks as _st_refresh_subtitle_tracks,
        refresh_audio_tracks as _st_refresh_audio_tracks,
        set_subtitle_track as _st_set_subtitle_track,
        _set_subtitle_track_impl as _st_set_subtitle_track_impl,
        set_subtitles_enabled as _st_set_subtitles_enabled,
        set_audio_track as _st_set_audio_track,
        _set_custom_audio_track as _st_set_custom_audio_track,
        _find_subtitle_list_index as _st_find_subtitle_list_index,
    )
    _HAS_SUBTITLES_MOD = True
except Exception as _st_exc:
    print("myostoox.subtitles:", _st_exc, file=sys.stderr)

try:
    from myostoox import player as _py
    from myostoox.player import (
        apply_safe_gstreamer_ranks as _py_apply_safe_gstreamer_ranks,
        _gst_set_rank as _py__gst_set_rank,
        gst_set_rank as _py_gst_set_rank,
        create_playbin as _py_create_playbin,
        _effective_perf_mode as _py_effective_perf_mode,
        _should_use_custom_pipeline as _py_should_use_custom_pipeline,
        _configure_playbin_buffers as _py_configure_playbin_buffers,
        _active_pipeline as _py_active_pipeline,
        _detach_equalizer_for_custom as _py_detach_equalizer_for_custom,
        _destroy_custom_pipeline as _py_destroy_custom_pipeline,
        _create_video_sink as _py_create_video_sink,
        _build_mkv_pipeline as _py_build_mkv_pipeline,
        _play_file_custom_mkv as _py_play_file_custom_mkv,
    )
    _HAS_PLAYER_MOD = True
except Exception as _py_exc:
    print("myostoox.player:", _py_exc, file=sys.stderr)



try:
    from myostoox import osd as _osdmod
    _HAS_OSD_MOD = True
except Exception as _osd_exc:
    print("myostoox.osd:", _osd_exc, file=sys.stderr)
    _HAS_OSD_MOD = False
    _osdmod = None

try:
    from myostoox.shortcuts import (
        on_key_press as _sc_on_key_press,
        normalize_key_name as _sc_normalize_key_name,
        event_to_shortcut as _sc_event_to_shortcut,
        shortcut_matches as _sc_shortcut_matches,
        is_text_input_focused as _sc_is_text_input_focused,
    )
    _HAS_SHORTCUTS_MOD = True
except Exception as _sc_exc:
    print("myostoox.shortcuts:", _sc_exc, file=sys.stderr)
    _HAS_SHORTCUTS_MOD = False

try:
    from myostoox import themes as _th
    from myostoox.themes import THEME_PALETTES as _TH_THEME_PALETTES, THEME_LABELS as _TH_THEME_LABELS
    _HAS_THEMES_MOD = True
except Exception as _th_exc:
    print("myostoox.themes:", _th_exc, file=sys.stderr)

try:
    from myostoox import menus as _menumod
    _HAS_MENUS_MOD = True
except Exception as _menus_exc:
    print("myostoox.menus:", _menus_exc, file=sys.stderr)

try:
    from myostoox import dialogs as _dialogsmod
    _HAS_DIALOGS_MOD = True
except Exception as _dialogs_exc:
    print("myostoox.dialogs:", _dialogs_exc, file=sys.stderr)

try:
    from myostoox import playlist_view as _plviewmod
    _HAS_PLAYLIST_VIEW_MOD = True
except Exception as _plview_exc:
    print("myostoox.playlist_view:", _plview_exc, file=sys.stderr)

try:
    from myostoox import spectrum as _spectrummod
    _HAS_SPECTRUM_MOD = True
except Exception as _spectrum_exc:
    print("myostoox.spectrum:", _spectrum_exc, file=sys.stderr)

try:
    from myostoox import compact_player as _compactmod
    _HAS_COMPACT_MOD = True
except Exception as _compact_exc:
    print("myostoox.compact_player:", _compact_exc, file=sys.stderr)

try:
    from myostoox import equalizer as _eqmod
    _HAS_EQUALIZER_MOD = True
except Exception as _equalizer_exc:
    print("myostoox.equalizer:", _equalizer_exc, file=sys.stderr)

try:
    from myostoox import mpris as _mprismod
    _HAS_MPRIS_MOD = True
except Exception as _mpris_exc:
    print("myostoox.mpris:", _mpris_exc, file=sys.stderr)

_HAS_RADIO_TV_MOD = False
_radiotvmod = None
_HAS_SCROBBLER_MOD = False
_scrobmod = None

try:
    from myostoox import radio_tv as _radiotvmod
    _HAS_RADIO_TV_MOD = True
except Exception as _radiotv_exc:
    print("myostoox.radio_tv:", _radiotv_exc, file=sys.stderr)

try:
    from myostoox import scrobbler as _scrobmod
    _HAS_SCROBBLER_MOD = True
except Exception as _scrob_exc:
    print("myostoox.scrobbler:", _scrob_exc, file=sys.stderr)

_HAS_RECORDING_MOD = False
_recmod = None
_HAS_DISCS_MOD = False
_discsmod = None

try:
    from myostoox import recording as _recmod
    _HAS_RECORDING_MOD = True
except Exception as _rec_exc:
    print("myostoox.recording:", _rec_exc, file=sys.stderr)

try:
    from myostoox import discs as _discsmod
    _HAS_DISCS_MOD = True
except Exception as _discs_exc:
    print("myostoox.discs:", _discs_exc, file=sys.stderr)

_HAS_RESUME_MOD = False
_resumemod = None
_HAS_STATE_MOD = False
_statemod = None

try:
    from myostoox import resume as _resumemod
    _HAS_RESUME_MOD = True
except Exception as _resume_exc:
    print("myostoox.resume:", _resume_exc, file=sys.stderr)

try:
    from myostoox import state as _statemod
    _HAS_STATE_MOD = True
except Exception as _state_exc:
    print("myostoox.state:", _state_exc, file=sys.stderr)

_HAS_LYRICS_MOD = False
_lyricsmod = None

try:
    from myostoox import lyrics as _lyricsmod
    _HAS_LYRICS_MOD = True
except Exception as _lyrics_exc:
    print("myostoox.lyrics:", _lyrics_exc, file=sys.stderr)

_HAS_SCREENSAVER_MOD = False
_ssmod = None

try:
    from myostoox import screensaver as _ssmod
    _HAS_SCREENSAVER_MOD = True
except Exception as _ss_exc:
    print("myostoox.screensaver:", _ss_exc, file=sys.stderr)

_HAS_COVER_MOD = False
_covermod = None

try:
    from myostoox import cover as _covermod
    _HAS_COVER_MOD = True
except Exception as _cover_exc:
    print("myostoox.cover:", _cover_exc, file=sys.stderr)

_HAS_WINDOW_PLACEMENT_MOD = False
_wpmod = None

try:
    from myostoox import window_placement as _wpmod
    _HAS_WINDOW_PLACEMENT_MOD = True
except Exception as _wp_exc:
    print("myostoox.window_placement:", _wp_exc, file=sys.stderr)

_HAS_METADATA_PANEL_MOD = False
_metapanelmod = None

try:
    from myostoox import metadata_panel as _metapanelmod
    _HAS_METADATA_PANEL_MOD = True
except Exception as _meta_exc:
    print("myostoox.metadata_panel:", _meta_exc, file=sys.stderr)

_HAS_RECENT_MOD = False
_recentmod = None
_HAS_AUTOSTART_MOD = False
_autostartmod = None
_HAS_SLEEP_MOD = False
_sleepmod = None
_HAS_ASSOCIATIONS_MOD = False
_assocmod = None
_HAS_NOTIFICATIONS_MOD = False
_notifmod = None

try:
    from myostoox import recent as _recentmod
    _HAS_RECENT_MOD = True
except Exception as _recent_exc:
    print("myostoox.recent:", _recent_exc, file=sys.stderr)

try:
    from myostoox import autostart as _autostartmod
    _HAS_AUTOSTART_MOD = True
except Exception as _auto_exc:
    print("myostoox.autostart:", _auto_exc, file=sys.stderr)

try:
    from myostoox import sleep_timer as _sleepmod
    _HAS_SLEEP_MOD = True
except Exception as _sleep_exc:
    print("myostoox.sleep_timer:", _sleep_exc, file=sys.stderr)

try:
    from myostoox import associations as _assocmod
    _HAS_ASSOCIATIONS_MOD = True
except Exception as _assoc_exc:
    print("myostoox.associations:", _assoc_exc, file=sys.stderr)

try:
    from myostoox import notifications as _notifmod
    _HAS_NOTIFICATIONS_MOD = True
except Exception as _notif_exc:
    print("myostoox.notifications:", _notif_exc, file=sys.stderr)

_HAS_WINDOW_STATE_MOD = False
_wsmod = None

try:
    from myostoox import window_state as _wsmod
    _HAS_WINDOW_STATE_MOD = True
except Exception as _ws_exc:
    print("myostoox.window_state:", _ws_exc, file=sys.stderr)

_HAS_GST_DEBUG_MOD = False
_gstdebugmod = None
_HAS_INTERFACE_MOD = False
_interfacemod = None

try:
    from myostoox import gst_debug as _gstdebugmod
    _HAS_GST_DEBUG_MOD = True
except Exception as _gstdebug_exc:
    print("myostoox.gst_debug:", _gstdebug_exc, file=sys.stderr)

try:
    from myostoox import interface as _interfacemod
    _HAS_INTERFACE_MOD = True
except Exception as _iface_exc:
    print("myostoox.interface:", _iface_exc, file=sys.stderr)

_HAS_STATUS_MOD = False
_statusmod = None

try:
    from myostoox import status as _statusmod
    _HAS_STATUS_MOD = True
except Exception as _status_exc:
    print("myostoox.status:", _status_exc, file=sys.stderr)

_HAS_SUBS_TRACK_MOD = False
_substrackmod = None

try:
    from myostoox import subs_track as _substrackmod
    _HAS_SUBS_TRACK_MOD = True
except Exception as _substrack_exc:
    print("myostoox.subs_track:", _substrack_exc, file=sys.stderr)

_HAS_TRANSPORT_MOD = False
_transportmod = None

try:
    from myostoox import transport as _transportmod
    _HAS_TRANSPORT_MOD = True
except Exception as _transport_exc:
    print("myostoox.transport:", _transport_exc, file=sys.stderr)

_HAS_TOOLS_MOD = False
_toolsmod = None

try:
    from myostoox import tools as _toolsmod
    _HAS_TOOLS_MOD = True
except Exception as _tools_exc:
    print("myostoox.tools:", _tools_exc, file=sys.stderr)

_HAS_AUDIO_OUTPUT_MOD = False
_audiomod = None

try:
    from myostoox import audio_output as _audiomod
    _HAS_AUDIO_OUTPUT_MOD = True
except Exception as _audio_exc:
    print("myostoox.audio_output:", _audio_exc, file=sys.stderr)

_HAS_CROSSFADE_MOD = False
_crossfademod = None

try:
    from myostoox import crossfade as _crossfademod
    _HAS_CROSSFADE_MOD = True
except Exception as _crossfade_exc:
    print("myostoox.crossfade:", _crossfade_exc, file=sys.stderr)





APP_NAME = "Myostoox"
DEBUG_MYOSTOOX = bool(os.environ.get("MYOSTOOX_DEBUG", "").strip())
GST_ELEMENT_DEBUG = bool(os.environ.get("MYOSTOOX_DEBUG_GST", "").strip())
METADATA_CACHE_MAX = 1500
COVER_DECODE_MAX_PX = 256
COVER_PIXBUF_CACHE_MAX = 24
PROBE_CACHE_MAX = 256
EXTERNAL_COVER_MAX_BYTES = 8 * 1024 * 1024
VISUALIZER_INTERVAL_MS = 16
FS_BAR_ALPHA = 0.62
FS_OSD_AUTOHIDE_MS = 2800
FS_OSD_LEAVE_HIDE_MS = 450
FS_OSD_FADE_MS = 140
FS_OSD_MAX_WIDTH = 1100
FS_OSD_COMPACT_WIDTH = 760
FS_OSD_SHOW_ON_ANY_MOTION = False
FS_OSD_EXIT_SUPPRESS_MS = 800
PLAYBACK_RATES = (0.50, 0.75, 1.0, 1.25, 1.5, 1.75)
SEEK_COALESCE_MS = 100
SEEK_GUARD_S = 2.0
PLAYLIST_COUNTDOWN_ENABLED = True
PLAYLIST_COUNTDOWN_PREFIX = "-"
_AV1_HW_OTHER_NAMES = (
    "vaav1dec",
    "vaapiav1dec",
    "v4l2av1dec",
    "msdkav1dec",
)
_AV1_HW_NVIDIA_NAMES = (
    "nvav1dec",
)
_AV1_HW_DECODER_NAMES = _AV1_HW_OTHER_NAMES + _AV1_HW_NVIDIA_NAMES
_AV1_SOFT_DECODER_ORDER = ("dav1ddec", "av1dec", "avdec_av1")
_NVIDIA_DECODER_NAMES = (
    "nvh264dec",
    "nvh265dec",
    "nvav1dec",
    "nvvp8dec",
    "nvvp9dec",
    "nvmpeg2videodec",
    "nvmpeg4videodec",
    "nvmpegvideodec",
    "nvv4l2decoder",
    "nvdec",
)
_OTHER_HW_DECODER_NAMES = (
    "vah264dec",
    "vah265dec",
    "vaav1dec",
    "vavp8dec",
    "vavp9dec",
    "vampeg2dec",
    "vaapidecodebin",
    "vaapih264dec",
    "vaapih265dec",
    "vaapiav1dec",
    "vaapivp8dec",
    "vaapivp9dec",
    "vulkanh264dec",
    "vulkanh265dec",
    "qsvh264dec",
    "qsvh265dec",
    "qsvvp9dec",
    "v4l2h265dec",
    "v4l2h264dec",
    "v4l2slh265dec",
    "v4l2slh264dec",
)
_SOFTWARE_VIDEO_DECODER_NAMES = (
    "avdec_h264",
    "avdec_h265",
    "avdec_hevc",
    "avdec_vp9",
    "avdec_vp8",
    "avdec_av1",
    "avdec_mpeg2video",
    "avdec_mpeg4",
    "dav1ddec",
    "av1dec",
)

def _gst_set_rank(name, rank):
    try:
        factory = Gst.ElementFactory.find(name)
        if factory is not None:
            factory.set_rank(rank)
    except Exception: pass

def apply_safe_gstreamer_ranks(prefer_nvidia_av1=False):
    _gst_set_rank("a52dec", Gst.Rank.NONE)
    for n in ("avdec_eac3", "avdec_ac3"):
        _gst_set_rank(n, Gst.Rank.PRIMARY + 100)
    for n in _AV1_HW_OTHER_NAMES:
        _gst_set_rank(n, Gst.Rank.NONE)
    if prefer_nvidia_av1:
        for n in _AV1_HW_NVIDIA_NAMES:
            _gst_set_rank(n, Gst.Rank.PRIMARY + 200)
        soft_ranks = (
            (_AV1_SOFT_DECODER_ORDER[0], Gst.Rank.PRIMARY + 90),
            (_AV1_SOFT_DECODER_ORDER[1], Gst.Rank.PRIMARY + 80),
            (_AV1_SOFT_DECODER_ORDER[2], Gst.Rank.PRIMARY + 70),
            ("av1parse", Gst.Rank.PRIMARY + 50),
        )
    else:
        for n in _AV1_HW_NVIDIA_NAMES:
            _gst_set_rank(n, Gst.Rank.NONE)
        soft_ranks = (
            (_AV1_SOFT_DECODER_ORDER[0], Gst.Rank.PRIMARY + 120),
            (_AV1_SOFT_DECODER_ORDER[1], Gst.Rank.PRIMARY + 110),
            (_AV1_SOFT_DECODER_ORDER[2], Gst.Rank.PRIMARY + 100),
            ("av1parse", Gst.Rank.PRIMARY + 50),
        )
    for n, rank in soft_ranks:
        _gst_set_rank(n, rank)
try:
    gi.require_version("Notify", "0.7")
    from gi.repository import Notify
    if not Notify.is_initted():
        Notify.init(APP_NAME)
except Exception:
    Notify = None
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", APP_NAME)
SOCKET_FILE = os.path.join(CONFIG_DIR, "instance.sock")
LOCK_FILE = os.path.join(CONFIG_DIR, "instance.lock")
PLAYLIST_FILE = os.path.join(
    CONFIG_DIR,
    "playlist.json"
)
RECENT_FILE = os.path.join(CONFIG_DIR, "recent.json")
RECENT_MAX = 15
META_CACHE_FILE = os.path.join(CONFIG_DIR, "meta_cache.json")
META_DISK_MAX = 5000
STATE_FILE = os.path.join(CONFIG_DIR, "state.json")
RESUME_FILE = os.path.join(CONFIG_DIR, "resume.json")
RESUME_MIN_POS_S = 30.0
RESUME_END_MARGIN_S = 30.0
RESUME_MAX_ENTRIES = 200
RESUME_SAVE_INTERVAL_S = 12.0
RESUME_SEEK_MAX_TRIES = 10
RADIOS_FILE = os.path.join(CONFIG_DIR, "radios.json")
TVS_FILE = os.path.join(CONFIG_DIR, "tvs.json")
BOUQUETS_FILE = os.path.join(CONFIG_DIR, "bouquets.json")
EQ_PRESETS_FILE = os.path.join(CONFIG_DIR, "eq_presets.json")
DEFAULT_EQ_PRESETS = [{'gains': [1.2958579881656789,
            0.0,
            0.0,
            -1.3179190751445091,
            0.13872832369942145,
            1.595375722543352,
            3.884393063583815,
            2.843930635838152,
            1.1791907514450841,
            -0.14201183431952558],
  'name': 'Crystal'},
 {'gains': [0.0, 0.0, 0.0, 0.0, 0.037974683544305776, 0.0, 0.0, 0.0, 0.0, 0.0],
  'name': 'Flat'},
 {'gains': [4.481012658227847,
            7.777777777777779,
            3.7777777777777786,
            0.037974683544305776,
            -0.6666666666666679,
            -2.2222222222222214,
            -0.3607594936708871,
            -0.018987341772152888,
            -0.075949367088608,
            0.37974683544304],
  'name': 'Bass Boost'},
 {'gains': [0.8924050632911396,
            3.552713678800501e-15,
            -0.8888888888888893,
            -1.3179190751445091,
            3.552713678800501e-15,
            0.2088607594936711,
            1.1111111111111107,
            1.12025316455696,
            1.1772151898734151,
            1.1772151898734151],
  'name': 'Classique'},
 {'gains': [-0.8888888888888893,
            -0.7594936708860764,
            1.0063291139240462,
            0.037974683544305776,
            -1.044303797468352,
            -0.2468354430379769,
            1.0063291139240462,
            2.031645569620256,
            1.9746835443038009,
            1.063291139240505],
  'name': 'Jazz'},
 {'gains': [2.0,
            2.8888888888888893,
            2.0,
            0.8924050632911396,
            0.037974683544305776,
            -0.9873417721518969,
            2.031645569620256,
            3.0,
            1.9746835443038009,
            1.063291139240505],
  'name': 'Rock Pop'}]

ASSOCIATIONS_FILE = os.path.join(CONFIG_DIR, "associations.json")
DESKTOP_FILE_NAME = f"{APP_NAME.lower()}.desktop"
DESKTOP_FILE_PATH = os.path.join(
    os.path.expanduser("~"),
    ".local",
    "share",
    "applications",
    DESKTOP_FILE_NAME,
)
AUTOSTART_DIR = os.path.join(os.path.expanduser("~"), ".config", "autostart")
AUTOSTART_DESKTOP_PATH = os.path.join(AUTOSTART_DIR, DESKTOP_FILE_NAME)
WINDOW_PLACEMENTS = (
    "center",
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
)
WINDOW_PLACEMENT_MARGIN = 48
AUDIO_EXTENSIONS = {
    ".mp3",
    ".ogg",
    ".oga",
    ".opus",
    ".flac",
    ".wav",
    ".aac",
    ".m4a",
    ".mp4",
    ".mkv",
    ".mka",
    ".ac3",
    ".dts",
    ".aiff",
    ".aif",
    ".wv",
    ".wma",
}
VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mpeg",
    ".mpg",
    ".webm",
    ".mov",
    ".m4v",
    ".ts",
    ".wmv",
    ".flv",
    ".ogv",
}
SUBTITLE_FONT_DESC = "DejaVu Sans Bold 12"
SUBTITLE_EXTENSIONS = {
    ".srt",
    ".vtt",
    ".ass",
    ".ssa",
    ".sub",
    ".smi",
    ".ttml",
    ".sbv",
}
ASSOCIABLE_FORMATS = [
    ('.mp3', ['audio/mpeg', 'audio/mp3']),
    ('.flac', ['audio/flac', 'audio/x-flac']),
    ('.ogg', ['audio/ogg', 'audio/vorbis']),
    ('.oga', ['audio/ogg']),
    ('.opus', ['audio/opus', 'audio/ogg']),
    ('.wav', ['audio/wav', 'audio/x-wav', 'audio/vnd.wave']),
    ('.aac', ['audio/aac', 'audio/x-aac']),
    ('.m4a', ['audio/mp4', 'audio/x-m4a']),
    ('.wma', ['audio/x-ms-wma', 'audio/wma']),
    ('.mp4', ['video/mp4', 'audio/mp4']),
    ('.mkv', ['video/x-matroska', 'video/mkv']),
    ('.avi', ['video/x-msvideo', 'video/avi']),
    ('.mpeg', ['video/mpeg']),
    ('.mpg', ['video/mpeg']),
    ('.webm', ['video/webm', 'audio/webm']),
    ('.ac3', ['audio/ac3']),
    ('.dts', ['audio/vnd.dts', 'audio/dts']),
    ('.aiff', ['audio/x-aiff', 'audio/aiff']),
    ('.aif', ['audio/x-aiff']),
    ('.wv', ['audio/x-wavpack']),
    ('.mov', ['video/quicktime', 'video/x-quicktime']),
    ('.m4v', ['video/x-m4v', 'video/mp4']),
    ('.ts', ['video/mp2t', 'video/mpegts']),
    ('.wmv', ['video/x-ms-wmv', 'video/x-ms-asf']),
    ('.flv', ['video/x-flv', 'video/flv']),
    ('.ogv', ['video/ogg', 'video/x-ogg']),
    ('.mka', ['audio/x-matroska', 'audio/matroska']),
]

STREAM_SCHEMES = ("http://", "https://", "mms://", "rtsp://", "icy://")
LANGUAGES = (
    "English",
    "Français",
    "Deutsch",
    "Castellano",
    "Italiano",
    "Nederlands",
    "Português",
    "Polski",
    "Svenska",
    "Русский",
    "简体中文",
    "한국어",
    "日本語",
)
_TR_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translations.json")
try:
    with open(_TR_FILE, encoding="utf-8") as _f:
        TRANSLATIONS = json.load(_f)
except Exception as exc:
    print("translations.json illisible :", exc, file=sys.stderr)
    TRANSLATIONS = {}
DEFAULT_SHORTCUTS = {
    "play_pause": "space",
    "mute": "m",
    "fullscreen": "F11",
    "fullscreen_alt": "f",
    "seek_back_5": "Left",
    "seek_forward_5": "Right",
    "seek_back_10": "j",
    "seek_forward_10": "l",
    "seek_back_30": "Page_Up",
    "seek_forward_30": "Page_Down",
    "volume_up": "Ctrl+Up",
    "volume_down": "Ctrl+Down",
    "playlist_up": "Up",
    "playlist_down": "Down",
    "delete": "Delete",
    "clear_playlist": "F1",
    "screenshot": "F12",
    "quit": "Alt+q",
    "factory_reset": "Ctrl+Alt+x",
    "playlist_menu": "Ctrl+p",
    "focus_search": "Ctrl+r",
    "toggle_recording": "Ctrl+s",
    "toggle_playlist_only": "Ctrl+n",
}
SHORTCUT_LABELS = {
    "play_pause": "Lecture / Pause",
    "mute": "Muet",
    "clear_playlist": "Vider la playlist",
    "fullscreen": "Plein écran",
    "fullscreen_alt": "Plein écran (alt.)",
    "seek_back_5": "Seek −5 s",
    "seek_forward_5": "Seek +5 s",
    "seek_back_10": "Seek −10 s",
    "seek_forward_10": "Seek +10 s",
    "seek_back_30": "Seek −30 s",
    "seek_forward_30": "Seek +30 s",
    "volume_up": "Volume +",
    "volume_down": "Volume −",
    "playlist_up": "Playlist ↑",
    "playlist_down": "Playlist ↓",
    "delete": "Supprimer la sélection",
    "screenshot": "Capture d'écran",
    "quit": "Quitter",
    "factory_reset": "Quitter et réinitialiser",
    "playlist_menu": "Menu playlist",
    "focus_search": "Champ de recherche",
    "toggle_recording": "Enregistrement",
    "toggle_playlist_only": "Sans lecteur",
}
_THEME_PALETTES_Z = bytes.fromhex(
    "78da959adb72e3360c865f2533bd483ba3e9f028417d990ec44336d3246e1d6ff7a2d3772f654b040f506ac7570b8b14007e067f82fbcff3e7e97d39"
    "87e7df9efe79fef1fae14f3f7e5f5ed2bf9e7f92526a699f87a7dd1e6f760fdefbb8da2fa73f173ce7e767e964653f9d7d385fbfd3421b0deb77cbe5"
    "631fa0941a15eec66d76e7bdf6363f594c01da1bb97ff1edf4374d3dea65b7a3bbbcfe1df6376834de8eed7734a775939ec2d5e5d7f7b0bb8061599c"
    "58addf02a647b3bf56cdca15767a7e5aae1e5cce21f4e9bb5af7f026e75cccd6cff0967d154618acbed9c6c4ebdf358ad3e5727acf6f98244a57dab9"
    "84bb3553fb10318b45b8c25c8cb01af5968bcb5b76d8bba08259cdaf1ff1b45b619eed7c75f6f38297ef9fbb7d9c273b5dedefe1e37b4fccd5babb1f"
    "5600b2b55cd13d13a74fbf3d7d7e59f067315c3fbf4ef0cbfe6d9da27fd7c0def0f5cce01c4db471ea7156a882d63dce010286c0e3ec6282141b9c8b"
    "65229c69f60667671d7adde3ec63d001799c9df52688639c279c9745b4385b1cedc4e01c421451f738d3f325ce11e3125d8b7391bc06e7059c0b82c3"
    "39419b56bec79912dee34c09af704e68da802cce94df0a67199556d0e24c21d7384f0866162dce344789332d7f8333ad6883b311833183558968b05f"
    "10fd891f2f0cd00aa591d0031d63caa4eb81d65eba5bde7ba0274c05a3adcf34a0009a666feb73f534853f8654891c0f34a6971a3806da0b2bc60ee8"
    "289c70d003ad57b04c0f343d5f024de92b814ee1895bb96b81863545ee91faac9584a3fa4c09af8096410a6958a0694405747ab388aa053a08848501"
    "da09801e685ad312685ad006685ad10668a9c4a013d46b8d9ec517447f249f78cd115298c830add250c3698e71d1074c4b6351b5455a853958d9301d"
    "44744539a729103ca0608a34c6548a79a603a4749a63a6d33e146f0b5632ed4d149e615ae29476f29e697abed21c397d15d322bfb161da41888e2dd2"
    "6967f035bb6dc27ba629e135d3ad99468868702b490dd3db0faa649a42ae995e84770b744c67622acd91dd6f985606d0188e693b3c8d727852303c25"
    "aa554bf5b6dc2bd5f8d77764981641e2ad2cd54c27ea44048669ab4003cfb4428b535ba765d06845cff4367b5ba77144809e690506c703a655a270fe"
    "4278d8a42a7d57a7e7547503233c24ac0aaf679a9e2f99a6f4954cfb2416225ba7158e02c4433a5a29a105cf3425bcd6d1ebe6c1eb681a51339d56e3"
    "a69f2a1d0d0b78a64e8f386ff5bb649ad6b4623af3d2329d57b4657a1c0c0c9362cb74021ab632bdbcbe5ccea70f8e692f26c1303daa490253a76384"
    "b439f34c8beb5fcbf48a94edb4c78cac98aea7287fd5694b9a78a6c9259e69e952b64dcb34591ba69d940218ed4181974ce7f4d5dac3c579e6986e66"
    "29c574f6a766ba88ae639ab255339d9deaeb741e518be9fcf292e924c3a260ce86d66990a6d71e7bd035d3fbf2374c535c0dd3497a4831d881abd1db"
    "a015e937fcb884338bb45913c0b53ba20b1353a6fd325bf300d2c24a23da7687f6de8df800d2226d9852f148934b3cd2c2ec1e944893b5463ad53894"
    "4c992e022f91cee92b914658c5378774334b293db23f4d99a6e8ee463a3b752fd2f4f212e994f42019e991a48d2be444177489342d7f8334c5d5206d"
    "871bd41cd2dba06bc3e3fcfdf35be05a1e624ca709ee8468fcb617d548db058d9b1f411a257427c429a46d1c1e403aedbfa081479a5c3a403a7b5021"
    "9dad0dd261dfe99b9607055e229dd35722bdc0ba0d734837b39448539e2aa48be8ee463a3b7537d2f9e525d21277d158234df2a5449a82ae90ce3337"
    "48535c0dd2302833e891457a1bb422fde2f12d3240a763aaf10cd01a35dcd6b5911d36ca30f2400382eda4b4f71e1cf43d3c508201ba9e82c20f4b18"
    "fd410f8f5c3a90d26847032dd014600db407af1c733c2c1252f6f044287b725d78fdf1d00984831e1e48c1c80e8aae039ab255014d217440d3885a76"
    "e497d73dbc3d716d0f6fb2630734055df5f0b2fb0dd09489be87a761d0bc94dea65b89f678be7ce34a34ac1f4648afdd1e866867d6d3de23425ac942"
    "2fe4838411563c52a2d7be9438e84a67970e8434ee2156423a5b1b216df637d544178197253aa7af243a00b6dc2eec2c771c0e8be8ee2ed1d9a9bb85"
    "744e4649b4c1bdd4b7874359b2db055d09e9bcfc2dd139aeae893798f4493c9b96e76dccca733c873421d7c14b27e3db0d530df4ac8cb59e031ac5f8"
    "08d049fea26cbb1dde2c008f680e9d34878423a077978e80de43ac81deadcdad21aaada5db029d032f3b78347705740a902fd1f52c7589de666a81ce"
    "d1dd0b344d753fd0fb881a688d8a05daa26180de832e81a6e5ef80dee36a4f86e355472b56746ca3b66ec77b78c1838e47fa191939f65c9ba4a22cd3"
    "c5039cd5ec1e29d4742d465c2f6201f748a14ebb5ad0075d3c72e980eb1c62c575b636853a28a3b0e7ba08bce49ae62ebb78c28fdef1b72dd52c25d7"
    "79a69aeb22babbb9ce53ddcd751e51773c8c325cc703473386ee363c075d15eabcfc0dd714575ba861e55af15c6fa356aeffc01ff8ca5d88c7606e9a"
    "beede181758eebe1cdc11df4a563923aa8bb0bf1bd9f5b106d96058c6788aeafcfcb8ecf228eee5a621cc3f245c363d53973d79736711a1dd3c38bd1"
    "8bc0f4f0e8f94a4caf176f1dd1cdb305d1d314c4fc90f4a084f74453c22ba21d441b047f7f18fcbc883bef5aac98b72bd39ae8e692bb0bbabe100f10"
    "39a229136da54e3c8fa954ebffbd4074afe18d151f0667e6fa30396222f35f96144ed11ff4f06c582076e2230fa8dad225b9d55540f974213e10301c"
    "a86993963c7e71258e229dc463777d984e76376b7b253ea36790de9afcddf5a12d75739fbc0669f2b56f78a422c29c0f8b8c744853c2eb223d6a0fbc"
    "9aa61177208d10eccd5a238dd1bb88bdf8d883aec487b1e5b50cb7a27d5b7a25da8883c6f48de87fff03044a1d83"
)
import zlib as _zlib_themes
THEME_PALETTES = eval(_zlib_themes.decompress(_THEME_PALETTES_Z).decode("utf-8"))

THEME_LABELS = {
    "aqua": "Aqua",
    "sombre": "Sombre",
    "clair": "Clair",
    "sang": "Sang",
    "nature": "Nature",
    "kawai": "Kawai",
    "ciel": "Ciel",
    "bigtron": "BigTron",
    "lantern": "Lantern",
    "crusher": "Crusher",
    "gdalf": "Gdalf",
    "darth": "Darth",
    "fremen": "Fremen",
    "bigmegatron": "BigMegatron",
}
SPECTRUM_BANDS = 12
SPECTRUM_SOURCE_BANDS = 64
SPECTRUM_LOW_CUT = 0.24
SPECTRUM_SPREAD_EXPONENT = 2.25
SPECTRUM_LOW_DB = -79.0
SPECTRUM_HIGH_DB = -4.0
SPECTRUM_VISUAL_FLOOR = 0.00
SPECTRUM_VERTICAL_COMPRESSION = 1.29
SPECTRUM_AGC_ENABLED_DEFAULT = True
SPECTRUM_AGC_CEILING_MIN_DB = -38.0
SPECTRUM_AGC_ATTACK = 0.35
SPECTRUM_AGC_RELEASE = 0.006
SPECTRUM_PEAK_HOLD_SECONDS = 0.30
SPECTRUM_PEAK_RISE = 0.80
SPECTRUM_PEAK_FALL = 0.965
SPECTRUM_REFERENCE_DT = 0.016
SPECTRUM_SYNC_OFFSET_MIN_MS = -500
SPECTRUM_SYNC_OFFSET_MAX_MS = 1500
SPECTRUM_FALLBACK_DELAY_S = 0.25
SPECTRUM_QUEUE_MAX = 400
SPECTRUM_MAX_LEAD_S = 5.0
SPECTRUM_BROKEN_AFTER = 40
SPECTRUM_DEBUG = bool(os.environ.get("MYOSTOOX_SPECTRUM_DEBUG", "").strip())
EQ_BANDS = 10
EQ_FREQS = [
    "29 Hz", "59 Hz", "119 Hz", "237 Hz", "474 Hz",
    "947 Hz", "1.9 kHz", "3.8 kHz", "7.5 kHz", "15 kHz"
]
EQ_MIN_DB = -24.0
EQ_MAX_DB = 12.0
REPLAYGAIN_MODES = ("off", "track", "album", "auto")
CROSSFADE_MAX_S = 12.0
SLEEP_PRESETS_MIN = (15, 30, 45, 60, 90)

def format_time(seconds):
    try:
        seconds = int(seconds)
    except Exception:
        seconds = 0
    seconds = max(0, seconds)
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    if hours: return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"

def format_video_resolution(width, height):
    try:
        return "%d × %d" % (int(width), int(height))
    except Exception:
        return "—"

def format_video_fps(fps):
    try:
        fps = float(fps)
    except Exception:
        return None
    if fps <= 0: return None
    if abs(fps - round(fps)) < 0.005: return "%d fps" % int(round(fps))
    return ("%.3f" % fps).rstrip("0").rstrip(".") + " fps"

def is_stream(path):
    if not isinstance(path, str): return False
    return path.lower().startswith(STREAM_SCHEMES)

def is_cdda(path):
    return isinstance(path, str) and path.startswith("cdda://")

def is_dvd(path):
    return isinstance(path, str) and path.lower().startswith("dvd://")

def is_bluray(path):
    if not isinstance(path, str): return False
    p = path.lower()
    return p.startswith("bluray://") or p.startswith("bd://")

def is_special_source(path):
    return is_cdda(path) or is_stream(path) or is_dvd(path) or is_bluray(path)

def path_to_uri(path):
    if is_special_source(path): return path
    return GLib.filename_to_uri(os.path.abspath(path), None)

def atomic_write_json(path, data):
    try:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        temporary = path + ".tmp"
        with open(temporary, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    except Exception as exc:
        print("Écriture impossible :", path, exc, file=sys.stderr)

def is_audio_file(path):
    if is_special_source(path): return True
    return (
        os.path.isfile(path)
        and os.path.splitext(path)[1].lower()
        in AUDIO_EXTENSIONS
    )

def is_pure_audio_file(path):
    if not isinstance(path, str): return False
    if is_special_source(path): return False
    if is_video_file(path): return False
    try:
        return (
            os.path.isfile(path)
            and os.path.splitext(path)[1].lower() in AUDIO_EXTENSIONS
        )
    except Exception:
        return False

def is_video_file(path):
    if not isinstance(path, str) or is_cdda(path) or is_stream(path): return False
    if is_dvd(path) or is_bluray(path): return True
    return os.path.splitext(path)[1].lower() in VIDEO_EXTENSIONS

def find_external_subtitles(video_path):
    results = []
    if not isinstance(video_path, str) or is_stream(video_path) or is_cdda(video_path): return results
    try:
        if is_dvd(video_path) or is_bluray(video_path): return results
    except Exception: pass
    if not os.path.isfile(video_path): return results
    directory = os.path.dirname(os.path.abspath(video_path))
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    base_lower = base_name.casefold()

    def _norm_token(s):
        s = (s or "").casefold().strip()
        for ch in ("_", "-", " "):
            s = s.replace(ch, ".")
        while ".." in s:
            s = s.replace("..", ".")
        return s.strip(".")
    base_norm = _norm_token(base_name)
    try:
        entries = os.listdir(directory)
    except OSError:
        return results
    all_subs = []
    for name in entries:
        path = os.path.join(directory, name)
        if not os.path.isfile(path): continue
        root, ext = os.path.splitext(name)
        ext_lower = ext.lower()
        if ext_lower not in SUBTITLE_EXTENSIONS: continue
        all_subs.append((name, path, root, ext_lower))
    if not all_subs: return results
    matched_paths = set()

    def _add(path, lang, ext_lower, priority):
        if path in matched_paths: return
        matched_paths.add(path)
        fmt = ext_lower.lstrip(".").upper()
        if lang:
            label = "%s (%s)" % (lang, fmt)
        else:
            label = "%s [%s]" % (fmt, os.path.basename(path))
        results.append({
            "path": path,
            "lang": lang,
            "label": label,
            "ext": ext_lower,
            "_prio": priority,
        })
    for name, path, root, ext_lower in all_subs:
        root_lower = root.casefold()
        lang = None
        prio = 50
        if root_lower == base_lower:
            lang = None
            prio = 0
        elif root_lower.startswith(base_lower + "."):
            suffix = root[len(base_name) + 1 :]
            token = suffix.split(".")[0].strip() if suffix else ""
            lang = token if token else None
            prio = 1
        else:
            root_norm = _norm_token(root)
            if root_norm == base_norm:
                lang = None
                prio = 2
            elif root_norm.startswith(base_norm + "."):
                suffix = root_norm[len(base_norm) + 1 :]
                token = suffix.split(".")[0].strip() if suffix else ""
                lang = token if token else None
                prio = 3
            elif base_norm in root_norm and (
                root_norm.startswith(base_norm)
                or (".%s." % base_norm) in (".%s." % root_norm)
            ):
                rest = root_norm[len(base_norm):].lstrip(".")
                token = rest.split(".")[0] if rest else ""
                lang = token if token else None
                prio = 4
            else:
                continue
        _add(path, lang, ext_lower, prio)
    if not results and len(all_subs) == 1:
        name, path, root, ext_lower = all_subs[0]
        _add(path, None, ext_lower, 10)
    if not results and len(all_subs) > 1:
        for name, path, root, ext_lower in all_subs:
            root_norm = _norm_token(root)
            common = 0
            for a, b in zip(base_norm, root_norm):
                if a == b:
                    common += 1
                else:
                    break
            if common >= 6 and common >= min(len(base_norm), len(root_norm)) * 0.5:
                rest = root_norm[common:].lstrip(".")
                token = rest.split(".")[0] if rest else ""
                _add(path, token or None, ext_lower, 20)
    results.sort(
        key=lambda item: (
            item.get("_prio", 99),
            0 if not item["lang"] else 1,
            (item["lang"] or "").casefold(),
            item["path"].casefold(),
        )
    )
    for item in results:
        item.pop("_prio", None)
    return results

def guess_subtitle_encoding(path):
    """Devine l'encodage d'un fichier de sous-titres (UTF-8 / UTF-16 / CP1252)."""
    limit = 256 * 1024
    try:
        with open(path, "rb") as f:
            data = f.read(limit)
    except Exception:
        return "UTF-8"
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return "UTF-16"
    if data.startswith(b"\xef\xbb\xbf"):
        return "UTF-8"
    try:
        data.decode("utf-8")
        return "UTF-8"
    except UnicodeDecodeError as exc:
        if len(data) >= limit and exc.start >= len(data) - 4:
            return "UTF-8"
    return "CP1252"

def parse_lrc_content(content):
    lines = []
    for raw in content.splitlines():
        raw = raw.strip()
        if not raw or raw.startswith(("[ti:", "[ar:", "[al:", "[by:", "[offset:", "[length:")): continue
        tags = list(re.finditer(r"\[(\d{1,3}):(\d{2})(?:[.:](\d{1,3}))?\]", raw))
        if not tags: continue
        last = tags[-1]
        text_part = raw[last.end():].strip()
        if not text_part: continue
        for m in tags:
            mm = int(m.group(1))
            ss = int(m.group(2))
            frac = m.group(3) or "0"
            if len(frac) == 1:
                frac = frac + "0"
            cent = int(frac) if frac.isdigit() else 0
            if len(m.group(3) or "") == 3:
                sec = mm * 60 + ss + cent / 1000.0
            else:
                sec = mm * 60 + ss + cent / 100.0
            lines.append((sec, text_part))
    lines.sort(key=lambda x: x[0])
    return lines

def load_lyrics_for_file(filepath):
    if not isinstance(filepath, str):
        return None
    try:
        pure = is_pure_audio_file(filepath)
    except Exception:
        pure = False
        try:
            ext = os.path.splitext(filepath)[1].lower()
            pure = (
                os.path.isfile(filepath)
                and ext
                in {
                    ".mp3",
                    ".ogg",
                    ".oga",
                    ".opus",
                    ".flac",
                    ".wav",
                    ".aac",
                    ".m4a",
                    ".wma",
                    ".wv",
                    ".aif",
                    ".aiff",
                }
            )
        except Exception:
            pure = False
    if not pure:
        return None
    if not os.path.isfile(filepath):
        return None
    directory = os.path.dirname(os.path.abspath(filepath))
    base = os.path.splitext(os.path.basename(filepath))[0]
    for ext in (".lrc", ".LRC"):
        lrc_path = os.path.join(directory, base + ext)
        if os.path.isfile(lrc_path):
            try:
                with open(lrc_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                timed = parse_lrc_content(content)
                if timed: return {"timed": True, "lines": timed, "source": "lrc"}
            except Exception as exc:
                print("LRC read:", exc, file=sys.stderr)
    for ext in (".txt", ".TXT"):
        txt_path = os.path.join(directory, base + ext)
        if os.path.isfile(txt_path):
            try:
                with open(txt_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                plain = [
                    (None, ln.strip())
                    for ln in content.splitlines()
                    if ln.strip()
                ]
                if plain: return {"timed": False, "lines": plain, "source": "txt"}
            except Exception as exc:
                print("TXT lyrics:", exc, file=sys.stderr)
    if MutagenFile is None: return None
    try:
        audio = MutagenFile(filepath, easy=False)
        if audio is None: return None
        tags = getattr(audio, "tags", None)
        if tags is None: return None
        try:
            for key in list(tags.keys()):
                sk = str(key)
                if sk.startswith("USLT") or sk.startswith("©lyr"):
                    frame = tags[key]
                    text = None
                    if hasattr(frame, "text"):
                        text = frame.text
                    elif isinstance(frame, (list, tuple)) and frame:
                        text = frame[0]
                    else:
                        text = str(frame)
                    if text and str(text).strip():
                        plain = [
                            (None, ln.strip())
                            for ln in str(text).splitlines()
                            if ln.strip()
                        ]
                        if plain: return {
                                "timed": False,
                                "lines": plain,
                                "source": "embedded",
                            }
        except Exception: pass
        for key in ("LYRICS", "lyrics", "UNSYNCEDLYRICS", "unsyncedlyrics"):
            try:
                if key in tags:
                    val = tags[key]
                    if isinstance(val, (list, tuple)):
                        val = val[0] if val else ""
                    text = str(val).strip()
                    if text:
                        plain = [
                            (None, ln.strip())
                            for ln in text.splitlines()
                            if ln.strip()
                        ]
                        if plain: return {
                                "timed": False,
                                "lines": plain,
                                "source": "embedded",
                            }
            except Exception: pass
    except Exception as exc:
        print("embedded lyrics:", exc, file=sys.stderr)
    return None

def get_cdda_track_number(path):
    if not is_cdda(path): return None
    try:
        return int(path.split("://", 1)[1].split("#")[0])
    except Exception:
        return None

def get_tag(tags, names, default=""):
    if not tags: return default
    for name in names:
        try:
            value = None
            if hasattr(tags, "getall"):
                try:
                    frames = tags.getall(name)
                    if frames:
                        value = frames[0]
                except Exception:
                    value = None
            if value is None:
                try:
                    if hasattr(tags, "get"):
                        value = tags.get(name)
                    if value is None and name in tags:
                        value = tags[name]
                except Exception:
                    value = None
            if value is None: continue
            if isinstance(value, (list, tuple)):
                if not value: continue
                value = value[0]
            if hasattr(value, "text"):
                value = value.text
                if isinstance(value, (list, tuple)):
                    value = value[0] if value else ""
            if value is not None and not isinstance(value, (str, bytes, int, float)):
                for attr in ("year", "text"):
                    if hasattr(value, attr):
                        try:
                            cand = getattr(value, attr)
                            if isinstance(cand, (list, tuple)):
                                cand = cand[0] if cand else ""
                            if cand is not None and str(cand).strip():
                                value = cand
                                break
                        except Exception: pass
            if value is not None:
                s = str(value).strip()
                if s: return s
        except Exception: pass
    return default

def load_external_cover(filename):
    directory = os.path.dirname(filename)
    cover_names = {
        "cover.jpg",
        "cover.jpeg",
        "cover.png",
        "cover.webp",
        "folder.jpg",
        "folder.jpeg",
        "folder.png",
        "folder.webp",
        "front.jpg",
        "front.jpeg",
        "front.png",
        "front.webp",
        "albumart.jpg",
        "albumart.jpeg",
        "albumart.png",
        "album.jpg",
        "album.jpeg",
        "album.png",
        "albumartsmall.jpg",
        "embedded.png",
        "thumb.jpg",
    }
    try:
        for name in os.listdir(directory):
            if name.lower() not in cover_names: continue
            path = os.path.join(directory, name)
            if not os.path.isfile(path): continue
            try:
                try:
                    sz = os.path.getsize(path)
                    if sz <= 0 or sz > EXTERNAL_COVER_MAX_BYTES: continue
                except Exception: pass
                with open(path, "rb") as file:
                    data = file.read(EXTERNAL_COVER_MAX_BYTES + 1)
                if data and len(data) <= EXTERNAL_COVER_MAX_BYTES: return data
            except Exception: pass
    except Exception: pass
    return None

def load_metadata(filename, load_cover=True):
    if is_cdda(filename):
        track = get_cdda_track_number(filename) or 0
        title = f"Piste {track:02d}"
        return (
            title,
            "CD Audio",
            "CD Audio",
            "",
            0,
            None,
            {
                "format": "CDDA",
                "sample_rate": "44 100 Hz",
                "channels": "2",
                "bitrate": "",
                "bits": "16 bits",
            },
        )
    if is_stream(filename):
        title = filename
        if len(title) > 80:
            title = title[:77] + "…"
        return (
            title,
            "Flux en direct",
            "Streaming",
            "",
            0,
            None,
            {
                "format": "STREAM",
                "sample_rate": "",
                "channels": "",
                "bitrate": "",
                "bits": "",
            },
        )
    title = os.path.splitext(
        os.path.basename(filename)
    )[0]
    artist = ""
    album = ""
    year = ""
    duration = 0
    cover = None
    technical = {
        "format": os.path.splitext(filename)[1].upper().lstrip("."),
        "sample_rate": "",
        "channels": "",
        "bitrate": "",
        "bits": "",
    }
    if MutagenFile is None:
        if load_cover:
            cover = load_external_cover(filename)
        return (
            title,
            artist,
            album,
            year,
            duration,
            cover,
            technical,
        )
    try:
        try:
            easy = MutagenFile(filename, easy=True)
        except Exception:
            easy = None
        if easy is not None:
            info = getattr(easy, "info", None)
            if info is not None:
                try:
                    duration = float(getattr(info, "length", 0) or 0)
                except Exception:
                    duration = 0
                rate = getattr(info, "sample_rate", None)
                if rate:
                    try:
                        technical["sample_rate"] = (
                            f"{int(rate):,} Hz".replace(",", " ")
                        )
                    except Exception:
                        technical["sample_rate"] = f"{rate} Hz"
                channels = getattr(info, "channels", None)
                if channels:
                    technical["channels"] = str(channels)
                bitrate = getattr(info, "bitrate", None)
                if bitrate:
                    try: technical["bitrate"] = f"{int(bitrate / 1000)} kb/s"
                    except Exception: pass
                bits = getattr(info, "bits_per_sample", None)
                if bits:
                    technical["bits"] = f"{bits} bits"
            def _easy_first(keys):
                for k in keys:
                    try:
                        val = easy.get(k)
                        if not val: continue
                        if isinstance(val, (list, tuple)):
                            val = val[0] if val else ""
                        s = str(val).strip()
                        if s: return s
                    except Exception:
                        continue
                return ""
            title = _easy_first(("title", "TITLE", "TIT2")) or title
            artist = _easy_first(("artist", "ARTIST", "TPE1")) or artist
            album = _easy_first(("album", "ALBUM", "TALB")) or album
            year = _easy_first(
                ("date", "DATE", "year", "YEAR", "TDRC", "TYER")
            ) or year
        need_raw = bool(load_cover) or not (title and artist)
        if not need_raw:
            if year:
                try:
                    y = str(year).strip()
                    if len(y) >= 4 and y[:4].isdigit():
                        year = y[:4]
                except Exception: pass
            return (
                title,
                artist,
                album,
                year,
                duration,
                cover,
                technical,
            )
        audio = MutagenFile(filename, easy=False)
        if audio is None:
            if load_cover and cover is None:
                cover = load_external_cover(filename)
            if year:
                y = str(year).strip()
                if len(y) >= 4 and y[:4].isdigit():
                    year = y[:4]
            return (
                title,
                artist,
                album,
                year,
                duration,
                cover,
                technical,
            )
        info = getattr(audio, "info", None)
        if info is not None and not duration:
            try: duration = float(getattr(info, "length", 0) or 0)
            except Exception: pass
            if not technical.get("sample_rate"):
                rate = getattr(info, "sample_rate", None)
                if rate:
                    try:
                        technical["sample_rate"] = (
                            f"{int(rate):,} Hz".replace(",", " ")
                        )
                    except Exception: pass
            if not technical.get("channels"):
                channels = getattr(info, "channels", None)
                if channels:
                    technical["channels"] = str(channels)
            if not technical.get("bitrate"):
                bitrate = getattr(info, "bitrate", None)
                if bitrate:
                    try: technical["bitrate"] = f"{int(bitrate / 1000)} kb/s"
                    except Exception: pass
            if not technical.get("bits"):
                bits = getattr(info, "bits_per_sample", None)
                if bits:
                    technical["bits"] = f"{bits} bits"
        tags = getattr(audio, "tags", None)
        if tags and (not title or title == os.path.splitext(os.path.basename(filename))[0]):
            title = (
                get_tag(tags, ["TIT2", "title", "TITLE", "\xa9nam"])
                or title
            )
        if tags and not artist:
            artist = get_tag(
                tags, ["TPE1", "artist", "ARTIST", "\xa9ART"]
            )
        if tags and not album:
            album = get_tag(
                tags, ["TALB", "album", "ALBUM", "\xa9alb"]
            )
        if tags and not year:
            year = get_tag(
                tags,
                ["TDRC", "TYER", "date", "DATE", "year", "YEAR", "\xa9day"],
            )
        if load_cover:
            try:
                if tags is not None and (
                    (MP4 is not None and isinstance(audio, MP4))
                    or "covr" in tags
                ):
                    cov = tags.get("covr") if hasattr(tags, "get") else None
                    if cov is None and "covr" in tags:
                        cov = tags["covr"]
                    if cov:
                        if isinstance(cov, (list, tuple)):
                            cov = cov[0]
                        cover = bytes(cov)
            except Exception: pass
            if cover is None and tags is not None:
                try:
                    apics = None
                    if hasattr(tags, "getall"):
                        try:
                            apics = tags.getall("APIC")
                        except Exception:
                            apics = None
                    if apics:
                        chosen = None
                        for ap in apics:
                            try:
                                if int(getattr(ap, "type", -1)) == 3:
                                    chosen = ap
                                    break
                            except Exception: pass
                        if chosen is None:
                            chosen = apics[0]
                        data = getattr(chosen, "data", None)
                        if data:
                            cover = bytes(data)
                    if cover is None:
                        for key in list(tags.keys()):
                            sk = str(key)
                            if not (
                                sk.startswith("APIC")
                                or "PICTURE" in sk.upper()
                                or sk == "covr"
                            ):
                                continue
                            try:
                                frame = tags[key]
                                if isinstance(frame, (list, tuple)) and frame:
                                    frame = frame[0]
                                data = getattr(frame, "data", None)
                                if data is None and isinstance(
                                    frame, (bytes, bytearray, memoryview)
                                ):
                                    data = bytes(frame)
                                if data:
                                    cover = bytes(data)
                                    break
                            except Exception: pass
                except Exception: pass
            if cover is None:
                try:
                    pics = getattr(audio, "pictures", None)
                    if pics:
                        data = getattr(pics[0], "data", None)
                        if data:
                            cover = bytes(data)
                except Exception: pass
            if cover is None:
                cover = load_external_cover(filename)
        if year:
            try:
                y = str(year).strip()
                if len(y) >= 4 and y[:4].isdigit():
                    year = y[:4]
            except Exception: pass
    except Exception as exc:
        print(
            f"Lecture métadonnées impossible : "
            f"{filename}: {exc}",
            file=sys.stderr
        )
        if load_cover and cover is None:
            try: cover = load_external_cover(filename)
            except Exception: pass
    return (
        title,
        artist,
        album,
        year,
        duration,
        cover,
        technical,
    )

def detect_ui_scale():
    try:
        display = Gdk.Display.get_default()
        if display is None: return 1.0
        monitor = None
        try:
            monitor = display.get_primary_monitor()
        except Exception:
            monitor = None
        if monitor is None:
            try:
                if display.get_n_monitors() > 0:
                    monitor = display.get_monitor(0)
            except Exception: pass
        if monitor is None: return 1.0
        try:
            sys_scale = float(monitor.get_scale_factor() or 1)
        except Exception:
            sys_scale = 1.0
        sys_scale = max(1.0, sys_scale)
        if sys_scale >= 1.5: return 1.0
        geo = monitor.get_geometry()
        width = int(getattr(geo, "width", 0) or 0)
        height = int(getattr(geo, "height", 0) or 0)
        dpi = None
        try:
            w_mm = monitor.get_width_mm()
            if w_mm and w_mm > 0 and width > 0:
                dpi = (width * 25.4) / float(w_mm)
        except Exception:
            dpi = None
        boost = 1.0
        if dpi is not None and dpi >= 160:
            boost = min(2.0, max(1.25, dpi / 110.0))
        elif width >= 3840 or height >= 2160:
            boost = 1.5
        elif width >= 3000 or height >= 1800:
            boost = 1.35
        elif width >= 2560 or height >= 1440:
            boost = 1.2
        else:
            boost = 1.0
        for candidate in (1.0, 1.15, 1.25, 1.35, 1.5, 1.75, 2.0):
            if abs(boost - candidate) < 0.08: return candidate
        return round(boost * 20) / 20.0
    except Exception:
        return 1.0

def _memlog_tick():
    try:
        import tracemalloc
        lines = []
        try:
            with open("/proc/self/status", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith(("VmRSS:", "RssAnon:", "RssFile:", "RssShmem:")):
                        lines.append(line.strip())
        except Exception: pass
        try:
            if not tracemalloc.is_tracing():
                tracemalloc.start(15)
            snap = tracemalloc.take_snapshot()
            top = snap.statistics("lineno")[:5]
            lines.append("tracemalloc top:")
            for s in top:
                lines.append("  " + str(s))
        except Exception: pass
        try:
            w = getattr(_memlog_tick, "window", None)
            if w is not None:
                lines.append(
                    "cache=%s missing=%s playlist=%s gc=%s"
                    % (
                        len(getattr(w, "metadata_cache", {}) or {}),
                        len(getattr(w, "_missing_cache", {}) or {}),
                        len(w.playlist) if getattr(w, "playlist", None) is not None else 0,
                        gc.get_count(),
                    )
                )
        except Exception: pass
        print("[memlog]", " | ".join(lines), flush=True)
    except Exception as exc:
        print("[memlog] error:", exc, file=sys.stderr)
    return True

_CSS_TPL_Z = bytes.fromhex(
    "78dad51c5d6fdb38ecbdbfc2c01eb61e6c234dd32eeb80fe837bbac7c361b063c531ceb1025b5ddb"
    "15fdef274bfed00745cb49daf5b6a14d248a22298a22296a8f4595d1c7e0e5e5224d36ffe6357da8"
    "b2bbe0e55134ff48f31f9ba679fdae74461b5ad21a00e9db0f7f7feebab6f9e77f78c7ebeb45cce8"
    "214d6a6b1a0e2b7b381a019bd23a23759452c6e89e03345fae2e5f0f4f4143cb22d3e005e0807fb3"
    "abe99e44599de4c624ac4eaae690d4a462001b7aafc07957d18ab45f9ea26697703eba063e4dfac0"
    "c9aae20dad584d4b7da2a8d82739e9071b4ca6acea3954c4d4b66e55be4186c5d891db4e42759215"
    "0f8d1870dd0ef87e7148b2aca8f2b1a9fdb0967dfba28a1e8b8ced44eff2ebd8ba2345be63b27925"
    "9bb79cbda8297e11494ed76ab35f26291142902c15d58ed40543c64bb588aba4a2d19e662450d442"
    "a5feaaa77e6952bfe05f923a2faaf613849163d2a147161d23f83a8b5103da9e1207bcfc782893e7"
    "b26818d7d4a7d0066a365c4025c9d48e6188ec744e3a977e4b274151ae2045b85a838a70750b2ac2"
    "42b6da0ab874afb04b6560d40886567ad1149337a0b62f6126d72093cb7994b8185a2ac81fe5a429"
    "2d3369ac7475603521e145fbf367411e814ec3ce2806a4ed05ec8a68ee0c8b53d0c884770d29c986"
    "916c62660ee69abded1acdbfe776986652b3d0a3456a9ef75cba512be110683356495b0f433e370e"
    "6377b7a33f09787eb5e659749a72b00ec10e63b261c54fe242257b3dc4da6d43e338e9876ba7a363"
    "0b09d6b7c9be289feffee2c7a0258c6f2e2506ad95387756f0c9b236c58a6ca2a32852c49b65909d"
    "b0495da3a4ea136b47a3c7c40eb380a2693649c90d81f815ef685dfce25049d9b7700d6305ffd462"
    "a50fac2c2a82782a624cc06979c877364ea36340ad35072d33dc2f6aba664b6305d40fd909bb886e"
    "08cd59d2dd2ea1d60d7b2ef5fef14c741e4096207439192b0d9e88a3b32265b0e3e0653b0410a2d5"
    "37c8d1ec090e35cd6bd2342ed10e031c42de16658989d8eeff1d02eea5a60aa973c800ef02821e35"
    "0d5e2c684cc31d655203eb630a5902ea2ee2e03ed8fe41d70ab968136104b60a9de0857b6f187120"
    "16894ab2650aa9b7ba0bd612ebece5beb5d2f74deb93f195b5e2ed1063efee1ef6a915752c8e5205"
    "297f79927a2f9772f0a234ca33f8559979d88dba820ccddeea019f69bd2bd52948db141991d8e23b"
    "68307b913aeda50d70c46eb60344df253304a72fd884f81c7e12b45038ffc87aea46625ca8b52b3e"
    "b91e8c479c158d703d58b12763e82a1d2cdea479cd9d23f227ad28df961b82c40ae2bc8f69e3f098"
    "eb3c4dbe2cc2a0fb17dfdc5c0ebedda7adf863791c8b29e76bd44dd5b5b0b9577cfe78dbf42e4a73"
    "429a04b56fc0cc2ac5b73dc12659ace6ce3aabc6451904e3a452dd08c6d2dc4287fbf52d3825a4b3"
    "1ddf62e19637376130fe58c457edf219482222f318301dea2a0615adf749e922ceed3a5bd3b9824f"
    "6c528e472062346918acadf8620752deb8f65e018e6e60a8ef62cc7a597e6c3098a4b87cae8b0da7"
    "7724ea04aa39c2ac4e78649673c0e438dc83043513a20b62d2745c63f9812134de912403ac2927a3"
    "7efe213bd1142d0ca8d8bcae0bce155cd9bb770c8f056a9052e07842dc867332e6304c4e7e8dad76"
    "bdc2b98b9524c9a00fa109abf5c50ddfa79b5d54d34710e20d8cb0295f6039d401b398bddbd2cd43"
    "13ce19d1a792660d6a99cb6a7a7867f1285931f0a66276b66d6967db603d41bbe3b6670226b80fa4"
    "407d700dc088b7f2c2ead7307861b9f8998a9f949bb2823dbf5e3ae53bc5a9a20ed364fa020f70bd"
    "7ace402d87f8e739419d38360f0aeb8207105fc0968b03ad3de17be8b32ff8e49559acde9478d8c0"
    "f32861dc45276f3dcfa0690e7d7564d2a774eb6c997623c91e4ef42b7a356500e7e7eaf1a9676e06"
    "6490d7e6c0c6cfda5a1f7fbfbeedfe3ef960fbed2cbe9b913a95ca89bd2b7fb9aa2c8edfbaf0f582"
    "1f29daad8591565b28295d4f6c785e793e42f7cd460b3071b56180b8c31ee765037c03b59ecfc698"
    "ba84d890bd281b10c854cef124ee94ace9d5b1fc3a738d0a4b78b611023c820ec78dee11e29f33b9"
    "bc763c8bee7a2c3a1a44dbbbdab137d5ccf80966a5e3fd6d14404b09b39228ded5101d76e1932423"
    "d4dd40bd734691d890ce30fd3c5de0d05e44eae5d0f2b1859ede19b2c9b78e1b03305f054ba5bf36"
    "4064734451852e0ae7e432358a2f8c51bee6ca8759d939296b906ad1639432f2b31d5e970ed8a863"
    "7449447418e73384b683d3b136b4ca23a1ccd69d87a2e046f2628da52805c6a2da520361dbe4c037"
    "e60ee386254c46ddca50d938994989b969294666f03570b17ad4daec49f510cdd9d5eedb0a85ae16"
    "aba2cfedd73088bb5f228c7d6251fbd595a48873c2be48349ceb30d06b6a2f5f9db3f9d79c767415"
    "8cec3bdada8fc6fa69a8d1e49c82aedba8c1f0fd0f04ab32aeb32ec3b831f60e7490719b4fc84e9a"
    "1b213ec5fa5c4ed4740d93654593a4a5367fdf045a1a5ddb3bffff6e117f950721e1b24a1855380c"
    "86360733820b0e64d786293de6ed12583039ecb5435271f2efc7a943d934baf5409fe2a4df4f10fd"
    "6921fe9c70d56d9c4f33d8530bc3d492628be7fe207373ae43c0fc23978c9fae93f62f16fa750e51"
    "723844599194340f2fe46fa5c99dc41c2af5c114a6deeb5476c45ac025f9f329435f1028e844cdb5"
    "da90d745a6b7e00994a3a78eb0bc39f09ae1ec6f1d406f6d3d7973ac70e0e7066035b24b10efa6a4"
    "0df13a17a123017d153151d7a2ca64893f7c584f3f7cc0385fb93947f6f7fcda5e43dfa1f303dd20"
    "e2aaeda4b2f133bc473137adbfe364caed3d5fceacccfa14af5d85043426337eb5e2006e28cb806b"
    "986f89b8bf26f6f15408b622f95c4fb5734c675eaf4030677fb4004d82c6f6761c794c283f46e606"
    "0d1bba4f69fb5a696af2336e19c3d2a5347b3ef944d5ead716e06eea4ae1ada6c1fb82faf4e4b073"
    "fae9da790bf55017ef26080101caeeed19fe3fb5f6d7deb5f653a9e05bf7daab15f488d05128b852"
    "df9e6aaccd9f5e968f5ea7ef5de98b08b52f974640dca5d31fa9def9d432ee3348f14dcaa1515577"
    "af9ed7cb880fbc7e8e9b85d559d7cff15ce14d5750bdf318ef384200ca71b9eb8aef911cc064d90e"
    "34b7df6d2e3cd4f7ea1666da712a5a9e968f37f61637b530d5e8b63aff5171fe0b598cade98de163"
    "33a626715ead9e77fb21f7a9c7e9d8bbdda87a6fde99776e3e012c1e246131e2541aed98f8c92b64"
    "f3206a5e6c77c64bdc5a7f7b88e6014fbbc6f512d5db2433fa28368463dbfbc0dd37bcc8e7dfdf25"
    "faf5f7aff1505d923c4f9e0263ca3d96282d3978a87deb85a4b4b42970f87661b558dddc2c2d8c66"
    "567178c062d561f045e1e848ddec2865ed7fd912a200329f8dc3b4cf5a7188ba7f3e6d80b402c208"
    "19fb9d748c200e324680da8ef56624b5a75e1bfc073102aae8"
)

# Modules prioritaires (monobloc = repli si import échoué)
if _HAS_PLAYLIST_MOD:
    is_stream = _pl_is_stream
    is_cdda = _pl_is_cdda
    is_dvd = _pl_is_dvd
    is_bluray = _pl_is_bluray
    is_special_source = _pl_is_special_source
    path_to_uri = _pl_path_to_uri
    atomic_write_json = _pl_atomic_write_json
    is_audio_file = _pl_is_audio_file
    is_pure_audio_file = _pl_is_pure_audio_file
    is_video_file = _pl_is_video_file
if _HAS_METADATA_MOD:
    format_time = _md_format_time
    format_video_resolution = _md_format_video_resolution
    format_video_fps = _md_format_video_fps
    get_tag = _md_get_tag
    load_external_cover = _md_load_external_cover
    load_metadata = _md_load_metadata
    parse_lrc_content = _md_parse_lrc_content
    load_lyrics_for_file = _md_load_lyrics_for_file
    SUBTITLE_FONT_DESC = _MD_SUBTITLE_FONT_DESC
    SUBTITLE_EXTENSIONS = _MD_SUBTITLE_EXTENSIONS
if _HAS_SUBTITLES_MOD:
    find_external_subtitles = _st_find_external_subtitles
    guess_subtitle_encoding = _st_guess_subtitle_encoding
if _HAS_PLAYER_MOD:
    apply_safe_gstreamer_ranks = _py_apply_safe_gstreamer_ranks
    _gst_set_rank = _py__gst_set_rank
if _HAS_THEMES_MOD:
    THEME_PALETTES = _TH_THEME_PALETTES
    THEME_LABELS = _TH_THEME_LABELS

# Modules d'interface : reçoivent les globales finales du main (après les
# rebindings ci-dessus), ce qui évite tout import circulaire.
if _HAS_DIALOGS_MOD:
    _bind_missing = _dialogsmod.bind(globals())
    if _bind_missing:
        print("myostoox.dialogs: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_PLAYLIST_VIEW_MOD:
    _bind_missing = _plviewmod.bind(globals())
    if _bind_missing:
        print("myostoox.playlist_view: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_SPECTRUM_MOD:
    _bind_missing = _spectrummod.bind(globals())
    if _bind_missing:
        print("myostoox.spectrum: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_COMPACT_MOD:
    _bind_missing = _compactmod.bind(globals())
    if _bind_missing:
        print("myostoox.compact_player: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_EQUALIZER_MOD:
    _bind_missing = _eqmod.bind(globals())
    if _bind_missing:
        print("myostoox.equalizer: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_MPRIS_MOD:
    _bind_missing = _mprismod.bind(globals())
    if _bind_missing:
        print("myostoox.mpris: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_RADIO_TV_MOD:
    _bind_missing = _radiotvmod.bind(globals())
    if _bind_missing:
        print("myostoox.radio_tv: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_SCROBBLER_MOD:
    _bind_missing = _scrobmod.bind(globals())
    if _bind_missing:
        print("myostoox.scrobbler: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_RECORDING_MOD:
    _bind_missing = _recmod.bind(globals())
    if _bind_missing:
        print("myostoox.recording: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_DISCS_MOD:
    _bind_missing = _discsmod.bind(globals())
    if _bind_missing:
        print("myostoox.discs: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_RESUME_MOD:
    _bind_missing = _resumemod.bind(globals())
    if _bind_missing:
        print("myostoox.resume: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_STATE_MOD:
    _bind_missing = _statemod.bind(globals())
    if _bind_missing:
        print("myostoox.state: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_LYRICS_MOD:
    _bind_missing = _lyricsmod.bind(globals())
    if _bind_missing:
        print("myostoox.lyrics: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_SCREENSAVER_MOD:
    _bind_missing = _ssmod.bind(globals())
    if _bind_missing:
        print("myostoox.screensaver: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_COVER_MOD:
    _bind_missing = _covermod.bind(globals())
    if _bind_missing:
        print("myostoox.cover: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_WINDOW_PLACEMENT_MOD:
    _bind_missing = _wpmod.bind(globals())
    if _bind_missing:
        print("myostoox.window_placement: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_METADATA_PANEL_MOD:
    _bind_missing = _metapanelmod.bind(globals())
    if _bind_missing:
        print("myostoox.metadata_panel: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_RECENT_MOD:
    _bind_missing = _recentmod.bind(globals())
    if _bind_missing:
        print("myostoox.recent: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_AUTOSTART_MOD:
    _bind_missing = _autostartmod.bind(globals())
    if _bind_missing:
        print("myostoox.autostart: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_SLEEP_MOD:
    _bind_missing = _sleepmod.bind(globals())
    if _bind_missing:
        print("myostoox.sleep_timer: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_ASSOCIATIONS_MOD:
    _bind_missing = _assocmod.bind(globals())
    if _bind_missing:
        print("myostoox.associations: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_NOTIFICATIONS_MOD:
    _bind_missing = _notifmod.bind(globals())
    if _bind_missing:
        print("myostoox.notifications: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_WINDOW_STATE_MOD:
    _bind_missing = _wsmod.bind(globals())
    if _bind_missing:
        print("myostoox.window_state: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_GST_DEBUG_MOD:
    _bind_missing = _gstdebugmod.bind(globals())
    if _bind_missing:
        print("myostoox.gst_debug: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_INTERFACE_MOD:
    _bind_missing = _interfacemod.bind(globals())
    if _bind_missing:
        print("myostoox.interface: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_STATUS_MOD:
    _bind_missing = _statusmod.bind(globals())
    if _bind_missing:
        print("myostoox.status: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_SUBS_TRACK_MOD:
    _bind_missing = _substrackmod.bind(globals())
    if _bind_missing:
        print("myostoox.subs_track: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_TRANSPORT_MOD:
    _bind_missing = _transportmod.bind(globals())
    if _bind_missing:
        print("myostoox.transport: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)
if _HAS_TOOLS_MOD:
    _bind_missing = _toolsmod.bind(globals())
    if _bind_missing:
        print("myostoox.tools: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)

if _HAS_AUDIO_OUTPUT_MOD:
    _bind_missing = _audiomod.bind(globals())
    if _bind_missing:
        print("myostoox.audio_output: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)

if _HAS_CROSSFADE_MOD:
    _bind_missing = _crossfademod.bind(globals())
    if _bind_missing:
        print("myostoox.crossfade: noms manquants :", ", ".join(_bind_missing), file=sys.stderr)





class Myostoox(Gtk.Window):
    COL_PATH = 0
    COL_TITLE = 1
    COL_ARTIST = 2
    COL_ALBUM = 3
    COL_DURATION_TEXT = 4
    COL_DURATION = 5
    _MINI_MARQUEE_HEIGHT = 20
    _MINI_MARQUEE_FONT = "Sans Bold 9"
    _MINI_MARQUEE_SPEED = 40.0
    _MINI_MARQUEE_GAP = 90
    _MINI_MARQUEE_PAD = 10
    _MINI_MARQUEE_PAUSE_MS = 0
    _MINI_MARQUEE_ALWAYS_SCROLL = True

    def __init__(self):
        super().__init__(title=APP_NAME)
        try: self._init_rgba_visual()
        except Exception: pass
        self.ui_scale = detect_ui_scale()
        try:
            s = float(self.ui_scale) or 1.0
        except Exception:
            s = 1.0
            self.ui_scale = 1.0
        self._ui_s = lambda n, _s=s: max(1, int(round(float(n) * _s)))
        self.set_default_size(self._ui_s(950), self._ui_s(620))
        self.set_position(
            Gtk.WindowPosition.CENTER
        )
        self.set_size_request(self._ui_s(700), self._ui_s(430))
        self.current_path = None
        self.current_duration = 0
        self.is_playing = False
        self.is_paused = False
        self.repeat_mode = False
        self.repeat_track_path = None
        self.shuffle_mode = False
        self.shuffle_queue = []
        self.language = self.load_saved_language()
        try:
            self._load_tr_table(self.language)
        except Exception:
            self._tr_table = TRANSLATIONS.get(self.language, {}) or {}
        self.user_seeking = False
        self._seek_user_moved = False
        self._seek_press_value = None
        self.search_text = ""
        self.sort_column = None
        self.sort_ascending = True
        self.spectrum_values = [0.0] * SPECTRUM_BANDS
        self.spectrum_targets = [0.0] * SPECTRUM_BANDS
        self.spectrum_peaks = [0.0] * SPECTRUM_BANDS
        self.spectrum_quiet = [0] * SPECTRUM_BANDS
        self.spectrum_peak_hold = [0.0] * SPECTRUM_BANDS
        self._spectrum_delay_queue = deque()
        self.spectrum_sync_offset_ms = 0
        self.spectrum_sync_window = None
        self._spectrum_stale_count = 0
        self._spectrum_use_fallback = False
        self._spectrum_epoch = 0
        self._spectrum_ok_count = 0
        self.metadata_cache = OrderedDict()
        self._disk_meta_cache = {}
        self._disk_meta_dirty = False
        self._disk_meta_save_id = 0
        try:
            self._load_disk_meta_cache()
        except Exception:
            self._disk_meta_cache = {}
        self._missing_cache = {}
        self._cover_pixbuf_cache = OrderedDict()
        self._selection_info_timeout_id = 0
        self._pending_selection_path = None
        self._info_generation = 0
        self._transparency_css_timeout_id = 0
        self._spectrum_mag_method = None
        self._mkv_probe_cache = OrderedDict()
        self._spectrum_in_filter = True
        self._sub_lang_cache = OrderedDict()
        self._video_probe_cache = OrderedDict()
        self._discoverer = None
        self._discover_lock = threading.Lock()
        self._discover_info_cache = OrderedDict()
        self.spectrum_enabled = True
        self.spectrum_agc_enabled = SPECTRUM_AGC_ENABLED_DEFAULT
        self._window_obscured = False
        self._visualizer_idle_ticks = 0
        self.recent_files = []
        try:
            self._load_recent_files()
        except Exception:
            self.recent_files = []
        self._factory_reset = False
        self.spectrum_agc_ceiling = SPECTRUM_HIGH_DB
        self._visualizer_last_tick = None
        self.eq_window = None
        self.eq_scales = []
        self.current_is_cdda = False
        self.radios = []
        self.load_radios()
        self.eq_presets = []
        self.load_eq_presets()
        self.icy_title = ""
        self.icy_artist = ""
        self.current_radio_name = None
        self.current_tv_name = None
        self._recording = False
        self._record_pipeline = None
        self._record_temp_path = None
        self._record_bus_watch_id = 0
        # EGL by default: DMABuf import, avoids 100% Render/3D on iGPU.
        # MYOSTOOX_GL_PLATFORM=glx to revert.
        _glp = os.environ.get("MYOSTOOX_GL_PLATFORM", "egl").strip().lower()
        if _glp in ("egl", "glx"):
            os.environ["GST_GL_PLATFORM"] = _glp
        Gst.init(None)
        self.player = Gst.ElementFactory.make(
            "playbin",
            "player"
        )
        if self.player is None:
            raise RuntimeError(
                "Impossible de créer le lecteur GStreamer."
            )
        try:
            if self.player.find_property("subtitle-font-desc"):
                self.player.set_property(
                    "subtitle-font-desc", SUBTITLE_FONT_DESC
                )
        except Exception:
            pass
        self.player.set_property(
            "volume",
            0.75
        )

        try:
            self.player.connect(
                "deep-element-added", self._on_playbin_deep_element_added
            )
        except Exception:
            pass
        self._gapless_pending = None
        self._gapless_next = None
        self._gapless_next_for = None
        self._gapless_refresh_t = 0.0
        self._fade_gain = 1.0
        self._fade_out_active = False
        self._fade_in_pending = False
        self._fade_in_tid = 0
        try:
            self.player.connect("about-to-finish", self._on_about_to_finish)
        except Exception as exc:
            print("about-to-finish indisponible :", exc, file=sys.stderr)
        self.performance_mode = self._load_performance_mode()
        self.hdr_tonemap_enabled = True
        self._hw_fallback_path = None
        self._apply_decoder_performance_mode()
        self._apply_safe_audio_decoder_ranks()
        self._custom_pipeline = None
        self._need_playbin_rebind = False
        self._custom_volume = None
        self._custom_audio_linked = False
        self._custom_video_linked = False
        self._custom_bus_handler_ids = []
        self._custom_audio_pads = []  # [(Gst.Pad, label), ...]
        self._custom_audio_queue = None
        self._custom_audio_index = 0
        self._custom_subtitle_overlay = None
        self._custom_subtitle_pads = []  # [(demux_pad, label), ...]
        self._custom_subtitle_index = -1
        self._custom_sub_linked = False
        self._custom_sub_muted = False
        self._custom_sub_overlay = None
        self.video_sink = None
        self._video_sink_is_real = False
        try:
            _vfake = Gst.ElementFactory.make("fakesink", "video_sink_placeholder")
            if _vfake is not None:
                try: _vfake.set_property("sync", False)
                except Exception: pass
                try: _vfake.set_property("async", False)
                except Exception: pass
                self.player.set_property("video-sink", _vfake)
                self.video_sink = _vfake
        except Exception: pass
        self._configure_playbin_buffers()
        self.is_fullscreen = False
        self.subtitles_enabled = True
        self.current_is_video = False
        self._current_video_dims = None  # (w, h, par_n, par_d)
        self._current_video_hdr = False
        self._hdr_off_path = None
        self._hdr_tonemap_active = False
        self._video_sink_has_tonemap = False
        self._hdr_flags_applied = False
        self._mini_title_scroll_id = 0
        self._mini_title_text = ""
        self._mini_title_offset = 0
        self.lyrics_enabled = False
        self.lyrics_data = None
        self.lyrics_current_index = -1
        self.lyrics_mode = False
        self.desktop_notifications = True
        self.autostart_enabled = False
        self.window_placement = "center"
        self.window_borders = True
        self.window_layer = "normal"
        self.playlist_transparency = False
        self.playlist_transparency_opacity = 0.35
        self.show_metadata_panel = True
        self.spectrum_bar_color = (0.31, 0.71, 0.94)
        self.spectrum_style = "pixel"
        self.playlist_only_mode = False
        self.resume_enabled = False
        self._resume_map = {}
        self._resume_last_save_mono = 0.0
        self._resume_pending_pos = None
        self._resume_seek_tries = 0
        self._resume_pending_tracks = None
        self._resume_track_tries = 0
        self.playlist_only_maximized = False
        self.hide_playlist_mode = False
        self.pure_spectrum_mode = False
        self.pure_spectrum_size = "medium"
        self._pure_spectrum_prev_size = None
        self._pure_spectrum_hover = None
        self.lyrics_transparent_bg = False
        self._playlist_only_prev_size = None
        self._playlist_only_prev_pos = None
        self._playlist_only_prev_layer = None
        self._playlist_only_restore_tid = 0
        self.playback_rate = 1.0
        self._need_rate_reset = False
        self.speed_window = None
        self.nano_player_mode = False
        self.nano_banner_enabled = False
        self.nano_vertical = False
        self.nano_playlist_enabled = False
        self.nano_playlist_side = "right"
        self._last_notify_key = None
        self._notify_unavailable = False
        self._notify_service_checked = False
        self.mini_player_mode = False
        self._normal_size = None
        self._ss_cond = threading.Condition()
        self._ss_want = False
        self._ss_xid = None
        self._ss_quit = False
        self._ss_thread = None
        self._ss_idle = threading.Event()
        self._ss_idle.set()
        self._ss_retry_at = 0.0
        self._ss_method = None
        self._ss_dbus = None
        self._ss_bus = None
        self._ss_xdg_xid = None
        self._video_window_handle = None
        self._pending_restore_path = None
        self._restore_handle_tries = 0
        self._fullscreen_ui_state = None
        self.subtitle_tracks = []
        self.current_subtitle_index = -1
        self._preferred_custom_sub_index = -1
        self._preferred_custom_audio_index = -1
        self._custom_volume_boost = 1.0
        self._preferred_ext_sub_path = None
        self.external_subtitles = []
        self._active_external_sub_path = None
        self._custom_ext_sub_src = None
        self._custom_ext_sub_q = None
        self._custom_ext_sub_parse = None
        self.audio_tracks = []
        self.current_audio_index = -1
        self._size_allocate_timer = 0
        self._seek_in_progress = False
        self._seek_release_timeout_id = 0
        self._seek_coalesce_id = 0
        self._seek_pending_target = None
        self._seek_guard = None
        self._playback_generation = 0
        self._instance_lock_fd = None
        self.instance_socket = None
        self._last_known_position = 0.0
        self._pending_seek_delta = 0.0
        self._updating_position_scale = False
        self._pause_pixbuf = None
        self.tvs = []
        self.load_tvs()
        self.bouquets = []
        self.load_bouquets()
        self.bouquet_active = False
        self.associated_formats = set()
        self.load_associations()
        try: self._ensure_desktop_file()
        except Exception: pass
        self.pitch = None
        self.equalizer = Gst.ElementFactory.make(
            "equalizer-10bands",
            "equalizer"
        )

        self.audio_balance_el = Gst.ElementFactory.make(
            "audiopanorama", "audio-balance"
        )
        if self.audio_balance_el is not None:

            try:
                Gst.util_set_object_arg(self.audio_balance_el, "method", "simple")
            except Exception:
                try:
                    self.audio_balance_el.set_property("method", 1)
                except Exception:
                    pass
            try:
                self.audio_balance_el.set_property("panorama", 0.0)
            except Exception:
                pass
        self._bal_conv = None

        self._mono_c1 = None
        self._mono_caps = None
        self._mono_c2 = None
        self._mono_caps2 = None
        self.eq_preamp_db = 0.0
        self.audio_balance = 0.0
        self.audio_mono = False
        self.sound_settings_window = None
        self.scaletempo = Gst.ElementFactory.make("scaletempo", "scaletempo")
        self.tempo_conv = (
            Gst.ElementFactory.make("audioconvert", "tempo-conv")
            if self.scaletempo is not None else None
        )
        self.eq_muted = False
        self.eq_saved_gains = []
        self.is_muted = False
        self._volume_before_mute = 0.75
        self.replaygain_mode = "off"          # off | track | album | auto
        self.rgvolume = None
        try:
            self.rgvolume = Gst.ElementFactory.make("rgvolume", "rgvolume")
        except Exception:
            self.rgvolume = None
        if self.rgvolume is not None:
            try:
                self.rgvolume.set_property("album-mode", False)
                self.rgvolume.set_property("pre-amp", 0.0)
                self.rgvolume.set_property("fallback-gain", -6.0)
            except Exception: pass
        self.crossfade_seconds = 0.0
        self.gapless_enabled = False
        self._crossfade_active = False
        self._crossfade_timeout_id = 0
        self.sleep_timer_id = 0
        self.sleep_timer_end = 0.0
        self.sleep_timer_minutes = 0
        self.sleep_end_of_track = False
        self.audio_sink_name = ""
        self._audio_sink_element = None
        self.scrobble_enabled = False
        self.scrobble_service = "listenbrainz"  # listenbrainz | lastfm
        self.scrobble_token = ""                 # LB token or Last.fm session key
        self.scrobble_username = ""
        self.scrobble_api_key = ""               # Last.fm only
        self.scrobble_api_secret = ""
        self._scrobble_sent_for = None           # path already scrobbled this play
        self._scrobble_started_at = 0.0
        self._nowplaying_sent_for = None
        self.play_next_queue = []                # list of paths, FIFO front = next
        self.chapters = []
        self._osd_timeout_id = 0
        self._cursor_hide_timeout_id = 0
        self._cursor_hidden = False
        self.theme_name = "aqua"
        self.shortcuts = dict(DEFAULT_SHORTCUTS)
        self._css_provider = None
        self._mpris_owner_id = 0
        self._mpris_reg_ids = []
        self.pitch_value = 1.0
        self.tempo_value = 1.0
        self.pitch_window = None
        self.pitch_scale = None
        self.tempo_scale = None
        self._pitch_active = False
        self.colorimetry_enabled = False
        self.color_brightness = 0.0
        self.color_contrast = 1.0
        self.color_saturation = 1.0
        self.color_gamma = 1.0
        self.colorimetry_window = None
        self._video_balance = None
        self._video_gamma = None
        self._video_color_bin = None
        self._custom_vbalance = None
        self._custom_vgamma = None
        self.colorimetry_menu_item = None
        self.colorimetry_check_item = None
        self.colorimetry_adjust_item = None
        self.filter_bin = None
        self.spectrum = Gst.ElementFactory.make(
            "spectrum",
            "spectrum"
        )
        if self.spectrum is not None:
            self.spectrum.set_property("bands", SPECTRUM_SOURCE_BANDS)
            self.spectrum.set_property("interval", 20000000)
            self.spectrum.set_property("threshold", -80)
            self.spectrum.set_property("post-messages", True)
            self.spectrum.set_property("message-magnitude", True)
            self.spectrum.set_property("message-phase", False)
        self.rebuild_audio_filter(force=True)
        self.playlist = Gtk.ListStore(
            str, str, str, str, str, float
        )
        self.playlist.set_sort_func(self.COL_TITLE, self.compare_title, None)
        self.playlist.set_sort_func(self.COL_ARTIST, self.compare_artist, None)
        self.playlist.set_sort_func(self.COL_ALBUM, self.compare_album, None)
        self.playlist.set_sort_func(self.COL_DURATION, self.compare_duration, None)
        self._load_ui_prefs()
        self.build_css()
        self.build_interface()
        self.load_playlist()
        self.setup_drag_and_drop()
        self.setup_keyboard()
        self.bus = self.player.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message", self.on_gstreamer_message)
        self.bus.enable_sync_message_emission()
        self.bus.connect("sync-message::element", self.on_sync_message)
        self.restore_state()
        try:
            self.autostart_enabled = bool(self._is_autostart_enabled())
        except Exception:
            pass
        try:
            if not bool(getattr(self, "window_borders", True)):
                self.set_decorated(False)
        except Exception: pass
        try: self._update_undecorated_move_hint()
        except Exception: pass
        try: self._apply_playlist_transparency()
        except Exception: pass
        try: self._apply_metadata_panel_visibility()
        except Exception: pass
        try:
            if getattr(self, "nano_player_mode", False) or getattr(self, "mini_player_mode", False):
                GLib.idle_add(self._apply_compact_player_mode)
            try: GLib.idle_add(self._apply_window_layer)
            except Exception: pass
            try: GLib.idle_add(self._apply_hide_playlist_mode)
            except Exception: pass
        except Exception: pass
        self.connect("destroy", self.on_destroy)
        self._app_closing = False
        self._main_popup_menu = None
        self._playlist_context_menu = None
        self._position_timeout_id = GLib.timeout_add(100, self.update_position)
        self._visualizer_timeout_id = GLib.timeout_add(VISUALIZER_INTERVAL_MS, self.update_visualizer)
        try:
            self._idle_trim_timeout_id = GLib.timeout_add_seconds(90, self._idle_memory_trim)
        except Exception:
            self._idle_trim_timeout_id = 0
        try:
            self._setup_mpris()
        except Exception as exc:
            print("MPRIS2 indisponible :", exc, file=sys.stderr)

    def load_saved_language(self):
        try:
            if os.path.isfile(STATE_FILE):
                with open(STATE_FILE, "r", encoding="utf-8") as file:
                    state = json.load(file)
                language = state.get("language") if isinstance(state, dict) else None
                if language in LANGUAGES: return language
        except Exception: pass
        return "English"

    def tr(self, text):
        if self.language == "Français": return text
        table = getattr(self, "_tr_table", None)
        if table is None:
            table = TRANSLATIONS.get(self.language, {})
        return table.get(text, text)

    def _load_tr_table(self, language):
        if language == "Français":
            self._tr_table = {}
            return
        table = TRANSLATIONS.get(language)
        if isinstance(table, dict):
            self._tr_table = table
        else:
            self._tr_table = {}

    def set_language(self, language):
        if language not in LANGUAGES: return
        self.language = language
        try:
            self._load_tr_table(language)
        except Exception:
            self._tr_table = TRANSLATIONS.get(language, {}) or {}
        self.apply_language()
        self.save_state()

    def apply_language(self):
        self.set_title(APP_NAME)
        try:
            self._fs_retranslate_controls()
        except Exception:
            pass
        try: self._fs_update_video_buttons()
        except Exception: pass
        if hasattr(self, "add_files_button"):
            self.add_files_button.set_tooltip_text(self.tr("Ajout des fichiers"))
        if hasattr(self, "record_button"):
            if getattr(self, "_recording", False):
                self.record_button.set_tooltip_text(self.tr("Arrêter l'enregistrement"))
            else:
                self.record_button.set_tooltip_text(self.tr("Enregistrement"))
        if hasattr(self, "previous_button"):
            self.previous_button.set_tooltip_text(self.tr("Morceau précédent"))
        if hasattr(self, "play_button"):
            self.play_button.set_tooltip_text(self.tr("Lecture / Pause"))
        if hasattr(self, "stop_button"):
            self.stop_button.set_tooltip_text(self.tr("Stop"))
        if hasattr(self, "next_button"):
            self.next_button.set_tooltip_text(self.tr("Morceau suivant"))
        if hasattr(self, "shuffle_button"):
            self.shuffle_button.set_tooltip_text(
                self.tr(
                    "Lecture aléatoire activée"
                    if self.shuffle_mode
                    else "Lecture aléatoire"
                )
            )
        if hasattr(self, "repeat_button"):
            if self.repeat_track_path:
                self.repeat_button.set_tooltip_text(self.tr("Répétition du morceau sélectionné activée"))
            elif self.repeat_mode:
                self.repeat_button.set_tooltip_text(self.tr("Répétition de la playlist activée"))
            else:
                self.repeat_button.set_tooltip_text(self.tr("Répéter la playlist"))
        if hasattr(self, "bluetooth_button"):
            self.bluetooth_button.set_tooltip_text(
                self.tr("Bluetooth")
                + " — "
                + self.tr("Ouvrir les réglages Bluetooth du système")
            )
        if hasattr(self, "search_entry"):
            self.search_entry.set_placeholder_text(self.tr("Rechercher un titre, un artiste, un album…"))
        if hasattr(self, "bottom_title") and self.current_path is None:
            self.bottom_title.set_text(self.tr("Aucun morceau sélectionné"))
        if hasattr(self, "status_label"):
            self.status_label.set_text(self.tr("Prêt"))
        if hasattr(self, "tree"):
            titles = ["Titre", "Artiste", "Album", "Durée"]
            for column, title in zip(self.tree.get_columns(), titles):
                column.set_title(self.tr(title))
        try: self._update_undecorated_move_hint()
        except Exception: pass
    def load_radios(self):
        if _HAS_RADIO_TV_MOD:
            return _radiotvmod.load_radios(self)
        return None

    def save_radios(self):
        if _HAS_RADIO_TV_MOD:
            return _radiotvmod.save_radios(self)
        return None

    def find_radio_name(self, url):
        if _HAS_RADIO_TV_MOD:
            return _radiotvmod.find_radio_name(self, url)
        return None

    def play_radio(self, url):
        if _HAS_RADIO_TV_MOD:
            return _radiotvmod.play_radio(self, url)
        return None

    def manage_radios(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.manage_radios(self, *args)
        return None

    def _radio_edit_dialog(self, name="", url=""):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod._radio_edit_dialog(self, name, url)
        return None

    def load_tvs(self):
        if _HAS_RADIO_TV_MOD:
            return _radiotvmod.load_tvs(self)
        return None

    def save_tvs(self):
        if _HAS_RADIO_TV_MOD:
            return _radiotvmod.save_tvs(self)
        return None

    def find_tv_name(self, url):
        if _HAS_RADIO_TV_MOD:
            return _radiotvmod.find_tv_name(self, url)
        return None

    def play_tv(self, url, name=None):
        if _HAS_RADIO_TV_MOD:
            return _radiotvmod.play_tv(self, url, name=None)
        return None

    def manage_tvs(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.manage_tvs(self, *args)
        return None

    def _tv_edit_dialog(self, name="", url=""):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod._tv_edit_dialog(self, name, url)
        return None

    def load_bouquets(self):
        if _HAS_RADIO_TV_MOD:
            return _radiotvmod.load_bouquets(self)
        return None

    def save_bouquets(self):
        if _HAS_RADIO_TV_MOD:
            return _radiotvmod.save_bouquets(self)
        return None

    def manage_bouquets(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.manage_bouquets(self, *args)
        return None

    def _bouquet_edit_dialog(self, name="", url=""):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod._bouquet_edit_dialog(self, name, url)
        return None
    @staticmethod
    @staticmethod
    def parse_m3u_playlist(text):
        if _HAS_RADIO_TV_MOD:
            return _radiotvmod.parse_m3u_playlist(text)
        return None

    def _clear_playlist_search(self):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._clear_playlist_search(self)
        return None
    def dismiss_bouquet_playlist(self):
        if _HAS_RADIO_TV_MOD:
            return _radiotvmod.dismiss_bouquet_playlist(self)
        return None

    def load_bouquet(self, m3u_url):
        if _HAS_RADIO_TV_MOD:
            return _radiotvmod.load_bouquet(self, m3u_url)
        return None

    def _bouquet_loaded(self, raw, err):
        if _HAS_RADIO_TV_MOD:
            return _radiotvmod._bouquet_loaded(self, raw, err)
        return None

    def load_associations(self):
        if _HAS_ASSOCIATIONS_MOD:
            return _assocmod.load_associations(self)
        return None

    def save_associations(self):
        if _HAS_ASSOCIATIONS_MOD:
            return _assocmod.save_associations(self)
        return None

    def _script_path(self):
        return os.path.abspath(__file__)

    def _ensure_desktop_file(self):
        try:
            apps_dir = os.path.dirname(DESKTOP_FILE_PATH)
            os.makedirs(apps_dir, exist_ok=True)
            mime_types = []
            for ext, mimes in ASSOCIABLE_FORMATS:
                if ext in self.associated_formats:
                    for m in mimes:
                        if m not in mime_types:
                            mime_types.append(m)
            script = self._script_path().replace('"', '\\"')
            interpreter = sys.executable.replace('"', '\\"')
            exec_line = f'"{interpreter}" "{script}" %F'
            content = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                f"Name={APP_NAME}\n"
                "Comment=Lecteur audio et vidéo\n"
                f"Exec={exec_line}\n"
                "Icon=myostoox\n"
                "Terminal=false\n"
                "Categories=AudioVideo;Player;Audio;Video;\n"
                f"MimeType={';'.join(mime_types)}\n"
                "StartupNotify=true\n"
                "StartupWMClass=Myostoox\n"
            )
            with open(DESKTOP_FILE_PATH, "w", encoding="utf-8") as f:
                f.write(content)
            try: os.chmod(DESKTOP_FILE_PATH, 0o755)
            except Exception: pass
            try:
                subprocess.run(
                    ["update-desktop-database", apps_dir],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception: pass
            return True
        except Exception as exc:
            print("Impossible d'écrire le fichier .desktop :", exc, file=sys.stderr)
            return False

    def _is_autostart_enabled(self):
        if _HAS_AUTOSTART_MOD:
            return _autostartmod._is_autostart_enabled(self)
        return None

    def _set_autostart_enabled(self, enabled):
        if _HAS_AUTOSTART_MOD:
            return _autostartmod._set_autostart_enabled(self,enabled)
        return None

    def toggle_autostart(self, menuitem):
        if _HAS_AUTOSTART_MOD:
            return _autostartmod.toggle_autostart(self,menuitem)
        return None

    def _apply_window_placement(self, placement=None):
        if _HAS_WINDOW_PLACEMENT_MOD:
            return _wpmod._apply_window_placement(self, placement)
        return None

    def show_window_placement_dialog(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.show_window_placement_dialog(self, *args)
        return None

    def _xdg_mime_default(self, mime_type, enable=True):
        try:
            if enable:
                subprocess.run(
                    ["xdg-mime", "default", DESKTOP_FILE_NAME, mime_type],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
        except Exception as exc:
            print(f"xdg-mime ({mime_type}) :", exc, file=sys.stderr)

    def is_format_associated(self, ext):
        if _HAS_ASSOCIATIONS_MOD:
            return _assocmod.is_format_associated(self,ext)
        return None

    def set_format_association(self, ext, enable):
        if _HAS_ASSOCIATIONS_MOD:
            return _assocmod.set_format_association(self,ext,enable)
        return None

    def toggle_format_association(self, menuitem, ext):
        if _HAS_ASSOCIATIONS_MOD:
            return _assocmod.toggle_format_association(self,menuitem,ext)
        return None

    def associate_all_formats(self, *args):
        if _HAS_ASSOCIATIONS_MOD:
            return _assocmod.associate_all_formats(self,*args)
        return None

    def load_eq_presets(self):
        if _HAS_EQUALIZER_MOD:
            return _eqmod.load_eq_presets(self)
        return None

    def save_eq_presets(self):
        if _HAS_EQUALIZER_MOD:
            return _eqmod.save_eq_presets(self)
        return None

    def get_metadata(self, filename, load_cover=False):
        if _HAS_METADATA_PANEL_MOD:
            return _metapanelmod.get_metadata(self, filename, load_cover)
        return None

    def _load_disk_meta_cache(self):
        self._disk_meta_cache = {}
        if not os.path.isfile(META_CACHE_FILE): return
        try:
            with open(META_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._disk_meta_cache = data
        except Exception as exc:
            print("meta_cache load:", exc, file=sys.stderr)
            self._disk_meta_cache = {}

    def _schedule_disk_meta_save(self):
        self._disk_meta_dirty = True
        tid = getattr(self, "_disk_meta_save_id", 0) or 0
        if tid: return
        def _do():
            self._disk_meta_save_id = 0
            try: self._save_disk_meta_cache()
            except Exception: pass
            return False
        try:
            self._disk_meta_save_id = GLib.timeout_add_seconds(8, _do)
        except Exception:
            try: self._save_disk_meta_cache()
            except Exception: pass
    def _save_disk_meta_cache(self):
        if not getattr(self, "_disk_meta_dirty", False): return
        cache = getattr(self, "_disk_meta_cache", None)
        if not isinstance(cache, dict): return
        try:
            if len(cache) > META_DISK_MAX:
                keys = list(cache.keys())
                for k in keys[: max(0, len(keys) - META_DISK_MAX)]:
                    cache.pop(k, None)
            os.makedirs(CONFIG_DIR, exist_ok=True)
            tmp = META_CACHE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, META_CACHE_FILE)
            self._disk_meta_dirty = False
        except Exception as exc:
            print("meta_cache save:", exc, file=sys.stderr)

    def _disk_meta_lookup(self, filename):
        if not filename or is_stream(filename) or is_cdda(filename): return None
        if is_dvd(filename) or is_bluray(filename): return None
        try:
            st = os.stat(filename)
        except Exception:
            return None
        cache = getattr(self, "_disk_meta_cache", None) or {}
        rec = cache.get(filename)
        if not isinstance(rec, dict): return None
        try:
            if int(rec.get("m", -1)) != int(st.st_mtime) or int(rec.get("s", -1)) != int(st.st_size): return None
        except Exception:
            return None
        return {
            "title": rec.get("title") or os.path.splitext(os.path.basename(filename))[0],
            "artist": rec.get("artist") or "",
            "album": rec.get("album") or "",
            "year": rec.get("year") or "",
            "duration": float(rec.get("duration") or 0),
            "technical": rec.get("technical") or {},
        }

    def _disk_meta_store(self, filename, entry):
        if not filename or is_stream(filename) or is_cdda(filename): return
        if is_dvd(filename) or is_bluray(filename): return
        try:
            st = os.stat(filename)
        except Exception:
            return
        cache = getattr(self, "_disk_meta_cache", None)
        if cache is None:
            self._disk_meta_cache = {}
            cache = self._disk_meta_cache
        cache[filename] = {
            "m": int(st.st_mtime),
            "s": int(st.st_size),
            "title": entry.get("title") or "",
            "artist": entry.get("artist") or "",
            "album": entry.get("album") or "",
            "year": entry.get("year") or "",
            "duration": float(entry.get("duration") or 0),
            "technical": entry.get("technical") or {},
        }
        self._schedule_disk_meta_save()
    @staticmethod
    @lru_cache(maxsize=4096)
    def normalize_sort_text(value):
        if value is None: return ""
        value = str(value).strip()
        value = unicodedata.normalize("NFKD", value)
        value = "".join(
            char for char in value
            if not unicodedata.combining(char)
        )
        return value.casefold()

    def compare_text_values(self, value1, value2):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.compare_text_values(self, value1, value2)
        return None

    def compare_title(self, model, iterator1, iterator2, data):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.compare_title(self, model, iterator1, iterator2, data)
        return None

    def compare_artist(self, model, iterator1, iterator2, data):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.compare_artist(self, model, iterator1, iterator2, data)
        return None

    def compare_album(self, model, iterator1, iterator2, data):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.compare_album(self, model, iterator1, iterator2, data)
        return None

    def compare_duration(self, model, iterator1, iterator2, data):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.compare_duration(self, model, iterator1, iterator2, data)
        return None

    def on_column_clicked(self, column):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.on_column_clicked(self, column)
        return None

    def start_single_instance_server(self):
        self.instance_socket = None
        try: os.makedirs(CONFIG_DIR, exist_ok=True)
        except Exception: pass
        if os.path.exists(SOCKET_FILE):
            try: os.unlink(SOCKET_FILE)
            except Exception: pass
        try:
            self.instance_socket = socket.socket(
                socket.AF_UNIX,
                socket.SOCK_STREAM
            )
            old_mask = os.umask(0o077)
            try:
                self.instance_socket.bind(SOCKET_FILE)
            finally:
                os.umask(old_mask)
            self.instance_socket.listen(16)
            thread = threading.Thread(
                target=self.instance_server_loop,
                daemon=True,
                name="myostoox-instance-server",
            )
            thread.start()
            return True
        except Exception as exc:
            print("Serveur d'instance unique indisponible :", exc, file=sys.stderr)
            self.instance_socket = None
            return False

    def instance_server_loop(self):
        while True:
            sock = getattr(self, "instance_socket", None)
            if sock is None: break
            try:
                connection, _ = sock.accept()
            except OSError:
                break
            except Exception as exc:
                print("instance_server accept:", exc, file=sys.stderr)
                continue
            try:
                chunks = []
                connection.settimeout(5.0)
                while True:
                    try:
                        data = connection.recv(1024 * 256)
                    except socket.timeout:
                        break
                    except Exception:
                        break
                    if not data: break
                    chunks.append(data)
                    if sum(len(c) for c in chunks) > 8 * 1024 * 1024: break
                payload = b"".join(chunks).decode("utf-8", errors="ignore")
                files = [
                    line.strip()
                    for line in payload.splitlines()
                    if line.strip()
                ]
                GLib.idle_add(self.receive_external_files, files)
            except Exception as exc:
                print("instance_server handle:", exc, file=sys.stderr)
            finally:
                try: connection.close()
                except Exception: pass
    def receive_external_files(self, files):
        try:
            self.present()
            try:
                self.set_keep_above(True)
                self.set_keep_above(False)
            except Exception: pass
            self.present()
            try: GLib.timeout_add(1500, self._apply_window_layer)
            except Exception: pass
        except Exception: pass
        if not files: return False
        try: self.cancel_pending_session_restore()
        except Exception: pass
        added = False
        valid_paths = []
        for filename in files:
            if not isinstance(filename, str): continue
            if (
                is_audio_file(filename)
                or is_video_file(filename)
                or is_stream(filename)
                or is_cdda(filename)
            ):
                self.add_file(filename, save=False)
                valid_paths.append(filename)
                added = True
        if added:
            self.save_playlist()
        if len(valid_paths) == 1:
            self.play_file(valid_paths[0])
        return False

    def save_playlist(self):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.save_playlist(self)
        return None

    def load_playlist(self):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.load_playlist(self)
        return None

    def _restore_playlist_from_disk(self, quiet=True):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._restore_playlist_from_disk(self, quiet)
        return None

    def _playlist_append_path(self, filename):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._playlist_append_path(self, filename)
        return None

    def _playlist_views_detach_clear_reattach(self, clear_cache=True):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._playlist_views_detach_clear_reattach(self, clear_cache)
        return None

    def save_state(self):
        if _HAS_STATE_MOD:
            return _statemod.save_state(self)
        return None

    def load_state(self):
        if not os.path.isfile(STATE_FILE): return None
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as file:
                state = json.load(file)
            if not isinstance(state, dict): return None
            return state
        except Exception as e:
            print("Impossible de charger l'état :", e, file=sys.stderr)
            return None

    def restore_state(self):
        if _HAS_STATE_MOD:
            return _statemod.restore_state(self)
        return None

    def _resume_path_key(self, path):
        if _HAS_RESUME_MOD:
            return _resumemod._resume_path_key(self, path)
        return None

    def _resume_load_map(self):
        if _HAS_RESUME_MOD:
            return _resumemod._resume_load_map(self)
        return None

    def _resume_write_map(self):
        if _HAS_RESUME_MOD:
            return _resumemod._resume_write_map(self)
        return None

    def _resume_lookup(self, path):
        if _HAS_RESUME_MOD:
            return _resumemod._resume_lookup(self, path)
        return None

    def _resume_clear(self, path):
        if _HAS_RESUME_MOD:
            return _resumemod._resume_clear(self, path)
        return None

    def _resume_save_current(self, force=False):
        if _HAS_RESUME_MOD:
            return _resumemod._resume_save_current(self, force=False)
        return None

    def _resume_ask(self, path, pos):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod._resume_ask(self, path, pos)
        return False

    def _resume_schedule_seek(self, pos):
        if _HAS_RESUME_MOD:
            return _resumemod._resume_schedule_seek(self, pos)
        return None

    def _resume_try_seek(self):
        if _HAS_RESUME_MOD:
            return _resumemod._resume_try_seek(self)
        return None

    def _resume_track_snapshot(self):
        if _HAS_RESUME_MOD:
            return _resumemod._resume_track_snapshot(self)
        return None

    def _resume_lookup_record(self, path):
        if _HAS_RESUME_MOD:
            return _resumemod._resume_lookup_record(self, path)
        return None

    def _resume_store_pending_tracks(self, rec):
        if _HAS_RESUME_MOD:
            return _resumemod._resume_store_pending_tracks(self, rec)
        return None

    def _resume_schedule_tracks(self):
        if _HAS_RESUME_MOD:
            return _resumemod._resume_schedule_tracks(self)
        return None

    def _resume_try_apply_tracks(self):
        if _HAS_RESUME_MOD:
            return _resumemod._resume_try_apply_tracks(self)
        return None

    def _resume_resolve_subtitle_list_index(self, sub_kind, sub_index, sub_path):
        if _HAS_RESUME_MOD:
            return _resumemod._resume_resolve_subtitle_list_index(self, sub_kind, sub_index, sub_path)
        return None

    def _resume_apply_custom_audio_quiet(self, index):
        if _HAS_RESUME_MOD:
            return _resumemod._resume_apply_custom_audio_quiet(self, index)
        return None

    def toggle_resume_enabled(self, menuitem):
        if _HAS_RESUME_MOD:
            return _resumemod.toggle_resume_enabled(self, menuitem)
        return None

    def clear_resume_positions(self, *args):
        if _HAS_RESUME_MOD:
            return _resumemod.clear_resume_positions(self, *args)
        return None

    def cancel_pending_session_restore(self):
        self._pending_restore_path = None
        self._restore_handle_tries = 0

    def _deferred_restore_paused(self):
        path = getattr(self, "_pending_restore_path", None)
        if not path: return False
        try:
            if not self.get_realized(): return True
            if not self.get_window(): return True
        except Exception: pass
        try:
            if (
                is_video_file(path)
                or is_dvd(path)
                or is_bluray(path)
            ):
                try: self.show_video_area(True)
                except Exception: pass
                try: self._ensure_video_sink()
                except Exception: pass
                try:
                    while Gtk.events_pending():
                        Gtk.main_iteration_do(False)
                except Exception: pass
                try:
                    self._cache_video_window_handle()
                    self._apply_video_overlay_handle()
                except Exception: pass
                if not getattr(self, "_video_window_handle", None):
                    if not hasattr(self, "_restore_handle_tries"):
                        self._restore_handle_tries = 0
                    self._restore_handle_tries += 1
                    if self._restore_handle_tries < 25:
                        return True
        except Exception: pass
        self._pending_restore_path = None
        self._restore_handle_tries = 0
        try:
            if self._should_use_custom_pipeline(path):
                # Pas de préchargement playbin : Lecture relancera via play_file
                self.select_filename(path)
                self.update_information(path)
                return False
        except Exception: pass
        try:
            self.load_file_paused(path)
        except Exception as e:
            print("restauration différée:", e, file=sys.stderr)
        return False

    def load_file_paused(self, filename):
        """Restauration de session : précharge en pause avec sink vidéo réel."""
        if not filename:
            return
        try:
            if is_cdda(filename) or is_stream(filename) or is_dvd(filename) or is_bluray(filename):
                uri = filename
            else:
                if not os.path.isfile(filename):
                    return
                uri = GLib.filename_to_uri(os.path.abspath(filename), None)
            self._playback_generation += 1
            gen = self._playback_generation
            try:
                self._destroy_custom_pipeline()
            except Exception:
                pass
            try:
                self.player.set_state(Gst.State.NULL)
                self.player.get_state(100 * Gst.MSECOND)
            except Exception:
                pass
            if gen != self._playback_generation:
                return
            self.current_path = filename
            self.current_duration = 0
            self.current_is_cdda = is_cdda(filename)
            self.icy_title = ""
            self.icy_artist = ""
            if is_stream(filename):
                self.current_radio_name = self.find_radio_name(filename)
                if not getattr(self, "current_tv_name", None):
                    self.current_tv_name = self.find_tv_name(filename)
            else:
                self.current_radio_name = None
                self.current_tv_name = None
            try:
                self.position_scale.set_range(0, 1)
                self.position_scale.set_value(0)
            except Exception:
                pass
            self._last_known_position = 0.0
            self._pending_seek_delta = 0.0
            self._seek_in_progress = False
            try:
                self.reset_spectrum()
            except Exception:
                pass
            is_vid = bool(
                is_video_file(filename)
                or is_dvd(filename)
                or is_bluray(filename)
            )
            if is_vid:
                try:
                    self.show_video_area(True)
                except Exception:
                    pass
                try:
                    info = self._probe_video_info(filename)
                    self._current_video_hdr = bool(info and info.get("hdr"))
                    self._configure_playbin_buffers(audio_only=False)
                except Exception:
                    self._current_video_hdr = False
                try:
                    self._ensure_video_sink()
                except Exception as e:
                    print("restore ensure sink:", e, file=sys.stderr)
                try:
                    while Gtk.events_pending():
                        Gtk.main_iteration_do(False)
                except Exception:
                    pass
                try:
                    self._cache_video_window_handle()
                    self._apply_video_overlay_handle()
                except Exception:
                    pass
            else:
                try:
                    self.show_video_area(False)
                except Exception:
                    pass
                try:
                    self._release_real_video_sink()
                except Exception:
                    pass
            try:
                self.rebuild_audio_filter(force=True, restart=False)
            except Exception:
                pass
            try:
                self.set_subtitles_enabled(self.subtitles_enabled)
            except Exception:
                pass
            self.subtitle_tracks = []
            self.current_subtitle_index = -1
            self.audio_tracks = []
            self.current_audio_index = -1
            try:
                self._prepare_external_subtitles_for(filename)
            except Exception:
                pass
            try:
                self._register_external_subtitle_tracks()
            except Exception:
                pass
            try:
                self.player.set_property("current-text", -1)
            except Exception:
                pass
            if not is_vid:
                try:
                    self._refresh_lyrics_for_current()
                except Exception as e:
                    print("restore lyrics:", e, file=sys.stderr)
            try:
                self.player.set_property("uri", uri)
            except Exception as e:
                print("restore uri:", e, file=sys.stderr)
                return
            if is_vid:
                try:
                    self._ensure_video_sink()
                    self._apply_video_overlay_handle()
                except Exception:
                    pass
            try:
                ret = self.player.set_state(Gst.State.PAUSED)
            except Exception as e:
                print("restore PAUSED:", e, file=sys.stderr)
                ret = Gst.StateChangeReturn.FAILURE
            if ret == Gst.StateChangeReturn.FAILURE:
                try:
                    self.status_label.set_text(self.tr("Impossible de restaurer la session"))
                except Exception:
                    pass
                self.is_playing = False
                self.is_paused = False
                return
            self.is_playing = True
            self.is_paused = True
            try:
                self.play_button.set_label("▶")
            except Exception:
                pass
            try:
                self.status_label.set_text(self.tr("Session restaurée (en pause)"))
            except Exception:
                pass
            def _after_preroll():
                if gen != self._playback_generation:
                    return False
                if getattr(self, "current_path", None) != filename:
                    return False
                try:
                    self._try_update_duration()
                except Exception:
                    pass
                if is_vid:
                    try:
                        self._cache_video_window_handle()
                        self._apply_video_overlay_handle()
                        self._nudge_video_redraw()
                    except Exception:
                        pass
                try:
                    rate = float(getattr(self, "playback_rate", 1.0) or 1.0)
                    if abs(rate - 1.0) > 0.001 and self._is_speed_media(filename):
                        self._apply_playback_rate()
                except Exception:
                    pass
                return False
            try:
                GLib.timeout_add(400, _after_preroll)
            except Exception:
                _after_preroll()
            try:
                self.update_information(filename)
            except Exception:
                pass
            try:
                self.select_filename(filename)
            except Exception:
                pass
            try:
                self._update_pitch_menu_sensitivity()
                self._update_colorimetry_menu_sensitivity()
            except Exception:
                pass
        except Exception as e:
            try:
                self.status_label.set_text(self.tr("Erreur : ") + str(e))
            except Exception:
                pass
            print("Erreur restauration de session:", e, file=sys.stderr)
            self.is_playing = False
            self.is_paused = False

    def _load_ui_prefs(self):
        if _HAS_STATE_MOD:
            return _statemod._load_ui_prefs(self)
        return None

    def _css_from_palette(self, p):
        s = getattr(self, "_ui_s", None)
        if s is None:
            try:
                factor = float(getattr(self, "ui_scale", 1.0) or 1.0)
            except Exception:
                factor = 1.0
            s = lambda n, _f=factor: max(1, int(round(float(n) * _f)))
        _menu_sep_overrides = {
            "sang": "#9a4850",
            "bigtron": "#a85a18",
            "lantern": "#1a7a3c",
            "crusher": "#3a7088",
            "darth": "#8a2838",
        }
        try:
            _tn = str(getattr(self, "theme_name", "") or "").lower()
        except Exception:
            _tn = ""
        menu_sep = _menu_sep_overrides.get(_tn) or p.get("btn_border") or "#555555"
        def _hex_rgb(hx, fallback=(17, 19, 21)):
            try:
                h = (hx or "").lstrip("#")
                if len(h) >= 6: return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            except Exception: pass
            return fallback
        tr, tg, tb = _hex_rgb(p.get("tree_bg"))
        try:
            topacity = float(getattr(self, "playlist_transparency_opacity", 0.35))
        except Exception:
            topacity = 0.35
        topacity = max(0.0, min(1.0, topacity))
        try:
            win_transp = bool(getattr(self, "playlist_transparency", False))
        except Exception:
            win_transp = False
        if win_transp:
            window_bg_css = "transparent"
            entry_header_bg_css = "transparent"
        else:
            window_bg_css = p['window_bg']
            entry_header_bg_css = p['header_bg']
        _tn = (getattr(self, "theme_name", "") or "").lower()
        if _tn == "sang":
            scale_fill, scale_trough = "#c41e3a", "#3a1018"
            scale_thumb, scale_thumb_hover = "#e04050", "#ff6070"
        elif _tn == "nature":
            scale_fill, scale_trough = "#f0e6c8", "#2a4a30"
            scale_thumb, scale_thumb_hover = "#fff5dc", "#ffffff"
        elif _tn == "gdalf":
            scale_fill, scale_trough = "#ffffff", "#6a6558"
            scale_thumb, scale_thumb_hover = "#f5f1e6", "#ffffff"
        elif _tn == "darth":
            scale_fill, scale_trough = "#8a929c", "#1a1010"
            scale_thumb, scale_thumb_hover = "#b0b8c0", "#d0d6dc"
        elif _tn == "fremen":
            scale_fill, scale_trough = "#c4a06a", "#2a2014"
            scale_thumb, scale_thumb_hover = "#d4b888", "#e8d4b0"
        else:
            scale_fill, scale_trough = "#2f80ed", "#1a2a3a"
            scale_thumb, scale_thumb_hover = "#4d9fff", "#7ab8ff"
        slider_color = (
            p.get("btn_active_border")
            or p.get("tree_sel_bg")
            or p.get("title_fg")
            or "#5c737e"
        )
        slider_hover = p.get("title_fg") or p.get("btn_fg") or slider_color
        _theme = getattr(self, "theme_name", "") or ""
        _accent_scroll_themes = (
            "bigtron",
            "lantern",
            "crusher",
            "darth",
            "fremen",
            "bigmegatron",
        )
        _bb = (p.get("btn_border") or "").lower()
        if _theme in _accent_scroll_themes or _bb in ("#000000", "#000", "black"):
            scroll_slider = (
                p.get("tree_sel_bg")
                or p.get("topbar_bg")
                or p.get("btn_fg")
                or slider_color
            )
            scroll_slider_hover = p.get("btn_fg") or p.get("header_fg") or scroll_slider
            scroll_trough = p.get("btn_bg") or p.get("header_bg") or p.get("tree_bg")
        else:
            scroll_slider = p.get("btn_border") or slider_color
            scroll_slider_hover = p.get("btn_hover") or scroll_slider
            scroll_trough = p.get("header_bg") or p.get("tree_bg")
        _tpl = None
        try:
            if _HAS_THEMES_MOD and hasattr(_th, "CSS_TEMPLATE"):
                _tpl = _th.CSS_TEMPLATE
        except Exception:
            _tpl = None
        if not _tpl:
            import zlib as _z
            _tpl = _z.decompress(_CSS_TPL_Z).decode("utf-8")
        return eval("f" + repr(_tpl), dict(locals())).encode("utf-8")

    def build_css(self):
        palette = THEME_PALETTES.get(
            getattr(self, "theme_name", "sombre"),
            THEME_PALETTES["sombre"],
        )
        css = self._css_from_palette(palette)
        provider = Gtk.CssProvider()
        provider.load_from_data(css)
        screen = Gdk.Screen.get_default()
        if self._css_provider is not None:
            try:
                Gtk.StyleContext.remove_provider_for_screen(
                    screen, self._css_provider
                )
            except Exception: pass
        self._css_provider = provider
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER,
        )

    def set_theme(self, name):
        if name not in THEME_PALETTES: return
        if name == getattr(self, "theme_name", None): return
        self.theme_name = name
        self.build_css()
        try: self.save_state()
        except Exception: pass
        self.status_label.set_text(
            self.tr("Thèmes") + " : " + self.tr(THEME_LABELS.get(name, name))
        )

    def _translate_dialog_action_buttons(self, dialog):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod._translate_dialog_action_buttons(self, dialog)
        return None

    def _style_app_dialog(self, widget):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod._style_app_dialog(self, widget)
        return None
    def build_interface(self):
        if _HAS_INTERFACE_MOD:
            return _interfacemod.build_interface(self)
        return None

    def make_button(self, text, tooltip):
        button = Gtk.Button(label=text)
        button.get_style_context().add_class("control")
        button.set_tooltip_text(tooltip)
        return button

    def create_columns(self):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.create_columns(self)
        return None

    def _refresh_playlist_current_style(self):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._refresh_playlist_current_style(self)
        return None

    def _path_is_missing(self, path):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._path_is_missing(self, path)
        return None

    def _playlist_cell_data(self, column, cell, model, iterator, col_id):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._playlist_cell_data(self, column, cell, model, iterator, col_id)
        return None

    def _playlist_countdown_seconds(self, path):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._playlist_countdown_seconds(self, path)
        return None

    def _playlist_countdown_tick(self):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._playlist_countdown_tick(self)
        return None

    def playlist_filter_func(self, model, iterator, data):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.playlist_filter_func(self, model, iterator, data)
        return None

    def on_search_changed(self, entry):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.on_search_changed(self, entry)
        return None

    def setup_drag_and_drop(self):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.setup_drag_and_drop(self)
        return None

    def on_drag_data_received(self, widget, context, x, y, selection, info, timestamp):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.on_drag_data_received(self, widget, context, x, y, selection, info, timestamp)
        return None
    def _setup_playlist_reorder(self):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._setup_playlist_reorder(self)
        return None

    def _filter_path_to_child_index(self, fpath):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._filter_path_to_child_index(self, fpath)
        return None

    def _playlist_collect_selected_indices(self, tree, prefer_idx=None):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._playlist_collect_selected_indices(self, tree, prefer_idx)
        return None

    def _playlist_left_button_press(self, tree, event):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._playlist_left_button_press(self, tree, event)
        return None

    def _on_playlist_reorder_motion(self, tree, event):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._on_playlist_reorder_motion(self, tree, event)
        return None

    def _on_playlist_reorder_release(self, tree, event):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._on_playlist_reorder_release(self, tree, event)
        return None

    def _playlist_move_indices(self, src_indices, dest_idx):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._playlist_move_indices(self, src_indices, dest_idx)
        return None

    def setup_keyboard(self):
        self.connect("key-press-event", self.on_key_press)

    def _normalize_key_name(self, key):
        if _HAS_SHORTCUTS_MOD:
            return _sc_normalize_key_name(key)
        return key or ""

    def _event_to_shortcut(self, event):
        if _HAS_SHORTCUTS_MOD:
            return _sc_event_to_shortcut(event)
        return ""

    def _shortcut_matches(self, action, event_str, key_name):
        if _HAS_SHORTCUTS_MOD:
            return _sc_shortcut_matches(self, action, event_str, key_name)
        return False

    def _is_text_input_focused(self):
        if _HAS_SHORTCUTS_MOD:
            return _sc_is_text_input_focused(self)
        return False

    def on_key_press(self, widget, event):
        if _HAS_SHORTCUTS_MOD:
            return _sc_on_key_press(self, widget, event)
        return False

    def focus_search_entry(self):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.focus_search_entry(self)
        return None

    def _on_add_button_clicked(self, button):
        self._popup_add_media_menu(button)

    def add_files(self, *args):
        self._add_files_dialog()

    def add_folder(self, *args):
        self._add_folder_dialog()

    def _popup_add_media_menu(self, widget=None):
        if _HAS_MENUS_MOD:
            return _menumod._popup_add_media_menu(self, widget)
        return None


    def _add_files_dialog(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod._add_files_dialog(self, *args)
        return None

    def _add_folder_dialog(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod._add_folder_dialog(self, *args)
        return None

    def _ingest_media_paths(self, paths):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._ingest_media_paths(self, paths)
        return None
    def _update_record_button_state(self):
        if _HAS_RECORDING_MOD:
            return _recmod._update_record_button_state(self)
        return None

    def toggle_recording(self, *args):
        if _HAS_RECORDING_MOD:
            return _recmod.toggle_recording(self, *args)
        return None

    def _start_recording(self):
        if _HAS_RECORDING_MOD:
            return _recmod._start_recording(self)
        return None

    def _on_record_bus_message(self, bus, message):
        if _HAS_RECORDING_MOD:
            return _recmod._on_record_bus_message(self, bus, message)
        return None

    def _on_record_failed(self, err_msg=""):
        if _HAS_RECORDING_MOD:
            return _recmod._on_record_failed(self, err_msg="")
        return None

    def _on_record_eos(self):
        if _HAS_RECORDING_MOD:
            return _recmod._on_record_eos(self)
        return None

    def _destroy_record_pipeline(self):
        if _HAS_RECORDING_MOD:
            return _recmod._destroy_record_pipeline(self)
        return None

    def _stop_recording(self, show_save_dialog=True):
        if _HAS_RECORDING_MOD:
            return _recmod._stop_recording(self, show_save_dialog=True)
        return None

    def _prompt_save_recording(self, temp_path):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod._prompt_save_recording(self, temp_path)
        return None

    def add_directory(self, directory):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.add_directory(self, directory)
        return None

    def _add_directory_files(self, files):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._add_directory_files(self, files)
        return None

    def add_file(self, filename, save=True, scroll_to=True):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.add_file(self, filename, save, scroll_to)
        return None

    def open_stream_url(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.open_stream_url(self, *args)
        return None

    def list_cd_tracks(self):
        if _HAS_DISCS_MOD:
            return _discsmod.list_cd_tracks(self)
        return None

    def _find_optical_devices(self):
        devices = []
        seen = set()
        for n in range(0, 16):
            path = "/dev/sr%d" % n
            if path not in seen and os.path.exists(path):
                devices.append(path)
                seen.add(path)
        for alias in ("/dev/cdrom", "/dev/dvd", "/dev/bd", "/dev/cdrw"):
            if alias not in seen and os.path.exists(alias):
                try:
                    real = os.path.realpath(alias)
                except Exception:
                    real = alias
                if real not in seen:
                    devices.append(alias)
                    seen.add(alias)
                    seen.add(real)
        return devices

    def toggle_disc_tray(self, *args):
        if _HAS_DISCS_MOD:
            return _discsmod.toggle_disc_tray(self, *args)
        return None

    def add_cd(self, *args):
        if _HAS_DISCS_MOD:
            return _discsmod.add_cd(self, *args)
        return None

    def list_dvd_titles(self):
        if _HAS_DISCS_MOD:
            return _discsmod.list_dvd_titles(self)
        return None

    def add_dvd(self, *args):
        if _HAS_DISCS_MOD:
            return _discsmod.add_dvd(self, *args)
        return None

    def list_bluray_titles(self):
        if _HAS_DISCS_MOD:
            return _discsmod.list_bluray_titles(self)
        return None

    def add_bluray(self, *args):
        if _HAS_DISCS_MOD:
            return _discsmod.add_bluray(self, *args)
        return None

    def _clear_now_playing_display(self, reset_time=False):
        try: self.bottom_title.set_text(self.tr("Aucun morceau sélectionné"))
        except Exception: pass
        try: self.bottom_artist.set_text("")
        except Exception: pass
        try: self.bottom_album.set_text("")
        except Exception: pass
        try: self.set_default_cover()
        except Exception: pass
        if reset_time:
            self.current_duration = 0
            self._last_known_position = 0.0
            try:
                self.position_scale.set_range(0, 1)
                self.position_scale.set_value(0)
            except Exception: pass
            try: self.time_label.set_text("0:00 • 0:00")
            except Exception: pass
        try: self._update_mini_title()
        except Exception: pass
        try: self._update_nano_tooltip()
        except Exception: pass
    def _refresh_bottom_after_selection_cleared(self):
        path = getattr(self, "current_path", None)
        if path:
            try:
                still_there = path in self.get_paths()
            except Exception:
                still_there = False
            if still_there:
                try: self.update_information(path)
                except Exception: pass
                return
            self.current_path = None
        self._clear_now_playing_display(reset_time=True)

    def selection_changed(self, selection):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.selection_changed(self, selection)
        return None

    def _selection_info_timeout(self):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._selection_info_timeout(self)
        return None

    def row_activated(self, tree, path, column):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.row_activated(self, tree, path, column)
        return None

    def update_information(self, filename):
        if _HAS_STATUS_MOD:
            return _statusmod.update_information(self,filename)
        return None

    def set_default_cover(self):
        if _HAS_COVER_MOD:
            return _covermod.set_default_cover(self)
        return None

    def set_cover(self, data, for_path=None):
        if _HAS_COVER_MOD:
            return _covermod.set_cover(self, data, for_path)
        return None

    def reset_spectrum(self):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod.reset_spectrum(self)
        return None

    def _idle_memory_trim(self):
        """Trim périodique à l'arrêt : limite la croissance long-terme sans impact lecture."""
        if getattr(self, "_app_closing", False):
            self._idle_trim_timeout_id = 0
            return False
        try:
            if not getattr(self, "is_playing", False) and not getattr(self, "is_paused", False):
                trim_memory(force=True, full=True)
                for attr, limit in (
                    ("_video_probe_cache", PROBE_CACHE_MAX),
                    ("_mkv_probe_cache", PROBE_CACHE_MAX),
                    ("_sub_lang_cache", PROBE_CACHE_MAX),
                    ("_discover_info_cache", 4),
                ):
                    c = getattr(self, attr, None)
                    if isinstance(c, OrderedDict):
                        while len(c) > limit:
                            try:
                                c.popitem(last=False)
                            except Exception:
                                break
                    elif isinstance(c, dict) and len(c) > limit:
                        try:
                            for k in list(c.keys())[: max(1, len(c) - limit)]:
                                c.pop(k, None)
                        except Exception:
                            pass
        except Exception:
            pass
        return True


    def _extract_magnitudes(self, structure):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._extract_magnitudes(self, structure)
        return None

    def _build_spectrum_ranges(self, source_count):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._build_spectrum_ranges(self, source_count)
        return None

    def _spectrum_message_running_time(self, structure):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._spectrum_message_running_time(self, structure)
        return None

    def _spectrum_playback_running_time_ns(self):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._spectrum_playback_running_time_ns(self)
        return None

    def _spectrum_enqueue(self, rt_ns, targets):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._spectrum_enqueue(self, rt_ns, targets)
        return None

    def _flush_spectrum_delay(self):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._flush_spectrum_delay(self)
        return None

    def process_spectrum(self, structure):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod.process_spectrum(self, structure)
        return None

    def update_visualizer(self):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod.update_visualizer(self)
        return None

    def _spectrum_base_color(self):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._spectrum_base_color(self)
        return None

    def _draw_spectrum_bars(self, cr, width, height, us):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._draw_spectrum_bars(self, cr, width, height, us)
        return None

    def _draw_spectrum_oscilloscope(self, cr, width, height, us):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._draw_spectrum_oscilloscope(self, cr, width, height, us)
        return None

    def _draw_spectrum_pixel(self, cr, width, height, us):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._draw_spectrum_pixel(self, cr, width, height, us)
        return None

    def draw_visualizer(self, widget, cr):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod.draw_visualizer(self, widget, cr)
        return None

    def _spectrum_style_allowed(self):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._spectrum_style_allowed(self)
        return None

    def set_spectrum_style(self, style):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod.set_spectrum_style(self, style)
        return None

    def _load_performance_mode(self):
        try:
            if os.path.isfile(STATE_FILE):
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    state = json.load(f)
                if isinstance(state, dict):
                    mode = state.get("performance_mode")
                    if mode in ("hardware", "software"): return mode
        except Exception: pass
        return "hardware"

    def _apply_decoder_performance_mode(self, force_software=False):
        mode = getattr(self, "performance_mode", "hardware")
        if force_software:
            mode = "software"
        if mode == "hardware":
            # NVIDIA prioritaire. VA/Vulkan/QSV restent sous le logiciel par défaut :
            # les forcer fait fermer l'app sur certains MKV 4K (driver / negotiation).
            # MYOSTOOX_VA_FIRST=1 active le matériel non-NVIDIA pour ceux qui le veulent.
            _va_first = os.environ.get("MYOSTOOX_VA_FIRST", "").strip().lower() in (
                "1", "true", "yes", "on"
            )
            for name in _NVIDIA_DECODER_NAMES:
                _gst_set_rank(name, Gst.Rank.PRIMARY + 200)
            for name in _SOFTWARE_VIDEO_DECODER_NAMES:
                _gst_set_rank(name, Gst.Rank.PRIMARY + 80)
            for name in _OTHER_HW_DECODER_NAMES:
                _gst_set_rank(
                    name,
                    Gst.Rank.PRIMARY + (150 if _va_first else 20),
                )
            try: apply_safe_gstreamer_ranks(prefer_nvidia_av1=True)
            except Exception: pass
        else:
            for name in _NVIDIA_DECODER_NAMES:
                _gst_set_rank(name, Gst.Rank.NONE)
            for name in _OTHER_HW_DECODER_NAMES:
                _gst_set_rank(name, Gst.Rank.NONE)
            for name in _SOFTWARE_VIDEO_DECODER_NAMES:
                _gst_set_rank(name, Gst.Rank.PRIMARY + 100)
            try: apply_safe_gstreamer_ranks(prefer_nvidia_av1=False)
            except Exception: pass
    def _apply_safe_audio_decoder_ranks(self):
        try:
            factory = Gst.ElementFactory.find("a52dec")
            if factory is not None:
                factory.set_rank(Gst.Rank.NONE)
        except Exception: pass
        for name in ("avdec_eac3", "avdec_ac3"):
            try:
                factory = Gst.ElementFactory.find(name)
                if factory is not None:
                    factory.set_rank(Gst.Rank.PRIMARY + 100)
            except Exception: pass

    def set_performance_mode(self, mode):
        if mode not in ("hardware", "software"): return
        if mode == getattr(self, "performance_mode", None): return
        self.performance_mode = mode
        try: self.save_state()
        except Exception: pass
        self._apply_decoder_performance_mode()
        try: self._configure_playbin_buffers()
        except Exception: pass
        label = (
            self.tr("Matériel") if mode == "hardware" else self.tr("Logiciel")
        )
        self.status_label.set_text(
            self.tr("Performances") + " : " + label
        )
        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text=self.tr("Redémarrage recommandé"),
        )
        dialog.format_secondary_text(
            self.tr(
                "Le mode de décodage vidéo a été modifié.\n"
                "Pour une prise en compte complète, redémarrez l'application."
            )
        )
        dialog.run()
        dialog.destroy()

    def _create_video_sink(self, half_res=True):
        if _HAS_PLAYER_MOD:
            try:
                return _py_create_video_sink(self, half_res=half_res)
            except Exception as e:
                print("create_video_sink:", e, file=sys.stderr)
        return None


    def _ensure_video_sink(self):
        want_scale = True
        try:
            if _HAS_PLAYER_MOD and hasattr(_py, "_should_downscale_for_display"):
                want_scale = bool(_py._should_downscale_for_display(self, True))
            else:
                dims = getattr(self, "_current_video_dims", None)
                if dims is not None and len(dims) >= 2:
                    h = int(dims[1] or 0)
                    if h > 0 and h < 2000:
                        want_scale = False
        except Exception:
            want_scale = True
        want_hdr = False
        try:
            if _HAS_PLAYER_MOD and hasattr(_py, "hdr_tonemap_wanted"):
                want_hdr = bool(_py.hdr_tonemap_wanted(self))
        except Exception:
            want_hdr = False
        have_hdr = bool(getattr(self, "_video_sink_has_tonemap", False))
        have = getattr(self, "_video_sink_has_scale", None)
        if (
            getattr(self, "_video_sink_is_real", False)
            and self.video_sink is not None
            and have is not None
            and bool(have) == bool(want_scale)
            and have_hdr == want_hdr
        ):
            return self.video_sink
        try:
            if getattr(self, "_video_sink_is_real", False):
                try:
                    self._release_real_video_sink()
                except Exception:
                    self._video_sink_is_real = False
                    self.video_sink = None
        except Exception:
            pass
        try:
            sink = self._create_video_sink(half_res=True)
        except Exception:
            sink = None
        if sink is None:
            return self.video_sink
        self.video_sink = sink
        self._video_sink_is_real = True
        try:
            self._video_sink_has_scale = bool(want_scale)
        except Exception:
            pass
        try:
            if self.player is not None:
                self.player.set_property("video-sink", sink)
        except Exception:
            pass
        return sink

    def _release_real_video_sink(self):
        if not getattr(self, "_video_sink_is_real", False): return
        try:
            fake = Gst.ElementFactory.make("fakesink", "video_sink_placeholder")
            if fake is None: return
            try: fake.set_property("sync", False)
            except Exception: pass
            try: fake.set_property("async", False)
            except Exception: pass
            if self.player is not None:
                self.player.set_property("video-sink", fake)
            self.video_sink = fake
            self._video_sink_is_real = False
            try:
                self._video_sink_overlay = None
            except Exception:
                pass
            try: self._pause_pixbuf = None
            except Exception: pass
        except Exception as exc:
            print("release video sink:", exc, file=sys.stderr)



    def _apply_av_sync_compensation(self, enable=True):
        try:
            if _HAS_PLAYER_MOD:
                _py._apply_av_sync_compensation(self, enable=False)
        except Exception:
            pass
        try:
            if self.player is not None and self.player.find_property("av-offset") is not None:
                self.player.set_property("av-offset", 0)
        except Exception:
            pass


    def _on_decodebin_autoplug_sort(self, decodebin, pad, caps, factories):
        if not caps or not caps.to_string().startswith("video/x-h265"):
            return factories

        print(
            "\nMYOSTOOX AUTOPLUG-SORT AVANT :",
            [f.get_name() for f in factories],
            file=sys.stderr
        )

        try:
            ordered = sorted(
                factories,
                key=lambda f: (
                    0 if f.get_name() == "vah265dec" else
                    1 if f.get_name() == "avdec_h265" else
                    2
                )
            )

            print(
                "MYOSTOOX AUTOPLUG-SORT APRES :",
                [f.get_name() for f in ordered],
                file=sys.stderr
            )

            return ordered

        except Exception as e:
            print(
                "MYOSTOOX AUTOPLUG-SORT ERROR:",
                repr(e),
                file=sys.stderr
            )
            return factories

    def _debug_video_pad_caps(self, element):
        try:
            for pad in element.pads:
                if pad.get_direction() == Gst.PadDirection.SRC:
                    caps = pad.get_current_caps()

                    print(
                        "MYOSTOOX PAD CAPS:",
                        element.get_name(),
                        "=>",
                        caps.to_string() if caps else "NON NEGOCIEES",
                        file=sys.stderr
                    )

        except Exception as e:
            print(
                "MYOSTOOX PAD CAPS ERROR:",
                repr(e),
                file=sys.stderr
            )

    def _on_playbin_deep_element_added(self, bin, sub_bin, element):
        if GST_ELEMENT_DEBUG:
            return self._on_playbin_deep_element_added_debug(bin, sub_bin, element)
        try:
            if _HAS_PLAYER_MOD:
                _py._tune_playbin_element(self, element)
        except Exception:
            pass
        try:
            factory = element.get_factory()
            if (
                factory is not None
                and factory.get_name() == "decodebin"
                and not getattr(element, "_myostoox_sort_connected", False)
            ):
                element.connect("autoplug-sort", self._on_decodebin_autoplug_sort)
                element._myostoox_sort_connected = True
        except Exception:
            pass

    def _on_playbin_deep_element_added_debug(self, bin, sub_bin, element):
        if _HAS_GST_DEBUG_MOD:
            return _gstdebugmod._on_playbin_deep_element_added_debug(self,bin,sub_bin,element)
        return None

    def _configure_playbin_buffers(self, audio_only=False):
        if _HAS_PLAYER_MOD:
            try:
                return _py_configure_playbin_buffers(self, audio_only=audio_only)
            except Exception as e:
                print("configure_playbin_buffers:", e, file=sys.stderr)


    def _set_spectrum_active_for_media(self, is_video):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._set_spectrum_active_for_media(self, is_video)
        return None

    def _spectrum_messages_wanted(self):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._spectrum_messages_wanted(self)
        return None

    def _visualizer_should_animate(self):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._visualizer_should_animate(self)
        return None


    def _sync_spectrum_activity(self):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._sync_spectrum_activity(self)
        return None
    def _ensure_visualizer_timer(self):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._ensure_visualizer_timer(self)
        return None

    def _release_pause_pixbuf(self):
        self._pause_pixbuf = None

    def _cache_video_window_handle(self):
        if self.video_area is None: return None
        try:
            if not self.video_area.get_realized():
                self.video_area.realize()
            try:
                if not self.video_area.get_mapped():
                    self.video_area.show()
                    while Gtk.events_pending():
                        Gtk.main_iteration_do(False)
            except Exception: pass
            window = self.video_area.get_window()
            if window is None: return None
            try: window.ensure_native()
            except Exception: pass
            xid = window.get_xid()
            if xid and xid != 0:
                self._video_window_handle = xid
                return xid
        except Exception as e:
            print("Erreur cache window handle:", e, file=sys.stderr)
        return None

    def _iter_video_overlay_targets(self, root):
        """Yield elements that can take an X11 window handle (unwrap bins)."""
        if root is None:
            return
        seen = set()
        stack = [root]
        while stack:
            el = stack.pop()
            if el is None:
                continue
            try:
                i = id(el)
                if i in seen:
                    continue
                seen.add(i)
            except Exception:
                pass
            yield el
            try:
                it = el.iterate_elements()
            except Exception:
                it = None
            if it is None:
                continue
            try:
                while True:
                    ok, child = it.next()
                    if not ok:
                        break
                    stack.append(child)
            except Exception:
                pass

    def _apply_video_overlay_handle(self, sink=None):
        handle = getattr(self, "_video_window_handle", None)
        if not handle:
            handle = self._cache_video_window_handle()
        if not handle:
            return False
        targets = []
        ov = getattr(self, "_video_sink_overlay", None)
        if ov is not None:
            targets.append(ov)
        if sink is not None:
            targets.append(sink)
        vs = getattr(self, "video_sink", None)
        if vs is not None:
            targets.append(vs)
        ok = False
        tried = set()
        for root in targets:
            for target in self._iter_video_overlay_targets(root):
                try:
                    tid = id(target)
                    if tid in tried:
                        continue
                    tried.add(tid)
                except Exception:
                    pass
                try:
                    if isinstance(target, GstVideo.VideoOverlay):
                        GstVideo.VideoOverlay.set_window_handle(target, handle)
                        ok = True
                    elif hasattr(target, "set_window_handle"):
                        target.set_window_handle(handle)
                        ok = True
                except Exception as e:
                    print("apply overlay handle:", e, file=sys.stderr)
        return ok

    def on_sync_message(self, bus, message):
        try:
            if not GstVideo.is_video_overlay_prepare_window_handle_message(message): return
        except Exception:
            structure = message.get_structure()
            if structure is None: return
            if structure.get_name() != "prepare-window-handle": return
        handle = self._video_window_handle
        if handle is None:
            handle = self._cache_video_window_handle()
        if handle is None: return
        try:
            sink = message.src
            if isinstance(sink, GstVideo.VideoOverlay):
                GstVideo.VideoOverlay.set_window_handle(sink, handle)
            elif hasattr(sink, "set_window_handle"):
                sink.set_window_handle(handle)
            self._apply_video_overlay_handle(sink)
        except Exception as e:
            print("Erreur prepare-window-handle:", e, file=sys.stderr)

    def _nudge_video_redraw(self):
        if not self.current_is_video or self.video_sink is None: return False
        try:
            if isinstance(self.video_sink, GstVideo.VideoOverlay):
                GstVideo.VideoOverlay.expose(self.video_sink)
            if self.video_area is not None:
                self.video_area.queue_draw()
        except Exception: pass
        return False

    def on_video_realize(self, widget):
        try:
            window = widget.get_window()
            if window is not None:
                black = Gdk.RGBA()
                black.red = 0.0
                black.green = 0.0
                black.blue = 0.0
                black.alpha = 1.0
                window.set_background_rgba(black)
        except Exception: pass
        self._cache_video_window_handle()

    def on_video_size_allocate(self, widget, allocation):
        if getattr(self, "_fs_controls_visible", False):
            try: GLib.idle_add(self._position_fs_popup)
            except Exception: pass
        if not self.current_is_video or self.video_sink is None: return
        if self._size_allocate_timer:
            try: GLib.source_remove(self._size_allocate_timer)
            except Exception: pass
            self._size_allocate_timer = 0
        def _after_resize():
            self._size_allocate_timer = 0
            self._cache_video_window_handle()
            self._apply_video_overlay_handle()
            try:
                sink = getattr(self, "video_sink", None)
                if sink is not None and sink.find_property("force-aspect-ratio"):
                    sink.set_property("force-aspect-ratio", True)
            except Exception: pass
            self._nudge_video_redraw()
            return False
        self._size_allocate_timer = GLib.timeout_add(150, _after_resize)

    def on_video_draw(self, widget, cr):
        if os.environ.get("MYOSTOOX_DEBUG_LYRICS", "").strip():
            _t = time.monotonic()
            if _t - getattr(self, "_dbg_lyr_t", 0.0) > 1.0:
                self._dbg_lyr_t = _t
                a = widget.get_allocation()
                print(
                    "[lyrics-draw] lyrics_mode=%s data=%s size=%dx%d video=%s"
                    % (
                        getattr(self, "lyrics_mode", None),
                        bool(getattr(self, "lyrics_data", None)),
                        a.width, a.height,
                        getattr(self, "current_is_video", None),
                    ),
                    file=sys.stderr,
                )
        if getattr(self, "lyrics_mode", False):
            try:
                self._draw_lyrics(widget, cr)
            except Exception as e:
                print("lyrics draw:", e, file=sys.stderr)
            return True
        if (
            bool(getattr(self, "hide_playlist_mode", False))
            and not getattr(self, "current_is_video", False)
            and not (self.is_playing and not self.is_paused)
        ):
            allocation = widget.get_allocation()
            cr.set_source_rgb(0.06, 0.07, 0.09)
            cr.rectangle(0, 0, allocation.width, allocation.height)
            cr.fill()
            return True
        if self.current_is_video and self.is_playing and not self.is_paused: return False
        if self.current_is_video and self.is_playing and self.is_paused:
            allocation = widget.get_allocation()
            cr.set_source_rgb(0.0, 0.0, 0.0)
            cr.rectangle(0, 0, allocation.width, allocation.height)
            cr.fill()
            if self._pause_pixbuf is not None:
                try:
                    pw = self._pause_pixbuf.get_width()
                    ph = self._pause_pixbuf.get_height()
                    if pw > 0 and ph > 0 and allocation.width > 0 and allocation.height > 0:
                        scale = min(
                            allocation.width / pw,
                            allocation.height / ph,
                        )
                        dw = max(1, int(pw * scale))
                        dh = max(1, int(ph * scale))
                        ox = (allocation.width - dw) // 2
                        oy = (allocation.height - dh) // 2
                        pix = self._pause_pixbuf
                        if dw != pw or dh != ph:
                            pix = self._pause_pixbuf.scale_simple(
                                dw, dh, GdkPixbuf.InterpType.BILINEAR
                            )
                        Gdk.cairo_set_source_pixbuf(cr, pix, ox, oy)
                        cr.paint()
                except Exception: pass
            return True
        allocation = widget.get_allocation()
        cr.set_source_rgb(0.0, 0.0, 0.0)
        cr.rectangle(0, 0, allocation.width, allocation.height)
        cr.fill()
        return True

    def _capture_pause_frame(self):
        self._pause_pixbuf = None
        if not self.current_is_video or self.video_area is None: return
        try:
            if self.video_sink is not None and isinstance(
                self.video_sink, GstVideo.VideoOverlay
            ):
                try: GstVideo.VideoOverlay.expose(self.video_sink)
                except Exception: pass
            window = self.video_area.get_window()
            if window is None: return
            w = self.video_area.get_allocated_width()
            h = self.video_area.get_allocated_height()
            if w <= 0 or h <= 0: return
            pixbuf = Gdk.pixbuf_get_from_window(window, 0, 0, w, h)
            if pixbuf is None: return
            max_w = 960
            if w > max_w:
                nh = max(1, int(h * (max_w / float(w))))
                try:
                    pixbuf = pixbuf.scale_simple(
                        max_w, nh, GdkPixbuf.InterpType.BILINEAR
                    )
                except Exception: pass
            self._pause_pixbuf = pixbuf
        except Exception:
            self._pause_pixbuf = None

    def _capture_pause_frame_and_redraw(self):
        self._capture_pause_frame()
        try:
            if self.video_area is not None:
                self.video_area.queue_draw()
        except Exception: pass
        return False

    def _refresh_video_surface(self):
        if not self.current_is_video: return False
        try:
            self._cache_video_window_handle()
            if self.is_paused and self._pause_pixbuf is not None:
                if self.video_area is not None:
                    self.video_area.queue_draw()
            else:
                self._nudge_video_redraw()
        except Exception: pass
        return False

    def on_window_focus_in(self, widget, event):
        if _HAS_WINDOW_STATE_MOD:
            return _wsmod.on_window_focus_in(self,widget,event)
        return None

    def on_window_map(self, widget, event):
        if _HAS_WINDOW_STATE_MOD:
            return _wsmod.on_window_map(self,widget,event)
        return None

    def on_video_button_press(self, widget, event):
        if event.type == Gdk.EventType._2BUTTON_PRESS and event.button == 1:
            self.toggle_video_fullscreen()
            return True
        return False

    def on_window_state_event(self, widget, event):
        if _HAS_WINDOW_STATE_MOD:
            return _wsmod.on_window_state_event(self,widget,event)
        return None

    def toggle_video_fullscreen(self):
        if not (self.current_is_video or getattr(self, "lyrics_mode", False)): return
        really_fs = False
        try:
            win = self.get_window()
            if win is not None:
                really_fs = bool(win.get_state() & Gdk.WindowState.FULLSCREEN)
        except Exception:
            really_fs = self.is_fullscreen
        if really_fs or self.is_fullscreen:
            self.unfullscreen()
            self._restore_ui_after_fullscreen()
        else:
            self._enter_video_fullscreen()

    def _apply_fullscreen_ui_layout(self):
        try:
            for attr in ("top_bar_wrap", "top_bar", "bottom_bar_wrap", "bottom_bar"):
                w = getattr(self, attr, None)
                if w is not None:
                    try: w.hide()
                    except Exception: pass
            if hasattr(self, "playlist_box"):
                self.playlist_box.hide()
            if hasattr(self, "video_overlay"):
                self.video_overlay.show()
            self.video_area.show()
            self.video_area.set_size_request(-1, -1)
            try:
                if getattr(self, "lyrics_mode", False):
                    self.video_area.queue_draw()
            except Exception: pass
            alloc = self.get_allocation()
            h = max(alloc.height, self.get_allocated_height() or 800)
            self.content_paned.set_position(max(h - 2, 400))
        except Exception as e:
            print("Erreur layout plein écran:", e, file=sys.stderr)

    def _set_fullscreen_compositor_bypass(self, enabled):
        """Active ou retire le contournement du compositeur X11."""
        prop = "_NET_WM_BYPASS_COMPOSITOR"

        if enabled:
            try:
                if GdkX11 is None:
                    return False

                window = self.get_window()
                if window is None:
                    return False

                xid = int(GdkX11.X11Window.get_xid(window))
                if not xid:
                    return False

                command = [
                    "xprop",
                    "-id", hex(xid),
                    "-f", prop, "32c",
                    "-set", prop, "1",
                ]

            except Exception as e:
                print(
                    "Impossible d'obtenir la fenêtre X11 :",
                    e, file=sys.stderr
                )
                return False

        else:
            xid = getattr(self, "_compositor_bypass_xid", None)
            if not xid:
                return False

            command = [
                "xprop",
                "-id", hex(int(xid)),
                "-remove", prop,
            ]

        try:
            subprocess.run(
                command,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3,
            )

            if enabled:
                self._compositor_bypass_xid = xid
            else:
                self._compositor_bypass_xid = None

            return True

        except (OSError, subprocess.SubprocessError) as e:
            print(
                "Erreur propriété X11 du compositeur :",
                e, file=sys.stderr
            )
            return False

    def _enter_video_fullscreen(self):
        try:
            try:
                self._fs_popup_geom = None
                self._hide_fs_controls(immediate=True, force=True)
            except Exception:
                pass
            self._fs_suppress_until = 0.0
            if self._fullscreen_ui_state is None:
                self._fullscreen_ui_state = {
                    "paned_pos": self.content_paned.get_position(),
                }
            if bool(getattr(self, "hide_playlist_mode", False)):
                try:
                    self._pure_video_saved_pos = self.get_position()
                    self._pure_video_saved_size = self.get_size()
                except Exception:
                    self._pure_video_saved_pos = None
                    self._pure_video_saved_size = None
            self._apply_fullscreen_ui_layout()
            self.fullscreen()
            self.is_fullscreen = True
            self._set_fullscreen_compositor_bypass(True)
            try:
                self._update_screensaver_inhibit()
            except Exception:
                pass
            self._cache_video_window_handle()
            self._nudge_video_redraw()
            self._reset_cursor_hide_timer()
        except Exception as e:
            print("Erreur entrée plein écran:", e, file=sys.stderr)

    def _restore_ui_after_fullscreen(self):
        self._set_fullscreen_compositor_bypass(False)

        if self._fullscreen_ui_state is None and not self.is_fullscreen:
            return
        try:
            self._fs_on_fullscreen_left()
        except Exception:
            pass
        self._fullscreen_ui_state = None
        self.is_fullscreen = False
        try:
            self._update_screensaver_inhibit()
        except Exception:
            pass
        try:
            compact = bool(getattr(self, "mini_player_mode", False)) or bool(
                getattr(self, "nano_player_mode", False)
            )
            if compact:
                try: self._apply_compact_player_mode()
                except Exception: pass
                self._show_cursor()
                self._hide_fs_controls(immediate=True, force=True)
                return
            playlist_only = bool(getattr(self, "playlist_only_mode", False))
            pure_video = bool(getattr(self, "hide_playlist_mode", False)) and not playlist_only
            for attr in ("top_bar_wrap", "top_bar"):
                w = getattr(self, attr, None)
                if w is not None:
                    try:
                        if playlist_only or pure_video:
                            w.hide()
                        else:
                            w.show()
                    except Exception: pass
            if playlist_only or pure_video:
                for attr in ("bottom_bar_wrap", "bottom_bar"):
                    w = getattr(self, attr, None)
                    if w is not None:
                        try: w.hide()
                        except Exception: pass
            else:
                try:
                    self._apply_metadata_panel_visibility()
                except Exception:
                    bar = getattr(self, "bottom_bar_wrap", None) or getattr(
                        app, "bottom_bar", None
                    )
                    if bar is not None:
                        if bool(getattr(self, "show_metadata_panel", True)):
                            bar.show()
                        else:
                            bar.hide()
            if hasattr(self, "playlist_box"):
                try:
                    if pure_video:
                        self.playlist_box.hide()
                    else:
                        self.playlist_box.show()
                except Exception: pass
            if self.current_is_video:
                if hasattr(self, "video_overlay"):
                    self.video_overlay.show()
                self.video_area.show()
                if pure_video:
                    try: self._apply_hide_playlist_mode()
                    except Exception: pass
                elif playlist_only:
                    try:
                        self._apply_playlist_only_mode()
                    except Exception:
                        self._apply_video_playlist_split()
                        GLib.idle_add(self._apply_video_playlist_split)
                else:
                    self._apply_video_playlist_split()
                    GLib.idle_add(self._apply_video_playlist_split)
                    try: self._apply_metadata_panel_visibility()
                    except Exception: pass
                    def _re_show_meta():
                        try: self._apply_metadata_panel_visibility()
                        except Exception: pass
                        return False
                    GLib.idle_add(_re_show_meta)
            elif getattr(self, "lyrics_mode", False) and getattr(
                app, "lyrics_enabled", False
            ):
                try:
                    self._refresh_lyrics_for_current()
                except Exception:
                    if hasattr(self, "video_overlay"):
                        self.video_overlay.show()
                    if self.video_area is not None:
                        self.video_area.show()
                        self.video_area.set_size_request(-1, -1 if pure_video else 120)
                        self.video_area.queue_draw()
                    if not pure_video:
                        try:
                            self._apply_video_playlist_split()
                            GLib.idle_add(self._apply_video_playlist_split)
                        except Exception: pass
                if pure_video:
                    try: self._apply_hide_playlist_mode()
                    except Exception: pass
                elif playlist_only:
                    try: self._apply_playlist_only_mode()
                    except Exception: pass
            else:
                self.show_video_area(False)
                if playlist_only:
                    try: self._apply_playlist_only_mode()
                    except Exception: pass
            if playlist_only:
                def _re_apply_po():
                    try:
                        if bool(getattr(self, "playlist_only_mode", False)):
                            self._apply_playlist_only_mode()
                    except Exception: pass
                    return False
                try: GLib.idle_add(_re_apply_po)
                except Exception: pass
            if pure_video:
                def _re_apply_pv():
                    try:
                        if bool(getattr(self, "hide_playlist_mode", False)):
                            self._apply_hide_playlist_mode()
                            self._apply_pure_video_window_geometry(force_base=True)
                            GLib.timeout_add(
                                int(FS_OSD_EXIT_SUPPRESS_MS) + 100,
                                self._fs_ensure_idle_osd,
                            )
                    except Exception: pass
                    return False
                try: GLib.idle_add(_re_apply_pv)
                except Exception: pass
            self._show_cursor()
            try:
                self._hide_fs_controls(immediate=True, force=True)
            except Exception:
                pass
            self._cache_video_window_handle()
            self._nudge_video_redraw()
            if self.video_area is not None:
                self.video_area.queue_draw()
        except Exception as e:
            print("Erreur restauration UI:", e, file=sys.stderr)
            self._show_cursor()

    def _playlist_min_height_for_rows(self, rows=6):
        s = getattr(self, "_ui_s", None)
        if s is not None:
            row_h = s(26)
            chrome = s(52)
        else:
            row_h = 26
            chrome = 52
        return rows * row_h + chrome

    def _apply_video_playlist_split(self):
        if (
            not (
                getattr(self, "current_is_video", False)
                or getattr(self, "lyrics_mode", False)
            )
            or self.is_fullscreen
        ):
            return False
        if self.content_paned is None: return False
        playlist_min = self._playlist_min_height_for_rows(6)
        try:
            if hasattr(self, "playlist_box") and self.playlist_box is not None:
                self.playlist_box.set_size_request(-1, playlist_min)
        except Exception: pass
        paned_h = self.content_paned.get_allocated_height()
        if paned_h <= 1:
            win_h = self.get_allocated_height() or 600
            paned_h = max(320, win_h - 160)
        video_pos = max(120, paned_h - playlist_min)
        video_pos = min(video_pos, max(120, int(paned_h * 0.68)))
        if paned_h - video_pos < playlist_min:
            video_pos = max(100, paned_h - playlist_min)
        try:
            self.video_area.set_size_request(-1, 120)
            self.content_paned.set_position(video_pos)
        except Exception: pass
        try: self._refresh_playlist_scroll_adjustments()
        except Exception: pass
        return False

    def _refresh_playlist_scroll_adjustments(self):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._refresh_playlist_scroll_adjustments(self)
        return None

    def _scroll_playlist_to_path(self, child_path):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._scroll_playlist_to_path(self, child_path)
        return None

    def _scroll_playlist_to_end(self):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._scroll_playlist_to_end(self)
        return None

    def toggle_lyrics(self, menuitem=None):
        if _HAS_LYRICS_MOD:
            return _lyricsmod.toggle_lyrics(self, menuitem)
        return None

    def _hide_lyrics_display(self):
        if _HAS_LYRICS_MOD:
            return _lyricsmod._hide_lyrics_display(self)
        return None

    def _refresh_lyrics_for_current(self):
        if _HAS_LYRICS_MOD:
            return _lyricsmod._refresh_lyrics_for_current(self)
        return None

    def _ensure_lyrics_visible(self, path):
        if _HAS_LYRICS_MOD:
            return _lyricsmod._ensure_lyrics_visible(self, path)
        return None

    def _update_lyrics_index(self, position_sec):
        if _HAS_LYRICS_MOD:
            return _lyricsmod._update_lyrics_index(self, position_sec)
        return None

    def _draw_lyrics(self, widget, cr):
        if _HAS_LYRICS_MOD:
            return _lyricsmod._draw_lyrics(self, widget, cr)
        return None

    def _cairo_draw_line(self, cr, text, x, y, max_width, size, color, weight):
        try:
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, weight)
            cr.set_font_size(size)
            cr.set_source_rgb(*color)
            te = cr.text_extents(text)
            draw = text
            if te.width > max_width and max_width > 20:
                while draw and cr.text_extents(draw + "…").width > max_width:
                    draw = draw[:-1]
                draw = draw + "…" if draw != text else text
                te = cr.text_extents(draw)
            tx = x + max(0, (max_width - te.width) / 2.0)
            cr.move_to(tx, y + size * 0.35)
            cr.show_text(draw)
        except Exception: pass

    def _cairo_center_text(self, cr, w, h, text, size, color):
        try:
            cr.select_font_face(
                "Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL
            )
            cr.set_font_size(size)
            cr.set_source_rgb(*color)
            te = cr.text_extents(text)
            cr.move_to((w - te.width) / 2.0, (h + te.height) / 2.0)
            cr.show_text(text)
        except Exception: pass

    def show_video_area(self, show=True):
        if show:
            self.lyrics_mode = False
            self.lyrics_data = None
            self.lyrics_current_index = -1
            self.current_is_video = True
            self._set_spectrum_active_for_media(True)
            try:
                self._apply_av_sync_compensation(True)
            except Exception:
                pass
            if self.is_fullscreen:
                self._apply_fullscreen_ui_layout()
                self._cache_video_window_handle()
                return
            if hasattr(self, "video_overlay"):
                self.video_overlay.show_all()
                self.video_overlay.show()
            self.video_area.show()
            if hasattr(self, "osd_label"):
                self.osd_label.hide()
            self._apply_video_playlist_split()
            GLib.idle_add(self._apply_video_playlist_split)
            try:
                while Gtk.events_pending():
                    Gtk.main_iteration_do(False)
            except Exception: pass
            self._cache_video_window_handle()
            self._apply_video_overlay_handle()
            try:
                if bool(getattr(self, "playlist_only_mode", False)):
                    for attr in ("top_bar_wrap", "top_bar", "bottom_bar_wrap", "bottom_bar"):
                        w = getattr(self, attr, None)
                        if w is not None:
                            try: w.hide()
                            except Exception: pass
            except Exception: pass
        else:
            try:
                self._hide_fs_controls(immediate=True, force=True)
            except Exception:
                pass
            if hasattr(self, "video_overlay"):
                self.video_overlay.hide()
            self.video_area.hide()
            self.video_area.set_size_request(-1, 0)
            try:
                if hasattr(self, "playlist_box") and self.playlist_box is not None:
                    self.playlist_box.set_size_request(-1, -1)
            except Exception: pass
            try: self.content_paned.set_position(0)
            except Exception: pass
            self.current_is_video = False
            self._set_spectrum_active_for_media(False)
            self._release_pause_pixbuf()
            if self.is_fullscreen:
                self.unfullscreen()
                self._restore_ui_after_fullscreen()
        try: self._update_colorimetry_menu_sensitivity()
        except Exception: pass
    def _disable_all_subtitles(self):
        if _HAS_SUBTITLES_MOD:
            try:
                return _st_disable_all_subtitles(self)
            except Exception as e:
                print("disable_all_subtitles:", e, file=sys.stderr)


    def set_subtitles_enabled(self, *args, **kwargs):
        if _HAS_SUBTITLES_MOD:
            try:
                return _st_set_subtitles_enabled(self, *args, **kwargs)
            except Exception as e:
                print("set_subtitles_enabled:", e, file=sys.stderr)


    def _clear_external_suburi(self):
        try:
            self.player.set_property("suburi", None)
        except Exception:
            try: self.player.set_property("suburi", "")
            except Exception: pass
        self._active_external_sub_path = None

    def _ensure_playbin_text_flag(self):
        try:
            flags = self.player.get_property("flags")
            TEXT = 1 << 2
            if not (flags & TEXT):
                self.player.set_property("flags", flags | TEXT)
        except Exception: pass

    def _select_playbin_external_text_track(self):
        try:
            n = int(self.player.get_property("n-text") or 0)
        except Exception:
            n = 0
        if n <= 0:
            try: self.player.set_property("current-text", 0)
            except Exception: pass
            return False
        target = n - 1
        try:
            self.player.set_property("current-text", target)
        except Exception:
            try: self.player.set_property("current-text", 0)
            except Exception: pass
        return False

    def _apply_external_suburi(self, path, restore_position=True):
        if _HAS_SUBS_TRACK_MOD:
            return _substrackmod._apply_external_suburi(self,path,restore_position)
        return None

    def _prepare_external_subtitles_for(self, path):
        if _HAS_SUBTITLES_MOD:
            try:
                return _st_prepare_external_subtitles_for(self, path)
            except Exception as e:
                print("prepare_external_subtitles:", e, file=sys.stderr)


    def _register_external_subtitle_tracks(self, *args, **kwargs):
        if _HAS_SUBTITLES_MOD:
            try:
                return _st_register_external_subtitle_tracks(self, *args, **kwargs)
            except Exception as e:
                print("register_external_subtitles:", e, file=sys.stderr)


    def _custom_text_sink_pad(self):
        """Pad d'entrée texte de l'overlay de sous-titres du pipeline custom."""
        overlay = getattr(self, "_custom_sub_overlay", None)
        if overlay is None:
            return None
        try:
            if getattr(self, "_custom_sub_overlay_is_text", True):
                return overlay.get_static_pad("text_sink")
            return overlay.get_static_pad("subtitle_sink")
        except Exception:
            return None

    def _unlink_custom_text_sink(self):
        if _HAS_SUBS_TRACK_MOD:
            return _substrackmod._unlink_custom_text_sink(self)
        return None

    def _link_external_subtitle_custom(self, path):
        if _HAS_SUBS_TRACK_MOD:
            return _substrackmod._link_external_subtitle_custom(self,path)
        return None

    def _maybe_attach_external_to_custom(self):
        try: self._register_external_subtitle_tracks()
        except Exception: pass
        return False

    def _discover_subtitle_languages(self, filepath):
        if _HAS_SUBTITLES_MOD:
            try:
                return _st_discover_subtitle_languages(self, filepath) or {}
            except Exception as e:
                print("discover_subtitle_languages:", e, file=sys.stderr)
        return {}


    def _discover_audio_track_labels(self, filepath):
        if _HAS_SUBTITLES_MOD:
            try:
                return _st_discover_audio_track_labels(self, filepath) or []
            except Exception as e:
                print("discover_audio_track_labels:", e, file=sys.stderr)
        return []


    def _get_discoverer(self):
        if GstPbutils is None:
            return None
        disc = getattr(self, "_discoverer", None)
        if disc is not None:
            return disc
        try:
            disc = GstPbutils.Discoverer.new(2 * Gst.SECOND)
            self._discoverer = disc
            return disc
        except Exception:
            self._discoverer = None
            return None

    def _discover_info(self, filepath):
        if _HAS_SUBS_TRACK_MOD:
            return _substrackmod._discover_info(self,filepath)
        return None

    def _probe_video_info(self, filepath):
        if _HAS_SUBS_TRACK_MOD:
            return _substrackmod._probe_video_info(self,filepath)
        return None

    def _normalize_lang_code(self, raw):
        if not raw: return None
        s = str(raw).strip()
        if not s or s.lower() in ("und", "unk", "unknown", ""): return None
        low = s.casefold()
        if len(s) <= 3 and s.isalpha():
            map3 = {
                "fre": "fr", "fra": "fr", "eng": "en", "ger": "de", "deu": "de",
                "spa": "es", "ita": "it", "por": "pt", "dut": "nl", "nld": "nl",
                "pol": "pl", "swe": "sv", "rus": "ru", "jpn": "ja", "chi": "zh",
                "zho": "zh", "kor": "ko", "ara": "ar", "hin": "hi", "tur": "tr",
            }
            if low in map3: return map3[low]
            return low[:2] if len(low) >= 2 else low
        names = {
            "french": "fr", "français": "fr", "francais": "fr",
            "english": "en", "anglais": "en",
            "german": "de", "deutsch": "de", "allemand": "de",
            "spanish": "es", "español": "es", "espanol": "es", "castellano": "es",
            "italian": "it", "italiano": "it",
            "portuguese": "pt", "portugais": "pt", "português": "pt",
            "dutch": "nl", "nederlands": "nl", "néerlandais": "nl",
            "polish": "pl", "polski": "pl", "polonais": "pl",
            "swedish": "sv", "svenska": "sv", "suédois": "sv",
            "russian": "ru", "русский": "ru", "russe": "ru",
            "japanese": "ja", "japonais": "ja",
            "chinese": "zh", "chinois": "zh",
        }
        if low in names: return names[low]
        if "-" in s or "_" in s: return self._normalize_lang_code(s.replace("_", "-").split("-")[0])
        return s[:8]

    def _delayed_subtitle_lang_probe(self, pad, track_index):
        try:
            lang = None
            try:
                event = pad.get_sticky_event(Gst.EventType.TAG, 0)
                if event is not None:
                    tags = event.parse_tag()
                    for tkey in (
                        Gst.TAG_LANGUAGE_CODE,
                        Gst.TAG_LANGUAGE_NAME,
                        Gst.TAG_TITLE,
                    ):
                        try:
                            ok, val = tags.get_string(tkey)
                            if ok and val:
                                if tkey == Gst.TAG_TITLE and len(str(val)) > 16: continue
                                lang = val
                                break
                        except Exception: pass
            except Exception: pass
            if not lang:
                try:
                    caps = pad.get_current_caps()
                    if caps is None:
                        caps = pad.query_caps(None)
                    if caps is not None and caps.get_size() > 0:
                        st = caps.get_structure(0)
                        for key in ("language", "language-code", "lang"):
                            if st.has_field(key):
                                ok, val = st.get_string(key)
                                if ok and val and val not in ("und", "unk", ""):
                                    lang = val
                                    break
                except Exception: pass
            if not lang:
                try:
                    sid = pad.get_stream_id()
                except Exception:
                    sid = None
                if sid:
                    lang = (getattr(self, "_custom_sub_lang_list", None) or {}).get(sid)
            if lang:
                short = self._normalize_lang_code(lang) or lang
                self._set_subtitle_track_label(track_index, short)
        except Exception: pass
        return False

    def _set_subtitle_track_label(self, track_index, lang):
        try:
            for t in self.subtitle_tracks or []:
                if (
                    isinstance(t, dict)
                    and t.get("kind") == "embedded"
                    and t.get("index") == track_index
                ):
                    t["label"] = lang
                    break
            pads = getattr(self, "_custom_subtitle_pads", None) or []
            if 0 <= track_index < len(pads):
                entry = pads[track_index]
                pad = entry[0]
                is_text = entry[2] if len(entry) > 2 else True
                self._custom_subtitle_pads[track_index] = (pad, lang, is_text)
        except Exception: pass
        return False

    def refresh_subtitle_tracks(self, *args, **kwargs):
        if _HAS_SUBTITLES_MOD:
            try:
                return _st_refresh_subtitle_tracks(self, *args, **kwargs)
            except Exception as e:
                print("refresh_subtitle_tracks:", e, file=sys.stderr)


    def _link_custom_subtitle_pad_now(self, pipe, pad, sidx, nice, sub_overlay):
        if _HAS_SUBS_TRACK_MOD:
            return _substrackmod._link_custom_subtitle_pad_now(self,pipe,pad,sidx,nice,sub_overlay)
        return None

    def _link_preferred_custom_subtitle_while_paused(self):
        pref = getattr(self, "_preferred_custom_sub_index", -1)
        if pref is None or pref < 0: return False
        if not getattr(self, "subtitles_enabled", True): return False
        pipe = getattr(self, "_custom_pipeline", None)
        overlay = getattr(self, "_custom_sub_overlay", None)
        pads = getattr(self, "_custom_subtitle_pads", None) or []
        if pipe is None or overlay is None or not pads: return False
        if pref >= len(pads): return False
        entry = pads[pref]
        pad = entry[0]
        nice = entry[1] if len(entry) > 1 else "Sub"
        is_text = entry[2] if len(entry) > 2 else True
        if not is_text: return False
        if getattr(self, "_custom_sub_linked", False):
            try: overlay.set_property("silent", False)
            except Exception: pass
            return True
        ok = self._link_custom_subtitle_pad_now(pipe, pad, pref, nice, overlay)
        if ok:
            try: overlay.set_property("silent", False)
            except Exception: pass
        return ok

    def _reconnect_custom_sub_queue_output(self):
        """Rebranche la sortie du queue de ST intégrés sur l'overlay (elle est
        débranchée quand on désactive les ST ou qu'on passe à un ST externe)."""
        queue = getattr(self, "_custom_sub_queue", None)
        text_sink = self._custom_text_sink_pad()
        if queue is None or text_sink is None:
            return False
        try:
            if text_sink.is_linked():
                return True
            qsrc = queue.get_static_pad("src")
            if qsrc is None:
                return False
            target = qsrc
            peer = qsrc.get_peer()
            if peer is not None:
                el = peer.get_parent_element()
                target = el.get_static_pad("src") if el is not None else None
            if target is None or target.is_linked():
                return False
            return target.link(text_sink) == Gst.PadLinkReturn.OK
        except Exception as e:
            print("reconnect sub queue:", e, file=sys.stderr)
            return False

    def _set_custom_subtitle_active(self, pad_index):
        if _HAS_SUBS_TRACK_MOD:
            return _substrackmod._set_custom_subtitle_active(self,pad_index)
        return None

    def _flush_pipeline_at_position(self, pipe=None, pos_seconds=None):
        if _HAS_SUBS_TRACK_MOD:
            return _substrackmod._flush_pipeline_at_position(self,pipe,pos_seconds)
        return None

    def _sub_flush_finished(self, gen, ok, elapsed):
        """Retour dans le thread GTK à la fin du seek de resynchro."""
        if getattr(self, "_sub_flush_busy_gen", -1) == gen:
            self._sub_flush_busy_gen = -1
        if elapsed > 1.0:
            print("Sous-titres : seek FLUSH terminé en %.1f s" % elapsed, file=sys.stderr)
        if gen != self._playback_generation or getattr(self, "_app_closing", False):
            self._sub_flush_again = False
            return False
        if not ok:
            print("Sous-titres : seek de resynchro refusé", file=sys.stderr)
        try:
            if getattr(self, "current_is_video", False):
                self._nudge_video_redraw()
        except Exception:
            pass
        if getattr(self, "_sub_flush_again", False):
            self._sub_flush_again = False
            self._flush_pipeline_at_position()
        return False

    def set_subtitle_track(self, *args, **kwargs):
        if _HAS_SUBTITLES_MOD:
            try:
                return _st_set_subtitle_track(self, *args, **kwargs)
            except Exception as e:
                print("set_subtitle_track:", e, file=sys.stderr)


    def _set_subtitle_track_impl(self, *args, **kwargs):
        if _HAS_SUBTITLES_MOD:
            try:
                return _st_set_subtitle_track_impl(self, *args, **kwargs)
            except Exception as e:
                print("set_subtitle_track_impl:", e, file=sys.stderr)


    def _deferred_refresh_subtitles(self):
        self.refresh_subtitle_tracks()
        return False

    def refresh_audio_tracks(self, *args, **kwargs):
        if _HAS_SUBTITLES_MOD:
            try:
                return _st_refresh_audio_tracks(self, *args, **kwargs)
            except Exception as e:
                print("refresh_audio_tracks:", e, file=sys.stderr)


    def set_audio_track(self, *args, **kwargs):
        if _HAS_SUBTITLES_MOD:
            try:
                return _st_set_audio_track(self, *args, **kwargs)
            except Exception as e:
                print("set_audio_track:", e, file=sys.stderr)


    def _custom_audio_entry(self, index):
        try:
            entry = self._custom_audio_pads[index]
        except Exception:
            return None, "", ""
        if not entry:
            return None, "", ""
        pad = entry[0]
        label = entry[1] if len(entry) > 1 else ""
        media = entry[2] if len(entry) > 2 else ""
        return pad, label, media

    def _custom_audio_media_family(self, media):
        m = (media or "").lower()
        if "eac3" in m or "e-ac-3" in m:
            return "eac3"
        if "ac3" in m:
            return "ac3"
        if "dts" in m:
            return "dts"
        if "truehd" in m or "mlp" in m:
            return "truehd"
        if "opus" in m:
            return "opus"
        if "vorbis" in m:
            return "vorbis"
        if "flac" in m:
            return "flac"
        if "mpeg" in m or "mp4a" in m or "aac" in m:
            return "aac"
        if "pcm" in m or "x-raw" in m:
            return "pcm"
        return m.split(",")[0].strip() if m else ""

    def _restart_custom_with_audio_index(self, index):
        """Reconstruit le pipeline custom en gardant position + audio + sous-titres."""
        path = getattr(self, "current_path", None)
        if not path:
            return
        pend = getattr(self, "_seek_pending_target", None)
        pos = float(pend if pend is not None else (getattr(self, "_last_known_position", 0.0) or 0.0))
        snap = None
        try:
            snap = self._resume_track_snapshot()
        except Exception:
            snap = None
        try:
            self._preferred_custom_audio_index = int(index)
        except Exception:
            self._preferred_custom_audio_index = index
        self._keep_preferred_audio_once = True
        try:
            self.play_file(path, resume=False)
        except Exception as e:
            self._keep_preferred_audio_once = False
            print("restart custom audio:", e, file=sys.stderr)
            return
        if isinstance(snap, dict) and not snap.get("sub_off", True):
            try:
                snap["audio"] = int(index)
                self._resume_store_pending_tracks(snap)
                self._resume_schedule_tracks()
            except Exception as e:
                print("restart custom audio subs:", e, file=sys.stderr)
        if pos > 1.0:
            try:
                self._resume_schedule_seek(pos)
            except Exception as e:
                print("restart custom audio seek:", e, file=sys.stderr)
    def _set_custom_audio_track(self, *args, **kwargs):
        if _HAS_SUBTITLES_MOD:
            try:
                return _st_set_custom_audio_track(self, *args, **kwargs)
            except Exception as e:
                print("set_custom_audio_track:", e, file=sys.stderr)


    def open_system_bluetooth(self, *args):
        if _HAS_TOOLS_MOD:
            return _toolsmod.open_system_bluetooth(self,*args)
        return None

    def capture_screenshot(self, *args):
        if _HAS_TOOLS_MOD:
            return _toolsmod.capture_screenshot(self,*args)
        return None

    def _should_use_custom_pipeline(self, path):
        if _HAS_PLAYER_MOD:
            try:
                return bool(_py_should_use_custom_pipeline(self, path))
            except Exception as e:
                print("should_use_custom_pipeline:", e, file=sys.stderr)
        return False


    def _mkv_probe_flags(self, path, size=512 * 1024):
        try:
            st = os.stat(path)
            key = (os.path.abspath(path), int(st.st_mtime), int(st.st_size))
        except Exception:
            key = None
        cache = getattr(self, "_mkv_probe_cache", None)
        if cache is None:
            self._mkv_probe_cache = {}
            cache = self._mkv_probe_cache
        if key is not None and key in cache: return cache[key]
        flags = {"ac3": False, "av1": False, "hevc": False}
        data = b""
        try:
            with open(path, "rb") as f:
                data = f.read(size)
            if data:
                flags["ac3"] = (b"A_EAC3" in data) or (b"A_EAC-3" in data)
                flags["av1"] = (
                    (b"V_AV1" in data)
                    or (b"V_AV01" in data)
                    or (b"av01" in data)
                )
        
                flags["hevc"] = (
                    (b"V_MPEGH/ISO/HEVC" in data)
                    or (b"V_MPEGI/ISO/HEVC" in data)
                    or (b"hvc1" in data)
                    or (b"hev1" in data)
                )
        except Exception: pass
        finally:
            data = None
        if key is not None:
            if not isinstance(cache, OrderedDict):
                try:
                    self._mkv_probe_cache = OrderedDict(cache)
                    cache = self._mkv_probe_cache
                except Exception:
                    pass
            cache[key] = flags
            try:
                cache.move_to_end(key)
            except Exception:
                pass
            while len(cache) > PROBE_CACHE_MAX:
                try:
                    cache.popitem(last=False)
                except Exception:
                    break
        return flags

    def _mkv_has_ac3_family_audio(self, path):
        try:
            return bool(self._mkv_probe_flags(path).get("ac3"))
        except Exception:
            return False

    def _mkv_has_av1_video(self, path):
        try:
            return bool(self._mkv_probe_flags(path).get("av1"))
        except Exception:
            return False

    def _active_pipeline(self):
        if _HAS_PLAYER_MOD:
            try:
                return _py_active_pipeline(self)
            except Exception as e:
                print("active_pipeline:", e, file=sys.stderr)
        if getattr(self, "_custom_pipeline", None) is not None:
            return self._custom_pipeline
        return self.player


    def _effective_perf_mode(self):
        if _HAS_PLAYER_MOD:
            try:
                return _py_effective_perf_mode(self)
            except Exception as e:
                print("effective_perf_mode:", e, file=sys.stderr)
        return getattr(self, "performance_mode", "hardware")


    def _detach_equalizer_for_custom(self):
        if _HAS_PLAYER_MOD:
            try:
                return _py_detach_equalizer_for_custom(self)
            except Exception as e:
                print("detach_equalizer:", e, file=sys.stderr)
        return None


    def _destroy_custom_pipeline(self):
        if _HAS_PLAYER_MOD:
            try:
                return _py_destroy_custom_pipeline(self)
            except Exception as e:
                print("destroy_custom_pipeline:", e, file=sys.stderr)


    def _attach_custom_bus(self, element):
        try:
            bus = element.get_bus()
            bus.add_signal_watch()
            hid1 = bus.connect("message", self.on_gstreamer_message)
            bus.enable_sync_message_emission()
            hid2 = bus.connect("sync-message::element", self.on_sync_message)
            self._custom_bus_handler_ids = [hid1, hid2]
        except Exception as e:
            print("attach bus:", e, file=sys.stderr)

    def _build_mkv_pipeline(self, filepath, force_software=False):
        if _HAS_PLAYER_MOD:
            try:
                return _py_build_mkv_pipeline(self, filepath, force_software)
            except Exception as e:
                print("build_mkv_pipeline:", e, file=sys.stderr)
                return None
        return None


    def _ensure_video_sink_geometry(self):
        if not getattr(self, "current_is_video", False): return
        try:
            if self.video_area is not None:
                alloc = self.video_area.get_allocation()
                if alloc.height < 8 or alloc.width < 8:
                    self.video_area.set_size_request(-1, max(180, alloc.height or 180))
                if not self.video_area.get_realized():
                    self.video_area.realize()
                self.video_area.show()
                for _ in range(6):
                    if not Gtk.events_pending(): break
                    Gtk.main_iteration_do(False)
        except Exception: pass
        try: self._cache_video_window_handle()
        except Exception: pass
    def _play_file_custom_mkv(self, path):
        if _HAS_PLAYER_MOD:
            try:
                return bool(_py_play_file_custom_mkv(self, path))
            except Exception as e:
                print("play_file_custom_mkv:", e, file=sys.stderr)
                try:
                    self._destroy_custom_pipeline()
                except Exception:
                    pass
                return False
        return False


    def _set_playback_volume(self, value):
        value = max(0.0, min(1.0, float(value)))
        try:
            gain = max(0.0, min(1.0, float(getattr(self, "_fade_gain", 1.0))))
        except Exception:
            gain = 1.0
        value = value * gain
        # Préampli via volume, plafonné à 1.0 (évite le clipping)
        try:
            pdb = float(getattr(self, "eq_preamp_db", 0.0) or 0.0)
        except Exception:
            pdb = 0.0
        if abs(pdb) > 0.01:
            try:
                value = value * float(
                    10.0 ** (max(-12.0, min(12.0, pdb)) / 20.0)
                )
            except Exception:
                pass
            value = max(0.0, min(1.0, value))
        if self._custom_volume is not None:
            try:
                boost = float(getattr(self, "_custom_volume_boost", 1.0) or 1.0)
                self._custom_volume.set_property(
                    "volume", min(3.5, value * boost)
                )
            except Exception:
                pass
        try:
            self.player.set_property("volume", value)
        except Exception:
            pass
    def play_file(self, filename, resume=True):
        try:
            if bool(getattr(self, "pure_spectrum_mode", False)):
                if not self._pure_spectrum_media_allowed(filename):
                    self.pure_spectrum_mode = False
                    try:
                        self.set_size_request(-1, -1)
                    except Exception:
                        pass
                    try:
                        self._apply_pure_spectrum_mode()
                    except Exception:
                        pass
                    try:
                        GLib.idle_add(self._restore_geometry_after_pure_spectrum)
                    except Exception:
                        pass
        except Exception:
            pass
        try: self._dbg_transport("play_file")
        except Exception: pass
        if not filename: return
        if bool(getattr(self, "playlist_only_mode", False)) and not bool(
            getattr(self, "hide_playlist_mode", False)
        ):
            try:
                self._hide_fs_controls(immediate=True, force=True)
            except Exception:
                pass
        fade_in = bool(getattr(self, "_fade_in_pending", False))
        self._fade_in_pending = False
        try: self._gapless_cancel()
        except Exception: pass
        if not fade_in:
            try: self._fade_cancel()
            except Exception: pass
        try:
            trim_memory(force=True, full=False)
        except Exception:
            pass
        start_at = 0.0
        self._resume_pending_pos = None
        if getattr(self, "_keep_preferred_audio_once", False):
            self._keep_preferred_audio_once = False
        else:
            self._preferred_custom_audio_index = -1
        self._preferred_custom_sub_index = -1
        self._preferred_ext_sub_path = None
        if (
            resume
            and bool(getattr(self, "resume_enabled", False))
            and not is_special_source(filename)
            and is_video_file(filename)
        ):
            try:
                saved = self._resume_lookup(filename)
            except Exception:
                saved = None
            if saved is not None and float(saved) >= RESUME_MIN_POS_S:
                try:
                    if self._resume_ask(filename, float(saved)):
                        start_at = float(saved)
                        self._resume_pending_pos = float(saved)
                        try:
                            rec = self._resume_lookup_record(filename)
                            self._resume_store_pending_tracks(rec)
                        except Exception:
                            self._resume_pending_tracks = None
                    else:
                        self._resume_clear(filename)
                        self._resume_pending_tracks = None
                except Exception as e:
                    print("resume offer:", e, file=sys.stderr)
        try:
            if (
                isinstance(filename, str)
                and not is_special_source(filename)
                and os.path.isfile(filename)
            ):
                filename = os.path.abspath(filename)
        except Exception:
            pass
        try:
            if getattr(self, "_recording", False):
                if filename != getattr(self, "current_path", None):
                    self._stop_recording(show_save_dialog=True)
        except Exception: pass
        try:
            if is_cdda(filename) or is_stream(filename) or is_dvd(filename) or is_bluray(filename):
                uri = filename
            else:
                uri = GLib.filename_to_uri(os.path.abspath(filename), None)
            try:
                if filename != getattr(self, "_hw_fallback_path", None):
                    self._hw_fallback_path = None
                    if getattr(self, "performance_mode", "hardware") == "hardware":
                        self._apply_decoder_performance_mode(force_software=False)
            except Exception: pass
            self._playback_generation += 1
            gen = self._playback_generation
            try: self._hide_fs_toasts()
            except Exception: pass
            self._destroy_custom_pipeline()
            try:
                self.player.set_state(Gst.State.NULL)
                self.player.get_state(100 * Gst.MSECOND)
            except Exception: pass
            try:
                bus = self.player.get_bus()
                if bus is not None:
                    while True:
                        msg = bus.pop_filtered(
                            Gst.MessageType.EOS | Gst.MessageType.ERROR
                        )
                        if msg is None: break
            except Exception: pass
            if gen != self._playback_generation: return
            try:
                if filename != getattr(self, "current_path", None):
                    self._resume_save_current(force=True)
            except Exception: pass
            self.current_path = filename
            self._refresh_playlist_current_style()
            self.current_duration = 0
            try: self._scrobble_on_track_start(filename)
            except Exception: pass
            self.current_is_cdda = is_cdda(filename)
            if getattr(self, "_need_playbin_rebind", False):
                self._need_playbin_rebind = False
                try:
                    self._video_sink_is_real = False
                    self._ensure_video_sink()
                except Exception: pass
                try: self.rebuild_audio_filter(force=True, restart=False)
                except Exception: pass
            try:
                _, _, _, _, meta_duration, _, _ = self.get_metadata(filename, load_cover=False)
                if meta_duration and float(meta_duration) > 0:
                    self.current_duration = float(meta_duration)
                    self.position_scale.set_range(0, self.current_duration)
                else:
                    self.position_scale.set_range(0, 1)
            except Exception:
                self.position_scale.set_range(0, 1)
            self.time_label.set_text(
                f"0:00 • {format_time(self.current_duration)}"
                if self.current_duration > 0 else "0:00 • 0:00"
            )
            self.icy_title = ""
            self.icy_artist = ""
            if is_stream(filename):
                self.current_radio_name = self.find_radio_name(filename)
                if not getattr(self, "current_tv_name", None):
                    self.current_tv_name = self.find_tv_name(filename)
            else:
                self.current_radio_name = None
                self.current_tv_name = None
            self.position_scale.set_value(0)
            self._last_known_position = 0.0
            self._pending_seek_delta = 0.0
            self._seek_in_progress = False
            self._seek_cancel_pending()
            self.reset_spectrum()
            self._clear_chapters()
            prefer_video = bool(getattr(self, "_prefer_video", False))
            is_known_radio = bool(
                is_stream(filename)
                and (
                    getattr(self, "current_radio_name", None)
                    or self.find_radio_name(filename)
                )
            )
            if not prefer_video and is_stream(filename) and not is_known_radio:
                if (
                    getattr(self, "current_tv_name", None)
                    or self.find_tv_name(filename)
                    or getattr(self, "bouquet_active", False)
                ):
                    prefer_video = True
            if prefer_video and is_stream(filename) and not getattr(self, "current_tv_name", None):
                try: self.current_tv_name = self.find_tv_name(filename)
                except Exception: pass
            if is_known_radio:
                prefer_video = False
            if (
                is_video_file(filename)
                or is_dvd(filename)
                or is_bluray(filename)
                or prefer_video
                or (getattr(self, "bouquet_active", False) and is_stream(filename) and not is_known_radio)
            ):
                self.lyrics_mode = False
                self.lyrics_data = None
                self.lyrics_current_index = -1
                self.show_video_area(True)
                self._current_video_dims = None
                self._current_video_hdr = False
                try:
                    info = self._probe_video_info(filename)
                    if info and info.get("width") and info.get("height"):
                        self._current_video_dims = (
                            int(info["width"]),
                            int(info["height"]),
                            int(info.get("par_n") or 1),
                            int(info.get("par_d") or 1),
                        )
                    self._current_video_hdr = bool(info and info.get("hdr"))
                except Exception:
                    pass
                if bool(getattr(self, "hide_playlist_mode", False)):
                    try: self._apply_pure_video_window_geometry()
                    except Exception: pass
                    try: self._schedule_pure_video_geometry(400)
                    except Exception: pass
                    try: self._schedule_pure_video_geometry(1200)
                    except Exception: pass
            else:
                if not (
                    getattr(self, "lyrics_enabled", False)
                    and is_pure_audio_file(filename)
                ):
                    self.lyrics_mode = False
                    self.lyrics_data = None
                    self.lyrics_current_index = -1
                    self.show_video_area(False)
                self._current_video_hdr = False
                self._current_video_dims = None
                if bool(getattr(self, "hide_playlist_mode", False)):
                    try:
                        self._pure_video_prev_playlist_only = False
                        self.set_hide_playlist_mode(False)
                    except Exception: pass
            self._prefer_video = False
            try:
                self._refresh_lyrics_for_current()
            except Exception as e:
                print("lyrics refresh:", e, file=sys.stderr)
            try:
                want_pitch = (
                    self.pitch is not None
                    and is_pure_audio_file(filename)
                    and (
                        abs(self.pitch_value - 1.0) > 0.001
                        or abs(self.tempo_value - 1.0) > 0.001
                    )
                )
                want_spectrum = not bool(getattr(self, "current_is_video", False))
                need_rebuild = (
                    want_pitch != bool(getattr(self, "_pitch_active", False))
                    or want_spectrum != bool(getattr(self, "_spectrum_in_filter", True))
                )
                if need_rebuild:
                    self.rebuild_audio_filter(force=True, restart=False)
            except Exception: pass
            try: self._update_pitch_menu_sensitivity()
            except Exception: pass
            try: self._update_colorimetry_menu_sensitivity()
            except Exception: pass
            try: self._rebuild_video_color_filter(restore_playback=False)
            except Exception: pass
            self.set_subtitles_enabled(self.subtitles_enabled)
            self.subtitle_tracks = []
            self.current_subtitle_index = -1
            self.audio_tracks = []
            self.current_audio_index = -1
            self._prepare_external_subtitles_for(filename)
            try: self._register_external_subtitle_tracks()
            except Exception: pass
            try: self.player.set_property("current-text", -1)
            except Exception: pass
            if self.current_is_video:
                try:
                    while Gtk.events_pending():
                        Gtk.main_iteration_do(False)
                except Exception: pass
                self._cache_video_window_handle()
                self._apply_video_overlay_handle()
            used_custom = False
            if self._should_use_custom_pipeline(filename):
                used_custom = self._play_file_custom_mkv(filename)
                if not used_custom:
                    if DEBUG_MYOSTOOX:
                        print(
                            "Myostoox: pipeline MKV custom échoué → playbin",
                            file=sys.stderr,
                        )
                else:
                    try:
                        self._maybe_attach_external_to_custom()
                    except Exception as e:
                        print("ext sub custom:", e, file=sys.stderr)
                    try: GLib.timeout_add(1200, self._maybe_attach_external_to_custom)
                    except Exception: pass
            if not used_custom:
                self._destroy_custom_pipeline()
                if getattr(self, "_need_playbin_rebind", False):
                    self._need_playbin_rebind = False
                    try:
                        self._video_sink_is_real = False
                        self._ensure_video_sink()
                    except Exception: pass
                    try: self.rebuild_audio_filter(force=True, restart=False)
                    except Exception: pass
                try:
                    audio_only = not bool(getattr(self, "current_is_video", False))
                    self._configure_playbin_buffers(audio_only=audio_only)
                except Exception: pass
                if getattr(self, "current_is_video", False):
                    try: self._ensure_video_sink()
                    except Exception: pass
                else:
                    try: self._release_real_video_sink()
                    except Exception: pass
                self.player.set_property("uri", uri)
                self.player.set_state(Gst.State.PLAYING)
            self.is_playing = True
            try: self._update_screensaver_inhibit()
            except Exception: pass
            try: self._update_record_button_state()
            except Exception: pass
            self.is_paused = False
            try: self._sync_spectrum_activity()
            except Exception: pass
            self.play_button.set_label("❚❚")
            self.status_label.set_text(self.tr("Lecture"))
            try: self._fs_sync_play_button()
            except Exception: pass
            try: self._fs_arm_autohide()
            except Exception: pass
            try: self._announce_track_change(filename)
            except Exception: pass
            try: self._push_recent_file(filename)
            except Exception: pass
            self.update_information(filename)
            try:
                rp = getattr(self, "_resume_pending_pos", None)
                if rp is not None and float(rp) >= RESUME_MIN_POS_S:
                    self._resume_schedule_seek(float(rp))
            except Exception as e:
                print("resume schedule play:", e, file=sys.stderr)
            try:
                if getattr(self, "_resume_pending_tracks", None):
                    self._resume_schedule_tracks()
            except Exception as e:
                print("resume tracks play:", e, file=sys.stderr)
            self.select_filename(filename)
            self._mpris_notify_playback()
            try:
                if getattr(self, "_lyrics_loaded_for", None) == filename:
                    GLib.timeout_add(500, self._ensure_lyrics_visible, filename)
                    GLib.timeout_add(1500, self._ensure_lyrics_visible, filename)
            except Exception: pass
            if fade_in:
                try: self._fade_in_start()
                except Exception as exc: print("fade in:", exc, file=sys.stderr)
            try:
                if bool(getattr(self, "playlist_only_mode", False)):
                    self._apply_playlist_only_mode()
            except Exception: pass
            try:
                if (
                    abs(float(getattr(self, "playback_rate", 1.0) or 1.0) - 1.0) > 0.001
                    and self._is_speed_media(filename)
                ):
                    GLib.timeout_add(350, self._apply_playback_rate_idle)
            except Exception: pass
        except Exception as e:
            try: self._fade_cancel()
            except Exception: pass
            self.status_label.set_text(self.tr("Erreur : ") + str(e))
            print("Erreur lecture:", e, file=sys.stderr)

    def seek_to_cdda_track(self, track_num):
        if _HAS_DISCS_MOD:
            return _discsmod.seek_to_cdda_track(self, track_num)
        return None

    def select_filename(self, filename):
        iterator = self.playlist.get_iter_first()
        while iterator is not None:
            if self.playlist[iterator][self.COL_PATH] == filename:
                child_path = self.playlist.get_path(iterator)
                filter_path = self.playlist_filter.convert_child_path_to_path(child_path)
                if filter_path is not None:
                    sel = self.tree.get_selection()
                    blocked = False
                    try:
                        sel.handler_block_by_func(self.selection_changed)
                        blocked = True
                    except Exception: pass
                    try:
                        sel.unselect_all()
                        sel.select_path(filter_path)
                        self.tree.set_cursor(filter_path)
                        self.tree.scroll_to_cell(filter_path, None, True, 0.5, 0)
                    finally:
                        if blocked:
                            try: sel.handler_unblock_by_func(self.selection_changed)
                            except Exception: pass
                return
            iterator = self.playlist.iter_next(iterator)

    def toggle_play(self, *args):
        if _HAS_TRANSPORT_MOD:
            return _transportmod.toggle_play(self,*args)
        return None

    def _note_pause_started(self):
        try:
            self._pause_started_mono = time.monotonic()
        except Exception:
            self._pause_started_mono = 0.0

    def _long_pause_elapsed(self):
        try:
            t0 = float(getattr(self, "_pause_started_mono", 0.0) or 0.0)
            if t0 <= 0:
                return 0.0
            return max(0.0, time.monotonic() - t0)
        except Exception:
            return 0.0

    def _video_sink_qos_defaults(self):
        soft = getattr(self, "performance_mode", "hardware") == "software"
        return True, (3 if soft else 2) * Gst.SECOND

    def _relax_video_sink_qos_for_resume(self):
        if _HAS_RESUME_MOD:
            return _resumemod._relax_video_sink_qos_for_resume(self)
        return None

    def _restore_video_sink_qos(self):
        self._qos_restore_tid = 0
        sink = getattr(self, "video_sink", None)
        if sink is None:
            return False
        qos, lateness = self._video_sink_qos_defaults()
        try:
            if sink.find_property("qos") is not None:
                sink.set_property("qos", qos)
        except Exception:
            pass
        try:
            if sink.find_property("max-lateness") is not None:
                sink.set_property("max-lateness", int(lateness))
        except Exception:
            pass
        return False

    def _resync_pipeline_after_long_pause(self):
        """Re-synchronise doucement horloge / décodeur après pause ≥ 15 s.

        Seek KEY_UNIT asynchrone à la position courante (sans bloquer le GTK).
        """
        try:
            pipe = self._active_pipeline()
        except Exception:
            pipe = None
        if pipe is None:
            return False
        pos_ns = None
        try:
            ok, pos = pipe.query_position(Gst.Format.TIME)
            if ok and pos is not None and pos >= 0:
                pos_ns = int(pos)
        except Exception:
            pos_ns = None
        if pos_ns is None:
            try:
                pos_ns = max(
                    0,
                    int(float(getattr(self, "_last_known_position", 0.0) or 0.0)
                        * Gst.SECOND),
                )
            except Exception:
                return False
        rate = 1.0
        try:
            rate = float(getattr(self, "playback_rate", 1.0) or 1.0)
            if rate <= 0:
                rate = 1.0
        except Exception:
            rate = 1.0
        try:
            pipe.seek(
                rate,
                Gst.Format.TIME,
                Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                Gst.SeekType.SET,
                pos_ns,
                Gst.SeekType.NONE,
                0,
            )
        except Exception as e:
            if DEBUG_MYOSTOOX:
                print("resync after pause:", e, file=sys.stderr)
        return False

    def toggle_pause(self, *args):
        try:
            self._dbg_transport("toggle_pause")
        except Exception:
            pass
        if self.current_path is None:
            return
        if self.is_playing and not self.is_paused:
            try:
                self._active_pipeline().set_state(Gst.State.PAUSED)
            except Exception as e:
                print("pause:", e, file=sys.stderr)
            self.is_paused = True
            try:
                self._note_pause_started()
            except Exception:
                pass
            try:
                self._sync_spectrum_activity()
            except Exception:
                pass
            try:
                self.play_button.set_label("▶")
            except Exception:
                pass
            try:
                self.status_label.set_text(self.tr("Pause"))
            except Exception:
                pass
            if self.current_is_video:
                try:
                    if self.video_sink is not None and isinstance(
                        self.video_sink, GstVideo.VideoOverlay
                    ):
                        GstVideo.VideoOverlay.expose(self.video_sink)
                except Exception:
                    pass
                try:
                    GLib.timeout_add(40, self._capture_pause_frame_and_redraw)
                except Exception:
                    pass
            try:
                self.show_osd("❚❚  " + self.tr("Pause"))
            except Exception:
                pass
            try:
                self._fs_sync_play_button()
            except Exception:
                pass
            try:
                self._mpris_notify_playback()
            except Exception:
                pass
            try:
                self._update_screensaver_inhibit()
            except Exception:
                pass
            return
        if self.is_paused:
            try:
                if (
                    getattr(self, "lyrics_enabled", False)
                    and is_pure_audio_file(self.current_path)
                    and not getattr(self, "lyrics_mode", False)
                ):
                    self._refresh_lyrics_for_current()
            except Exception as e:
                print("resume lyrics:", e, file=sys.stderr)
            needs_video = (
                is_video_file(self.current_path)
                or is_dvd(self.current_path)
                or is_bluray(self.current_path)
                or getattr(self, "_prefer_video", False)
                or getattr(self, "current_is_video", False)
                or (
                    is_stream(self.current_path)
                    and (
                        getattr(self, "current_tv_name", None)
                        or self.find_tv_name(self.current_path)
                        or getattr(self, "bouquet_active", False)
                    )
                )
            )
            if needs_video:
                try:
                    if self.is_fullscreen:
                        self._apply_fullscreen_ui_layout()
                        self._cache_video_window_handle()
                    else:
                        va = getattr(self, "video_area", None)
                        already = bool(
                            getattr(self, "current_is_video", False)
                            and va is not None
                            and va.get_mapped()
                        )
                        if not already:
                            self.show_video_area(True)
                except Exception as exc:
                    print("toggle_pause video area:", exc, file=sys.stderr)
                if getattr(self, "video_sink", None) is None:
                    try:
                        self._ensure_video_sink()
                        self._cache_video_window_handle()
                        self._apply_video_overlay_handle()
                    except Exception:
                        pass
            long_pause = False
            try:
                long_pause = self._long_pause_elapsed() >= 15.0
            except Exception:
                long_pause = False
            if long_pause and (
                getattr(self, "current_is_video", False)
                or is_video_file(getattr(self, "current_path", None) or "")
            ):
                try:
                    self._relax_video_sink_qos_for_resume()
                except Exception:
                    pass
            try:
                self._active_pipeline().set_state(Gst.State.PLAYING)
            except Exception as e:
                print("resume:", e, file=sys.stderr)
                try:
                    self.play_file(self.current_path, resume=False)
                except Exception:
                    pass
                return
            self.is_playing = True
            self.is_paused = False
            self._pause_pixbuf = None
            try:
                self._pause_started_mono = 0.0
            except Exception:
                pass
            if long_pause and getattr(self, "current_is_video", False):
                try:
                    GLib.timeout_add(80, self._resync_pipeline_after_long_pause)
                except Exception:
                    pass
                try:
                    GLib.timeout_add(120, self._nudge_video_redraw)
                    GLib.timeout_add(400, self._nudge_video_redraw)
                except Exception:
                    pass
            try:
                self._sync_spectrum_activity()
            except Exception:
                pass
            try:
                self.play_button.set_label("❚❚")
            except Exception:
                pass
            try:
                self.status_label.set_text(self.tr("Lecture"))
            except Exception:
                pass
            try:
                self._hide_fs_toasts()
            except Exception:
                pass
            if self.current_is_video:
                try:
                    self._nudge_video_redraw()
                except Exception:
                    pass
            try:
                rate = float(getattr(self, "playback_rate", 1.0) or 1.0)
                if abs(rate - 1.0) > 0.001 and self._is_speed_media():
                    GLib.timeout_add(150, self._apply_playback_rate_idle)
            except Exception:
                pass
            try:
                self.show_osd("▶  " + self.tr("Lecture"))
            except Exception:
                pass
            try:
                self._fs_sync_play_button()
            except Exception:
                pass
            try:
                self._mpris_notify_playback()
            except Exception:
                pass
            try:
                self._update_screensaver_inhibit()
            except Exception:
                pass
            return
        try:
            self.play_file(self.current_path, resume=False)
        except Exception as e:
            print("toggle_pause start:", e, file=sys.stderr)

    def stop(self, *args):
        try: self._dbg_transport("stop")
        except Exception: pass
        try:
            self._resume_save_current(force=True)
        except Exception:
            pass
        try:
            self._apply_av_sync_compensation(False)
        except Exception:
            pass
        self._resume_pending_pos = None
        self._resume_pending_tracks = None
        self._fade_in_pending = False
        try: self._gapless_cancel()
        except Exception: pass
        try: self._fade_cancel()
        except Exception: pass
        self._playback_generation += 1
        self._cancel_seek_release_timeout()
        self._seek_in_progress = False
        self._pending_seek_delta = 0.0
        self._seek_cancel_pending()
        self._last_known_position = 0.0
        try:
            if getattr(self, "_recording", False):
                self._stop_recording(show_save_dialog=True)
        except Exception: pass
        self._destroy_custom_pipeline()
        try: self.player.set_state(Gst.State.NULL)
        except Exception: pass
        self.is_playing = False
        try:
            self._pl_countdown_key = None
        except Exception:
            pass
        self.is_paused = False
        self._pause_pixbuf = None
        try: self._sync_spectrum_activity()
        except Exception: pass
        try:
            n = len(getattr(self, "spectrum_values", []) or [])
            if n:
                self.spectrum_values = [0.0] * n
                self.spectrum_targets = [0.0] * n
                self.spectrum_peaks = [0.0] * n
        except Exception: pass
        try: self._refresh_playlist_current_style()
        except Exception: pass
        self.current_is_cdda = False
        self.icy_title = ""
        self.icy_artist = ""
        self.current_radio_name = None
        self.current_tv_name = None
        self.subtitle_tracks = []
        self.current_subtitle_index = -1
        self._preferred_custom_sub_index = -1
        self._preferred_custom_audio_index = -1
        self._preferred_ext_sub_path = None
        self.external_subtitles = []
        self._active_external_sub_path = None
        self._clear_chapters()
        try: self.player.set_property("suburi", None)
        except Exception: pass
        self.play_button.set_label("▶")
        try: self.position_scale.set_value(0)
        except Exception: pass
        self.time_label.set_text(
            "0:00 • " + format_time(self.current_duration)
        )
        self.status_label.set_text(self.tr("Arrêt"))
        self.reset_spectrum()
        self.lyrics_mode = False
        self.lyrics_data = None
        self.lyrics_current_index = -1
        try: self._inhibit_screensaver(False)
        except Exception: pass
        if bool(getattr(self, "hide_playlist_mode", False)):
            path = getattr(self, "current_path", None)
            keep = False
            try:
                if path and (
                    is_video_file(path) or is_dvd(path) or is_bluray(path)
                ):
                    keep = True
            except Exception:
                keep = False
            self.current_is_video = bool(keep)
            try:
                if hasattr(self, "video_overlay") and self.video_overlay is not None:
                    self.video_overlay.show()
                if getattr(self, "video_area", None) is not None:
                    self.video_area.show()
                    self.video_area.set_size_request(-1, -1)
                    self.video_area.queue_draw()
            except Exception:
                pass
            try:
                self._apply_hide_playlist_mode()
            except Exception:
                pass
            try:
                GLib.idle_add(self._fs_ensure_idle_osd)
                GLib.timeout_add(250, self._fs_ensure_idle_osd)
            except Exception:
                pass
        elif bool(getattr(self, "playlist_only_mode", False)):
            try:
                self.current_is_video = False
            except Exception:
                pass
            try:
                self.show_video_area(False)
            except Exception:
                pass
            try:
                self._apply_playlist_only_mode()
            except Exception:
                pass
            try:
                self._hide_fs_controls(immediate=True, force=True)
            except Exception:
                pass
        else:
            try:
                self.current_is_video = False
            except Exception:
                pass
            self.show_video_area(False)
        try: self._update_pitch_menu_sensitivity()
        except Exception: pass
        try: self._update_colorimetry_menu_sensitivity()
        except Exception: pass
        try: self._update_record_button_state()
        except Exception: pass
        try:
            self._fs_sync_play_button()
        except Exception:
            pass
        self._mpris_notify_playback()
        try: GLib.idle_add(lambda: (trim_memory(force=True, full=True), False)[1])
        except Exception: pass
    def get_paths(self):
        if _HAS_PLAYLIST_VIEW_MOD:
            try:
                return _plviewmod.get_paths(self)
            except Exception:
                pass
        # Fallback (logique de la version qui fonctionnait)
        paths = []
        try:
            iterator = self.playlist.get_iter_first()
            while iterator is not None:
                paths.append(self.playlist[iterator][self.COL_PATH])
                iterator = self.playlist.iter_next(iterator)
        except Exception:
            pass
        return paths

    def next(self, *args, auto=False):
        if _HAS_TRANSPORT_MOD:
            return _transportmod.next(self, *args, auto=auto)
        return None

    def previous(self, *args):
        if _HAS_TRANSPORT_MOD:
            return _transportmod.previous(self,*args)
        return None

    def toggle_shuffle(self, button):
        self.shuffle_mode = not self.shuffle_mode
        self.shuffle_queue = []
        if self.shuffle_mode:
            paths = self.get_paths()
            if self.current_path in paths:
                self.shuffle_queue = [
                    path for path in paths
                    if path != self.current_path
                ]
                random.shuffle(self.shuffle_queue)
            button.get_style_context().add_class("active")
            button.set_tooltip_text(self.tr("Lecture aléatoire activée"))
            self.status_label.set_text(self.tr("Lecture aléatoire activée"))
        else:
            button.get_style_context().remove_class("active")
            button.set_tooltip_text(self.tr("Lecture aléatoire"))
            self.status_label.set_text(self.tr("Lecture aléatoire désactivée"))

    def _selected_playlist_path(self):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._selected_playlist_path(self)
        return None

    def _sync_repeat_ui(self):
        """Met à jour le bouton lecteur selon le mode de répétition."""
        btn = getattr(self, "repeat_button", None)
        if btn is None:
            return
        try:
            ctx = btn.get_style_context()
            if self.repeat_track_path is not None:
                ctx.add_class("active")
                btn.set_tooltip_text(self.tr("Répéter morceau"))
            elif self.repeat_mode:
                ctx.add_class("active")
                btn.set_tooltip_text(self.tr("Répéter playlist"))
            else:
                ctx.remove_class("active")
                btn.set_tooltip_text(self.tr("Répéter la playlist"))
        except Exception:
            pass
        try:
            self._mpris_properties_changed(
                {
                    "LoopStatus": GLib.Variant(
                        "s",
                        "Track"
                        if self.repeat_track_path
                        else ("Playlist" if self.repeat_mode else "None"),
                    )
                }
            )
        except Exception:
            pass

    def set_repeat_track_mode(self, enabled, path=None):
        """Active/désactive la répétition d'un morceau (exclut la playlist)."""
        enabled = bool(enabled)
        if enabled:
            p = path or getattr(self, "current_path", None) or self._selected_playlist_path()
            if not p:
                return
            # Toujours stocker un chemin qui existe dans la playlist
            try:
                paths = self.get_paths() or []
                def _norm(x):
                    if not isinstance(x, str): return x
                    if x.startswith(("http://", "https://", "cdda://", "dvd://", "bluray://")): return x
                    try: return os.path.abspath(x)
                    except Exception: return x
                pn = _norm(p)
                matched = None
                for cand in paths:
                    if cand == p or _norm(cand) == pn:
                        matched = cand
                        break
                if matched is not None:
                    p = matched
                elif paths and getattr(self, "current_path", None):
                    # dernier recours : le morceau courant s'il est dans la liste
                    cur = self.current_path
                    cn = _norm(cur)
                    for cand in paths:
                        if cand == cur or _norm(cand) == cn:
                            p = cand
                            break
            except Exception:
                pass
            self.repeat_track_path = p
            self.repeat_mode = False
            try:
                self.status_label.set_text(self.tr("Répétition du morceau sélectionné"))
            except Exception:
                pass
        else:
            self.repeat_track_path = None
            try:
                self.status_label.set_text(self.tr("Répétition désactivée"))
            except Exception:
                pass
        self._sync_repeat_ui()

    def set_repeat_playlist_mode(self, enabled):
        """Active/désactive la répétition de la playlist (exclut le morceau)."""
        enabled = bool(enabled)
        if enabled:
            self.repeat_mode = True
            self.repeat_track_path = None
            try:
                self.status_label.set_text(self.tr("Répétition de la playlist"))
            except Exception:
                pass
        else:
            self.repeat_mode = False
            try:
                self.status_label.set_text(self.tr("Répétition désactivée"))
            except Exception:
                pass
        self._sync_repeat_ui()

    def toggle_repeat(self, button):
        """Cycle du bouton barre : Off → Répéter morceau (courant) → Répéter playlist → Off."""
        cur = getattr(self, "current_path", None)
        if self.repeat_track_path is not None:
            # Morceau → Playlist
            self.set_repeat_track_mode(False)
            self.set_repeat_playlist_mode(True)
            return
        if self.repeat_mode:
            # Playlist → Off
            self.set_repeat_playlist_mode(False)
            return
        # Off → Morceau (toujours le fichier actuellement en lecture)
        p = cur
        if p is not None:
            self.set_repeat_track_mode(True, p)
        else:
            self.set_repeat_playlist_mode(True)

    def _active_playlist_tree(self):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._active_playlist_tree(self)
        return None

    def move_playlist_selection(self, direction):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.move_playlist_selection(self, direction)
        return None

    _SUB_ERROR_KEYS = (
        "subparse", "ssaparse",
        "mkv-ext-sub", "mkv-subparse", "mkv-ssaparse", "mkv-squeue",
    )

    def _is_subtitle_error_source(self, src):
        """True si l'erreur vient d'un parseur / d'une branche de sous-titres
        (et pas du décodage vidéo ou audio)."""
        obj = src
        for depth in range(6):
            if obj is None: break
            try: name = (obj.get_name() or "").lower()
            except Exception: name = ""
            if "suburi" in name:
                return True
            if depth == 0:
                try:
                    fac = obj.get_factory()
                    fname = (fac.get_name() if fac is not None else "").lower()
                except Exception:
                    fname = ""
                for key in self._SUB_ERROR_KEYS:
                    if key in name or key == fname:
                        return True
            try: obj = obj.get_parent()
            except Exception: break
        return False

    def _handle_subtitle_error(self, error, debug=None):
        print("Sous-titres (erreur non fatale) :", error, file=sys.stderr)
        if debug:
            print("Sous-titres debug:", debug, file=sys.stderr)
        if getattr(self, "_sub_recover_pending", False):
            return
        self._sub_recover_pending = True
        GLib.idle_add(self._recover_after_subtitle_error, self._playback_generation)

    def _recover_after_subtitle_error(self, gen):
        self._sub_recover_pending = False
        if gen != self._playback_generation or getattr(self, "_app_closing", False):
            return False
        try:
            if self._custom_pipeline is not None:
                self._unlink_custom_text_sink()
                self._active_external_sub_path = None
                ov = getattr(self, "_custom_sub_overlay", None)
                if ov is not None:
                    try: ov.set_property("silent", True)
                    except Exception: pass
                self._custom_subtitle_index = -1
            else:
                self._recover_playbin_without_subtitles()
            self.current_subtitle_index = -1
            self.status_label.set_text(self.tr("Sous-titre illisible"))
        except Exception as exc:
            print("recover subtitle error:", exc, file=sys.stderr)
        return False

    def _recover_playbin_without_subtitles(self):
        """Relance playbin au même endroit, sans sous-titre externe."""
        path = getattr(self, "current_path", None)
        if not path: return
        pos = float(getattr(self, "_last_known_position", 0.0) or 0.0)
        was_paused = bool(self.is_paused)
        self.player.set_state(Gst.State.READY)
        self.player.get_state(int(2 * Gst.SECOND))
        self._clear_external_suburi()
        try: self.player.set_property("current-text", -1)
        except Exception: pass
        self.player.set_property("uri", path_to_uri(path))
        self.player.set_state(Gst.State.PAUSED)
        self.player.get_state(int(3 * Gst.SECOND))
        if pos > 0.5:
            try:
                self.player.seek_simple(
                    Gst.Format.TIME,
                    Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                    int(pos * Gst.SECOND),
                )
            except Exception: pass
        self.is_playing = True
        if was_paused:
            self.is_paused = True
            try: self.play_button.set_label("▶")
            except Exception: pass
        else:
            self.player.set_state(Gst.State.PLAYING)
            self.is_paused = False
            try: self.play_button.set_label("❚❚")
            except Exception: pass
            try:
                if (
                    abs(float(getattr(self, "playback_rate", 1.0) or 1.0) - 1.0) > 0.001
                    and self._is_speed_media(path)
                ):
                    GLib.timeout_add(350, self._apply_playback_rate_idle)
            except Exception: pass

    def _replay_keeping_state(self, path):
        """Relance path (replis HW→SW / HDR) sans perdre position, audio, ST."""
        pend = getattr(self, "_seek_pending_target", None)
        pos = float(pend if pend is not None else (self._last_known_position or 0.0))
        snap = None
        try:
            snap = self._resume_track_snapshot()
        except Exception:
            snap = None
        audio = -1
        if isinstance(snap, dict):
            try:
                audio = int(snap.get("audio", -1))
            except Exception:
                audio = -1
        if audio >= 0:
            self._preferred_custom_audio_index = audio
            self._keep_preferred_audio_once = True
        try:
            self.play_file(path, resume=False)
        except Exception:
            self._keep_preferred_audio_once = False
            raise
        if getattr(self, "current_path", None) != path:
            return
        if isinstance(snap, dict) and not snap.get("sub_off", True):
            try:
                self._resume_store_pending_tracks(snap)
                self._resume_schedule_tracks()
            except Exception as e:
                print("replay tracks:", e, file=sys.stderr)
        if pos > 1.0:
            try:
                self._resume_schedule_seek(pos)
            except Exception as e:
                print("replay seek:", e, file=sys.stderr)

    def on_gstreamer_message(self, bus, message):
        if message.type == Gst.MessageType.EOS:
            if not getattr(self, "is_playing", False):
                return
            try:
                active = self._active_pipeline()
                src = message.src
                if active is None or src is None: return
                if src != active:
                    try:
                        parent = src
                        belongs = False
                        for _ in range(12):
                            if parent is None: break
                            if parent == active:
                                belongs = True
                                break
                            parent = parent.get_parent()
                        if not belongs: return
                    except Exception:
                        return
            except Exception: pass
            if getattr(self, "sleep_end_of_track", False):
                self.sleep_end_of_track = False
                try:
                    self.stop()
                except Exception: pass
                try: self.status_label.set_text(self.tr("Minuteur : arrêt"))
                except Exception: pass
                return
            try:
                self._resume_clear(getattr(self, "current_path", None))
            except Exception:
                pass
            self._auto_next_with_fade()
            return
        if message.type == Gst.MessageType.TOC:
            try:
                toc, _updated = message.parse_toc()
                self._ingest_toc(toc)
            except Exception: pass
            return
        if message.type == Gst.MessageType.STATE_CHANGED:
            try:
                if message.src == self._active_pipeline():
                    _old, new_state, _pending = message.parse_state_changed()
                    if new_state == Gst.State.PLAYING:
                        self._probe_video_size_for_colorimetry()
            except Exception: pass
        if message.type == Gst.MessageType.ERROR:
            error, debug = message.parse_error()
            if getattr(self, "_app_closing", False):
                return
            if not getattr(self, "is_playing", False):
                return
            try:
                if self._is_subtitle_error_source(message.src):
                    self._handle_subtitle_error(error, debug)
                    return
            except Exception as exc:
                print("subtitle error check:", exc, file=sys.stderr)
            print("GStreamer :", error, file=sys.stderr)
            if debug:
                print("GStreamer debug:", debug, file=sys.stderr)
            path = getattr(self, "current_path", None)
            if not path and not getattr(self, "is_playing", False):
                return
            if (
                path
                and getattr(self, "_hdr_tonemap_active", False)
                and getattr(self, "current_is_video", False)
                and getattr(self, "_hdr_off_path", None) != path
            ):
                self._hdr_off_path = path
                print(
                    "Myostoox: échec avec tone mapping HDR → relance sans",
                    file=sys.stderr,
                )
                try:
                    self.status_label.set_text(
                        self.tr("Repli sans tone mapping HDR…")
                    )
                except Exception:
                    pass
                def _retry_no_hdr(p=path):
                    if (
                        not getattr(self, "is_playing", False)
                        or getattr(self, "current_path", None) != p
                    ):
                        return False
                    try:
                        self._replay_keeping_state(p)
                    except Exception as e:
                        print("hdr fallback play:", e, file=sys.stderr)
                    return False
                GLib.idle_add(_retry_no_hdr)
                return
            can_fallback = (
                getattr(self, "performance_mode", "hardware") == "hardware"
                and path
                and getattr(self, "_hw_fallback_path", None) != path
                and (
                    getattr(self, "current_is_video", False)
                    or is_video_file(path)
                    or is_dvd(path)
                    or is_bluray(path)
                )
            )
            if can_fallback:
                self._hw_fallback_path = path
                print(
                    "Myostoox: échec décodage matériel → repli logiciel",
                    file=sys.stderr,
                )
                try:
                    self.status_label.set_text(
                        self.tr("Repli logiciel…")
                    )
                except Exception: pass
                try:
                    self._apply_decoder_performance_mode(force_software=True)
                except Exception as e:
                    print("fallback ranks:", e, file=sys.stderr)
                def _retry_soft(p=path):
                    if not getattr(self, "is_playing", False) or getattr(self, "current_path", None) != p:
                        return False
                    try:
                        self._replay_keeping_state(p)
                    except Exception as e:
                        print("fallback play:", e, file=sys.stderr)
                    return False
                GLib.idle_add(_retry_soft)
                return
            self.status_label.set_text(self.tr("Erreur : ") + str(error))
            self.is_playing = False
            self.is_paused = False
            self.play_button.set_label("▶")
            self.reset_spectrum()
            try:
                self._pl_countdown_key = None
                self._refresh_playlist_current_style()
            except Exception:
                pass
            self._refresh_playlist_current_style()
            return
        if message.type == Gst.MessageType.ASYNC_DONE:
            self._try_update_duration()
            if self._seek_in_progress:
                self._seek_in_progress = False
                self._cancel_seek_release_timeout()
                try:
                    ok, pos = self.player.query_position(Gst.Format.TIME)
                    if ok and pos >= 0:
                        self._last_known_position = pos / Gst.SECOND
                except Exception: pass
                if self.current_is_video:
                    self._nudge_video_redraw()
                if abs(self._pending_seek_delta) >= 0.001:
                    GLib.idle_add(self._apply_pending_seek_delta)
            return
        if message.type == Gst.MessageType.DURATION_CHANGED:
            self._try_update_duration()
            return
        if message.type == Gst.MessageType.STATE_CHANGED:
            if message.src == self.player:
                _, new_state, _ = message.parse_state_changed()
                if new_state in (Gst.State.PAUSED, Gst.State.PLAYING):
                    self._try_update_duration()
                if new_state == Gst.State.PAUSED and self.current_is_video:
                    gen = self._playback_generation
                    def _refresh_tracks(generation=gen):
                        if generation != self._playback_generation: return False
                        self.refresh_subtitle_tracks()
                        self.refresh_audio_tracks()
                        return False
                    GLib.idle_add(_refresh_tracks)
                if new_state == Gst.State.PLAYING and self.current_is_video:
                    self._nudge_video_redraw()
            return
        if message.type == Gst.MessageType.TAG:
            taglist = message.parse_tag()
            if taglist:
                ok, title = taglist.get_string(Gst.TAG_TITLE)
                if ok and title:
                    self.icy_title = title.strip()
                ok, artist = taglist.get_string(Gst.TAG_ARTIST)
                if ok and artist:
                    self.icy_artist = artist.strip()
                if self.current_path and is_stream(self.current_path):
                    self.update_information(self.current_path)
                try:
                    if hasattr(Gst, "TAG_VIDEO_WIDTH"):
                        ok_w, vw = taglist.get_uint(Gst.TAG_VIDEO_WIDTH)
                    else:
                        ok_w, vw = False, 0
                except Exception:
                    ok_w, vw = False, 0
                try:
                    if hasattr(Gst, "TAG_VIDEO_HEIGHT"):
                        ok_h, vh = taglist.get_uint(Gst.TAG_VIDEO_HEIGHT)
                    else:
                        ok_h, vh = False, 0
                except Exception:
                    ok_h, vh = False, 0
                if not ok_w:
                    try:
                        ok_w, vw = taglist.get_int("video-width")
                    except Exception:
                        ok_w = False
                if not ok_h:
                    try:
                        ok_h, vh = taglist.get_int("video-height")
                    except Exception:
                        ok_h = False
                if ok_w or ok_h:
                    try:
                        self._maybe_disable_colorimetry_for_4k(
                            vw if ok_w else 0, vh if ok_h else 0
                        )
                    except Exception: pass
            return
        if message.type != Gst.MessageType.ELEMENT: return
        structure = message.get_structure()
        if structure is None: return
        if structure.get_name() != "spectrum": return
        self.process_spectrum(structure)

    def update_position(self):
        if _HAS_STATUS_MOD:
            return _statusmod.update_position(self)
        return None

    def seek_press(self, widget, event):
        if event.button == 1:
            self.user_seeking = True
            self._seek_user_moved = False
            try:
                self._seek_press_value = float(widget.get_value())
            except Exception:
                self._seek_press_value = None
        return False

    def seek_release(self, widget, event):
        if event.button == 1:
            was_seeking = self.user_seeking
            moved = bool(getattr(self, "_seek_user_moved", False))
            press_value = getattr(self, "_seek_press_value", None)
            self.user_seeking = False
            self._seek_user_moved = False
            self._seek_press_value = None
            if not was_seeking: return False
            try:
                value = float(widget.get_value())
                changed = moved or (
                    press_value is not None and abs(value - press_value) > 0.05
                )
                has_duration = float(self.current_duration or 0) > 0
                if changed and has_duration:
                    self.seek_to(value)
            except Exception as e:
                print("seek_release:", e, file=sys.stderr)
            try: self._sync_fs_transport_ui()
            except Exception: pass
        return False

    def seek_value_changed(self, scale):
        if self._updating_position_scale: return
        value = scale.get_value()
        if self.user_seeking:
            self._seek_user_moved = True
            txt = f"{format_time(value)} • {format_time(self.current_duration)}"
            try: self.time_label.set_text(txt)
            except Exception: pass
            try:
                if getattr(self, "fs_time_label", None) is not None:
                    self.fs_time_label.set_text(txt)
            except Exception: pass
            try:
                if scale is getattr(self, "fs_scale", None):
                    self._updating_position_scale = True
                    try:
                        self.position_scale.set_value(value)
                    finally:
                        self._updating_position_scale = False
            except Exception: pass

    def _cancel_seek_release_timeout(self):
        tid = getattr(self, "_seek_release_timeout_id", 0) or 0
        if tid:
            try: GLib.source_remove(tid)
            except Exception: pass
            self._seek_release_timeout_id = 0

    def seek_to(self, seconds, accurate=False):
        try:
            if not self.current_path: return False
            self._seek_cancel_pending()
            self._seek_serial = int(getattr(self, "_seek_serial", 0) or 0) + 1
            self._try_update_duration()
            target = max(0.0, float(seconds))
            if self.current_duration > 0:
                target = min(target, self.current_duration)
            flags = (
                Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE
                if accurate
                else Gst.SeekFlags.FLUSH
                | Gst.SeekFlags.KEY_UNIT
                | Gst.SeekFlags.SNAP_NEAREST
            )
            self._cancel_seek_release_timeout()
            self._seek_in_progress = True
            pipe = self._active_pipeline()
            ns = int(target * Gst.SECOND)
            success = False
            if self._custom_pipeline is not None:
                flags_c = Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE
                was_playing = self.is_playing and not self.is_paused
                try:
                    pipe.set_state(Gst.State.PAUSED)
                    pipe.get_state(int(600 * Gst.MSECOND))
                    success = bool(self._seek_with_rate(pipe, flags_c, ns))
                    if not success:
                        success = bool(
                            self._seek_with_rate(
                                pipe,
                                Gst.SeekFlags.FLUSH
                                | Gst.SeekFlags.KEY_UNIT
                                | Gst.SeekFlags.SNAP_NEAREST,
                                ns,
                            )
                        )
                    pipe.get_state(int(600 * Gst.MSECOND))
                    if was_playing:
                        pipe.set_state(Gst.State.PLAYING)
                except Exception as e:
                    print("seek custom:", e, file=sys.stderr)
                    success = False
                    try:
                        if was_playing:
                            pipe.set_state(Gst.State.PLAYING)
                    except Exception: pass
            else:
                try:
                    success = bool(self._seek_with_rate(pipe, flags, ns))
                except Exception:
                    success = False
            if not success:
                self._seek_in_progress = False
                return False
            self._last_known_position = target
            _now_m = time.monotonic()
            self._seek_guard = (target, _now_m + SEEK_GUARD_S, _now_m)
            try:
                self._playlist_countdown_tick()
            except Exception: pass
            try:
                q = getattr(self, "_spectrum_delay_queue", None)
                if q is not None:
                    q.clear()
            except Exception: pass
            self._updating_position_scale = True
            try:
                if self.current_duration > 0:
                    self.position_scale.set_value(target)
            finally:
                self._updating_position_scale = False
            self.time_label.set_text(
                f"{format_time(target)} • {format_time(self.current_duration)}"
            )
            self._sync_fs_transport_ui()
            gen = self._playback_generation
            def _release_seek_lock(generation=gen):
                self._seek_release_timeout_id = 0
                if generation != self._playback_generation: return False
                if self._seek_in_progress:
                    self._seek_in_progress = False
                    if abs(self._pending_seek_delta) >= 0.001:
                        self._apply_pending_seek_delta()
                return False
            self._seek_release_timeout_id = GLib.timeout_add(
                250, _release_seek_lock
            )
            if self.is_playing and not self.is_paused:
                GLib.timeout_add(80, self._ensure_playing_after_seek)
                if self._custom_pipeline is not None:
                    GLib.timeout_add(250, self._ensure_playing_after_seek)
            return True
        except Exception:
            self._seek_in_progress = False
            return False

    def _ensure_playing_after_seek(self):
        try:
            if not self.is_playing or self.is_paused: return False
            pipe = self._active_pipeline()
            ret, state, pending = pipe.get_state(100 * Gst.MSECOND)
            if state != Gst.State.PLAYING:
                pipe.set_state(Gst.State.PLAYING)
            if self.current_is_video:
                self._nudge_video_redraw()
        except Exception: pass
        return False

    def _apply_pending_seek_delta(self):
        if abs(self._pending_seek_delta) < 0.001: return False
        delta = self._pending_seek_delta
        self._pending_seek_delta = 0.0
        base = self._last_known_position
        if self.current_duration > 0:
            base = min(max(0.0, base), self.current_duration)
        self.seek_to(base + delta, accurate=True)
        return False

    def _try_update_duration(self):
        try:
            if not self.current_path: return False
            ok, duration = self._active_pipeline().query_duration(Gst.Format.TIME)
            if not ok or duration <= 0: return False
            duration_seconds = duration / Gst.SECOND
            if duration_seconds <= 0: return False
            if self.current_duration <= 0 or abs(duration_seconds - self.current_duration) >= 0.05:
                self.current_duration = duration_seconds
                self.position_scale.set_range(0, duration_seconds)
                self._update_playlist_duration(self.current_path, duration_seconds)
            if not self.user_seeking:
                value = min(self.position_scale.get_value(), duration_seconds)
                self.time_label.set_text(
                    f"{format_time(value)} • {format_time(duration_seconds)}"
                )
            return True
        except Exception:
            return False

    def _update_playlist_duration(self, filename, duration):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._update_playlist_duration(self, filename, duration)
        return None

    def _seek_guard_active(self):
        g = getattr(self, "_seek_guard", None)
        try:
            return bool(g) and time.monotonic() < float(g[1])
        except Exception:
            return False

    def _seek_cancel_pending(self):
        tid = getattr(self, "_seek_coalesce_id", 0) or 0
        if tid:
            try: GLib.source_remove(tid)
            except Exception: pass
        self._seek_coalesce_id = 0
        self._seek_pending_target = None
        self._seek_guard = None

    def _seek_preview_ui(self, target):
        try:
            if self.current_duration > 0:
                self._updating_position_scale = True
                try:
                    self.position_scale.set_value(target)
                finally:
                    self._updating_position_scale = False
            if not self.user_seeking:
                self.time_label.set_text(
                    f"{format_time(target)} • {format_time(self.current_duration)}"
                )
            self._sync_fs_transport_ui()
        except Exception: pass

    def _seek_coalesce_fire(self):
        self._seek_coalesce_id = 0
        target = getattr(self, "_seek_pending_target", None)
        if target is None:
            return False
        if not self.current_path:
            self._seek_pending_target = None
            return False
        # Pipeline custom : attendre la fin du seek précédent
        if self._custom_pipeline is not None and self._seek_in_progress:
            self._seek_coalesce_id = GLib.timeout_add(
                60, self._seek_coalesce_fire
            )
            return False
        self._seek_pending_target = None
        self.seek_to(target, accurate=True)
        return False

    def seek_relative(self, seconds):
        try:
            if not self.current_path: return
            delta = float(seconds)
            def _clamp(t):
                t = max(0.0, t)
                dur = float(self.current_duration or 0)
                if dur > 2.0:
                    t = min(t, dur - 1.0)   # évite un FLUSH pile sur l'EOS
                elif dur > 0:
                    t = min(t, dur)
                return t
            pending = getattr(self, "_seek_pending_target", None)
            if pending is not None:
                base = float(pending)
            elif self._seek_in_progress or self._seek_guard_active():
                base = float(self._last_known_position or 0.0)
            else:
                ok, position = self._active_pipeline().query_position(Gst.Format.TIME)
                queried = position / Gst.SECOND if ok and position >= 0 else None
                last = float(self._last_known_position or 0.0)
                if queried is None:
                    base = last
                elif abs(queried - last) <= 2.5:
                    base = max(last, queried) if delta > 0 else min(last, queried)
                else:
                    base = last if last > 0 else queried
            target = _clamp(base + delta)
            self._seek_pending_target = target
            self._seek_preview_ui(target)
            if not (getattr(self, "_seek_coalesce_id", 0) or 0):
                self._seek_coalesce_id = GLib.timeout_add(
                    SEEK_COALESCE_MS, self._seek_coalesce_fire
                )
        except Exception: pass

    def volume_changed(self, scale):
        value = scale.get_value()
        if not self.is_muted:
            self._set_playback_volume(value)
            self._volume_before_mute = value
        else:
            if value > 0.001:
                self.is_muted = False
                self._set_playback_volume(value)
                self._volume_before_mute = value
                self._update_mute_button()
        self._mpris_properties_changed(
            {"Volume": GLib.Variant("d", float(value))}
        )
        if getattr(self, "is_playing", False):
            try:
                self._show_fs_toast(
                    "tr", f"♪  {int(round(value * 100))} %", 1000
                )
            except Exception:
                pass
        self.show_osd(f"♪  {int(round(value * 100))} %")
        try:
            self._fs_sync_volume_ui()
        except Exception:
            pass

    def adjust_volume(self, delta):
        try:
            current = self.volume_scale.get_value()
            if self.is_muted and delta > 0:
                self.is_muted = False
                self._update_mute_button()
            new_val = max(0.0, min(1.0, current + float(delta)))
            self.volume_scale.set_value(new_val)
        except Exception: pass

    def toggle_mute(self, *args):
        try:
            if not self.is_muted:
                self._volume_before_mute = max(
                    0.01, self.volume_scale.get_value()
                )
                self.is_muted = True
                self._set_playback_volume(0.0)
                self.show_osd("⌀  " + self.tr("Muet"))
            else:
                self.is_muted = False
                vol = self._volume_before_mute or 0.75
                self._set_playback_volume(vol)
                self.volume_scale.handler_block_by_func(self.volume_changed)
                self.volume_scale.set_value(vol)
                self.volume_scale.handler_unblock_by_func(self.volume_changed)
                self.show_osd("♪  " + self.tr("Son activé"))
            self._update_mute_button()
            self._mpris_properties_changed(
                {"Volume": GLib.Variant("d", 0.0 if self.is_muted else float(self.volume_scale.get_value()))}
            )
        except Exception as e:
            print("toggle_mute:", e, file=sys.stderr)

    def _update_mute_button(self):
        try:
            self._fs_sync_volume_ui()
        except Exception:
            pass
        if not hasattr(self, "mute_button") or self.mute_button is None:
            return
        if self.is_muted:
            self.mute_button.set_label("⌀")
            self.mute_button.set_tooltip_text(self.tr("Son activé") + " (M)")
        else:
            self.mute_button.set_label("♪")
            self.mute_button.set_tooltip_text(self.tr("Muet") + " (M)")

    def _is_osd_video_media(self, path=None):
        if _HAS_OSD_MOD:
            return _osdmod._is_osd_video_media(self, path)
        return None

    def _build_fullscreen_controls(self):
        if _HAS_OSD_MOD:
            return _osdmod._build_fullscreen_controls(self)
        return None

    def _install_fs_osd_css(self, force=False):
        if _HAS_OSD_MOD:
            return _osdmod._install_fs_osd_css(self, force)
        return None

    def _fs_on_volume_scale(self, scale):
        if _HAS_OSD_MOD:
            return _osdmod._fs_on_volume_scale(self, scale)
        return None

    def _fs_sync_volume_ui(self):
        if _HAS_OSD_MOD:
            return _osdmod._fs_sync_volume_ui(self)
        return None

    def _fs_retranslate_controls(self):
        if _HAS_OSD_MOD:
            return _osdmod._fs_retranslate_controls(self)
        return None

    def _fs_scroll_direction(self, event):
        if _HAS_OSD_MOD:
            return _osdmod._fs_scroll_direction(self, event)
        return None

    def _fs_on_volume_scroll(self, scale, event):
        if _HAS_OSD_MOD:
            return _osdmod._fs_on_volume_scroll(self, scale, event)
        return None

    def _fs_on_seek_scroll(self, scale, event):
        if _HAS_OSD_MOD:
            return _osdmod._fs_on_seek_scroll(self, scale, event)
        return None

    def _fs_scale_hover(self, scale, event):
        if _HAS_OSD_MOD:
            return _osdmod._fs_scale_hover(self, scale, event)
        return None

    def _fs_pointer_screen_xy(self):
        if _HAS_OSD_MOD:
            return _osdmod._fs_pointer_screen_xy(self)
        return None

    def _fs_pointer_over_widget(self, widget, margin=0):
        if _HAS_OSD_MOD:
            return _osdmod._fs_pointer_over_widget(self, widget, margin)
        return None

    def _fs_arm_autohide(self, delay_ms=None):
        if _HAS_OSD_MOD:
            return _osdmod._fs_arm_autohide(self, delay_ms)
        return None

    def _fs_schedule_leave_check(self):
        if _HAS_OSD_MOD:
            return _osdmod._fs_schedule_leave_check(self)
        return None

    def _fs_leave_check(self):
        if _HAS_OSD_MOD:
            return _osdmod._fs_leave_check(self)
        return None

    def on_video_leave(self, widget, event):
        if _HAS_OSD_MOD:
            return _osdmod.on_video_leave(self, widget, event)
        return None

    def _fs_popup_menu_above(self, menu, anchor):
        if _HAS_OSD_MOD:
            return _osdmod._fs_popup_menu_above(self, menu, anchor)
        return None

    def _fs_on_menu_deactivate(self, menu):
        if _HAS_OSD_MOD:
            return _osdmod._fs_on_menu_deactivate(self, menu)
        return None

    def _ensure_fs_toast_windows(self):
        if _HAS_OSD_MOD:
            return _osdmod._ensure_fs_toast_windows(self)
        return None

    def _position_fs_toast(self, corner):
        if _HAS_OSD_MOD:
            return _osdmod._position_fs_toast(self, corner)
        return None

    def _hide_fs_toasts(self):
        if _HAS_OSD_MOD:
            return _osdmod._hide_fs_toasts(self)
        return None

    def _show_fs_toast(self, corner, text, duration_ms=1800):
        if _HAS_OSD_MOD:
            return _osdmod._show_fs_toast(self, corner, text, duration_ms)
        return None

    def _fs_quick_screenshot(self, *args):
        if _HAS_OSD_MOD:
            return _osdmod._fs_quick_screenshot(self, *args)
        return None

    def _fs_quick_screenshot_do(self):
        if _HAS_OSD_MOD:
            return _osdmod._fs_quick_screenshot_do(self)
        return None

    def _announce_track_change(self, path):
        if _HAS_OSD_MOD:
            return _osdmod._announce_track_change(self, path)
        return None

    def _local_video_display_title(self):
        if _HAS_OSD_MOD:
            return _osdmod._local_video_display_title(self)
        return None

    def _fs_maybe_show_pause_title(self):
        if _HAS_OSD_MOD:
            return _osdmod._fs_maybe_show_pause_title(self)
        return None

    def _on_fs_controls_enter(self, *args):
        if _HAS_OSD_MOD:
            return _osdmod._on_fs_controls_enter(self, *args)
        return None

    def _pointer_over_fs_controls(self):
        if _HAS_OSD_MOD:
            return _osdmod._pointer_over_fs_controls(self)
        return None

    def _stop_fs_pointer_watch(self):
        if _HAS_OSD_MOD:
            return _osdmod._stop_fs_pointer_watch(self)
        return None

    def _on_fs_controls_leave(self, widget, event):
        if _HAS_OSD_MOD:
            return _osdmod._on_fs_controls_leave(self, widget, event)
        return None

    def _on_fs_controls_motion(self, *args):
        if _HAS_OSD_MOD:
            return _osdmod._on_fs_controls_motion(self, *args)
        return None

    def _sync_fs_transport_ui(self):
        if _HAS_OSD_MOD:
            return _osdmod._sync_fs_transport_ui(self)
        return None

    def _fs_pure_idle(self):
        if _HAS_OSD_MOD:
            return _osdmod._fs_pure_idle(self)
        return None

    def _fs_sync_play_button(self):
        if _HAS_OSD_MOD:
            return _osdmod._fs_sync_play_button(self)
        return None

    def _fs_ensure_idle_osd(self):
        if _HAS_OSD_MOD:
            return _osdmod._fs_ensure_idle_osd(self)
        return None

    def _dbg_transport(self, tag):
        if _HAS_OSD_MOD:
            return _osdmod._dbg_transport(self, tag)
        return None

    def _fs_osd_nav_allowed(self):
        if _HAS_OSD_MOD:
            return _osdmod._fs_osd_nav_allowed(self)
        return None

    def _on_fs_popup_draw(self, widget, cr):
        if _HAS_OSD_MOD:
            return _osdmod._on_fs_popup_draw(self, widget, cr)
        return None

    def _video_area_root_rect(self):
        if _HAS_OSD_MOD:
            return _osdmod._video_area_root_rect(self)
        return None

    def _position_fs_popup(self):
        if _HAS_OSD_MOD:
            return _osdmod._position_fs_popup(self)
        return None

    def _on_main_configure_for_fs_popup(self, widget, event):
        if _HAS_OSD_MOD:
            return _osdmod._on_main_configure_for_fs_popup(self, widget, event)
        return None

    def _fs_update_video_buttons(self):
        if _HAS_OSD_MOD:
            return _osdmod._fs_update_video_buttons(self)
        return None

    def _fs_toggle_fullscreen(self, *args):
        if _HAS_OSD_MOD:
            return _osdmod._fs_toggle_fullscreen(self, *args)
        return None

    def _fs_return_to_playlist_mode(self, *args):
        if _HAS_OSD_MOD:
            return _osdmod._fs_return_to_playlist_mode(self, *args)
        return None

    def _fs_popup_audio_menu(self, *args):
        if _HAS_OSD_MOD:
            return _osdmod._fs_popup_audio_menu(self, *args)
        return None

    def _fs_popup_subtitle_menu(self, *args):
        if _HAS_OSD_MOD:
            return _osdmod._fs_popup_subtitle_menu(self, *args)
        return None

    def _show_fs_controls(self):
        if _HAS_OSD_MOD:
            return _osdmod._show_fs_controls(self)
        return None

    def _fs_on_fullscreen_left(self):
        if _HAS_OSD_MOD:
            return _osdmod._fs_on_fullscreen_left(self)
        return None

    def _fs_popup_stale(self):
        if _HAS_OSD_MOD:
            return _osdmod._fs_popup_stale(self)
        return None

    def _hide_fs_controls(self, immediate=False, force=False):
        if _HAS_OSD_MOD:
            return _osdmod._hide_fs_controls(self, immediate, force)
        return None

    def _fs_hot_zone_px(self, area_h):
        if _HAS_OSD_MOD:
            return _osdmod._fs_hot_zone_px(self, area_h)
        return None

    def on_video_motion(self, widget, event):
        if _HAS_OSD_MOD:
            return _osdmod.on_video_motion(self, widget, event)
        return None

    def _reset_cursor_hide_timer(self):
        if _HAS_OSD_MOD:
            return _osdmod._reset_cursor_hide_timer(self)
        return None

    def _hide_cursor(self):
        if _HAS_OSD_MOD:
            return _osdmod._hide_cursor(self)
        return None

    def _show_cursor(self):
        if _HAS_OSD_MOD:
            return _osdmod._show_cursor(self)
        return None

    def show_osd(self, text, duration_ms=1600):
        if _HAS_OSD_MOD:
            return _osdmod.show_osd(self, text, duration_ms)
        return None

    def _osd_seek_feedback(self, delta):
        if _HAS_OSD_MOD:
            return _osdmod._osd_seek_feedback(self, delta)
        return None

    def _clear_chapters(self):
        self.chapters = []

    def _ingest_toc(self, toc):
        if toc is None: return
        found = []
        def _walk(entry):
            try:
                etype = entry.get_entry_type()
            except Exception:
                etype = None
            start_ns = None
            try:
                ret = entry.get_start_stop_times()
                if isinstance(ret, tuple) and len(ret) >= 3 and isinstance(ret[0], bool):
                    if ret[0]:
                        start_ns = int(ret[1])
                elif isinstance(ret, tuple) and len(ret) >= 2 and not isinstance(ret[0], bool):
                    start_ns = int(ret[0])
                elif isinstance(ret, tuple) and len(ret) == 2 and isinstance(ret[0], bool):
                    if ret[0]:
                        start_ns = int(ret[1])
            except Exception:
                start_ns = None
            title = None
            try:
                tags = entry.get_tags()
                if tags is not None:
                    ok, t = tags.get_string(Gst.TAG_TITLE)
                    if ok and t:
                        title = t.strip()
            except Exception: pass
            is_chapter = False
            try:
                if etype == Gst.TocEntryType.CHAPTER:
                    is_chapter = True
                elif etype is not None and "CHAPTER" in str(etype).upper():
                    is_chapter = True
            except Exception: pass
            if is_chapter and start_ns is not None and start_ns >= 0:
                sec = start_ns / float(Gst.SECOND)
                if title is None:
                    title = f"{self.tr('Chapitre')} {len(found) + 1}"
                found.append((sec, title))
            try:
                for sub in entry.get_sub_entries() or []:
                    _walk(sub)
            except Exception: pass
        try:
            for entry in toc.get_entries() or []:
                _walk(entry)
        except Exception: pass
        if found:
            found.sort(key=lambda x: x[0])
            self.chapters = found

    def seek_to_chapter(self, index):
        if index < 0 or index >= len(self.chapters): return
        start, title = self.chapters[index]
        self.seek_to(start, accurate=True)
        try:
            self._show_fs_toast(
                "tl",
                "⏭  %s  (%s)" % (title, format_time(start)),
                2000,
            )
        except Exception: pass

    def _setup_mpris(self):
        if _HAS_MPRIS_MOD:
            return _mprismod._setup_mpris(self)
        return None

    def _mpris_method_call(
        self, connection, sender, object_path, interface_name,
        method_name, parameters, invocation
    ):
        if _HAS_MPRIS_MOD:
            return _mprismod._mpris_method_call(self, connection, sender, object_path, interface_name, method_name, parameters, invocation)
        return None

    def _mpris_get_property(
        self, connection, sender, object_path, interface_name, property_name
    ):
        if _HAS_MPRIS_MOD:
            return _mprismod._mpris_get_property(self, connection, sender, object_path, interface_name, property_name)
        return None

    def _mpris_set_property(
        self, connection, sender, object_path, interface_name,
        property_name, value
    ):
        if _HAS_MPRIS_MOD:
            return _mprismod._mpris_set_property(self, connection, sender, object_path, interface_name, property_name, value)
        return None

    def _mpris_metadata_variant(self):
        if _HAS_MPRIS_MOD:
            return _mprismod._mpris_metadata_variant(self)
        return None

    def _mpris_properties_changed(self, props):
        if _HAS_MPRIS_MOD:
            return _mprismod._mpris_properties_changed(self, props)
        return None

    def _mpris_notify_playback(self):
        if _HAS_MPRIS_MOD:
            return _mprismod._mpris_notify_playback(self)
        return None

    def show_keyboard_shortcuts(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.show_keyboard_shortcuts(self, *args)
        return None

    def on_tree_button_press(self, tree, event):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.on_tree_button_press(self, tree, event)
        return None

    def show_metadata(self, filename):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.show_metadata(self, filename)
        return None

    def save_metadata(self, filename, title, artist, album, year):
        if _HAS_METADATA_PANEL_MOD:
            return _metapanelmod.save_metadata(self, filename, title, artist, album, year)
        return None

    def set_vorbis_tags(self, audio, title, artist, album, year):
        if title:
            audio["title"] = [title]
        else:
            audio.pop("title", None)
        if artist:
            audio["artist"] = [artist]
        else:
            audio.pop("artist", None)
        if album:
            audio["album"] = [album]
        else:
            audio.pop("album", None)
        if year:
            audio["date"] = [year]
        else:
            audio.pop("date", None)

    def refresh_file(self, filename):
        if filename in self.metadata_cache:
            del self.metadata_cache[filename]
        iterator = self.playlist.get_iter_first()
        while iterator is not None:
            if self.playlist[iterator][self.COL_PATH] == filename:
                title, artist, album, year, duration, cover, technical = \
                    self.get_metadata(filename, load_cover=False)
                self.playlist[iterator][self.COL_TITLE] = title
                self.playlist[iterator][self.COL_ARTIST] = artist
                self.playlist[iterator][self.COL_ALBUM] = album
                self.playlist[iterator][self.COL_DURATION_TEXT] = format_time(duration)
                self.playlist[iterator][self.COL_DURATION] = float(duration)
                return
            iterator = self.playlist.iter_next(iterator)

    def remove_selected(self):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.remove_selected(self)
        return None

    def remove_file(self, filename):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.remove_file(self, filename)
        return None

    def clear_playlist(self):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.clear_playlist(self)
        return None

    def show_sound_settings(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.show_sound_settings(self, *args)
        return None

    def show_equalizer(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.show_equalizer(self, *args)
        return None

    def toggle_eq_mute(self, button=None):
        if _HAS_EQUALIZER_MOD:
            return _eqmod.toggle_eq_mute(self, button)
        return None

    def reset_equalizer(self, *args):
        if _HAS_EQUALIZER_MOD:
            return _eqmod.reset_equalizer(self, *args)
        return None

    def apply_eq_preset(self, *args):
        if _HAS_EQUALIZER_MOD:
            return _eqmod.apply_eq_preset(self, *args)
        return None

    def save_eq_preset(self, *args):
        if _HAS_EQUALIZER_MOD:
            return _eqmod.save_eq_preset(self, *args)
        return None

    def delete_eq_preset(self, *args):
        if _HAS_EQUALIZER_MOD:
            return _eqmod.delete_eq_preset(self, *args)
        return None

    def _snap_pitch_tempo_values(self):
        if _HAS_EQUALIZER_MOD:
            return _eqmod._snap_pitch_tempo_values(self)
        return None

    def _configure_pitch_element(self):
        if _HAS_EQUALIZER_MOD:
            return _eqmod._configure_pitch_element(self)
        return None

    def _preamp_linear_gain(self):
        if _HAS_EQUALIZER_MOD:
            return _eqmod._preamp_linear_gain(self)
        return None

    def _apply_preamp_gain(self):
        if _HAS_EQUALIZER_MOD:
            return _eqmod._apply_preamp_gain(self)
        return None

    def _apply_balance_value(self):
        if _HAS_EQUALIZER_MOD:
            return _eqmod._apply_balance_value(self)
        return None


    def _ensure_downmix_elements(self):
        if _HAS_EQUALIZER_MOD:
            return _eqmod._ensure_downmix_elements(self)
        return None

    def _ensure_mono_elements(self):
        """Stereo → mono → stereo (L=R). No channel-mask (avoids bad upmix)."""
        try:
            if getattr(self, "_mono_c1", None) is None:
                self._mono_c1 = Gst.ElementFactory.make("audioconvert", "mono-c1")
            if getattr(self, "_mono_caps", None) is None:
                el = Gst.ElementFactory.make("capsfilter", "mono-caps")
                if el is not None:
                    el.set_property(
                        "caps", Gst.Caps.from_string("audio/x-raw,channels=1")
                    )
                self._mono_caps = el
            if getattr(self, "_mono_c2", None) is None:
                self._mono_c2 = Gst.ElementFactory.make("audioconvert", "mono-c2")
            if getattr(self, "_mono_caps2", None) is None:
                el = Gst.ElementFactory.make("capsfilter", "mono-caps2")
                if el is not None:
                    el.set_property(
                        "caps", Gst.Caps.from_string("audio/x-raw,channels=2")
                    )
                self._mono_caps2 = el
        except Exception as e:
            print("mono elements:", e, file=sys.stderr)
            return False
        return all(
            (
                self._mono_c1,
                self._mono_caps,
                self._mono_c2,
                self._mono_caps2,
            )
        )

    def _detach_mono_elements(self):
        for name in ("_mono_c1", "_mono_caps", "_mono_c2", "_mono_caps2"):
            el = getattr(self, name, None)
            if el is None:
                continue
            try:
                parent = el.get_parent()
                if parent is not None:
                    parent.remove(el)
            except Exception:
                pass



    def _detach_idle_sound_elements(self):
        """Detach mono/balance elements when they are not in use."""
        try:
            need_bal = abs(float(getattr(self, "audio_balance", 0.0) or 0.0)) > 0.001
        except Exception:
            need_bal = False
        if not bool(getattr(self, "audio_mono", False)):
            try:
                self._detach_mono_elements()
            except Exception:
                pass
        if not need_bal:
            for el in (
                getattr(self, "_bal_conv", None),
                getattr(self, "audio_balance_el", None),
            ):
                if el is None:
                    continue
                try:
                    parent = el.get_parent()
                    if parent is not None:
                        parent.remove(el)
                except Exception:
                    pass

    def _apply_sound_settings(self):
        try:
            self._apply_preamp_gain()
        except Exception:
            pass
        try:
            self._apply_balance_value()
        except Exception:
            pass
        try:
            self.rebuild_audio_filter(force=True, restart=True)
        except Exception:
            pass


    def rebuild_audio_filter(self, force=False, restart=True):
        if _HAS_EQUALIZER_MOD:
            return _eqmod.rebuild_audio_filter(self, force, restart)
        return None

    def _probe_video_size_for_colorimetry(self):
        try:
            pipe = self._active_pipeline()
            if pipe is None: return
            ok, w = pipe.query_duration(Gst.Format.TIME)
        except Exception: pass
        width = height = 0
        try:
            pipe = self._active_pipeline()
            if pipe is None: return
            try:
                pad = pipe.emit("get-video-pad", 0)
            except Exception:
                pad = None
            if pad is None:
                try:
                    pad = pipe.get_static_pad("src")
                except Exception:
                    pad = None
            caps = None
            if pad is not None:
                caps = pad.get_current_caps()
                if caps is None:
                    caps = pad.query_caps(None)
            if caps is not None and not caps.is_empty():
                st = caps.get_structure(0)
                if st is not None:
                    ok, width = st.get_int("width")
                    if not ok:
                        width = 0
                    ok, height = st.get_int("height")
                    if not ok:
                        height = 0
        except Exception:
            width = height = 0
        if width or height:
            self._maybe_disable_colorimetry_for_4k(width, height)

    def _maybe_disable_colorimetry_for_4k(self, width=None, height=None):
        try:
            w = int(width or 0)
            h = int(height or 0)
        except Exception:
            w = h = 0
        if w <= 0 and h <= 0: return
        is_4k = (w >= 3840) or (h >= 2160)
        if not is_4k: return
        if not bool(getattr(self, "colorimetry_enabled", False)): return
        self.colorimetry_enabled = False
        try: self._apply_video_colorimetry()
        except Exception: pass
        try: self._update_colorimetry_menu_sensitivity()
        except Exception: pass
        try:
            item = getattr(self, "colorimetry_check_item", None) or getattr(
                self, "colorimetry_menu_item", None
            )
            if item is not None and hasattr(item, "set_active"):
                try:
                    item.handler_block_by_func(self.toggle_colorimetry_enabled)
                    item.set_active(False)
                    item.handler_unblock_by_func(self.toggle_colorimetry_enabled)
                except Exception:
                    item.set_active(False)
        except Exception: pass
        try:
            self.status_label.set_text(
                self.tr("Colorimétrie") + " — 4K"
            )
        except Exception: pass
        try: self.save_state()
        except Exception: pass
    def _colorimetry_allowed(self):
        path = getattr(self, "current_path", None)
        if not path: return False
        if is_pure_audio_file(path) or is_cdda(path): return False
        if is_video_file(path) or is_dvd(path) or is_bluray(path): return True
        if getattr(self, "current_is_video", False): return True
        if is_stream(path) and (
            getattr(self, "bouquet_active", False)
            or getattr(self, "_prefer_video", False)
        ):
            return True
        return False

    def _update_colorimetry_menu_sensitivity(self):
        allowed = False
        try:
            allowed = self._colorimetry_allowed()
        except Exception:
            allowed = False
        enabled = bool(getattr(self, "colorimetry_enabled", False))
        for attr in (
            "colorimetry_menu_item",
            "colorimetry_check_item",
            "colorimetry_adjust_item",
        ):
            item = getattr(self, attr, None)
            if item is None: continue
            try:
                if attr == "colorimetry_adjust_item":
                    item.set_sensitive(allowed and enabled)
                else:
                    item.set_sensitive(allowed)
            except Exception: pass
        check = getattr(self, "colorimetry_check_item", None)
        if check is not None:
            try:
                if bool(check.get_active()) != enabled:
                    check.handler_block_by_func(self.toggle_colorimetry_enabled)
                    check.set_active(enabled)
                    check.handler_unblock_by_func(self.toggle_colorimetry_enabled)
            except Exception:
                try: check.set_active(enabled)
                except Exception: pass
        if not allowed:
            win = getattr(self, "colorimetry_window", None)
            if win is not None:
                try: win.destroy()
                except Exception: pass
    def _apply_color_props_to(self, balance, gamma):
        if balance is not None:
            for prop, val in (
                ("brightness", float(self.color_brightness)),
                ("contrast", float(self.color_contrast)),
                ("saturation", float(self.color_saturation)),
            ):
                try: balance.set_property(prop, val)
                except Exception: pass
        if gamma is not None:
            try: gamma.set_property("gamma", float(self.color_gamma))
            except Exception: pass
    def _apply_video_colorimetry(self):
        self._apply_color_props_to(
            getattr(self, "_video_balance", None),
            getattr(self, "_video_gamma", None),
        )
        self._apply_color_props_to(
            getattr(self, "_custom_vbalance", None),
            getattr(self, "_custom_vgamma", None),
        )


    def _apply_vpp_tonemap_filter(self):
        """HDR tone mapping in playbin video-filter, before subtitle composition.

        vapostproc is set but does not tone-map here (needs VA memory it does
        not get). Use the GL shader, then gldownload so textoverlay can composite.
        """
        if getattr(self, "_custom_pipeline", None) is not None:
            return
        if bool(getattr(self, "colorimetry_enabled", False)):
            return
        dbg = bool(os.environ.get("MYOSTOOX_DEBUG", "").strip())
        try:
            from player import _make_hdr_tonemap_chain
        except Exception:
            try:
                from myostoox.player import _make_hdr_tonemap_chain
            except Exception:
                _make_hdr_tonemap_chain = None
        chain = None
        if _make_hdr_tonemap_chain is not None:
            try:
                chain = _make_hdr_tonemap_chain()
            except Exception:
                chain = None
        if not chain:
            if dbg:
                print("hdr filter: shader chain unavailable", file=sys.stderr)
            return
        try:
            download = Gst.ElementFactory.make("gldownload", "hdr-download")
        except Exception:
            download = None
        if download is None:
            if dbg:
                print("hdr filter: gldownload unavailable", file=sys.stderr)
            return
        try:
            bin_ = Gst.Bin.new("hdr-tonemap-bin")
            for el in chain:
                bin_.add(el)
            bin_.add(download)
            for a, b in zip(chain, chain[1:]):
                if not a.link(b):
                    raise RuntimeError("hdr link")
            if not chain[-1].link(download):
                raise RuntimeError("hdr download link")
            sink_pad = chain[0].get_static_pad("sink")
            src_pad = download.get_static_pad("src")
            if not bin_.add_pad(Gst.GhostPad.new("sink", sink_pad)):
                raise RuntimeError("ghost sink")
            if not bin_.add_pad(Gst.GhostPad.new("src", src_pad)):
                raise RuntimeError("ghost src")
            self.player.set_property("video-filter", bin_)
            self._hdr_tonemap_active = True
            if dbg:
                print("Myostoox: tone mapping HDR via glshader", file=sys.stderr)
        except Exception as e:
            if dbg:
                print("hdr filter:", e, file=sys.stderr)
            try:
                self.player.set_property("video-filter", None)
            except Exception:
                pass
            self._hdr_tonemap_active = False

    def _rebuild_video_color_filter(self, restore_playback=True):
        """Rebuild playbin video-filter (colorimetry panel only)."""
        is_video = bool(getattr(self, "current_is_video", False))
        color_on = bool(getattr(self, "colorimetry_enabled", False))

        if (
            not is_video
            and not color_on
            and self._video_color_bin is None
        ):
            return True

        if getattr(self, "_custom_pipeline", None) is not None:
            self._video_balance = None
            self._video_gamma = None
            self._video_color_bin = None
            try:
                self.player.set_property("video-filter", None)
            except Exception:
                pass
            return True

        was_playing = bool(
            getattr(self, "is_playing", False)
            and not getattr(self, "is_paused", False)
        )
        was_paused = bool(getattr(self, "is_paused", False))
        pos = float(getattr(self, "_last_known_position", 0) or 0)
        path = getattr(self, "current_path", None)
        need_restore = bool(
            restore_playback
            and path
            and (was_playing or was_paused)
            and not is_pure_audio_file(path)
        )

        try:
            try:
                self.player.set_state(Gst.State.NULL)
                self.player.get_state(int(2 * Gst.SECOND))
            except Exception:
                pass

            self._video_balance = None
            self._video_gamma = None
            self._video_color_bin = None

            try:
                self.player.set_property("video-filter", None)
            except Exception:
                pass

            ok = True

            if is_video and color_on:
                elements = []
                vb = Gst.ElementFactory.make(
                    "videobalance", "play-vbalance"
                )
                gm = Gst.ElementFactory.make(
                    "gamma", "play-vgamma"
                )
                if vb is None and gm is None:
                    raise RuntimeError("videobalance/gamma indisponibles")
                self._apply_color_props_to(vb, gm)
                elements.extend(el for el in (vb, gm) if el is not None)

                bin_ = Gst.Bin.new("video-color-bin")
                for el in elements:
                    bin_.add(el)
                for first, second in zip(elements, elements[1:]):
                    if not first.link(second):
                        raise RuntimeError(
                            "liaison impossible dans video-filter"
                        )
                sink_pad = elements[0].get_static_pad("sink")
                src_pad = elements[-1].get_static_pad("src")
                if sink_pad is None or src_pad is None:
                    raise RuntimeError("pad vidéo indisponible")
                if not bin_.add_pad(Gst.GhostPad.new("sink", sink_pad)):
                    raise RuntimeError("ghost pad sink impossible")
                if not bin_.add_pad(Gst.GhostPad.new("src", src_pad)):
                    raise RuntimeError("ghost pad src impossible")
                self.player.set_property("video-filter", bin_)
                self._video_balance = vb
                self._video_gamma = gm
                self._video_color_bin = bin_
            if need_restore and path:
                try:
                    if (
                        is_cdda(path)
                        or is_stream(path)
                        or is_dvd(path)
                        or is_bluray(path)
                    ):
                        uri = path
                    else:
                        uri = GLib.filename_to_uri(
                            os.path.abspath(path), None
                        )
                    self.player.set_property("uri", uri)
                except Exception as e:
                    print("color filter re-uri:", e, file=sys.stderr)

                try:
                    self.player.set_state(Gst.State.PAUSED)
                    self.player.get_state(int(3 * Gst.SECOND))
                except Exception:
                    pass

                if pos > 0.4:
                    try:
                        self.player.seek_simple(
                            Gst.Format.TIME,
                            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                            int(pos * Gst.SECOND),
                        )
                        self.player.get_state(int(2 * Gst.SECOND))
                    except Exception:
                        pass

                if was_playing:
                    try:
                        self.player.set_state(Gst.State.PLAYING)
                        self.is_playing = True
                        self.is_paused = False
                        self.play_button.set_label("❚❚")
                    except Exception:
                        pass
                elif was_paused:
                    self.is_playing = True
                    self.is_paused = True
                    self.play_button.set_label("▶")

            return ok

        except Exception as e:
            print("rebuild video color:", e, file=sys.stderr)
            return False

    def _link_through_video_color(self, pipe, prev, sink):
        if not bool(getattr(self, "colorimetry_enabled", False)):
            self._custom_vbalance = None
            self._custom_vgamma = None
            try:
                return bool(prev.link(sink))
            except Exception:
                return False
        vb = Gst.ElementFactory.make("videobalance", "mkv-vbalance")
        gm = Gst.ElementFactory.make("gamma", "mkv-vgamma")
        if vb is None and gm is None:
            self._custom_vbalance = None
            self._custom_vgamma = None
            try:
                return bool(prev.link(sink))
            except Exception:
                return False
        self._custom_vbalance = vb
        self._custom_vgamma = gm
        self._apply_color_props_to(vb, gm)
        chain = [el for el in (vb, gm) if el is not None]
        if not chain:
            try:
                return bool(prev.link(sink))
            except Exception:
                return False
        for el in chain:
            pipe.add(el)
            try: el.sync_state_with_parent()
            except Exception: pass
        try:
            if not prev.link(chain[0]): return bool(prev.link(sink))
            for i in range(len(chain) - 1):
                if not chain[i].link(chain[i + 1]):
                    chain[0].link(sink)
                    return True
            return bool(chain[-1].link(sink))
        except Exception as e:
            print("custom color link:", e, file=sys.stderr)
            try:
                return bool(prev.link(sink))
            except Exception:
                return False

    def toggle_colorimetry_enabled(self, menuitem=None):
        if menuitem is not None and hasattr(menuitem, "get_active"):
            want = bool(menuitem.get_active())
        else:
            want = not bool(getattr(self, "colorimetry_enabled", False))
        self.colorimetry_enabled = want
        ok = True
        try:
            custom = getattr(self, "_custom_pipeline", None) is not None
            path = getattr(self, "current_path", None)
            pos = float(getattr(self, "_last_known_position", 0) or 0)
            was_playing = self.is_playing and not self.is_paused
            was_paused = self.is_paused
            if custom and path and self._colorimetry_allowed():
                try:
                    if not self._play_file_custom_mkv(path):
                        ok = False
                    else:
                        if pos > 0.5:
                            GLib.timeout_add(
                                500,
                                lambda p=pos: (self.seek_to(p) or False),
                            )
                        if not was_playing and was_paused:
                            GLib.timeout_add(
                                600,
                                lambda: (
                                    self._active_pipeline().set_state(
                                        Gst.State.PAUSED
                                    )
                                    or False
                                ),
                            )
                except Exception as e:
                    print("colorimetry toggle custom:", e, file=sys.stderr)
                    ok = False
                try: self._rebuild_video_color_filter(restore_playback=False)
                except Exception: pass
            else:
                ok = bool(self._rebuild_video_color_filter(restore_playback=True))
        except Exception as e:
            print("colorimetry toggle:", e, file=sys.stderr)
            ok = False
        if not ok and want:
            self.colorimetry_enabled = False
            try:
                if menuitem is not None and hasattr(menuitem, "set_active"):
                    menuitem.handler_block_by_func(self.toggle_colorimetry_enabled)
                    menuitem.set_active(False)
                    menuitem.handler_unblock_by_func(self.toggle_colorimetry_enabled)
            except Exception:
                try:
                    if menuitem is not None:
                        menuitem.set_active(False)
                except Exception: pass
            try: self._rebuild_video_color_filter(restore_playback=True)
            except Exception: pass
            self.status_label.set_text(
                self.tr("Colorimétrie")
                + " — "
                + self.tr("échec, désactivée")
            )
        else:
            self.status_label.set_text(
                self.tr("Colorimétrie activée")
                if self.colorimetry_enabled
                else self.tr("Colorimétrie désactivée")
            )
        try: self._update_colorimetry_menu_sensitivity()
        except Exception: pass
        try: self.save_state()
        except Exception: pass
        if not self.colorimetry_enabled:
            win = getattr(self, "colorimetry_window", None)
            if win is not None:
                try: win.destroy()
                except Exception: pass
    def show_colorimetry(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.show_colorimetry(self, *args)
        return None

    def _is_speed_media(self, path=None):
        path = path if path is not None else getattr(self, "current_path", None)
        if not isinstance(path, str) or not path: return False
        try:
            if is_stream(path): return False
        except Exception: pass
        try:
            if is_video_file(path) or is_dvd(path) or is_bluray(path): return True
        except Exception: pass
        return False

    def _seek_with_rate(self, pipe, flags, ns):
        rate = 1.0
        try:
            if self._is_speed_media():
                rate = float(getattr(self, "playback_rate", 1.0) or 1.0)
        except Exception:
            rate = 1.0
        if rate <= 0.01:
            rate = 1.0
        return bool(
            pipe.seek(
                rate,
                Gst.Format.TIME,
                flags,
                Gst.SeekType.SET,
                int(ns),
                Gst.SeekType.NONE,
                -1,
            )
        )

    def _apply_playback_rate_idle(self):
        try:
            self._apply_playback_rate()
        except Exception as e:
            print("playback rate idle:", e, file=sys.stderr)
        return False

    def _apply_playback_rate(self):
        rate = float(getattr(self, "playback_rate", 1.0) or 1.0)
        if rate <= 0.01:
            rate = 1.0
            self.playback_rate = rate
        pipe = None
        try:
            pipe = self._active_pipeline()
        except Exception:
            pipe = None
        if pipe is None: return False
        pos_ns = 0
        try:
            ok, pos = pipe.query_position(Gst.Format.TIME)
            if ok and pos is not None and pos >= 0:
                pos_ns = int(pos)
            else:
                pos_ns = int(float(getattr(self, "_last_known_position", 0.0) or 0.0) * Gst.SECOND)
        except Exception:
            try:
                pos_ns = int(float(getattr(self, "_last_known_position", 0.0) or 0.0) * Gst.SECOND)
            except Exception:
                pos_ns = 0
        flags = Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE
        try:
            success = bool(
                pipe.seek(
                    rate,
                    Gst.Format.TIME,
                    flags,
                    Gst.SeekType.SET,
                    int(pos_ns),
                    Gst.SeekType.NONE,
                    -1,
                )
            )
        except Exception as e:
            print("playback rate seek:", e, file=sys.stderr)
            success = False
        if success and self.is_playing and not self.is_paused:
            try: pipe.set_state(Gst.State.PLAYING)
            except Exception: pass
        return success

    def set_playback_rate(self, rate):
        try:
            rate = float(rate)
        except Exception:
            rate = 1.0
        allowed = PLAYBACK_RATES
        rate = min(allowed, key=lambda x: abs(x - rate))
        self.playback_rate = rate
        if self._is_speed_media():
            try:
                self._apply_playback_rate()
            except Exception as e:
                print("set_playback_rate:", e, file=sys.stderr)
        try:
            self.status_label.set_text(
                self.tr("Vitesse") + " : " + ("x " + ("%.2f" % rate).rstrip("0").rstrip("."))
            )
        except Exception: pass
        try: self.save_state()
        except Exception: pass
    def show_speed(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.show_speed(self, *args)
        return None

    def show_pitch_tempo(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.show_pitch_tempo(self, *args)
        return None

    def on_pitch_changed(self, scale):
        if _HAS_EQUALIZER_MOD:
            return _eqmod.on_pitch_changed(self, scale)
        return None

    def on_tempo_changed(self, scale):
        if _HAS_EQUALIZER_MOD:
            return _eqmod.on_tempo_changed(self, scale)
        return None

    def reset_pitch_tempo(self, *args):
        if _HAS_EQUALIZER_MOD:
            return _eqmod.reset_pitch_tempo(self, *args)
        return None

    def _update_pitch_menu_sensitivity(self):
        if _HAS_EQUALIZER_MOD:
            return _eqmod._update_pitch_menu_sensitivity(self)
        return None
    def _update_speed_menu_sensitivity(self):
        item = getattr(self, "speed_menu_item", None)
        allowed = False
        try:
            allowed = self._is_speed_media()
        except Exception:
            allowed = False
        if item is not None:
            try: item.set_sensitive(allowed)
            except Exception: pass
        if not allowed and getattr(self, "speed_window", None) is not None:
            try: self.speed_window.destroy()
            except Exception: pass
    def _notify_track_change(self, title, artist, album=None):
        if _HAS_NOTIFICATIONS_MOD:
            return _notifmod._notify_track_change(self,title,artist,album)
        return None

    def _xdg_screensaver_window_id(self):
        if _HAS_SCREENSAVER_MOD:
            return _ssmod._xdg_screensaver_window_id(self)
        return None

    def _inhibit_screensaver(self, enable):
        if _HAS_SCREENSAVER_MOD:
            return _ssmod._inhibit_screensaver(self, enable)
        return None

    def _screensaver_shutdown(self, timeout=3.0):
        if _HAS_SCREENSAVER_MOD:
            return _ssmod._screensaver_shutdown(self, timeout=3.0)
        return None

    def _ss_worker(self):
        if _HAS_SCREENSAVER_MOD:
            return _ssmod._ss_worker(self)
        return None

    def _ss_apply_on(self, xid):
        if _HAS_SCREENSAVER_MOD:
            return _ssmod._ss_apply_on(self, xid)
        return None

    def _ss_apply_off(self):
        if _HAS_SCREENSAVER_MOD:
            return _ssmod._ss_apply_off(self)
        return None

    def _ss_get_bus(self):
        if _HAS_SCREENSAVER_MOD:
            return _ssmod._ss_get_bus(self)
        return None

    def _ss_dbus_inhibit(self):
        if _HAS_SCREENSAVER_MOD:
            return _ssmod._ss_dbus_inhibit(self)
        return None

    def _ss_dbus_release(self):
        if _HAS_SCREENSAVER_MOD:
            return _ssmod._ss_dbus_release(self)
        return None

    def _ss_run(self, cmd, timeout=6.0):
        if _HAS_SCREENSAVER_MOD:
            return _ssmod._ss_run(self, cmd, timeout=6.0)
        return None

    def _ss_xdg_suspend(self, xid):
        if _HAS_SCREENSAVER_MOD:
            return _ssmod._ss_xdg_suspend(self, xid)
        return None

    def _ss_xdg_resume(self):
        if _HAS_RESUME_MOD:
            return _resumemod._ss_xdg_resume(self)
        return None

    def _update_screensaver_inhibit(self):
        if _HAS_SCREENSAVER_MOD:
            return _ssmod._update_screensaver_inhibit(self)
        return None

    def toggle_mini_player(self, *args):
        if _HAS_COMPACT_MOD:
            return _compactmod.toggle_mini_player(self, *args)
        return None
    def toggle_mini_banner(self, *args):
        if _HAS_COMPACT_MOD:
            return _compactmod.toggle_mini_banner(self, *args)
        return None

    def _mini_banner_effectively_on(self):
        if _HAS_COMPACT_MOD:
            return _compactmod._mini_banner_effectively_on(self)
        return None

    def _apply_mini_banner_state(self):
        if _HAS_COMPACT_MOD:
            return _compactmod._apply_mini_banner_state(self)
        return None


    def _on_mini_banner_button_press(self, widget, event):
        if _HAS_COMPACT_MOD:
            return _compactmod._on_mini_banner_button_press(self, widget, event)
        return None

    def _build_mini_title_marquee(self, main):
        if _HAS_COMPACT_MOD:
            return _compactmod._build_mini_title_marquee(self, main)
        return None

    def _mini_marquee_start(self):
        if _HAS_COMPACT_MOD:
            return _compactmod._mini_marquee_start(self)
        return None

    def _stop_mini_title_scroll(self):
        if _HAS_COMPACT_MOD:
            return _compactmod._stop_mini_title_scroll(self)
        return None

    def _mini_marquee_tick(self, widget, frame_clock, *args):
        if _HAS_COMPACT_MOD:
            return _compactmod._mini_marquee_tick(self, widget, frame_clock, *args)
        return None

    def _mini_marquee_draw(self, widget, cr):
        if _HAS_COMPACT_MOD:
            return _compactmod._mini_marquee_draw(self, widget, cr)
        return None

    def _compose_mini_banner_text(self):
        if _HAS_COMPACT_MOD:
            return _compactmod._compose_mini_banner_text(self)
        return None

    def _update_mini_title(self):
        if _HAS_COMPACT_MOD:
            return _compactmod._update_mini_title(self)
        return None
    def toggle_nano_player(self, *args):
        if _HAS_COMPACT_MOD:
            return _compactmod.toggle_nano_player(self, *args)
        return None
    def toggle_nano_banner(self, *args):
        if _HAS_COMPACT_MOD:
            return _compactmod.toggle_nano_banner(self, *args)
        return None
    def toggle_nano_vertical(self, *args):
        if _HAS_COMPACT_MOD:
            return _compactmod.toggle_nano_vertical(self, *args)
        return None
    def toggle_nano_playlist(self, *args):
        if _HAS_COMPACT_MOD:
            return _compactmod.toggle_nano_playlist(self, *args)
        return None
    def set_nano_playlist_side(self, side):
        if _HAS_COMPACT_MOD:
            return _compactmod.set_nano_playlist_side(self, side)
        return None
    def _build_nano_playlist_panel(self, main):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._build_nano_playlist_panel(self, main)
        return None

    def _nano_playlist_row_activated(self, tree, path, column):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._nano_playlist_row_activated(self, tree, path, column)
        return None

    def _on_nano_playlist_key_press(self, tree, event):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._on_nano_playlist_key_press(self, tree, event)
        return None

    def _hide_nano_playlist_panel(self):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._hide_nano_playlist_panel(self)
        return None
    def _apply_nano_playlist_layout(self):
        if _HAS_COMPACT_MOD:
            return _compactmod._apply_nano_playlist_layout(self)
        return None

    def _queue_resize_recursive(self, widget):
        if _HAS_COMPACT_MOD:
            return _compactmod._queue_resize_recursive(self, widget)
        return None

    def _resize_nano_window_deferred(self):
        if _HAS_COMPACT_MOD:
            return _compactmod._resize_nano_window_deferred(self)
        return None

    def _resize_nano_window(self, _deferred=False):
        if _HAS_COMPACT_MOD:
            return _compactmod._resize_nano_window(self, _deferred)
        return None
    def _apply_compact_fixed_geometry(self, width, height):
        if _HAS_COMPACT_MOD:
            return _compactmod._apply_compact_fixed_geometry(self, width, height)
        return None
    def _resize_mini_window(self):
        if _HAS_COMPACT_MOD:
            return _compactmod._resize_mini_window(self)
        return None
    def _apply_nano_banner_state(self):
        if _HAS_COMPACT_MOD:
            return _compactmod._apply_nano_banner_state(self)
        return None

    def _nano_tooltip_text(self):
        if _HAS_COMPACT_MOD:
            return _compactmod._nano_tooltip_text(self)
        return None

    def _update_nano_tooltip(self):
        if _HAS_COMPACT_MOD:
            return _compactmod._update_nano_tooltip(self)
        return None
    def _nano_chrome_widgets(self):
        if _HAS_COMPACT_MOD:
            return _compactmod._nano_chrome_widgets(self)
        return None

    def _apply_nano_chrome(self, active):
        if _HAS_COMPACT_MOD:
            return _compactmod._apply_nano_chrome(self, active)
        return None

    def _restore_normal_ui_widgets(self):
        if _HAS_COMPACT_MOD:
            return _compactmod._restore_normal_ui_widgets(self)
        return None

    def _apply_compact_player_mode(self):
        if _HAS_COMPACT_MOD:
            return _compactmod._apply_compact_player_mode(self)
        return None

    def show_transparency_settings(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.show_transparency_settings(self, *args)
        return None

    def import_playlist_file(self, *args):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.import_playlist_file(self, *args)
        return None

    def export_playlist_file(self, *args):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.export_playlist_file(self, *args)
        return None

    def _parse_playlist_file(self, path):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._parse_playlist_file(self, path)
        return None

    def _write_m3u(self, path, paths):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._write_m3u(self, path, paths)
        return None

    def _write_pls(self, path, paths):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._write_pls(self, path, paths)
        return None

    def _load_recent_files(self):
        if _HAS_RECENT_MOD:
            return _recentmod._load_recent_files(self)
        return None

    def _save_recent_files(self):
        if _HAS_RECENT_MOD:
            return _recentmod._save_recent_files(self)
        return None

    def _push_recent_file(self, path):
        if _HAS_RECENT_MOD:
            return _recentmod._push_recent_file(self,path)
        return None

    def clear_recent_files(self, *args):
        if _HAS_RECENT_MOD:
            return _recentmod.clear_recent_files(self,*args)
        return None

    def _find_subtitle_list_index(self, *args, **kwargs):
        if _HAS_SUBTITLES_MOD:
            try:
                return _st_find_subtitle_list_index(self, *args, **kwargs)
            except Exception as e:
                print("find_subtitle_list_index:", e, file=sys.stderr)
        return -1


    def _play_recent_file(self, path):
        if _HAS_RECENT_MOD:
            return _recentmod._play_recent_file(self,path)
        return None

    def show_menu(self, button):
        if _HAS_MENUS_MOD:
            return _menumod.show_menu(self, button)
        return None


    def _on_menu_deactivate(self, menu):
        if _HAS_MENUS_MOD:
            return _menumod._on_menu_deactivate(self, menu)
        return None


    def _language_menu_toggled(self, menuitem, language):
        if _HAS_MENUS_MOD:
            return _menumod._language_menu_toggled(self, menuitem, language)
        return None


    def _on_hdr_tonemap_toggled(self, item):
        try:
            self.hdr_tonemap_enabled = bool(item.get_active())
        except Exception:
            self.hdr_tonemap_enabled = True
        try:
            import os
            os.environ["MYOSTOOX_HDR_TONEMAP"] = "auto" if self.hdr_tonemap_enabled else "off"
        except Exception:
            pass
        try:
            self.status_label.set_text(
                self.tr("Tone mapping HDR") + " : " +
                (self.tr("activé") if self.hdr_tonemap_enabled else self.tr("désactivé"))
            )
        except Exception:
            pass
        try:
            self._need_playbin_rebind = True
        except Exception:
            pass
        try:
            self.save_state()
        except Exception:
            pass

    def _performance_menu_toggled(self, menuitem, mode):
        if _HAS_MENUS_MOD:
            return _menumod._performance_menu_toggled(self, menuitem, mode)
        return None


    def _build_spectrum_menu_item(self):
        if _HAS_MENUS_MOD:
            return _menumod._build_spectrum_menu_item(self)
        return None


    def _build_media_track_menu_items(self):
        if _HAS_MENUS_MOD:
            return _menumod._build_media_track_menu_items(self)
        return None


    def _build_colorimetry_menu_item(self):
        if _HAS_MENUS_MOD:
            return _menumod._build_colorimetry_menu_item(self)
        return None


    def _build_audio_options_submenu(self):
        if _HAS_MENUS_MOD:
            return _menumod._build_audio_options_submenu(self)
        return None


    def _build_appearance_menu_item(self):
        if _HAS_MENUS_MOD:
            return _menumod._build_appearance_menu_item(self)
        return None


    def reset_appearance_defaults(self, *args):
        if _HAS_TOOLS_MOD:
            return _toolsmod.reset_appearance_defaults(self,*args)
        return None

    def _on_playlist_only_menu_toggled(self, menuitem):
        try:
            enabled = bool(menuitem.get_active())
        except Exception:
            return
        if enabled == bool(getattr(self, "playlist_only_mode", False)): return
        self.set_playlist_only_mode(enabled)

    def _on_playlist_only_maximize_toggled(self, menuitem):
        try:
            enabled = bool(menuitem.get_active())
        except Exception:
            return
        if not bool(getattr(self, "playlist_only_mode", False)): return
        if enabled == bool(getattr(self, "playlist_only_maximized", False)): return
        self.set_playlist_only_maximized(enabled)

    def set_playlist_only_mode(self, enabled):
        if enabled and bool(getattr(self, "pure_spectrum_mode", False)):
            try:
                self.pure_spectrum_mode = False
                self._apply_pure_spectrum_mode()
            except Exception:
                pass
        enabled = bool(enabled)
        self.playlist_only_mode = enabled
        if not enabled:
            if getattr(self, "playlist_only_maximized", False):
                self.set_playlist_only_maximized(False)
            if not bool(getattr(self, "is_fullscreen", False)):
                try: self._hide_fs_controls()
                except Exception: pass
            playing = bool(
                getattr(self, "is_playing", False)
                or getattr(self, "is_paused", False)
            )
            keep_video = playing and bool(getattr(self, "current_is_video", False))
            lyrics_on = bool(getattr(self, "lyrics_mode", False)) and bool(
                getattr(self, "lyrics_enabled", False)
            )
            if not keep_video and not lyrics_on:
                try:
                    self.current_is_video = False
                    self.show_video_area(False)
                except Exception:
                    pass
            else:
                try:
                    self.current_is_video = bool(keep_video)
                except Exception:
                    pass
        try:
            self._apply_playlist_only_mode()
        except Exception as e:
            print("playlist_only:", e, file=sys.stderr)
        if enabled and bool(getattr(self, "hide_playlist_mode", False)):
            self.hide_playlist_mode = False
            self._pure_video_prev_playlist_only = False
            try: self._apply_pure_video_opacity(False)
            except Exception: pass
        elif not enabled:
            if bool(getattr(self, "hide_playlist_mode", False)):
                try: self._apply_hide_playlist_mode()
                except Exception: pass
        try: self.save_state()
        except Exception: pass
        try:
            self.status_label.set_text(
                self.tr("Sans lecteur activé")
                if enabled
                else self.tr("Sans lecteur désactivé")
            )
        except Exception: pass
        if bool(getattr(self, "mini_player_mode", False)):
            try:
                self._apply_mini_banner_state()
            except Exception:
                pass

    def _query_live_video_dims(self):
        width = height = 0
        par_n = par_d = 1
        try:
            pipe = self._active_pipeline()
            if pipe is None:
                return None
            pad = None
            try:
                pad = pipe.emit("get-video-pad", 0)
            except Exception:
                pad = None
            if pad is None:
                try:
                    vs = getattr(self, "video_sink", None)
                    if vs is not None:
                        pad = vs.get_static_pad("sink")
                except Exception:
                    pad = None
            caps = None
            if pad is not None:
                caps = pad.get_current_caps()
                if caps is None:
                    caps = pad.query_caps(None)
            if caps is None or caps.is_empty():
                return None
            st = caps.get_structure(0)
            if st is None:
                return None
            ok, width = st.get_int("width")
            if not ok:
                width = 0
            ok, height = st.get_int("height")
            if not ok:
                height = 0
            try:
                ok, pn, pd = st.get_fraction("pixel-aspect-ratio")
                if ok and pn > 0 and pd > 0:
                    par_n, par_d = int(pn), int(pd)
            except Exception:
                pass
        except Exception:
            return None
        if width <= 0 or height <= 0:
            return None
        return (int(width), int(height), int(par_n), int(par_d))

    def _resolve_video_display_aspect(self):
        """Ratio d'affichage (largeur/hauteur) de l'image vidéo courante."""
        dims = getattr(self, "_current_video_dims", None)
        if not dims:
            dims = self._query_live_video_dims()
            if dims:
                self._current_video_dims = dims
        if not dims:
            path = getattr(self, "current_path", None)
            try:
                info = self._probe_video_info(path) if path else None
            except Exception:
                info = None
            if info and info.get("width") and info.get("height"):
                dims = (
                    int(info["width"]),
                    int(info["height"]),
                    int(info.get("par_n") or 1),
                    int(info.get("par_d") or 1),
                )
                self._current_video_dims = dims
        if dims:
            w, h, pn, pd = dims
            if w > 0 and h > 0 and pn > 0 and pd > 0:
                return (w * float(pn)) / (h * float(pd))
        return 16.0 / 9.0

    def _apply_pure_video_window_geometry(self, force_base=False):
        """Adapte la fenêtre fenêtrée au ratio réel de la vidéo.

        Taille ~55 % de la largeur moniteur, position conservée pour éviter les sauts
        après sortie du plein écran.
        """
        if not bool(getattr(self, "hide_playlist_mode", False)):
            return
        if getattr(self, "is_fullscreen", False):
            return
        try:
            if self.is_maximized():
                return
        except Exception:
            pass
        try:
            aspect = float(self._resolve_video_display_aspect())
            if aspect <= 0.05 or aspect > 20.0:
                aspect = 16.0 / 9.0
            mon_w = mon_h = 1280
            mon_x = mon_y = 0
            try:
                screen = self.get_screen()
                win = self.get_window()
                mon = 0
                if screen is not None and win is not None:
                    mon = screen.get_monitor_at_window(win)
                if screen is not None:
                    try:
                        geo = screen.get_monitor_workarea(mon)
                    except Exception:
                        geo = screen.get_monitor_geometry(mon)
                    mon_w = max(640, int(geo.width) - 32)
                    mon_h = max(360, int(geo.height) - 56)
                    mon_x = int(geo.x)
                    mon_y = int(geo.y)
            except Exception:
                pass
            base_w = int(round(mon_w * 0.55))
            base_w = max(640, min(base_w, mon_w))
            try:
                cur_w, cur_h = self.get_size()
            except Exception:
                cur_w, cur_h = base_w, int(round(base_w / aspect))
            try:
                cur_x, cur_y = self.get_position()
            except Exception:
                cur_x = cur_y = None
            if force_base or cur_w >= int(mon_w * 0.90) or cur_h >= int(mon_h * 0.90):
                target_w = base_w
            else:
                target_w = int(cur_w)
                if target_w < 480:
                    target_w = base_w
                if target_w > mon_w:
                    target_w = mon_w
            target_h = int(round(target_w / aspect))
            if target_h > mon_h:
                target_h = mon_h
                target_w = int(round(target_h * aspect))
            if target_w > mon_w:
                target_w = mon_w
                target_h = int(round(target_w / aspect))
            target_w = max(480, min(target_w, mon_w))
            target_h = max(270, min(target_h, mon_h))
            need_resize = abs(cur_w - target_w) > 6 or abs(cur_h - target_h) > 6
            if need_resize:
                self.resize(target_w, target_h)
            try:
                saved = getattr(self, "_pure_video_saved_pos", None)
                if force_base and saved is not None:
                    sx, sy = saved
                    nx = int(sx + (cur_w - target_w) / 2) if cur_w else sx
                    ny = int(sy + (cur_h - target_h) / 2) if cur_h else sy
                elif cur_x is not None and cur_y is not None and not force_base:
                    nx, ny = int(cur_x), int(cur_y)
                else:
                    nx = mon_x + max(0, (mon_w - target_w) // 2)
                    ny = mon_y + max(0, (mon_h - target_h) // 2)
                nx = max(mon_x, min(nx, mon_x + mon_w - target_w))
                ny = max(mon_y, min(ny, mon_y + mon_h - target_h))
                self.move(nx, ny)
            except Exception:
                pass
        except Exception as e:
            print("pure video geometry:", e, file=sys.stderr)

    def _refine_pure_video_client_aspect(self):
        """Assure que le paned vidéo occupe toute la hauteur (sans retoucher le ratio fenêtre)."""
        if not bool(getattr(self, "hide_playlist_mode", False)):
            return False
        if getattr(self, "is_fullscreen", False):
            return False
        try:
            paned = getattr(self, "content_paned", None)
            if paned is not None:
                ph = int(paned.get_allocated_height() or 0)
                if ph > 10:
                    paned.set_position(max(ph - 2, 1))
            va = getattr(self, "video_area", None)
            if va is not None:
                va.set_size_request(-1, -1)
        except Exception:
            pass
        return False

    def _schedule_pure_video_geometry(self, delay_ms=350):
        """Recalcule le cadre Pure vidéo quand les caps vidéo sont prêts."""
        if not bool(getattr(self, "hide_playlist_mode", False)):
            return
        if getattr(self, "is_fullscreen", False):
            return
        try:
            def _run():
                if not bool(getattr(self, "hide_playlist_mode", False)):
                    return False
                if getattr(self, "is_fullscreen", False):
                    return False
                try:
                    live = self._query_live_video_dims()
                    if live:
                        self._current_video_dims = live
                    self._apply_pure_video_window_geometry(force_base=False)
                    GLib.timeout_add(80, self._refine_pure_video_client_aspect)
                except Exception:
                    pass
                return False
            GLib.timeout_add(max(50, int(delay_ms)), _run)
        except Exception:
            pass

    def _apply_pure_video_opacity(self, enabled):
        try:
            if enabled:
                cur = 1.0
                try: cur = float(self.get_opacity())
                except Exception: pass
                target = 0.98
                if bool(getattr(self, "playlist_transparency", False)):
                    try:
                        self._pure_video_prev_opacity = cur
                    except Exception: pass
                else:
                    try:
                        self._pure_video_prev_opacity = cur
                    except Exception: pass
                    try: self.set_opacity(target)
                    except Exception: pass
            else:
                prev = getattr(self, "_pure_video_prev_opacity", None)
                if prev is not None and not bool(getattr(self, "playlist_transparency", False)):
                    try: self.set_opacity(float(prev))
                    except Exception: pass
                self._pure_video_prev_opacity = None
        except Exception: pass

    def _on_hide_playlist_menu_toggled(self, menuitem):
        try:
            self.set_hide_playlist_mode(bool(menuitem.get_active()))
        except Exception as e:
            print("hide_playlist menu:", e, file=sys.stderr)

    def _save_pre_pure_video_window(self):
        try:
            if getattr(self, "is_fullscreen", False):
                return
        except Exception:
            pass
        if bool(getattr(self, "hide_playlist_mode", False)):
            return
        if (
            bool(getattr(self, "playlist_only_maximized", False))
            and getattr(self, "_playlist_only_prev_size", None)
        ):
            self._pre_pure_video_size = tuple(self._playlist_only_prev_size)
            self._pre_pure_video_pos = getattr(self, "_playlist_only_prev_pos", None)
            return
        try:
            self._pre_pure_video_size = self.get_size()
        except Exception:
            self._pre_pure_video_size = None
        try:
            self._pre_pure_video_pos = self.get_position()
        except Exception:
            self._pre_pure_video_pos = None

    def _restore_pre_pure_video_window(self):
        """Restaure la fenêtre normale après Pure vidéo (pas le cadre vidéo)."""
        try:
            if getattr(self, "is_fullscreen", False):
                return
        except Exception:
            pass
        try:
            if self.is_maximized():
                return
        except Exception:
            pass
        sz = getattr(self, "_pre_pure_video_size", None)
        try:
            if not sz or int(sz[0]) < 500 or int(sz[1]) < 320:
                try:
                    sz = (int(self._ui_s(900)), int(self._ui_s(600)))
                except Exception:
                    sz = (900, 600)
            self.resize(int(sz[0]), int(sz[1]))
        except Exception:
            pass
        pos = getattr(self, "_pre_pure_video_pos", None)
        if pos is not None:
            try:
                self.move(int(pos[0]), int(pos[1]))
            except Exception:
                pass
        try:
            GLib.idle_add(self._apply_video_playlist_split)
        except Exception:
            pass

    def set_hide_playlist_mode(self, enabled, restore_playlist_only=None):
        if enabled and bool(getattr(self, "pure_spectrum_mode", False)):
            try:
                self.pure_spectrum_mode = False
                self._apply_pure_spectrum_mode()
            except Exception:
                pass
        enabled = bool(enabled)
        if enabled:
            path = getattr(self, "current_path", None)
            try:
                if path and is_pure_audio_file(path) and not (
                    is_video_file(path) or is_dvd(path) or is_bluray(path)
                ):
                    try:
                        self.status_label.set_text(
                            self.tr("Pure vidéo indisponible pour l'audio")
                        )
                    except Exception: pass
                    return
            except Exception: pass
            try:
                self._save_pre_pure_video_window()
            except Exception:
                pass
            self._pure_video_prev_playlist_only = bool(
                getattr(self, "playlist_only_mode", False)
            )
            if bool(getattr(self, "playlist_only_mode", False)):
                self.playlist_only_mode = False
                try:
                    if getattr(self, "playlist_only_maximized", False):
                        self.set_playlist_only_maximized(False)
                except Exception: pass
        else:
            prev_po = getattr(self, "_pure_video_prev_playlist_only", False)
            if restore_playlist_only is not None:
                prev_po = bool(restore_playlist_only)
            self.hide_playlist_mode = False
            try:
                self._apply_hide_playlist_mode()
            except Exception as e:
                print("hide_playlist:", e, file=sys.stderr)
            self._pure_video_prev_playlist_only = False
            try:
                self._restore_pre_pure_video_window()
            except Exception as e:
                print("restore pre pure:", e, file=sys.stderr)
            if prev_po:
                try:
                    self.set_playlist_only_mode(True)
                except Exception: pass
            try: self.save_state()
            except Exception: pass
            try:
                self.status_label.set_text(self.tr("Pure vidéo désactivé"))
            except Exception: pass
            return
        self.hide_playlist_mode = enabled
        try:
            self._apply_hide_playlist_mode()
        except Exception as e:
            print("hide_playlist:", e, file=sys.stderr)
        if enabled:
            try: self._apply_pure_video_window_geometry(force_base=True)
            except Exception: pass
            try: self._schedule_pure_video_geometry(280)
            except Exception: pass
            try: self._schedule_pure_video_geometry(900)
            except Exception: pass
        try: self.save_state()
        except Exception: pass
        try:
            self.status_label.set_text(
                self.tr("Pure vidéo activé")
                if enabled
                else self.tr("Pure vidéo désactivé")
            )
        except Exception: pass

    def _apply_hide_playlist_mode(self):
        if bool(getattr(self, "pure_spectrum_mode", False)):
            return
        if bool(getattr(self, "playlist_only_mode", False)):
            return
        enabled = bool(getattr(self, "hide_playlist_mode", False))
        for attr in ("playlist_box", "search_row", "search_entry", "visualizer", "playlist_scroll"):
            w = getattr(self, attr, None)
            if w is None: continue
            try:
                if enabled:
                    w.hide()
                else:
                    w.show()
            except Exception: pass
        if enabled:
            try:
                fw = self.get_focus()
                if fw is not None and not fw.get_visible():
                    self.set_focus(None)
            except Exception:
                pass
        if not getattr(self, "is_fullscreen", False):
            for attr in ("top_bar_wrap", "top_bar", "bottom_bar_wrap", "bottom_bar"):
                w = getattr(self, attr, None)
                if w is None: continue
                try:
                    if enabled:
                        w.hide()
                    else:
                        if attr in ("bottom_bar_wrap", "bottom_bar"):
                            try:
                                self._apply_metadata_panel_visibility()
                            except Exception:
                                w.show()
                        else:
                            w.show()
                except Exception: pass
        try:
            is_vid = bool(getattr(self, "current_is_video", False))
            lyrics_on = bool(getattr(self, "lyrics_mode", False)) and bool(
                getattr(self, "lyrics_enabled", False)
            )
            playing = bool(
                getattr(self, "is_playing", False)
                or getattr(self, "is_paused", False)
            )
            want_video = bool(enabled) or (is_vid and playing) or lyrics_on
            for attr in ("video_overlay", "video_area"):
                w = getattr(self, attr, None)
                if w is None:
                    continue
                if want_video:
                    w.show()
                    if attr == "video_overlay":
                        try:
                            w.show_all()
                        except Exception:
                            pass
                    if attr == "video_area":
                        try:
                            self.video_area.set_size_request(-1, -1)
                            self.video_area.queue_draw()
                        except Exception:
                            pass
                else:
                    w.hide()
            if not want_video and not enabled:
                try:
                    self.current_is_video = False
                except Exception:
                    pass
        except Exception:
            pass
        if enabled:
            try:
                GLib.timeout_add(200, lambda: (self._show_fs_controls() or False))
            except Exception:
                pass
        try:
            if enabled:
                if hasattr(self, "content_paned") and self.content_paned is not None:
                    try:
                        h = self.content_paned.get_allocated_height() or 600
                        self.content_paned.set_position(max(h - 2, 400))
                    except Exception: pass
                try:
                    self.video_area.set_size_request(-1, -1)
                except Exception:
                    pass
                try:
                    self._apply_pure_video_window_geometry(force_base=True)
                except Exception:
                    pass
                try:
                    self._schedule_pure_video_geometry(200)
                    self._schedule_pure_video_geometry(700)
                except Exception:
                    pass
                try:
                    GLib.timeout_add(250, self._refine_pure_video_client_aspect)
                except Exception:
                    pass
                try: self._apply_pure_video_opacity(True)
                except Exception: pass
            else:
                try: self._apply_pure_video_opacity(False)
                except Exception: pass
                try: self._apply_video_playlist_split()
                except Exception: pass
        except Exception: pass
        try: self.queue_resize()
        except Exception: pass

    def _apply_lyrics_transparent_surface(self):
        if _HAS_LYRICS_MOD:
            return _lyricsmod._apply_lyrics_transparent_surface(self)
        return None

    def _on_lyrics_transparent_toggled(self, menuitem):
        if _HAS_LYRICS_MOD:
            return _lyricsmod._on_lyrics_transparent_toggled(self, menuitem)
        return None

    def _playlist_only_monitor_geometry(self):
        try:
            screen = self.get_screen()
            win = self.get_window()
            mon = screen.get_monitor_at_window(win) if win is not None else 0
            return screen.get_monitor_geometry(mon)
        except Exception:
            return None

    def _playlist_only_remember_geometry(self):
        """Mémorise taille/position AVANT agrandissement (jamais une taille plein écran)."""
        geo = self._playlist_only_monitor_geometry()
        try:
            w, h = self.get_size()
        except Exception:
            w = h = 0
        try:
            x, y = self.get_position()
        except Exception:
            x = y = None
        try:
            wm_max = bool(self.is_maximized())
        except Exception:
            wm_max = False
        too_big = wm_max or (
            geo is not None
            and w >= int(geo.width) - 8
            and h >= int(geo.height) - 8
        )
        if w > 0 and h > 0 and not too_big:
            self._playlist_only_prev_size = (int(w), int(h))
            if x is not None and y is not None:
                self._playlist_only_prev_pos = (int(x), int(y))
            else:
                self._playlist_only_prev_pos = None
        else:
            self._playlist_only_prev_size = None
            self._playlist_only_prev_pos = None

    def _playlist_only_apply_maximized_geometry(self):
        geo = self._playlist_only_monitor_geometry()
        if geo is None:
            try: self.maximize()
            except Exception: pass
            return
        try:
            if self.is_maximized():
                self.unmaximize()
        except Exception: pass
        try: self.resize(int(geo.width), int(geo.height))
        except Exception: pass
        try: self.move(int(geo.x), int(geo.y))
        except Exception: pass

    def _playlist_only_restore_geometry(self, size=None, pos=None):
        """Restaure la taille d'avant (2 passes pour résister aux délais du WM)."""
        tid = getattr(self, "_playlist_only_restore_tid", 0) or 0
        if tid:
            try: GLib.source_remove(tid)
            except Exception: pass
            self._playlist_only_restore_tid = 0
        min_w = self._ui_s(700)
        min_h = self._ui_s(430)
        geo = self._playlist_only_monitor_geometry()
        w = h = None
        try:
            if size is not None and len(size) == 2:
                w, h = int(size[0]), int(size[1])
        except Exception:
            w = h = None
        if (
            not w or not h
            or w < min_w or h < min_h
            or (
                geo is not None
                and w >= int(geo.width) - 8
                and h >= int(geo.height) - 8
            )
        ):
            w, h = self._ui_s(950), self._ui_s(620)
            pos = None
        x = y = None
        try:
            if pos is not None and len(pos) == 2:
                x, y = int(pos[0]), int(pos[1])
        except Exception:
            x = y = None
        if geo is not None:
            if x is None or y is None:
                x = int(geo.x) + max(0, (int(geo.width) - w) // 2)
                y = int(geo.y) + max(0, (int(geo.height) - h) // 2)
            else:
                x = max(int(geo.x), min(x, int(geo.x) + int(geo.width) - w))
                y = max(int(geo.y), min(y, int(geo.y) + int(geo.height) - h))
        def _apply():
            if getattr(self, "playlist_only_maximized", False): return
            if getattr(self, "is_fullscreen", False): return
            if getattr(self, "mini_player_mode", False) or getattr(
                app, "nano_player_mode", False
            ):
                return
            try:
                if self.is_maximized():
                    self.unmaximize()
            except Exception: pass
            try: self.resize(int(w), int(h))
            except Exception: pass
            if x is not None and y is not None:
                try: self.move(int(x), int(y))
                except Exception: pass
        _apply()
        state = {"n": 0}
        def _tick():
            self._playlist_only_restore_tid = 0
            _apply()
            state["n"] += 1
            if state["n"] < 2:
                self._playlist_only_restore_tid = GLib.timeout_add(300, _tick)
            return False
        self._playlist_only_restore_tid = GLib.timeout_add(150, _tick)

    def set_playlist_only_maximized(self, enabled, force=False):
        enabled = bool(enabled)
        if enabled and not bool(getattr(self, "playlist_only_mode", False)): return
        prev = bool(getattr(self, "playlist_only_maximized", False))
        self.playlist_only_maximized = enabled
        try:
            if enabled and (not prev or force):
                already = bool(
                    force and getattr(self, "_playlist_only_prev_size", None)
                )
                if not already:
                    self._playlist_only_remember_geometry()
                    layer = str(getattr(self, "window_layer", "normal") or "normal")
                    if layer == "above" or (force and layer == "below"):
                        layer = "normal"
                    self._playlist_only_prev_layer = layer
                elif not getattr(self, "_playlist_only_prev_layer", None):
                    self._playlist_only_prev_layer = "normal"
                self.set_window_layer("below")
                self._playlist_only_apply_maximized_geometry()
            elif not enabled and prev:
                size = getattr(self, "_playlist_only_prev_size", None)
                pos = getattr(self, "_playlist_only_prev_pos", None)
                layer = getattr(self, "_playlist_only_prev_layer", None) or "normal"
                if layer == "above":
                    layer = "normal"
                self._playlist_only_prev_size = None
                self._playlist_only_prev_pos = None
                self._playlist_only_prev_layer = None
                self.set_window_layer(layer)
                self._playlist_only_restore_geometry(size, pos)
        except Exception as e:
            print("playlist_only maximize:", e, file=sys.stderr)
        try: self.save_state()
        except Exception: pass

    def _apply_playlist_only_mode(self):
        if bool(getattr(self, "pure_spectrum_mode", False)):
            return
        enabled = bool(getattr(self, "playlist_only_mode", False))
        compact = bool(getattr(self, "mini_player_mode", False)) or bool(
            getattr(self, "nano_player_mode", False)
        )
        if compact: return
        for attr in ("top_bar_wrap", "top_bar"):
            w = getattr(self, attr, None)
            if w is None: continue
            try:
                if enabled:
                    w.hide()
                else:
                    w.show()
            except Exception: pass
        is_vid = bool(getattr(self, "current_is_video", False))
        lyrics_on = bool(getattr(self, "lyrics_mode", False)) and bool(
            getattr(self, "lyrics_enabled", False)
        )
        playing = bool(
            getattr(self, "is_playing", False)
            or getattr(self, "is_paused", False)
        )
        show_media_area = lyrics_on or (is_vid and playing)
        if is_vid and not playing and not lyrics_on:
            try:
                self.current_is_video = False
            except Exception:
                pass
            is_vid = False
        for attr in ("video_overlay", "video_area"):
            w = getattr(self, attr, None)
            if w is None: continue
            try:
                if enabled and not show_media_area:
                    w.hide()
                elif show_media_area:
                    w.show()
                    if attr == "video_overlay":
                        try: w.show_all()
                        except Exception: pass
                    if lyrics_on and attr == "video_area":
                        try: w.set_size_request(-1, 120)
                        except Exception: pass
                else:
                    w.hide()
            except Exception: pass
        if enabled and is_vid:
            try:
                self._cache_video_window_handle()
                self._apply_video_overlay_handle()
            except Exception: pass
        paned = getattr(self, "content_paned", None)
        if paned is not None:
            try:
                paned.set_no_show_all(False)
                paned.show()
                if enabled and not show_media_area:
                    paned.set_position(0)
                elif show_media_area:
                    try:
                        alloc = paned.get_allocation()
                        h = int(getattr(alloc, "height", 0) or 0)
                        if h > 80:
                            if enabled:
                                if lyrics_on and not is_vid:
                                    paned.set_position(max(80, h // 2))
                                else:
                                    paned.set_position(max(80, (h * 2) // 3))
                            else:
                                paned.set_position(max(0, h // 3))
                        else:
                            self._apply_video_playlist_split()
                    except Exception:
                        try: self._apply_video_playlist_split()
                        except Exception: pass
                else:
                    try:
                        alloc = paned.get_allocation()
                        h = int(getattr(alloc, "height", 0) or 0)
                        if h > 80:
                            paned.set_position(max(0, h // 3))
                    except Exception: pass
            except Exception: pass
        for attr in ("tree",):
            tree = getattr(self, attr, None)
            if tree is None: continue
            try: tree.set_headers_visible(not enabled)
            except Exception: pass
        for attr in ("search_row", "search_entry", "visualizer"):
            w = getattr(self, attr, None)
            if w is None: continue
            try: w.show()
            except Exception: pass
        if enabled:
            for attr in ("bottom_bar_wrap", "bottom_bar"):
                w = getattr(self, attr, None)
                if w is not None:
                    try: w.hide()
                    except Exception: pass
        else:
            try: self._apply_metadata_panel_visibility()
            except Exception: pass
        try: self.queue_resize()
        except Exception: pass
        try: self._apply_hide_playlist_mode()
        except Exception: pass

    def _pure_spectrum_media_allowed(self, path=None):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._pure_spectrum_media_allowed(self, path)
        return None

    def _restore_geometry_after_pure_spectrum(self):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._restore_geometry_after_pure_spectrum(self)
        return None

    def _pure_spectrum_target_size(self):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._pure_spectrum_target_size(self)
        return None

    def set_pure_spectrum_size(self, size):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod.set_pure_spectrum_size(self, size)
        return None

    def set_pure_spectrum_mode(self, enabled):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod.set_pure_spectrum_mode(self, enabled)
        return None


    def _on_pure_spectrum_menu_toggled(self, menuitem):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._on_pure_spectrum_menu_toggled(self, menuitem)
        return None

    def _apply_pure_spectrum_mode(self):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._apply_pure_spectrum_mode(self)
        return None

    def _pure_spectrum_kick_draw(self):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._pure_spectrum_kick_draw(self)
        return None


    def _on_pure_spectrum_button_press(self, widget, event):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._on_pure_spectrum_button_press(self, widget, event)
        return None

    def _pure_spectrum_now_playing_label(self):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._pure_spectrum_now_playing_label(self)
        return None

    def _hide_pure_spectrum_hover(self):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._hide_pure_spectrum_hover(self)
        return None

    def _show_pure_spectrum_hover(self, x_root=None, y_root=None):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._show_pure_spectrum_hover(self, x_root, y_root)
        return None

    def _on_pure_spectrum_enter(self, widget, event):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._on_pure_spectrum_enter(self, widget, event)
        return None

    def _on_pure_spectrum_leave(self, widget, event):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._on_pure_spectrum_leave(self, widget, event)
        return None

    def _on_pure_spectrum_motion(self, widget, event):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod._on_pure_spectrum_motion(self, widget, event)
        return None

    def _build_player_mode_submenu(self):
        if _HAS_MENUS_MOD:
            return _menumod._build_player_mode_submenu(self)
        return None


    def _build_playlist_context_menu(self, filename=None, multi=False):
        if _HAS_MENUS_MOD:
            return _menumod._build_playlist_context_menu(self, filename, multi)
        return None


    def _popup_playlist_menu_from_shortcut(self):
        if _HAS_MENUS_MOD:
            return _menumod._popup_playlist_menu_from_shortcut(self)
        return None


    def _lastfm_call(self, params, secret):
        if _HAS_SCROBBLER_MOD:
            return _scrobmod._lastfm_call(self, params, secret)
        return None

    def show_scrobbling_dialog(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.show_scrobbling_dialog(self, *args)
        return None

    def _scrobble_payload(self, path):
        if _HAS_SCROBBLER_MOD:
            return _scrobmod._scrobble_payload(self, path)
        return None

    def _scrobble_send_async(self, kind, artist, title, album, duration=0):
        if _HAS_SCROBBLER_MOD:
            return _scrobmod._scrobble_send_async(self, kind, artist, title, album, duration=0)
        return None

    def _scrobble_on_track_start(self, path):
        if _HAS_SCROBBLER_MOD:
            return _scrobmod._scrobble_on_track_start(self, path)
        return None

    def _scrobble_maybe_submit(self, path, position, duration):
        if _HAS_SCROBBLER_MOD:
            return _scrobmod._scrobble_maybe_submit(self, path, position, duration)
        return None

    def play_next_add(self, path):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.play_next_add(self, path)
        return None

    def play_next_pop(self):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod.play_next_pop(self)
        return None

    def _next_with_play_next_queue(self, auto=True):
        if _HAS_PLAYLIST_VIEW_MOD:
            return _plviewmod._next_with_play_next_queue(self, auto)
        return None
    def set_replaygain_mode(self, mode):
        if _HAS_EQUALIZER_MOD:
            return _eqmod.set_replaygain_mode(self, mode)
        return None
    def set_crossfade_seconds(self, seconds):
        if _HAS_CROSSFADE_MOD:
            return _crossfademod.set_crossfade_seconds(self, seconds)
        return None

    def set_gapless_enabled(self, enabled):
        self.gapless_enabled = bool(enabled)
        if not self.gapless_enabled:
            self._gapless_next = None
            self._gapless_next_for = None
        try: self.save_state()
        except Exception: pass
        try:
            self.status_label.set_text(
                self.tr("Gapless activé") if self.gapless_enabled
                else self.tr("Gapless désactivé")
            )
        except Exception: pass

    def _apply_current_volume(self):
        if _HAS_CROSSFADE_MOD:
            return _crossfademod._apply_current_volume(self)
        return None

    def _crossfade_half(self):
        if _HAS_CROSSFADE_MOD:
            return _crossfademod._crossfade_half(self)
        return 0.0

    def _fade_cancel(self):
        if _HAS_CROSSFADE_MOD:
            return _crossfademod._fade_cancel(self)
        return None

    def _fade_in_start(self):
        if _HAS_CROSSFADE_MOD:
            return _crossfademod._fade_in_start(self)
        return None

    def _crossfade_update_out(self, position):
        if _HAS_CROSSFADE_MOD:
            return _crossfademod._crossfade_update_out(self, position)
        return None

    def _auto_next_with_fade(self):
        if _HAS_CROSSFADE_MOD:
            return _crossfademod._auto_next_with_fade(self)
        return None

    def _transition_tick(self, position_seconds):
        if _HAS_CROSSFADE_MOD:
            return _crossfademod._transition_tick(self, position_seconds)
        return None

    def _gapless_cancel(self):
        if _HAS_TRANSPORT_MOD:
            return _transportmod._gapless_cancel(self)
        return None

    def _gapless_peek_next(self):
        if _HAS_TRANSPORT_MOD:
            return _transportmod._gapless_peek_next(self)
        return None

    def _gapless_refresh_next(self):
        if _HAS_TRANSPORT_MOD:
            return _transportmod._gapless_refresh_next(self)
        return None

    def _on_about_to_finish(self, playbin):
        # Thread GStreamer : pas d'accès GTK
        try:
            if not getattr(self, "gapless_enabled", False): return
            if getattr(self, "_custom_pipeline", None) is not None: return
            if getattr(self, "sleep_end_of_track", False): return
            if getattr(self, "_gapless_pending", None): return
            cur = getattr(self, "current_path", None)
            nxt = getattr(self, "_gapless_next", None)
            if not cur or not nxt: return
            if getattr(self, "_gapless_next_for", None) != cur: return
            uri = GLib.filename_to_uri(os.path.abspath(nxt), None)
            self._gapless_pending = nxt
            try:
                playbin.set_property("uri", uri)
            except Exception:
                self._gapless_pending = None
                raise
        except Exception as exc:
            print("gapless:", exc, file=sys.stderr)

    def _gapless_check_transition(self, position_seconds):
        if _HAS_TRANSPORT_MOD:
            return _transportmod._gapless_check_transition(self,position_seconds)
        return None

    def _gapless_commit(self):
        if _HAS_TRANSPORT_MOD:
            return _transportmod._gapless_commit(self)
        return None

    def cancel_sleep_timer(self):
        if _HAS_SLEEP_MOD:
            return _sleepmod.cancel_sleep_timer(self)
        return None

    def set_sleep_timer(self, minutes=0, end_of_track=False):
        if _HAS_SLEEP_MOD:
            return _sleepmod.set_sleep_timer(self,minutes,end_of_track)
        return None

    def show_sleep_timer_dialog(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.show_sleep_timer_dialog(self, *args)
        return None

    def _list_pulse_sinks(self):
        if _HAS_AUDIO_OUTPUT_MOD:
            return _audiomod._list_pulse_sinks(self)
        return [("", self.tr("Automatique (défaut)"))]

    def _apply_audio_sink(self, sink_name):
        if _HAS_AUDIO_OUTPUT_MOD:
            return _audiomod._apply_audio_sink(self, sink_name)
        return False

    def show_audio_device_dialog(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.show_audio_device_dialog(self, *args)
        return None

    def show_crossfade_dialog(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.show_crossfade_dialog(self, *args)
        return None

    def factory_reset_and_quit(self):
        if _HAS_TOOLS_MOD:
            return _toolsmod.factory_reset_and_quit(self)
        return None

    def set_window_layer(self, layer):
        if _HAS_WINDOW_PLACEMENT_MOD:
            return _wpmod.set_window_layer(self, layer)
        return None

    def _apply_window_layer(self):
        if _HAS_WINDOW_PLACEMENT_MOD:
            return _wpmod._apply_window_layer(self)
        return None

    def toggle_window_borders(self, menuitem):
        enabled = bool(menuitem.get_active())
        self.window_borders = enabled
        try:
            self.set_decorated(enabled)
        except Exception as e:
            print("window borders:", e, file=sys.stderr)
        try: self._update_undecorated_move_hint()
        except Exception: pass
        try: self.save_state()
        except Exception: pass
        try:
            self.status_label.set_text(
                self.tr("Bordures activées")
                if enabled
                else self.tr("Bordures désactivées")
            )
        except Exception: pass

    def _update_undecorated_move_hint(self):
        tip = None
        if not bool(getattr(self, "window_borders", True)):
            tip = self.tr(
                "Cliquer ici pour déplacer la fenêtre (clic gauche ou droit)"
            )
        for attr in (
            "top_bar_wrap",
            "top_bar",
            "time_label",
            "bottom_bar_wrap",
            "bottom_bar",
            "bottom_title",
            "bottom_artist",
            "bottom_album",
        ):
            w = getattr(self, attr, None)
            if w is None: continue
            try: w.set_tooltip_text(tip)
            except Exception: pass
    def _on_chrome_press_for_move(self, widget, event):
        if bool(getattr(self, "window_borders", True)): return False
        try:
            if event.type != Gdk.EventType.BUTTON_PRESS: return False
        except Exception:
            return False
        if int(getattr(event, "button", 0) or 0) not in (1, 2, 3): return False
        try:
            if isinstance(widget, (Gtk.Button, Gtk.Scale, Gtk.Entry, Gtk.Switch)): return False
        except Exception: pass
        try:
            self.begin_move_drag(
                int(event.button),
                int(event.x_root),
                int(event.y_root),
                int(event.time),
            )
            return True
        except Exception as e:
            print("begin_move_drag:", e, file=sys.stderr)
            return False

    def _on_transparency_menu_toggled(self, menuitem):
        try:
            enabled = bool(menuitem.get_active())
        except Exception:
            return
        if enabled == bool(getattr(self, "playlist_transparency", False)): return
        self.toggle_playlist_transparency(enabled)

    def _on_metadata_panel_menu_toggled(self, menuitem):
        if _HAS_METADATA_PANEL_MOD:
            return _metapanelmod._on_metadata_panel_menu_toggled(self, menuitem)
        return None

    def _apply_metadata_panel_visibility(self):
        if _HAS_METADATA_PANEL_MOD:
            return _metapanelmod._apply_metadata_panel_visibility(self)
        return None

    def toggle_playlist_transparency(self, menuitem=None):
        if isinstance(menuitem, bool):
            enabled = menuitem
        elif menuitem is not None and hasattr(menuitem, "get_active"):
            enabled = bool(menuitem.get_active())
        else:
            enabled = not bool(getattr(self, "playlist_transparency", False))
        if enabled == bool(getattr(self, "playlist_transparency", False)):
            try: self._apply_playlist_transparency()
            except Exception: pass
            return
        self.playlist_transparency = enabled
        self._apply_playlist_transparency()
        try: self.save_state()
        except Exception: pass
        try:
            self.status_label.set_text(
                self.tr("Transparence activée")
                if enabled
                else self.tr("Transparence désactivée")
            )
        except Exception: pass

    def _init_rgba_visual(self):
        if getattr(self, "_rgba_visual_ready", False): return bool(getattr(self, "_rgba_visual_ok", False))
        self._rgba_visual_ready = True
        self._rgba_visual_ok = False
        try:
            screen = None
            try:
                screen = self.get_screen()
            except Exception:
                screen = None
            if screen is None:
                screen = Gdk.Screen.get_default()
            if screen is None: return False
            visual = None
            try:
                if screen.is_composited():
                    visual = screen.get_rgba_visual()
            except Exception:
                visual = None
            if visual is None:
                try:
                    visual = screen.get_rgba_visual()
                except Exception:
                    visual = None
            if visual is not None:
                self.set_visual(visual)
                self._rgba_visual_ok = True
        except Exception as e:
            print("init rgba visual:", e, file=sys.stderr)
            self._rgba_visual_ok = False
        return self._rgba_visual_ok

    def _on_window_draw_transparent(self, widget, cr):
        if _HAS_WINDOW_STATE_MOD:
            return _wsmod._on_window_draw_transparent(self,widget,cr)
        return None

    def _playlist_rgba(self):
        rgba = Gdk.RGBA()
        try:
            palette = THEME_PALETTES.get(
                getattr(self, "theme_name", "sombre"),
                THEME_PALETTES.get("sombre", {}),
            )
            hx = (palette.get("tree_bg") or "#111315").lstrip("#")
            rgba.red = int(hx[0:2], 16) / 255.0
            rgba.green = int(hx[2:4], 16) / 255.0
            rgba.blue = int(hx[4:6], 16) / 255.0
        except Exception:
            rgba.red, rgba.green, rgba.blue = 0.07, 0.07, 0.08
        try:
            a = float(getattr(self, "playlist_transparency_opacity", 0.35))
        except Exception:
            a = 0.35
        rgba.alpha = max(0.0, min(1.0, a))
        return rgba

    def _set_widget_bg_alpha(self, widget, rgba_or_none, *, preserve_selection=False):
        if widget is None: return
        try:
            if preserve_selection:
                flags = (
                    Gtk.StateFlags.NORMAL,
                    Gtk.StateFlags.ACTIVE,
                    Gtk.StateFlags.PRELIGHT,
                    Gtk.StateFlags.FOCUSED,
                    Gtk.StateFlags.BACKDROP,
                )
            else:
                flags = (
                    Gtk.StateFlags.NORMAL,
                    Gtk.StateFlags.ACTIVE,
                    Gtk.StateFlags.PRELIGHT,
                    Gtk.StateFlags.SELECTED,
                    Gtk.StateFlags.FOCUSED,
                    Gtk.StateFlags.BACKDROP,
                )
        except Exception:
            flags = (Gtk.StateFlags.NORMAL,)
        for st in flags:
            try: widget.override_background_color(st, rgba_or_none)
            except Exception: pass
        if preserve_selection:
            try: widget.override_background_color(Gtk.StateFlags.SELECTED, None)
            except Exception: pass
            try:
                widget.override_background_color(
                    Gtk.StateFlags.SELECTED | Gtk.StateFlags.FOCUSED, None
                )
            except Exception: pass

    def _transparency_widget_chain(self):
        widgets = []
        for attr in (
            "tree",
            "playlist_box",
            "playlist_scroll",
            "content_paned",
            "search_entry",
            "search_row",
            "nano_playlist_box",
            "nano_playlist_scroll",
            "nano_playlist_tree",
        ):
            w = getattr(self, attr, None)
            if w is not None and w not in widgets:
                widgets.append(w)
        try:
            tree = getattr(self, "tree", None)
            if tree is not None:
                parent = tree.get_parent()
                hops = 0
                while parent is not None and hops < 8:
                    if parent not in widgets:
                        widgets.append(parent)
                    if parent is getattr(self, "content_paned", None): break
                    try:
                        parent = parent.get_parent()
                    except Exception:
                        break
                    hops += 1
        except Exception: pass
        try:
            child = self.get_child()
            if child is not None and child not in widgets:
                widgets.append(child)
        except Exception: pass
        return widgets

    def _apply_playlist_transparency(self):
        enabled = bool(getattr(self, "playlist_transparency", False))
        try: self._init_rgba_visual()
        except Exception: pass
        try:
            self.set_app_paintable(bool(enabled and getattr(self, "_rgba_visual_ok", False)))
        except Exception:
            try: self.set_app_paintable(enabled)
            except Exception: pass
        if not getattr(self, "_transparency_draw_connected", False):
            try:
                self.connect("draw", self._on_window_draw_transparent)
                self._transparency_draw_connected = True
            except Exception: pass
        try: self.build_css()
        except Exception: pass
        rgba = self._playlist_rgba() if enabled else None
        clear = Gdk.RGBA(red=0, green=0, blue=0, alpha=0) if enabled else None
        for w in self._transparency_widget_chain():
            try:
                ctx = w.get_style_context()
                if enabled:
                    ctx.add_class("playlist-transparent")
                else:
                    ctx.remove_class("playlist-transparent")
                    ctx.remove_class("content-transparent")
            except Exception: pass
            try:
                if not enabled:
                    self._set_widget_bg_alpha(w, None)
                elif w is getattr(self, "tree", None):
                    self._set_widget_bg_alpha(w, rgba, preserve_selection=True)
                    try:
                        palette = THEME_PALETTES.get(
                            getattr(self, "theme_name", "sombre"),
                            THEME_PALETTES.get("sombre", {}),
                        )
                        sel = Gdk.RGBA()
                        hx = (palette.get("tree_sel_bg") or "#30404a").lstrip("#")
                        sel.red = int(hx[0:2], 16) / 255.0
                        sel.green = int(hx[2:4], 16) / 255.0
                        sel.blue = int(hx[4:6], 16) / 255.0
                        sel.alpha = 1.0
                        w.override_background_color(Gtk.StateFlags.SELECTED, sel)
                        w.override_background_color(
                            Gtk.StateFlags.SELECTED | Gtk.StateFlags.FOCUSED, sel
                        )
                        fg = Gdk.RGBA()
                        hx2 = (palette.get("tree_sel_fg") or "#ffffff").lstrip("#")
                        fg.red = int(hx2[0:2], 16) / 255.0
                        fg.green = int(hx2[2:4], 16) / 255.0
                        fg.blue = int(hx2[4:6], 16) / 255.0
                        fg.alpha = 1.0
                        w.override_color(Gtk.StateFlags.SELECTED, fg)
                        w.override_color(
                            Gtk.StateFlags.SELECTED | Gtk.StateFlags.FOCUSED, fg
                        )
                    except Exception: pass
                elif w is getattr(self, "search_entry", None) or w is getattr(self, "search_row", None):
                    self._set_widget_bg_alpha(w, clear)
                    try:
                        for st in (
                            Gtk.StateFlags.NORMAL,
                            Gtk.StateFlags.ACTIVE,
                            Gtk.StateFlags.PRELIGHT,
                            Gtk.StateFlags.SELECTED,
                            Gtk.StateFlags.FOCUSED,
                            Gtk.StateFlags.BACKDROP,
                            Gtk.StateFlags.INSENSITIVE,
                        ):
                            w.override_background_color(st, clear)
                    except Exception: pass
                elif w is getattr(self, "playlist_scroll", None) or w is getattr(self, "playlist_box", None):
                    self._set_widget_bg_alpha(w, rgba)
                    try:
                        if w is getattr(self, "playlist_scroll", None):
                            child = w.get_child()
                            if child is not None:
                                self._set_widget_bg_alpha(child, rgba)
                    except Exception: pass
                else:
                    self._set_widget_bg_alpha(w, clear)
            except Exception: pass
        for attr in ("top_bar", "bottom_bar"):
            w = getattr(self, attr, None)
            if w is None: continue
            try: self._set_widget_bg_alpha(w, None)
            except Exception: pass
        try: self.queue_draw()
        except Exception: pass
        for attr in ("tree", "playlist_scroll", "playlist_box", "content_paned"):
            w = getattr(self, attr, None)
            if w is None: continue
            try: w.queue_draw()
            except Exception: pass

    def toggle_desktop_notifications(self, menuitem):
        if _HAS_NOTIFICATIONS_MOD:
            return _notifmod.toggle_desktop_notifications(self,menuitem)
        return None

    def show_spectrum_colors(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.show_spectrum_colors(self, *args)
        return None

    def _translate_color_chooser_labels(self, dialog):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod._translate_color_chooser_labels(self, dialog)
        return None
    def show_spectrum_sync(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.show_spectrum_sync(self, *args)
        return None

    def toggle_spectrum(self, menuitem):
        if _HAS_SPECTRUM_MOD:
            return _spectrummod.toggle_spectrum(self, menuitem)
        return None

    def toggle_subtitles(self, menuitem):
        self.set_subtitles_enabled(menuitem.get_active())
        if self.subtitles_enabled:
            self.status_label.set_text(self.tr("Sous-titres activés"))
            if self._custom_pipeline is None:
                GLib.timeout_add(300, self._deferred_refresh_subtitles)
        else:
            self.current_subtitle_index = -1
            self.status_label.set_text(self.tr("Sous-titres désactivés"))

    def _translate_about_dialog_buttons(self, dialog):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod._translate_about_dialog_buttons(self, dialog)
        return None

    def _hide_about_license_button(self, dialog):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod._hide_about_license_button(self, dialog)
        return None

    def show_about(self, *args):
        if _HAS_DIALOGS_MOD:
            return _dialogsmod.show_about(self, *args)
        return None

    def on_destroy(self, *args):
        try: self._screensaver_shutdown()
        except Exception: pass
        try: self._hide_pure_spectrum_hover()
        except Exception: pass
        try:
            self._resume_save_current(force=True)
        except Exception:
            pass
        self._app_closing = True
        try:
            if getattr(self, "_recording", False):
                self._stop_recording(show_save_dialog=True)
        except Exception: pass
        try: self._destroy_record_pipeline()
        except Exception: pass
        try: self._stop_mini_title_scroll()
        except Exception: pass
        for attr in (
            "_position_timeout_id",
            "_visualizer_timeout_id",
            "_idle_trim_timeout_id",
            "_size_allocate_timer",
            "_seek_release_timeout_id",
            "_seek_coalesce_id",
            "_osd_timeout_id",
            "_cursor_hide_timeout_id",
            "_fs_toast_tl_timeout",
            "_fs_toast_tr_timeout",
            "_mini_title_scroll_id",
            "_disk_meta_save_id",
            "_selection_info_timeout_id",
            "_transparency_css_timeout_id",
            "_playlist_only_restore_tid",
            "_fade_in_tid",
            "_fs_autohide_tid",
            "_fs_leave_tid",
            "_fs_fade_tid",
            "_fs_ptr_watch_tid",
        ):
            tid = getattr(self, attr, 0) or 0
            if tid:
                try: GLib.source_remove(tid)
                except Exception: pass
                try: setattr(self, attr, 0)
                except Exception: pass
        for attr in ("_main_popup_menu", "_playlist_context_menu"):
            m = getattr(self, attr, None)
            if m is not None:
                try: m.destroy()
                except Exception: pass
                try: setattr(self, attr, None)
                except Exception: pass
        for attr in (
            "pitch_window",
            "eq_window",
            "colorimetry_window",
            "speed_window",
            "spectrum_sync_window",
            "sound_settings_window",
            "fs_controls",
            "fs_toast_tl",
            "fs_toast_tr",
        ):
            w = getattr(self, attr, None)
            if w is not None:
                try: w.destroy()
                except Exception: pass
        try:
            if not getattr(self, "_factory_reset", False):
                self.save_playlist()
                self.save_state()
                self.save_radios()
                self.save_tvs()
                self.save_bouquets()
                self.save_associations()
                self._disk_meta_dirty = True
                self._save_disk_meta_cache()
        except Exception as e:
            print("save on destroy:", e, file=sys.stderr)
        try:
            self._discoverer = None
        except Exception: pass
        try: trim_memory(force=True, full=True)
        except Exception: pass
        try:
            if getattr(self, "_mpris_owner_id", 0):
                Gio.bus_unown_name(self._mpris_owner_id)
                self._mpris_owner_id = 0
        except Exception: pass
        try: self._destroy_custom_pipeline()
        except Exception: pass
        try:
            if getattr(self, "bus", None) is not None:
                try: self.bus.remove_signal_watch()
                except Exception: pass
        except Exception: pass
        try:
            self.player.set_state(Gst.State.NULL)
            self.player.get_state(100 * Gst.MSECOND)
        except Exception: pass
        try: self.player.set_property("video-sink", None)
        except Exception: pass
        try:
            if self.video_sink is not None:
                self.video_sink.set_state(Gst.State.NULL)
                self.video_sink = None
        except Exception: pass
        try:
            self._pause_pixbuf = None
            self.reset_spectrum()
        except Exception: pass
        owns_instance = getattr(self, "_instance_lock_fd", None) is not None
        try:
            sock = getattr(self, "instance_socket", None)
            if sock is not None:
                self.instance_socket = None
                try: sock.close()
                except Exception: pass
        except Exception: pass
        if owns_instance:
            try:
                if os.path.exists(SOCKET_FILE):
                    os.unlink(SOCKET_FILE)
            except Exception: pass
            lock_fd = self._instance_lock_fd
            self._instance_lock_fd = None
            try: fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
            except Exception: pass
            try: lock_fd.close()
            except Exception: pass
        Gtk.main_quit()

def parse_cli_media_files(argv):
    files = []
    seen = set()
    for argument in argv:
        if not argument or argument.startswith("-"): continue
        path = argument
        if path.startswith("file://"):
            try:
                path = GLib.filename_from_uri(path)[0]
            except Exception:
                continue
        elif path.startswith(STREAM_SCHEMES):
            if path not in seen:
                seen.add(path)
                files.append(path)
            continue
        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isfile(path): continue
        if not (is_audio_file(path) or is_video_file(path)): continue
        if path in seen: continue
        seen.add(path)
        files.append(path)
    return files

def forward_to_existing_instance(files, attempts=1, delay=0.05):
    if files:
        payload = ("\n".join(files) + "\n").encode("utf-8")
    else:
        payload = b"\n"
    for attempt in range(max(1, attempts)):
        client = None
        try:
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.settimeout(1.5)
            client.connect(SOCKET_FILE)
            client.sendall(payload)
            try: client.shutdown(socket.SHUT_WR)
            except Exception: pass
            try:
                client.settimeout(0.2)
                client.recv(16)
            except Exception: pass
            client.close()
            return True
        except Exception:
            if client is not None:
                try: client.close()
                except Exception: pass
            if attempt + 1 < attempts:
                time.sleep(delay)
    return False

def acquire_instance_lock():
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
    except Exception as exc:
        print("Impossible de créer le répertoire de config :", exc, file=sys.stderr)
    try:
        fd = open(LOCK_FILE, "a+", encoding="utf-8")
    except Exception as exc:
        print("Impossible d'ouvrir le verrou d'instance :", exc, file=sys.stderr)
        return None
    try:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError) as exc:
        if getattr(exc, "errno", None) not in (
            errno.EACCES,
            errno.EAGAIN,
            errno.EWOULDBLOCK,
            None,
        ) and not isinstance(exc, BlockingIOError):
            print("fcntl.flock :", exc, file=sys.stderr)
        try: fd.close()
        except Exception: pass
        return None
    try:
        fd.seek(0)
        fd.truncate()
        fd.write(str(os.getpid()))
        fd.flush()
    except Exception: pass
    return fd

def main():
    files = parse_cli_media_files(sys.argv[1:])
    if forward_to_existing_instance(files, attempts=4, delay=0.05): return
    lock_fd = acquire_instance_lock()
    if lock_fd is None:
        if forward_to_existing_instance(files, attempts=60, delay=0.05): return
        print(
            "Myostoox : une instance semble déjà active mais ne répond pas. "
            "Abandon pour éviter un doublon.",
            file=sys.stderr,
        )
        return
    try: GLib.set_prgname("myostoox")
    except Exception: pass
    try:
        Gst.init(None)
        apply_safe_gstreamer_ranks()
    except Exception: pass
    try:
        logo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
        if os.path.isfile(logo):
            Gtk.Window.set_default_icon_from_file(logo)
    except Exception: pass
    window = Myostoox()
    window._instance_lock_fd = lock_fd
    try:
        if os.environ.get("MYOSTOOX_MEMLOG", "").strip() in ("1", "true", "yes"):
            _memlog_tick.window = window
            GLib.timeout_add_seconds(30, _memlog_tick)
            print("[memlog] enabled (every 30s)", flush=True)
    except Exception: pass
    try:
        cache_root = GLib.get_user_cache_dir()
        rec_dir = os.path.join(cache_root or os.path.expanduser("~/.cache"), APP_NAME)
        if os.path.isdir(rec_dir):
            for name in os.listdir(rec_dir):
                if name.startswith("myostoox_rec_") and name.endswith(".mp3"):
                    try: os.unlink(os.path.join(rec_dir, name))
                    except Exception: pass
    except Exception: pass
    if not window.start_single_instance_server():
        print(
            "Myostoox : socket d'instance indisponible "
            "(les ouvertures externes pourraient échouer).",
            file=sys.stderr,
        )
    window.show_all()
    try: window.present()
    except Exception: pass
    try: window.deiconify()
    except Exception: pass
    try: window._hide_nano_playlist_panel()
    except Exception: pass
    _place_tries = {"n": 0}
    def _startup_place():
        _place_tries["n"] += 1
        try:
            mapped = bool(window.get_mapped())
        except Exception:
            mapped = True
        if not mapped and _place_tries["n"] < 12:
            return True
        try: window._apply_window_placement()
        except Exception: pass
        try:
            window.deiconify()
            window.present()
        except Exception: pass
        return False
    try:
        GLib.idle_add(_startup_place)
    except Exception: pass
    try: window._apply_window_layer()
    except Exception: pass
    try: window._apply_playlist_only_mode()
    except Exception: pass
    try: window._apply_hide_playlist_mode()
    except Exception: pass
    try:
        if getattr(window, "pure_spectrum_mode", False) and not window._pure_spectrum_media_allowed():
            window.pure_spectrum_mode = False
        window._apply_pure_spectrum_mode()
    except Exception:
        pass
    try:
        if getattr(window, "playlist_only_maximized", False) and getattr(
            window, "playlist_only_mode", False
        ):
            window.set_playlist_only_maximized(True, force=True)
    except Exception: pass
    if files:
        try: window.cancel_pending_session_restore()
        except Exception: pass
        for filename in files:
            window.add_file(filename, save=False)
        window.save_playlist()
        if len(files) == 1:
            def _cli_play(p=files[0]):
                try:
                    window.play_file(p)
                except Exception as exc:
                    print("cli play:", exc, file=sys.stderr)
                return False
            GLib.idle_add(_cli_play)
    Gtk.main()
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("Erreur :", e, file=sys.stderr)
        raise
