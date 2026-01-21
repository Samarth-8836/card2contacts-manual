# Card2Contacts Database Backup Script
# Downloads daily PostgreSQL backup from remote server to local machine
# Runs via Windows Task Scheduler at 2:00 AM IST

# ===== CONFIGURATION =====
$RemoteServer = "ubuntu@43.205.99.125"
$SSHKeyPath = "D:\SECURE-DO-NOT-DELETE\Card2Contacts-app-server-access\card2contacts - app server.pem"
$RemoteProjectDir = "/opt/digicard"
$RemoteBackupDir = "/opt/digicard/backups"
$LocalBackupDir = "D:\SECURE-DO-NOT-DELETE\Card2Contacts-db-backups"
$LogDir = "D:\SECURE-DO-NOT-DELETE\Card2Contacts-db-backups\logs"
$RetentionDays = 7
$BackupTimeoutSeconds = 180

# ===== INITIALIZATION =====
$ErrorActionPreference = "Stop"
$CurrentDate = Get-Date -Format "yyyyMMdd"
$LogFile = Join-Path $LogDir "backup-$CurrentDate.log"

# ===== FUNCTIONS =====
function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogEntry = "[$Timestamp] [$Level] $Message"
    
    # Ensure log directory exists before writing
    if (-not (Test-Path $LogDir)) {
        New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    }
    
    Add-Content -Path $LogFile -Value $LogEntry
    Write-Host $LogEntry
}

function Get-BackupFilename {
    param([string]$BackupOutput)
    if ($BackupOutput -match "Backup completed: (db_backup_\d{8}_\d{6}\.sql\.gz)") {
        return $matches[1]
    }
    return $null
}

function Test-BackupFile {
    param([string]$FilePath)
    $File = Get-Item $FilePath -ErrorAction SilentlyContinue
    if ($null -eq $File) { return $false }
    if ($File.Length -eq 0) { return $false }
    return $true
}

# ===== MAIN SCRIPT =====
try {
    Write-Log "=========================================="
    Write-Log "Card2Contacts Database Backup Script Started"
    Write-Log "=========================================="
    
    # Create directories if they don't exist
    Write-Log "Creating directories..."
    New-Item -ItemType Directory -Path $LocalBackupDir -Force | Out-Null
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    Write-Log "Directories verified/created"
    
    # Pre-flight checks
    Write-Log "Running pre-flight checks..."
    
    # Check SSH key file exists
    if (-not (Test-Path $SSHKeyPath)) {
        Write-Log "ERROR: SSH key file not found at: $SSHKeyPath" "ERROR"
        exit 1
    }
    Write-Log "SSH key file verified"
    
    # Check OpenSSH availability
    $sshExists = Get-Command ssh -ErrorAction SilentlyContinue
    if (-not $sshExists) {
        Write-Log "ERROR: OpenSSH client not found. Please install OpenSSH client." "ERROR"
        exit 1
    }
    Write-Log "OpenSSH client verified"
    
    # Step 1: Trigger remote backup
    Write-Log "Triggering remote backup on server..."
    Write-Log "Command: cd $RemoteProjectDir && sudo ./backup.sh"
    
    $BackupCommand = "cd $RemoteProjectDir && sudo ./backup.sh"
    $BackupOutput = & ssh -i $SSHKeyPath $RemoteServer $BackupCommand 2>&1
    $ExitCode = $LASTEXITCODE
    
    Write-Log "Backup command output:"
    Write-Log $BackupOutput
    
    if ($ExitCode -ne 0) {
        Write-Log "ERROR: Remote backup failed with exit code $ExitCode" "ERROR"
        exit 1
    }
    
    # Parse backup filename from output
    $BackupFilename = Get-BackupFilename -BackupOutput $BackupOutput
    
    if ($null -eq $BackupFilename) {
        Write-Log "ERROR: Could not parse backup filename from output" "ERROR"
        exit 1
    }
    
    Write-Log "Remote backup completed successfully: $BackupFilename"
    
    # Step 2: Wait for file system sync
    Write-Log "Waiting 5 seconds for file system sync..."
    Start-Sleep -Seconds 5
    
    # Step 3: Verify backup file exists on remote server
    Write-Log "Verifying backup file exists on remote server..."
    $RemoteBackupPath = "$RemoteBackupDir/$BackupFilename"
    
    $CheckCommand = "test -f $RemoteBackupPath && echo EXISTS || echo NOT_FOUND"
    $CheckOutput = & ssh -i $SSHKeyPath $RemoteServer $CheckCommand 2>&1
    
    if ($CheckOutput -notmatch "EXISTS") {
        Write-Log "ERROR: Backup file not found on remote server: $RemoteBackupPath" "ERROR"
        exit 1
    }
    
    Write-Log "Backup file verified on remote server"
    
    # Step 4: Download backup
    Write-Log "Downloading backup from remote server..."
    $LocalBackupPath = Join-Path $LocalBackupDir $BackupFilename
    
    $scpCommand = "scp -i `"$SSHKeyPath`" ${RemoteServer}:${RemoteBackupPath} `"$LocalBackupPath`""
    Write-Log "SCP command: $scpCommand"
    
    Invoke-Expression $scpCommand
    $ScpExitCode = $LASTEXITCODE
    
    if ($ScpExitCode -ne 0) {
        Write-Log "ERROR: SCP download failed with exit code $ScpExitCode" "ERROR"
        exit 1
    }
    
    # Step 5: Verify downloaded file
    Write-Log "Verifying downloaded file..."
    if (-not (Test-BackupFile -FilePath $LocalBackupPath)) {
        Write-Log "ERROR: Downloaded file is invalid or empty" "ERROR"
        Remove-Item $LocalBackupPath -Force -ErrorAction SilentlyContinue
        exit 1
    }
    
    $File = Get-Item $LocalBackupPath
    $FileSizeKB = [math]::Round($File.Length / 1KB, 2)
    Write-Log "Downloaded: $BackupFilename ($FileSizeKB KB)"
    
    # Step 6: Cleanup old local backups
    Write-Log "Cleaning up old local backups (older than $RetentionDays days)..."
    
    $OldFiles = Get-ChildItem -Path $LocalBackupDir -Filter "db_backup_*.sql.gz" | 
                Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$RetentionDays) }
    
    if ($OldFiles.Count -gt 0) {
        foreach ($OldFile in $OldFiles) {
            Write-Log "Deleting old backup: $($OldFile.Name) (Age: $((Get-Date) - $OldFile.LastWriteTime).Days days)"
            Remove-Item $OldFile.FullName -Force
        }
        Write-Log "Cleanup completed: Removed $($OldFiles.Count) old backup(s)"
    } else {
        Write-Log "No old backups to clean up"
    }
    
    # Step 7: Summary
    Write-Log "=========================================="
    Write-Log "Backup Summary:"
    Write-Log "  - Downloaded: $BackupFilename"
    Write-Log "  - Size: $FileSizeKB KB"
    Write-Log "  - Location: $LocalBackupPath"
    Write-Log "  - Cleaned: $($OldFiles.Count) old backup(s)"
    Write-Log "=========================================="
    Write-Log "Script completed successfully"
    Write-Log "=========================================="
    
    exit 0
    
} catch {
    Write-Log "ERROR: Script failed with exception: $($_.Exception.Message)" "ERROR"
    Write-Log "Stack trace: $($_.ScriptStackTrace)" "ERROR"
    exit 1
}
