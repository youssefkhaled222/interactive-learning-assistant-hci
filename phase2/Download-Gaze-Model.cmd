@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" backend\download_face_model.py
if errorlevel 1 (
    echo Face model download failed. Check your connection, then retry.
    exit /b 1
)
echo Official face model ready.
