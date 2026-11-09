# -*- coding: utf-8 -*-
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from .database import Base, engine, SessionLocal
from . import models
from .config import FRONTEND_DIR
from .routers import (auth, users, org, kpis, entries, dashboard, reports,
                      strategy, holding)

app = FastAPI(title="سامانه مدیریت و پایش شاخص‌های کلیدی عملکرد (KPI-MS)",
              version="1.1.0",
              description="Enterprise KPI Management & Monitoring System — Arena.ai prototype")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"], allow_credentials=False)

for r in [auth, users, org, kpis, entries, dashboard, reports, strategy, holding]:
    app.include_router(r.router)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    # auto-seed if empty
    db = SessionLocal()
    try:
        if db.query(models.KPI).count() == 0:
            from .seed import run_seed
            run_seed()
    finally:
        db.close()


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---- serve frontend (SPA) ----
if os.path.isdir(FRONTEND_DIR):
    app.mount("/vendor", StaticFiles(directory=os.path.join(FRONTEND_DIR, "vendor")), name="vendor")
    app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")

    @app.get("/")
    def index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    @app.get("/manifest.webmanifest")
    def manifest():
        return FileResponse(os.path.join(FRONTEND_DIR, "manifest.webmanifest"),
                            media_type="application/manifest+json")

    @app.get("/sw.js")
    def service_worker():
        # service worker must be served from the root scope
        return FileResponse(os.path.join(FRONTEND_DIR, "sw.js"),
                            media_type="application/javascript",
                            headers={"Cache-Control": "no-cache"})

    @app.exception_handler(404)
    async def spa_fallback(request, exc):
        # let API 404s be JSON; serve SPA for everything else
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": "یافت نشد"}, status_code=404)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
