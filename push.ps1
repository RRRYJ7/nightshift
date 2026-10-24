# Push this repository to GitHub.
#
#   1. create an empty public repo at https://github.com/new  (name: nightshift, no README)
#   2. .\push.ps1
#
# The first run will open a browser once (Git Credential Manager); after that the
# credential is cached by Windows.
param(
    [string]$User = "chchliu",
    [string]$Repo = "nightshift",
    [switch]$Force
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

if (-not (Test-Path ".git")) { throw "not a git repository" }

$url = "https://github.com/$User/$Repo.git"
$existing = git remote get-url origin 2>$null
if ($existing -and -not $Force) {
    Write-Host "remote 'origin' already points to $existing (use -Force to re-point)" -ForegroundColor Yellow
} else {
    if ($existing) { git remote set-url origin $url } else { git remote add origin $url }
    Write-Host "remote origin -> $url"
}

$dirty = git status --porcelain
if ($dirty) {
    Write-Host "working tree has uncommitted changes:" -ForegroundColor Yellow
    $dirty | Select-Object -First 10 | ForEach-Object { Write-Host "  $_" }
    git add -A
    git commit -m "wip: uncommitted changes before push" | Out-Null
    Write-Host "committed them for you." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "pushing main -> $url" -ForegroundColor Cyan
git push -u origin main

Write-Host ""
Write-Host "done." -ForegroundColor Green
Write-Host "next:"
Write-Host "  1. open  https://github.com/$User/$Repo/settings  -> About -> paste Description + Topics"
Write-Host "  2. open  https://github.com/$User/$Repo/releases/new?tag=v0.1.0  -> paste the release body"
Write-Host "  3. post  launch-kit/douyin.md  (video: docs/nightshift-vertical.mp4)"
