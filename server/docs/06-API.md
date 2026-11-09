# مرجع REST API

- **Base URL:** `/api`
- **احراز هویت:** `Authorization: Bearer <JWT>` (به‌جز `/auth/login` و `/health`)
- **مستندات تعاملی:** `GET /docs` (Swagger UI) · `GET /openapi.json`
- **قالب داده:** JSON (UTF-8)؛ تاریخ‌ها بر مبنای **سال/ماه شمسی**.

## احراز هویت

| متد | مسیر | توضیح |
|-----|------|-------|
| POST | `/auth/login` | ورود (form: `username`, `password`) → `{access_token}` |
| GET | `/auth/me` | پروفایل کاربر جاری |

```bash
# نمونه ورود
curl -X POST /api/auth/login -d "username=admin&password=Passw0rd!"
# → {"access_token":"eyJ...","token_type":"bearer"}
```

## داشبورد و تحلیل

| متد | مسیر | نقش | توضیح |
|-----|------|-----|-------|
| GET | `/dashboard/overview?year=` | همه | آمار کلان: کل/سبز/زرد/قرمز، میانگین تحقق (ساده و وزنی) |
| GET | `/dashboard/by-process?year=` | همه | رتبه‌بندی و وضعیت فرایندها |
| GET | `/dashboard/trend?months=&kpi_id=&process_id=` | همه | روند تحقق (سازمان/فرایند/شاخص) |
| GET | `/dashboard/pareto?year=` | همه | Pareto شاخص‌های بحرانی (وزنی + تجمعی) |
| GET | `/dashboard/strategic?year=` | همه | شاخص‌های استراتژیک با آخرین وضعیت |
| GET | `/dashboard/critical?year=` | همه | فهرست شاخص‌های بحرانی + علت/اقدام |

## شاخص‌ها (KPI Master)

| متد | مسیر | نقش | توضیح |
|-----|------|-----|-------|
| GET | `/kpis?process_id=&importance=&strategic=&q=` | همه* | فهرست (مالک فرایند فقط فرایند خود) |
| GET | `/kpis/{id}` | همه | جزئیات شاخص |
| POST | `/kpis` | admin | ایجاد شاخص (کد خودکار در صورت خالی) |
| PUT | `/kpis/{id}` | admin | ویرایش — **`reason` اجباری**، هر فیلد در Audit ثبت می‌شود |
| DELETE | `/kpis/{id}?reason=` | admin | حذف + ثبت دلیل |

## داده‌ها و گردش‌کار

| متد | مسیر | نقش | توضیح |
|-----|------|-----|-------|
| GET | `/entries?kpi_id=&process_id=&year=&month=&state=` | همه* | فهرست رکوردها |
| POST | `/entries` | owner/admin | ثبت/به‌روزرسانی (محاسبه خودکار تحقق/وضعیت) |
| POST | `/entries/workflow` | نقش‌محور | اقدام گردش‌کار: `submit\|review\|approve\|reject\|reopen` |
| GET | `/entries/inbox` | owner/quality/admin | کارتابل نیازمند اقدام |

```json
// POST /api/entries
{ "kpi_id": 1, "year": 1405, "month": 5, "actual": 88.5,
  "comment": "بهبود نسبت به ماه قبل", "deviation_cause": "", "corrective_action": "" }
```

## ساختار سازمانی

| متد | مسیر | نقش | توضیح |
|-----|------|-----|-------|
| GET | `/org/tree` | همه | درخت شرکت←معاونت←فرایند با رول‌آپ تعداد شاخص |
| GET | `/org/processes` | همه | فهرست فرایندها + مالک |
| POST | `/org/units` | admin | ایجاد واحد |
| PUT | `/org/units/{id}` | admin | ویرایش واحد |

## کاربران و نقش‌ها

| متد | مسیر | نقش | توضیح |
|-----|------|-----|-------|
| GET | `/users` | admin | فهرست کاربران |
| POST/PUT/DELETE | `/users`, `/users/{id}` | admin | مدیریت کاربر |
| GET | `/users/roles` | admin/quality | فهرست نقش‌ها |
| GET | `/users/views` | admin | کلید و برچسب دسترسی‌های صفحه‌به‌صفحه + پیش‌فرض هر نقش |
| — | `UserIn.permissions` / `UserIn.must_change` | admin | بازنویسی دسترسی‌های کاربر و اجبار تغییر رمز |

## گزارش، ممیزی، تنظیمات

| متد | مسیر | نقش | توضیح |
|-----|------|-----|-------|
| GET | `/export/excel?year=` | همه | خروجی Excel رنگی (جایگزین فایل فعلی) |
| GET | `/export/pdf?year=` | همه | گزارش مدیریتی PDF فارسی |
| GET | `/audit?limit=&entity_type=` | admin/quality | لاگ تغییرات |
| GET/PUT | `/settings` | GET همه / PUT admin | آستانه‌ها، سال جاری، نام سازمان |
| GET | `/meta` | همه | فهرست‌های مرجع UI (سال‌ها، ماه‌ها، enums، شرکت‌ها، دسترسی‌ها، آستانه‌ها) |
| GET | `/export/csv?year=` | همه | داده خام ثبت‌ها (CSV با BOM) |
| GET | `/reports/list?scope=all\|active\|inactive&format=json\|csv\|xlsx` | همه | خروجی فهرست شاخص‌ها |
| GET | `/reports/range?from=&to=&basis=avg\|last` | همه | گزارش دوره‌ای با بازه تاریخ شمسی |
| GET | `/reports/range.csv/.xlsx/.pdf` | همه | همان گزارش با خروجی فایل |
| GET | `/reports/no-data?from=&to=&kind=none\|partial` | همه | شاخص‌های بدون داده/ناقص در بازه |
| GET | `/reports/no-data.xlsx/.pdf` | همه | خروجی فایل گزارش داده ناقص |
| GET | `/reports/backup` | admin | پشتیبان JSON از ۱۱ جدول |
| POST | `/reports/restore` | admin | بازیابی از فایل پشتیبان (تنظیمات حفظ می‌شود) |
| POST | `/settings/load-sample` | admin | بازتولید داده نمونه سال جاری |
| POST | `/settings/clear-data` | admin | حذف همه ثبت‌های عملکرد |

پارامترهای مشترک گزارش‌های دوره‌ای: `process_id`, `status`, `importance`, `approved_only`, `company`.

## احراز هویت و امنیت ورود

| متد | مسیر | توضیح |
|-----|------|-------|
| POST | `/auth/login` | OAuth2 password form؛ پس از ۵ تلاش ناموفق، حساب ۵ دقیقه قفل می‌شود |
| GET | `/auth/me` | کاربر جاری + دسترسی‌های موثر |
| POST | `/auth/change-password` | تغییر رمز (سیاست: ≥۸ کاراکتر، حرف+عدد، غیر از رمزهای پیش‌فرض) |
| POST | `/auth/admin-recovery` | با `{"confirm":"RESET"}` رمز admin بازنشانی و `setup_token` صادر می‌شود |
| POST | `/auth/complete-setup` | با `setup_token` رمز جدید تعیین می‌شود |

> ورود با رمز پیش‌فرض `Passw0rd!` پاسخ `must_change: true` می‌دهد و رابط کاربری صفحه تغییر رمز را نمایش می‌دهد.
> `admin-recovery` با تنظیم `recovery_enabled=0` در `/settings` غیرفعال می‌شود.

## اهداف استراتژیک و برنامه اقدام

| متد | مسیر | توضیح |
|-----|------|-------|
| GET | `/strategy/goals?asof=&company_id=` | اهداف + ارزیابی + اتصال شاخص‌ها + اقدامات + رویدادها |
| POST/PUT | `/strategy/goals`, `/strategy/goals/{id}` | ایجاد/ویرایش هدف (`start_period`/`end_period` به شکل `1405/01`) |
| POST | `/strategy/goals/{id}/archive` | بایگانی هدف |
| POST/PUT/DELETE | `/strategy/goals/{id}/links`, `/strategy/links/{id}` | اتصال شاخص با `mode` (`maintain`/`improve`)، `baseline`، `target`، `weight` |
| POST/PUT | `/strategy/goals/{id}/actions`, `/strategy/actions/{id}` | برنامه اقدام با `rule` (`always`/`behind`/`below`/`above`) و `threshold` |
| POST | `/strategy/actions/{id}/report` | ثبت گزارش اجرا (وضعیت/پیشرفت؛ گزارش یا دلیل الزامی) |
| POST | `/strategy/actions/{id}/start-checked` | شروع اقدام فقط در صورت تحقق شرط؛ بدنه: `{"asof":"1405/08"}` |
| POST | `/strategy/samples` | نصب ۴ هدف نمونه با اتصال به شاخص‌های موجود |

## تحلیل آماری و هلدینگ

| متد | مسیر | توضیح |
|-----|------|-------|
| GET | `/kpis/{id}/analysis?fy=&fm=&ty=&tm=&alpha=0.05&method=paired\|welch` | تحلیل چندساله: نقاط، خلاصه سالانه، مقایسه زوجی با اصلاح هولم، آزمون شیب روند |
| GET | `/holding/overview?year=` | مقایسه شرکت‌ها، میانگین وزنی، برترین شرکت |
| GET/POST/PUT/DELETE | `/companies` | CRUD شرکت‌های هلدینگ |
| GET | `/dashboard/top?year=&limit=` | برترین/ضعیف‌ترین شاخص‌ها با تحقق بدون سقف |
| GET | `/dashboard/radar?year=` | میانگین تحقق معاونت‌ها (نمودار راداری) |

## کدهای وضعیت (HTTP)
`200` موفق · `400` خطای اعتبارسنجی/قاعده کسب‌وکار · `401` عدم احراز · `403` عدم دسترسی نقش · `404` یافت‌نشد.

> نکته یکپارچه‌سازی: سیستم‌های تولید/MES می‌توانند مقادیر را به‌صورت خودکار از طریق `POST /entries` ثبت کنند؛ موتور محاسبات و گردش‌کار به‌صورت خودکار اعمال می‌شوند.
