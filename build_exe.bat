@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .build-env
if errorlevel 1 goto failed
.build-env\Scripts\python.exe -m pip install -r requirements-build.txt
if errorlevel 1 goto failed
.build-env\Scripts\python.exe -m unittest discover -s tests
if errorlevel 1 goto failed
.build-env\Scripts\python.exe tools\build_release.py
if errorlevel 1 goto failed
.build-env\Scripts\python.exe tools\package_release.py
if errorlevel 1 goto failed
echo Build completed. See the release folder.
pause
exit /b 0
:failed
echo Build failed. See the messages above.
pause
exit /b 1
