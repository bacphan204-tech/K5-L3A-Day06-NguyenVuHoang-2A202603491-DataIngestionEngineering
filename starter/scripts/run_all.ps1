param([switch]$Install)

$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
Set-Location -LiteralPath $projectRoot
$labPython = Join-Path $projectRoot 'starter\.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $labPython)) {
    & python -m venv (Join-Path $projectRoot 'starter\.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create virtual environment.' }
}

function Invoke-LabPython {
    param([string[]]$PythonArguments)
    & $labPython @PythonArguments
    if ($LASTEXITCODE -ne 0) {
        throw ('Python step failed: ' + ($PythonArguments -join ' '))
    }
}

if ($Install) {
    Invoke-LabPython -PythonArguments @('-m', 'pip', 'install', '-r', 'starter/requirements.txt')
}
if (-not (Test-Path -LiteralPath '.local/models/multilingual-e5-small/download_info.json')) {
    Invoke-LabPython -PythonArguments @('starter/scripts/download_model.py')
}

Invoke-LabPython -PythonArguments @('starter/scripts/prepare_corpus.py')
Invoke-LabPython -PythonArguments @('-m', 'starter.src.run', '--stage', 'validate')
Invoke-LabPython -PythonArguments @('-m', 'starter.src.run', '--stage', 'all')
Invoke-LabPython -PythonArguments @('starter/scripts/build_report.py')
Invoke-LabPython -PythonArguments @('starter/scripts/check_results.py')
Write-Host 'Completed. See README.md and report/individual/2A202603491_NguyenVuHoang.md.'
