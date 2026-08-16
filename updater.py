"""
自动升级模块：通过认证服务检查新版本并静默下载替换。
- 启动时后台静默检查 → 有新版本静默下载到临时目录 → 写入待更新标记
- 下次启动时检测到标记 → 执行替换 → 启动新版本 → 清理标记
- 用户全程无感知

Windows 专用：替换脚本使用 .bat（tasklist + copy + start）
"""
import os
import sys
import json
import tempfile
import subprocess
import urllib.request
import urllib.error

# 当前版本（CI 打包时通过正则自动替换）
APP_VERSION = "v1.0.0"

# 待更新标记文件路径（与 exe 同目录）
PENDING_UPDATE_FILE = "pending_update.json"

# 下载配置
DOWNLOAD_TIMEOUT = 300          # 单次下载超时 5 分钟（exe 可能 50-100MB+）
DOWNLOAD_RETRY = 3             # 下载失败重试次数
DOWNLOAD_CHUNK = 65536         # 下载缓冲块大小
API_TIMEOUT = 15               # API 超时


def get_current_version() -> str:
    return APP_VERSION


def _data_dir() -> str:
    """可写目录：打包后为 exe 所在目录，开发时为脚本所在目录"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _pending_path() -> str:
    return os.path.join(_data_dir(), PENDING_UPDATE_FILE)


def _get_auth_service_url() -> str:
    """读取认证服务地址（与 app.py 的 _load_auth_service_url 逻辑一致）"""
    # 1. 环境变量
    url = os.environ.get("AUTH_SERVICE_URL")
    if url:
        return url.rstrip("/")
    # 2. 配置文件
    url_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "auth_service_url.txt")
    if getattr(sys, "frozen", False):
        if os.name == "nt":
            appdata = os.environ.get("APPDATA")
            base = os.path.join(appdata, "ExcelMerger") if appdata else os.path.dirname(sys.executable)
        else:
            base = os.path.dirname(sys.executable)
        url_file = os.path.join(base, "data", "auth_service_url.txt")
    try:
        if os.path.exists(url_file):
            with open(url_file, "r", encoding="utf-8") as f:
                url = f.read().strip()
                if url:
                    return url.rstrip("/")
    except Exception:
        pass
    # 3. 默认值
    return "http://18.177.82.156:8001"


def _get_service_token() -> str:
    """读取服务间通信密钥"""
    return os.environ.get("SERVICE_TOKEN", "lx-internal-service-token")


def check_latest_version() -> dict:
    """
    向认证服务查询最新版本信息。
    返回 {"tag": "v1.1.0", "url": "...", "body": "...", "has_file": True}
    失败返回 {"error": "..."}
    """
    base_url = _get_auth_service_url()
    token = _get_service_token()
    try:
        req = urllib.request.Request(
            f"{base_url}/update/check",
            headers={
                "X-Service-Token": token,
            },
        )
        with urllib.request.urlopen(req, timeout=API_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        version = data.get("version", "")
        if not version:
            return {"error": "服务器未设置版本号"}
        return {
            "tag": version,
            "url": f"{base_url}/update/download",
            "body": data.get("notes", ""),
            "has_file": data.get("has_file", False),
        }
    except urllib.error.HTTPError as e:
        return {"error": f"认证服务错误: HTTP {e.code}"}
    except urllib.error.URLError as e:
        return {"error": f"网络错误: {e.reason}"}
    except Exception as e:
        return {"error": f"检查更新失败: {e}"}


def is_newer(latest_tag: str, current_tag: str) -> bool:
    """
    比较版本号，latest > current 返回 True。
    支持语义版本格式：v1.2.3, 1.2.3, v1.2.3-beta 等。
    预发布版本（含 -）视为低于同号正式版。
    """
    try:
        def parse(tag):
            # 去掉 v/V 前缀，取 - 之前的数字部分
            clean = tag.strip().lstrip("vV")
            pre_release = None
            if "-" in clean:
                clean, pre_release = clean.split("-", 1)
            nums = clean.split(".")
            parsed = tuple(int(n) for n in nums if n.isdigit())
            # 正式版 (pre_release=None) 排在预发布之前
            return (parsed, 0 if pre_release is None else -1)
        return parse(latest_tag) > parse(current_tag)
    except Exception:
        return False


def _download_file(url: str, dest_path: str) -> bool:
    """
    下载文件到指定路径，支持重试。
    使用临时文件写入，成功后原子重命名，避免下载到一半的损坏文件。
    """
    token = _get_service_token()
    for attempt in range(1, DOWNLOAD_RETRY + 1):
        tmp_path = dest_path + ".downloading"
        try:
            req = urllib.request.Request(url, headers={
                "X-Service-Token": token,
            })
            with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
                # 获取文件总大小（用于将来扩展进度条）
                total = resp.getheader("Content-Length")
                total = int(total) if total else None
                with open(tmp_path, "wb") as f:
                    downloaded = 0
                    while True:
                        data = resp.read(DOWNLOAD_CHUNK)
                        if not data:
                            break
                        f.write(data)
                        downloaded += len(data)
            # 下载完成，原子重命名
            if os.path.exists(dest_path):
                os.remove(dest_path)
            os.rename(tmp_path, dest_path)
            print(f"[updater] 下载成功 ({attempt}/{DOWNLOAD_RETRY} 次): {dest_path}")
            return True
        except Exception as e:
            print(f"[updater] 下载失败 (第 {attempt}/{DOWNLOAD_RETRY} 次): {e}")
            # 清理临时文件
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            if attempt < DOWNLOAD_RETRY:
                import time
                time.sleep(2 * attempt)  # 指数退避
    return False


def check_and_download_update() -> dict:
    """
    静默检查并下载新版本（不执行替换）。
    有新版本 → 下载到临时目录 → 写入 pending_update.json 标记 → 返回结果。
    下次启动时由 apply_pending_update() 执行替换。
    """
    current = get_current_version()
    result = check_latest_version()
    if "error" in result:
        return {"has_update": False, "current": current, "error": result["error"]}

    latest = result["tag"]
    has_update = is_newer(latest, current)

    if not has_update:
        return {
            "has_update": False,
            "current": current,
            "latest": latest,
            "error": None,
        }

    if not result.get("has_file"):
        return {
            "has_update": True,
            "current": current,
            "latest": latest,
            "body": result.get("body", ""),
            "error": "新版本已发布但服务器上暂无安装包",
        }

    # 下载新 exe 到临时目录
    temp_dir = tempfile.gettempdir()
    new_exe_path = os.path.join(temp_dir, "LX_new.exe")
    if _download_file(result["url"], new_exe_path):
        # 校验下载文件大小（至少 1MB，防止下到错误页面）
        file_size = os.path.getsize(new_exe_path)
        if file_size < 1_000_000:
            print(f"[updater] 下载文件过小 ({file_size} bytes)，可能不是有效 exe，跳过")
            try:
                os.remove(new_exe_path)
            except Exception:
                pass
            return {
                "has_update": True,
                "current": current,
                "latest": latest,
                "body": result.get("body", ""),
                "error": "下载文件异常，请稍后再试",
            }
        # 写入待更新标记
        pending = {
            "new_exe_path": new_exe_path,
            "from_version": current,
            "to_version": latest,
        }
        with open(_pending_path(), "w", encoding="utf-8") as f:
            json.dump(pending, f)
        print(f"[updater] 新版本 {latest} 已下载，下次启动时自动升级")
    else:
        print("[updater] 下载失败，跳过本次升级")

    return {
        "has_update": has_update,
        "current": current,
        "latest": latest,
        "body": result.get("body", ""),
        "error": None,
    }


def has_pending_update() -> bool:
    """检查是否存在待应用的更新"""
    return os.path.exists(_pending_path())


def apply_pending_update() -> bool:
    """
    启动时调用：如果存在待更新标记，执行替换并重启。
    1. 读取 pending_update.json
    2. 校验新 exe 文件是否存在且有效
    3. 生成 .bat 替换脚本：等待旧进程退出 → 备份 → 替换 → 启动 → 清理
    4. 启动脚本并退出当前进程

    仅 Windows + PyInstaller 打包后生效。
    """
    if not getattr(sys, "frozen", False):
        return False

    if not has_pending_update():
        return False

    try:
        with open(_pending_path(), "r", encoding="utf-8") as f:
            pending = json.load(f)
    except Exception as e:
        print(f"[updater] 读取更新标记失败: {e}")
        _clear_pending()
        return False

    new_exe = pending.get("new_exe_path", "")
    if not os.path.isfile(new_exe):
        print(f"[updater] 新版本文件不存在: {new_exe}")
        _clear_pending()
        return False

    # 校验文件大小（至少 1MB）
    if os.path.getsize(new_exe) < 1_000_000:
        print(f"[updater] 新版本文件异常（过小），跳过更新")
        try:
            os.remove(new_exe)
        except Exception:
            pass
        _clear_pending()
        return False

    current_exe = sys.executable
    backup_exe = current_exe + ".bak"

    # 生成替换脚本：等待旧进程退出 → 备份 → 替换 → 启动 → 清理
    temp_dir = tempfile.gettempdir()
    bat_path = os.path.join(temp_dir, "LX_apply_update.bat")
    pid = os.getpid()
    bat_content = f"""@echo off
chcp 65001 >nul 2>&1
echo [LX更新] 正在等待应用退出...
:wait
tasklist /fi "pid eq {pid}" 2>nul | find "{pid}" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait
)
echo [LX更新] 正在备份旧版本...
copy /y "{current_exe}" "{backup_exe}" >nul 2>&1
echo [LX更新] 正在安装新版本...
copy /y "{new_exe}" "{current_exe}" >nul 2>&1
if errorlevel 1 (
    echo [LX更新] 安装失败，恢复旧版本...
    copy /y "{backup_exe}" "{current_exe}" >nul 2>&1
    start "" "{current_exe}"
    goto cleanup
)
del /f /q "{new_exe}" >nul 2>&1
del /f /q "{_pending_path()}" >nul 2>&1
echo [LX更新] 启动新版本...
start "" "{current_exe}"
:cleanup
timeout /t 3 /nobreak >nul
del /f /q "{backup_exe}" >nul 2>&1
del /f /q "%~f0" >nul 2>&1
"""
    with open(bat_path, "w", encoding="ascii") as f:
        f.write(bat_content)

    # 清除标记（避免循环）
    _clear_pending()

    # 启动替换脚本并退出
    subprocess.Popen(["cmd", "/c", bat_path], creationflags=subprocess.CREATE_NO_WINDOW)
    print("[updater] 正在应用更新，即将重启...")
    os._exit(0)
    return True


def _clear_pending():
    """删除待更新标记文件"""
    try:
        if os.path.exists(_pending_path()):
            os.remove(_pending_path())
    except Exception:
        pass


def check_and_update(auto: bool = False) -> dict:
    """
    兼容旧接口：检查更新。
    auto=False: 仅检查，不下载
    auto=True: 检查并下载（不立即替换，下次启动时替换）
    """
    if auto:
        return check_and_download_update()
    else:
        current = get_current_version()
        result = check_latest_version()
        if "error" in result:
            return {"has_update": False, "current": current, "error": result["error"]}
        latest = result["tag"]
        return {
            "has_update": is_newer(latest, current),
            "current": current,
            "latest": latest,
            "body": result.get("body", ""),
            "has_file": result.get("has_file", False),
            "error": None,
        }
