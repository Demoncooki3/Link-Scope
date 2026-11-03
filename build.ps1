$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$version = (Get-Content -LiteralPath (Join-Path $PSScriptRoot 'VERSION') -Raw).Trim()
if ($version -notmatch '^\d+\.\d+(\.\d+)?$') { throw 'Invalid VERSION' }
$appName = "linkscope-v$version"
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
python -m PyInstaller --noconfirm --clean --onefile --windowed --name $appName --distpath dist/release --collect-all scapy app.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'START-HERE.txt') -Destination (Join-Path $PSScriptRoot 'dist\release\START-HERE.txt') -Force
Compress-Archive -LiteralPath (Join-Path $PSScriptRoot "dist\release\$appName.exe"), (Join-Path $PSScriptRoot 'dist\release\START-HERE.txt') -DestinationPath (Join-Path $PSScriptRoot "dist\$appName-Windows-x64.zip") -Force
Write-Host "Ready: dist\release\$appName.exe and dist\$appName-Windows-x64.zip"
