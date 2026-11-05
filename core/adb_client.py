"""
Rinova Pro - Core ADB Client
Provides safe, asynchronous, and robust interaction with ADB (Android Debug Bridge)
across Windows and Linux, supporting both USB and Wireless debugging.
"""

import os
import sys
import subprocess
import shutil
import re
from typing import List, Dict, Optional, Tuple

class ADBClient:
    def __init__(self, custom_adb_path: Optional[str] = None):
        self.adb_bin = self._resolve_adb_binary(custom_adb_path)
        self.selected_device: Optional[str] = None

    def _resolve_adb_binary(self, custom_path: Optional[str]) -> str:
        """Finds the adb binary in bundled directories, system PATH, or platform-tools."""
        if custom_path and os.path.isfile(custom_path):
            return custom_path

        # 1. Check relative bundled paths (for packaged Windows .exe)
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        bundled_candidates = [
            os.path.join(exe_dir, "platform-tools", "adb.exe"),
            os.path.join(exe_dir, "adb.exe"),
            os.path.join(exe_dir, "platform-tools", "adb"),
            os.path.join(exe_dir, "adb"),
        ]
        for candidate in bundled_candidates:
            if os.path.isfile(candidate):
                return candidate

        # 2. Check system PATH
        system_adb = shutil.which("adb")
        if system_adb:
            return system_adb

        # Default fallback
        return "adb.exe" if sys.platform.startswith("win") else "adb"

    def run(self, args: List[str], target_device: Optional[str] = None, timeout: int = 15) -> Tuple[int, str, str]:
        """Runs an ADB command with timeout safety and returns (exit_code, stdout, stderr)."""
        cmd = [self.adb_bin]
        device = target_device or self.selected_device
        if device:
            cmd.extend(["-s", device])
        cmd.extend(args)

        try:
            # On Windows, hide command console window
            startupinfo = None
            if sys.platform.startswith("win"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                startupinfo=startupinfo
            )
            stdout, stderr = process.communicate(timeout=timeout)
            return process.returncode, stdout.strip(), stderr.strip()
        except subprocess.TimeoutExpired:
            process.kill()
            return -1, "", "Command timed out"
        except Exception as e:
            return -1, "", str(e)

    def shell(self, command: str, target_device: Optional[str] = None, timeout: int = 15) -> Tuple[int, str, str]:
        """Executes an adb shell command."""
        return self.run(["shell", command], target_device=target_device, timeout=timeout)

    def list_devices(self) -> List[Dict[str, str]]:
        """Lists connected ADB devices (USB & Wireless)."""
        code, out, _ = self.run(["devices", "-l"], target_device=None)
        if code != 0:
            return []

        devices = []
        for line in out.splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                serial = parts[0]
                status = parts[1]
                model = "Unknown"
                product = "Unknown"
                for extra in parts[2:]:
                    if extra.startswith("model:"):
                        model = extra.split(":", 1)[1]
                    elif extra.startswith("product:"):
                        product = extra.split(":", 1)[1]
                devices.append({
                    "serial": serial,
                    "status": status,
                    "model": model,
                    "product": product,
                    "is_wireless": ":" in serial
                })
        return devices

    def pair_wireless(self, address_port: str, pairing_code: str) -> Tuple[bool, str]:
        """Pairs a wireless debugging device."""
        code, out, err = self.run(["pair", address_port, pairing_code], target_device=None, timeout=20)
        output = (out + "\n" + err).strip()
        if "Successfully paired" in output or "paired to" in output.lower():
            return True, output
        return False, output

    def connect_wireless(self, address_port: str) -> Tuple[bool, str]:
        """Connects to a wireless debugging device."""
        code, out, err = self.run(["connect", address_port], target_device=None, timeout=20)
        output = (out + "\n" + err).strip()
        if "connected to" in output.lower() and "unable" not in output.lower():
            self.selected_device = address_port
            return True, output
        return False, output

    def disconnect(self, address_port: Optional[str] = None) -> Tuple[bool, str]:
        """Disconnects a wireless ADB target or all wireless connections."""
        args = ["disconnect"]
        if address_port:
            args.append(address_port)
        code, out, err = self.run(args, target_device=None)
        if self.selected_device == address_port:
            self.selected_device = None
        return code == 0, (out + " " + err).strip()
