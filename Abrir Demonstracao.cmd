@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" demonstracao.py %*
    goto resultado
)
where py >nul 2>&1
if not errorlevel 1 (
    py -3 demonstracao.py %*
) else (
    python demonstracao.py %*
)
:resultado
if errorlevel 1 pause
