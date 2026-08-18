from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import config
from merger import _resource_path

router = APIRouter()


def _serve_spa():
    """返回 Vue SPA 的 index.html"""
    if config.USE_VUE_FRONTEND:
        return config.serve_vue_index()
    with open(_resource_path("templates/index.html"), "r", encoding="utf-8") as f:
        return f.read()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return _serve_spa()


# 旧路径重定向到 hash 路由，保持 URL 干净
@router.get("/login", response_class=HTMLResponse)
async def login_page():
    # 重定向到 /#/login，让 Vue 路由处理
    return RedirectResponse("/#/login", status_code=302)


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
