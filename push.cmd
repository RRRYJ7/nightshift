@echo off
rem Wrapper so the publish step works even when the PowerShell execution policy
rem blocks unsigned scripts (the default on many Windows machines).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0push.ps1" %*
