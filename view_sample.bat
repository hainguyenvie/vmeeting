@echo off
echo.
echo ==============================================
echo 📌  MEETING SUMMARY VIEWER TOOL
echo ==============================================
echo.
echo 👉 Dang tim va mo file 'sample.json'...
echo.

python view_sample.py

echo.
echo ==============================================
if errorlevel 1 echo ❌ CO LOI! Vui long kiem tra ban da CAI DAT PYTHON chua.
if not errorlevel 1 echo ✅ HOAN THANH! Ban co the tat cua so nay.
echo ==============================================
echo.
pause
