"""
Rinova Pro - Storage Optimizer
Executes safe 1-Click recovery for corrupted MediaProvider databases
and restarts indexing without deleting user photos, videos, or documents.
"""

from typing import Dict, Any, Optional
from core.adb_client import ADBClient

class StorageOptimizer:
    def __init__(self, adb: ADBClient):
        self.adb = adb

    def fix_media_storage(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Safely resets bloated MediaProvider database and initiates rescan."""
        # Check initial free space
        _, df_before, _ = self.adb.shell("df -k /data", target_device=serial)
        free_before_kb = self._extract_free_kb(df_before)

        # 1. Reset package data of MediaProvider
        code, out, err = self.adb.shell(
            "pm clear com.google.android.providers.media.module",
            target_device=serial,
            timeout=15
        )
        if "success" not in out.lower() and code != 0:
            return {
                "success": False,
                "error": f"Gagal mereset MediaProvider: {out} {err}".strip()
            }

        # 2. Trigger automatic MediaScanner on primary media paths
        scan_paths = [
            "/storage/emulated/0/DCIM",
            "/storage/emulated/0/Pictures",
            "/storage/emulated/0/Download",
            "/storage/emulated/0/Movies",
            "/storage/emulated/0/Music"
        ]
        for path in scan_paths:
            self.adb.shell(
                f"cmd activity broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file://{path}",
                target_device=serial,
                timeout=5
            )

        # 3. Check reclaimed space
        _, df_after, _ = self.adb.shell("df -k /data", target_device=serial)
        free_after_kb = self._extract_free_kb(df_after)

        reclaimed_mb = round((free_after_kb - free_before_kb) / 1024, 2)
        reclaimed_gb = round(reclaimed_mb / 1024, 2)

        return {
            "success": True,
            "reclaimed_mb": max(0.0, reclaimed_mb),
            "reclaimed_gb": max(0.0, reclaimed_gb),
            "message": (
                f"Sukses! Penyimpanan dipulihkan sekitar {reclaimed_gb} GB. "
                "Database media sudah dibersihkan dan Galeri sedang memuat ulang secara otomatis."
            )
        }

    def _extract_free_kb(self, df_output: str) -> int:
        lines = df_output.strip().splitlines()
        if len(lines) >= 2:
            parts = lines[1].split()
            if len(parts) >= 4:
                try:
                    return int(parts[3])
                except ValueError:
                    pass
        return 0
