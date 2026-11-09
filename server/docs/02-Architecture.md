# معماری نرم‌افزار و ماژول‌های سامانه

> دیاگرام کامل: [`architecture.svg`](architecture.svg)

## ۱. سبک معماری

سامانه بر اساس **معماری لایه‌ای (Layered / Clean-ish)** با جداسازی مسئولیت‌ها طراحی شده و از الگوی **SPA + REST API** پیروی می‌کند:

```
┌─────────────────────────────────────────────────────────────┐
│  Presentation   │  React SPA (RTL) — داشبورد، فرم‌ها، نمودارها  │
├─────────────────────────────────────────────────────────────┤
│  API & Security │  FastAPI · OAuth2/JWT · RBAC · Pydantic       │
├─────────────────────────────────────────────────────────────┤
│  Domain Services│  Calc Engine · Workflow · Aggregation ·        │
│                 │  Jalali · Reporting · Audit                   │
├─────────────────────────────────────────────────────────────┤
│  Persistence    │  SQLAlchemy ORM → PostgreSQL / SQLite         │
├─────────────────────────────────────────────────────────────┤
│  Integration    │  REST API · Excel Import · Docker · Nginx/TLS │
└─────────────────────────────────────────────────────────────┘
```

**چرا لایه‌ای؟** جداسازی موتور محاسبات و گردش‌کار از لایهٔ ارائه و داده به‌معنای آن است که منطق شاخص‌ها (که در سازمان‌ها مکرراً تغییر می‌کند) بدون دست‌زدن به UI یا مدل داده قابل به‌روزرسانی است — دقیقاً برخلاف اکسل که فرمول با داده در هم تنیده است.

## ۲. ماژول‌های اصلی (Backend)

| ماژول | فایل | مسئولیت |
|-------|------|---------|
| **Auth & Security** | `security.py`, `routers/auth.py` | JWT، bcrypt، `require_roles`، احراز/تفویض |
| **User Management** | `routers/users.py` | CRUD کاربر، تخصیص نقش |
| **Org Structure** | `routers/org.py` | درخت سازمانی، فرایندها، رول‌آپ تعداد شاخص |
| **KPI Master** | `routers/kpis.py` | CRUD شاخص، تولید کد، الزام دلیل تغییر |
| **Data & Workflow** | `routers/entries.py` | ثبت داده، ماشین‌حالت تأیید، کارتابل |
| **Calculation Engine** | `calc.py` | درصد تحقق، تعیین وضعیت (دو حالت) |
| **Dashboard/Analytics** | `routers/dashboard.py` | overview، by-process، trend، pareto، strategic، critical |
| **Reporting** | `routers/reports.py` | خروجی Excel/PDF، Audit، Settings، Meta |
| **Jalali Calendar** | `jalali.py` | تبدیل/نمایش تاریخ شمسی، نام ماه، اعداد فارسی |
| **Audit** | `audit.py`, model `AuditLog` | ثبت تغییرات حساس |
| **Seed/Migration** | `seed.py` | بارگذاری ۱۶۴ شاخص و داده نمونه |

## ۳. ماژول‌های Frontend (SPA)

`Dashboard` (مدیریتی) · `Processes` · `KpiList`/`KpiDetail` · `DataEntry`/`EntryForm` · `Approvals` (کارتابل) · `KpiMaster`/`KpiForm` · `Org` (درخت) · `Users`/`UserForm` · `Audit` · `Settings` · `Reports` — همراه با لایهٔ مشترک `api`, `Ctx` (Auth Context)، اتم‌های UI و بستهٔ نمودار (Chart.js).

## ۴. الگوهای طراحی به‌کار‌رفته

- **RBAC via Dependency Injection**: `require_roles("admin", ...)` به‌عنوان وابستگی FastAPI؛ کنترل دسترسی متمرکز و اعلانی.
- **Row-Level Security اپلیکیشنی**: کوئری‌های مالک فرایند به‌صورت خودکار به `process_id` او محدود می‌شوند.
- **Strategy Pattern در موتور محاسبات**: `calc_mode ∈ {achievement, band}` منطق تعیین وضعیت را قابل‌تعویض می‌کند.
- **State Machine**: انتقال‌های مجاز گردش‌کار در جدول `TRANSITIONS` تعریف و اعتبارسنجی می‌شوند.
- **Configuration over Code**: آستانه‌ها/سال جاری/نام سازمان در جدول `settings`؛ تغییر بدون استقرار مجدد.
- **Audit Interceptor**: هر تغییر حساس از طریق `audit.log(...)` ثبت می‌شود.

## ۵. امنیت

- احراز هویت: **OAuth2 Password Flow + JWT** (انقضای ۱۲ ساعت).
- رمز عبور: **bcrypt** با salt.
- تفویض: RBAC چهارنقشه + محدودسازی سطح داده.
- اعتبارسنجی ورودی: **Pydantic** روی همهٔ بدنه‌ها.
- انتقال: **HTTPS** از طریق reverse-proxy (Nginx) در استقرار.
- توصیه‌های تولید: چرخش `KPI_SECRET_KEY`، Rate-limit روی `/auth/login`، Security Headers، جداسازی شبکه دیتابیس.

## ۶. پیشنهاد فناوری (خلاصه — جزئیات در `08-Tech-Stack.md`)

| لایه | فناوری منتخب | دلیل |
|------|--------------|------|
| Backend | **Python 3.12 + FastAPI** | سرعت توسعه، async، OpenAPI خودکار، اکوسیستم داده |
| ORM | **SQLAlchemy 2.0** | بلوغ، پشتیبانی چند‌پایگاه، Alembic برای migration |
| Database | **PostgreSQL 16** | متن‌باز، قدرتمند، مناسب On-Premise و Multi-Tenant |
| Frontend | **React 18** | اکوسیستم بالغ، مناسب داشبورد تعاملی |
| Charts | **Chart.js / (Recharts در build کامل)** | سبک، RTL-friendly |
| Auth | **JWT (python-jose) + bcrypt** | استاندارد، بدون وابستگی به سرور نشست |
| Reporting | **openpyxl + reportlab + arabic-reshaper** | Excel/PDF فارسی |
| Deploy | **Docker Compose + Nginx** | استقرار ساده داخل شبکه سازمان |

> **یادداشت دربارهٔ نمونهٔ اولیه:** برای خودکفایی و اجرای بدون‌وابستگی، نمونه از **SQLite** و React از طریق UMD (بدون مرحلهٔ build) استفاده می‌کند. برای تولید، تنها با تنظیم `DATABASE_URL` به PostgreSQL و اجرای build کامل React (Vite) مهاجرت انجام می‌شود — بدون تغییر در منطق دامنه.

## ۷. مقیاس‌پذیری و چند‌شرکتی (Multi-Company)

- مدل `org_units` درختی و **چند‌ریشه‌ای** است؛ هر شرکت یک ریشهٔ `level=company` با زیردرخت مستقل.
- گزارش‌ها و داشبوردها بر اساس زیردرخت انتخابی قابل محدودسازی‌اند.
- برای جداسازی سخت‌گیرانه، الگوی **Schema-per-Tenant** در PostgreSQL توصیه می‌شود.

## ۸. یکپارچه‌سازی

- **REST API** کامل (`/docs`) برای اتصال ERP/MES/BI و ثبت خودکار داده.
- **Excel Import** برای مهاجرت اولیه از فایل فعلی.
- نقشهٔ راه: Webhook رویدادها، اتصال LDAP/SSO، Connector مستقیم به منابع داده تولید.
