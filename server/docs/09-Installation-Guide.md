# راهنمای نصب و استقرار برای تیم IT
## سامانه مدیریت و پایش شاخص‌های کلیدی عملکرد (KPI-MS)

> این سند برای **کارشناس زیرساخت / سیستم‌های عامل** نوشته شده است. هدف، استقرار سامانه روی **یک سرور مرکزی در شبکهٔ داخلی سازمان (On-Premise)** است؛ کاربران فقط با مرورگر به آن وصل می‌شوند و هیچ نصبی روی سیستم کاربران لازم نیست.

---

## ۰. خلاصهٔ اجرایی (TL;DR)

اگر Docker روی سرور نصب است، کل نصب در ۴ گام است:

```bash
git clone <repo>  &&  cd kpi-system            # ۱) دریافت کد
cp .env.example .env                            # ۲) ساخت فایل تنظیمات
nano .env      # DB_PASSWORD و KPI_SECRET_KEY را مقداردهی کنید
docker compose up -d --build                    # ۳) بالا آوردن سرویس‌ها
# ۴) مرورگر: http://<IP-سرور>:8000  → ورود با admin / Passw0rd!
```
سامانه در اولین اجرا به‌طور خودکار جداول را می‌سازد و ۱۶۴ شاخص نمونه را بارگذاری می‌کند.

سه بخش بعدی جزئیات کامل، سخت‌سازی امنیتی و نگهداری را پوشش می‌دهند.

---

## ۱. معماری در یک نگاه

```
[کاربران شبکه داخلی] ──HTTPS──▶ [Nginx + TLS] ──▶ [API: Uvicorn×4]
   مرورگر / بدون نصب                (443)            (کانتینر api:8000)
                                                          │
                                                          ▼
                                              [PostgreSQL 16 (کانتینر db)]
                                                          │
                                                  [Volume: pgdata]  ──▶  Backup روزانه (pg_dump)
```
- **api**: برنامهٔ FastAPI + رابط کاربری React (هر دو در یک کانتینر).
- **db**: پایگاه‌دادهٔ مرکزی PostgreSQL؛ داده روی Volume ماندگار `pgdata`.
- **nginx** (اختیاری اما توصیه‌شده): پایانهٔ TLS و reverse-proxy.

---

## ۲. پیش‌نیازها

### ۲.۱ سخت‌افزار پیشنهادی سرور

| اندازهٔ سازمان | vCPU | RAM | دیسک |
|----------------|:----:|:---:|:----:|
| کوچک (تا ۵۰ کاربر، ۱۶۴ شاخص فعلی) | ۲ | ۴ GB | ۲۰ GB SSD |
| متوسط (تا ۲۰۰ کاربر، چند شرکت) | ۴ | ۸ GB | ۵۰ GB SSD |
| بزرگ | ۸ | ۱۶ GB | ۱۰۰ GB SSD |

> ردپای منابع سامانه کم است؛ گلوگاه معمولاً حجم تاریخچهٔ داده و تعداد کاربران هم‌زمان است.

### ۲.۲ سیستم‌عامل و نرم‌افزار
- **سیستم‌عامل:** Ubuntu Server 22.04/24.04 LTS یا RHEL/Rocky 8/9 (هر توزیع لینوکس ۶۴بیتی).
- **مسیر A (توصیه‌شده):** `Docker Engine ≥ 24` و `Docker Compose v2`.
- **مسیر B (بدون Docker):** `Python 3.12`، `PostgreSQL ≥ 14`، `Nginx`.

نصب Docker روی Ubuntu:
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER      # سپس یک‌بار logout/login
docker --version && docker compose version
```

### ۲.۳ شبکه و پورت‌ها

| پورت | سرویس | دسترسی |
|------|-------|--------|
| ۴۴۳ | Nginx (HTTPS) | باز برای کاربران شبکهٔ داخلی |
| ۸۰ | Nginx (ریدایرکت به HTTPS) | باز |
| ۸۰۰۰ | API | فقط داخلی؛ در حالت Nginx نباید به بیرون باز باشد |
| ۵۴۳۲ | PostgreSQL | **فقط داخل شبکهٔ Docker**؛ به بیرون باز نشود |

- یک رکورد DNS داخلی برای دامنه بسازید، مثلاً `kpi.company.local → <IP سرور>`.
- به اینترنت نیازی نیست؛ فقط برای مرحلهٔ build اولیهٔ ایمیج‌ها (دریافت پکیج‌ها) لازم است. در محیط ایزوله، ایمیج‌ها را روی یک سرور با اینترنت build و به رجیستری داخلی push کنید.

---

## ۳. مسیر A — نصب با Docker (توصیه‌شده)

### گام ۱: دریافت کد و رفتن به پوشه
```bash
git clone <repo-url> kpi-system   # یا انتقال فایل پروژه به سرور
cd kpi-system
```

### گام ۲: ساخت فایل تنظیمات و مقادیر امن
```bash
cp .env.example .env
# تولید مقادیر تصادفی امن:
echo "DB_PASSWORD=$(openssl rand -hex 16)"     >> .env.tmp
echo "KPI_SECRET_KEY=$(openssl rand -hex 32)"  >> .env.tmp
# سپس مقادیر تولیدشده را داخل .env جایگزین کنید (nano .env)
```
فایل `.env` باید شامل دو کلید باشد:
```
DB_PASSWORD=<یک رمز قوی>
KPI_SECRET_KEY=<رشته تصادفی ۶۴ کاراکتری>
```

### گام ۳: بالا آوردن سرویس‌ها
```bash
docker compose up -d --build
docker compose ps         # هر دو سرویس باید Up/healthy باشند
docker compose logs -f api   # مشاهدهٔ لاگ راه‌اندازی (Ctrl+C برای خروج)
```
در اولین اجرا، سامانه جداول را می‌سازد و **۱۶۴ شاخص + دادهٔ نمونه** را بارگذاری می‌کند (پیام `Application startup complete`).

### گام ۴: بررسی سلامت
```bash
curl http://localhost:8000/api/health      # → {"status":"ok"}
```
حالا از یک کلاینت در شبکهٔ داخلی: `http://<IP سرور>:8000` را باز کنید و با `admin / Passw0rd!` وارد شوید.

> **مهم:** بلافاصله رمز کاربر `admin` را عوض کنید و حساب‌های نمونه (`ceo`, `quality`, `owner_*`) را غیرفعال/حذف کنید (بخش ۱۱).

---

## ۴. مسیر B — نصب دستی بدون Docker

اگر سیاست سازمان اجازهٔ Docker نمی‌دهد:

### گام ۱: نصب PostgreSQL و ساخت دیتابیس
```bash
sudo apt install -y postgresql
sudo -u postgres psql <<'SQL'
CREATE USER kpi WITH PASSWORD 'ChangeMe_Strong';
CREATE DATABASE kpi OWNER kpi;
SQL
```

### گام ۲: ساخت کاربر سیستمی و محیط Python
```bash
sudo useradd -r -m -d /opt/kpi-system kpi
sudo cp -r kpi-system/* /opt/kpi-system/
cd /opt/kpi-system
python3.12 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
```

### گام ۳: تنظیم متغیرهای محیطی
```bash
cat > backend/.env <<'ENV'
DATABASE_URL=postgresql+psycopg://kpi:ChangeMe_Strong@localhost:5432/kpi
KPI_SECRET_KEY=<openssl rand -hex 32>
ENV
sudo chown -R kpi:kpi /opt/kpi-system
```

### گام ۴: بارگذاری اولیهٔ داده (اختیاری—در غیر این‌صورت خودکار انجام می‌شود)
```bash
cd /opt/kpi-system/backend
sudo -u kpi ../.venv/bin/python -c "from app.seed import run_seed; print(run_seed())"
```

### گام ۵: اجرا به‌صورت سرویس دائمی (systemd)
```bash
sudo cp deploy/kpi-ms.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kpi-ms
sudo systemctl status kpi-ms
sudo journalctl -u kpi-ms -f      # مشاهدهٔ لاگ
```

---

## ۵. راه‌اندازی داده و مدیریت اولیه

- **بارگذاری خودکار:** اگر جدول شاخص‌ها خالی باشد، سامانه در هر بار startup به‌طور خودکار داده نمونه را بارگذاری می‌کند.
- **بارگذاری مجدد کامل (ریست داده):** فقط در محیط تست — این کار همهٔ داده‌ها را پاک می‌کند:
  ```bash
  docker compose exec api python -c "from app.seed import run_seed; run_seed()"
  ```
- **مهاجرت از فایل اکسل واقعی سازمان:** به‌جای دادهٔ نمونه، از اسکریپت Import (نقشهٔ راه/فاز ۲) یا API `POST /api/kpis` و `POST /api/entries` استفاده کنید. جزئیات نگاشت در `docs/07-Data-Analysis.md`.

---

## ۶. فعال‌سازی HTTPS با Nginx (توصیهٔ اکید برای تولید)

### گام ۱: آماده‌سازی گواهی TLS
گواهی داخلی سازمان (CA داخلی) یا self-signed را در `deploy/certs/` قرار دهید:
```bash
mkdir -p deploy/certs
# نمونه self-signed برای تست:
openssl req -x509 -nodes -days 825 -newkey rsa:2048 \
  -keyout deploy/certs/server.key -out deploy/certs/server.crt \
  -subj "/CN=kpi.company.local"
```

### گام ۲: تنظیم دامنه در کانفیگ
در `deploy/nginx.conf` مقدار `server_name` را به دامنهٔ داخلی خود تغییر دهید (مثلاً `kpi.company.local`).

### گام ۳: فعال‌سازی سرویس nginx
در `docker-compose.yml` بلوک `nginx` را از حالت کامنت خارج کنید و برای امنیت، **انتشار پورت ۸۰۰۰ سرویس api را حذف کنید** تا فقط از طریق Nginx در دسترس باشد:
```yaml
  api:
    # ports:            ← این خط و زیرش را حذف/کامنت کنید
    #   - "8000:8000"
  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./deploy/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./deploy/certs:/etc/nginx/certs:ro
    depends_on: [api]
    restart: unless-stopped
```
سپس:
```bash
docker compose up -d --build
```
اکنون سامانه روی `https://kpi.company.local` در دسترس است و HTTP به HTTPS هدایت می‌شود.

---

## ۷. فایروال

فقط پورت‌های لازم را باز بگذارید (نمونهٔ UFW):
```bash
sudo ufw allow 443/tcp
sudo ufw allow 80/tcp
sudo ufw deny  8000/tcp     # API نباید مستقیم از بیرون در دسترس باشد
sudo ufw deny  5432/tcp     # PostgreSQL هرگز به بیرون باز نشود
sudo ufw enable
```

---

## ۸. پشتیبان‌گیری و بازیابی

اسکریپت آماده `deploy/backup.sh` از دیتابیس، پشتیبان فشرده می‌گیرد و نسخه‌های قدیمی را پاک می‌کند.

**زمان‌بندی خودکار روزانه (ساعت ۲ بامداد):**
```bash
sudo chmod +x deploy/backup.sh
( crontab -l 2>/dev/null; echo "0 2 * * * cd $(pwd) && bash deploy/backup.sh >> /var/log/kpi-backup.log 2>&1" ) | crontab -
```

**بازیابی از پشتیبان:**
```bash
gunzip -c /var/backups/kpi-ms/kpi_YYYYMMDD_HHMMSS.sql.gz \
  | docker compose exec -T db psql -U kpi -d kpi
```

> Volume `pgdata` را نیز در سیاست پشتیبان‌گیری زیرساخت (Snapshot ماشین مجازی) لحاظ کنید.

---

## ۹. به‌روزرسانی نسخه (Upgrade)

```bash
cd kpi-system
bash deploy/backup.sh            # ۱) ابتدا پشتیبان بگیرید
git pull                          # ۲) دریافت نسخهٔ جدید
docker compose up -d --build      # ۳) build و جایگزینی بدون قطعی طولانی
docker compose logs -f api        # ۴) بررسی سلامت
```
> در نسخه‌های تولیدی، تغییرات اسکیمای دیتابیس با **Alembic migration** اعمال می‌شود (به‌جای بازسازی جدول). داده‌های موجود حفظ می‌شوند.

---

## ۱۰. پایش، سلامت و لاگ

| مورد | دستور / مسیر |
|------|--------------|
| سلامت سرویس | `curl http://localhost:8000/api/health` → `{"status":"ok"}` |
| وضعیت کانتینرها | `docker compose ps` |
| لاگ برنامه | `docker compose logs -f api` |
| لاگ دیتابیس | `docker compose logs -f db` |
| مصرف منابع | `docker stats` |
| لاگ ممیزی (درون سامانه) | صفحهٔ «لاگ تغییرات» یا `GET /api/audit` |

توصیه: نقطهٔ `/api/health` را به سامانهٔ مانیتورینگ سازمان (Zabbix/Prometheus/Uptime-Kuma) متصل کنید.

---

## ۱۱. چک‌لیست سخت‌سازی امنیتی (قبل از تحویل به کاربران)

- [ ] مقدار `KPI_SECRET_KEY` تصادفی و منحصربه‌فرد (`openssl rand -hex 32`).
- [ ] رمز `DB_PASSWORD` قوی و متفاوت.
- [ ] **رمز کاربر `admin` تغییر داده شد.**
- [ ] حساب‌های نمونه (`ceo`, `quality`, `owner_*`) حذف یا غیرفعال شدند.
- [ ] HTTPS (Nginx + TLS) فعال و پورت ۸۰۰۰ از بیرون بسته است.
- [ ] پورت ۵۴۳۲ (PostgreSQL) فقط داخل شبکهٔ Docker.
- [ ] فایروال فقط ۴۴۳/۸۰ را باز گذاشته است.
- [ ] پشتیبان‌گیری خودکار روزانه فعال و یک‌بار **تست بازیابی** انجام شده است.
- [ ] کاربران واقعی با نقش‌های صحیح ساخته شدند (بخش «کاربران و نقش‌ها»).
- [ ] (اختیاری) اتصال به LDAP/AD در نقشهٔ راه فاز ۳.

---

## ۱۲. تست پذیرش پس از نصب (Smoke Test)

```bash
BASE=https://kpi.company.local        # یا http://<IP>:8000
# ۱) سلامت
curl -k $BASE/api/health
# ۲) ورود و دریافت توکن
TOKEN=$(curl -sk -X POST $BASE/api/auth/login -d "username=admin&password=<رمز جدید>" \
        | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
# ۳) تعداد شاخص‌ها (باید ۱۶۴ باشد)
curl -sk $BASE/api/kpis -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json;print(len(json.load(sys.stdin)),'شاخص')"
# ۴) داشبورد
curl -sk "$BASE/api/dashboard/overview" -H "Authorization: Bearer $TOKEN"
```
معیار قبولی: هر ۴ فرمان بدون خطا و با داده صحیح پاسخ دهند و صفحهٔ داشبورد در مرورگر با نمودارها بارگذاری شود.

---

## ۱۳. عیب‌یابی رایج

| نشانه | علت محتمل | راه‌حل |
|-------|-----------|--------|
| کانتینر `api` بالا نمی‌آید | خطای اتصال به دیتابیس | صبر تا `db` سالم شود؛ بررسی `DATABASE_URL` و `DB_PASSWORD` |
| صفحهٔ سفید / نمودارها لود نمی‌شود | فایل‌های استاتیک | `docker compose logs api`؛ بررسی build کامل frontend |
| خطای ۴۰۱ هنگام استفاده | توکن منقضی/نامعتبر | خروج و ورود مجدد؛ بررسی هماهنگی ساعت سرور |
| خطای ۵۰۰ در خروجی PDF | فونت/کتابخانه | فونت Vazirmatn در ایمیج هست؛ build مجدد `--build` |
| کندی داشبورد | نبود ایندکس/منابع کم | افزایش RAM/CPU؛ ایندکس‌ها در اسکیمای تولید فعال‌اند |
| «پورت در حال استفاده است» | تداخل پورت ۸۰۰۰/۴۴۳ | تغییر نگاشت پورت در `docker-compose.yml` |

**دستورات مفید:**
```bash
docker compose restart api        # ری‌استارت فقط برنامه
docker compose down               # توقف (داده حفظ می‌شود روی volume)
docker compose down -v            # ⚠️ توقف + حذف داده (فقط محیط تست)
```

---

## پیوست الف — متغیرهای محیطی

| متغیر | کجا | توضیح |
|-------|-----|-------|
| `DATABASE_URL` | api | DSN اتصال به PostgreSQL؛ اگر تنظیم نشود → SQLite (فقط نمونه) |
| `KPI_SECRET_KEY` | api | کلید امضای JWT (اجباری در تولید) |
| `DB_PASSWORD` | compose/db | رمز کاربر پایگاه‌داده |

## پیوست ب — مسیر فایل‌های کلیدی

| فایل | نقش |
|------|-----|
| `docker-compose.yml` | تعریف سرویس‌ها |
| `.env` | مقادیر محرمانه Compose (ساخته می‌شود؛ در Git نباشد) |
| `backend/Dockerfile` | ساخت ایمیج برنامه |
| `deploy/nginx.conf` | reverse proxy + TLS |
| `deploy/backup.sh` | پشتیبان‌گیری |
| `deploy/kpi-ms.service` | یونیت systemd (نصب بدون Docker) |
| Volume `pgdata` | دادهٔ ماندگار PostgreSQL |

---

**پشتیبانی:** برای مهاجرت دادهٔ واقعی، اتصال LDAP/SSO، یا تنظیمات خاص شبکه، به اسناد `02-Architecture.md`، `07-Data-Analysis.md` و `08-Tech-Stack.md` مراجعه کنید.
