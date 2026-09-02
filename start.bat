@echo off
:: ============================================================
::  Steel Frame Generator — Lanceur Web (Streamlit)
::  Double-cliquez sur ce fichier pour démarrer l'application.
::  Le navigateur s'ouvre automatiquement sur http://localhost:8501
:: ============================================================
setlocal

:: Répertoire du script (même dossier que ce .bat)
set "APP_DIR=%~dp0"
set "SCRIPT=%APP_DIR%steel_frame_web.py"

:: ------------------------------------------------------------
:: 1. Vérification de Python
:: ------------------------------------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERREUR] Python est introuvable dans le PATH.
    echo  Installez Python depuis https://www.python.org/downloads/
    echo  et cochez "Add Python to PATH" lors de l'installation.
    echo.
    pause
    exit /b 1
)

:: ------------------------------------------------------------
:: 2. Installation / mise a jour de Streamlit et requests
:: ------------------------------------------------------------
echo.
echo  Vérification des dépendances...
python -m pip install --quiet --upgrade streamlit requests
if errorlevel 1 (
    echo.
    echo  [ERREUR] Impossible d'installer les dépendances.
    echo  Vérifiez votre connexion Internet et les droits administrateur.
    echo.
    pause
    exit /b 1
)
echo  Dépendances OK.

:: ------------------------------------------------------------
:: 3. Vérification du script Python
:: ------------------------------------------------------------
if not exist "%SCRIPT%" (
    echo.
    echo  [ERREUR] Fichier introuvable : %SCRIPT%
    echo  Assurez-vous que lancer.bat et steel_frame_web.py
    echo  sont dans le même dossier.
    echo.
    pause
    exit /b 1
)

:: ------------------------------------------------------------
:: 4. Lancement de Streamlit
::    --server.headless false  -> ouvre le navigateur auto
::    --server.port 8501       -> port local (modifiable si besoin)
::    --server.address localhost -> accessible uniquement en local
::                                 Remplacer par 0.0.0.0 pour
::                                 un acces reseau local (LAN)
:: ------------------------------------------------------------
echo.
echo  Demarrage de Steel Frame Generator...
echo  Ouverture du navigateur sur http://localhost:8501
echo.
echo  Pour arreter l'application : fermez cette fenetre
echo  ou appuyez sur Ctrl+C dans cette console.
echo.

python -m streamlit run "%SCRIPT%" ^
    --server.port 8501 ^
    --server.address localhost ^
    --server.headless false ^
    --browser.gatherUsageStats false ^
    --theme.base dark ^
    --theme.primaryColor "#1d4ed8" ^
    --theme.backgroundColor "#0f1623" ^
    --theme.secondaryBackgroundColor "#1e2634" ^
    --theme.textColor "#e2e8f0"

:: ------------------------------------------------------------
:: 5. L'application s'est fermée
:: ------------------------------------------------------------
echo.
echo  L'application Steel Frame Generator s'est arrêtée.
pause
endlocal
