"""
Rinova Pro - Deep Storage Analyzer
Scans physical partitions, inspects MediaProvider SQLite databases,
and discovers hidden storage leaks without risking user files.
"""

import json
import re
from typing import Dict, Any, List, Optional
from core.adb_client import ADBClient

class StorageAnalyzer:
    def __init__(self, adb: ADBClient):
        self.adb = adb

    def analyze(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Performs full storage audit on /data and analyzes potential SQLite bloats."""
        # 1. Query physical partition stats via df
        code, df_out, _ = self.adb.shell("df -k /data", target_device=serial)
        total_kb = 0
        used_kb = 0
        free_kb = 0
        percent_used = 0

        if code == 0:
            lines = df_out.strip().splitlines()
            if len(lines) >= 2:
                parts = lines[1].split()
                if len(parts) >= 5:
                    try:
                        total_kb = int(parts[1])
                        used_kb = int(parts[2])
                        free_kb = int(parts[3])
                        pct_str = parts[4].replace("%", "")
                        percent_used = int(pct_str)
                    except ValueError:
                        pass

        total_gb = round(total_kb / (1024 * 1024), 2)
        used_gb = round(used_kb / (1024 * 1024), 2)
        free_gb = round(free_kb / (1024 * 1024), 2)

        # 2. Query diskstats to get breakdown by packages
        code, diskstats_out, _ = self.adb.shell("dumpsys diskstats", target_device=serial, timeout=10)
        app_sizes = self._parse_diskstats(diskstats_out)

        # 3. Specifically inspect MediaProvider database bloat
        media_db_info = self._check_media_provider_db(serial)

        # 4. Formulate diagnostic verdict
        status = "HEALTHY"
        status_message = "Kondisi penyimpanan dalam batas normal."
        status_color = "#10b981" # Green

        media_bloat_detected = False
        reclaimable_gb = 0.0

        if media_db_info.get("external_db_mb", 0) > 1000: # > 1 GB is definitely bloated
            media_bloat_detected = True
            reclaimable_gb = round(media_db_info["external_db_mb"] / 1024, 2)
            status = "CRITICAL_MEDIA_BLOAT"
            status_message = (
                f"Ditemukan kerusakan database Media Storage ({reclaimable_gb} GB)! "
                f"Penyimpanan bisa dipulihkan tanpa menghapus foto/video."
            )
            status_color = "#ef4444" # Red
        elif percent_used >= 95:
            status = "STORAGE_ALMOST_FULL"
            status_message = f"Penyimpanan kritis ({percent_used}% terpakai), sisa hanya {free_gb} GB."
            status_color = "#f59e0b" # Amber
        elif percent_used >= 85:
            status = "STORAGE_WARNING"
            status_message = f"Penyimpanan mulai menipis ({percent_used}% terpakai)."
            status_color = "#f59e0b"

        return {
            "partition": {
                "total_gb": total_gb,
                "used_gb": used_gb,
                "free_gb": free_gb,
                "percent_used": percent_used,
            },
            "status": status,
            "status_message": status_message,
            "status_color": status_color,
            "media_bloat": {
                "detected": media_bloat_detected,
                "reclaimable_gb": reclaimable_gb,
                "details": media_db_info
            },
            "top_apps": app_sizes[:10]
        }

    def _parse_diskstats(self, content: str) -> List[Dict[str, Any]]:
        """Parses dumpsys diskstats output for Package Names and App Data Sizes."""
        if not content:
            return []

        pkg_match = re.search(r"Package Names:\s*(\[.*?\])", content)
        data_match = re.search(r"App Data Sizes:\s*(\[.*?\])", content)

        if not (pkg_match and data_match):
            return []

        try:
            pkgs = json.loads(pkg_match.group(1))
            sizes = json.loads(data_match.group(1))
            results = []
            for p, s in zip(pkgs, sizes):
                mb = round(s / (1024 * 1024), 2)
                gb = round(mb / 1024, 2)
                if mb > 1.0:
                    results.append({
                        "package": p,
                        "size_mb": mb,
                        "size_gb": gb
                    })
            results.sort(key=lambda x: x["size_mb"], reverse=True)
            return results
        except Exception:
            return []

    def _check_media_provider_db(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Inspects com.google.android.providers.media.module memory and DB size."""
        code, out, _ = self.adb.shell(
            "dumpsys meminfo com.google.android.providers.media.module",
            target_device=serial,
            timeout=8
        )
        if code != 0 or not out:
            return {"found": False, "external_db_mb": 0}

        external_db_kb = 0
        match = re.search(r"(\d+)\s+.*external\.db", out)
        if match:
            try:
                external_db_kb = int(match.group(1))
            except ValueError:
                pass

        mb = round(external_db_kb / 1024, 2)
        gb = round(mb / 1024, 2)
        return {
            "found": external_db_kb > 0,
            "external_db_kb": external_db_kb,
            "external_db_mb": mb,
            "external_db_gb": gb
        }
