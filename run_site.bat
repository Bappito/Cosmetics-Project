@echo off
cd /d "%~dp0"

echo [1/5] Backing up data files...
set "BK=backup_%RANDOM%%RANDOM%"
mkdir "%BK%" || goto fail
for %%F in (cosmetics_3sim_erp.db cosmetics_3sim_erp.db-wal cosmetics_3sim_erp.db-shm django.sqlite3) do (
  if exist "%%F" (
    copy "%%F" "%BK%\" >nul || goto fail
  )
)

echo [2/5] Getting the latest code...
git switch main || goto fail
git pull --ff-only || goto fail

echo [3/5] Installing packages...
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto fail

echo [4/5] Updating the database...
".venv\Scripts\python.exe" manage.py migrate || goto fail
".venv\Scripts\python.exe" manage.py shell -c "from django.contrib.auth.models import User; raise SystemExit(0 if User.objects.exists() else 3)"
if errorlevel 4 goto fail
if errorlevel 3 (
  echo Create your user for the site. The password stays hidden while you type.
  ".venv\Scripts\python.exe" manage.py createsuperuser || goto fail
) else (
  if errorlevel 1 goto fail
)

echo [5/5] Starting the site. Keep this window open.
start "" /min cmd /c "timeout /t 5 >nul & start http://127.0.0.1:8000"
".venv\Scripts\python.exe" manage.py runserver
pause
exit /b

:fail
echo.
echo Something failed. Take a screenshot of this window and send it to Claude.
pause
exit /b 1
