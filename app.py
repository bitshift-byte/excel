"""
联合利华 Excel 合并筛选系统 — 主入口（Web 版）
- 登录认证（用户名 + 密码，SQLite 数据库）
- 第一步：上传文件，分析所有 Sheet 表头 + 前10行数据
- 第二步：用户纠正表头列名 + 选择参与合并的 Sheet + 选择筛选省份
- 第三步：按列名对齐合并，筛选选中省份的数据，输出 Excel + 预览

模块拆分：
  config.py          — 配置常量、路径
  state.py           — 共享可变状态（session、用户缓存、配置缓存）
  auth.py            — 认证中间件、用户管理、配置获取
  database.py        — SQLite 数据库操作
  routers/auth.py    — 登录/登出/me/sync/users/rules 路由
  routers/merge.py   — 分析/处理/下载/regions/features 路由
  routers/mail.py    — 邮件读取器路由
  routers/admin.py   — 管理后台路由（直接调用 database）
  routers/pages.py   — HTML 页面路由
"""

import os

# 清除代理环境变量
for _k in ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "http_proxy", "https_proxy"):
    os.environ.pop(_k, None)

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import config
import state
import auth
import database
import mail_reader
from merger import _resource_path
from routers.auth import router as auth_router
from routers.merge import router as merge_router
from routers.mail import router as mail_router
from routers.admin import router as admin_router
from routers.pages import router as pages_router


# ===================== 生命周期 =====================


@asynccontextmanager
async def lifespan(app):
    """启动时初始化数据库、加载配置、启动邮件后台；关闭时停止邮件后台"""
    # 初始化数据库
    database.init_db()
    print("[app] 数据库已初始化")

    # 加载应用配置
    app_cfg = auth.fetch_app_config()
    import time as _time
    state.APP_CONFIG_CACHE = app_cfg
    state.APP_CONFIG_CACHE_TIME = _time.time()

    # 刷新用户缓存
    auth.refresh_users()

    # 启动邮件后台
    mail_cfg = app_cfg.get("mail_config", {})
    if mail_cfg.get("enabled"):
        mail_cfg["output_dir"] = config.OUTPUT_DIR
        mail_cfg["processed_uids_file"] = None  # 使用数据库存储
        mail_reader.start_background(mail_cfg)
    yield
    mail_reader.stop_background()


# ===================== FastAPI 应用 =====================

app = FastAPI(title="Excel 合并筛选系统", lifespan=lifespan)

# 静态资源
_static_dir = _resource_path("templates/static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")

# Vue 前端构建产物
if config.USE_VUE_FRONTEND:
    _vue_assets = os.path.join(config.VUE_DIST_DIR, "assets")
    if os.path.isdir(_vue_assets):
        app.mount("/assets", StaticFiles(directory=_vue_assets), name="vue-assets")

# 认证中间件
app.add_middleware(auth.AuthMiddleware)

# 注册 AdminError 异常处理
from routers.admin import AdminError
from fastapi.responses import JSONResponse as _JR

@app.exception_handler(AdminError)
async def _admin_error_handler(request, exc: AdminError):
    return _JR({"status": "error", "detail": exc.detail}, status_code=exc.status_code)

# 注册路由
app.include_router(auth_router)
app.include_router(merge_router)
app.include_router(mail_router)
app.include_router(admin_router)
app.include_router(pages_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
