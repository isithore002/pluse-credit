param(
    [switch]$Recreate = $true,
    [switch]$InstallSpacyModel
)

$ErrorActionPreference = "Stop"

function Get-Python311Command {
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return @("py", "-3.11")
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return @("python")
    }

    throw "Python is not installed. Install Python 3.11 and rerun this script."
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$venvPath = Join-Path $repoRoot ".venv-clean"
$pythonExe = Join-Path $venvPath "Scripts\python.exe"

if ($Recreate -and (Test-Path $venvPath)) {
    Write-Host "[bootstrap] Removing existing .venv-clean"
    Remove-Item -Recurse -Force $venvPath
}

if (!(Test-Path $venvPath)) {
    $py = Get-Python311Command
    Write-Host "[bootstrap] Creating .venv-clean with Python 3.11"
    if ($py.Length -gt 1) {
        & $py[0] $py[1] -m venv $venvPath
    } else {
        & $py[0] -m venv $venvPath
    }
}

Write-Host "[bootstrap] Installing backend dependencies"
& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r (Join-Path $repoRoot "backend\requirements.txt")

if ($InstallSpacyModel) {
    Write-Host "[bootstrap] Installing spaCy model en_core_web_sm"
    & $pythonExe -m spacy download en_core_web_sm
}

Write-Host ""
Write-Host "Bootstrap complete."
Write-Host "Start backend with:"
Write-Host "  Push-Location backend; ../.venv-clean/Scripts/python.exe -m uvicorn main:app --reload; Pop-Location"
