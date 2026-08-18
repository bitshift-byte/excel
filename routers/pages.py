from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import config
from merger import _resource_path

router = APIRouter()

NO_CACHE_HEADERS = {"Cache-Control": "no-cache, no-store, must-revalidate"}


def _serve_spa():
    """返回 Vue SPA 的 index.html"""
    if config.USE_VUE_FRONTEND:
        return HTMLResponse(content=config.serve_vue_index(), headers=NO_CACHE_HEADERS)
    with open(_resource_path("templates/index.html"), "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read(), headers=NO_CACHE_HEADERS)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return _serve_spa()


# 旧路径重定向到 hash 路由，保持 URL 干净
@router.get("/login", response_class=HTMLResponse)
async def login_page():
    # 直接返回 SPA，让 Vue Router 处理 /login 路由
    return _serve_spa()


@router.get("/mail", response_class=HTMLResponse)
async def mail_page():
    return RedirectResponse("/#/mail", status_code=302)


@router.get("/mail/results", response_class=HTMLResponse)
async def mail_results_page():
    return RedirectResponse("/#/mail", status_code=302)


@router.get("/admin", response_class=HTMLResponse)
async def admin_page():
    return RedirectResponse("/#/admin", status_code=302)


@router.get("/rules", response_class=HTMLResponse)
async def rules_page():
    return RedirectResponse("/#/rules", status_code=302)


@router.get("/mail-merge", response_class=HTMLResponse)
async def mail_merge_page():
    return RedirectResponse("/#/mail-merge", status_code=302)
