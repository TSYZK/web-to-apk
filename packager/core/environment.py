# -*- coding: utf-8 -*-
"""构建环境管理：检测 / 自动下载安装 JDK17、Gradle、Android SDK。"""
import os
import shutil
import subprocess
import sys
import zipfile
import urllib.request
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[2]          # D:\BV\WebToApk
WORKSPACE = APP_ROOT / "workspace"
TOOLS_DIR = WORKSPACE / "tools"
GRADLE_USER_HOME = WORKSPACE / "gradle-home"
JDK_PARENT = TOOLS_DIR / "jdk"
GRADLE_PARENT = TOOLS_DIR / "gradle"
SDK_DIR = TOOLS_DIR / "android-sdk"

# ---- 下载地址（已按本机实测可用性排序：国内镜像优先，自动回退）----
JDK_URLS = [
    "https://mirrors.huaweicloud.com/openjdk/17.0.2/openjdk-17.0.2_windows-x64_bin.zip",
    "https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jdk/hotspot/normal/eclipse",
]
GRADLE_URLS = [
    "https://mirrors.huaweicloud.com/gradle/gradle-8.7-bin.zip",
    "https://services.gradle.org/distributions/gradle-8.7-bin.zip",
    "https://mirrors.cloud.tencent.com/gradle/gradle-8.7-bin.zip",
]
CMDLINE_TOOLS_URLS = [
    "https://mirrors.cloud.tencent.com/AndroidSDK/commandlinetools-win-11076708_latest.zip",
    "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip",
]

SDK_PACKAGES = ["platform-tools", "platforms;android-34", "build-tools;34.0.0"]


def _log_cb_default(msg):
    print(msg, flush=True)


# ---------------- 环境检测 ----------------

def _find_system(cmd):
    return shutil.which(cmd)


def find_local_jdk():
    """返回本地（tools目录）JDK 的 JAVA_HOME，没有则 None。"""
    if JDK_PARENT.is_dir():
        for child in sorted(JDK_PARENT.iterdir(), reverse=True):
            if (child / "bin" / "java.exe").is_file():
                return child
    return None


def find_local_gradle():
    if GRADLE_PARENT.is_dir():
        for child in sorted(GRADLE_PARENT.iterdir(), reverse=True):
            if (child / "bin" / "gradle.bat").is_file():
                return child
    return None


def detect():
    """返回当前可用的构建环境信息。"""
    jdk_home = find_local_jdk()
    java_exe = str(jdk_home / "bin" / "java.exe") if jdk_home else _find_system("java")
    if java_exe and not jdk_home:
        # 系统 java：推断 JAVA_HOME
        jdk_home = Path(java_exe).resolve().parents[1]

    gradle_dir = find_local_gradle()
    gradle_exe = None
    if gradle_dir:
        gradle_exe = str(gradle_dir / "bin" / "gradle.bat")
    else:
        g = _find_system("gradle")
        if g:
            gradle_exe = g

    sdk = None
    if (SDK_DIR / "cmdline-tools" / "latest" / "bin" / "sdkmanager.bat").is_file():
        sdk = str(SDK_DIR)
    elif os.environ.get("ANDROID_HOME") and Path(os.environ["ANDROID_HOME"]).is_dir():
        sdk = os.environ["ANDROID_HOME"]
    elif os.environ.get("ANDROID_SDK_ROOT") and Path(os.environ["ANDROID_SDK_ROOT"]).is_dir():
        sdk = os.environ["ANDROID_SDK_ROOT"]

    sdk_complete = bool(
        sdk and (Path(sdk) / "platforms" / "android-34").is_dir()
        and (Path(sdk) / "build-tools" / "34.0.0").is_dir())

    return {
        "java": java_exe,
        "java_home": str(jdk_home) if jdk_home and Path(java_exe).is_file() else None,
        "gradle": gradle_exe,
        "sdk": sdk,
        "sdk_complete": sdk_complete,
        "ready": bool(java_exe and gradle_exe and sdk_complete),
    }


# ---------------- 下载与解压 ----------------

def _download(urls, dest: Path, log=_log_cb_default, progress=None,
              is_cancelled=None):
    """按候选 URL 依次尝试下载，progress(got, total) 回调。"""
    last_err = None
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    for url in urls:
        try:
            log(f"正在下载：{url}")
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                total = int(resp.headers.get("Content-Length", 0)) or None
                got = 0
                tmp = dest.with_suffix(".part")
                with open(tmp, "wb") as f:
                    while True:
                        if is_cancelled and is_cancelled():
                            tmp.unlink(missing_ok=True)
                            raise RuntimeError("已取消")
                        chunk = resp.read(1024 * 256)
                        if not chunk:
                            break
                        f.write(chunk)
                        got += len(chunk)
                        if progress:
                            progress(got, total)
                tmp.replace(dest)
            log("下载完成，正在校验压缩包...")
            with zipfile.ZipFile(dest) as zf:
                bad = zf.testzip()
                if bad:
                    raise RuntimeError(f"压缩包损坏：{bad}")
            return True
        except Exception as e:
            last_err = e
            log(f"该地址失败：{e}")
            continue
    raise RuntimeError(f"所有下载地址均失败：{last_err}")


def _extract(zip_path: Path, target_dir: Path, log=_log_cb_default):
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(target_dir)
    log(f"已解压到：{target_dir}")


def _run(cmd, log=_log_cb_default, input_text=None, env=None, check=True):
    log("$ " + " ".join(str(c) for c in cmd))
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE if input_text is not None else None,
        env=env, text=True, encoding="utf-8", errors="ignore",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if input_text is not None:
        try:
            out, _ = proc.communicate(input=input_text, timeout=600)
            for line in out.splitlines():
                log(line)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise
    else:
        for line in proc.stdout:
            log(line.rstrip())
        proc.wait()
    if check and proc.returncode != 0:
        raise RuntimeError(f"命令执行失败（退出码 {proc.returncode}）")
    return proc.returncode


# ---------------- 安装流程 ----------------

def ensure_jdk(log=_log_cb_default, progress=None, is_cancelled=None) -> Path:
    jdk = find_local_jdk()
    if jdk:
        log(f"JDK 已存在：{jdk}")
        return jdk
    JDK_PARENT.mkdir(parents=True, exist_ok=True)
    zipp = TOOLS_DIR / "jdk17.zip"
    _download(JDK_URLS, zipp, log, progress, is_cancelled)
    _extract(zipp, JDK_PARENT, log)
    zipp.unlink(missing_ok=True)
    jdk = find_local_jdk()
    if not jdk:
        raise RuntimeError("JDK 解压后未找到 java.exe")
    log(f"JDK 安装完成：{jdk}")
    return jdk


def ensure_gradle(log=_log_cb_default, progress=None, is_cancelled=None) -> Path:
    g = find_local_gradle()
    if g:
        log(f"Gradle 已存在：{g}")
        return g
    GRADLE_PARENT.mkdir(parents=True, exist_ok=True)
    zipp = TOOLS_DIR / "gradle-8.7.zip"
    _download(GRADLE_URLS, zipp, log, progress, is_cancelled)
    _extract(zipp, GRADLE_PARENT, log)
    zipp.unlink(missing_ok=True)
    g = find_local_gradle()
    if not g:
        raise RuntimeError("Gradle 解压后未找到 gradle.bat")
    log(f"Gradle 安装完成：{g}")
    return g


def ensure_android_sdk(java_home: Path, log=_log_cb_default, progress=None,
                       is_cancelled=None) -> str:
    sdkmanager = SDK_DIR / "cmdline-tools" / "latest" / "bin" / "sdkmanager.bat"
    if not sdkmanager.is_file():
        SDK_DIR.mkdir(parents=True, exist_ok=True)
        zipp = TOOLS_DIR / "cmdline-tools.zip"
        _download(CMDLINE_TOOLS_URLS, zipp, log, progress, is_cancelled)
        tmp_extract = TOOLS_DIR / "_cmdline_tmp"
        if tmp_extract.exists():
            shutil.rmtree(tmp_extract)
        _extract(zipp, tmp_extract, log)
        zipp.unlink(missing_ok=True)
        # zip 内顶层为 cmdline-tools/，需放到 SDK/cmdline-tools/latest/
        src = tmp_extract / "cmdline-tools"
        if not src.is_dir():
            # 某些打包结构不同，寻找含 bin 的目录
            for p in tmp_extract.rglob("sdkmanager.bat"):
                src = p.parents[1]
                break
        dest = SDK_DIR / "cmdline-tools" / "latest"
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        shutil.rmtree(tmp_extract, ignore_errors=True)
        log(f"Android cmdline-tools 安装完成：{dest}")

    env = _build_env(java_home)
    log("正在接受 Android SDK 许可协议...")
    _run([str(sdkmanager), f"--sdk_root={SDK_DIR}", "--licenses"],
         log=log, input_text="y\n" * 30, env=env, check=False)
    log("正在安装 SDK 组件（platform-tools / android-34 / build-tools 34）...")
    _run([str(sdkmanager), f"--sdk_root={SDK_DIR}"] + SDK_PACKAGES,
         log=log, input_text="y\n" * 10, env=env)
    log("Android SDK 安装完成")
    return str(SDK_DIR)


def _build_env(java_home: Path):
    env = os.environ.copy()
    env["JAVA_HOME"] = str(java_home)
    env["ANDROID_HOME"] = str(SDK_DIR)
    env["ANDROID_SDK_ROOT"] = str(SDK_DIR)
    env["GRADLE_USER_HOME"] = str(GRADLE_USER_HOME)
    env["PATH"] = (str(java_home / "bin") + os.pathsep
                   + str(SDK_DIR / "platform-tools") + os.pathsep
                   + env.get("PATH", ""))
    return env


def ensure_all(log=_log_cb_default, progress=None, is_cancelled=None):
    """一键安装全部构建环境。progress(percent, text)。"""
    def sub_p(pct, text):
        if progress:
            progress(int(pct), text)

    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    sub_p(2, "安装 JDK 17 ...")
    jdk = ensure_jdk(log,
                     progress=lambda g, t: progress(2 + int(28 * g / (t or g)),
                                                   f"下载 JDK 17：{g // 1024 // 1024}MB/{(t or 0) // 1024 // 1024}MB")
                     if progress else None,
                     is_cancelled=is_cancelled)
    sub_p(32, "安装 Gradle 8.7 ...")
    gradle = ensure_gradle(log,
                           progress=lambda g, t: progress(32 + int(18 * g / (t or g)),
                                                         f"下载 Gradle：{g // 1024 // 1024}MB/{(t or 0) // 1024 // 1024}MB")
                           if progress else None,
                           is_cancelled=is_cancelled)
    sub_p(52, "安装 Android SDK ...")
    ensure_android_sdk(
        jdk, log,
        progress=lambda g, t: progress(52 + int(20 * g / (t or g)),
                                       f"下载 cmdline-tools：{g // 1024 // 1024}MB")
        if progress else None,
        is_cancelled=is_cancelled)
    sub_p(95, "校验环境 ...")
    info = detect()
    if not info["ready"]:
        raise RuntimeError("环境安装后校验未通过：" + str(info))
    progress(100, "构建环境准备完成") if progress else None
    return info


def generate_keystore(project_dir: Path, java_home: Path,
                      password: str = "webtoapk",
                      log=_log_cb_default):
    """在工程根目录生成 release.keystore 与 keystore.properties。"""
    ks = project_dir / "release.keystore"
    if not ks.is_file():
        keytool = java_home / "bin" / "keytool.exe"
        _run([
            str(keytool), "-genkeypair", "-v",
            "-keystore", str(ks), "-alias", "release",
            "-keyalg", "RSA", "-keysize", "2048", "-validity", "10000",
            "-storepass", password, "-keypass", password,
            "-dname", "CN=WebToApk, OU=Dev, O=WebToApk, L=City, ST=Province, C=CN",
        ], log=log, env=_build_env(java_home))
    props = project_dir / "keystore.properties"
    props.write_text(
        "storeFile=../release.keystore\n"
        "storePassword=%s\n"
        "keyAlias=release\n"
        "keyPassword=%s\n" % (password, password),
        encoding="utf-8")
    return ks
