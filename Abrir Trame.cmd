@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" iniciar.py %*
    goto resultado
)
where py >nul 2>&1
if not errorlevel 1 (
    py -3 iniciar.py %*
) else (
    python iniciar.py %*
)
:resultado
if errorlevel 1 (
    echo.
    echo Confira se o Python 3.12 ou superior esta instalado.
    echo O erro acima informa o que impediu a inicializacao.
    pause
)
