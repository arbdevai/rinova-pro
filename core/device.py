"""
Rinova Pro - Device Inspector
Fetches detailed specifications and live telemetry from an Android device.
"""

from typing import Dict, Any, Optional
from core.adb_client import ADBClient

class DeviceInspector:
    def __init__(self, adb: ADBClient):
        self.adb = adb

    def get_info(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Gathers system specs, battery status, and OS version."""
        props_cmd = (
            "getprop ro.product.brand; "
            "getprop ro.product.model; "
            "getprop ro.product.manufacturer; "
            "getprop ro.build.version.release; "
            "getprop ro.build.version.sdk; "
            "getprop ro.build.version.security_patch; "
            "dumpsys battery | grep -E 'level|status|health|temperature'"
        )
        code, out, _ = self.adb.shell(props_cmd, target_device=serial)
        if code != 0:
            return {"connected": False, "error": "Unable to communicate with device"}

        lines = [line.strip() for line in out.splitlines()]
        brand = lines[0] if len(lines) > 0 else "Unknown"
        model = lines[1] if len(lines) > 1 else "Unknown"
        manufacturer = lines[2] if len(lines) > 2 else "Unknown"
        android_ver = lines[3] if len(lines) > 3 else "Unknown"
        sdk_ver = lines[4] if len(lines) > 4 else "Unknown"
        security_patch = lines[5] if len(lines) > 5 else "Unknown"

        battery_level = "Unknown"
        battery_temp = "Unknown"
        for line in lines[6:]:
            if "level:" in line:
                battery_level = line.split(":", 1)[1].strip() + "%"
            elif "temperature:" in line:
                try:
                    raw_temp = float(line.split(":", 1)[1].strip()) / 10.0
                    battery_temp = f"{raw_temp:.1f}°C"
                except Exception:
                    pass

        target_serial = serial or self.adb.selected_device or "Default"
        return {
            "connected": True,
            "serial": target_serial,
            "brand": brand.capitalize(),
            "model": model,
            "manufacturer": manufacturer.capitalize(),
            "android_version": android_ver,
            "sdk_version": sdk_ver,
            "security_patch": security_patch,
            "battery_level": battery_level,
            "battery_temp": battery_temp,
            "is_wireless": ":" in target_serial
        }
