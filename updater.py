"""
自动升级模块：通过认证服务检查新版本并静默下载替换。
- 启动时后台静默检查 → 有新版本静默下载到临时目录 → 写入待更新标记
- 下次启动时检测到标记 → 执行替换 → 启动新版本 → 清理标记
- 用户全程无感知

跨平台支持：
- Windows: 替换脚本使用 .bat（tasklist + copy + start）
- macOS: 替换脚本使用 .sh（sleep + cp + open）
"""
import os
import sys
import json
import tempfile
import subprocess
import urllib.request
import urllib.error

# 当前版本（CI 打包时通过正则自动替换）
APP_VERSION = "v1.2.2"

# 待更新标记文件路径（与 exe/app 同目录）
PENDING_UPDATE_FILE = "pending_update.json"

# 下载配置
DOWNLOAD_TIMEOUT = 300          # 单次下载超时 5 分钟（exe 可能 50-100MB+）
DOWNLOAD_RETRY = 3             # 下载失败重试次数
DOWNLOAD_CHUNK = 65536         # 下载缓冲块大小
API_TIMEOUT = 15               # API 超时

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"


def get_current_version() -> str:
    return APP_VERSION


def _data_dir() -> str:
    """可写目录：打包后为 exe/app 所在目录，开发时为脚本所在目录"""
    if getattr(sys, "frozen", False):
        if IS_WINDOWS:
            return os.path.dirname(sys.executable)
        elif IS_MACOS:
            # PyInstaller --windowed on macOS creates .app bundle
            # sys.executable = .../LX.app/Contents/MacOS/LX
            # data dir = .../LX.app/Contents/  (writable, inside bundle)
            exe_dir = os.path.dirname(sys.executable)  # .../Contents/MacOS
            contents_dir = os.path.dirname(exe_dir)      # .../Contents
            return contents_dir
        else:
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
        if IS_WINDOWS:
            appdata = os.environ.get("APPDATA")
            base = os.path.join(appdata, "ExcelMerger") if appdata else os.path.dirname(sys.executable)
        elif IS_MACOS:
            base = _data_dir()
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


_platform_str = "macos" if IS_MACOS else "windows"


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
            f"{base_url}/update/check?platform={_platform_str}",
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
            "url": f"{base_url}/update/download?platform={_platform_str}",
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
                with open(tmp_path, "wb") as f:
                    while True:
                        chunk = resp.read(DOWNLOAD_CHUNK)
                        if not chunk:
                            break
                        f.write(chunk)
            # 原子重命名
            if os.path.exists(dest_path):
                os.remove(dest_path)
            os.rename(tmp_path, dest_path)
            print(f"[updater] 下载成功: {dest_path} (第 {attempt} 次)")
            return True
        except Exception as e:
            print(f"[updater] 下载失败 (第 {attempt}/{DOWNLOAD_RETRY} 次): {e}")
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            if attempt < DOWNLOAD_RETRY:
                import time
                time.sleep(2)
    return False


def _get_download_filename() -> str:
    """根据平台返回下载文件名"""
    if IS_MACOS:
        return "LX_new.app.zip"
    return "LX_new.exe"


def _get_download_ext() -> str:
    """根据平台返回下载文件扩展名"""
    if IS_MACOS:
        return ".zip"
    return ".exe"


def check_and_download_update() -> dict:
    """
    检查并下载更新（不立即替换，下次启动时替换）。
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
            "body": result.get("body", ""),
            "error": None,
        }

    if not result.get("has_file", False):
        return {
            "has_update": True,
            "current": current,
            "latest": latest,
            "body": result.get("body", ""),
            "error": "服务器已发布新版本但尚未上传安装包",
        }

    # 下载新版本
    temp_dir = tempfile.gettempdir()
    if IS_MACOS:
        new_file_path = os.path.join(temp_dir, "LX_new.zip")
    else:
        new_file_path = os.path.join(temp_dir, "LX_new.exe")

    if _download_file(result["url"], new_file_path):
        # 校验下载文件大小（至少 1MB，防止下到错误页面）
        file_size = os.path.getsize(new_file_path)
        if file_size < 1_000_000:
            print(f"[updater] 下载文件过小 ({file_size} bytes)，可能不是有效文件，跳过")
            try:
                os.remove(new_file_path)
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
            "new_file_path": new_file_path,
            "from_version": current,
            "to_version": latest,
            "platform": "macos" if IS_MACOS else "windows",
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


def _clear_pending():
    """删除待更新标记文件"""
    try:
        if os.path.exists(_pending_path()):
            os.remove(_pending_path())
    except Exception:
        pass


def _apply_windows_update(pending: dict) -> bool:
    """Windows 平台应用更新"""
    new_exe = pending.get("new_file_path", pending.get("new_exe_path", ""))
    if not os.path.isfile(new_exe):
        print(f"[updater] 新版本文件不存在: {new_exe}")
        _clear_pending()
        return False

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
    with open(bat_path, "w", encoding="gbk", errors="replace") as f:
        f.write(bat_content)

    _clear_pending()
    subprocess.Popen(["cmd", "/c", bat_path], creationflags=subprocess.CREATE_NO_WINDOW)
    print("[updater] 正在应用更新，即将重启...")
    os._exit(0)
    return True


def _apply_macos_update(pending: dict) -> bool:
    """macOS 平台应用更新"""
    new_zip = pending.get("new_file_path", pending.get("new_exe_path", ""))
    if not os.path.isfile(new_zip):
        print(f"[updater] 新版本文件不存在: {new_zip}")
        _clear_pending()
        return False

    if os.path.getsize(new_zip) < 1_000_000:
        print(f"[updater] 新版本文件异常（过小），跳过更新")
        try:
            os.remove(new_zip)
        except Exception:
            pass
        _clear_pending()
        return False

    # macOS: sys.executable = .../LX.app/Contents/MacOS/LX
    # app_bundle = .../LX.app
    current_exe = sys.executable
    contents_dir = os.path.dirname(os.path.dirname(current_exe))  # .../Contents
    app_bundle = os.path.dirname(contents_dir)                      # .../LX.app
    app_dir = os.path.dirname(app_bundle)                           # parent dir
    backup_bundle = app_bundle + ".bak"

    pid = os.getpid()
    temp_dir = tempfile.gettempdir()
    sh_path = os.path.join(temp_dir, "LX_apply_update.sh")

    sh_content = f"""#!/bin/bash
# LX macOS 自动更新脚本
echo "[LX更新] 正在等待应用退出..."
while kill -0 {pid} 2>/dev/null; do
    sleep 1
done
echo "[LX更新] 正在备份旧版本..."
rm -rf "{backup_bundle}"
cp -R "{app_bundle}" "{backup_bundle}"
echo "[LX更新] 正在解压新版本..."
# 解压 zip 到临时目录
UNZIP_DIR="{temp_dir}/LX_update_extract"
rm -rf "$UNZIP_DIR"
mkdir -p "$UNZIP_DIR"
cd "$UNZIP_DIR"
unzip -o "{new_zip}" -d "$UNZIP_DIR" 2>/dev/null
# 查找解压出来的 .app
NEW_APP=$(find "$UNZIP_DIR" -maxdepth 2 -name "*.app" -type d | head -1)
if [ -z "$NEW_APP" ]; then
    echo "[LX更新] 未找到 .app，恢复旧版本"
    rm -rf "$UNZIP_DIR"
    open "{app_bundle}"
    exit 1
fi
echo "[LX更新] 正在安装新版本..."
rm -rf "{app_bundle}"
cp -R "$NEW_APP" "{app_bundle}"
# 清理
rm -rf "$UNZIP_DIR"
rm -f "{new_zip}"
rm -f "{_pending_path()}"
echo "[LX更新] 启动新版本..."
open "{app_bundle}"
# 清理备份和脚本
sleep 3
rm -rf "{backup_bundle}"
rm -f "$0"
"""
    with open(sh_path, "w", encoding="utf-8") as f:
        f.write(sh_content)
    os.chmod(sh_path, 0o755)

    _clear_pending()
    subprocess.Popen(["/bin/bash", sh_path])
    print("[updater] 正在应用更新，即将重启...")
    os._exit(0)
    return True


def apply_pending_update() -> bool:
    """
    启动时调用：如果存在待更新标记，执行替换并重启。
    1. 读取 pending_update.json
    2. 校验新文件是否存在且有效
    3. 生成平台对应的替换脚本
    4. 启动脚本并退出当前进程

    仅 PyInstaller 打包后生效。
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

    if IS_WINDOWS:
        return _apply_windows_update(pending)
    elif IS_MACOS:
        return _apply_macos_update(pending)
    else:
        print(f"[updater] 不支持的平台: {sys.platform}")
        _clear_pending()
        return False


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
