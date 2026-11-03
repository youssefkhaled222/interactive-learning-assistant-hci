@echo off
cd /d "%~dp0"
call "%~dp0Run-HCI-Tests.cmd"
if errorlevel 1 exit /b 1
exit /b 0
