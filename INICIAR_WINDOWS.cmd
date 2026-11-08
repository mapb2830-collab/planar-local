@echo off
setlocal
cd /d "%~dp0"
echo.
echo PLANAR - Instalacion y arranque local
echo Carpeta: %CD%
echo.
where node >nul 2>&1
if errorlevel 1 (
  echo Falta Node.js. Instala Node.js 24 LTS desde https://nodejs.org
  echo Despues cierra esta ventana y abre este archivo otra vez.
  pause
  exit /b 1
)
node -e "const [a,b]=process.versions.node.split('.').map(Number); if(a<22 || (a===22 && b<12)) process.exit(1)"
if errorlevel 1 (
  echo Se necesita Node.js 22.12 o superior. Se recomienda Node.js 24.
  pause
  exit /b 1
)
py -3.12 --version >nul 2>&1
if errorlevel 1 (
  echo Falta Python 3.12 con el lanzador py.
  echo Instala Python 3.12 desde https://www.python.org/downloads/windows/
  echo Incluye el Python Launcher durante la instalacion.
  pause
  exit /b 1
)
if not exist "backend\.venv\Scripts\python.exe" (
  py -3.12 -m venv "backend\.venv"
  if errorlevel 1 goto failed
)
echo [1/3] Instalando dependencias de Python...
"backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 goto failed
echo [2/3] Instalando dependencias de la interfaz...
pushd frontend
call npm ci
if errorlevel 1 (
  popd
  goto failed
)
popd
echo [3/3] Abriendo los servidores...
start "PLANAR - Backend" cmd /k call "%~dp0scripts\backend.cmd"
start "PLANAR - Frontend" cmd /k call "%~dp0scripts\frontend.cmd"
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; Write-Host 'Esperando ambos servidores...'; for ($attempt=0; $attempt -lt 60; $attempt++) { try { $api=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/api/health' -TimeoutSec 2; $web=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5173' -TimeoutSec 2; $health=$api.Content | ConvertFrom-Json; if ($health.status -eq 'ok' -and $web.StatusCode -eq 200 -and $web.Content -match 'PLANAR') { Start-Process 'http://127.0.0.1:5173'; exit 0 } } catch {}; Start-Sleep -Seconds 1 }; Write-Host 'Revisa los errores en las ventanas Backend y Frontend.'; exit 1"
if errorlevel 1 goto failed
echo.
echo PLANAR iniciado. Conserva abiertas las ventanas Backend y Frontend.
echo Para cerrar la aplicacion, pulsa Ctrl+C en cada una.
pause
exit /b 0
:failed
echo.
echo No se pudo completar el arranque. Copia el error que aparece arriba.
pause
exit /b 1
