@echo off
rem Planetary Gearbox Generator - standalone launcher (no Fusion 360 required).
rem This file is ASCII-only on purpose: cmd.exe misreads non-ASCII text in .bat files,
rem while the folder path itself (e.g. "Okan Yesilyurt" with Turkish letters) is safe via %~dp0.
setlocal
chcp 65001 >nul
title Planet Reduktor Tasarimcisi (Standalone)
cd /d "%~dp0"

echo ===================================================================
echo        PLANET REDUKTOR TASARIMCISI - STANDALONE (OpenCascade)
echo ===================================================================
echo.

rem --- 1) Find a Python that has OpenCascade (OCP) and pywebview ---------
set "PY="
for %%V in (3.14 3.13 3.12 3.11) do call :try_py "py -%%V"
if not defined PY call :try_py "python"
if defined PY goto :run

echo [UYARI] OpenCascade (OCP) ve pywebview kurulu bir Python bulunamadi.
set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY (
    echo [HATA] Python bulunamadi. https://www.python.org adresinden Python 3.11+ kurun
    echo        ve kurulumda "Add Python to PATH" secenegini isaretleyin.
    pause
    exit /b 1
)
echo.
echo Gerekli paketler kurulacak (requirements-standalone.txt, internetten indirilir):
type requirements-standalone.txt | findstr /v /b "#"
echo.
set "ANS="
set /p ANS=Simdi kurulsun mu? (E/H):
if /i not "%ANS%"=="E" (
    echo Kurulum iptal edildi.
    pause
    exit /b 1
)
%PY% -m pip install -r requirements-standalone.txt
if errorlevel 1 (
    echo [HATA] Paket kurulumu basarisiz oldu.
    pause
    exit /b 1
)
%PY% -c "import OCP, webview" >nul 2>&1 || (
    echo [HATA] Kurulumdan sonra da OCP / pywebview yuklenemedi. Python 3.11 - 3.14 kullanin.
    pause
    exit /b 1
)

rem --- 2) Start the application --------------------------------------------
:run
echo [OK] Python: %PY%
echo [OK] Arayuz aciliyor... (bu pencereyi kapatmayin; uygulama kapaninca kapanir)
echo.
%PY% -m standalone
if errorlevel 1 (
    echo.
    echo [HATA] Uygulama beklenmedik sekilde kapandi.
    echo        Ayrintilar: %APPDATA%\PlanetaryGearbox\logs\app.log
    echo        Tarayici modu icin: %PY% -m standalone serve
    pause
    exit /b 1
)
exit /b 0

rem --- Helper: set PY if the given Python can import OCP and webview -------
:try_py
if defined PY goto :eof
%~1 -c "import OCP, webview" >nul 2>&1 && set "PY=%~1"
goto :eof
