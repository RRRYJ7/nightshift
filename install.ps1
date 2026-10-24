# Install the NIGHTSHIFT skill into an agent's skills directory.
#   .\install.ps1                    -> $HOME\.claude\skills\nightshift
#   .\install.ps1 "$HOME\.dsh\skills"
param(
    [string]$Target = (Join-Path $HOME ".claude\skills")
)
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$dest = Join-Path $Target "nightshift"

New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Recurse -Force (Join-Path $here "nightshift") $dest
foreach ($f in @("SKILL.md", "README.md", "LICENSE", "pyproject.toml")) {
    $src = Join-Path $here $f
    if (Test-Path $src) { Copy-Item -Force $src $dest }
}

Write-Host "skill  -> $dest"
Write-Host ""
Write-Host "put the CLI on PATH (pick one):"
Write-Host "  pipx install `"$here`""
Write-Host "  python -m pip install --user -e `"$here`""
Write-Host "  set-alias nsh { python -m nightshift }"
Write-Host ""
Write-Host "then, in any project:   nsh init --goal `"...`" --deadline 06:30"
