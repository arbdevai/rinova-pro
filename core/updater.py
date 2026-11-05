"""
Rinova Pro - In-App Update Engine
Checks GitHub Releases API for new portable releases and assets.
"""

import json
import urllib.request
import urllib.error
from typing import Dict, Any
from core.version import APP_VERSION, REPO_OWNER, REPO_NAME

class UpdateChecker:
    def __init__(self, owner: str = REPO_OWNER, repo: str = REPO_NAME, current_version: str = APP_VERSION):
        self.owner = owner
        self.repo = repo
        self.current_version = current_version
        self.api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"

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
            with urllib.request.urlopen(req, timeout=8) as response:
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

            # Find portable windows zip asset
            download_url = html_url
            asset_name = ""
            for asset in data.get("assets", []):
                name = asset.get("name", "")
                if name.endswith(".zip") or name.endswith(".exe"):
                    download_url = asset.get("browser_download_url", download_url)
                    asset_name = name
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
