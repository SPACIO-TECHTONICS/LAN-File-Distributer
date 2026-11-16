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
#
# ==============================================================================
# Client Silent Update Script for Offline LAN PC
# Runs under Admin account via Windows Task Scheduler.
# Checks the online PC's shared folder, installs approved applications
# and approved extensions silently, then reports client status to host.
# ==============================================================================

param (
    [string]$SharePath = "\\HOST-PC\lan_shared_files",
    [string[]]$Apps = @("ingetrazo", "opencadstudio")
)

$localStateDir = "C:\UpdateScripts"
$localExtStateDir = "C:\UpdateScripts\extensions"
if (!(Test-Path $localStateDir)) {
    New-Item -ItemType Directory -Path $localStateDir -Force | Out-Null
}
if (!(Test-Path $localExtStateDir)) {
    New-Item -ItemType Directory -Path $localExtStateDir -Force | Out-Null
}

$clientsReportDir = Join-Path $SharePath "clients"
$extensionsShareDir = Join-Path $SharePath "extensions"

$installedVersions = @{}
$overallStatus = "Current"

Write-Host "[Offline Relay] Checking for software updates in: $SharePath"

# ------------------------------------------------------------------------------
# 1. Update Main Applications (Centrally Controlled from Online PC)
# ------------------------------------------------------------------------------
# Automatically resolve apps from Online PC's central manifest.json
$manifestPath = Join-Path $SharePath "manifest.json"
if (Test-Path $manifestPath) {
    try {
        $manifestObj = Get-Content $manifestPath -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json
        if ($manifestObj.apps) {
            $manifestApps = @($manifestObj.apps.PSObject.Properties | ForEach-Object { $_.Name })
            if ($manifestApps.Count -gt 0) {
                $Apps = $manifestApps
            }
        }
    } catch {}
}

# Dynamic discovery fallback: scan for any <slug>_version.txt on the LAN share
if ($Apps.Count -eq 0 -or ($Apps.Count -eq 1 -and $Apps[0] -eq "auto")) {
    $discoveredAppFiles = Get-ChildItem -Path $SharePath -Filter "*_version.txt" -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne "latest_version.txt" }
    if ($discoveredAppFiles) {
        $Apps = @($discoveredAppFiles | ForEach-Object { $_.BaseName -replace "_version$", "" })
    }
}

if ($Apps.Count -eq 0) {
    $Apps = @("ingetrazo", "opencadstudio")
}

foreach ($app in $Apps) {
    $slug = $app.Trim().ToLower()
    $versionFile = Join-Path $SharePath "$($slug)_version.txt"
    $localStateFile = Join-Path $localStateDir "$($slug)_installed_version.txt"

    if (!(Test-Path $versionFile)) {
        $versionFile = Join-Path $SharePath "latest_version.txt"
    }

    $localVersion = if (Test-Path $localStateFile) { (Get-Content $localStateFile -ErrorAction SilentlyContinue).Trim() } else { "None" }

    if (!(Test-Path $versionFile)) {
        $installedVersions[$slug] = $localVersion
        continue
    }

    $remoteVersion = (Get-Content $versionFile -ErrorAction SilentlyContinue).Trim()
    if ([string]::IsNullOrWhiteSpace($remoteVersion)) {
        $installedVersions[$slug] = $localVersion
        continue
    }

    if ($remoteVersion -ne $localVersion) {
        Write-Host " -> Update available for $slug ($localVersion ➔ $remoteVersion). Installing..."
        $overallStatus = "Updated"

        Stop-Process -Name $slug -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2

        $msiFile = Join-Path $SharePath "$($slug)_latest.msi"
        $exeFile = Join-Path $SharePath "$($slug)_latest.exe"
        $zipFile = Join-Path $SharePath "$($slug)_latest.zip"
        $installSuccess = $false

        if (Test-Path $msiFile) {
            Write-Host "   Installing MSI package..."
            $proc = Start-Process "msiexec.exe" -ArgumentList "/i `"$msiFile`" /qn /norestart" -Wait -PassThru
            if ($proc.ExitCode -eq 0) { $installSuccess = $true }
        }
        elseif (Test-Path $exeFile) {
            Write-Host "   Installing EXE package..."
            $proc = Start-Process $exeFile -ArgumentList "/S" -Wait -PassThru
            if ($proc.ExitCode -ne 0) {
                $proc = Start-Process $exeFile -ArgumentList "/VERYSILENT /SUPPRESSMSGBOXES /NORESTART" -Wait -PassThru
            }
            if ($proc.ExitCode -eq 0) { $installSuccess = $true }
        }
        elseif (Test-Path $zipFile) {
            Write-Host "   Extracting portable ZIP package..."
            $targetDir = "C:\Program Files\$slug"
            Expand-Archive -Path $zipFile -DestinationPath $targetDir -Force
            $installSuccess = $true
        }

        if ($installSuccess) {
            $remoteVersion | Out-File $localStateFile -Force
            $installedVersions[$slug] = $remoteVersion
            Write-Host "   [Success] $slug updated to $remoteVersion."
        } else {
            $installedVersions[$slug] = $localVersion
            $overallStatus = "Install Warning"
        }
    } else {
        $installedVersions[$slug] = $localVersion
        Write-Host " -> $slug is up to date ($localVersion)."
    }
}

# ------------------------------------------------------------------------------
# 2. Update Approved Extensions (Selective Installation Only)
# ------------------------------------------------------------------------------
if (Test-Path $extensionsShareDir) {
    Write-Host "[Offline Relay] Checking for approved extensions in: $extensionsShareDir"
    $extVersionFiles = Get-ChildItem -Path $extensionsShareDir -Filter "*_version.txt" -ErrorAction SilentlyContinue

    foreach ($vFile in $extVersionFiles) {
        $extSlug = $vFile.BaseName -replace "_version$", ""
        $extLocalState = Join-Path $localExtStateDir "$($extSlug)_installed_version.txt"
        $remoteExtVersion = (Get-Content $vFile.FullName -ErrorAction SilentlyContinue).Trim()
        $localExtVersion = if (Test-Path $extLocalState) { (Get-Content $extLocalState -ErrorAction SilentlyContinue).Trim() } else { "None" }

        if ([string]::IsNullOrWhiteSpace($remoteExtVersion)) { continue }

        if ($remoteExtVersion -ne $localExtVersion) {
            Write-Host " -> Extension update available for $extSlug ($localExtVersion ➔ $remoteExtVersion)..."
            $extZip = Join-Path $extensionsShareDir "$($extSlug)_latest.zip"

            if (Test-Path $extZip) {
                # Target IngeTrazo system-wide plugins directory
                $pluginTargetDir = "C:\Program Files\Ingetrazo\plugins\$extSlug"
                if (!(Test-Path $pluginTargetDir)) {
                    New-Item -ItemType Directory -Path $pluginTargetDir -Force | Out-Null
                }

                try {
                    Expand-Archive -Path $extZip -DestinationPath $pluginTargetDir -Force
                    $remoteExtVersion | Out-File $extLocalState -Force
                    $installedVersions["ext:$extSlug"] = $remoteExtVersion
                    Write-Host "   [Success] Extension $extSlug installed to $pluginTargetDir."
                } catch {
                    Write-Host "   [Error] Failed to extract extension $extSlug: $_"
                }
            }
        } else {
            $installedVersions["ext:$extSlug"] = $localExtVersion
            Write-Host " -> Extension $extSlug is up to date ($localExtVersion)."
        }
    }
}

# ------------------------------------------------------------------------------
# 3. Report Client Status to Online Host
# ------------------------------------------------------------------------------
try {
    if (Test-Path $clientsReportDir) {
        $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch 'Loopback' -and $_.IPAddress -notmatch '^169\.' } | Select-Object -First 1).IPAddress
        if (!$ip) { $ip = "Unknown" }

        $report = [PSCustomObject]@{
            computer_name      = $env:COMPUTERNAME
            ip_address         = $ip
            last_seen          = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
            status             = $overallStatus
            installed_versions = $installedVersions
        }

        $reportPath = Join-Path $clientsReportDir "$($env:COMPUTERNAME).json"
        $report | ConvertTo-Json -Depth 3 | Out-File $reportPath -Force -Encoding utf8
        Write-Host "[Offline Relay] Reported status to host: $reportPath"
    }
} catch {
    Write-Host "[Notice] Could not write client status report: $_"
}

Write-Host "[Offline Relay] Check finished."
