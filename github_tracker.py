# Copyright (C) 2026 Keshavanarayan and contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
GitHub Release Tracker and Downloader.
Uses Python 3 standard library only (zero external pip packages).
"""

import os
import re
import json
import shutil
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple


def format_size(bytes_val: int) -> str:
    """Format bytes into readable MB string."""
    if not bytes_val:
        return "Unknown size"
    mb = bytes_val / (1024 * 1024)
    return f"{mb:.1f} MB"


def normalize_app_slug(name: str) -> str:
    """Convert an application name into a clean file slug (e.g. 'Ingetrazo' -> 'ingetrazo')."""
    return re.sub(r"[^a-zA-Z0-9_-]", "", name.strip().lower().replace(" ", "_"))


def load_env(env_path: str = ".env") -> Dict[str, str]:
    """Load simple key-value pairs from .env file without external dependencies."""
    env_vars = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    env_vars[key.strip()] = val.strip()
    return env_vars


def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    """Read configuration from config.json."""
    if not os.path.exists(config_path):
        default_config = {
            "lan_folder": os.path.abspath("./lan_shared_files"),
            "check_time": "11:00",
            "repositories": []
        }
        save_config(default_config, config_path)
        return default_config
    
    with open(config_path, "r", encoding="utf-8") as file:
        cfg = json.load(file)
        if "lan_folder" in cfg and not os.path.isabs(cfg["lan_folder"]):
            cfg["lan_folder"] = os.path.abspath(cfg["lan_folder"])
        return cfg


def save_config(config: Dict[str, Any], config_path: str = "config.json") -> None:
    """Save configuration to config.json safely using a temporary file."""
    temp_path = config_path + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=2)
    os.replace(temp_path, config_path)


def parse_github_repo(repo_input: str) -> Optional[Tuple[str, str]]:
    """
    Extract owner and repository name from URL or owner/repo format.
    Examples:
      - https://github.com/owner/repo -> (owner, repo)
      - owner/repo -> (owner, repo)
    """
    repo_input = repo_input.strip().rstrip("/")
    if "github.com/" in repo_input:
        parts = repo_input.split("github.com/")[-1].split("/")
        if len(parts) >= 2:
            return parts[0], parts[1].replace(".git", "")
    elif "/" in repo_input:
        parts = repo_input.split("/")
        if len(parts) == 2:
            return parts[0], parts[1].replace(".git", "")
    return None


def fetch_latest_release(owner: str, repo: str, token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetch the latest release information from GitHub REST API.
    Uses standard library urllib.request.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "LAN-File-Distributor-Agent"
    }
    if token:
        headers["Authorization"] = f"token {token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.status == 200:
                return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        if err.code == 404:
            print(f"[Notice] No releases found for {owner}/{repo}.")
        elif err.code == 403:
            print(f"[Warning] Rate limit exceeded or access forbidden for {owner}/{repo}.")
        else:
            print(f"[Error] HTTP {err.code} checking {owner}/{repo}: {err.reason}")
    except Exception as err:
        print(f"[Error] Connection failed for {owner}/{repo}: {err}")
    return None


def find_matching_asset(release: Dict[str, Any], pattern: str) -> Optional[Dict[str, Any]]:
    """Find the first asset matching the given regular expression pattern."""
    assets = release.get("assets", [])
    regex = re.compile(pattern, re.IGNORECASE)
    for asset in assets:
        name = asset.get("name", "")
        if regex.search(name):
            return asset
    return None


def check_for_all_updates() -> List[Dict[str, Any]]:
    """
    Check all repositories in config.json.
    Returns list of items that have a newer release available.
    """
    env = load_env()
    token = env.get("GITHUB_TOKEN") or None
    config = load_config()
    
    updates_available = []
    
    for item in config.get("repositories", []):
        parsed = parse_github_repo(item.get("repo_url", ""))
        if not parsed:
            continue
        
        owner, repo = parsed
        release = fetch_latest_release(owner, repo, token)
        if not release:
            continue
        
        latest_tag = release.get("tag_name", "")
        item["last_known_tag"] = latest_tag
        
        pattern = item.get("asset_pattern", ".*\\.(exe|msi|zip)$")
        asset = find_matching_asset(release, pattern)
        
        last_downloaded = item.get("last_downloaded_tag", "")
        if latest_tag and latest_tag != last_downloaded:
            updates_available.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "type": item.get("type", "app"),
                "parent_app": item.get("parent_app"),
                "repo": f"{owner}/{repo}",
                "latest_tag": latest_tag,
                "current_tag": last_downloaded or "None",
                "asset_name": asset.get("name") if asset else None,
                "asset_size": asset.get("size", 0) if asset else 0,
                "download_url": asset.get("browser_download_url") if asset else None
            })

    save_config(config)
    return updates_available


def download_asset(download_url: str, destination_dir: str, filename: str) -> str:
    """
    Stream download asset file directly into the target LAN folder.
    Uses chunked streaming to keep RAM usage near zero.
    """
    os.makedirs(destination_dir, exist_ok=True)
    target_path = os.path.join(destination_dir, filename)
    
    headers = {
        "User-Agent": "LAN-File-Distributor-Agent"
    }
    req = urllib.request.Request(download_url, headers=headers)
    
    temp_target = target_path + ".downloading"
    with urllib.request.urlopen(req, timeout=120) as response, open(temp_target, "wb") as out_file:
        chunk_size = 1024 * 64  # 64 KB chunks
        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            out_file.write(chunk)
            
    os.replace(temp_target, target_path)
    return target_path


def apply_update_download(item_id: str, new_tag: str) -> None:
    """Record that an item has been successfully downloaded to the LAN folder."""
    config = load_config()
    for item in config.get("repositories", []):
        if item.get("id") == item_id:
            item["last_downloaded_tag"] = new_tag
            break
    save_config(config)


def write_offline_relay_artifacts(destination_dir: str, app_name: str, filename: str, tag: str, item_type: str = "app", parent_app: Optional[str] = None) -> None:
    """
    Write version files and latest asset aliases for offline client PCs:
    - If item_type == 'extension': places files in destination_dir/extensions/
    - If item_type == 'app': places files directly in destination_dir/
    """
    os.makedirs(destination_dir, exist_ok=True)
    os.makedirs(os.path.join(destination_dir, "clients"), exist_ok=True)
    slug = normalize_app_slug(app_name)
    _, ext = os.path.splitext(filename)
    source_file = os.path.join(destination_dir, filename)

    if item_type == "extension":
        ext_dir = os.path.join(destination_dir, "extensions")
        os.makedirs(ext_dir, exist_ok=True)

        # 1. Write extension version file
        ext_version_file = os.path.join(ext_dir, f"{slug}_version.txt")
        with open(ext_version_file, "w", encoding="utf-8") as vf:
            vf.write(tag)

        # 2. Copy extension asset to extensions/<slug>_latest.<ext>
        if os.path.exists(source_file):
            target_ext_file = os.path.join(ext_dir, f"{slug}_latest{ext}")
            shutil.copyfile(source_file, target_ext_file)

        # 3. Update extensions manifest
        manifest_path = os.path.join(ext_dir, "extensions_manifest.json")
        manifest = {}
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as mf:
                    manifest = json.load(mf)
            except Exception:
                manifest = {}
        manifest[slug] = {
            "name": app_name,
            "parent_app": parent_app or "Ingetrazo",
            "version": tag,
            "filename": f"{slug}_latest{ext}"
        }
        with open(manifest_path, "w", encoding="utf-8") as mf:
            json.dump(manifest, mf, indent=2)

    else:
        # Standard Main Application
        app_version_file = os.path.join(destination_dir, f"{slug}_version.txt")
        with open(app_version_file, "w", encoding="utf-8") as vf:
            vf.write(tag)

        generic_version_file = os.path.join(destination_dir, "latest_version.txt")
        with open(generic_version_file, "w", encoding="utf-8") as vf:
            vf.write(tag)

        if os.path.exists(source_file):
            alias_file = os.path.join(destination_dir, f"{slug}_latest{ext}")
            shutil.copyfile(source_file, alias_file)

    # 4. Update central manifest.json in destination_dir for offline clients
    manifest_path = os.path.join(destination_dir, "manifest.json")
    manifest = {"apps": {}, "extensions": {}}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as mf:
                loaded = json.load(mf)
                if isinstance(loaded, dict):
                    manifest = loaded
        except Exception:
            manifest = {"apps": {}, "extensions": {}}

    manifest.setdefault("apps", {})
    manifest.setdefault("extensions", {})

    if item_type == "extension":
        manifest["extensions"][slug] = {
            "name": app_name,
            "parent_app": parent_app or "Ingetrazo",
            "version": tag,
            "filename": f"{slug}_latest{ext}"
        }
    else:
        manifest["apps"][slug] = {
            "name": app_name,
            "version": tag,
            "filename": f"{slug}_latest{ext}"
        }

    with open(manifest_path, "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2)


def get_staging_dir(destination_dir: str) -> str:
    """Get or create the staging directory for test installations on the host PC."""
    staging_dir = os.path.join(destination_dir, "staging")
    os.makedirs(staging_dir, exist_ok=True)
    return staging_dir


def download_single_for_testing(item_id: str, destination_dir: str, env_vars: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Download a single application or extension to the local staging folder for verification on the host PC.
    The file is NOT distributed to offline LAN clients until the test is approved.
    """
    config = load_config()
    target_item = None
    for item in config.get("repositories", []):
        if item.get("id") == item_id:
            target_item = item
            break

    if not target_item:
        raise ValueError(f"Repository with id '{item_id}' not found.")

    token = (env_vars or load_env()).get("GITHUB_TOKEN") or None
    parsed = parse_github_repo(target_item.get("repo_url", ""))
    if not parsed:
        raise ValueError(f"Invalid repository URL: {target_item.get('repo_url')}")

    owner, repo = parsed
    release = fetch_latest_release(owner, repo, token)
    if not release:
        raise RuntimeError(f"Could not retrieve latest release for {owner}/{repo}")

    latest_tag = release.get("tag_name", "")
    pattern = target_item.get("asset_pattern", ".*\\.(exe|msi|zip)$")
    asset = find_matching_asset(release, pattern)
    if not asset:
        raise RuntimeError(f"No matching installer asset found in release {latest_tag}")

    filename = asset.get("name")
    url = asset.get("browser_download_url")
    staging_dir = get_staging_dir(destination_dir)

    staged_path = download_asset(url, staging_dir, filename)

    target_item["staging_tag"] = latest_tag
    target_item["staging_file"] = filename
    target_item["staging_status"] = "downloaded"
    save_config(config)

    return {
        "status": "success",
        "id": item_id,
        "name": target_item.get("name"),
        "tag": latest_tag,
        "file": filename,
        "staged_path": staged_path
    }


def download_batch_for_testing(items: List[Dict[str, Any]], destination_dir: str) -> int:
    """Download multiple update assets into the staging directory for local testing."""
    config = load_config()
    staging_dir = get_staging_dir(destination_dir)
    success_count = 0

    for it in items:
        url = it.get("download_url")
        filename = it.get("asset_name")
        item_id = it.get("id")
        tag = it.get("latest_tag")
        if url and filename and item_id and tag:
            try:
                download_asset(url, staging_dir, filename)
                for repo in config.get("repositories", []):
                    if repo.get("id") == item_id:
                        repo["staging_tag"] = tag
                        repo["staging_file"] = filename
                        repo["staging_status"] = "downloaded"
                        break
                success_count += 1
            except Exception as err:
                print(f"[Error] Failed to stage {filename}: {err}")

    save_config(config)
    return success_count


def launch_test_installer(item_id: str, destination_dir: str) -> Dict[str, Any]:
    """
    Launch the downloaded staged installer locally on the Online Host PC for testing.
    Runs non-blocking using Windows shell launch.
    """
    config = load_config()
    target_item = None
    for item in config.get("repositories", []):
        if item.get("id") == item_id:
            target_item = item
            break

    if not target_item:
        raise ValueError(f"Repository with id '{item_id}' not found.")

    filename = target_item.get("staging_file")
    if not filename:
        raise ValueError("No staged file available. Download for testing first.")

    staging_dir = get_staging_dir(destination_dir)
    file_path = os.path.join(staging_dir, filename)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Staged file not found at: {file_path}")

    if sys.platform == "win32":
        os.startfile(file_path)
    else:
        subprocess.Popen(["xdg-open", file_path])

    target_item["staging_status"] = "tested"
    save_config(config)

    return {
        "status": "launched",
        "id": item_id,
        "name": target_item.get("name"),
        "file": filename
    }


def approve_and_push_to_fleet(item_id: str, destination_dir: str) -> Dict[str, Any]:
    """
    Clear verification and approve pushing a tested release to the active LAN distribution folder.
    Copies the verified asset to the LAN folder and updates version files and manifest.json.
    """
    config = load_config()
    target_item = None
    for item in config.get("repositories", []):
        if item.get("id") == item_id:
            target_item = item
            break

    if not target_item:
        raise ValueError(f"Repository with id '{item_id}' not found.")

    filename = target_item.get("staging_file")
    tag = target_item.get("staging_tag")
    app_name = target_item.get("name", "app")
    item_type = target_item.get("type", "app")
    parent_app = target_item.get("parent_app")

    if not filename or not tag:
        raise ValueError("Missing staging release information. Please download and test first.")

    staging_dir = get_staging_dir(destination_dir)
    source_path = os.path.join(staging_dir, filename)
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Staged file not found at: {source_path}")

    dest_file = os.path.join(destination_dir, filename)
    shutil.copyfile(source_path, dest_file)

    apply_update_download(item_id, tag)
    write_offline_relay_artifacts(destination_dir, app_name, filename, tag, item_type, parent_app)

    target_item["staging_status"] = "approved"
    save_config(config)

    return {
        "status": "approved",
        "id": item_id,
        "name": app_name,
        "tag": tag,
        "file": filename
    }


def download_batch_updates(items: List[Dict[str, Any]], destination_dir: str) -> int:
    """
    Download multiple items in a batch.
    Creates offline relay version files and latest file aliases.
    Supports both applications and selective extensions.
    Returns the count of successfully downloaded files.
    """
    success_count = 0
    for item in items:
        url = item.get("download_url")
        filename = item.get("asset_name")
        item_id = item.get("id")
        app_name = item.get("name", "app")
        item_type = item.get("type", "app")
        parent_app = item.get("parent_app")
        tag = item.get("latest_tag")
        if url and filename and item_id and tag:
            try:
                download_asset(url, destination_dir, filename)
                apply_update_download(item_id, tag)
                write_offline_relay_artifacts(destination_dir, app_name, filename, tag, item_type, parent_app)
                success_count += 1
            except Exception as err:
                print(f"[Error] Failed to download {filename}: {err}")
    return success_count


def get_connected_clients(destination_dir: str) -> List[Dict[str, Any]]:
    """
    Read client status reports from the shared clients folder.
    Returns list of recognized offline workstations.
    """
    clients_dir = os.path.join(destination_dir, "clients")
    if not os.path.exists(clients_dir):
        return []

    client_records = []
    for fname in os.listdir(clients_dir):
        if fname.lower().endswith(".json"):
            file_path = os.path.join(clients_dir, fname)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        client_records.append(data)
            except Exception as err:
                print(f"[Warning] Failed to read client report {fname}: {err}")

    # Sort by computer name
    client_records.sort(key=lambda x: x.get("computer_name", "").lower())
    return client_records
