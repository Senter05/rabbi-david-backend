@echo off
setlocal
cd /d "%~dp0"
set "RD_PYTHON=C:\Users\srgm2\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%RD_PYTHON%" (
  echo No se encuentra Python. Consulta LEEME.md.
  pause
  exit /b 1
)
"%RD_PYTHON%" -c "import urllib.request,json; d=json.load(urllib.request.urlopen('http://127.0.0.1:8100/api/config',timeout=2)); assert d.get('mode')=='preview' and d.get('payments') is False" >nul 2>&1
if not errorlevel 1 goto abrir
if not exist "..\..\work\rabbi-david-private\config.json" (
  echo No se encuentra la configuracion privada. Consulta LEEME.md.
  pause
  exit /b 1
)
powershell -NoProfile -Command "Start-Process -FilePath $env:RD_PYTHON -ArgumentList 'server.py --config ../../work/rabbi-david-private/config.json --data ../../work/rabbi-david-private/antigravity-data --port 8100 --enable-voice' -WorkingDirectory (Get-Location).Path -WindowStyle Hidden"
for /l %%n in (1,1,20) do (
  "%RD_PYTHON%" -c "import time,urllib.request,json; time.sleep(.5); d=json.load(urllib.request.urlopen('http://127.0.0.1:8100/api/config',timeout=1)); assert d.get('mode')=='preview'" >nul 2>&1
  if not errorlevel 1 goto abrir
)
echo No se pudo iniciar la pagina. Comprueba si el puerto 8100 esta ocupado.
pause
exit /b 1
:abrir
start "" "http://127.0.0.1:8100/"
exit /b 0
