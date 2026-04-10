@echo off
REM ============================================================
REM Solpark Performance Reports - Monthly Generation
REM ============================================================
REM
REM Kör denna .bat-fil 1:a varje månad för att:
REM   1. Synka senaste Bazefield-data (inkrementell)
REM   2. Generera rapporter för senaste fullständiga månad
REM   3. Logga output till Resultat\logs\monthly_reports.log
REM
REM Användning:
REM   Dubbelklicka filen ELLER kör från terminal:
REM   ./monthly_reports.bat
REM
REM Rapporter sparas i: Resultat\rapporter\performance_*.html
REM ============================================================

setlocal enabledelayedexpansion

REM Se till att vi kör från projektets rot
cd /d "%~dp0"

REM Skapa logs-mappen om den inte finns
if not exist "Resultat\logs" mkdir "Resultat\logs"

REM Timestamp för loggrad
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value ^| find "="') do set DATETIME=%%I
set TIMESTAMP=!DATETIME:~0,4!-!DATETIME:~4,2!-!DATETIME:~6,2! !DATETIME:~8,2!:!DATETIME:~10,2!:!DATETIME:~12,2!

set LOGFILE=Resultat\logs\monthly_reports.log

echo. >> "%LOGFILE%"
echo ============================================================ >> "%LOGFILE%"
echo [%TIMESTAMP%] Monthly reports run started >> "%LOGFILE%"
echo ============================================================ >> "%LOGFILE%"

REM Säkerställ UTF-8 output
set PYTHONIOENCODING=utf-8

echo.
echo ============================================================
echo Solpark Performance Reports - Monthly Generation
echo ============================================================
echo.
echo Steg 1/2: Synkar Bazefield-data (inkrementell)...
echo.

python bazefield_download.py >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo FEL vid Bazefield-synk — se %LOGFILE%
    echo [%TIMESTAMP%] ERROR in bazefield_download >> "%LOGFILE%"
    exit /b 1
)

echo Synk klar.
echo.
echo Steg 2/2: Genererar rapporter för alla 8 parker...
echo (Default: senaste fullständiga månad)
echo.

python generate_performance_report.py --all >> "%LOGFILE%" 2>&1
if errorlevel 1 (
    echo FEL vid rapport-generering — se %LOGFILE%
    echo [%TIMESTAMP%] ERROR in generate_performance_report >> "%LOGFILE%"
    exit /b 1
)

echo.
echo ============================================================
echo KLART! Rapporter finns i Resultat\rapporter\
echo ============================================================
echo.
echo Senaste rapporter:
dir /b /od "Resultat\rapporter\performance_*.html" 2>nul | findstr /r "performance_.*\.html" > temp_list.txt
for /f "delims=" %%f in (temp_list.txt) do set LAST_FILES=%%f
type temp_list.txt | more +1 2>nul
del temp_list.txt 2>nul

echo [%TIMESTAMP%] Monthly reports run completed successfully >> "%LOGFILE%"

echo.
echo Logg sparad till: %LOGFILE%
echo.

endlocal
