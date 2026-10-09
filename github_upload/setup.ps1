param([string]$Python = '3.11')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'Install uv first, or follow the standard Python/pip instructions in README.md.'
}
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    uv --cache-dir .uv-cache venv --python $Python .venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
}
uv --cache-dir .uv-cache pip install --python .venv\Scripts\python.exe -r requirements.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
& .\.venv\Scripts\python.exe check_setup.py
if ($LASTEXITCODE -ne 0) { throw 'Environment verification failed' }
