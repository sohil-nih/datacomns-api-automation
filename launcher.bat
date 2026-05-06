@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
where python >nul 2>&1 && set PYTHON=python || set PYTHON=py
%PYTHON% launcher.py
if %ERRORLEVEL% neq 0 pause
