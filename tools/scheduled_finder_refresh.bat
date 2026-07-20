@echo off
REM ====================================================================
REM  Scheduled global Finder refresh   (see tools/FINDER.md "Keeping it fresh").
REM
REM  Rebuilds registries\index.html + every per-project index.html from the live
REM  registry. Meant to run daily via Task Scheduler on the data-office workstation.
REM
REM  Uses the UNC share root by DEFAULT (not a mapped drive) so it works from a
REM  scheduled context where J: may not be mapped. Pass a different root as the
REM  first argument to override, e.g.:
REM      scheduled_finder_refresh.bat J:\gjesus3-data
REM
REM  Register (daily 05:00, under your own account):
REM      schtasks /Create /TN "gjesus3 Finder refresh" /SC DAILY /ST 05:00 /F ^
REM          /TR "\"%~f0\""
REM
REM  Requires `python` on PATH; edit the PYTHON var below to a full path if not.
REM ====================================================================
setlocal
set "PYTHON=python"
set "TOOLS=%~dp0"
set "NAS=%~1"
if "%NAS%"=="" set "NAS=\\GJESUS3\gjesus3\gjesus3-data"
set "LOGDIR=%LOCALAPPDATA%\gjesus3"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "LOG=%LOGDIR%\finder_refresh.log"

echo(>> "%LOG%"
echo ==== %DATE% %TIME%  refresh START (nas=%NAS%) ==== >> "%LOG%"
"%PYTHON%" "%TOOLS%generate_index.py" --nas-root "%NAS%" --per-project >> "%LOG%" 2>&1
echo ==== %DATE% %TIME%  refresh DONE (exit %ERRORLEVEL%) ==== >> "%LOG%"
endlocal
