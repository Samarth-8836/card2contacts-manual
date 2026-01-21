# Fix SSH key file permissions
$keyPath = "D:\SECURE-DO-NOT-DELETE\Card2Contacts-app-server-access\card2contacts - app server.pem"

Write-Host "Fixing permissions on SSH key file..."
Write-Host "Path: $keyPath"

# Remove inheritance and clear all permissions
$acl = Get-Acl $keyPath
$acl.SetAccessRuleProtection($true, $false)

# Add full control for current user only
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$accessRule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    $currentUser,
    'FullControl',
    'Allow'
)
$acl.SetAccessRule($accessRule)

# Apply permissions
Set-Acl $keyPath $acl

Write-Host "Permissions fixed successfully!"
Write-Host ""
Write-Host "Current permissions:"
$acl | Format-List
