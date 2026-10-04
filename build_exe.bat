@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .build-env
if errorlevel 1 goto failed
.build-env\Scripts\python.exe -m pip install -r requirements-build.txt
if errorlevel 1 goto failed
set "PYINSTALLER_CONFIG_DIR=%CD%\.pyinstaller-cache"
.build-env\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --noupx --name AION2_Event_Overlay_Ping --paths AION2-Event-Overlay --icon AION2-Event-Overlay\AION2_Event_Overlay.ico --add-data "AION2-Event-Overlay\AION2_Event_Overlay.ico;." --add-data "AION2-Event-Overlay\aion2_overlay.json;." AION2_Event_Overlay_Ping.pyw
if errorlevel 1 goto failed
copy /y dist\AION2_Event_Overlay_Ping.exe AION2_Event_Overlay_Ping.exe
echo Build completed.
pause
exit /b 0
:failed
echo Build failed. See the messages above.
pause
exit /b 1
