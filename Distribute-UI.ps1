Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# Create Main Form
$mainForm = New-Object System.Windows.Forms.Form
$mainForm.Text = "LAN File Distributor"
$mainForm.Size = New-Object System.Drawing.Size(450, 250)
$mainForm.StartPosition = "CenterScreen"
$mainForm.FormBorderStyle = "FixedDialog"
$mainForm.MaximizeBox = $false

# Title Label
$titleLabel = New-Object System.Windows.Forms.Label
$titleLabel.Text = "Deploy File to NewUser1 - NewUser10"
$titleLabel.Font = New-Object System.Drawing.Font("Segoe UI", 12, [System.Drawing.FontStyle]::Bold)
$titleLabel.AutoSize = $true
$titleLabel.Location = New-Object System.Drawing.Point(20, 15)
$mainForm.Controls.Add($titleLabel)

# File Selection Label
$fileLabel = New-Object System.Windows.Forms.Label
$fileLabel.Text = "Select EXE to Distribute:"
$fileLabel.Location = New-Object System.Drawing.Point(20, 50)
$fileLabel.AutoSize = $true
$mainForm.Controls.Add($fileLabel)

# TextBox for File Path
$fileTextBox = New-Object System.Windows.Forms.TextBox
$fileTextBox.Location = New-Object System.Drawing.Point(20, 70)
$fileTextBox.Size = New-Object System.Drawing.Size(300, 20)
$fileTextBox.ReadOnly = $true
$mainForm.Controls.Add($fileTextBox)

# Browse Button
$browseButton = New-Object System.Windows.Forms.Button
$browseButton.Text = "Browse..."
$browseButton.Location = New-Object System.Drawing.Point(330, 68)
$browseButton.Size = New-Object System.Drawing.Size(80, 25)
$mainForm.Controls.Add($browseButton)

# Distribute Button
$distributeButton = New-Object System.Windows.Forms.Button
$distributeButton.Text = "Distribute to All Users"
$distributeButton.Location = New-Object System.Drawing.Point(20, 110)
$distributeButton.Size = New-Object System.Drawing.Size(390, 40)
$distributeButton.Font = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$distributeButton.BackColor = [System.Drawing.Color]::LightGreen
$distributeButton.Enabled = $false
$mainForm.Controls.Add($distributeButton)

# Status Label
$statusLabel = New-Object System.Windows.Forms.Label
$statusLabel.Text = "Ready."
$statusLabel.Location = New-Object System.Drawing.Point(20, 160)
$statusLabel.Size = New-Object System.Drawing.Size(390, 40)
$mainForm.Controls.Add($statusLabel)

# Browse Button Click Event
$browseButton.Add_Click({
        $openFileDialog = New-Object System.Windows.Forms.OpenFileDialog
        $openFileDialog.Filter = "Executable files (*.exe)|*.exe|All files (*.*)|*.*"
        $openFileDialog.Title = "Select File to Distribute"
    
        if ($openFileDialog.ShowDialog() -eq "OK") {
            $fileTextBox.Text = $openFileDialog.FileName
            $distributeButton.Enabled = $true
        }
    })

# Distribute Button Click Event
$distributeButton.Add_Click({
        $sourceFile = $fileTextBox.Text
        $serverName = "KGANEWSERVER"
    
        $distributeButton.Enabled = $false
        $browseButton.Enabled = $false
    
        $successCount = 0
        $failCount = 0

        $statusLabel.Text = "Deploying..."
        $mainForm.Refresh()

        for ($i = 1; $i -le 10; $i++) {
            $shareName = "NewUser$i"
            $destinationPath = "\\$serverName\$shareName\"
        
            $statusLabel.Text = "Deploying to $shareName..."
            $mainForm.Refresh()
        
            try {
                if (Test-Path $destinationPath) {
                    # Copy the file
                    $fileName = Split-Path $sourceFile -Leaf
                    Copy-Item -Path $sourceFile -Destination "$destinationPath\$fileName" -Force
                    $successCount++
                }
                else {
                    $failCount++
                }
            }
            catch {
                $failCount++
            }
        }
    
        # Final Status update
        if ($failCount -eq 0) {
            $statusLabel.Text = "Success! Deployed to $successCount users."
            $statusLabel.ForeColor = [System.Drawing.Color]::Green
        }
        else {
            $statusLabel.Text = "Finished! Success: $successCount, Failed: $failCount users.`nCheck permissions or network connection."
            $statusLabel.ForeColor = [System.Drawing.Color]::Red
        }
    
        $distributeButton.Enabled = $true
        $browseButton.Enabled = $true
    })

# Show the Form
$mainForm.Topmost = $true
$mainForm.ShowDialog() | Out-Null
