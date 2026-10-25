# Push this repository to GitHub.
#
#   1. create an empty public repo at https://github.com/new  (name: nightshift, no README)
#   2. run:  .\push.cmd          <- recommended on Windows (handles the execution policy)
#      or:   powershell -NoProfile -ExecutionPolicy Bypass -File .\push.ps1
#
# The first run opens a browser once (Git Credential Manager); after that the
# credential is cached by Windows.
#
# -RemoteUrl exists so this script can be tested against a local bare repository
# without touching GitHub.
param(
    [string]$User = "RRRYJ7",
    [string]$Repo = "nightshift",
    [string]$RemoteUrl = "",
    [switch]$Force
)

# Native commands write diagnostics to stderr, and with ErrorActionPreference=Stop
# PowerShell turns that into a terminating error. Check $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

if (-not (Test-Path ".git")) { throw "not a git repository" }

$url = if ($RemoteUrl) { $RemoteUrl } else { "https://github.com/$User/$Repo.git" }

function Fail($message) {
    Write-Host $message -ForegroundColor Red
    exit 1
}

# `git config --get` exits 1 silently when the key is missing; `git remote
# get-url` writes "No such remote" to stderr, which used to abort the script.
$existing = git config --get remote.origin.url
if ($LASTEXITCODE -eq 0 -and $existing) {
    if (-not $Force) {
        Write-Host "remote 'origin' already points to $existing (use -Force to re-point)" -ForegroundColor Yellow
    } else {
        git remote set-url origin $url
        if ($LASTEXITCODE -ne 0) { Fail "could not re-point origin" }
        Write-Host "remote origin -> $url"
    }
} else {
    git remote add origin $url
    if ($LASTEXITCODE -ne 0) { Fail "could not add origin" }
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

$branch = git rev-parse --abbrev-ref HEAD
Write-Host ""
Write-Host "pushing $branch -> $url" -ForegroundColor Cyan
git push -u origin $branch
if ($LASTEXITCODE -ne 0) { Fail "push failed - if this is an auth problem, run: git push -u origin $branch" }

Write-Host ""
Write-Host "done." -ForegroundColor Green
Write-Host "next:"
Write-Host "  1. open  https://github.com/$User/$Repo/settings  -> About -> paste Description + Topics"
Write-Host "  2. open  https://github.com/$User/$Repo/releases/new?tag=v0.1.0  -> paste the release body"
Write-Host "  3. post  launch-kit/douyin.md  (video: docs/nightshift-vertical.mp4)"
