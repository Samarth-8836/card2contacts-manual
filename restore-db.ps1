# Card2Contacts Database Restore Script
# Restores PostgreSQL database from local backup to remote server
# Usage: powershell -ExecutionPolicy Bypass -File "D:\Code Projects\c2c-demo hosted\DigiCard-Enterprise\restore-db.ps1"

# ===== CONFIGURATION =====
$LocalBackupDir = "D:\SECURE-DO-NOT-DELETE\Card2Contacts-db-backups"
$LogDir = "D:\SECURE-DO-NOT-DELETE\Card2Contacts-db-backups\restore-logs"
$DBUser = "admin"
$DBName = "scanner_prod"

# ===== INITIALIZATION =====
$ErrorActionPreference = "Stop"
$CurrentTimestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$LogFile = Join-Path $LogDir "restore-$CurrentTimestamp.log"

# Ensure log directory exists
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# ===== FUNCTIONS =====
function Write-RestoreLog {
    param([string]$Message, [string]$Level = "INFO")
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogEntry = "[$Timestamp] [$Level] $Message"
    
    Add-Content -Path $LogFile -Value $LogEntry
    
    # Color-coded console output
    switch ($Level) {
        "ERROR"   { Write-Host $LogEntry -ForegroundColor Red }
        "WARN"    { Write-Host $LogEntry -ForegroundColor Yellow }
        "SUCCESS" { Write-Host $LogEntry -ForegroundColor Green }
        "INFO"    { Write-Host $LogEntry -ForegroundColor Cyan }
        default   { Write-Host $LogEntry }
    }
}

function Get-UserInput {
    param(
        [string]$Prompt,
        [string]$Default = "",
        [bool]$Required = $true,
        [bool]$AsSecureString = $false
    )
    
    $defaultText = if ($Default -ne "") { "[$Default]" } else { "" }
    $displayPrompt = $Prompt + " " + $defaultText + ": "
    
    if ($AsSecureString) {
        $secureString = Read-Host $displayPrompt -AsSecureString
        $plainText = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureString))
        if ($plainText -eq "" -and $Default -ne "") {
            return $Default
        }
        return $plainText
    }
    
    $input = Read-Host $displayPrompt
    if ($input -eq "" -and $Default -ne "") {
        return $Default
    }
    
    if ($Required -and $input -eq "") {
        Write-RestoreLog "ERROR: This field is required." "ERROR"
        return Get-UserInput -Prompt $Prompt -Default $Default -Required $Required -AsSecureString $AsSecureString
    }
    
    return $input
}

function Invoke-SSHCommand {
    param(
        [string]$Server,
        [string]$Username,
        [string]$KeyPath,
        [string]$Command,
        [int]$Timeout = 300
    )
    
    $fullCommand = "ssh -i `"$KeyPath`" ${Username}@${Server} `"$Command`""
    Write-RestoreLog "Executing SSH command: $Command"
    
    try {
        $output = Invoke-Expression $fullCommand
        return @{
            Success = $true
            Output = $output
            ExitCode = $LASTEXITCODE
        }
    } catch {
        return @{
            Success = $false
            Output = $_.Exception.Message
            ExitCode = 1
        }
    }
}

function Upload-FileViaSCP {
    param(
        [string]$LocalFile,
        [string]$RemotePath,
        [string]$Server,
        [string]$Username,
        [string]$KeyPath
    )
    
    $scpCommand = "scp -i `"$KeyPath`" `"$LocalFile`" ${Username}@${Server}:${RemotePath}"
    Write-RestoreLog "Uploading file: $LocalFile -> ${Username}@${Server}:${RemotePath}"
    
    try {
        Invoke-Expression $scpCommand
        $success = ($LASTEXITCODE -eq 0)
        
        if ($success) {
            Write-RestoreLog "File uploaded successfully" "SUCCESS"
        } else {
            Write-RestoreLog "File upload failed with exit code: $LASTEXITCODE" "ERROR"
        }
        
        return $success
    } catch {
        Write-RestoreLog "File upload failed: $($_.Exception.Message)" "ERROR"
        return $false
    }
}

function Get-ContainerStatus {
    param(
        [string]$Server,
        [string]$Username,
        [string]$KeyPath,
        [string]$ContainerName
    )
    
    $command = "docker ps --filter name=$ContainerName --format '{{.Status}}'"
    $result = Invoke-SSHCommand -Server $Server -Username $Username -KeyPath $KeyPath -Command $command
    
    if ($result.Success -and $result.Output) {
        $cleanOutput = ("$($result.Output)").Trim()
        
        if ($cleanOutput -ne "") {
            return $cleanOutput
        }
    }
    
    return $null
}

function Stop-Container {
    param(
        [string]$Server,
        [string]$Username,
        [string]$KeyPath,
        [string]$ContainerName,
        [int]$WaitSeconds = 30
    )
    
    Write-RestoreLog "Stopping container: $ContainerName"
    
    $command = "sudo docker stop $ContainerName"
    $result = Invoke-SSHCommand -Server $Server -Username $Username -KeyPath $KeyPath -Command $command
    
    if (-not $result.Success) {
        Write-RestoreLog "Failed to stop container $ContainerName" "ERROR"
        return $false
    }
    
    Write-RestoreLog "Waiting $WaitSeconds seconds for container to stop..."
    Start-Sleep -Seconds $WaitSeconds
    
    # Verify container is stopped
    $status = Get-ContainerStatus -Server $Server -Username $Username -KeyPath $KeyPath -ContainerName $ContainerName
    if ($status -eq $null -or -not $status.StartsWith("Up")) {
        Write-RestoreLog "Container $ContainerName stopped successfully" "SUCCESS"
        return $true
    } else {
        Write-RestoreLog "Container $ContainerName still running. Status: $status" "WARN"
        return $false
    }
}

function Start-Container {
    param(
        [string]$Server,
        [string]$Username,
        [string]$KeyPath,
        [string]$ContainerName,
        [int]$WaitSeconds = 30
    )
    
    Write-RestoreLog "Starting container: $ContainerName"
    
    $command = "sudo docker start $ContainerName"
    $result = Invoke-SSHCommand -Server $Server -Username $Username -KeyPath $KeyPath -Command $command
    
    if (-not $result.Success) {
        Write-RestoreLog "Failed to start container $ContainerName" "ERROR"
        return $false
    }
    
    Write-RestoreLog "Waiting $WaitSeconds seconds for container to be ready..."
    Start-Sleep -Seconds $WaitSeconds
    
    # Verify container is running
    $status = Get-ContainerStatus -Server $Server -Username $Username -KeyPath $KeyPath -ContainerName $ContainerName
    if ($status -and $status.StartsWith("Up")) {
        Write-RestoreLog "Container $ContainerName started successfully. Status: $status" "SUCCESS"
        return $true
    } else {
        Write-RestoreLog "Container $ContainerName not running. Status: $status" "ERROR"
        return $false
    }
}

# ===== MAIN SCRIPT =====
try {
    Write-RestoreLog "=========================================="
    Write-RestoreLog "Card2Contacts Database Restore Script"
    Write-RestoreLog "=========================================="
    Write-RestoreLog ""
    
    # Step 1: Collect SSH key path
    Write-RestoreLog "Step 1: SSH Key Configuration"
    $SSHKeyPath = Get-UserInput -Prompt "Enter SSH private key path" -Required $true
    
    if (-not (Test-Path -Path $SSHKeyPath -PathType Leaf)) {
        Write-RestoreLog "ERROR: SSH key file not found at: $SSHKeyPath" "ERROR"
        Write-RestoreLog "Please provide the full path to the SSH key FILE (e.g., D:\path\key.pem), not the directory." "ERROR"
        exit 1
    }
    Write-RestoreLog "SSH key file verified: $SSHKeyPath" "SUCCESS"
    
    # Fix SSH key permissions automatically
    Write-RestoreLog "Fixing SSH key permissions..."
    Write-RestoreLog "SSH key path to fix: $SSHKeyPath"
    
    # Convert to absolute path
    try {
        $SSHKeyPath = Resolve-Path -Path $SSHKeyPath -ErrorAction Stop
        Write-RestoreLog "Resolved absolute path: $SSHKeyPath"
    } catch {
        Write-RestoreLog "ERROR: Failed to resolve path: $($_.Exception.Message)" "ERROR"
        exit 1
    }
    
    . "$PSScriptRoot\fix-ssh-permissions.ps1" | Out-Null
    $permissionFixed = Fix-SSHKeyPermissions -KeyPath $SSHKeyPath -Silent $true
    
    if (-not $permissionFixed) {
        Write-RestoreLog "ERROR: Failed to fix SSH key permissions. Try running as Administrator." "ERROR"
        exit 1
    }
    Write-RestoreLog "SSH key permissions fixed successfully" "SUCCESS"
    Write-RestoreLog ""
    
    # Step 2: Collect server details
    Write-RestoreLog "Step 2: Target Server Configuration"
    $ServerIP = Get-UserInput -Prompt "Enter target server IP address" -Required $true
    $SSHUser = Get-UserInput -Prompt "Enter SSH username" -Default "ubuntu"
    $DockerComposePath = Get-UserInput -Prompt "Enter docker-compose file path" -Default "/opt/digicard/docker-compose.production.yml"
    $ProjectDir = Get-UserInput -Prompt "Enter project directory" -Default "/opt/digicard"
    $PostgresPassword = Get-UserInput -Prompt "Enter POSTGRES_PASSWORD" -Required $true -AsSecureString $true
    Write-RestoreLog "Server configuration collected"
    Write-RestoreLog ""
    
    # Step 3: List available backups
    Write-RestoreLog "Step 3: Select Backup File"
    $backups = Get-ChildItem -Path $LocalBackupDir -Filter "*.sql.gz" | 
               Sort-Object LastWriteTime -Descending
    
    if ($backups.Count -eq 0) {
        Write-RestoreLog "ERROR: No backup files found in $LocalBackupDir" "ERROR"
        exit 1
    }
    
    Write-Host ""
    Write-Host "Available backup files:" -ForegroundColor Cyan
    for ($i = 0; $i -lt $backups.Count; $i++) {
        $sizeKB = [math]::Round($backups[$i].Length / 1KB, 2)
        $dateStr = $backups[$i].LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
        Write-Host "  $($i + 1). $($backups[$i].Name) ($sizeKB KB) - $dateStr" -ForegroundColor White
    }
    Write-Host ""
    
    $backupChoice = Get-UserInput -Prompt "Select backup file (1-$($backups.Count), or 'q' to quit)"
    
    if ($backupChoice -eq "q") {
        Write-RestoreLog "Restore cancelled by user" "INFO"
        exit 0
    }
    
    try {
        $backupIndex = [int]$backupChoice - 1
        if ($backupIndex -lt 0 -or $backupIndex -ge $backups.Count) {
            Write-RestoreLog "ERROR: Invalid selection" "ERROR"
            exit 1
        }
    } catch {
        Write-RestoreLog "ERROR: Invalid selection. Please enter a number." "ERROR"
        exit 1
    }
    
    $SelectedBackup = $backups[$backupIndex]
    $BackupFileName = $SelectedBackup.Name
    $BackupSizeKB = [math]::Round($SelectedBackup.Length / 1KB, 2)
    
    Write-RestoreLog "Selected backup: $BackupFileName ($BackupSizeKB KB)"
    Write-RestoreLog ""
    
    # Step 4: Confirmation
    Write-RestoreLog "Step 4: Confirmation"
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "Restore Configuration Summary:" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "  Target Server: $ServerIP" -ForegroundColor White
    Write-Host "  SSH Username: $SSHUser" -ForegroundColor White
    Write-Host "  Project Dir: $ProjectDir" -ForegroundColor White
    Write-Host "  Backup File: $BackupFileName ($BackupSizeKB KB)" -ForegroundColor White
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host ""
    
    $confirmation = Get-UserInput -Prompt "Type 'CONFIRM' to proceed or 'CANCEL' to abort" -Required $false
    
    if ($confirmation -ne "CONFIRM") {
        Write-RestoreLog "Restore cancelled by user" "INFO"
        exit 0
    }
    
    Write-RestoreLog "User confirmed restore operation"
    Write-RestoreLog ""
    
    # Step 5: Create safety backup
    Write-RestoreLog "Step 5: Creating Safety Backup"
    $SafetyBackupCommand = "cd $ProjectDir && sudo chmod +x backup.sh && sudo ./backup.sh"

    $SafetyBackupResult = Invoke-SSHCommand -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -Command $SafetyBackupCommand
    
    if (-not $SafetyBackupResult.Success -or $SafetyBackupResult.ExitCode -ne 0) {
        Write-RestoreLog "ERROR: Safety backup creation failed" "ERROR"
        Write-RestoreLog "Output: $($SafetyBackupResult.Output)" "ERROR"
        exit 1
    }
    
    # Parse safety backup filename
    # Flatten the output array to a single string so -match populates $matches
    $OutputString = $SafetyBackupResult.Output -join "`n"

    # Parse safety backup filename
    if ($OutputString -match "Backup completed: (db_backup_\d{8}_\d{6}\.sql\.gz)") {
        $SafetyBackupFile = $matches[1]
        Write-RestoreLog "Safety backup created: $SafetyBackupFile" "SUCCESS"
    } else {
        Write-RestoreLog "ERROR: Could not parse safety backup filename" "ERROR"
        Write-RestoreLog "Full Output received from server:" "WARN"
        Write-RestoreLog $OutputString "WARN"
        exit 1
    }
    Write-RestoreLog ""
    
    # Step 6: Stop services
    Write-RestoreLog "Step 6: Stopping Services"
    
    # Stop frontend
    $frontendStopped = Stop-Container -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -ContainerName "scanner_frontend" -WaitSeconds 30
    if (-not $frontendStopped) {
        Write-RestoreLog "ERROR: Failed to stop frontend container" "ERROR"
        Write-RestoreLog "Attempting to force stop..." "WARN"
        $forceCommand = "sudo docker kill scanner_frontend"
        Invoke-SSHCommand -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -Command $forceCommand | Out-Null
    }
    
    # Stop backend
    $backendStopped = Stop-Container -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -ContainerName "scanner_backend" -WaitSeconds 30
    if (-not $backendStopped) {
        Write-RestoreLog "ERROR: Failed to stop backend container" "ERROR"
        Write-RestoreLog "Attempting to force stop..." "WARN"
        $forceCommand = "sudo docker kill scanner_backend"
        Invoke-SSHCommand -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -Command $forceCommand | Out-Null
    }
    Write-RestoreLog ""
    
    # Step 7: Upload backup file
    Write-RestoreLog "Step 7: Uploading Backup File"
    $RemoteBackupDir = "$ProjectDir/backups"
    
    # Upload to /tmp first to avoid "Permission denied" errors
    $TempRemotePath = "/tmp"
    Write-RestoreLog "Uploading to temporary location (/tmp) to avoid permission errors..."
    
    $UploadSuccess = Upload-FileViaSCP -LocalFile $SelectedBackup.FullName -RemotePath $TempRemotePath -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath
    
    if ($UploadSuccess) {
        Write-RestoreLog "File uploaded to /tmp successfully. Moving to final destination..."
        
        # Use sudo to move the file from /tmp to the protected directory
        # We assume the filename remains the same when uploaded to directory
        $MoveCommand = "sudo mkdir -p $RemoteBackupDir && sudo mv /tmp/$BackupFileName $RemoteBackupDir/$BackupFileName"
        
        $MoveResult = Invoke-SSHCommand -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -Command $MoveCommand
        
        if (-not $MoveResult.Success -or $MoveResult.ExitCode -ne 0) {
            Write-RestoreLog "ERROR: Failed to move file to protected directory" "ERROR"
            Write-RestoreLog "Output: $($MoveResult.Output)" "ERROR"
            $UploadSuccess = $false
        } else {
            Write-RestoreLog "File moved to $RemoteBackupDir successfully" "SUCCESS"
        }
    }
    
    if (-not $UploadSuccess) {
        Write-RestoreLog "ERROR: Failed to upload backup file" "ERROR"
        Write-RestoreLog "Attempting to restart services..." "WARN"
        Start-Container -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -ContainerName "scanner_backend" | Out-Null
        Start-Container -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -ContainerName "scanner_frontend" | Out-Null
        exit 1
    }
    Write-RestoreLog ""
    
    # Step 8: Decompress backup
    Write-RestoreLog "Step 8: Decompressing Backup File"
    $RemoteBackupPath = "$RemoteBackupDir/$BackupFileName"
    $DecompressCommand = "cd $RemoteBackupDir && sudo gunzip -k $BackupFileName"
    $DecompressResult = Invoke-SSHCommand -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -Command $DecompressCommand
    
    if (-not $DecompressResult.Success -or $DecompressResult.ExitCode -ne 0) {
        Write-RestoreLog "ERROR: Failed to decompress backup file" "ERROR"
        Write-RestoreLog "Output: $($DecompressResult.Output)" "ERROR"
        Write-RestoreLog "Attempting to restart services..." "WARN"
        Start-Container -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -ContainerName "scanner_backend" | Out-Null
        Start-Container -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -ContainerName "scanner_frontend" | Out-Null
        exit 1
    }
    
    $SqlFileName = $BackupFileName -replace '\.gz$', ''
    Write-RestoreLog "Backup decompressed: $SqlFileName" "SUCCESS"
    Write-RestoreLog ""
    
    # Step 9: Restore database
    Write-RestoreLog "Step 9: Restoring Database"

    Write-RestoreLog "Cleaning existing database (Wiping all data)..."
    
    # This command drops the public schema and recreates it, effectively wiping the DB
    $CleanCommand = "cd $ProjectDir && sudo docker-compose -f $DockerComposePath exec -T db psql -U $DBUser -d $DBName -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'"
    
    $CleanResult = Invoke-SSHCommand -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -Command $CleanCommand
    
    if (-not $CleanResult.Success -or $CleanResult.ExitCode -ne 0) {
        Write-RestoreLog "ERROR: Failed to clean database" "ERROR"
        Write-RestoreLog "Output: $($CleanResult.Output)" "ERROR"
        Write-RestoreLog "Attempting to restart services..." "WARN"
        Start-Container -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -ContainerName "scanner_backend" | Out-Null
        Start-Container -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -ContainerName "scanner_frontend" | Out-Null
        exit 1
    }
    Write-RestoreLog "Database wiped successfully" "SUCCESS"

    $RestoreCommand = "cd $ProjectDir && sudo docker-compose -f $DockerComposePath exec -T db psql -U $DBUser -d $DBName < $RemoteBackupDir/$SqlFileName"
    Write-RestoreLog "Executing restore command (this may take a few minutes)..."
    
    $RestoreResult = Invoke-SSHCommand -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -Command $RestoreCommand -Timeout 600
    
    if (-not $RestoreResult.Success -or $RestoreResult.ExitCode -ne 0) {
        Write-RestoreLog "ERROR: Database restore failed" "ERROR"
        Write-RestoreLog "Output: $($RestoreResult.Output)" "ERROR"
        Write-RestoreLog "Attempting to restart services..." "WARN"
        Start-Container -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -ContainerName "scanner_backend" | Out-Null
        Start-Container -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -ContainerName "scanner_frontend" | Out-Null
        exit 1
    }
    
    Write-RestoreLog "Database restored successfully" "SUCCESS"
    Write-RestoreLog ""
    
    # Step 10: Start services
    Write-RestoreLog "Step 10: Starting Services"
    
    $backendStarted = Start-Container -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -ContainerName "scanner_backend" -WaitSeconds 30
    if (-not $backendStarted) {
        Write-RestoreLog "ERROR: Failed to start backend container" "ERROR"
        exit 1
    }
    
    $frontendStarted = Start-Container -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -ContainerName "scanner_frontend" -WaitSeconds 10
    if (-not $frontendStarted) {
        Write-RestoreLog "ERROR: Failed to start frontend container" "ERROR"
        exit 1
    }
    Write-RestoreLog ""
    
    # Step 11: Cleanup
    Write-RestoreLog "Step 11: Cleanup"
    $CleanupCommand = "cd $RemoteBackupDir && sudo rm -f $BackupFileName $SqlFileName"
    $CleanupResult = Invoke-SSHCommand -Server $ServerIP -Username $SSHUser -KeyPath $SSHKeyPath -Command $CleanupCommand
    
    if ($CleanupResult.Success) {
        Write-RestoreLog "Cleanup completed successfully" "SUCCESS"
    } else {
        Write-RestoreLog "WARNING: Cleanup failed. Manual cleanup may be required." "WARN"
    }
    Write-RestoreLog ""
    
    # Step 12: Summary
    Write-RestoreLog "=========================================="
    Write-RestoreLog "RESTORE SUMMARY"
    Write-RestoreLog "=========================================="
    Write-RestoreLog "  Target Server: $ServerIP"
    Write-RestoreLog "  Backup File: $BackupFileName ($BackupSizeKB KB)"
    Write-RestoreLog "  Safety Backup: $SafetyBackupFile"
    Write-RestoreLog "  Services: Stopped and Restarted"
    Write-RestoreLog "  Status: SUCCESS"
    Write-RestoreLog "=========================================="
    Write-RestoreLog ""
    Write-RestoreLog "Log file: $LogFile"
    Write-RestoreLog "=========================================="
    
    Write-Host ""
    Write-Host "Restore completed successfully!" -ForegroundColor Green
    Write-Host "Log file: $LogFile" -ForegroundColor Cyan
    Write-Host ""
    
    exit 0
    
} catch {
    Write-RestoreLog "ERROR: Restore failed with exception: $($_.Exception.Message)" "ERROR"
    Write-RestoreLog "Stack trace: $($_.ScriptStackTrace)" "ERROR"
    Write-RestoreLog "Log file: $LogFile" "ERROR"
    exit 1
}
