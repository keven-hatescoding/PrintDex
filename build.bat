@echo off
rem Gera o executável do PrintDex (veja build.ps1)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1"
pause
