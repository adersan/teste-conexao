@echo off
chcp 65001 > nul 2>&1
color 0B
title AS TECH - Iniciando...

cls
echo.
echo  ================================================================
echo   AS TECH SOLUTIONS - Network Diagnostic v11 - Flet Edition
echo  ================================================================
echo.

python --version > nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo  ERRO: Python nao encontrado no PATH.
    echo  Instale em: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo  [1/2] Verificando dependencias...
python -m pip install flet speedtest-cli -q 2>nul
if %errorlevel% neq 0 (
    python -m pip install flet speedtest-cli -q --break-system-packages 2>nul
)

echo  [2/2] Abrindo dashboard...

set "DIR=%~dp0"
cd /d "%DIR%"

start "" python "%DIR%teste_rede_dashboard_v11_flet.py"

exit
