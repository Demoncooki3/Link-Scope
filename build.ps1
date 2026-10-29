$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
python -m PyInstaller --noconfirm --clean --onefile --windowed --name LinkScope --distpath dist/hostnames --collect-all scapy app.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'START-HERE.txt') -Destination (Join-Path $PSScriptRoot 'dist\hostnames\START-HERE.txt') -Force
Compress-Archive -LiteralPath (Join-Path $PSScriptRoot 'dist\hostnames\LinkScope.exe'), (Join-Path $PSScriptRoot 'dist\hostnames\START-HERE.txt') -DestinationPath (Join-Path $PSScriptRoot 'dist\LinkScope-Hostnames-Windows-x64.zip') -Force
Write-Host 'Ready: dist\hostnames\LinkScope.exe and dist\LinkScope-Hostnames-Windows-x64.zip'
