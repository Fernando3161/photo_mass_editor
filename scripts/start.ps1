param(
    [int]$Port = 8000,
    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))

if ($Port -lt 1 -or $Port -gt 65535) { throw 'Port must be between 1 and 65535.' }
if (-not (Test-Path -LiteralPath 'requirements.lock' -PathType Leaf)) { throw 'Missing requirements.lock.' }
if (-not (Test-Path -LiteralPath 'frontend/package-lock.json' -PathType Leaf)) { throw 'Missing frontend/package-lock.json.' }

New-Item -ItemType Directory -Force -Path 'data/input','data/catalog','data/exports','data/backups','data/evidence','data/models' | Out-Null
$venvPython = Join-Path (Get-Location) '.venv/Scripts/python.exe'
if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
    & $venvPython scripts/setup_env.py
} else {
    $bootstrapPython = (Get-Command python -ErrorAction Stop).Source
    & $bootstrapPython scripts/setup_env.py
}
if ($LASTEXITCODE -ne 0) { throw 'Environment setup failed.' }
if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf)) { throw 'Repository .venv Python is missing.' }
& $venvPython -c "import pathlib,sys; assert pathlib.Path(sys.prefix).resolve() == pathlib.Path('.venv').resolve()"
if ($LASTEXITCODE -ne 0) { throw 'The selected Python is outside this repository .venv.' }

$photos = @(Get-ChildItem -LiteralPath 'data/input' -File -ErrorAction Stop | Where-Object { $_.Extension -match '^\.(jpe?g|png|tiff?|webp)$' })
if ($photos.Count -gt 0) {
    & $venvPython -m backend.catalog import-folder data/input
    if ($LASTEXITCODE -ne 0) { throw 'Photo import failed.' }
} else {
    & $venvPython -m backend.catalog init
    if ($LASTEXITCODE -ne 0) { throw 'Catalog initialization failed.' }
    Write-Host 'No supported photos in data/input. Copy originals there and rerun this script to import them.'
}

$npm = (Get-Command npm.cmd -ErrorAction Stop).Source
& $npm --prefix frontend run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
if (-not (Test-Path -LiteralPath 'frontend/dist/index.html' -PathType Leaf)) { throw 'Frontend build did not create index.html.' }

$addresses = @(Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.IPv4Address } | ForEach-Object { $_.IPv4Address.IPAddress } | Where-Object { $_ -and $_ -notlike '169.254.*' } | Select-Object -Unique)
if ($addresses.Count -eq 0) { throw 'No active LAN IPv4 address with a default gateway was found.' }
$passwordBytes = New-Object byte[] 24
$generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
try { $generator.GetBytes($passwordBytes) } finally { $generator.Dispose() }
$env:PHOTO_EDITOR_ACCESS_PASSWORD = [Convert]::ToBase64String($passwordBytes).TrimEnd('=') -replace '\+', '-' -replace '/', '_'
$env:PHOTO_EDITOR_ALLOWED_HOSTS = 'localhost,127.0.0.1,' + ($addresses -join ',')

Write-Host ''
Write-Host "Local: http://127.0.0.1:$Port/"
foreach ($address in $addresses) { Write-Host "LAN:   http://${address}:$Port/" }
Write-Host 'Username: owner'
Write-Host "Password for this run: $env:PHOTO_EDITOR_ACCESS_PASSWORD"
Write-Host 'Use only on a trusted private network. HTTP traffic is not encrypted. Do not forward this port to the internet.'
Write-Host 'Press Ctrl+C to stop the server.'
if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$Port/" }
try {
    & $venvPython -m backend.review --data-dir data/catalog --host 0.0.0.0 --port $Port
    if ($LASTEXITCODE -ne 0) { throw 'Review server exited with an error.' }
} finally {
    Remove-Item Env:PHOTO_EDITOR_ACCESS_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:PHOTO_EDITOR_ALLOWED_HOSTS -ErrorAction SilentlyContinue
}
