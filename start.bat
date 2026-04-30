@echo off
setlocal

set "ROOT=%~dp0"
set "PYTHON=%ROOT%.venv\Scripts\python.exe"
set "PYTHONW=%ROOT%.venv\Scripts\pythonw.exe"

if not exist "%PYTHON%" (
    echo Virtual environment not found: .venv\Scripts\python.exe
    echo Run these commands first:
    echo   python -m venv .venv
    echo   .\.venv\Scripts\python.exe -m pip install -e .[dev]
    echo Optional for local fast mode:
    echo   .\.venv\Scripts\python.exe -m pip install -e .[local-asr]
    pause
    exit /b 1
)

pushd "%ROOT%"
"%PYTHON%" -c "import app.main" >nul 2>&1
if errorlevel 1 (
    echo Project dependencies are not ready.
    echo Run these commands first:
    echo   .\.venv\Scripts\python.exe -m pip install -e .[dev]
    echo Optional for local fast mode:
    echo   .\.venv\Scripts\python.exe -m pip install -e .[local-asr]
    pause
    popd
    exit /b 1
)

if exist "%PYTHONW%" (
    start "" /D "%ROOT%" "%PYTHONW%" -m app.main
) else (
    start "" /D "%ROOT%" "%PYTHON%" -m app.main
)

popd
exit /b 0
