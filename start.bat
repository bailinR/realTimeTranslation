@echo off
setlocal
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
pushd "%~dp0"

set "PY=%CD%\.venv\Scripts\python.exe"

if exist "%PY%" goto have_py
echo ERROR: venv not found. Expected:
echo   %PY%
echo.
echo Create:  python -m venv .venv
echo Install: .\.venv\Scripts\python.exe -m pip install -U pip
echo Project: .\.venv\Scripts\python.exe -m pip install -e .
pause
popd
exit /b 1

:have_py
echo Checking dependencies...
"%PY%" -c "import app.main"
if errorlevel 1 goto pip_install
goto run_app

:pip_install
echo Running: pip install -e .
"%PY%" -m pip install -e "%CD%"
if errorlevel 1 goto pip_fail
"%PY%" -c "import app.main"
if errorlevel 1 goto imp_fail
goto run_app

:pip_fail
echo ERROR: pip install failed.
pause
popd
exit /b 1

:imp_fail
echo ERROR: import app.main failed.
"%PY%" -c "import app.main"
pause
popd
exit /b 1

:run_app
echo Starting (python.exe keeps this window open and shows errors)...
"%PY%" -m app.main
echo.
echo App process ended.
pause
popd
exit /b 0
