#!/bin/bash
# ============================================================
#  راه‌اندازی سریع KPI-MS روی macOS / Linux
#  پیش‌نیاز: Python 3.11+ (معمولاً نصب است؛ در غیر این صورت از سایت python.org)
#  اجرا:  bash quickstart.sh
# ============================================================
cd "$(dirname "$0")"
cd backend

python3 -m venv venv 2>/dev/null || true
if [ -d venv ]; then source venv/bin/activate; fi

echo "[۲] نصب کتابخانه‌ها..."
pip install --upgrade pip >/dev/null 2>&1
pip install -r requirements.txt

echo "[۳] بارگذاری ۱۶۴ شاخص نمونه (در صورت خالی بودن)..."
python -c "from app.seed import run_seed; run_seed()"

echo "[۴] اجرای سامانه..."
echo "============================================================"
echo "  سامانه آماده شد. مرورگر را باز کنید و بروید به:"
echo "       http://localhost:8000"
echo "  نام کاربری: admin   |   رمز عبور: Passw0rd!"
echo "============================================================"
uvicorn app.main:app --host 0.0.0.0 --port 8000
