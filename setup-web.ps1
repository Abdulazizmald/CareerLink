# Creates the web/ folder tree and moves the downloaded React files into it.
#
# Run from your project folder (the one containing main.py):
#     powershell -ExecutionPolicy Bypass -File setup-web.ps1
#
# By default it looks in your Downloads folder. Point it somewhere else with:
#     powershell -ExecutionPolicy Bypass -File setup-web.ps1 -From "C:\some\other\folder"

param([string]$From = "$env:USERPROFILE\Downloads")

$ErrorActionPreference = "Stop"

if (-not (Test-Path "main.py")) {
    Write-Host "main.py is not in this folder. cd to your project folder first." -ForegroundColor Red
    exit 1
}

# Which file belongs in which folder. Downloads arrive flat, so the tree has to
# be rebuilt from the filenames.
$layout = @{
    "index.html"      = "web"
    "package.json"    = "web"
    "vite.config.js"  = "web"
    "main.jsx"        = "web\src"
    "App.jsx"         = "web\src"
    "index.css"       = "web\src"
    "api.js"          = "web\src\lib"
    "UI.jsx"          = "web\src\components"
    "Charts.jsx"      = "web\src\components"
    "Home.jsx"        = "web\src\pages"
    "StudyGuide.jsx"  = "web\src\pages"
    "RolePlan.jsx"    = "web\src\pages"
    "Jobs.jsx"        = "web\src\pages"
    "Skills.jsx"      = "web\src\pages"
    "SkillDetail.jsx" = "web\src\pages"
    "Market.jsx"      = "web\src\pages"
    "Candidates.jsx"  = "web\src\pages"
}

foreach ($dir in ($layout.Values | Sort-Object -Unique)) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}
Write-Host "Folders created." -ForegroundColor Green

$missing = @()
foreach ($name in $layout.Keys) {
    $dest = Join-Path $layout[$name] $name
    # already in place from a previous run
    if (Test-Path $dest) { continue }

    # look in the project root first (files often land there), then in $From
    $src = $null
    if (Test-Path $name) { $src = $name }
    elseif (Test-Path (Join-Path $From $name)) { $src = Join-Path $From $name }

    if ($src) {
        Move-Item -Force $src $dest
        Write-Host "  moved $name -> $($layout[$name])"
    } else {
        $missing += $name
    }
}

if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "Still missing $($missing.Count) file(s):" -ForegroundColor Yellow
    $missing | ForEach-Object { Write-Host "  $_ -> $($layout[$_])" }
    Write-Host "Download those, then run this script again." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "All 17 files are in place." -ForegroundColor Green
Write-Host "Next:"
Write-Host "    cd web"
Write-Host "    npm install"
Write-Host "    npm run build"
Write-Host "    cd .."
Write-Host "    python main.py"
