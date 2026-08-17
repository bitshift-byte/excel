"""
自动升级模块：通过认证服务检查新版本并静默下载替换。

流程：
1. 启动时检查 pending_update.json → 存在则执行替换 → 重启新版本
2. 后台静默检查 /update/check → 有新版本则下载到临时目录
3. 校验 SHA256 哈希 → 写入待更新标记
4. 下次启动时检测到标记 → 执行替换脚本 → 启动新版本 → 清理标记

安全机制：
- SHA256 哈希校验确保下载文件完整
- 替换前备份旧版本，失败自动回滚
- 下载使用临时文件+原子重命名，避免半截文件
- 指数退避重试（3次）
- 代理环境变量清除，避免代理干扰

跨平台支持：
- Windows: .bat 脚本（tasklist + copy + start）
- macOS: .sh 脚本（sleep + cp + open）
"""
import os
import sys
import json
import time
import hashlib
import shutil
import tempfile
import subprocess
import urllib.request
import urllib.error

# 当前版本（CI 打包时通过正则自动替换）
APP_VERSION = "v1.3.0"

# 文件路径
PENDING_UPDATE_FILE = "pending_update.json"
UPDATE_LOG_FILE = "update.log"
MAX_UPDATE_ATTEMPTS = 3  # 最多尝试应用更新次数，超过则放弃并清理

# 下载配置
DOWNLOAD_TIMEOUT = 600          # 单次下载超时 10 分钟
DOWNLOAD_RETRY = 3             # 下载失败重试次数
DOWNLOAD_CHUNK = 131072        # 下载缓冲块大小 128KB
API_TIMEOUT = 15               # API 超时

IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"

_platform_str = "macos" if IS_MACOS else "windows"


# ===================== 日志 =====================

def _log(msg: str):
    """写日志到文件和 stdout"""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(f"[updater] {msg}")
    try:
        log_path = os.path.join(_data_dir(), UPDATE_LOG_FILE)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        # 限制日志大小 100KB
        if os.path.getsize(log_path) > 100 * 1024:
            with open(log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            with open(log_path, "w", encoding="utf-8") as f:
                f.writelines(lines[-50:])
    except Exception:
        pass


# ===================== 路径工具 =====================

def get_current_version() -> str:
    return APP_VERSION


def _data_dir() -> str:
    """可写目录：打包后为 exe/app 所在目录，开发时为脚本所在目录"""
    if getattr(sys, "frozen", False):
        if IS_WINDOWS:
            return os.path.dirname(sys.executable)
        elif IS_MACOS:
            exe_dir = os.path.dirname(sys.executable)  # .../Contents/MacOS
            contents_dir = os.path.dirname(exe_dir)      # .../Contents
            return contents_dir
        else:
            return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _pending_path() -> str:
    return os.path.join(_data_dir(), PENDING_UPDATE_FILE)


# ===================== 代理清除 =====================

def _clear_proxy_env():
    """清除代理环境变量，避免下载被代理拦截"""
    for key in ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY",
                "all_proxy", "http_proxy", "https_proxy"):
        os.environ.pop(key, None)


# ===================== 认证服务地址 =====================

def _get_auth_service_url() -> str:
    """读取认证服务地址"""
    url = os.environ.get("AUTH_SERVICE_URL")
    if url:
        return url.rstrip("/")
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
    return "http://18.177.82.156:8001"


def _get_service_token() -> str:
    """读取服务间通信密钥"""
    return os.environ.get("SERVICE_TOKEN", "lx-internal-service-token")


# ===================== 版本检查 =====================

def check_latest_version() -> dict:
    """
    向认证服务查询最新版本信息。
    返回 {"tag": "v1.1.0", "url": "...", "body": "...", "has_file": True, "sha256": "...", "size": 12345}
    失败返回 {"error": "..."}
    """
    _clear_proxy_env()
    base_url = _get_auth_service_url()
    token = _get_service_token()
    try:
        req = urllib.request.Request(
            f"{base_url}/update/check?platform={_platform_str}",
            headers={"X-Service-Token": token},
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
            "sha256": data.get("sha256", ""),
            "size": data.get("size", 0),
        }
    except urllib.error.HTTPError as e:
        _log(f"检查更新 HTTP 错误: {e.code}")
        return {"error": f"认证服务错误: HTTP {e.code}"}
    except urllib.error.URLError as e:
        _log(f"检查更新网络错误: {e.reason}")
        return {"error": f"网络错误: {e.reason}"}
    except Exception as e:
        _log(f"检查更新失败: {e}")
        return {"error": f"检查更新失败: {e}"}


def is_newer(latest_tag: str, current_tag: str) -> bool:
    """
    比较版本号，latest > current 返回 True。
    支持语义版本格式：v1.2.3, 1.2.3, v1.2.3-beta 等。
    """
    try:
        def parse(tag):
            clean = tag.strip().lstrip("vV")
            pre_release = None
            if "-" in clean:
                clean, pre_release = clean.split("-", 1)
            nums = clean.split(".")
            parsed = tuple(int(n) for n in nums if n.isdigit())
            return (parsed, 0 if pre_release is None else -1)
        return parse(latest_tag) > parse(current_tag)
    except Exception:
        return False


# ===================== SHA256 校验 =====================

def _compute_sha256(file_path: str) -> str:
    """计算文件的 SHA256 哈希"""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(DOWNLOAD_CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _verify_file(file_path: str, expected_sha256: str, expected_size: int = 0) -> bool:
    """校验文件：大小 + SHA256"""
    if not os.path.exists(file_path):
        return False
    actual_size = os.path.getsize(file_path)
    if actual_size < 1_000_000:
        _log(f"文件过小: {actual_size} bytes")
        return False
    if expected_size > 0 and actual_size != expected_size:
        _log(f"文件大小不匹配: 期望 {expected_size}, 实际 {actual_size}")
        return False
    if expected_sha256:
        actual_hash = _compute_sha256(file_path)
        if actual_hash != expected_sha256:
            _log(f"SHA256 校验失败: 期望 {expected_sha256[:16]}..., 实际 {actual_hash[:16]}...")
            return False
        _log("SHA256 校验通过")
    return True


# ===================== 下载 =====================

def _download_file(url: str, dest_path: str, expected_sha256: str = "", expected_size: int = 0) -> bool:
    """
    下载文件到指定路径，支持重试（指数退避）。
    使用临时文件写入，成功后原子重命名。
    下载后进行 SHA256 校验。
    """
    _clear_proxy_env()
    token = _get_service_token()

    for attempt in range(1, DOWNLOAD_RETRY + 1):
        tmp_path = dest_path + ".downloading"
        try:
            _log(f"开始下载 (第 {attempt}/{DOWNLOAD_RETRY} 次): {url}")
            req = urllib.request.Request(url, headers={
                "X-Service-Token": token,
            })
            with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                with open(tmp_path, "wb") as f:
                    while True:
                        chunk = resp.read(DOWNLOAD_CHUNK)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0 and downloaded % (DOWNLOAD_CHUNK * 20) == 0:
                            pct = round(downloaded / total * 100)
                            _log(f"下载进度: {pct}% ({downloaded // 1024}KB / {total // 1024}KB)")

            _log(f"下载完成: {downloaded} bytes")

            # 校验下载文件
            if not _verify_file(tmp_path, expected_sha256, expected_size or total):
                _log("文件校验失败，删除临时文件")
                os.remove(tmp_path)
                if attempt < DOWNLOAD_RETRY:
                    wait = 2 ** attempt  # 指数退避: 2s, 4s, 8s
                    _log(f"等待 {wait}s 后重试...")
                    time.sleep(wait)
                continue

            # 原子重命名
            if os.path.exists(dest_path):
                os.remove(dest_path)
            os.rename(tmp_path, dest_path)
            _log(f"文件已保存: {dest_path}")
            return True

        except Exception as e:
            _log(f"下载失败 (第 {attempt}/{DOWNLOAD_RETRY} 次): {e}")
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
            if attempt < DOWNLOAD_RETRY:
                wait = 2 ** attempt
                _log(f"等待 {wait}s 后重试...")
                time.sleep(wait)

    _log("所有下载尝试均失败")
    return False


# ===================== 待更新标记 =====================

def has_pending_update() -> bool:
    """检查是否存在待应用的更新"""
    return os.path.exists(_pending_path())


def _clear_pending():
    """删除待更新标记文件"""
    try:
        if os.path.exists(_pending_path()):
            os.remove(_pending_path())
            _log("已清除待更新标记")
    except Exception as e:
        _log(f"清除待更新标记失败: {e}")


def _read_pending() -> dict:
    """读取待更新标记"""
    try:
        with open(_pending_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        _log(f"读取待更新标记失败: {e}")
        return {}


def _write_pending(info: dict):
    """写入待更新标记"""
    with open(_pending_path(), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    _log(f"已写入待更新标记: {info.get('to_version', '?')}")


# ===================== 检查并下载 =====================

def check_and_download_update() -> dict:
    """
    检查并下载更新（不立即替换，下次启动时替换）。
    """
    _clear_proxy_env()
    current = get_current_version()
    result = check_latest_version()

    if "error" in result:
        return {"has_update": False, "current": current, "error": result["error"]}

    latest = result["tag"]
    has_update = is_newer(latest, current)

    if not has_update:
        _log(f"当前版本 {current} 已是最新")
        return {
            "has_update": False,
            "current": current,
            "latest": latest,
            "body": result.get("body", ""),
            "error": None,
        }

    _log(f"发现新版本: {latest} (当前: {current})")

    if not result.get("has_file", False):
        return {
            "has_update": True,
            "current": current,
            "latest": latest,
            "body": result.get("body", ""),
            "error": "服务器已发布新版本但尚未上传安装包",
        }

    # 检查是否已经下载过同版本（避免重复下载）
    if has_pending_update():
        pending = _read_pending()
        if pending.get("to_version") == latest:
            _log(f"版本 {latest} 已下载，等待下次启动应用")
            return {
                "has_update": True,
                "current": current,
                "latest": latest,
                "body": result.get("body", ""),
                "error": None,
                "already_downloaded": True,
            }

    # 下载新版本
    temp_dir = tempfile.gettempdir()
    if IS_MACOS:
        new_file_path = os.path.join(temp_dir, "LX_new.zip")
    else:
        new_file_path = os.path.join(temp_dir, "LX_new.exe")

    expected_sha256 = result.get("sha256", "")
    expected_size = result.get("size", 0)

    if _download_file(result["url"], new_file_path, expected_sha256, expected_size):
        # 写入待更新标记
        pending = {
            "new_file_path": new_file_path,
            "from_version": current,
            "to_version": latest,
            "platform": _platform_str,
            "sha256": expected_sha256,
            "size": expected_size,
            "downloaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "attempts": 0,
        }
        _write_pending(pending)
        _log(f"新版本 {latest} 已下载，将在下次启动时自动升级")
    else:
        _log("下载失败，跳过本次升级")

    return {
        "has_update": has_update,
        "current": current,
        "latest": latest,
        "body": result.get("body", ""),
        "error": None if os.path.exists(_pending_path()) else "下载失败",
    }


# ===================== Windows 替换 =====================

def _apply_windows_update(pending: dict) -> bool:
    """Windows 平台应用更新"""
    new_exe = pending.get("new_file_path", pending.get("new_exe_path", ""))
    if not os.path.isfile(new_exe):
        _log(f"新版本文件不存在: {new_exe}")
        _clear_pending()
        return False

    # SHA256 校验
    expected_sha256 = pending.get("sha256", "")
    if expected_sha256 and not _verify_file(new_exe, expected_sha256, pending.get("size", 0)):
        _log("新版本文件校验失败，放弃更新")
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

    # 使用英文 echo 避免 GBK/UTF-8 编码问题
    bat_content = f"""@echo off
chcp 65001 >nul 2>&1
echo [LX Update] Waiting for app to exit...
:wait
tasklist /fi "pid eq {pid}" 2>nul | find "{pid}" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait
)
echo [LX Update] Backing up old version...
copy /y "{current_exe}" "{backup_exe}" >nul 2>&1
if errorlevel 1 (
    echo [LX Update] Backup failed, aborting
    start "" "{current_exe}"
    goto cleanup
)
echo [LX Update] Installing new version...
copy /y "{new_exe}" "{current_exe}" >nul 2>&1
if errorlevel 1 (
    echo [LX Update] Install failed, restoring old version...
    copy /y "{backup_exe}" "{current_exe}" >nul 2>&1
    start "" "{current_exe}"
    goto cleanup
)
echo [LX Update] Verifying new version...
if not exist "{current_exe}" (
    echo [LX Update] New exe missing! Restoring backup...
    copy /y "{backup_exe}" "{current_exe}" >nul 2>&1
)
del /f /q "{new_exe}" >nul 2>&1
del /f /q "{_pending_path()}" >nul 2>&1
echo [LX Update] Starting new version...
start "" "{current_exe}"
:cleanup
timeout /t 3 /nobreak >nul
del /f /q "{backup_exe}" >nul 2>&1
del /f /q "%~f0" >nul 2>&1
"""
    with open(bat_path, "w", encoding="gbk", errors="replace") as f:
        f.write(bat_content)

    _clear_pending()
    _log("启动 Windows 更新脚本...")
    subprocess.Popen(["cmd", "/c", bat_path], creationflags=subprocess.CREATE_NO_WINDOW)
    _log("正在应用更新，即将重启...")
    os._exit(0)
    return True


# ===================== macOS 替换 =====================

def _apply_macos_update(pending: dict) -> bool:
    """macOS 平台应用更新"""
    new_zip = pending.get("new_file_path", pending.get("new_exe_path", ""))
    if not os.path.isfile(new_zip):
        _log(f"新版本文件不存在: {new_zip}")
        _clear_pending()
        return False

    # SHA256 校验
    expected_sha256 = pending.get("sha256", "")
    if expected_sha256 and not _verify_file(new_zip, expected_sha256, pending.get("size", 0)):
        _log("新版本文件校验失败，放弃更新")
        try:
            os.remove(new_zip)
        except Exception:
            pass
        _clear_pending()
        return False

    # macOS: sys.executable = .../LX.app/Contents/MacOS/LX
    current_exe = sys.executable
    contents_dir = os.path.dirname(os.path.dirname(current_exe))  # .../Contents
    app_bundle = os.path.dirname(contents_dir)                      # .../LX.app
    backup_bundle = app_bundle + ".bak"

    pid = os.getpid()
    temp_dir = tempfile.gettempdir()
    sh_path = os.path.join(temp_dir, "LX_apply_update.sh")

    sh_content = f"""#!/bin/bash
# LX macOS Auto Update Script
echo "[LX Update] Waiting for app to exit..."
WAIT_COUNT=0
while kill -0 {pid} 2>/dev/null; do
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
    if [ $WAIT_COUNT -gt 30 ]; then
        echo "[LX Update] Timeout waiting for exit, force killing..."
        kill -9 {pid} 2>/dev/null
        sleep 2
        break
    fi
done
echo "[LX Update] Backing up old version..."
rm -rf "{backup_bundle}"
cp -R "{app_bundle}" "{backup_bundle}"
BACKUP_OK=$?
if [ $BACKUP_OK -ne 0 ]; then
    echo "[LX Update] Backup failed, aborting"
    open "{app_bundle}"
    exit 1
fi
echo "[LX Update] Extracting new version..."
UNZIP_DIR="{temp_dir}/LX_update_extract"
rm -rf "$UNZIP_DIR"
mkdir -p "$UNZIP_DIR"
cd "$UNZIP_DIR"
unzip -o "{new_zip}" -d "$UNZIP_DIR" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[LX Update] Unzip failed, restoring old version"
    rm -rf "$UNZIP_DIR"
    open "{app_bundle}"
    exit 1
fi
NEW_APP=$(find "$UNZIP_DIR" -maxdepth 2 -name "*.app" -type d | head -1)
if [ -z "$NEW_APP" ]; then
    echo "[LX Update] No .app found in archive, restoring old version"
    rm -rf "$UNZIP_DIR"
    open "{app_bundle}"
    exit 1
fi
echo "[LX Update] Installing new version..."
rm -rf "{app_bundle}"
cp -R "$NEW_APP" "{app_bundle}"
INSTALL_OK=$?
if [ $INSTALL_OK -ne 0 ]; then
    echo "[LX Update] Install failed, restoring from backup..."
    rm -rf "{app_bundle}"
    cp -R "{backup_bundle}" "{app_bundle}"
    open "{app_bundle}"
    rm -rf "$UNZIP_DIR"
    exit 1
fi
# Verify new app exists
if [ ! -d "{app_bundle}" ]; then
    echo "[LX Update] New app missing! Restoring from backup..."
    cp -R "{backup_bundle}" "{app_bundle}"
fi
# Cleanup
rm -rf "$UNZIP_DIR"
rm -f "{new_zip}"
rm -f "{_pending_path()}"
echo "[LX Update] Starting new version..."
open "{app_bundle}"
# Clean up backup and script after delay
sleep 5
rm -rf "{backup_bundle}"
rm -f "$0"
"""
    with open(sh_path, "w", encoding="utf-8") as f:
        f.write(sh_content)
    os.chmod(sh_path, 0o755)

    _clear_pending()
    _log("启动 macOS 更新脚本...")
    subprocess.Popen(["/bin/bash", sh_path])
    _log("正在应用更新，即将重启...")
    os._exit(0)
    return True


# ===================== 应用待更新 =====================

def apply_pending_update() -> bool:
    """
    启动时调用：如果存在待更新标记，执行替换并重启。
    包含重试次数限制和文件校验。
    """
    if not getattr(sys, "frozen", False):
        return False

    if not has_pending_update():
        return False

    pending = _read_pending()
    if not pending:
        _clear_pending()
        return False

    # 检查重试次数
    attempts = pending.get("attempts", 0)
    if attempts >= MAX_UPDATE_ATTEMPTS:
        _log(f"更新已尝试 {attempts} 次均失败，放弃更新并清理")
        # 清理临时文件
        new_file = pending.get("new_file_path", "")
        if new_file and os.path.exists(new_file):
            try:
                os.remove(new_file)
            except Exception:
                pass
        _clear_pending()
        return False

    # 递增尝试次数
    pending["attempts"] = attempts + 1
    _write_pending(pending)
    _log(f"应用待更新 (第 {attempts + 1}/{MAX_UPDATE_ATTEMPTS} 次): {pending.get('to_version', '?')}")

    try:
        if IS_WINDOWS:
            return _apply_windows_update(pending)
        elif IS_MACOS:
            return _apply_macos_update(pending)
        else:
            _log(f"不支持的平台: {sys.platform}")
            _clear_pending()
            return False
    except Exception as e:
        _log(f"应用更新异常: {e}")
        # 不立即清除，允许下次重试
        return False


# ===================== 兼容旧接口 =====================

def check_and_update(auto: bool = False) -> dict:
    """
    兼容旧接口：检查更新。
    auto=False: 仅检查，不下载
    auto=True: 检查并下载（不立即替换，下次启动时替换）
    """
    if auto:
        return check_and_download_update()
    else:
        _clear_proxy_env()
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
