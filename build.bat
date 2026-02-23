@echo off
echo ============================================
echo   FiveM Cache Cleaner - Lokaler Build
echo ============================================
echo.

echo [1/3] Installiere Abhaengigkeiten...
python -m pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [ERR] pip install fehlgeschlagen.
    pause
    exit /b 1
)

echo [2/3] Baue EXE mit PyInstaller...
python -m PyInstaller ^
    --onefile ^
    --console ^
    --name FiveM_Cache_Cleaner ^
    --distpath dist ^
    --workpath build_tmp ^
    --specpath build_tmp ^
    src/main.py

if %errorlevel% neq 0 (
    echo [ERR] PyInstaller fehlgeschlagen.
    pause
    exit /b 1
)

echo [3/3] Bereinige temporaere Build-Dateien...
rmdir /s /q build_tmp 2>nul

echo.
echo ============================================
echo   Build erfolgreich!
echo   Ausgabe: dist\FiveM_Cache_Cleaner.exe
echo ============================================
echo.
pause
