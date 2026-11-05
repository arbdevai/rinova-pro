"""
Rinova Pro - Industrial Grade In-App Update Engine
Implements Section 9 (Anti-Corrupt Streaming, .part Isolation, Resumable Range, Deep Integrity Verification).
"""

import os
import sys
import json
import time
import zipfile
import threading
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
from core.version import APP_VERSION, REPO_OWNER, REPO_NAME

BUFFER_SIZE = 64 * 1024  # 64 KB chunk buffer as per standard
CONNECT_TIMEOUT = 30
READ_TIMEOUT = 60

class UpdateManager:
    def __init__(self, owner: str = REPO_OWNER, repo: str = REPO_NAME, current_version: str = APP_VERSION):
        self.owner = owner
        self.repo = repo
        self.current_version = current_version
        self.api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
        self.updates_dir = self._resolve_updates_dir()

        # Threading state for background download
        self._lock = threading.Lock()
        self._download_thread: Optional[threading.Thread] = None
        self._cancel_flag = False

        self.state = {
            "status": "idle",  # idle | downloading | verifying | ready | error | cancelled
            "progress": 0,     # 0 to 100
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "downloaded_mb": 0.0,
            "total_mb": 0.0,
            "speed_kbps": 0.0,
            "error": "",
            "target_file": "",
            "version": ""
        }

    def _resolve_updates_dir(self) -> str:
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        updates_dir = os.path.join(exe_dir, "updates")
        os.makedirs(updates_dir, exist_ok=True)
        return updates_dir

    def check_update(self) -> Dict[str, Any]:
        """Queries GitHub API for the latest release."""
        req = urllib.request.Request(
            self.api_url,
            headers={
                "User-Agent": f"RinovaPro/{self.current_version} (Desktop Diagnostic Client)",
                "Accept": "application/vnd.github.v3+json"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=CONNECT_TIMEOUT) as response:
                if response.status != 200:
                    return {
                        "success": False,
                        "update_available": False,
                        "error": f"HTTP status {response.status}"
                    }
                data = json.loads(response.read().decode("utf-8"))

            latest_tag = data.get("tag_name", "").lstrip("v")
            release_name = data.get("name", "") or latest_tag
            body = data.get("body", "Pembaruan sistem dan perbaikan performa.")
            html_url = data.get("html_url", "")
            published_at = data.get("published_at", "")

            # Resolve asset
            download_url = html_url
            asset_name = ""
            asset_size = 0
            for asset in data.get("assets", []):
                name = asset.get("name", "")
                if name.endswith(".zip") or name.endswith(".exe"):
                    download_url = asset.get("browser_download_url", download_url)
                    asset_name = name
                    asset_size = asset.get("size", 0)
                    break

            update_available = self._is_newer(latest_tag, self.current_version)

            return {
                "success": True,
                "update_available": update_available,
                "current_version": self.current_version,
                "latest_version": latest_tag,
                "release_name": release_name,
                "release_notes": body,
                "download_url": download_url,
                "asset_name": asset_name,
                "asset_size": asset_size,
                "published_at": published_at
            }
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {
                    "success": True,
                    "update_available": False,
                    "current_version": self.current_version,
                    "latest_version": self.current_version,
                    "message": "Belum ada rilis publik di GitHub."
                }
            return {"success": False, "update_available": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "update_available": False, "error": str(e)}

    def start_download(self, download_url: str, version: str) -> Dict[str, Any]:
        """Initiates background resumable chunk download with .part isolation."""
        with self._lock:
            if self.state["status"] == "downloading":
                return {"success": False, "message": "Proses unduhan sedang berlangsung."}

            self._cancel_flag = False
            self.state = {
                "status": "downloading",
                "progress": 0,
                "downloaded_bytes": 0,
                "total_bytes": 0,
                "downloaded_mb": 0.0,
                "total_mb": 0.0,
                "speed_kbps": 0.0,
                "error": "",
                "target_file": "",
                "version": version
            }

            self._download_thread = threading.Thread(
                target=self._download_worker,
                args=(download_url, version),
                daemon=True
            )
            self._download_thread.start()

        return {"success": True, "message": "Unduhan latar belakang dimulai."}

    def cancel_download(self) -> Dict[str, Any]:
        """Signals download cancellation and cleans up temporary .part files."""
        with self._lock:
            self._cancel_flag = True
            self.state["status"] = "cancelled"
        return {"success": True, "message": "Unduhan dibatalkan."}

    def get_progress(self) -> Dict[str, Any]:
        """Thread-safe snapshot of download telemetry."""
        with self._lock:
            return dict(self.state)

    def _cleanup_old_files(self, keep_version: str):
        """Purges old incomplete .part files and older update archives."""
        try:
            for item in os.listdir(self.updates_dir):
                if item.endswith(".part") or (item.startswith("RinovaPro-") and not keep_version in item):
                    full_path = os.path.join(self.updates_dir, item)
                    try:
                        os.remove(full_path)
                    except Exception:
                        pass
        except Exception:
            pass

    def _download_worker(self, download_url: str, version: str):
        filename = f"RinovaPro-v{version}.zip"
        final_file = os.path.join(self.updates_dir, filename)
        part_file = final_file + ".part"

        # Auto-cleanup previous leftovers
        self._cleanup_old_files(keep_version=version)

        existing_bytes = 0
        if os.path.isfile(part_file):
            existing_bytes = os.path.getsize(part_file)

        headers = {
            "User-Agent": f"RinovaPro/{self.current_version} (Desktop Diagnostic Client)",
            "Accept": "*/*"
        }

        # Resumable Range Header if part already exists
        if existing_bytes > 0:
            headers["Range"] = f"bytes={existing_bytes}-"

        req = urllib.request.Request(download_url, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=CONNECT_TIMEOUT) as response:
                status_code = response.status

                if status_code == 206:
                    # Partial Content (Resuming)
                    mode = "ab"
                    content_range = response.headers.get("Content-Range", "")
                    # format: bytes 1024-2048/2049
                    if "/" in content_range:
                        total_bytes = int(content_range.split("/")[1])
                    else:
                        total_bytes = existing_bytes + int(response.headers.get("Content-Length", 0))
                else:
                    # 200 OK (Full download or server doesn't support Range)
                    mode = "wb"
                    existing_bytes = 0
                    total_bytes = int(response.headers.get("Content-Length", 0))

                with self._lock:
                    self.state["total_bytes"] = total_bytes
                    self.state["total_mb"] = round(total_bytes / (1024 * 1024), 2)
                    self.state["downloaded_bytes"] = existing_bytes
                    self.state["downloaded_mb"] = round(existing_bytes / (1024 * 1024), 2)

                downloaded = existing_bytes
                last_time = time.time()
                bytes_since_last = 0

                with open(part_file, mode) as f:
                    while True:
                        if self._cancel_flag:
                            f.close()
                            if os.path.isfile(part_file):
                                os.remove(part_file)
                            return

                        chunk = response.read(BUFFER_SIZE)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded += len(chunk)
                        bytes_since_last += len(chunk)

                        now = time.time()
                        dt = now - last_time
                        if dt >= 0.5:
                            speed = (bytes_since_last / 1024.0) / dt
                            pct = int((downloaded * 100) / total_bytes) if total_bytes > 0 else 0
                            with self._lock:
                                self.state["downloaded_bytes"] = downloaded
                                self.state["downloaded_mb"] = round(downloaded / (1024 * 1024), 2)
                                self.state["progress"] = min(99, pct)
                                self.state["speed_kbps"] = round(speed, 1)
                            bytes_since_last = 0
                            last_time = now

            # -------------------------------------------------------------
            # STEP 3: DEEP ARCHIVE INTEGRITY VERIFICATION (Anti-Corrupt Zip)
            # -------------------------------------------------------------
            with self._lock:
                self.state["status"] = "verifying"
                self.state["progress"] = 99

            if not os.path.isfile(part_file) or os.path.getsize(part_file) < 5 * 1024 * 1024:
                raise ValueError("Ukuran file update tidak valid atau terpotong (< 5 MB).")

            # Test ZIP integrity (CRC32 checksum per entry)
            with zipfile.ZipFile(part_file, "r") as zf:
                bad_file = zf.testzip()
                if bad_file is not None:
                    raise ValueError(f"Integritas arsip rusak: file '{bad_file}' terkorupsi.")

            # ATOMIC RENAME: .part -> .zip ONLY AFTER VERIFIED
            if os.path.isfile(final_file):
                os.remove(final_file)
            os.rename(part_file, final_file)

            # Generate launcher batch script
            self._create_updater_script(final_file)

            with self._lock:
                self.state["status"] = "ready"
                self.state["progress"] = 100
                self.state["target_file"] = final_file

        except Exception as e:
            # On corruption or socket abort, delete temporary .part immediately
            if os.path.isfile(part_file):
                try:
                    os.remove(part_file)
                except Exception:
                    pass

            with self._lock:
                self.state["status"] = "error"
                self.state["error"] = str(e)

    def _create_updater_script(self, zip_path: str):
        """Generates updater.bat helper script for automatic replacement on Windows."""
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        bat_path = os.path.join(exe_dir, "updater.bat")

        bat_content = f"""@echo off
title Rinova Pro Auto-Updater
echo ========================================================
echo Memasang pembaruan Rinova Pro ke versi terbaru...
echo ========================================================
timeout /t 2 /nobreak >nul
powershell -Command "Expand-Archive -Path '{zip_path}' -DestinationPath '{exe_dir}' -Force"
del /f /q "{zip_path}"
echo Pembaruan selesai. Membuka kembali Rinova Pro...
start "" "{os.path.join(exe_dir, 'RinovaPro.exe')}"
del /f /q "%~f0"
exit
"""
        try:
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_content)
        except Exception:
            pass

    def apply_update_and_restart(self) -> Dict[str, Any]:
        """Launches updater.bat and exits application process cleanly."""
        exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        bat_path = os.path.join(exe_dir, "updater.bat")

        if sys.platform.startswith("win") and os.path.isfile(bat_path):
            import subprocess
            subprocess.Popen([bat_path], shell=True, creationflags=subprocess.DETACHED_PROCESS)
            threading.Thread(target=lambda: (time.sleep(1), os._exit(0)), daemon=True).start()
            return {"success": True, "message": "Pembaruan sedang diterapkan. Aplikasi akan restart otomatis."}
        else:
            return {"success": True, "message": "Update siap di folder updates/. Ekstrak manual jika di Linux."}

    def _is_newer(self, latest: str, current: str) -> bool:
        """SemVer comparison (returns True if latest > current)."""
        def parse(v: str):
            parts = []
            for p in v.split("."):
                try:
                    parts.append(int(p))
                except ValueError:
                    parts.append(0)
            while len(parts) < 3:
                parts.append(0)
            return parts[:3]

        return parse(latest) > parse(current)
