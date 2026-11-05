#!/usr/bin/env python3
"""
Rinova Pro - Local Live Preview Server
"""

import os
import sys
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.api import RinovaAPI

api = RinovaAPI()

class RinovaRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.join(BASE_DIR, "frontend"), **kwargs)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            payload = {}

        response_data = {}

        try:
            if path == "/api/get-devices":
                response_data = api.get_devices()
            elif path == "/api/select-device":
                response_data = api.select_device(payload.get("serial", ""))
            elif path == "/api/get-device-info":
                response_data = api.get_device_info(payload.get("serial"))
            elif path == "/api/scan-storage":
                response_data = api.scan_storage(payload.get("serial"))
            elif path == "/api/execute-remediation":
                response_data = api.execute_remediation(payload.get("vector_ids", []), payload.get("serial"))
            elif path == "/api/list-device-packages":
                response_data = api.list_device_packages(payload.get("serial"))
            elif path == "/api/batch-package-action":
                response_data = api.batch_package_action(
                    payload.get("packages", []),
                    payload.get("action", "disable"),
                    payload.get("serial")
                )
            elif path == "/api/pair-wireless":
                response_data = api.pair_wireless(payload.get("address_port", ""), payload.get("pairing_code", ""))
            elif path == "/api/connect-wireless":
                response_data = api.connect_wireless(payload.get("address_port", ""))
            elif path == "/api/disconnect-device":
                response_data = api.disconnect_device(payload.get("address_port"))
            elif path == "/api/heartbeat":
                response_data = api.heartbeat()
            elif path == "/api/check-update":
                response_data = api.check_update()
            elif path == "/api/start-update-download":
                response_data = api.start_update_download(payload.get("download_url", ""), payload.get("version", ""))
            elif path == "/api/get-update-progress":
                response_data = api.get_update_progress()
            elif path == "/api/apply-update-and-restart":
                response_data = api.apply_update_and_restart()
            elif path == "/api/cancel-update-download":
                response_data = api.cancel_update_download()
            elif path == "/api/get-app-version":
                response_data = api.get_app_version()
            else:
                self.send_response(404)
                self.end_headers()
                return

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

def run_server(port=8080):
    server = HTTPServer(("0.0.0.0", port), RinovaRequestHandler)
    print(f"🚀 RINOVA PRO LIVE SERVER: http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)
