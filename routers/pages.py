from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

import config
from merger import _resource_path

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
async def login_page():
    if config.USE_VUE_FRONTEND:
        return config.serve_vue_index()
    with open(_resource_path("templates/login.html"), "r", encoding="utf-8") as f:
        return f.read()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if config.USE_VUE_FRONTEND:
        return config.serve_vue_index()
    with open(_resource_path("templates/index.html"), "r", encoding="utf-8") as f:
        return f.read()


@router.get("/mail", response_class=HTMLResponse)
async def mail_page(request: Request):
    # 邮件捞取已整合为主页 SPA 面板，重定向到首页
    return RedirectResponse("/#mail", status_code=302)


@router.get("/mail/results", response_class=HTMLResponse)
async def mail_results_page(request: Request):
    # 处理结果已整合为主页 SPA 面板，重定向到首页
    return RedirectResponse("/#results", status_code=302)
