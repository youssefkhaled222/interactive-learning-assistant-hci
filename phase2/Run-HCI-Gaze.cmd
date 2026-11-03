@echo off
cd /d "%~dp0"
if not exist "models\face_landmarker.task" (
    echo Face model missing. First run Download-Gaze-Model.cmd
    exit /b 2
)
call "%~dp0Run-HCI.cmd"
start "HCI Gaze - second webcam" powershell.exe -NoExit -ExecutionPolicy Bypass -File "%~dp0launchers\gaze.ps1"
echo The FIFTH gaze terminal tracks your face using camera 1. YOLO keeps camera 0.
echo Calibrate in the Eye Tracking mode at http://127.0.0.1:5173
