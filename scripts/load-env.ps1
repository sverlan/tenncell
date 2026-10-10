<#
.SYNOPSIS
Load the KEY=value lines of .env into the current PowerShell session.

.DESCRIPTION
For running pytest directly with the opt-in tool tests (`pdm test` and the
other pdm scripts load .env themselves). Dot-source it so the variables stay
in your session:

    . .\scripts\load-env.ps1            # keeps variables already set
    . .\scripts\load-env.ps1 -Force     # overrides them

Lines are KEY=value; blank lines and lines starting with # are skipped, and
one pair of surrounding quotes is removed from a value.
#>
param(
    [string]$Path = (Join-Path $PSScriptRoot '..\.env'),
    [switch]$Force
)

if (-not (Test-Path -LiteralPath $Path)) {
    Write-Warning "No env file at $Path (copy .env.example to .env)"
    return
}
foreach ($line in Get-Content -LiteralPath $Path) {
    $text = $line.Trim()
    if (-not $text -or $text.StartsWith('#')) { continue }
    $split = $text.IndexOf('=')
    if ($split -lt 1) {
        Write-Warning "Skipping line without KEY=value: $text"
        continue
    }
    $key = $text.Substring(0, $split).Trim()
    $value = $text.Substring($split + 1).Trim()
    if ($value.Length -ge 2 -and $value[0] -eq $value[-1] -and '"', "'" -contains $value[0]) {
        $value = $value.Substring(1, $value.Length - 2)
    }
    if (-not $Force -and (Test-Path -LiteralPath "Env:$key")) {
        Write-Host "$key kept (already set)"
        continue
    }
    Set-Item -LiteralPath "Env:$key" -Value $value
    Write-Host "$key set"
}
