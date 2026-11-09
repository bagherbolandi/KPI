# مدل داده و دیکشنری جداول

> دیاگرام کامل: [`erd.svg`](erd.svg)

پایگاه داده حول ۸ جدول اصلی طراحی شده که یکپارچگی ارجاعی کامل بین ساختار سازمانی، شاخص‌ها، داده‌های دوره‌ای و حسابرسی را تضمین می‌کند.

## نمای کلی روابط

```
companies/divisions/processes  →  org_units (درخت خودارجاع)
org_units 1──N kpis            (هر فرایند چند شاخص)
kpis      1──N kpi_entries     (هر شاخص چند رکورد دوره‌ای، یکتا بر (kpi,year,month))
roles     1──N users
org_units 1──N users           (انتساب مالک فرایند)
users     1──N kpi_entries     (ثبت/بررسی/تأیید)
* هر تغییر حساس → audit_logs
```

---

## جدول `org_units` — ساختار سازمانی (درخت خودارجاع)

| ستون | نوع | توضیح |
|------|-----|-------|
| id | PK | شناسه |
| code | varchar(30) | کد یکتای واحد (CO, OPS, PLN, …) |
| name | varchar(160) | نام فارسی |
| level | varchar(20) | `company` \| `division` \| `process` |
| parent_id | FK→org_units.id | والد (NULL برای شرکت) |
| owner_user_id | FK→users.id | مالک فرایند |
| order | int | ترتیب نمایش |

> این مدل واحدِ «شرکت ← معاونت ← فرایند» را می‌سازد و با چند ریشهٔ `company` از **چند‌شرکتی** پشتیبانی می‌کند.

## جدول `roles` — نقش‌ها

| ستون | نوع | توضیح |
|------|-----|-------|
| id | PK | |
| code | varchar(40) UNIQUE | `admin`, `process_owner`, `quality`, `executive` |
| name_fa / name_en | varchar | نام دوزبانه |
| description | text | شرح دسترسی |

## جدول `users` — کاربران

| ستون | نوع | توضیح |
|------|-----|-------|
| id | PK | |
| username | varchar(60) UNIQUE | نام کاربری |
| full_name / email | varchar | مشخصات |
| hashed_password | varchar(200) | bcrypt |
| role_id | FK→roles.id | نقش |
| process_id | FK→org_units.id | فرایند منتسب (برای مالک فرایند) |
| is_active | bool | فعال/غیرفعال |
| created_at | datetime | |

## جدول `kpis` — شاخص اصلی (KPI Master)

| ستون | نوع | توضیح |
|------|-----|-------|
| id | PK | |
| code | varchar(20) UNIQUE | کد شاخص (مثل `PLN-01`) |
| name | varchar(240) | نام شاخص |
| process_id | FK→org_units.id | فرایند |
| uom | varchar(30) | واحد اندازه‌گیری (percent, count, days, ppm, …) |
| direction | varchar(6) | `up` (🔺 بیشتر بهتر) \| `down` (🔻 کمتر بهتر) |
| frequency | varchar(16) | monthly \| quarterly \| semiannual \| annual \| event |
| target | float | مقدار هدف |
| warning | float | حد هشدار |
| critical | float | حد بحرانی |
| weight | float | وزن شاخص |
| importance | varchar(16) | `key` (کلیدی) \| `operational` (عملیاتی) |
| is_strategic | bool | نمایش در داشبورد استراتژیک |
| definition | text | تعریف شاخص |
| formula | text | روش محاسبه |
| acceptance_text | varchar(120) | معیار پذیرش (متن اصلی حفظ‌شده) |
| calc_mode | varchar(16) | `achievement` \| `band` |
| th_green / th_yellow | float NULL | بازنویسی آستانه در سطح شاخص |
| data_owner_id / approver_id | FK→users.id | مسئول ثبت / مسئول تأیید |
| active | bool | فعال بودن |
| created_at | datetime | |

## جدول `kpi_entries` — داده‌های دوره‌ای + گردش‌کار

| ستون | نوع | توضیح |
|------|-----|-------|
| id | PK | |
| kpi_id | FK→kpis.id | شاخص |
| year / month | int | **سال و ماه شمسی** |
| — | UNIQUE(kpi_id, year, month) | جلوگیری از ثبت تکراری دوره |
| actual | float NULL | مقدار واقعی (NULL = ثبت‌نشده) |
| achievement | float NULL | درصد تحقق محاسبه‌شده (۰..۱) |
| status | varchar(8) NULL | green \| yellow \| red |
| comment | text | توضیحات عملکرد |
| deviation_cause | text | علت انحراف |
| corrective_action | text | اقدام اصلاحی |
| workflow_state | varchar(16) | draft \| submitted \| qc_reviewed \| approved \| rejected |
| submitted_by/at, reviewed_by/at, approved_by/at | FK/datetime | ردگیری گردش‌کار |
| rejection_reason | text | دلیل رد |
| updated_at | datetime | |

## جدول `audit_logs` — ثبت تغییرات (Change-Log)

| ستون | نوع | توضیح |
|------|-----|-------|
| id | PK | |
| user_id / username | FK/varchar | کاربر انجام‌دهنده |
| entity_type | varchar(40) | kpi \| entry \| user \| org \| setting \| system |
| entity_id | varchar(40) | شناسه موجودیت |
| action | varchar(30) | create \| update \| delete \| submit \| review \| approve \| reject |
| field | varchar(60) | نام فیلد تغییر‌یافته |
| old_value / new_value | text | **مقدار قبل و بعد** |
| reason | text | **دلیل تغییر** (برای شاخص‌ها اجباری) |
| created_at | datetime (index) | زمان |

## جدول `settings` — پیکربندی سراسری

| کلید | مقدار پیش‌فرض | کاربرد |
|------|--------------|--------|
| th_green | 0.85 | آستانه سبز |
| th_yellow | 0.60 | آستانه زرد |
| org_name | «شرکت صنعتی نمونه» | نام سازمان |
| current_year | 1405 | سال جاری شمسی |

---

## نمایه‌ها و یکپارچگی (Indexing & Integrity)
- ایندکس روی `kpi_entries(kpi_id, year, month)` و `audit_logs(created_at)` برای سرعت داشبورد و گزارش.
- محدودیت یکتایی دوره از داده تکراری جلوگیری می‌کند.
- در تولید: کلیدهای خارجی با `ON DELETE` مناسب، و برای Multi-Tenant افزودن `company_id` به جداول تراکنشی یا Schema-per-Tenant.

## مهاجرت (Migration)
نمونه از `Base.metadata.create_all` استفاده می‌کند. برای تولید، **Alembic** جهت نسخه‌بندی اسکیمای PostgreSQL توصیه می‌شود؛ اسکریپت `seed.py` نگاشت اولیهٔ ۱۶۴ شاخص را انجام می‌دهد.
