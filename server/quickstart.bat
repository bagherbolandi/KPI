@echo off
REM ============================================================
REM  راه‌اندازی سریع KPI-MS روی ویندوز (با دوبار کلیک باز شود)
REM  پیش‌نیاز: فقط نصب Python 3.11+ (در نصب تیک "Add Python to PATH" را بزنید)
REM ============================================================
cd /d %~dp0backend

IF NOT EXIST venv (
    echo [۱] ساخت محیط مجازی (venv)...
    python -m venv venv
)
call venv\Scripts\activate

echo [۲] نصب کتابخانه‌ها (اولین بار ممکن است چند دقیقه طول بکشد)...
pip install --upgrade pip >nul 2>&1
pip install -r requirements.txt

echo [۳] بارگذاری ۱۶۴ شاخص نمونه (در صورت خالی بودن)...
python -c "from app.seed import run_seed; run_seed()"

echo [۴] اجرای سامانه...
echo.
echo ============================================================
echo   سامانه آماده شد. مرورگر را باز کنید و بروید به:
echo        http://localhost:8000
echo   نام کاربری: admin   |   رمز عبور: Passw0rd!
echo ============================================================
echo.
uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
