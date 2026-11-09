import os, base64, json
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8000"
OUT = "/home/user/kpi-system/docs/img"
os.makedirs(OUT, exist_ok=True)
PW = "Passw0rd!"

SHOTS = []  # (filename, role, nav_hash, action_fn_name)

def login(page, user):
    page.goto(f"{BASE}/#/login", wait_until="networkidle")
    page.wait_for_selector("input[placeholder='admin']")
    page.fill("input[placeholder='admin']", user)
    page.fill("input[type='password']", PW)
    page.click("button:has-text('ورود به سامانه')")
    page.wait_for_selector(".sidebar", timeout=15000)
    page.wait_for_timeout(800)

def go(page, h):
    page.evaluate(f"location.hash='{h}'")
    page.wait_for_timeout(1100)

def clip(p, name, jpeg=True):
    path = os.path.join(OUT, name)
    if jpeg:
        p.screenshot(path=path, full_page=False, type="jpeg", quality=82)
    else:
        p.screenshot(path=path, full_page=False)
    print("captured", name)

def verify_approvals():
    pass

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox"])
    vw = {"viewport": {"width": 1440, "height": 860}, "device_scale_factor": 1}

    # 1) Login
    pg = b.new_page(**vw)
    pg.goto(f"{BASE}/#/login", wait_until="networkidle")
    pg.wait_for_selector(".login-card")
    pg.wait_for_timeout(500)
    clip(pg, "01-login.jpg")
    pg.close()

    # 2) Dashboard (executive / ceo)
    pg = b.new_page(**vw)
    login(pg, "ceo")
    go(pg, "#/dashboard")
    pg.wait_for_selector(".stat")
    pg.wait_for_timeout(1200)
    clip(pg, "02-dashboard.jpg")
    pg.close()

    # 3) Processes
    pg = b.new_page(**vw)
    login(pg, "ceo")
    go(pg, "#/processes")
    pg.wait_for_selector(".gauge")
    pg.wait_for_timeout(1000)
    clip(pg, "03-processes.jpg")
    pg.close()

    # 4) KPIs list
    pg = b.new_page(**vw)
    login(pg, "ceo")
    go(pg, "#/kpis")
    pg.wait_for_selector("table.tbl")
    pg.wait_for_timeout(1000)
    clip(pg, "04-kpis.jpg")
    pg.close()

    # 5) KPI detail modal
    pg = b.new_page(**vw)
    login(pg, "ceo")
    go(pg, "#/kpis")
    pg.wait_for_selector("table.tbl a")
    pg.locator("a:has-text('روند و جزئیات')").first.click()
    pg.wait_for_selector(".modal canvas", timeout=15000)
    pg.wait_for_timeout(1400)
    clip(pg, "05-kpi-detail.jpg")
    pg.close()

    # 6) Data entry (process owner)
    pg = b.new_page(**vw)
    login(pg, "owner_pln")
    go(pg, "#/entry")
    pg.wait_for_selector("table.tbl")
    pg.wait_for_timeout(900)
    clip(pg, "06-dataentry.jpg")
    pg.close()

    # 7) Data entry form modal (owner) + submit a value to create a pending item
    pg = b.new_page(**vw)
    login(pg, "owner_pln")
    go(pg, "#/entry")
    pg.wait_for_selector("table.tbl .btn-primary")
    pg.locator("table.tbl .btn-primary").first.click()
    pg.wait_for_selector(".modal input[type='number']", timeout=15000)
    pg.wait_for_timeout(700)
    pg.fill(".modal input[type='number']", "88")
    pg.wait_for_timeout(400)
    clip(pg, "07-entry-form.jpg")
    # submit to create a pending approval
    btn = pg.locator(".modal button:has-text('ذخیره و ارسال')")
    if btn.count():
        btn.first.click()
        pg.wait_for_timeout(1200)
    pg.close()

    # 8) Approvals inbox (quality) — should now contain the submitted item
    pg = b.new_page(**vw)
    login(pg, "quality")
    go(pg, "#/approvals")
    pg.wait_for_timeout(1500)
    try:
        rows = pg.locator("table.tbl tbody tr").count()
        print("approvals inbox rows:", rows)
    except Exception as e:
        print("approvals check err", e)
    clip(pg, "08-approvals.jpg")
    pg.close()

    # 9) KPI Master (admin)
    pg = b.new_page(**vw)
    login(pg, "admin")
    go(pg, "#/master")
    pg.wait_for_selector("table.tbl")
    pg.wait_for_timeout(900)
    clip(pg, "09-master.jpg")
    pg.close()

    # 10) Org structure (admin)
    pg = b.new_page(**vw)
    login(pg, "admin")
    go(pg, "#/org")
    pg.wait_for_selector(".tree")
    pg.wait_for_timeout(900)
    clip(pg, "10-org.jpg")
    pg.close()

    # 11) Users (admin)
    pg = b.new_page(**vw)
    login(pg, "admin")
    go(pg, "#/users")
    pg.wait_for_selector("table.tbl")
    pg.wait_for_timeout(900)
    clip(pg, "11-users.jpg")
    pg.close()

    # 12) Audit log (admin)
    pg = b.new_page(**vw)
    login(pg, "admin")
    go(pg, "#/audit")
    pg.wait_for_selector("table.tbl")
    pg.wait_for_timeout(900)
    clip(pg, "12-audit.jpg")
    pg.close()

    # 13) Settings (admin)
    pg = b.new_page(**vw)
    login(pg, "admin")
    go(pg, "#/settings")
    pg.wait_for_selector(".form-grid")
    pg.wait_for_timeout(900)
    clip(pg, "13-settings.jpg")
    pg.close()

    # 14) Reports (ceo)
    pg = b.new_page(**vw)
    login(pg, "ceo")
    go(pg, "#/reports")
    pg.wait_for_selector("button:has-text('دانلود')")
    pg.wait_for_timeout(900)
    clip(pg, "14-reports.jpg")
    pg.close()

    b.close()

print("DONE")
