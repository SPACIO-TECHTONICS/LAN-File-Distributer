# Variables
$sourceExePath = ".\app.exe" # Change this to the actual name of your EXE file
$serverName = "KGANEWSERVER" # The name of your server from the network path

Write-Host "Starting distribution to $serverName..." -ForegroundColor Cyan

# Loop through NewUser1 to NewUser10
for ($i = 1; $i -le 10; $i++) {
    $shareName = "NewUser$i"
    $destinationPath = "\\$serverName\$shareName\"
    
    Write-Host "Processing $shareName..."
    
    try {
        # Check if the network path exists
        if (Test-Path $destinationPath) {
            # Copy the EXE file to the network share
            Copy-Item -Path $sourceExePath -Destination $destinationPath -Force
            Write-Host "  [+] Successfully copied to \\$serverName\$shareName" -ForegroundColor Green
        }
        else {
            Write-Host "  [-] Network path \\$serverName\$shareName is not accessible or does not exist." -ForegroundColor Yellow
        }
    }
    catch {
        Write-Host "  [x] Error copying to ${shareName} : $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host "Deployment finished!" -ForegroundColor Cyan
