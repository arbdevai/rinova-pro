"""
Rinova Pro - Multi-Vector Storage Diagnostic Engine
Performs comprehensive multi-sector audits across:
1. MediaStore SQLite Database (external.db bloat)
2. Multi-User / Work Profile / Dual Messenger partitions (User 10, 150, 999)
3. WhatsApp Redundant Local Backup Accumulation (7-day duplicate db.crypt)
4. Recycle Bin & Temporary Thumbnail Cache (.Trash / .thumbnails)
5. Telegram Streaming Cache Accumulation
6. System Dumpstate & Tombstone Crash Logs
"""

import json
import re
from typing import Dict, Any, List, Optional
from core.adb_client import ADBClient

class StorageAnalyzer:
    def __init__(self, adb: ADBClient):
        self.adb = adb

    def analyze(self, serial: Optional[str] = None) -> Dict[str, Any]:
        """Runs full multi-vector diagnostic audit on target device."""
        # 1. Query physical partition stats via df
        code, df_out, _ = self.adb.shell("df -k /data", target_device=serial)
        total_kb = used_kb = free_kb = percent_used = 0

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

        # 2. Vector Audits
        findings: List[Dict[str, Any]] = []

        # Vector 1: MediaStore Database SQLite Bloat
        v1 = self._audit_mediastore(serial)
        findings.append(v1)

        # Vector 2: Multi-User / Dual Space / Knox Profile Check
        v2 = self._audit_multiuser(serial)
        findings.append(v2)

        # Vector 3: WhatsApp Duplicate Local Backups Check
        v3 = self._audit_whatsapp_backups(serial)
        findings.append(v3)

        # Vector 4: Gallery & Storage Trash Retention
        v4 = self._audit_recycle_bin(serial)
        findings.append(v4)

        # Vector 5: Telegram Streaming Cache
        v5 = self._audit_telegram_cache(serial)
        findings.append(v5)

        # Vector 6: Crash Logs & Dumpstate
        v6 = self._audit_crash_logs(serial)
        findings.append(v6)

        # Vector 7: Application Temporary Cache & Dexopt Buffers
        v7 = self._audit_app_caches(serial)
        findings.append(v7)

        # Calculate total reclaimable space
        total_reclaimable_mb = sum(f["size_mb"] for f in findings if f["reclaimable"])
        total_reclaimable_gb = round(total_reclaimable_mb / 1024, 2)

        # 3. Query top consuming packages via dumpsys diskstats
        _, diskstats_out, _ = self.adb.shell("dumpsys diskstats", target_device=serial, timeout=8)
        top_apps = self._parse_diskstats(diskstats_out)

        return {
            "partition": {
                "total_gb": total_gb,
                "used_gb": used_gb,
                "free_gb": free_gb,
                "percent_used": percent_used,
            },
            "findings": findings,
            "total_reclaimable_gb": total_reclaimable_gb,
            "top_apps": top_apps[:10]
        }

    def _detect_mediaprovider_package(self, serial: Optional[str] = None) -> str:
        """Dynamically identifies the active MediaProvider package on device (Samsung/Pixel/AOSP)."""
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

    def _audit_mediastore(self, serial: Optional[str]) -> Dict[str, Any]:
        """Vector 1: Checks external.db size in MediaProvider dynamically."""
        pkg = self._detect_mediaprovider_package(serial)
        code, out, _ = self.adb.shell(
            f"dumpsys meminfo {pkg}",
            target_device=serial,
            timeout=8
        )
        db_kb = 0
        if code == 0 and out:
            match = re.search(r"(\d+)\s+.*external\.db", out)
            if match:
                try:
                    db_kb = int(match.group(1))
                except ValueError:
                    pass

        mb = round(db_kb / 1024, 2)
        gb = round(mb / 1024, 2)
        is_bloated = mb > 1000 # > 1 GB is considered bloated

        return {
            "id": "mediastore_bloat",
            "title": f"MediaStore Database SQLite ({pkg})",
            "target": f"/data/user/0/{pkg}/databases/external.db",
            "size_mb": mb,
            "size_gb": gb,
            "reclaimable": is_bloated,
            "severity": "CRITICAL" if is_bloated else "CLEAN",
            "note": "Indeks SQLite membengkak akibat loop transaksi. Reset aman tanpa menghapus file media fisik." if is_bloated else f"Ukuran database MediaStore ({mb} MB) berada pada batas normal."
        }

    def _audit_multiuser(self, serial: Optional[str]) -> Dict[str, Any]:
        """Vector 2: Checks secondary profiles (Dual Apps / Knox / Second Space)."""
        code, out, _ = self.adb.shell("pm list users", target_device=serial)
        user_list = []
        has_secondary = False

        if code == 0 and out:
            for line in out.splitlines():
                match = re.search(r"UserInfo\{(\d+):([^:]+):", line)
                if match:
                    uid = int(match.group(1))
                    uname = match.group(2)
                    user_list.append({"uid": uid, "name": uname})
                    if uid != 0:
                        has_secondary = True

        note = f"Ditemukan {len(user_list)} profil aktif ({', '.join(u['name'] for u in user_list)})." if has_secondary else "Hanya profil utama (User 0) yang aktif."

        return {
            "id": "multi_user",
            "title": "Secondary User Profiles (Dual Apps / Knox / Work Space)",
            "target": "UserHandle partitions (/data/user/*)",
            "size_mb": 0.0,
            "size_gb": 0.0,
            "reclaimable": False, # Requires manual technician review
            "severity": "INFO" if has_secondary else "CLEAN",
            "note": note,
            "user_list": user_list
        }

    def _audit_whatsapp_backups(self, serial: Optional[str]) -> Dict[str, Any]:
        """Vector 3: Checks accumulation of redundant local WhatsApp daily backups."""
        check_cmd = (
            "ls -l /storage/emulated/0/Android/media/com.whatsapp/WhatsApp/Databases/msgstore-*.db.crypt* 2>/dev/null || "
            "ls -l /storage/emulated/0/WhatsApp/Databases/msgstore-*.db.crypt* 2>/dev/null"
        )
        code, out, _ = self.adb.shell(check_cmd, target_device=serial)
        files = []
        total_bytes = 0

        if code == 0 and out:
            lines = [l.strip() for l in out.splitlines() if l.strip() and not l.startswith("ls:")]
            for line in lines:
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        sz = int(parts[4])
                        total_bytes += sz
                        files.append(parts[-1])
                    except ValueError:
                        pass

        # If there are multiple daily backup files (keep newest, prune older)
        redundant_count = max(0, len(files) - 1)
        reclaimable_mb = 0.0
        if len(files) > 1 and total_bytes > 0:
            # Approximate redundant size (pro-rated by file count)
            reclaimable_mb = round(((total_bytes / len(files)) * redundant_count) / (1024 * 1024), 2)

        reclaimable_gb = round(reclaimable_mb / 1024, 2)
        has_redundant = redundant_count > 0

        return {
            "id": "wa_backups",
            "title": "WhatsApp Redundant Local Backups",
            "target": ".../WhatsApp/Databases/msgstore-YYYY-MM-DD.db.crypt*",
            "size_mb": reclaimable_mb,
            "size_gb": reclaimable_gb,
            "reclaimable": has_redundant and reclaimable_mb > 50,
            "severity": "HIGH" if reclaimable_mb > 500 else ("MEDIUM" if has_redundant else "CLEAN"),
            "note": f"Ditemukan {len(files)} backup harian. {redundant_count} backup usang dapat dibersihkan dengan menyisakan 1 backup terbaru." if has_redundant else "Tidak ada akumulasi backup duplikat WhatsApp."
        }

    def _audit_recycle_bin(self, serial: Optional[str]) -> Dict[str, Any]:
        """Vector 4: Checks Gallery / Storage Recycle Bin (.Trash, Samsung trash & .thumbnails)."""
        check_cmd = (
            "du -sk /storage/emulated/0/Android/.Trash 2>/dev/null; "
            "du -sk /storage/emulated/0/.Trash 2>/dev/null; "
            "du -sk /storage/emulated/0/.Trash-1000 2>/dev/null; "
            "du -sk /storage/emulated/0/DCIM/.thumbnails 2>/dev/null; "
            "du -sk /storage/emulated/0/Pictures/.thumbnails 2>/dev/null; "
            "du -sk /storage/emulated/0/Android/data/com.sec.android.gallery3d/cache 2>/dev/null"
        )
        code, out, _ = self.adb.shell(check_cmd, target_device=serial)
        total_kb = 0

        if code == 0 and out:
            for line in out.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2:
                    try:
                        total_kb += int(parts[0])
                    except ValueError:
                        pass

        mb = round(total_kb / 1024, 2)
        gb = round(mb / 1024, 2)
        has_trash = mb > 50

        return {
            "id": "recycle_bin",
            "title": "Recycle Bin & Thumbnail Cache (.Trash / .thumbnails)",
            "target": "/sdcard/.Trash & DCIM/.thumbnails",
            "size_mb": mb,
            "size_gb": gb,
            "reclaimable": has_trash,
            "severity": "MEDIUM" if has_trash else "CLEAN",
            "note": f"Ditemukan {mb} MB file sampah recycle bin dan cache thumbnail." if has_trash else "Recycle Bin dan thumbnail cache dalam kondisi bersih."
        }

    def _audit_telegram_cache(self, serial: Optional[str]) -> Dict[str, Any]:
        """Vector 5: Checks Telegram unlimited media cache."""
        check_cmd = "du -sk /storage/emulated/0/Android/data/org.telegram.messenger/cache 2>/dev/null"
        code, out, _ = self.adb.shell(check_cmd, target_device=serial)
        kb = 0
        if code == 0 and out:
            parts = out.strip().split()
            if len(parts) >= 2:
                try:
                    kb = int(parts[0])
                except ValueError:
                    pass

        mb = round(kb / 1024, 2)
        gb = round(mb / 1024, 2)
        has_cache = mb > 200

        return {
            "id": "telegram_cache",
            "title": "Telegram Streaming & Video Cache",
            "target": "/sdcard/Android/data/org.telegram.messenger/cache",
            "size_mb": mb,
            "size_gb": gb,
            "reclaimable": has_cache,
            "severity": "HIGH" if mb > 1000 else ("MEDIUM" if has_cache else "CLEAN"),
            "note": "Cache streaming video dan file sementara Telegram." if has_cache else "Cache media Telegram dalam batas wajar."
        }

    def _audit_crash_logs(self, serial: Optional[str]) -> Dict[str, Any]:
        """Vector 6: Audits system crash dumps, DropBox entries, and tombstone traces."""
        code, out, _ = self.adb.shell("dumpsys dropbox | grep -E 'Drop box contents:|entries'", target_device=serial, timeout=8)
        entry_count = 0
        if code == 0 and out:
            match = re.search(r"(\d+)\s+entries", out)
            if match:
                entry_count = int(match.group(1))

        # Check accessible app crash dumps in storage
        check_cmd = "du -sk /storage/emulated/0/Android/data/*/cache/*crash* 2>/dev/null; du -sk /storage/emulated/0/Android/data/*/cache/*dump* 2>/dev/null"
        _, out_sd, _ = self.adb.shell(check_cmd, target_device=serial, timeout=5)
        sd_kb = 0
        if out_sd:
            for line in out_sd.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2:
                    try:
                        sd_kb += int(parts[0])
                    except ValueError:
                        pass

        # Estimate MB (average DropBox entry + file caches)
        mb = round((entry_count * 0.15) + (sd_kb / 1024), 2)
        gb = round(mb / 1024, 2)
        has_logs = (entry_count > 50) or (mb > 20.0)

        return {
            "id": "crash_logs",
            "title": "System Crash Dumps & DropBox Logs (Tombstones/ANR)",
            "target": "DropBoxManager & App Crash Traces",
            "size_mb": mb,
            "size_gb": gb,
            "reclaimable": has_logs,
            "severity": "MEDIUM" if has_logs else "CLEAN",
            "note": f"Ditemukan {entry_count} riwayat crash/ANR di DropBox dan trace cache sistem." if has_logs else "Log crash sistem dan DropBox dalam batas normal."
        }

    def _audit_app_caches(self, serial: Optional[str]) -> Dict[str, Any]:
        """Vector 7: Checks accumulated temporary application caches via diskstats."""
        code, out, _ = self.adb.shell("dumpsys diskstats", target_device=serial, timeout=8)
        cache_bytes = 0
        if code == 0 and out:
            cache_match = re.search(r"App Cache Sizes:\s*(\[.*?\])", out)
            if cache_match:
                try:
                    sizes = json.loads(cache_match.group(1))
                    cache_bytes = sum(sizes)
                except Exception:
                    pass

        mb = round(cache_bytes / (1024 * 1024), 2)
        gb = round(mb / 1024, 2)
        has_cache = mb > 100.0

        return {
            "id": "app_caches",
            "title": "Application Temporary Caches & Dexopt Residuals",
            "target": "Global Package Cache (pm trim-caches)",
            "size_mb": mb,
            "size_gb": gb,
            "reclaimable": has_cache,
            "severity": "HIGH" if mb > 1000 else ("MEDIUM" if has_cache else "CLEAN"),
            "note": f"Ditemukan {mb} MB cache aplikasi terakumulasi yang dapat dibersihkan secara aman tanpa menghapus data login." if has_cache else "Cache aplikasi dalam batas aman."
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
