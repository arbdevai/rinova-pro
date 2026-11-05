#!/usr/bin/env python3
"""
Rinova Pro - Desktop Application Entry Point
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.api import RinovaAPI

class DesktopAPIBridge:
    def __init__(self, window):
        self.window = window
        self.api = RinovaAPI()

    def get_devices(self, payload=None):
        return self.api.get_devices()

    def select_device(self, payload):
        return self.api.select_device(payload.get("serial", ""))

    def get_device_info(self, payload):
        return self.api.get_device_info(payload.get("serial"))

    def scan_storage(self, payload):
        return self.api.scan_storage(payload.get("serial"))

    def execute_remediation(self, payload):
        return self.api.execute_remediation(payload.get("vector_ids", []), payload.get("serial"))

    def list_device_packages(self, payload=None):
        serial = payload.get("serial") if payload else None
        return self.api.list_device_packages(serial)

    def batch_package_action(self, payload):
        return self.api.batch_package_action(
            payload.get("packages", []),
            payload.get("action", "disable"),
            payload.get("serial")
        )

    def pair_wireless(self, payload):
        return self.api.pair_wireless(payload.get("address_port", ""), payload.get("pairing_code", ""))

    def connect_wireless(self, payload):
        return self.api.connect_wireless(payload.get("address_port", ""))

    def heartbeat(self, payload=None):
        return self.api.heartbeat()

    def check_update(self, payload=None):
        return self.api.check_update()

    def start_update_download(self, payload):
        return self.api.start_update_download(payload.get("download_url", ""), payload.get("version", ""))

    def get_update_progress(self, payload=None):
        return self.api.get_update_progress()

    def apply_update_and_restart(self, payload=None):
        return self.api.apply_update_and_restart()

    def cancel_update_download(self, payload=None):
        return self.api.cancel_update_download()

    def get_app_version(self, payload=None):
        return self.api.get_app_version()

    def disconnect_device(self, payload=None):
        return self.api.disconnect_device(payload.get("address_port") if payload else None)

def main():
    try:
        import webview
    except ImportError:
        print("[!] PyWebView is not installed. To launch desktop GUI, run: pip install pywebview")
        print("[!] Or use the live preview server: python preview_server.py")
        sys.exit(1)

    html_path = os.path.join(BASE_DIR, "frontend", "index.html")

    window = webview.create_window(
        title="Rinova Pro",
        url=html_path,
        width=1100,
        height=750,
        min_size=(960, 620),
        frameless=False,
        easy_drag=False,
        background_color="#000000"
    )

    bridge = DesktopAPIBridge(window)
    window.expose(
        bridge.get_devices,
        bridge.select_device,
        bridge.get_device_info,
        bridge.scan_storage,
        bridge.execute_remediation,
        bridge.list_device_packages,
        bridge.batch_package_action,
        bridge.pair_wireless,
        bridge.connect_wireless,
        bridge.disconnect_device,
        bridge.heartbeat,
        bridge.check_update,
        bridge.start_update_download,
        bridge.get_update_progress,
        bridge.apply_update_and_restart,
        bridge.cancel_update_download,
        bridge.get_app_version
    )

    webview.start(debug=False)

if __name__ == "__main__":
    main()
