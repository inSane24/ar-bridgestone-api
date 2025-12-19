<#
.SYNOPSIS
    Automate port forwarding and firewall configuration for exposing a WSL service.

.DESCRIPTION
    - Detects the Windows host IPv4 (for reference) and the current WSL IPv4.
    - Adds or replaces a portproxy rule that forwards the chosen port from Windows to WSL.
    - Ensures a corresponding inbound firewall rule exists.

    Run this script from an elevated PowerShell session each time the WSL IP changes
    (typically after reboot). The firewall rule is created once and reused.

.EXAMPLE
    .\setup-portproxy.ps1 -Port 8000 -RuleName "WSL FastAPI 8000"
#>

[CmdletBinding()]
param(
    [int]$Port = 8000,
    [string]$RuleName = "WSL FastAPI 8000"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Assert-IsAdministrator {
    $currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw "Please run this script from an elevated (Administrator) PowerShell session."
    }
}

function Get-WindowsIpv4 {
    $defaultRoute = Get-NetRoute -DestinationPrefix "0.0.0.0/0" |
        Sort-Object -Property RouteMetric |
        Select-Object -First 1

    if (-not $defaultRoute) {
        throw "Unable to determine an active Windows network route."
    }

    $ipConfig = Get-NetIPAddress -InterfaceIndex $defaultRoute.InterfaceIndex -AddressFamily IPv4 |
        Where-Object { $_.IPAddress -notmatch '^169\.254\.' } |
        Select-Object -First 1

    if (-not $ipConfig) {
        throw "Unable to obtain the Windows IPv4 address."
    }

    return $ipConfig.IPAddress
}

function Get-WslIpv4 {
    $output = wsl hostname -I 2>$null
    if (-not $output) {
        throw "Unable to obtain an IPv4 address from WSL. Please ensure the 'wsl' command is available."
    }

    $ip = $output.Trim().Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries) |
        Where-Object { $_ -match '^\d+\.\d+\.\d+\.\d+$' } |
        Select-Object -First 1

    if (-not $ip) {
        throw "Unable to determine the WSL IPv4 address. Output of 'hostname -I': $output"
    }

    return $ip
}

function Ensure-PortProxy {
    param(
        [int]$ListenPort,
        [string]$ConnectAddress,
        [int]$ConnectPort
    )

    Write-Host ("Configuring portproxy... (0.0.0.0:{0} -> {1}:{2})" -f $ListenPort, $ConnectAddress, $ConnectPort)
    netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=$ListenPort 2>$null | Out-Null
    netsh interface portproxy add v4tov4 `
        listenaddress=0.0.0.0 listenport=$ListenPort `
        connectaddress=$ConnectAddress connectport=$ConnectPort | Out-Null
}

function Ensure-FirewallRule {
    param(
        [string]$DisplayName,
        [int]$LocalPort
    )

    $rule = Get-NetFirewallRule -DisplayName $DisplayName -ErrorAction SilentlyContinue
    if ($rule) {
        Write-Host "Using existing firewall rule '$DisplayName'."
        return
    }

    Write-Host "Creating firewall rule '$DisplayName'."
    New-NetFirewallRule `
        -DisplayName $DisplayName `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $LocalPort `
        -EdgeTraversalPolicy Block `
        -Profile Any | Out-Null
}

try {
    Assert-IsAdministrator

    $windowsIp = Get-WindowsIpv4
    $wslIp = Get-WslIpv4

    Write-Host "Windows IPv4 : $windowsIp"
    Write-Host "WSL IPv4     : $wslIp"

    Ensure-PortProxy -ListenPort $Port -ConnectAddress $wslIp -ConnectPort $Port
    Ensure-FirewallRule -DisplayName $RuleName -LocalPort $Port

    Write-Host ""
    Write-Host "Current portproxy configuration:"
    netsh interface portproxy show all

    Write-Host ""
    Write-Host ("Setup complete. Start FastAPI in WSL and access it at http://{0}:{1}" -f $windowsIp, $Port)
}
catch {
    Write-Error $_
    exit 1
}
