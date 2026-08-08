@echo off
REM Copy the application into a cloned Hugging Face Space repository.
REM
REM Usage (from anywhere):
REM   deploy\huggingface\sync-space.bat "C:\path\to\cloned\space"
REM
REM Copies backend and frontend sources, then drops in the Space-specific
REM Dockerfile and README (the one carrying the Space YAML header).

setlocal
set "HERE=%~dp0"
set "PROJECT=%HERE%..\.."
set "SPACE=%~1"

if "%SPACE%"=="" (
  echo.
  echo   Usage: sync-space.bat "path\to\cloned\space"
  echo.
  exit /b 1
)

if not exist "%SPACE%\.git" (
  echo.
  echo   "%SPACE%" does not look like a cloned git repository.
  echo   Clone the Space first, then run this script with its path.
  echo.
  exit /b 1
)

echo Copying backend...
robocopy "%PROJECT%\backend" "%SPACE%\backend" /MIR /NFL /NDL /NJH /NJS /NC /NS ^
  /XD data __pycache__ .pytest_cache .ruff_cache static .venv venv

echo Copying frontend...
robocopy "%PROJECT%\frontend" "%SPACE%\frontend" /MIR /NFL /NDL /NJH /NJS /NC /NS ^
  /XD node_modules dist

echo Copying Space files...
copy /Y "%HERE%Dockerfile" "%SPACE%\Dockerfile" >nul
copy /Y "%HERE%README.md" "%SPACE%\README.md" >nul
copy /Y "%PROJECT%\.dockerignore" "%SPACE%\.dockerignore" >nul

echo.
echo Done. Next:
echo   cd /d "%SPACE%"
echo   git add -A
echo   git commit -m "Deploy Synapse demo"
echo   git push
echo.
endlocal
