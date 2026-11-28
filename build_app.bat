@echo off
cd /d "%~dp0"

echo Cleaning up old build folder, zip, and __pycache__...
if exist "LeoAltholicViewer" rmdir /s /q "LeoAltholicViewer"
if exist "LeoAltholicViewer.zip" del /q "LeoAltholicViewer.zip"
if exist "__pycache__" rmdir /s /q "__pycache__"

echo Building LeoAltholicViewer.exe...
python -m PyInstaller --noconfirm --onefile --windowed --paths "." --distpath "LeoAltholicViewer" --name "LeoAltholicViewer" --icon="app_icon.ico" --version-file="version_info.txt" --add-data "app_icon.ico;." altholic_viewer_standalone.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! Check the messages above.
    pause
    exit /b 1
)

echo.
echo Copying READ_ME.txt and LeoAltholicViewer.txt to LeoAltholicViewer folder...
copy /Y "READ_ME.txt" "LeoAltholicViewer\READ_ME.txt"
copy /Y "LeoAltholicViewer.txt" "LeoAltholicViewer\LeoAltholicViewer.txt"

echo.
echo Creating Minion-compatible LeoAltholicViewer.zip...
python -c "import shutil; shutil.make_archive('LeoAltholicViewer', 'zip', root_dir='.', base_dir='LeoAltholicViewer')"

echo.
echo Cleaning up temporary PyInstaller files and __pycache__...
if exist "build" rmdir /s /q "build"
if exist "LeoAltholicViewer.spec" del /q "LeoAltholicViewer.spec"
if exist "__pycache__" rmdir /s /q "__pycache__"

echo.
echo ============================================
echo Build complete!
echo  - Folder: LeoAltholicViewer\
echo  - Zip:    LeoAltholicViewer.zip
echo ============================================
pause

