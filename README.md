# LAN File Distributor

LAN File Distributor tracks GitHub repository releases, requests your approval for updates, and downloads release files directly to your local area network (LAN) folder.

The application uses an **on-demand architecture**. It uses zero background memory when idle. Your computer retains full RAM and GPU resources for 3D modeling and rendering.

---

## Key Features

- **Unified Setup Executable (`LAN_Relay_Setup.exe`):** Single installer for both online relay hosts and offline target clients.
- **Scheduled Morning Monitor:** Inspects GitHub releases for configured applications and extensions daily.
- **User Approval Flow:** Shows a native prompt before downloading any file:
  > *"Updates available: [app list]. Target LAN Folder: [path]. Do you want to pull these files into the LAN now?"*
- **Direct LAN Folder Download:** Streams `.exe`, `.msi`, and `.zip` files directly into your specified LAN directory.
- **Two-Stage Offline Relay:** Automatically generates `<app>_version.txt`, `latest_version.txt`, and standardized `<app>_latest.<ext>` aliases for offline computers.
- **Manual Staged Testing on Online Host:** Download new releases into a local staging sandbox first, execute and test the installer on the online PC, and approve deployment before pushing to offline workstations.
- **Zero Idle Memory:** The scheduled check stops immediately after execution. It leaves 0 MB of background RAM.
- **On-Demand Web Manager:** A local web dashboard with GitHub URL auto-parsing, preset buttons, and checkbox selection.
- **UI Design Compliance:** Designed according to the **UI UX PRO MAX** standards using a neutral dark theme with zero blue colors.

---

## Architecture and Design Decisions

```
+-----------------------------------------------------------+
|                    GitHub API                             |
|  https://api.github.com/repos/{owner}/{repo}/releases/latest
+-----------------------------+-----------------------------+
                              |
                              v
+-----------------------------------------------------------+
|               github_tracker.py (Core Engine)             |
|  • Fetches releases using urllib.request                  |
|  • Compares release tags with config.json                 |
|  • Streams downloads in 64 KB chunks                      |
|  • Writes <app>_version.txt and <app>_latest.<ext>        |
+---------------+-----------------------------+-------------+
                |                             |
                v                             v
+-------------------------------+  +------------------------+
|       check_updates.py        |  |       manager.py       |
|  (Morning Scheduled Task)     |  |  (On-Demand Dashboard) |
|  • Runs via Windows Scheduler |  |  • Serves Web UI       |
|  • Shows native Yes/No prompt |  |  • Edits repositories  |
|  • Exits immediately (0 MB)   |  |  • Stops on command    |
+---------------+---------------+  +-----------+------------+
                |                              |
                +--------------+---------------+
                               |
                               v
+-----------------------------------------------------------+
|               Predefined LAN Target Folder                |
|               (e.g., F:\LAN_Share\Software)                |
+-----------------------------------------------------------+
                               | (SMB Network Share)
                               v
+-----------------------------------------------------------+
|                 Offline Target PC                         |
|  • Runs pull_update.ps1 silently under Admin              |
|  • Installs .msi, .exe (/S, /VERYSILENT), or .zip         |
+-----------------------------------------------------------+
```

---

## Project Structure

```
LAN-File-Distributer/
├── .github/
│   └── FUNDING.yml       # GitHub Sponsors configuration
├── .env.example          # Template for environment configuration
├── .gitignore            # Protects credentials, cache, and downloads
├── LICENSE               # GNU General Public License v3.0 (GPLv3)
├── NOTICE                # Attribution and copyright notice
├── pyproject.toml        # Standard Python package metadata
├── config.json           # Tracks LAN folder path, apps, and extensions
├── setup_wizard.py       # Source for the unified setup executable
├── build_installer.bat   # Script to compile LAN_Relay_Setup.exe
├── github_tracker.py     # Core GitHub API and download streaming logic
├── check_updates.py      # Scheduled task script with native user prompt
├── manager.py            # On-demand HTTP server for the management UI
├── run_manager.bat       # Windows shortcut to start the web dashboard
├── setup_scheduler.bat   # Registers the 11:00 AM daily task in Windows
├── client_scripts/
│   └── pull_update.ps1   # Silent background installer for offline PCs
├── web/
│   ├── index.html        # Semantic HTML dashboard
│   ├── style.css         # Centralized Vanilla CSS (Zero blue colors)
│   └── app.js            # Client-side ES6 JavaScript
└── README.md             # System documentation
```

---

## Setup and Installation

### 1. Build the Unified Setup Executable
Run `build_installer.bat` or execute:
```powershell
pyinstaller --onefile --noconsole --name "LAN_Relay_Setup" --add-data "web;web" setup_wizard.py
```
This generates `dist\LAN_Relay_Setup.exe`. Copy this single executable file to your online and offline computers.

### 2. On Your Online PC (Relay Host)
1. Run `LAN_Relay_Setup.exe`.
2. Select **Online PC (Relay Host)**.
3. Confirm the LAN share folder (for example, `C:\LAN_Share\Software`).
4. Click **Install Role**.
5. The installer registers the morning update task and sets up folder sharing.

### 3. On Your Offline PC (Target Client)
1. Run `LAN_Relay_Setup.exe`.
2. Select **Offline PC (Target Client)**.
3. Enter the Online PC's share path (for example, `\\[Online-PC-IP]\lan_shared_files`).
4. Click **Install Role**.
5. The installer places `pull_update.ps1` into `C:\UpdateScripts` and schedules the background silent installation task under the Admin account.

---

## Support Development

If LAN File Distributor helps your workstations and rendering workflows, you can sponsor the project on [GitHub Sponsors](https://github.com/sponsors/keshavanarayan).

---

## License

This project is licensed under the **GNU General Public License, Version 3 (GPLv3)**. See the [LICENSE](LICENSE) file for the full license text and [NOTICE](NOTICE) for copyright attribution.

