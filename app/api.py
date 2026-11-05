"""
Rinova Pro - Unified API Controller
"""

from typing import Dict, Any, List, Optional
from core.adb_client import ADBClient
from core.device import DeviceInspector
from core.analyzer import StorageAnalyzer
from core.optimizer import StorageOptimizer
from core.debloater import Debloater
from core.updater import UpdateManager
from core.version import APP_VERSION

class RinovaAPI:
    def __init__(self):
        self.adb = ADBClient()
        self.device_inspector = DeviceInspector(self.adb)
        self.storage_analyzer = StorageAnalyzer(self.adb)
        self.storage_optimizer = StorageOptimizer(self.adb)
        self.debloater = Debloater(self.adb)
        self.updater = UpdateManager()

    def get_devices(self) -> List[Dict[str, Any]]:
        return self.adb.list_devices()

    def heartbeat(self) -> Dict[str, Any]:
        return self.adb.get_heartbeat()

    def select_device(self, serial: str) -> Dict[str, Any]:
        self.adb.selected_device = serial
        return {"success": True, "selected": serial}

    def get_device_info(self, serial: Optional[str] = None) -> Dict[str, Any]:
        return self.device_inspector.get_info(serial)

    def scan_storage(self, serial: Optional[str] = None) -> Dict[str, Any]:
        return self.storage_analyzer.analyze(serial)

    def execute_remediation(self, vector_ids: List[str], serial: Optional[str] = None) -> Dict[str, Any]:
        return self.storage_optimizer.execute_remediation(vector_ids, serial)

    def list_device_packages(self, serial: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.debloater.list_all_packages(serial)

    def batch_package_action(self, packages: List[str], action: str, serial: Optional[str] = None) -> Dict[str, Any]:
        return self.debloater.batch_execute(packages, action, serial)

    def pair_wireless(self, address_port: str, pairing_code: str) -> Dict[str, Any]:
        success, message = self.adb.pair_wireless(address_port, pairing_code)
        return {"success": success, "message": message}

    def connect_wireless(self, address_port: str) -> Dict[str, Any]:
        success, message = self.adb.connect_wireless(address_port)
        return {"success": success, "message": message}

    def disconnect_device(self, address_port: Optional[str] = None) -> Dict[str, Any]:
        success, message = self.adb.disconnect(address_port)
        return {"success": success, "message": message}

    def check_update(self) -> Dict[str, Any]:
        return self.updater.check_update()

    def start_update_download(self, download_url: str, version: str) -> Dict[str, Any]:
        return self.updater.start_download(download_url, version)

    def get_update_progress(self) -> Dict[str, Any]:
        return self.updater.get_progress()

    def apply_update_and_restart(self) -> Dict[str, Any]:
        return self.updater.apply_update_and_restart()

    def cancel_update_download(self) -> Dict[str, Any]:
        return self.updater.cancel_download()

    def get_app_version(self) -> Dict[str, str]:
        return {"version": APP_VERSION}
