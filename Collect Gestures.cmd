@echo off
title GESTR - Collect Gestures
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\launch-collector.ps1"
if errorlevel 1 (
  echo.
  echo The collector could not start. Read the message above.
  pause
  exit /b 1
)
