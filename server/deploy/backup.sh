#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  پشتیبان‌گیری خودکار از پایگاه‌داده KPI-MS (PostgreSQL در Docker)
#  اجرا:  bash deploy/backup.sh
#  زمان‌بندی روزانه (crontab):  0 2 * * *  /path/to/kpi-system/deploy/backup.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/kpi-ms}"
DB_SERVICE="db"                 # نام سرویس دیتابیس در docker-compose
DB_USER="kpi"
DB_NAME="kpi"
RETENTION_DAYS="${RETENTION_DAYS:-30}"   # نگهداری ۳۰ روز اخیر
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_DIR/kpi_${STAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] گرفتن پشتیبان از پایگاه‌داده…"
docker compose exec -T "$DB_SERVICE" pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$OUT"
echo "[$(date)] پشتیبان ذخیره شد: $OUT ($(du -h "$OUT" | cut -f1))"

# حذف پشتیبان‌های قدیمی‌تر از بازه نگهداری
find "$BACKUP_DIR" -name 'kpi_*.sql.gz' -mtime +"$RETENTION_DAYS" -delete
echo "[$(date)] پشتیبان‌های قدیمی‌تر از ${RETENTION_DAYS} روز پاک شدند."

# ── بازیابی (Restore) در صورت نیاز: ──
#   gunzip -c kpi_YYYYMMDD_HHMMSS.sql.gz | docker compose exec -T db psql -U kpi -d kpi
