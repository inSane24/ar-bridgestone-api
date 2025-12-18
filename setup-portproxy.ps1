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
        throw "このスクリプトは管理者 PowerShell から実行してください。"
    }
}

function Get-WindowsIpv4 {
    $defaultRoute = Get-NetRoute -DestinationPrefix "0.0.0.0/0" |
        Sort-Object -Property RouteMetric |
        Select-Object -First 1

    if (-not $defaultRoute) {
        throw "Windows の有効なネットワーク経路を特定できませんでした。"
    }

    $ipConfig = Get-NetIPAddress -InterfaceIndex $defaultRoute.InterfaceIndex -AddressFamily IPv4 |
        Where-Object { $_.IPAddress -notmatch '^169\.254\.' } |
        Select-Object -First 1

    if (-not $ipConfig) {
        throw "Windows 側の IPv4 アドレスを取得できませんでした。"
    }

    return $ipConfig.IPAddress
}

function Get-WslIpv4 {
    $output = wsl hostname -I 2>$null
    if (-not $output) {
        throw "WSL から IPv4 を取得できませんでした。`wsl` コマンドが実行できるか確認してください。"
    }

    $ip = $output.Trim().Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries) |
        Where-Object { $_ -match '^\d+\.\d+\.\d+\.\d+$' } |
        Select-Object -First 1

    if (-not $ip) {
        throw "WSL の IPv4 アドレスを判別できませんでした。`hostname -I` の結果: $output"
    }

    return $ip
}

function Ensure-PortProxy {
    param(
        [int]$ListenPort,
        [string]$ConnectAddress,
        [int]$ConnectPort
    )

    Write-Host "PortProxy を設定中... (0.0.0.0:$ListenPort -> $ConnectAddress:$ConnectPort)"
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
        Write-Host "既存のファイアウォールルール '$DisplayName' を使用します。"
        return
    }

    Write-Host "ファイアウォールルール '$DisplayName' を新規作成します。"
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

    Write-Host "Windows 側 IP : $windowsIp"
    Write-Host "WSL 側 IP     : $wslIp"

    Ensure-PortProxy -ListenPort $Port -ConnectAddress $wslIp -ConnectPort $Port
    Ensure-FirewallRule -DisplayName $RuleName -LocalPort $Port

    Write-Host ""
    Write-Host "現在の portproxy:"
    netsh interface portproxy show all

    Write-Host ""
    Write-Host "セットアップ完了。FastAPI を WSL で起動したら http://$windowsIp:$Port でアクセスできます。"
}
catch {
    Write-Error $_
    exit 1
}
