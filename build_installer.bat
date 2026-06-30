@echo off
setlocal
chcp 65001 > nul 2>&1
cd /d "%~dp0"

echo.
echo ================================================================
echo  AS TECH - Gerando executavel e instalador
echo ================================================================
echo.

python -m pip install --upgrade flet-cli==0.85.3 pyinstaller speedtest-cli
if errorlevel 1 goto :erro

if not exist ".dist" mkdir ".dist"
if not exist "release" mkdir "release"

echo [1/2] Gerando aplicativo independente...
flet pack "teste_rede_dashboard_v11_flet.py" ^
  --name "AS-Tech-Diagnostico" ^
  --distpath ".dist" ^
  --product-name "AS Tech - Diagnostico de Conexao" ^
  --file-description "Dashboard de diagnostico de rede" ^
  --product-version "1.0.1" ^
  --file-version "1.0.1.0" ^
  --company-name "AS Tech Solutions" ^
  --copyright "Copyright (c) 2026 AS Tech Solutions" ^
  --hidden-import speedtest ^
  --yes
if errorlevel 1 goto :erro

echo [2/2] Gerando instalador...
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" "installer.iss"
if errorlevel 1 goto :erro

echo.
echo Instalador criado em:
echo %CD%\release\AS-Tech-Diagnostico-Setup-1.0.1.exe
echo.
exit /b 0

:erro
echo.
echo ERRO: nao foi possivel gerar o instalador.
exit /b 1
