# Run ONCE as Administrator (right-click > Run with PowerShell, or:
#   powershell -ExecutionPolicy Bypass -File allow-firewall.ps1
#
# Without this, Windows Firewall blocks your phone from reaching the relay.
# Scoped to the Private (home) network profile only -- not public Wi-Fi.

$rule = "Torrent Relay 8800"
if (Get-NetFirewallRule -DisplayName $rule -ErrorAction SilentlyContinue) {
    Write-Host "Firewall rule '$rule' already exists. Nothing to do."
} else {
    New-NetFirewallRule -DisplayName $rule -Direction Inbound -Protocol TCP `
        -LocalPort 8800 -Action Allow -Profile Private | Out-Null
    Write-Host "Added firewall rule '$rule' (TCP 8800, Private network)."
}

Write-Host ""
Write-Host "Your PC's address on this network:"
Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
    Select-Object IPAddress, InterfaceAlias | Format-Table -AutoSize
Write-Host "On your phone, open http://<that-IP>:8800"
