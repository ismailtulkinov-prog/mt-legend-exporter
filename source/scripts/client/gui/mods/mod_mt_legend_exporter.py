# -*- coding: utf-8 -*-
from __future__ import print_function

import json
import os
import sys
import threading
import time
import traceback

import adisp
import BigWorld
from Account import PlayerAccount
from gui.Scaleform.daapi.view.lobby.hangar.Hangar import Hangar
from helpers import dependency
from skeletons.connection_mgr import IConnectionManager
from skeletons.gui.game_control import IComp7Controller

try:
    import urllib2
except ImportError:
    import urllib.request as urllib2

MOD_ID = 'mt_legend_exporter'
MOD_VERSION = '0.1.9'
CONFIG_DIR = os.path.join(os.getcwd(), 'mods', 'configs', MOD_ID)
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')
LOG_PATH = os.path.join(CONFIG_DIR, 'exporter.log')
LOG_BACKUP_PATH = os.path.join(CONFIG_DIR, 'exporter.log.1')
SNAPSHOT_PATH = os.path.join(CONFIG_DIR, 'latest_snapshot.json')

DEFAULT_CONFIG = {
    'active_poll_interval_sec': 5,
    'enabled': True,
    'endpoint': 'http://77.91.77.218:18787/mt/legend/ingest',
    'auth_token': '2ed8bc656c66a03192899ecbcf4a3821',
    'client_label': '',
    'max_log_size_kb': 512,
    'poll_interval_sec': 300,
    'request_stall_timeout_sec': 8,
    'request_timeout_sec': 10,
    'send_only_on_change': True,
    'send_player_name': False,
    'debug': False
}


def _ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def _now_ts():
    return int(time.time())


class MTLegendExporter(object):
    def __init__(self):
        self._running = False
        self._request_in_flight = False
        self._callback_id = None
        self._config = {}
        self._last_sent_key = None
        self._last_local_key = None
        self._warned_no_endpoint = False
        self._warned_season_fallback = False
        self._api_logged = False
        self._request_started_ts = None
        self._request_stage = None
        self._request_seq = 0
        self._ui_last_update_ts = None
        self._ui_legend_threshold = None
        self._ui_legend_position = None
        self._ui_hooks_ready = False
        self._ui_hooks_logged = False

    def start(self, delay=45):
        self._load_config()
        if not self._config.get('enabled', True):
            self._log('disabled in config')
            return
        self._ensure_ui_hooks()
        self._running = True
        self._schedule_next(delay)
        self._log('started')

    def stop(self):
        self._running = False
        self._request_in_flight = False
        self._cancel_callback()
        self._log('stopped')

    def trigger_soon(self, delay=15):
        if not self._running:
            return
        self._ensure_ui_hooks()
        self._schedule_next(delay)

    def _cancel_callback(self):
        if self._callback_id is not None:
            try:
                BigWorld.cancelCallback(self._callback_id)
            except Exception:
                pass
        self._callback_id = None

    def _schedule_next(self, delay=None):
        if not self._running:
            return
        if delay is None:
            delay = max(60, int(self._config.get('poll_interval_sec', 300)))
        self._cancel_callback()
        self._callback_id = BigWorld.callback(float(delay), self._poll)

    def _load_config(self):
        _ensure_dir(CONFIG_DIR)
        if not os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH, 'wb') as stream:
                stream.write(json.dumps(DEFAULT_CONFIG, indent=2, sort_keys=True).encode('utf-8'))
        with open(CONFIG_PATH, 'rb') as stream:
            raw = stream.read()
        if not raw:
            self._config = dict(DEFAULT_CONFIG)
            return self._config
        loaded = json.loads(raw.decode('utf-8'))
        config = dict(DEFAULT_CONFIG)
        config.update(loaded)
        if not str(config.get('endpoint', '')).strip():
            config['endpoint'] = DEFAULT_CONFIG['endpoint']
        if not str(config.get('auth_token', '')).strip():
            config['auth_token'] = DEFAULT_CONFIG['auth_token']
        self._config = config
        return config

    def _rotate_log_if_needed(self):
        try:
            max_size_kb = int(self._config.get('max_log_size_kb', 512))
        except Exception:
            max_size_kb = 512
        max_size_bytes = max(128, max_size_kb) * 1024
        try:
            if not os.path.isfile(LOG_PATH) or os.path.getsize(LOG_PATH) < max_size_bytes:
                return
            if os.path.isfile(LOG_BACKUP_PATH):
                os.remove(LOG_BACKUP_PATH)
            os.rename(LOG_PATH, LOG_BACKUP_PATH)
        except Exception:
            pass

    def _log(self, message, force=False):
        prefix = '[%s %s] ' % (MOD_ID, MOD_VERSION)
        line = '%s%s' % (prefix, message)
        if force or self._config.get('debug', False):
            print(line)
        try:
            _ensure_dir(CONFIG_DIR)
            self._rotate_log_if_needed()
            with open(LOG_PATH, 'ab') as stream:
                stream.write(('[%s] %s\n' % (_now_ts(), line)).encode('utf-8'))
        except Exception:
            pass

    def _log_exception(self, title):
        self._log('%s\n%s' % (title, traceback.format_exc()), force=True)

    def _get_attr_value(self, obj, attr_names, default=None):
        for name in attr_names:
            try:
                value = getattr(obj, name)
            except Exception:
                continue
            if callable(value):
                try:
                    return value()
                except TypeError:
                    continue
            return value
        return default

    def _get_season_number(self, comp7_ctrl):
        return self._get_attr_value(
            comp7_ctrl,
            ('getActualSeasonNumber', 'getCurrentSeasonNumber', 'actualSeasonNumber', 'seasonNumber'),
            default=None
        )

    def _has_active_season(self, comp7_ctrl):
        value = self._get_attr_value(
            comp7_ctrl,
            ('hasActiveSeason', 'isSeasonActive', 'hasSeason', 'isActiveSeason'),
            default=None
        )
        if value is not None:
            return bool(value)

        season_number = self._get_season_number(comp7_ctrl)
        if season_number is not None:
            if not self._warned_season_fallback:
                self._warned_season_fallback = True
                self._log('Comp7Controller has no hasActiveSeason(), fallback to season_number=%s' % (
                    season_number,
                ), force=True)
            return bool(season_number)

        if not self._warned_season_fallback:
            self._warned_season_fallback = True
            self._log('Comp7Controller season state API not found, polling will continue without season precheck', force=True)
        return True

    def _get_elite_rank_percent(self, comp7_ctrl, leaderboard):
        return self._get_attr_value(
            leaderboard,
            ('getEliteRankPercent', 'eliteRankPercent'),
            default=self._get_attr_value(comp7_ctrl, ('getEliteRankPercent', 'eliteRankPercent'), default=None)
        )

    def _get_player_rating(self, comp7_ctrl):
        return self._get_attr_value(comp7_ctrl, ('getRating', 'rating'), default=None)

    def _get_player_is_elite(self, comp7_ctrl):
        return self._get_attr_value(comp7_ctrl, ('isElite', 'getIsElite'), default=None)

    def _log_comp7_api_once(self, comp7_ctrl, leaderboard):
        if self._api_logged or not self._config.get('debug', False):
            return
        self._api_logged = True
        try:
            ctrl_attrs = sorted(
                name for name in dir(comp7_ctrl) if not name.startswith('_')
            )
            leaderboard_attrs = sorted(
                name for name in dir(leaderboard) if not name.startswith('_')
            )
            self._log('Comp7Controller API: %s' % ', '.join(ctrl_attrs), force=True)
            self._log('Comp7 leaderboard API: %s' % ', '.join(leaderboard_attrs), force=True)
        except Exception:
            self._log_exception('failed to log Comp7 API surface')

    def _start_request(self, stage):
        self._request_in_flight = True
        self._request_started_ts = _now_ts()
        self._request_stage = stage
        self._request_seq += 1
        if self._config.get('debug', False):
            self._log('request started: seq=%s stage=%s' % (self._request_seq, stage), force=True)
        return self._request_seq

    def _set_request_stage(self, stage):
        self._request_stage = stage
        if self._config.get('debug', False):
            self._log('request progress: seq=%s stage=%s' % (self._request_seq, stage), force=True)

    def _is_current_request(self, request_seq):
        return request_seq == self._request_seq

    def _clear_request_state(self):
        self._request_in_flight = False
        self._request_started_ts = None
        self._request_stage = None

    def _is_request_stalled(self):
        if not self._request_in_flight or self._request_started_ts is None:
            return False
        timeout_sec = max(5, int(self._config.get('request_stall_timeout_sec', 20)))
        return (_now_ts() - self._request_started_ts) >= timeout_sec

    def _get_active_poll_delay(self):
        return max(3, int(self._config.get('active_poll_interval_sec', 5)))

    def _read_cached_leaderboard_state(self, leaderboard):
        last_update_ts = getattr(leaderboard, '_LeaderboardDataProvider__lastUpdateTimestamp', None)
        legend_threshold = getattr(leaderboard, '_LeaderboardDataProvider__eliteRankPointsThreshold', None)
        legend_position = getattr(leaderboard, '_LeaderboardDataProvider__eliteRankPositionThreshold', None)
        if not last_update_ts or legend_threshold is None:
            return None
        return (last_update_ts, legend_threshold, legend_position)

    def _try_use_cached_snapshot(self, comp7_ctrl, leaderboard):
        cached = self._read_cached_leaderboard_state(leaderboard)
        if cached is None:
            return False
        last_update_ts, legend_threshold, legend_position = cached
        payload = self._make_payload(
            comp7_ctrl=comp7_ctrl,
            last_update_ts=last_update_ts,
            legend_threshold=legend_threshold,
            legend_position=legend_position
        )
        self._save_snapshot(payload)
        self._send_payload_if_needed(payload)
        self._request_done('used cached leaderboard snapshot')
        return True

    def _make_ui_payload_if_ready(self):
        if self._ui_last_update_ts is None or self._ui_legend_threshold is None:
            return None
        comp7_ctrl = dependency.instance(IComp7Controller)
        if comp7_ctrl is None:
            return None
        return self._make_payload(
            comp7_ctrl=comp7_ctrl,
            last_update_ts=self._ui_last_update_ts,
            legend_threshold=self._ui_legend_threshold,
            legend_position=self._ui_legend_position
        )

    def _flush_ui_snapshot_if_ready(self, reason):
        payload = self._make_ui_payload_if_ready()
        if payload is None:
            return False
        self._save_snapshot(payload)
        self._send_payload_if_needed(payload)
        if self._config.get('debug', False):
            self._log(
                'ui snapshot captured: reason=%s threshold=%s update=%s position=%s' % (
                    reason,
                    self._ui_legend_threshold,
                    self._ui_last_update_ts,
                    self._ui_legend_position
                ),
                force=True
            )
        return True

    def on_ui_progression_timestamp(self, value):
        if value is None or value <= 0:
            return
        self._ui_last_update_ts = int(value)
        self._flush_ui_snapshot_if_ready('progression_timestamp')

    def on_ui_progression_threshold(self, value):
        if value is None or value <= 0:
            return
        self._ui_legend_threshold = int(value)
        self._flush_ui_snapshot_if_ready('progression_threshold')

    def on_ui_leaderboard_position(self, value):
        if value is None:
            return
        # UI stores zero-based index and -1 when missing.
        if int(value) < 0:
            self._ui_legend_position = None
        else:
            self._ui_legend_position = int(value) + 1
        self._flush_ui_snapshot_if_ready('leaderboard_position')

    def _patch_ui_model_setter(self, cls, method_name, capture_method_name, error_title):
        original_attr = '_mt_legend_exporter_orig_' + method_name
        if getattr(cls, original_attr, None) is not None:
            return True
        original = getattr(cls, method_name, None)
        if original is None:
            return False

        def _patched(instance, value, _original=original, _capture_method_name=capture_method_name, _error_title=error_title):
            result = _original(instance, value)
            try:
                getattr(g_exporter, _capture_method_name)(value)
            except Exception:
                g_exporter._log_exception(_error_title)
            return result

        setattr(cls, original_attr, original)
        setattr(cls, method_name, _patched)
        return True

    def _get_module_if_available(self, module_name):
        module = sys.modules.get(module_name)
        if module is not None:
            return module
        try:
            return __import__(module_name, fromlist=['*'])
        except Exception:
            return None

    def _ensure_ui_hooks(self):
        if self._ui_hooks_ready:
            return True

        progression_module = self._get_module_if_available(
            'comp7.gui.impl.gen.view_models.views.lobby.meta_view.pages.progression_model'
        )
        leaderboard_module = self._get_module_if_available(
            'comp7.gui.impl.gen.view_models.views.lobby.meta_view.pages.leaderboard_model'
        )

        if progression_module is None or leaderboard_module is None:
            if self._config.get('debug', False) and not self._ui_hooks_logged:
                self._ui_hooks_logged = True
                self._log('UI hook modules are not available yet, will retry later', force=True)
            return False

        progression_cls = getattr(progression_module, 'ProgressionModel', None)
        leaderboard_cls = getattr(leaderboard_module, 'LeaderboardModel', None)
        if progression_cls is None or leaderboard_cls is None:
            return False

        ok = True
        ok = self._patch_ui_model_setter(
            progression_cls,
            'setLastBestUserPointsValue',
            'on_ui_progression_threshold',
            'failed to capture progression threshold from UI'
        ) and ok
        ok = self._patch_ui_model_setter(
            progression_cls,
            'setLeaderboardUpdateTimestamp',
            'on_ui_progression_timestamp',
            'failed to capture progression timestamp from UI'
        ) and ok
        ok = self._patch_ui_model_setter(
            leaderboard_cls,
            'setLeaderboardUpdateTimestamp',
            'on_ui_progression_timestamp',
            'failed to capture leaderboard timestamp from UI'
        ) and ok
        ok = self._patch_ui_model_setter(
            leaderboard_cls,
            'setLastBestUserPosition',
            'on_ui_leaderboard_position',
            'failed to capture leaderboard position from UI'
        ) and ok

        if ok:
            self._ui_hooks_ready = True
            self._log('UI hooks installed', force=True)
        return ok

    def _poll(self):
        self._callback_id = None
        if not self._running:
            return
        try:
            self._load_config()
            self._ensure_ui_hooks()
            if not self._config.get('enabled', True):
                self._schedule_next()
                return
            comp7_ctrl = dependency.instance(IComp7Controller)
            leaderboard = getattr(comp7_ctrl, 'leaderboard', None) if comp7_ctrl is not None else None
            if self._request_in_flight:
                if comp7_ctrl is not None and leaderboard is not None and self._try_use_cached_snapshot(comp7_ctrl, leaderboard):
                    return
                if self._is_request_stalled():
                    self._log(
                        'request stalled: seq=%s stage=%s, resetting' % (
                            self._request_seq,
                            self._request_stage
                        ),
                        force=True
                    )
                    self._clear_request_state()
                else:
                    self._schedule_next(self._get_active_poll_delay())
                    return
            if comp7_ctrl is None:
                self._schedule_next()
                return
            if not comp7_ctrl.isEnabled() or not self._has_active_season(comp7_ctrl):
                self._schedule_next()
                return
            if leaderboard is None:
                self._request_done('leaderboard is unavailable')
                return
            self._log_comp7_api_once(comp7_ctrl, leaderboard)
            if self._try_use_cached_snapshot(comp7_ctrl, leaderboard):
                return
            if not hasattr(leaderboard, 'getLastUpdateTime'):
                self._request_done('leaderboard API has no getLastUpdateTime')
                return
            if self._request_in_flight:
                if self._is_request_stalled():
                    self._log(
                        'request stalled: seq=%s stage=%s, resetting' % (
                            self._request_seq,
                            self._request_stage
                        ),
                        force=True
                    )
                    self._clear_request_state()
                else:
                    self._schedule_next(self._get_active_poll_delay())
                    return
            request_seq = self._start_request('getLastUpdateTime')
            self._run_direct_request(request_seq, comp7_ctrl)
            self._schedule_next(self._get_active_poll_delay())
        except Exception:
            self._clear_request_state()
            self._log_exception('poll failed')
            self._schedule_next()

    @adisp.adisp_process
    def _run_direct_request(self, request_seq, comp7_ctrl):
        try:
            leaderboard = getattr(comp7_ctrl, 'leaderboard', None)
            if leaderboard is None:
                self._request_done('leaderboard is unavailable')
                return
            self._set_request_stage('getLastUpdateTime:yield')
            last_update_result = yield leaderboard.getLastUpdateTime()
            self._on_last_update(request_seq, last_update_result, comp7_ctrl)
        except Exception:
            self._log_exception('direct request failed')
            self._request_done()

    def _on_last_update(self, request_seq, result, comp7_ctrl):
        try:
            if not self._is_current_request(request_seq):
                return
            self._set_request_stage('getLastUpdateTime:result')
            last_update_ts, is_success = result
            if not is_success or last_update_ts is None:
                self._request_done('last update unavailable')
                return
            leaderboard = getattr(comp7_ctrl, 'leaderboard', None)
            if leaderboard is None or not hasattr(leaderboard, 'getLastEliteRating'):
                self._request_done('leaderboard API has no getLastEliteRating')
                return
            self._run_direct_request_rating(request_seq, last_update_ts, comp7_ctrl)
        except Exception:
            self._log_exception('last update callback failed')
            self._request_done()

    @adisp.adisp_process
    def _run_direct_request_rating(self, request_seq, last_update_ts, comp7_ctrl):
        try:
            if not self._is_current_request(request_seq):
                return
            leaderboard = getattr(comp7_ctrl, 'leaderboard', None)
            if leaderboard is None or not hasattr(leaderboard, 'getLastEliteRating'):
                self._request_done('leaderboard API has no getLastEliteRating')
                return
            self._set_request_stage('getLastEliteRating:yield')
            rating_result = yield leaderboard.getLastEliteRating()
            self._on_last_rating(request_seq, last_update_ts, rating_result, comp7_ctrl)
        except Exception:
            self._log_exception('last rating request failed')
            self._request_done()

    def _on_last_rating(self, request_seq, last_update_ts, result, comp7_ctrl):
        try:
            if not self._is_current_request(request_seq):
                return
            self._set_request_stage('getLastEliteRating:result')
            legend_threshold, is_success = result
            if not is_success or legend_threshold is None:
                self._request_done('legend threshold unavailable')
                return
            leaderboard = getattr(comp7_ctrl, 'leaderboard', None)
            if leaderboard is None or not hasattr(leaderboard, 'getLastElitePosition'):
                self._request_done('leaderboard API has no getLastElitePosition')
                return
            self._run_direct_request_position(request_seq, last_update_ts, legend_threshold, comp7_ctrl)
        except Exception:
            self._log_exception('last rating callback failed')
            self._request_done()

    @adisp.adisp_process
    def _run_direct_request_position(self, request_seq, last_update_ts, legend_threshold, comp7_ctrl):
        try:
            if not self._is_current_request(request_seq):
                return
            leaderboard = getattr(comp7_ctrl, 'leaderboard', None)
            if leaderboard is None or not hasattr(leaderboard, 'getLastElitePosition'):
                self._request_done('leaderboard API has no getLastElitePosition')
                return
            self._set_request_stage('getLastElitePosition:yield')
            position_result = yield leaderboard.getLastElitePosition()
            self._on_last_position(request_seq, last_update_ts, legend_threshold, position_result, comp7_ctrl)
        except Exception:
            self._log_exception('last position request failed')
            self._request_done()

    def _on_last_position(self, request_seq, last_update_ts, legend_threshold, result, comp7_ctrl):
        try:
            if not self._is_current_request(request_seq):
                return
            self._set_request_stage('getLastElitePosition:result')
            legend_position, is_success = result
            if not is_success:
                legend_position = None
            payload = self._make_payload(
                comp7_ctrl=comp7_ctrl,
                last_update_ts=last_update_ts,
                legend_threshold=legend_threshold,
                legend_position=legend_position
            )
            self._save_snapshot(payload)
            self._send_payload_if_needed(payload)
            self._request_done()
        except Exception:
            self._log_exception('last position callback failed')
            self._request_done()

    def _make_payload(self, comp7_ctrl, last_update_ts, legend_threshold, legend_position):
        player = BigWorld.player()
        leaderboard = getattr(comp7_ctrl, 'leaderboard', None)
        connection_mgr = None
        try:
            connection_mgr = dependency.instance(IConnectionManager)
        except Exception:
            connection_mgr = None
        account_dbid = getattr(connection_mgr, 'databaseID', None) or getattr(player, 'databaseID', None)
        player_name = getattr(player, 'name', None)
        payload = {
            'mod_id': MOD_ID,
            'mod_version': MOD_VERSION,
            'game': 'Mir Tankov',
            'publisher': 'Lesta',
            'client_label': self._config.get('client_label', ''),
            'account_dbid': account_dbid,
            'season_number': self._get_season_number(comp7_ctrl),
            'elite_rank_percent': self._get_elite_rank_percent(comp7_ctrl, leaderboard),
            'legend_threshold': legend_threshold,
            'legend_position_threshold': legend_position,
            'player_rating': self._get_player_rating(comp7_ctrl),
            'player_is_elite': self._get_player_is_elite(comp7_ctrl),
            'last_recalculation_ts': last_update_ts,
            'polled_at_ts': _now_ts()
        }
        if self._config.get('send_player_name', False) and player_name:
            payload['player_name'] = player_name
        return payload

    def _save_snapshot(self, payload):
        try:
            _ensure_dir(CONFIG_DIR)
            with open(SNAPSHOT_PATH, 'wb') as stream:
                stream.write(json.dumps(payload, indent=2, sort_keys=True).encode('utf-8'))
        except Exception:
            self._log_exception('failed to save local snapshot')

    def _send_payload_if_needed(self, payload):
        local_key = (
            payload.get('season_number'),
            payload.get('last_recalculation_ts'),
            payload.get('legend_threshold'),
            payload.get('legend_position_threshold')
        )
        if local_key != self._last_local_key:
            self._last_local_key = local_key
            self._log('new local snapshot: threshold=%s update=%s' % (
                payload.get('legend_threshold'), payload.get('last_recalculation_ts')
            ), force=True)
        endpoint = self._config.get('endpoint', '').strip()
        if not endpoint:
            if not self._warned_no_endpoint:
                self._warned_no_endpoint = True
                self._log('endpoint is empty, snapshot will only be saved locally', force=True)
            return
        should_send = True
        if self._config.get('send_only_on_change', True):
            should_send = local_key != self._last_sent_key
        if not should_send:
            return
        self._last_sent_key = local_key
        thread = threading.Thread(target=self._send_payload_worker, args=(payload,))
        try:
            thread.setDaemon(True)
        except Exception:
            pass
        thread.start()

    def _send_payload_worker(self, payload):
        try:
            data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')
            request = urllib2.Request(self._config.get('endpoint', '').strip(), data=data)
            request.add_header('Content-Type', 'application/json; charset=utf-8')
            auth_token = self._config.get('auth_token', '').strip()
            if auth_token:
                request.add_header('Authorization', 'Bearer %s' % auth_token)
            response = urllib2.urlopen(request, timeout=int(self._config.get('request_timeout_sec', 10)))
            status_code = getattr(response, 'getcode', lambda : 200)()
            try:
                response.read()
            except Exception:
                pass
            self._log('payload sent, status=%s threshold=%s' % (
                status_code, payload.get('legend_threshold')
            ), force=True)
        except Exception:
            self._log_exception('payload send failed')

    def _request_done(self, message=None):
        self._clear_request_state()
        if message and self._config.get('debug', False):
            self._log(message, force=True)
        self._schedule_next()


g_exporter = MTLegendExporter()

_old_account_on_become_player = PlayerAccount.onBecomePlayer
_old_account_on_become_non_player = PlayerAccount.onBecomeNonPlayer
_old_hangar_populate = Hangar._populate


def _patched_account_on_become_player(self, *args, **kwargs):
    result = _old_account_on_become_player(self, *args, **kwargs)
    try:
        g_exporter.start(delay=45)
    except Exception:
        g_exporter._log_exception('failed to start exporter on login')
    return result


def _patched_account_on_become_non_player(self, *args, **kwargs):
    try:
        g_exporter.stop()
    except Exception:
        g_exporter._log_exception('failed to stop exporter on logout')
    return _old_account_on_become_non_player(self, *args, **kwargs)


def _patched_hangar_populate(self, *args, **kwargs):
    result = _old_hangar_populate(self, *args, **kwargs)
    try:
        g_exporter.trigger_soon(delay=15)
    except Exception:
        g_exporter._log_exception('failed to trigger exporter from hangar')
    return result


PlayerAccount.onBecomePlayer = _patched_account_on_become_player
PlayerAccount.onBecomeNonPlayer = _patched_account_on_become_non_player
Hangar._populate = _patched_hangar_populate

g_exporter._log('module loaded', force=True)
