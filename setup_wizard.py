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
LAN File Distributor - Unified Setup Wizard
Configures either the Online Relay PC or the Offline Client PC.
Runs as a standalone executable (PyInstaller compatible).
"""

import os
import sys
import subprocess
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller bundle."""
    base_path = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base_path, relative_path)


def run_command_hidden(cmd: list) -> int:
    """Execute a system command without showing a console window."""
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    try:
        proc = subprocess.run(cmd, startupinfo=startupinfo, capture_output=True, text=True)
        return proc.returncode
    except Exception as err:
        print(f"Command error: {err}")
        return 1


def setup_online_host(install_dir: str, lan_folder: str, check_time: str = "11:00") -> bool:
    """Configure Online Relay Host machine."""
    os.makedirs(install_dir, exist_ok=True)
    os.makedirs(lan_folder, exist_ok=True)

    # 1. Register daily task in Task Scheduler
    if getattr(sys, "frozen", False):
        exe_path = os.path.abspath(sys.executable)
        task_cmd = [
            "schtasks", "/Create", "/SC", "DAILY",
            "/TN", "LANFileDistributor_DailyCheck",
            "/TR", f'"{exe_path}" --check',
            "/ST", check_time, "/F"
        ]
    else:
        check_script = os.path.join(install_dir, "check_updates.py")
        task_cmd = [
            "schtasks", "/Create", "/SC", "DAILY",
            "/TN", "LANFileDistributor_DailyCheck",
            "/TR", f'pythonw "{check_script}"',
            "/ST", check_time, "/F"
        ]
    code = run_command_hidden(task_cmd)

    # 2. Enable simple Windows sharing for lan_folder if net.exe is available
    share_cmd = ["net", "share", f"lan_shared_files={lan_folder}", "/GRANT:Everyone,READ"]
    run_command_hidden(share_cmd)

    return code == 0


def setup_offline_client(share_path: str, apps: list, check_time: str = "11:15") -> bool:
    """Configure Offline Client PC machine."""
    scripts_dir = r"C:\UpdateScripts"
    os.makedirs(scripts_dir, exist_ok=True)

    # Write customized pull_update.ps1 with the user's specific share path
    app_list_str = ', '.join([f'"{a.strip()}"' for a in apps if a.strip()])
    ps_content = f'''# Offline Client Silent Update Script
param (
    [string]$SharePath = "{share_path}",
    [string[]]$Apps = @({app_list_str})
)

$localStateDir = "C:\\UpdateScripts"
if (!(Test-Path $localStateDir)) {{
    New-Item -ItemType Directory -Path $localStateDir -Force | Out-Null
}}

# Auto-discover centrally managed applications from Online PC's manifest
$manifestFile = Join-Path $SharePath "manifest.json"
if (Test-Path $manifestFile) {{
    try {{
        $manifestObj = Get-Content $manifestFile -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json
        if ($manifestObj.apps) {{
            $Apps = @($manifestObj.apps.PSObject.Properties | ForEach-Object {{ $_.Name }})
        }}
    }} catch {{}}
}}

if ($Apps.Count -eq 0 -or ($Apps.Count -eq 1 -and $Apps[0] -eq "auto")) {{
    $discoveredFiles = Get-ChildItem -Path $SharePath -Filter "*_version.txt" -ErrorAction SilentlyContinue |
        Where-Object {{ $_.Name -ne "latest_version.txt" }}
    if ($discoveredFiles) {{
        $Apps = @($discoveredFiles | ForEach-Object {{ $_.BaseName -replace "_version$", "" }})
    }}
}}

if ($Apps.Count -eq 0) {{
    $Apps = @("ingetrazo", "opencadstudio")
}}

foreach ($app in $Apps) {{
    $slug = $app.Trim().ToLower()
    $versionFile = Join-Path $SharePath "$($slug)_version.txt"
    $localStateFile = Join-Path $localStateDir "$($slug)_installed_version.txt"

    if (!(Test-Path $versionFile)) {{
        $versionFile = Join-Path $SharePath "latest_version.txt"
    }}

    if (!(Test-Path $versionFile)) {{ continue }}

    $remoteVersion = (Get-Content $versionFile -ErrorAction SilentlyContinue).Trim()
    $localVersion = if (Test-Path $localStateFile) {{ (Get-Content $localStateFile -ErrorAction SilentlyContinue).Trim() }} else {{ "" }}

    if ([string]::IsNullOrWhiteSpace($remoteVersion)) {{ continue }}

    if ($remoteVersion -ne $localVersion) {{
        Stop-Process -Name $slug -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2

        $msiFile = Join-Path $SharePath "$($slug)_latest.msi"
        $exeFile = Join-Path $SharePath "$($slug)_latest.exe"
        $zipFile = Join-Path $SharePath "$($slug)_latest.zip"
        $installed = $false

        if (Test-Path $msiFile) {{
            $p = Start-Process "msiexec.exe" -ArgumentList "/i `"$msiFile`" /qn /norestart" -Wait -PassThru
            if ($p.ExitCode -eq 0) {{ $installed = $true }}
        }} elseif (Test-Path $exeFile) {{
            $p = Start-Process $exeFile -ArgumentList "/S" -Wait -PassThru
            if ($p.ExitCode -ne 0) {{
                $p = Start-Process $exeFile -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART" -Wait -PassThru
            }}
            if ($p.ExitCode -eq 0) {{ $installed = $true }}
        }} elseif (Test-Path $zipFile) {{
            Expand-Archive -Path $zipFile -DestinationPath "C:\\Program Files\\$slug" -Force
            $installed = $true
        }}

        if ($installed) {{
            $remoteVersion | Out-File $localStateFile -Force
        }}
    }}
}}

# Check for approved selective extensions
$extDir = Join-Path $SharePath "extensions"
if (Test-Path $extDir) {{
    $vFiles = Get-ChildItem -Path $extDir -Filter "*_version.txt" -ErrorAction SilentlyContinue
    $localExtDir = "C:\\UpdateScripts\\extensions"
    if (!(Test-Path $localExtDir)) {{ New-Item -ItemType Directory -Path $localExtDir -Force | Out-Null }}

    foreach ($vf in $vFiles) {{
        $eSlug = $vf.BaseName -replace "_version$", ""
        $eLocal = Join-Path $localExtDir "$($eSlug)_installed_version.txt"
        $rVer = (Get-Content $vf.FullName -ErrorAction SilentlyContinue).Trim()
        $lVer = if (Test-Path $eLocal) {{ (Get-Content $eLocal -ErrorAction SilentlyContinue).Trim() }} else {{ "" }}

        if ($rVer -and ($rVer -ne $lVer)) {{
            $eZip = Join-Path $extDir "$($eSlug)_latest.zip"
            if (Test-Path $eZip) {{
                $targetPlugin = "C:\\Program Files\\Ingetrazo\\plugins\\$eSlug"
                if (!(Test-Path $targetPlugin)) {{ New-Item -ItemType Directory -Path $targetPlugin -Force | Out-Null }}
                try {{
                    Expand-Archive -Path $eZip -DestinationPath $targetPlugin -Force
                    $rVer | Out-File $eLocal -Force
                }} catch {{}}
            }}
        }}
    }}
}}

# Report client status back to host
try {{
    $repDir = Join-Path $SharePath "clients"
    if (Test-Path $SharePath) {{
        if (!(Test-Path $repDir)) {{ New-Item -ItemType Directory -Path $repDir -Force -ErrorAction SilentlyContinue | Out-Null }}
        $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {{ $_.InterfaceAlias -notmatch 'Loopback' -and $_.IPAddress -notmatch '^169\\.' }} | Select-Object -First 1).IPAddress
        if (!$ip) {{ $ip = "Unknown" }}
        $statusObj = [PSCustomObject]@{{
            computer_name = $env:COMPUTERNAME
            ip_address = $ip
            last_seen = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
            status = "Current"
            installed_versions = @{{}}
        }}
        $statusObj | ConvertTo-Json | Out-File (Join-Path $repDir "$($env:COMPUTERNAME).json") -Force -Encoding utf8
    }}
}} catch {{}}
'''
    script_path = os.path.join(scripts_dir, "pull_update.ps1")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(ps_content)

    # Register task under highest privileges (Admin)
    task_cmd = [
        "schtasks", "/Create", "/SC", "DAILY",
        "/TN", "LANFileDistributor_ClientUpdate",
        "/TR", f'powershell.exe -ExecutionPolicy Bypass -File "{script_path}"',
        "/RL", "HIGHEST",
        "/ST", check_time, "/F"
    ]
    code = run_command_hidden(task_cmd)
    return code == 0


class UnifiedSetupApp(tk.Tk):
    """Graphical setup wizard interface."""

    def __init__(self):
        super().__init__()
        self.title("LAN File Distributor - Unified Setup")
        self.geometry("640x620")
        self.resizable(False, False)
        self.configure(bg="#09090b")

        self.role_var = tk.StringVar(value="online")
        self.build_ui()

    def build_ui(self):
        # Header
        header = tk.Frame(self, bg="#18181b", padx=20, pady=16)
        header.pack(fill="x")
        lbl_title = tk.Label(header, text="LAN File Distributor Setup", font=("Segoe UI", 16, "bold"), fg="#10b981", bg="#18181b")
        lbl_title.pack(anchor="w")
        lbl_sub = tk.Label(header, text="Unified installer for Online Host PC and Offline Client PC", font=("Segoe UI", 10), fg="#a1a1aa", bg="#18181b")
        lbl_sub.pack(anchor="w")

        # Role Selection Radio Buttons
        role_frame = tk.LabelFrame(self, text=" 1. Select Computer Role ", font=("Segoe UI", 11, "bold"), fg="#f4f4f5", bg="#09090b", padx=16, pady=12)
        role_frame.pack(fill="x", padx=20, pady=12)

        rb_online = tk.Radiobutton(
            role_frame, text="Online PC (Relay Host) - Downloads GitHub releases and shares across LAN",
            variable=self.role_var, value="online", font=("Segoe UI", 10),
            fg="#f4f4f5", bg="#09090b", selectcolor="#18181b", activebackground="#09090b",
            command=self.toggle_role_view
        )
        rb_online.pack(anchor="w", pady=4)

        rb_offline = tk.Radiobutton(
            role_frame, text="Offline PC (Target Client) - Installs updates silently from LAN share",
            variable=self.role_var, value="offline", font=("Segoe UI", 10),
            fg="#f4f4f5", bg="#09090b", selectcolor="#18181b", activebackground="#09090b",
            command=self.toggle_role_view
        )
        rb_offline.pack(anchor="w", pady=4)

        # Dynamic Options Container
        self.content_frame = tk.Frame(self, bg="#09090b", padx=20)
        self.content_frame.pack(fill="both", expand=True)

        # Footer Buttons
        footer = tk.Frame(self, bg="#18181b", padx=20, pady=12)
        footer.pack(fill="x", side="bottom")

        lbl_lic = tk.Label(footer, text="Licensed under GNU GPL v3", font=("Segoe UI", 9), fg="#71717a", bg="#18181b")
        lbl_lic.pack(side="left", padx=6)

        btn_sponsor = tk.Button(
            footer, text="❤ Sponsor", font=("Segoe UI", 9, "bold"),
            bg="#18181b", fg="#fb7185", activebackground="#27272a", activeforeground="#f43f5e",
            border=0, cursor="hand2", command=lambda: webbrowser.open("https://github.com/sponsors/keshavanarayan")
        )
        btn_sponsor.pack(side="left", padx=10)

        btn_cancel = tk.Button(footer, text="Exit", font=("Segoe UI", 10), width=10, bg="#27272a", fg="#f4f4f5", border=0, command=self.destroy)
        btn_cancel.pack(side="right", padx=6)

        btn_install = tk.Button(footer, text="Install Role", font=("Segoe UI", 10, "bold"), width=14, bg="#10b981", fg="#042f1a", border=0, command=self.run_installation)
        btn_install.pack(side="right", padx=6)

        self.toggle_role_view()

    def toggle_role_view(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        role = self.role_var.get()
        if role == "online":
            self.build_online_view()
        else:
            self.build_offline_view()

    def build_online_view(self):
        lbl = tk.Label(self.content_frame, text="Online Relay Host Configuration:", font=("Segoe UI", 11, "bold"), fg="#f4f4f5", bg="#09090b")
        lbl.pack(anchor="w", pady=(8, 4))

        tk.Label(self.content_frame, text="Target LAN Shared Directory Path:", font=("Segoe UI", 9), fg="#a1a1aa", bg="#09090b").pack(anchor="w")
        self.ent_lan_folder = tk.Entry(self.content_frame, font=("Segoe UI", 10), bg="#18181b", fg="#f4f4f5", insertbackground="#f4f4f5")
        self.ent_lan_folder.insert(0, os.path.abspath("./lan_shared_files"))
        self.ent_lan_folder.pack(fill="x", pady=4)

        tk.Label(self.content_frame, text="Morning Release Check Time (24h format):", font=("Segoe UI", 9), fg="#a1a1aa", bg="#09090b").pack(anchor="w", pady=(8, 0))
        self.ent_online_time = tk.Entry(self.content_frame, font=("Segoe UI", 10), bg="#18181b", fg="#f4f4f5", insertbackground="#f4f4f5")
        self.ent_online_time.insert(0, "11:00")
        self.ent_online_time.pack(fill="x", pady=4)

        # GitHub Repository Management Card
        repo_box = tk.LabelFrame(
            self.content_frame, text=" Manage Tracked GitHub Projects & Extensions ",
            font=("Segoe UI", 10, "bold"), fg="#10b981", bg="#09090b", padx=12, pady=10
        )
        repo_box.pack(fill="x", pady=(12, 4))

        tk.Label(
            repo_box,
            text="Add or modify GitHub repositories and extensions in the Web Dashboard, or paste a repository URL below:",
            font=("Segoe UI", 9), fg="#a1a1aa", bg="#09090b", wraplength=560, justify="left"
        ).pack(anchor="w", pady=(0, 6))

        quick_frame = tk.Frame(repo_box, bg="#09090b")
        quick_frame.pack(fill="x", pady=2)

        self.ent_quick_url = tk.Entry(quick_frame, font=("Segoe UI", 10), bg="#18181b", fg="#f4f4f5", insertbackground="#f4f4f5")
        self.ent_quick_url.insert(0, "https://github.com/owner/repository")
        self.ent_quick_url.pack(side="left", fill="x", expand=True, padx=(0, 6))

        btn_quick_add = tk.Button(
            quick_frame, text="+ Add URL", font=("Segoe UI", 9, "bold"),
            bg="#27272a", fg="#10b981", activebackground="#3f3f46", activeforeground="#34d399",
            border=0, padx=10, pady=3, cursor="hand2", command=self.quick_add_repo
        )
        btn_quick_add.pack(side="right")

        btn_launch_web = tk.Button(
            repo_box,
            text="Open Web Manager Dashboard (http://127.0.0.1:5432)",
            font=("Segoe UI", 10, "bold"), bg="#10b981", fg="#042f1a",
            activebackground="#059669", activeforeground="#ffffff",
            border=0, pady=6, cursor="hand2", command=self.launch_web_manager
        )
        btn_launch_web.pack(fill="x", pady=(10, 2))

    def quick_add_repo(self):
        """Quickly add a GitHub repository URL into config.json directly from the installer."""
        import json
        import re
        url = self.ent_quick_url.get().strip()
        if not url or "github.com" not in url or url == "https://github.com/owner/repository":
            messagebox.showwarning("Invalid URL", "Please enter a valid GitHub repository URL (e.g. https://github.com/ingelibre/ingetrazo).")
            return

        cfg_path = os.path.abspath("config.json")
        try:
            cfg = {"lan_folder": os.path.abspath("./lan_shared_files"), "check_time": "11:00", "repositories": []}
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)

            existing = [r.get("repo_url", "").lower() for r in cfg.get("repositories", [])]
            if url.lower() in existing:
                messagebox.showinfo("Already Exists", f"The repository {url} is already configured.")
                return

            repo_name = url.rstrip("/").split("/")[-1].replace(".git", "")
            repo_id = re.sub(r"[^a-zA-Z0-9_-]", "-", repo_name.lower()) + "-app"
            new_item = {
                "id": repo_id,
                "name": repo_name.capitalize(),
                "type": "app",
                "parent_app": None,
                "repo_url": url,
                "asset_pattern": ".*\\.(exe|msi|zip)$",
                "last_known_tag": "",
                "last_downloaded_tag": ""
            }
            cfg.setdefault("repositories", []).append(new_item)
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)

            messagebox.showinfo("Repository Added", f"Successfully added {repo_name} to config.json!")
            self.ent_quick_url.delete(0, tk.END)
        except Exception as err:
            messagebox.showerror("Error", f"Failed to save repository: {err}")

    def launch_web_manager(self):
        """Start manager in background if not already running and open browser."""
        import socket
        import webbrowser
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        res = sock.connect_ex(('127.0.0.1', 5432))
        sock.close()
        if res != 0:
            creationflags = 0x08000000 if sys.platform == "win32" else 0
            if getattr(sys, "frozen", False):
                subprocess.Popen([sys.executable, "--manager"], creationflags=creationflags)
            else:
                manager_script = os.path.join(os.path.abspath("."), "manager.py")
                if os.path.exists(manager_script):
                    subprocess.Popen([sys.executable, manager_script], creationflags=creationflags)
        webbrowser.open("http://127.0.0.1:5432")

    def build_offline_view(self):
        lbl = tk.Label(self.content_frame, text="Offline Target Client Configuration:", font=("Segoe UI", 11, "bold"), fg="#f4f4f5", bg="#09090b")
        lbl.pack(anchor="w", pady=(8, 4))

        tk.Label(self.content_frame, text="Online PC Network Share UNC Path:", font=("Segoe UI", 9), fg="#a1a1aa", bg="#09090b").pack(anchor="w")
        self.ent_share_path = tk.Entry(self.content_frame, font=("Segoe UI", 10), bg="#18181b", fg="#f4f4f5", insertbackground="#f4f4f5")
        self.ent_share_path.insert(0, r"\\HOST-PC\lan_shared_files")
        self.ent_share_path.pack(fill="x", pady=4)

        tk.Label(self.content_frame, text="Central Application Control (Managed from Online PC):", font=("Segoe UI", 9), fg="#a1a1aa", bg="#09090b").pack(anchor="w", pady=(8, 0))
        self.ent_apps = tk.Entry(self.content_frame, font=("Segoe UI", 10), bg="#18181b", fg="#f4f4f5", insertbackground="#f4f4f5")
        self.ent_apps.insert(0, "auto")
        self.ent_apps.pack(fill="x", pady=4)
        tk.Label(self.content_frame, text="Keep as 'auto' to automatically install all applications and extensions configured on the Online PC.", font=("Segoe UI", 8), fg="#71717a", bg="#09090b").pack(anchor="w")

        tk.Label(self.content_frame, text="Scheduled Install Time (24h format):", font=("Segoe UI", 9), fg="#a1a1aa", bg="#09090b").pack(anchor="w", pady=(8, 0))
        self.ent_offline_time = tk.Entry(self.content_frame, font=("Segoe UI", 10), bg="#18181b", fg="#f4f4f5", insertbackground="#f4f4f5")
        self.ent_offline_time.insert(0, "11:15")
        self.ent_offline_time.pack(fill="x", pady=4)

    def run_installation(self):
        role = self.role_var.get()
        if role == "online":
            lan_dir = self.ent_lan_folder.get().strip()
            time_val = self.ent_online_time.get().strip() or "11:00"
            install_dir = os.path.abspath(".")
            ok = setup_online_host(install_dir, lan_dir, time_val)
            if ok:
                messagebox.showinfo("Success", f"Online Relay Host configured successfully!\n\nTask scheduled at {time_val} daily.\nFiles shared at: {lan_dir}")
            else:
                messagebox.showwarning("Notice", "Task configured, but please ensure Task Scheduler permissions are elevated.")
        else:
            share = self.ent_share_path.get().strip()
            apps_list = [a.strip() for a in self.ent_apps.get().split(",") if a.strip()]
            time_val = self.ent_offline_time.get().strip() or "11:15"
            ok = setup_offline_client(share, apps_list, time_val)
            if ok:
                messagebox.showinfo("Success", f"Offline Client Agent configured successfully!\n\nScript installed to C:\\UpdateScripts\\pull_update.ps1\nAdmin Task scheduled at {time_val} daily.")
            else:
                messagebox.showwarning("Notice", "Script created. If task failed to register, run this installer as Administrator.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        from check_updates import run_morning_check
        run_morning_check()
        sys.exit(0)
    elif len(sys.argv) > 1 and sys.argv[1] == "--manager":
        from manager import start_manager
        start_manager()
        sys.exit(0)
    else:
        app = UnifiedSetupApp()
        app.mainloop()
