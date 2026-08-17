"""
联合利华 Excel 合并筛选系统 — 主入口
- 登录认证（用户名 + 密码，走认证服务）
- 第一步：上传文件，分析所有 Sheet 表头 + 前10行数据
- 第二步：用户纠正表头列名 + 选择参与合并的 Sheet + 选择筛选省份
- 第三步：按列名对齐合并，筛选选中省份的数据，输出 Excel + 预览

模块拆分：
  config.py          — 配置常量、路径、认证服务地址
  state.py           — 共享可变状态（session、用户缓存、配置缓存）
  auth.py            — 认证中间件、用户管理、配置获取
  routers/auth.py    — 登录/登出/me/sync/users/rules 路由
  routers/merge.py   — 分析/处理/下载/regions/features 路由
  routers/mail.py    — 邮件读取器路由
  routers/admin.py   — 管理后台代理路由
  routers/pages.py   — HTML 页面路由
"""

import os

# 清除代理环境变量，避免打包后 httpx 走代理导致连不上认证服务
for _k in ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "http_proxy", "https_proxy"):
    os.environ.pop(_k, None)

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import config
import state
import auth
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
    """启动时从认证服务获取配置，启动邮件后台；关闭时停止邮件后台"""
    app_cfg = auth.fetch_app_config_from_auth_service()
    import time as _time
    state.APP_CONFIG_CACHE = app_cfg
    state.APP_CONFIG_CACHE_TIME = _time.time()

    mail_cfg = app_cfg.get("mail_config", {})
    if mail_cfg.get("enabled"):
        mail_cfg["output_dir"] = config.OUTPUT_DIR
        mail_cfg["processed_uids_file"] = os.path.join(config.DATA_DIR, "processed_uids.json")
        mail_reader.start_background(mail_cfg)
    yield
    mail_reader.stop_background()


# ===================== FastAPI 应用 =====================

app = FastAPI(title="Excel 合并筛选系统", lifespan=lifespan)

# 静态资源
app.mount("/static", StaticFiles(directory=_resource_path("templates/static")), name="static")

# Vue 前端构建产物
if config.USE_VUE_FRONTEND:
    app.mount("/assets", StaticFiles(directory=os.path.join(config.VUE_DIST_DIR, "assets")), name="vue-assets")

# 认证中间件
app.add_middleware(auth.AuthMiddleware)

# 注册路由
app.include_router(auth_router)
app.include_router(merge_router)
app.include_router(mail_router)
app.include_router(admin_router)
app.include_router(pages_router)


# ===================== 桌面窗口模式（pywebview） =====================

if __name__ == "__main__":
    import sys
    import uvicorn
    import threading
    import time

    # 无感升级：启动时应用待更新的版本（仅打包后生效）
    import updater
    updater.apply_pending_update()

    port = 8000
    print(f"[auth] 认证服务地址: {config.AUTH_SERVICE_URL}")

    # 桌面窗口模式
    import webview

    # 无感升级：后台静默检查并下载新版本（5 秒后执行）
    _update_status = {"checking": False, "last_result": None}

    def _silent_update_check():
        time.sleep(5)
        _update_status["checking"] = True
        try:
            result = updater.check_and_download_update()
            _update_status["last_result"] = result
            if result.get("has_update") and not result.get("error"):
                _to_version = result.get("latest", "")
                print(f"[updater] 新版本 {_to_version} 已下载，将在下次启动时自动升级")
            elif result.get("has_update") and result.get("already_downloaded"):
                print(f"[updater] 新版本已下载，等待重启应用")
        except Exception as e:
            print(f"[updater] 静默检查失败: {e}")
            _update_status["last_result"] = {"has_update": False, "error": str(e)}
        finally:
            _update_status["checking"] = False

    threading.Thread(target=_silent_update_check, daemon=True).start()

    class Api:
        """pywebview JS API — 供前端调用原生文件对话框和升级功能"""

        def _save(self, src, save_filename):
            import shutil
            if not os.path.isfile(src):
                return None
            dest = webview.windows[0].create_file_dialog(
                webview.FileDialog.SAVE,
                directory=os.path.expanduser("~"),
                save_filename=save_filename,
            )
            if not dest:
                return None
            if isinstance(dest, (tuple, list)):
                dest = dest[0]
            shutil.copy(src, dest)
            return dest

        def download_file(self, filename):
            safe = os.path.basename(filename)
            return self._save(os.path.join(config.OUTPUT_DIR, safe), safe)

        def download_latest(self):
            files = [f for f in os.listdir(config.OUTPUT_DIR) if f.endswith(".xlsx")]
            if not files:
                return None
            files.sort(key=lambda f: os.path.getmtime(os.path.join(config.OUTPUT_DIR, f)), reverse=True)
            return self._save(os.path.join(config.OUTPUT_DIR, files[0]), files[0])

        def check_update(self):
            """检查是否有新版本（不自动升级，仅返回信息）"""
            import updater
            return updater.check_and_update(auto=False)

        def do_update(self):
            """执行自动升级"""
            import updater
            return updater.check_and_update(auto=True)

        def get_version(self):
            """返回当前版本号"""
            import updater
            return updater.get_current_version()

        def get_update_status(self):
            """返回后台静默检查的状态"""
            return _update_status

        def has_pending_update(self):
            """是否有待应用的更新（下次启动时生效）"""
            import updater
            return updater.has_pending_update()

        def get_update_log(self):
            """读取更新日志"""
            try:
                log_path = os.path.join(updater._data_dir(), updater.UPDATE_LOG_FILE)
                if os.path.exists(log_path):
                    with open(log_path, "r", encoding="utf-8") as f:
                        return f.read()
            except Exception:
                pass
            return ""

    def _run_server():
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

    threading.Thread(target=_run_server, daemon=True).start()

    window = webview.create_window(
        "LX捞数据",
        f"http://127.0.0.1:{port}",
        width=1280,
        height=820,
        min_size=(900, 600),
        js_api=Api(),
    )

    # 窗口关闭时通知认证服务清除所有设备绑定
    def _on_closing():
        for token, session in list(state.SESSIONS.items()):
            username = session["username"]
            try:
                import httpx
                httpx.post(
                    f"{config.AUTH_SERVICE_URL}/logout",
                    json={"username": username},
                    headers={"X-Service-Token": config.get_service_token()},
                    timeout=3,
                )
            except Exception:
                pass

    window.events.closing += _on_closing

    webview.start()
