"""
Rinova Pro - Multi-Vector Storage Optimizer
Executes granular or batch remediation across identified diagnostic vectors.
"""

from typing import Dict, Any, List, Optional
from core.adb_client import ADBClient

class StorageOptimizer:
    def __init__(self, adb: ADBClient):
        self.adb = adb

    def execute_remediation(self, vector_ids: List[str], serial: Optional[str] = None) -> Dict[str, Any]:
        """Runs targeted remediation based on selected vector IDs."""
        # Check initial free space
        _, df_before, _ = self.adb.shell("df -k /data", target_device=serial)
        free_before_kb = self._extract_free_kb(df_before)

        results = []
        for vid in vector_ids:
            if vid == "mediastore_bloat":
                res = self._fix_mediastore(serial)
                results.append({"id": vid, "name": "MediaStore Database Optimization", "status": res})
            elif vid == "wa_backups":
                res = self._clean_whatsapp_backups(serial)
                results.append({"id": vid, "name": "WhatsApp Redundant Backups Pruning", "status": res})
            elif vid == "recycle_bin":
                res = self._clean_recycle_bin(serial)
                results.append({"id": vid, "name": "Recycle Bin & Thumbnail Purge", "status": res})
            elif vid == "telegram_cache":
                res = self._clean_telegram_cache(serial)
                results.append({"id": vid, "name": "Telegram Media Cache Purge", "status": res})
            elif vid == "crash_logs":
                res = self._clean_crash_logs(serial)
                results.append({"id": vid, "name": "System Crash Logs & Tombstones Purge", "status": res})
            elif vid == "app_caches":
                res = self._trim_app_caches(serial)
                results.append({"id": vid, "name": "Global Application Cache Trim", "status": res})

        # Check reclaimed space
        _, df_after, _ = self.adb.shell("df -k /data", target_device=serial)
        free_after_kb = self._extract_free_kb(df_after)

        delta_kb = free_after_kb - free_before_kb
        reclaimed_mb = round(delta_kb / 1024, 2)
        reclaimed_gb = round(reclaimed_mb / 1024, 2)

        if delta_kb > 0:
            msg = f"Remediasi tuntas. Total partisi /data dipulihkan: {reclaimed_gb} GB ({reclaimed_mb} MB)."
        else:
            msg = "Remediasi tuntas dieksekusi. Tidak ada pertambahan kapasitas fisik (file target sudah bersih atau dilindungi Scoped Storage)."

        return {
            "success": True,
            "reclaimed_mb": max(0.0, reclaimed_mb),
            "reclaimed_gb": max(0.0, reclaimed_gb),
            "executed_vectors": results,
            "message": msg
        }

    def _detect_mediaprovider_package(self, serial: Optional[str] = None) -> str:
        candidates = [
            "com.android.providers.media.module",
            "com.google.android.providers.media.module",
            "com.android.providers.media"
        ]
        _, out, _ = self.adb.shell("pm list packages media", target_device=serial, timeout=5)
        for cand in candidates:
            if cand in out:
                return cand
        return "com.android.providers.media.module"

    def _fix_mediastore(self, serial: Optional[str]) -> bool:
        """Vector 1: Resets bloated MediaProvider database & broadcasts media scanner."""
        pkg = self._detect_mediaprovider_package(serial)
        code, out, _ = self.adb.shell(f"pm clear {pkg}", target_device=serial, timeout=15)
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
        return code == 0 or "success" in out.lower()

    def _clean_whatsapp_backups(self, serial: Optional[str]) -> bool:
        """Vector 3: Keeps the newest backup file and removes older daily redundant backups."""
        script = (
            "for dir in "
            "/storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Databases "
            "/storage/emulated/0/WhatsApp/Databases "
            "/storage/emulated/0/Android/media/com.whatsapp.w4b/WhatsApp\\ Business/Databases; do "
            "  if [ -d \"$dir\" ]; then "
            "    ls -t \"$dir\"/msgstore-*.db.crypt* 2>/dev/null | tail -n +2 | while read -r f; do rm -f \"$f\"; done; "
            "  fi; "
            "done"
        )
        code, _, _ = self.adb.shell(script, target_device=serial, timeout=10)
        return code == 0

    def _clean_recycle_bin(self, serial: Optional[str]) -> bool:
        """Vector 4: Purges hidden .Trash folders, Samsung gallery trash, and dead thumbnails."""
        script = (
            "rm -rf /storage/emulated/0/Android/.Trash/* 2>/dev/null; "
            "rm -rf /storage/emulated/0/.Trash/* 2>/dev/null; "
            "rm -rf /storage/emulated/0/.Trash-1000/* 2>/dev/null; "
            "rm -rf /storage/emulated/0/DCIM/.thumbnails/* 2>/dev/null; "
            "rm -rf /storage/emulated/0/Pictures/.thumbnails/* 2>/dev/null; "
            "rm -rf /storage/emulated/0/Android/data/com.sec.android.gallery3d/cache/* 2>/dev/null"
        )
        code, _, _ = self.adb.shell(script, target_device=serial, timeout=10)
        return code == 0

    def _clean_telegram_cache(self, serial: Optional[str]) -> bool:
        """Vector 5: Purges temporary streaming cache from Telegram."""
        script = "rm -rf /storage/emulated/0/Android/data/org.telegram.messenger/cache/* 2>/dev/null"
        code, _, _ = self.adb.shell(script, target_device=serial, timeout=10)
        return code == 0

    def _trim_app_caches(self, serial: Optional[str]) -> bool:
        """Vector 7: Trims global temporary application caches safely via package manager."""
        code, out, _ = self.adb.shell("pm trim-caches 999G", target_device=serial, timeout=15)
        return code == 0 or "trimmed" in out.lower() or "success" in out.lower()

    def _clean_crash_logs(self, serial: Optional[str]) -> bool:
        """Vector 6: Clears system DropBox crash logs, tombstones, and temp crash dumps."""
        # Clears DropBoxManager crash events (accessible by shell uid=2000)
        code, _, _ = self.adb.shell("dumpsys dropbox --clear", target_device=serial, timeout=8)
        # Prune accessible crash traces in emulated storage
        self.adb.shell(
            "rm -rf /storage/emulated/0/Android/data/*/cache/*crash* 2>/dev/null; "
            "rm -rf /storage/emulated/0/Android/data/*/cache/*dump* 2>/dev/null",
            target_device=serial,
            timeout=8
        )
        return code == 0

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
