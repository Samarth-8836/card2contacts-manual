# Fix SSH Key File Permissions
# This script can be used in two ways:
# 1. Standalone: Run with -SSHKeyPath parameter to fix a specific key
# 2. Dot-sourced: Import into other scripts to use Fix-SSHKeyPermissions function
 
# Check if script is being dot-sourced
if ($MyInvocation.InvocationName -ne '.') {
    
    # Parameter for standalone mode only
    param(
        [Parameter(Mandatory=$false)]
        [string]$SSHKeyPath
    )
    
    # Script is run directly - standalone mode
    if (-not $SSHKeyPath) {
        Write-Host "Usage: powershell -ExecutionPolicy Bypass -File `"fix-ssh-permissions.ps1`" -SSHKeyPath `"<path-to-ssh-key>`"" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Example:" -ForegroundColor Yellow
        Write-Host '  powershell -ExecutionPolicy Bypass -File "fix-ssh-permissions.ps1" -SSHKeyPath "D:\path\to\key.pem"' -ForegroundColor White
        exit 0
    }
    
    # Check if file exists
    if (-not (Test-Path $SSHKeyPath)) {
        Write-Host "Error: SSH key file not found: $SSHKeyPath" -ForegroundColor Red
        exit 1
    }
    
    # Fix permissions interactively
    Fix-SSHKeyPermissions -KeyPath $SSHKeyPath -Silent $false
}

# ===== FUNCTION =====
function Fix-SSHKeyPermissions {
    param(
        [Parameter(Mandatory=$true)]
        [string]$KeyPath,
        [bool]$Silent = $false
    )
    
    # Validate parameter is not empty
    if ([string]::IsNullOrWhiteSpace($KeyPath)) {
        if (-not $Silent) {
            Write-Host "Error: SSH key path is empty or whitespace" -ForegroundColor Red
        }
        return $false
    }
    
    # Validate path is a file, not a directory
    if (-not (Test-Path -Path $KeyPath -PathType Leaf)) {
        if (-not $Silent) {
            Write-Host "Error: Path is not a file: $KeyPath" -ForegroundColor Red
        }
        return $false
    }
    
    if (-not $Silent) {
        Write-Host "KeyPath to fix: $KeyPath" -ForegroundColor Cyan
        Write-Host ""
    }
    
    $logFunction = if ($Silent) { $null } else { { param($msg, $lvl) Write-Host $msg -ForegroundColor $lvl } }
    
    if (-not $Silent) {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "Fixing SSH Key File Permissions" -ForegroundColor Cyan
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host "Path: $KeyPath" -ForegroundColor Yellow
        Write-Host ""
    }
    
    try {
        # Check if running as administrator
        $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
        
        if (-not $isAdmin) {
            if (-not $Silent) {
                Write-Host "Warning: Not running as administrator" -ForegroundColor Yellow
                Write-Host "Attempting to fix permissions with current user privileges..." -ForegroundColor Yellow
                Write-Host ""
            }
        }
        
        # Get current ACL
        $acl = Get-Acl $KeyPath
        
        # Store current user
        $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        
        # Remove inheritance and disable inheritance
        if (-not $Silent) {
            Write-Host "Removing inheritance..." -ForegroundColor Cyan
        }
        $acl.SetAccessRuleProtection($true, $false)
        
        # Clear existing access rules
        if (-not $Silent) {
            Write-Host "Clearing existing access rules..." -ForegroundColor Cyan
        }
        foreach ($accessRule in $acl.Access) {
            try {
                $acl.RemoveAccessRule($accessRule) | Out-Null
            } catch {
                # Ignore rules that can't be removed
            }
        }
        
        # Create access rule for current user only
        if (-not $Silent) {
            Write-Host "Adding access rule for: $currentUser" -ForegroundColor Cyan
        }
        $accessRule = New-Object System.Security.AccessControl.FileSystemAccessRule(
            $currentUser,
            'FullControl',
            'Allow'
        )
        $acl.SetAccessRule($accessRule)
        
        # Apply permissions
        if (-not $Silent) {
            Write-Host "Applying permissions..." -ForegroundColor Cyan
        }
        Set-Acl $KeyPath $acl
        
        # Verify the fix
        $newAcl = Get-Acl $KeyPath
        $rulesCount = $newAcl.Access.Count
        
        if (-not $Silent) {
            Write-Host ""
            Write-Host "Permissions fixed successfully!" -ForegroundColor Green
            Write-Host "Current user: $currentUser" -ForegroundColor White
            Write-Host "Access rules: $rulesCount" -ForegroundColor White
            Write-Host "========================================" -ForegroundColor Cyan
            Write-Host ""
        }
        
        return $true
        
    } catch {
        if (-not $Silent) {
            Write-Host ""
            Write-Host "========================================" -ForegroundColor Red
            Write-Host "Error: Failed to fix permissions" -ForegroundColor Red
            Write-Host "========================================" -ForegroundColor Red
            Write-Host "Error details: $($_.Exception.Message)" -ForegroundColor White
            Write-Host ""
            
            # Provide troubleshooting guidance
            Write-Host "Possible solutions:" -ForegroundColor Yellow
            Write-Host "1. Run this script as Administrator" -ForegroundColor White
            Write-Host "2. Check if the file is in use by another application" -ForegroundColor White
            Write-Host "3. Manually adjust permissions in Windows Explorer:" -ForegroundColor White
            Write-Host "   - Right-click the key file" -ForegroundColor Gray
            Write-Host "   - Select Properties > Security" -ForegroundColor Gray
            Write-Host "   - Remove all users except yourself" -ForegroundColor Gray
            Write-Host "   - Give yourself Full Control" -ForegroundColor Gray
            Write-Host "========================================" -ForegroundColor Red
            Write-Host ""
        }
        
        return $false
    }
}
