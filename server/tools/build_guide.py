#!/usr/bin/env python3
"""Build a self-contained, RTL Persian illustrated user guide (HTML+embedded images)."""
import os, base64, html as _html

IMG_DIR = "/home/user/kpi-system/docs/img"
OUT = "/home/user/kpi-system/docs/user-guide.html"

# token -> filename
IMAGES = {
    "LOGIN": "01-login.jpg",
    "DASH": "02-dashboard.jpg",
    "PROC": "03-processes.jpg",
    "KPIS": "04-kpis.jpg",
    "KPID": "05-kpi-detail.jpg",
    "ENTRY": "06-dataentry.jpg",
    "ENTRYF": "07-entry-form.jpg",
    "APPR": "08-approvals.jpg",
    "MASTER": "09-master.jpg",
    "ORG": "10-org.jpg",
    "USERS": "11-users.jpg",
    "AUDIT": "12-audit.jpg",
    "SETT": "13-settings.jpg",
    "REPORTS": "14-reports.jpg",
}

def b64(name):
    with open(os.path.join(IMG_DIR, name), "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()

B64 = {k: b64(v) for k, v in IMAGES.items()}

CSS = """
:root{--blue:#2563eb;--ink:#0f172a;--muted:#64748b;--line:#e2e8f0;--bg:#f1f5f9;
--green:#16a34a;--yellow:#d97706;--red:#dc2626;--card:#fff;}
*{box-sizing:border-box}
body{margin:0;font-family:'Vazir','Tahoma','Segoe UI',sans-serif;background:var(--bg);
color:var(--ink);direction:rtl;line-height:1.9;font-size:16px}
.wrap{max-width:1080px;margin:0 auto;padding:0 18px 80px}
.cover{background:linear-gradient(135deg,#1e3a8a,#2563eb 60%,#0ea5e9);color:#fff;
padding:54px 30px 46px;border-radius:0 0 26px 26px;box-shadow:0 10px 30px rgba(30,58,138,.25);margin-bottom:30px}
.cover .k{display:inline-block;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.4);
width:54px;height:54px;border-radius:14px;text-align:center;line-height:54px;font-weight:800;font-size:28px;margin-bottom:14px}
.cover h1{margin:6px 0 4px;font-size:30px}
.cover p{margin:0;opacity:.92;font-size:15px}
.cover .meta{margin-top:18px;display:flex;gap:14px;flex-wrap:wrap;font-size:13px}
.cover .meta span{background:rgba(255,255,255,.14);padding:5px 12px;border-radius:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px 24px;
margin:22px 0;box-shadow:0 4px 16px rgba(15,23,42,.05)}
.card h2{margin:0 0 6px;color:var(--blue);font-size:22px;display:flex;align-items:center;gap:10px}
.card h3{color:#12315b;font-size:17px;margin:18px 0 6px}
.lead{color:var(--muted);margin:0 0 10px}
figure{margin:18px 0;padding:0}
figure .frame{border:1px solid var(--line);border-radius:14px;overflow:hidden;background:#fff;
box-shadow:0 6px 20px rgba(15,23,42,.08)}
figure img{display:block;width:100%;height:auto}
figcaption{caption-side:bottom;color:var(--muted);font-size:13.5px;margin-top:8px;padding:0 4px}
.tag{display:inline-block;background:#eff6ff;color:var(--blue);border:1px solid #bfdbfe;
border-radius:8px;padding:2px 10px;font-size:13px;margin:2px 0}
.steps{counter-reset:s;list-style:none;padding:0;margin:10px 0}
.steps li{position:relative;padding:10px 46px 10px 0;counter-increment:s;border-bottom:1px dashed var(--line)}
.steps li:last-child{border-bottom:0}
.steps li::before{content:counter(s,persian);position:absolute;right:0;top:10px;width:30px;height:30px;
background:var(--blue);color:#fff;border-radius:50%;text-align:center;line-height:30px;font-weight:700;font-size:14px}
.steps li b{color:#12315b}
table.tblx{width:100%;border-collapse:collapse;margin:10px 0;font-size:14.5px}
table.tblx th,table.tblx td{border:1px solid var(--line);padding:9px 12px;text-align:right}
table.tblx th{background:#f8fafc;color:#12315b}
.note,.tip,.warn{display:flex;gap:10px;border-radius:12px;padding:12px 16px;margin:14px 0;font-size:14.5px}
.note{background:#eff6ff;border:1px solid #bfdbfe;color:#1e40af}
.tip{background:#ecfdf5;border:1px solid #a7f3d0;color:#065f46}
.warn{background:#fef2f2;border:1px solid #fecaca;color:#991b1b}
.note b,.tip b,.warn b{display:block;margin-bottom:2px}
.chip{display:inline-block;border-radius:7px;padding:2px 9px;font-size:12.5px;font-weight:700}
.chip.g{background:#dcfce7;color:var(--green)}
.chip.y{background:#fef3c7;color:var(--yellow)}
.chip.r{background:#fee2e2;color:var(--red)}
.chip.b{background:#dbeafe;color:var(--blue)}
.legend{display:flex;gap:14px;flex-wrap:wrap;margin:10px 0}
.legend div{display:flex;align-items:center;gap:7px;font-size:14px}
.dot{width:14px;height:14px;border-radius:4px;display:inline-block}
.dot.g{background:var(--green)}.dot.y{background:var(--yellow)}.dot.r{background:var(--red)}
.callout-role{background:#f8fafc;border-inline-start:4px solid var(--blue);padding:10px 16px;border-radius:0 10px 10px 0;margin:8px 0}
.toc{columns:2;column-gap:28px;font-size:14.5px}
.toc a{color:#12315b;text-decoration:none;display:block;padding:3px 0;border-bottom:1px dashed var(--line)}
.toc a:hover{color:var(--blue)}
.kbd{background:#0f172a;color:#fff;border-radius:6px;padding:1px 8px;font-size:13px;font-family:monospace}
.footer{text-align:center;color:var(--muted);font-size:13px;margin-top:40px;padding-top:20px;border-top:1px solid var(--line)}
.eq{background:#f8fafc;border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:8px 0;font-size:15px}
"""

HTML = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>راهنمای کاربری سامانه مدیریت شاخص‌های عملکرد (KPI-MS)</title>
<style>__CSS__</style>
</head>
<body>
<div class="cover">
  <div class="k">K</div>
  <h1>راهنمای کاربری ساده سامانه KPI-MS</h1>
  <p>سامانه مدیریت و پایش شاخص‌های کلیدی عملکرد — نسخه ۱.۰</p>
  <div class="meta">
    <span>📘 ویژه مدیران و مالکان فرایند</span>
    <span>🗓 تقویم شمسی (جلالی)</span>
    <span>🔒 دسترسی بر اساس نقش (RBAC)</span>
    <span>🖼 شامل تصاویر واقعی از محیط سامانه</span>
  </div>
</div>
<div class="wrap">

<div class="card">
  <h2>📑 فهرست مطالب</h2>
  <div class="toc">
    <a href="#intro">۱. این سامانه چیست؟</a>
    <a href="#login">۲. ورود به سامانه</a>
    <a href="#ui">۳. آشنایی با محیط کار</a>
    <a href="#roles">۴. نقش‌ها و سطوح دسترسی</a>
    <a href="#dash">۵. داشبورد مدیریتی</a>
    <a href="#proc">۶. فرایندها</a>
    <a href="#kpis">۷. شاخص‌ها و روندها</a>
    <a href="#entry">۸. ثبت اطلاعات عملکرد</a>
    <a href="#wf">۹. کارتابل تأیید و گردش کار</a>
    <a href="#reports">۱۰. گزارش‌ها و خروجی</a>
    <a href="#admin">۱۱. بخش مدیریت سیستم</a>
    <a href="#color">۱۲. معنی رنگ‌ها و وضعیت‌ها</a>
    <a href="#faq">۱۳. نکات و پرسش‌های متداول</a>
  </div>
</div>

<div class="card" id="intro">
  <h2>۱. این سامانه چیست؟</h2>
  <p class="lead">سامانه مدیریت شاخص‌های عملکرد (KPI-MS) جایگزین فایل اکسل دستی شما است. با این سامانه می‌توانید:</p>
  <ul>
    <li>شاخص‌های کلیدی هر واحد را در یک مکان متمرکز ببینید (۱۶۴ شاخص در ۱۶ فرایند).</li>
    <li>عملکرد واقعی هر ماه را ثبت کنید و درصد تحقق هدف را به‌صورت خودکار ببینید.</li>
    <li>گردش کار تأیید (مالک فرایند ← مدیر کیفیت) را به‌صورت سیستمی طی کنید.</li>
    <li>داشبوردهای مدیریتی، نمودار پارتو و گزارش‌های PDF/Excel خروجی بگیرید.</li>
  </ul>
  <div class="note"><b>نکته</b>تمام تاریخ‌ها با تقویم شمسی (مثلاً ۱۴۰۵/۰۵/۱۵) و اعداد به صورت فارسی نمایش داده می‌شوند.</div>
</div>

<div class="card" id="login">
  <h2>۲. ورود به سامانه</h2>
  <ol class="steps">
    <li>آدرس سامانه را در مرورگر باز کنید. صفحه ورود مانند تصویر زیر نمایش داده می‌شود.</li>
    <li>در فیلد <b>نام کاربری</b> نام کاربری خود را وارد کنید (مثلاً <span class="kbd">owner_pln</span>).</li>
    <li>در فیلد <b>رمز عبور</b> گذرواژه خود را بنویسید.</li>
    <li>روی دکمه <b>«ورود به سامانه»</b> کلیک کنید.</li>
  </ol>
  <figure><div class="frame"><img src="__LOGIN__" alt="صفحه ورود"></div>
    <figcaption>تصویر ۱ — صفحه ورود به سامانه (نام کاربری و گذرواژه).</figcaption></figure>
  <div class="tip"><b>حساب‌های نمونه برای آشنایی</b>رمز عبور همه یکسان است: <span class="kbd">Passw0rd!</span>
    &nbsp; • <span class="kbd">admin</span> مدیر سیستم &nbsp; • <span class="kbd">ceo</span> مدیریت ارشد &nbsp; • <span class="kbd">quality</span> مدیر کیفیت &nbsp; • <span class="kbd">owner_pln</span> مالک فرایند برنامه‌ریزی</div>
  <div class="warn"><b>اگر رمز را فراموش کردید</b>با مدیر سیستم (نقش admin) تماس بگیرید تا رمز را بازنشانی کند. امکان بازیابی خودکار رمز در حال حاضر غیرفعال است.</div>
</div>

<div class="card" id="ui">
  <h2>۳. آشنایی با محیط کار</h2>
  <p class="lead">پس از ورود، صفحه به دو بخش تقسیم می‌شود:</p>
  <ul>
    <li><b>نوار کناری (راست):</b> منوی اصلی شامل بخش‌های پایش، ثبت و گردش کار، و مدیریت سیستم. منوی هر کاربر فقط شامل بخش‌های مجاز به نقش اوست.</li>
    <li><b>نوار بالا:</b> نام صفحه فعلی، <b>فیلتر سال مالی</b> (برای جابجایی بین سال‌های ۱۴۰۳/۱۴۰۴/۱۴۰۵)، و کادر کاربری برای خروج (کلیک روی نام شما ⏻).</li>
  </ul>
  <div class="callout-role">برای دیدن داده‌های سال دیگر، کافی است در نوار بالا سال مورد نظر را انتخاب کنید؛ تمام صفحات (داشبورد، فرایندها، شاخص‌ها) به آن سال تغییر می‌کنند.</div>
</div>

<div class="card" id="roles">
  <h2>۴. نقش‌ها و سطوح دسترسی</h2>
  <p class="lead">سامانه چهار نقش دارد. دسترسی شما بستگی به نقش‌تان دارد:</p>
  <table class="tblx">
    <thead><tr><th>نقش</th><th>مشاهده داشبورد/شاخص‌ها</th><th>ثبت اطلاعات</th><th>تأیید (کارتابل)</th><th>تنظیمات و مدیریت</th></tr></thead>
    <tbody>
      <tr><td><b>مدیریت ارشد</b> (executive)</td><td><span class="chip g">بله</span></td><td><span class="chip.r">خیر</span></td><td><span class="chip.r">خیر</span></td><td><span class="chip.r">خیر</span></td></tr>
      <tr><td><b>مالک فرایند</b> (process_owner)</td><td><span class="chip g">فقط فرایند خود</span></td><td><span class="chip g">بله</span></td><td><span class="chip y">ویرایش/ارسال</span></td><td><span class="chip.r">خیر</span></td></tr>
      <tr><td><b>مدیر کیفیت</b> (quality)</td><td><span class="chip g">بله</span></td><td><span class="chip.r">خیر</span></td><td><span class="chip g">تأیید/رد</span></td><td><span class="chip y">ساختار/لاگ</span></td></tr>
      <tr><td><b>مدیر سیستم</b> (admin)</td><td><span class="chip g">همه</span></td><td><span class="chip g">بله</span></td><td><span class="chip g">تأیید/رد</span></td><td><span class="chip g">همه تنظیمات</span></td></tr>
    </tbody>
  </table>
  <div class="note"><b>محدودیت ردیفی</b>مالک فرایند فقط شاخص‌های <b>فرایندِ خودش</b> را می‌بیند؛ مدیر کیفیت و مدیر سیستم کل سازمان را.</div>
</div>

<div class="card" id="dash">
  <h2>۵. داشبورد مدیریتی</h2>
  <p class="lead">نخستین صفحه پس از ورود. نمای کلی سلامت سازمان را در یک نگاه نشان می‌دهد.</p>
  <figure><div class="frame"><img src="__DASH__" alt="داشبورد مدیریتی"></div>
    <figcaption>تصویر ۲ — داشبورد مدیریتی: کارت‌های آماری، نمودار توزیع، روند ۱۲ ماهه، شاخص‌های استراتژیک و رتبه‌بندی فرایندها.</figcaption></figure>
  <h3>بخش‌های داشبورد:</h3>
  <ul>
    <li><b>کارت‌های بالا:</b> کل شاخص‌ها، میانگین تحقق اهداف (وزنی)، تعداد شاخص‌های مطلوب و بحرانی.</li>
    <li><b>نمودار دونات:</b> توزیع وضعیت (سبز/زرد/قرمز/بدون داده).</li>
    <li><b>نمودار روند:</b> میانگین تحقق سازمان در ۱۲ ماه اخیر.</li>
    <li><b>جدول شاخص‌های استراتژیک:</b> وضعیت مهم‌ترین شاخص‌های شرکت.</li>
    <li><b>رتبه‌بندی فرایندها:</b> هر فرایند با میانگین تحقق و توزیع رنگی؛ روی «مشاهده شاخص‌ها ›» کلیک کنید تا شاخص‌های آن فرایند باز شود.</li>
    <li><b>شاخص‌های بحرانی:</b> فهرست مواردی که در وضعیت قرمز هستند تا در اولویت پیگیری قرار گیرند.</li>
  </ul>
  <div class="tip"><b>نکته مدیریتی</b>اگر کارت «میانگین تحقق» قرمز باشد، یعنی میانگین سازمان زیر ۶۰٪ است — نشانه نیاز به مداخله فوری.</div>
</div>

<div class="card" id="proc">
  <h2>۶. فرایندها</h2>
  <p class="lead">نمای فشرده عملکرد ۱۶ فرایند سازمان به صورت کارت‌های رنگی.</p>
  <figure><div class="frame"><img src="__PROC__" alt="فرایندها"></div>
    <figcaption>تصویر ۳ — کارت عملکرد هر فرایند شامل میانگین تحقق، نوار پیشرفت و تعداد شاخص‌های مطلوب/توجه/بحرانی.</figcaption></figure>
  <p>روی هر کارت دکمه <b>«مشاهده شاخص‌ها»</b> بزنید تا فهرست شاخص‌های همان فرایند باز شود.</p>
</div>

<div class="card" id="kpis">
  <h2>۷. شاخص‌ها و روندها</h2>
  <p class="lead">فهرست کامل شاخص‌ها با امکان جستجو، فیلتر و مشاهده روند هر شاخص.</p>
  <figure><div class="frame"><img src="__KPIS__" alt="فهرست شاخص‌ها"></div>
    <figcaption>تصویر ۴ — جدول شاخص‌ها: کد، نام، فرایند، جهت (🔺/🔻)، هدف، حد هشدار، تناوب و سطح اهمیت.</figcaption></figure>
  <ol class="steps">
    <li>با کادر <b>جستجو</b> شاخص یا کد را پیدا کنید.</li>
    <li>از فیلتر <b>فرایند</b> و <b>سطح اهمیت</b> (کلیدی/عملیاتی) برای محدود کردن فهرست استفاده کنید.</li>
    <li>روی <b>«روند و جزئیات ›»</b> هر شاخص کلیک کنید تا پنجره جزئیات باز شود.</li>
  </ol>
  <figure><div class="frame"><img src="__KPID__" alt="جزئیات شاخص"></div>
    <figcaption>تصویر ۵ — پنجره جزئیات شاخص: تعریف، فرمول محاسبه، هدف/حد هشدار/حد بحرانی و نمودار روند عملکرد در برابر هدف (۲۴ ماه).</figcaption></figure>
  <div class="note"><b>🔺 و 🔻 چیست؟</b><b>🔺 بیشتر بهتر</b> (مثل تولید): هرچه عدد واقعی بیشتر، بهتر. <b>🔻 کمتر بهتر</b> (مثل ضایعات): هرچه عدد واقعی کمتر، بهتر.</div>
</div>

<div class="card" id="entry">
  <h2>۸. ثبت اطلاعات عملکرد <span class="tag">مالک فرایند / مدیر سیستم</span></h2>
  <p class="lead">این بخش قلب سامانه است: در پایان هر دوره، مقدار واقعی هر شاخص را ثبت می‌کنید.</p>
  <figure><div class="frame"><img src="__ENTRY__" alt="ورود اطلاعات"></div>
    <figcaption>تصویر ۶ — صفحه ورود اطلاعات: انتخاب دوره (ماه و سال) و جدول شاخص‌های فرایند شما.</figcaption></figure>
  <ol class="steps">
    <li>در نوار ابزر، <b>دوره ثبت</b> (ماهِ شمسی) و سال را انتخاب کنید — مثلاً «خرداد ۱۴۰۵».</li>
    <li>در جدول، روی دکمه <b>«ثبت»</b> (برای موردی که هنوز ثبت نشده) یا <b>«ویرایش»</b> کلیک کنید.</li>
    <li>در پنجره باز‌شده، <b>مقدار واقعی عملکرد</b> را در خانه مربوطه وارد کنید.</li>
    <li>در صورت نیاز <b>توضیحات</b>، <b>علت انحراف</b> و <b>اقدام اصلاحی</b> را بنویسید (مخصوصاً اگر هدف محقق نشده).</li>
    <li>روی <b>«ذخیره پیش‌نویس»</b> بزنید تا بعداً ویرایشش کنید، یا روی <b>«ذخیره و ارسال برای تأیید»</b> تا وارد کارتابل مدیر کیفیت شود.</li>
  </ol>
  <figure><div class="frame"><img src="__ENTRYF__" alt="فرم ثبت عملکرد"></div>
    <figcaption>تصویر ۷ — فرم ثبت عملکرد: هدف و جهت نمایش داده شده، درصد تحقق و وضعیت به‌صورت خودکار محاسبه می‌شوند.</figcaption></figure>
  <div class="tip"><b>نکته</b>نیازی نیست درصد تحقق را خودتان حساب کنید؛ سامانه آن را طبق فرمول صعودی/نزولی محاسبه و رنگ‌بندی می‌کند.</div>
</div>

<div class="card" id="wf">
  <h2>۹. کارتابل تأیید و گردش کار <span class="tag">مدیر کیفیت / مالک فرایند</span></h2>
  <p class="lead">پس از ارسال مقدار توسط مالک فرایند، مدیر کیفیت آن را بررسی و تأیید یا رد می‌کند.</p>
  <figure><div class="frame"><img src="__APPR__" alt="کارتابل تأیید"></div>
    <figcaption>تصویر ۸ — کارتابل تأیید مدیر کیفیت: فهرست موارد در انتظار اقدام با دکمه‌های «تأیید» و «رد».</figcaption></figure>
  <h3>وضعیت‌های گردش کار (از شروع تا پایان):</h3>
  <table class="tblx">
    <thead><tr><th>وضعیت</th><th>معنی</th><th>مسئول</th></tr></thead>
    <tbody>
      <tr><td><span class="chip b">پیش‌نویس</span></td><td>ثبت اولیه، هنوز ارسال نشده</td><td>مالک فرایند</td></tr>
      <tr><td><span class="chip b">ثبت‌شده (منتظر بررسی)</span></td><td>ارسال شده، در انتظار مدیر کیفیت</td><td>مدیر کیفیت</td></tr>
      <tr><td><span class="chip y">بررسی کیفیت‌شده</span></td><td>توسط مدیر کیفیت بررسی شد</td><td>مدیر کیفیت</td></tr>
      <tr><td><span class="chip g">تأیید نهایی</span></td><td>تأیید شد و در گزارش‌ها نهایی شد</td><td>مدیر کیفیت</td></tr>
      <tr><td><span class="chip r">رد شده</span></td><td>بازگشت به مالک فرایند برای اصلاح</td><td>مالک فرایند</td></tr>
    </tbody>
  </table>
  <div class="steps">
    <li>مدیر کیفیت وارد بخش <b>«کارتابل تأیید»</b> می‌شود (نشانگر تعداد موارد در منو).</li>
    <li>روی <b>«تأیید»</b> کلیک می‌کند تا شاخص نهایی شود، یا روی <b>«رد»</b> با درج دلیل.</li>
    <li>اگر موردی رد شود، به مالک فرایند بازمی‌گردد تا اصلاح و دوباره ارسال کند.</li>
  </div>
  <div class="warn"><b>عدد واقعی خالی می‌ماند؟</b>تا زمانی که مقدار ثبت نشده، شاخص در داشبورد «بدون داده» (خاکستری) نمایش داده می‌شود.</div>
</div>

<div class="card" id="reports">
  <h2>۱۰. گزارش‌ها و خروجی <span class="tag">همه نقش‌ها</span></h2>
  <p class="lead">سامانه جایگزین فایل اکسل شماست — خروجی‌های آماده مدیریتی دارد.</p>
  <figure><div class="frame"><img src="__REPORTS__" alt="گزارش‌ها"></div>
    <figcaption>تصویر ۹ — صفحه گزارش‌ها: خروجی Excel، خروجی PDF مدیریتی و مستندات API.</figcaption></figure>
  <ul>
    <li><b>⬇ دانلود Excel:</b> خروجی کامل ۱۶۴ شاخص با آخرین عملکرد، درصد تحقق و وضعیت رنگی — مناسب جایگزینی فایل اکسل فعلی.</li>
    <li><b>⬇ دانلود PDF:</b> گزارش مدیریتی شامل نمای کلی، رتبه‌بندی فرایندها و فهرست شاخص‌های بحرانی — مناسب ارائه به مدیریت ارشد.</li>
    <li><b>🔌 API:</b> همه قابلیت‌ها از طریق REST API در دسترس‌اند (مستندات در <span class="kbd">/docs</span>).</li>
  </ul>
  <div class="note"><b>سال گزارش</b>گزارش‌ها طبق <b>سال مالی انتخاب‌شده در نوار بالا</b> تولید می‌شوند؛ قبل از دانلود، سال صحیح را انتخاب کنید.</div>
</div>

<div class="card" id="admin">
  <h2>۱۱. بخش مدیریت سیستم <span class="tag">فقط مدیر سیستم (admin)</span></h2>
  <p class="lead">تنظیمات زیربنایی سامانه فقط توسط مدیر سیستم انجام می‌شود.</p>

  <h3>۱۱-۱. مدیریت شاخص‌ها (KPI Master)</h3>
  <figure><div class="frame"><img src="__MASTER__" alt="مدیریت شاخص‌ها"></div>
    <figcaption>تصویر ۱۰ — تعریف/ویرایش شاخص: نام، فرایند، هدف، حد هشدار/بحرانی، وزن، اهمیت و فرمول.</figcaption></figure>
  <p>برای افزودن شاخص جدید روی <b>«+ شاخص جدید»</b> بزنید. هنگام <b>ویرایش</b>، درج <b>«دلیل تغییر»</b> الزامی است و در لاگ ثبت می‌شود.</p>

  <h3>۱۱-۲. ساختار سازمانی</h3>
  <figure><div class="frame"><img src="__ORG__" alt="ساختار سازمانی"></div>
    <figcaption>تصویر ۱۱ — درخت سازمان: شرکت ← معاونت ← فرایند ← شاخص.</figcaption></figure>

  <h3>۱۱-۳. کاربران و نقش‌ها</h3>
  <figure><div class="frame"><img src="__USERS__" alt="کاربران"></div>
    <figcaption>تصویر ۱۲ — مدیریت کاربران، نقش‌ها و تخصیص فرایند به مالکان.</figcaption></figure>

  <h3>۱۱-۴. لاگ تغییرات (حسابرسی)</h3>
  <figure><div class="frame"><img src="__AUDIT__" alt="لاگ تغییرات"></div>
    <figcaption>تصویر ۱۳ — ثبت کامل همه تغییرات شامل کاربر، زمان، مقدار قبل/بعد و دلیل تغییر.</figcaption></figure>
  <div class="note"><b>چرا لاگ مهم است؟</b>هر ویرایش شاخص یا تغییر هدف با نام کاربر و دلیل ثبت می‌شود — برای شفافیت و بازرسی.</div>

  <h3>۱۱-۵. تنظیمات عمومی</h3>
  <figure><div class="frame"><img src="__SETT__" alt="تنظیمات"></div>
    <figcaption>تصویر ۱۴ — تنظیمات: نام سازمان، سال جاری و آستانه‌های سبز/زرد.</figcaption></figure>
  <div class="eq">منطق وضعیت: تحقق ≥ <b>آستانه سبز (۰.۸۵ → ۸۵٪)</b> ⇒ مطلوب (سبز) &nbsp;|&nbsp; تحقق ≥ <b>آستانه زرد (۰.۶۰ → ۶۰٪)</b> ⇒ نیازمند توجه (زرد) &nbsp;|&nbsp; کمتر ⇒ بحرانی (قرمز)</div>
</div>

<div class="card" id="color">
  <h2>۱۲. معنی رنگ‌ها و وضعیت‌ها</h2>
  <div class="legend">
    <div><span class="dot g"></span> <b>مطلوب (سبز):</b> تحقق ≥ ۸۵٪</div>
    <div><span class="dot y"></span> <b>نیازمند توجه (زرد):</b> ۶۰٪ تا ۸۵٪</div>
    <div><span class="dot r"></span> <b>بحرانی (قرمز):</b> کمتر از ۶۰٪</div>
  </div>
  <div class="eq">مثال ضایعات: هدف ≤ ۲٪ و عملکرد واقعی = ۳٪ ⇒ تحقق کمتر از هدف ⇒ <span class="chip r">وضعیت بحرانی</span></div>
  <div class="note"><b>آستانه‌ها قابل تغییرند</b>مدیر سیستم می‌تواند آستانه‌های سبز/زرد را در تنظیمات تغییر دهد (یا در سطح تک‌تک شاخص‌ها بازنویسی کند).</div>
</div>

<div class="card" id="faq">
  <h2>۱۳. نکات و پرسش‌های متداول</h2>
  <ul>
    <li><b>چطور سال را عوض کنم؟</b> از فیلتر «سال مالی» در نوار بالا (گزینه سمت چپ نام کاربر).</li>
    <li><b>فرایند من خالی است؟</b> احتمالاً نقش شما به اشتباه تنظیم شده؛ با مدیر سیستم هماهنگ کنید.</li>
    <li><b>مقدار را اشتباه ثبت کردم؟</b> اگر هنوز تأیید نشده، آن را ویرایش کنید؛ اگر تأیید شده، از مدیر کیفیت بخواهید بازگشایی کند.</li>
    <li><b>چطور شاخص جدید اضافه کنم؟</b> فقط مدیر سیستم از بخش «مدیریت شاخص‌ها» (با درج دلیل تغییر).</li>
    <li><b>گزارش PDF/Excel کجاست؟</b> بخش «گزارش‌ها و خروجی» → دکمه‌های دانلود (مطابق سال انتخابی).</li>
    <li><b>آیا با موبایل کار می‌کند؟</b> بله، رابط کاملاً واکنش‌گرا (Responsive) است.</li>
  </ul>
  <div class="tip"><b>پیشنهاد</b>در پایان هر ماه، ابتدا همه شاخص‌های فرایند خود را ثبت و ارسال کنید، سپس در کارتابل مدیر کیفیت پیگیر تأیید آن‌ها باشید — قبل از بستن ماه مالی.</div>
</div>

<div class="footer">
  سامانه مدیریت شاخص‌های عملکرد (KPI-MS) · نسخه ۱.۰ · مستندات کاربری<br/>
  تولید شده متناسب با محیط واقعی سامانه · تمامی تصاویر از نسخه نمایشی گرفته شده است.
</div>

</div>
</body>
</html>
"""

out = HTML.replace("__CSS__", CSS)
for tok, uri in B64.items():
    out = out.replace("__" + tok + "__", uri)

with open(OUT, "w", encoding="utf-8") as f:
    f.write(out)

print("WROTE", OUT, "bytes=", len(out))
