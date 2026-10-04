@echo off
cd /d "%~dp0"
py -3 AION2_Event_Overlay_Ping.pyw
if errorlevel 1 pause
