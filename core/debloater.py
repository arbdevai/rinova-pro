"""
Rinova Pro - Dynamic Package & Debloat Engine
Dynamically discovers packages directly from connected devices,
eliminating hardcoded lists, and supports bulk operations with safety rules.
"""

import re
from typing import List, Dict, Any, Optional, Set
from core.adb_client import ADBClient

# Heuristic pattern matching for dynamic risk & category assessment
KNOWN_PATTERNS = {
    "Adware & Promosi": [
        r"aura\.oobe", r"ironsource", r"glance", r"heytap\.pictorial",
        r"msa\.global", r"miui\.hybrid", r"transsion\.ahagame", r"transsion\.palm"
    ],
    "Telemetri & Analitik": [
        r"diagmon", r"rubin", r"analytics", r"daemon", r"bugreport",
        r"telemetry", r"feedback", r"tracking", r"metrics"
    ],
    "Layanan Meta / Facebook": [
        r"facebook\.appmanager", r"facebook\.services", r"facebook\.system", r"facebook\.katana"
    ],
    "Layanan Cloud / Sync Eksternal": [
        r"skydrive", r"onedrive", r"dropbox"
    ],
    "Paket Bahasa TTS Non-Aktif": [
        r"samsung\.SMT\.lang_(?!in_id|en_us|id_id).*"
    ]
}

class Debloater:
    def __init__(self, adb: ADBClient):
        self.adb = adb

    def list_all_packages(self, serial: Optional[str] = None) -> List[Dict[str, Any]]:
        """Dynamically scans all installed packages directly from the phone."""
        # 1. Get currently active installed packages
        _, active_out, _ = self.adb.shell("pm list packages", target_device=serial)
        # 2. Get system packages
        _, sys_out, _ = self.adb.shell("pm list packages -s", target_device=serial)
        # 3. Get disabled packages
        _, dis_out, _ = self.adb.shell("pm list packages -d", target_device=serial)
        # 4. Get all packages including uninstalled ones
        _, all_u_out, _ = self.adb.shell("pm list packages -u", target_device=serial)

        active_pkgs = set(self._clean_package_list(active_out))
        sys_pkgs = set(self._clean_package_list(sys_out))
        dis_pkgs = set(self._clean_package_list(dis_out))
        all_u_pkgs = set(self._clean_package_list(all_u_out))

        # Uninstalled for User 0 (exists in -u but missing from active)
        uninstalled_pkgs = all_u_pkgs - active_pkgs

        # All packages to display
        combined_pkgs = sorted(list(active_pkgs | all_u_pkgs))

        results = []
        for pkg in combined_pkgs:
            is_sys = pkg in sys_pkgs
            is_dis = pkg in dis_pkgs
            is_uninst = pkg in uninstalled_pkgs
            category, is_suggested = self._categorize_package(pkg)

            if is_uninst:
                status_label = "Uninstalled"
            elif is_dis:
                status_label = "Disabled"
            else:
                status_label = "Enabled"

            results.append({
                "package": pkg,
                "is_system": is_sys,
                "is_disabled": is_dis,
                "is_uninstalled": is_uninst,
                "status": status_label,
                "category": category,
                "is_suggested": is_suggested,
                "type": "System" if is_sys else "User"
            })

        # Sort: Suggested bloat first, then active/disabled, then uninstalled, then alphabet
        results.sort(key=lambda x: (
            not x["is_suggested"],
            x["is_uninstalled"],
            not x["is_disabled"],
            x["package"]
        ))
        return results

    def _clean_package_list(self, raw_output: str) -> List[str]:
        pkgs = []
        for line in raw_output.splitlines():
            line = line.strip()
            if line.startswith("package:"):
                pkgs.append(line.replace("package:", "").strip())
        return pkgs

    def _categorize_package(self, package: str) -> (str, bool):
        for category, patterns in KNOWN_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, package, re.IGNORECASE):
                    return category, True

        # Android core checks
        if package.startswith("com.android.") or package.startswith("android"):
            return "Android Core", False
        if package.startswith("com.google."):
            return "Google Services", False

        return "Aplikasi Terpasang", False

    def batch_execute(self, packages: List[str], action: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes bulk action on packages.
        action: 'disable' | 'enable' | 'uninstall' | 'restore'
        """
        success_list = []
        error_list = []

        for pkg in packages:
            if action == "disable":
                cmd = f"pm disable-user --user 0 {pkg}"
            elif action == "enable":
                cmd = f"pm enable {pkg}"
            elif action == "uninstall":
                cmd = f"pm uninstall --user 0 {pkg}"
            elif action == "restore":
                cmd = f"cmd package install-existing {pkg}"
            else:
                continue

            code, out, err = self.adb.shell(cmd, target_device=serial, timeout=8)
            output = (out + " " + err).strip()
            out_lower = output.lower()

            # Strict failure check across Android OEMs (Samsung Knox, MIUI, AOSP)
            is_failure = (
                "failure" in out_lower or
                "error" in out_lower or
                "exception" in out_lower or
                "cannot disable" in out_lower or
                "unknown package" in out_lower or
                "not installed for 0" in out_lower or
                "new state: default" in out_lower
            )

            is_success = not is_failure and (
                "success" in out_lower or
                "new state: disabled" in out_lower or
                "new state: enabled" in out_lower or
                "installed for user" in out_lower or
                (action == "uninstall" and ("success" in out_lower or "uninstalled" in out_lower)) or
                (action == "restore" and "installed" in out_lower)
            )

            if is_success:
                success_list.append(pkg)
            else:
                clean_reason = output.splitlines()[-1] if output else "Perintah ditolak oleh kebijakan keamanan OS"
                error_list.append({"package": pkg, "reason": clean_reason})

        return {
            "action": action,
            "total_requested": len(packages),
            "success_count": len(success_list),
            "error_count": len(error_list),
            "success_packages": success_list,
            "errors": error_list
        }
