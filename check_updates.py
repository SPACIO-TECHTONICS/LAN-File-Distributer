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
Morning Scheduled Task for LAN-File-Distributer.
Checks tracked repositories for new releases.
Asks the user before pulling files into the LAN folder.
Exits immediately after completion to free all memory.
"""

import sys
import os
import tkinter as tk
from tkinter import messagebox
from github_tracker import (
    load_config,
    check_for_all_updates,
    download_batch_updates,
    format_size
)


def prompt_user_for_updates(updates: list, lan_folder: str) -> bool:
    """
    Display a native Windows dialog asking the user whether to pull updates.
    """
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    lines = ["New releases are available on GitHub:\n"]
    for u in updates:
        asset_info = f" ({u['asset_name']} - {format_size(u['asset_size'])})" if u.get('asset_name') else " (No matching .exe asset found)"
        lines.append(f"• {u['name']} [{u['type'].upper()}]: {u['current_tag']} ➔ {u['latest_tag']}{asset_info}")
    
    lines.append(f"\nTarget LAN Folder:\n{lan_folder}\n")
    lines.append("Do you want to pull these files into the LAN folder now?")
    
    message_text = "\n".join(lines)
    
    user_choice = messagebox.askyesno(
        title="LAN File Distributor - Updates Available",
        message=message_text,
        parent=root
    )
    
    root.destroy()
    return user_choice


def run_morning_check() -> None:
    """Main execution entry point."""
    print("[LAN File Distributor] Checking for GitHub updates...")
    config = load_config()
    lan_folder = config.get("lan_folder", os.path.abspath("./lan_shared_files"))
    
    updates = check_for_all_updates()
    
    if not updates:
        print("[LAN File Distributor] All tracked applications and extensions are up to date.")
        sys.exit(0)
    
    print(f"[LAN File Distributor] Found {len(updates)} available update(s).")
    
    downloadable_updates = [u for u in updates if u.get("download_url")]
    if not downloadable_updates:
        print("[LAN File Distributor] Updates found, but no matching asset files (.exe) were found in releases.")
        sys.exit(0)
    
    # Prompt the user for approval
    approved = prompt_user_for_updates(downloadable_updates, lan_folder)
    if not approved:
        print("[LAN File Distributor] User selected 'No'. Skipping downloads.")
        sys.exit(0)
    
    # Download approved updates using shared batch function
    print(f"[LAN File Distributor] Downloading updates into: {lan_folder}")
    success_count = download_batch_updates(downloadable_updates, lan_folder)
    
    # Notify user of completion
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    messagebox.showinfo(
        title="LAN File Distributor",
        message=f"Successfully downloaded {success_count} update(s) to:\n{lan_folder}",
        parent=root
    )
    root.destroy()
    
    print("[LAN File Distributor] Done. Releasing all memory.")
    sys.exit(0)


if __name__ == "__main__":
    run_morning_check()
