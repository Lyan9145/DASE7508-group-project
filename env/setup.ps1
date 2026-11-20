param([string]$Python = '3.11')
$ErrorActionPreference = 'Stop'
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw 'Install uv first, or follow the standard Python/pip instructions in README.md.'
}
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    uv --cache-dir .uv-cache venv --python $Python .venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
}
uv --cache-dir .uv-cache pip install --python .venv\Scripts\python.exe -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
$runId = [Guid]::NewGuid().ToString('N')
$checkOutput = Join-Path 'outputs' "setup_windows_$runId"
& .\.venv\Scripts\python.exe check_setup.py --out $checkOutput
if ($LASTEXITCODE -ne 0) { throw 'Environment verification failed' }
