@echo off
rem Wrapper so installing the skill works even when the PowerShell execution
rem policy blocks unsigned scripts.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
