param(
    [switch]$Background,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pythonw = Join-Path $projectRoot ".venv\Scripts\pythonw.exe"

if (-not (Test-Path $python)) {
    Write-Host "Virtual environment not found: .venv\Scripts\python.exe"
    Write-Host "Run these commands first:"
    Write-Host "  python -m venv .venv"
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -e .[dev]"
    Write-Host "Optional for local fast mode:"
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -e .[local-asr]"
    exit 1
}

Push-Location $projectRoot
try {
    $probeOutput = & $python -c "import app.main" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Project dependencies are not ready."
        Write-Host "Run these commands first:"
        Write-Host "  .\.venv\Scripts\python.exe -m pip install -e .[dev]"
        Write-Host "Optional for local fast mode:"
        Write-Host "  .\.venv\Scripts\python.exe -m pip install -e .[local-asr]"
        if ($probeOutput) {
            Write-Host ""
            Write-Host "Import check output:"
            $probeOutput | ForEach-Object { Write-Host $_ }
        }
        exit 1
    }

    if ($CheckOnly) {
        Write-Host "Environment check passed."
        exit 0
    }

    if ($Background) {
        $launcher = if (Test-Path $pythonw) { $pythonw } else { $python }
        Start-Process -FilePath $launcher -ArgumentList @("-m", "app.main") -WorkingDirectory $projectRoot | Out-Null
        Write-Host "Application started."
        exit 0
    }

    & $python -m app.main
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
