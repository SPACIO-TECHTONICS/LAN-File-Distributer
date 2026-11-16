# Copyright (C) 2026 Keshavanarayan and contributors
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

"""
On-Demand Web Manager for LAN File Distributor.
Uses Python 3 standard library only.
Terminates completely when closed to free all system RAM.
"""

import os
import sys
import json
import uuid
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from github_tracker import (
    load_config,
    save_config,
    check_for_all_updates,
    download_batch_updates,
    download_single_for_testing,
    download_batch_for_testing,
    launch_test_installer,
    approve_and_push_to_fleet,
    get_connected_clients
)

PORT = 5432
_base_dir = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
WEB_DIR = os.path.join(_base_dir, "web")
if not os.path.exists(WEB_DIR):
    WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
SERVER_INSTANCE = None


class ManagerAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the configuration dashboard and REST API."""

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, file_path, content_type):
        if not os.path.exists(file_path):
            self.send_error(404, "File not found.")
            return
        with open(file_path, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _read_json_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            raw = self.rfile.read(content_length).decode("utf-8")
            return json.loads(raw)
        return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path in ("/", "/index.html"):
            self._send_file(os.path.join(WEB_DIR, "index.html"), "text/html; charset=utf-8")
            return
        elif path == "/style.css":
            self._send_file(os.path.join(WEB_DIR, "style.css"), "text/css; charset=utf-8")
            return
        elif path == "/app.js":
            self._send_file(os.path.join(WEB_DIR, "app.js"), "application/javascript; charset=utf-8")
            return
        elif path == "/api/config":
            self._send_json(load_config())
            return
        elif path == "/api/check":
            self._send_json(check_for_all_updates())
            return
        elif path == "/api/clients":
            config = load_config()
            lan_folder = config.get("lan_folder", os.path.abspath("./lan_shared_files"))
            self._send_json(get_connected_clients(lan_folder))
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/config":
            payload = self._read_json_body()
            config = load_config()
            if "lan_folder" in payload:
                config["lan_folder"] = payload["lan_folder"]
            save_config(config)
            self._send_json({"status": "success", "config": config})
            return

        elif path == "/api/repos":
            payload = self._read_json_body()
            config = load_config()
            new_item = {
                "id": str(uuid.uuid4())[:8],
                "name": payload.get("name", "Untitled"),
                "type": payload.get("type", "app"),
                "parent_app": payload.get("parent_app") or None,
                "repo_url": payload.get("repo_url", ""),
                "asset_pattern": payload.get("asset_pattern", ".*\\.exe$"),
                "last_known_tag": "",
                "last_downloaded_tag": ""
            }
            config.setdefault("repositories", []).append(new_item)
            save_config(config)
            self._send_json({"status": "success", "item": new_item})
            return

        elif path == "/api/pull":
            payload = self._read_json_body()
            items_to_pull = payload.get("items", [])
            config = load_config()
            lan_folder = config.get("lan_folder", os.path.abspath("./lan_shared_files"))
            downloaded_count = download_batch_updates(items_to_pull, lan_folder)
            self._send_json({"status": "success", "count": downloaded_count})
            return

        elif path == "/api/test/download":
            payload = self._read_json_body()
            item_id = payload.get("id")
            items = payload.get("items", [])
            config = load_config()
            lan_folder = config.get("lan_folder", os.path.abspath("./lan_shared_files"))

            try:
                if item_id:
                    result = download_single_for_testing(item_id, lan_folder)
                    self._send_json({"status": "success", "result": result})
                elif items:
                    count = download_batch_for_testing(items, lan_folder)
                    self._send_json({"status": "success", "count": count})
                else:
                    self.send_error(400, "Missing id or items in payload")
            except Exception as err:
                self._send_json({"status": "error", "message": str(err)}, status=500)
            return

        elif path == "/api/test/launch":
            payload = self._read_json_body()
            item_id = payload.get("id")
            if not item_id:
                self.send_error(400, "Missing repo id")
                return

            config = load_config()
            lan_folder = config.get("lan_folder", os.path.abspath("./lan_shared_files"))
            try:
                result = launch_test_installer(item_id, lan_folder)
                self._send_json({"status": "success", "result": result})
            except Exception as err:
                self._send_json({"status": "error", "message": str(err)}, status=500)
            return

        elif path == "/api/test/approve":
            payload = self._read_json_body()
            item_id = payload.get("id")
            if not item_id:
                self.send_error(400, "Missing repo id")
                return

            config = load_config()
            lan_folder = config.get("lan_folder", os.path.abspath("./lan_shared_files"))
            try:
                result = approve_and_push_to_fleet(item_id, lan_folder)
                self._send_json({"status": "success", "result": result})
            except Exception as err:
                self._send_json({"status": "error", "message": str(err)}, status=500)
            return

        elif path == "/api/shutdown":
            self._send_json({"status": "shutting_down"})
            def terminate():
                print("[LAN File Distributor] Closing manager and releasing all memory...")
                if SERVER_INSTANCE:
                    SERVER_INSTANCE.shutdown()
                sys.exit(0)
            threading.Thread(target=terminate).start()
            return

        self.send_error(404, "Not Found")

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/repos":
            query = parse_qs(parsed.query)
            repo_id = query.get("id", [None])[0]
            if not repo_id:
                self.send_error(400, "Missing repo id")
                return

            config = load_config()
            config["repositories"] = [r for r in config.get("repositories", []) if r.get("id") != repo_id]
            save_config(config)
            self._send_json({"status": "success", "deleted_id": repo_id})
            return

        self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        # Suppress noisy standard request logs
        return


def start_manager():
    global SERVER_INSTANCE
    server_address = ("127.0.0.1", PORT)
    try:
        SERVER_INSTANCE = HTTPServer(server_address, ManagerAPIHandler)
    except OSError:
        server_address = ("127.0.0.1", 5433)
        SERVER_INSTANCE = HTTPServer(server_address, ManagerAPIHandler)

    active_url = f"http://127.0.0.1:{server_address[1]}"
    print(f"[LAN File Distributor] Manager running at: {active_url}")
    print("[LAN File Distributor] Press Ctrl+C or click 'Close & Free Memory' in the UI to terminate.")
    
    webbrowser.open(active_url)

    try:
        SERVER_INSTANCE.serve_forever()
    except KeyboardInterrupt:
        print("\n[LAN File Distributor] Manager closed. Memory released.")
    finally:
        SERVER_INSTANCE.server_close()


if __name__ == "__main__":
    start_manager()
