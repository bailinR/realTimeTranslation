# Build PyInstaller onedir under dist\RealTimeTranslation (Windows x64).
# Prerequisites: Python 3.12+ on PATH, optional venv at .venv
# Usage: .\scripts\build_windows.ps1
# Optional: -SkipInno  to only run PyInstaller

param(
    [switch]$SkipInno
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$Python = if (Test-Path "$Root\.venv\Scripts\python.exe") {
    "$Root\.venv\Scripts\python.exe"
} else {
    "python"
}

& $Python -m pip install -U pip
& $Python -m pip install -e "$Root"
& $Python -m pip install "pyinstaller>=6.0"

& $Python -m PyInstaller --noconfirm "$Root\packaging\realtime_translation.spec"

if (-not $SkipInno) {
    $isccExe = $null
    if (Get-Command iscc -ErrorAction SilentlyContinue) {
        $isccExe = "iscc"
    } else {
        $candidates = @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
        )
        foreach ($p in $candidates) {
            if (Test-Path $p) { $isccExe = $p; break }
        }
    }
    if ($isccExe) {
        & $isccExe "$Root\packaging\RealTimeTranslation.iss"
    } else {
        Write-Warning "Inno Setup 6 not found (iscc / ISCC.exe). Skipping installer. Install from https://jrsoftware.org/isdl.php or run with -SkipInno."
    }
}

Write-Host "Done. Output: $Root\dist\RealTimeTranslation"
if (Test-Path "$Root\dist\RealTimeTranslation-Setup.exe") {
    Write-Host "Installer: $Root\dist\RealTimeTranslation-Setup.exe"
}
