#!/usr/bin/env python3
import json
import os
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.environ.get("MT_EXPORTER_HOST", "0.0.0.0")
PORT = int(os.environ.get("MT_EXPORTER_PORT", "8787"))
AUTH_TOKEN = os.environ.get("MT_EXPORTER_TOKEN", "change-me")
STORAGE_DIR = os.environ.get("MT_EXPORTER_STORAGE_DIR", os.path.join(os.getcwd(), "storage"))
CLIENTS_DIR = os.path.join(STORAGE_DIR, "clients")
LATEST_PATH = os.path.join(STORAGE_DIR, "latest_snapshot.json")
HISTORY_PATH = os.path.join(STORAGE_DIR, "history.jsonl")


def ensure_dir(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, data):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, sort_keys=True)


def is_newer_snapshot(current_latest, received):
    current_ts = current_latest.get("last_recalculation_ts")
    new_ts = received.get("last_recalculation_ts")
    if not isinstance(current_ts, int):
        return True
    if new_ts > current_ts:
        return True
    if new_ts < current_ts:
        return False
    current_threshold = current_latest.get("legend_threshold")
    new_threshold = received.get("legend_threshold")
    if not isinstance(current_threshold, int):
        return True
    return new_threshold >= current_threshold


class Handler(BaseHTTPRequestHandler):
    server_version = "MTLegendExporterReceiver/0.1"

    def _reply(self, status_code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/mt/legend/ingest":
            self._reply(404, {"ok": False, "error": "not_found"})
            return

        auth_header = self.headers.get("Authorization", "")
        if AUTH_TOKEN and auth_header != "Bearer {0}".format(AUTH_TOKEN):
            self._reply(401, {"ok": False, "error": "unauthorized"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._reply(400, {"ok": False, "error": "bad_content_length"})
            return

        raw_body = self.rfile.read(content_length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception:
            self._reply(400, {"ok": False, "error": "bad_json"})
            return

        legend_threshold = payload.get("legend_threshold")
        last_recalc = payload.get("last_recalculation_ts")
        if not isinstance(legend_threshold, int) or not isinstance(last_recalc, int):
            self._reply(400, {"ok": False, "error": "missing_required_fields"})
            return

        received = dict(payload)
        received["received_at"] = utc_now()

        ensure_dir(STORAGE_DIR)
        ensure_dir(CLIENTS_DIR)

        client_key = payload.get("client_label") or str(payload.get("account_dbid") or "unknown")
        safe_client_key = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in client_key)

        write_json(os.path.join(CLIENTS_DIR, "{0}.json".format(safe_client_key)), received)

        current_latest = {}
        if os.path.isfile(LATEST_PATH):
            try:
                with open(LATEST_PATH, "r", encoding="utf-8") as stream:
                    current_latest = json.load(stream)
            except Exception:
                current_latest = {}

        if is_newer_snapshot(current_latest, received):
            write_json(LATEST_PATH, received)

        with open(HISTORY_PATH, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(received, ensure_ascii=False, sort_keys=True) + "\n")

        self._reply(200, {"ok": True})

    def log_message(self, fmt, *args):
        return


def main():
    ensure_dir(STORAGE_DIR)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print("Listening on http://{0}:{1}/mt/legend/ingest".format(HOST, PORT))
    server.serve_forever()


if __name__ == "__main__":
    main()
