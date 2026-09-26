# -*- coding: utf-8 -*-
"""Gradle 构建封装：调用 gradle 打包 APK，解析进度。"""
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from . import environment as env

TASK_PATTERN = re.compile(r"> Task :app:(\w+)")

# 任务名 -> 总体进度百分比（取已出现任务的最大值）
TASK_PROGRESS = [
    ("preBuild", 6),
    ("processReleaseManifest", 10),
    ("processDebugManifest", 10),
    ("mergeReleaseResources", 20),
    ("mergeDebugResources", 20),
    ("processReleaseResources", 28),
    ("processDebugResources", 28),
    ("compileReleaseJavaWithJavac", 45),
    ("compileDebugJavaWithJavac", 45),
    ("dexBuilderRelease", 58),
    ("dexBuilderDebug", 58),
    ("mergeReleaseDex", 68),
    ("mergeDebugDex", 68),
    ("packageRelease", 82),
    ("packageDebug", 82),
    ("createReleaseApk", 92),
    ("createDebugApk", 92),
    ("assembleRelease", 98),
    ("assembleDebug", 98),
]


def build_apk(project_dir: Path, build_type: str = "release",
              log=print, progress=None, is_cancelled=None) -> Path:
    """
    执行 Gradle 构建。
    build_type: "release" 或 "debug"
    返回最终 APK 路径。
    """
    info = env.detect()
    if not info["ready"]:
        raise RuntimeError("构建环境未就绪，请先一键安装环境")

    java_home = Path(info["java_home"])
    gradle_bat = info["gradle"]
    sdk_dir = info["sdk"]

    from .projectgen import write_local_properties
    write_local_properties(project_dir, sdk_dir)

    log("正在生成签名密钥（keystore）...")
    env.generate_keystore(project_dir, java_home, log=log)

    task = "assembleRelease" if build_type == "release" else "assembleDebug"
    cmd = [gradle_bat, "--no-daemon", "-x", "lint", task]
    run_env = env._build_env(java_home)

    log("开始 Gradle 构建（首次会下载依赖，可能需要几分钟）...")
    proc = subprocess.Popen(
        cmd, cwd=str(project_dir), stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, env=run_env, text=True,
        encoding="utf-8", errors="ignore",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    max_pct = 3
    success = False
    try:
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                log(line)
            m = TASK_PATTERN.search(line)
            if m:
                name = m.group(1)
                for task_name, pct in TASK_PROGRESS:
                    if name == task_name:
                        max_pct = max(max_pct, pct)
                        break
                if progress:
                    progress(max_pct, f"编译中：{name}")
            if "BUILD SUCCESSFUL" in line:
                success = True
                if progress:
                    progress(99, "构建成功，正在整理 APK ...")
            if "BUILD FAILED" in line:
                success = False
            if is_cancelled and is_cancelled():
                proc.terminate()
                raise RuntimeError("已取消构建")
        proc.wait()
    finally:
        if proc.poll() is None:
            proc.kill()

    if not success or proc.returncode != 0:
        raise RuntimeError(
            f"Gradle 构建失败（退出码 {proc.returncode}），请查看右侧日志")

    sub = "release" if build_type == "release" else "debug"
    apk = (project_dir / "app" / "build" / "outputs" / "apk" / sub
           / f"app-{sub}.apk")
    if not apk.is_file():
        raise RuntimeError(f"构建报告成功但未找到 APK：{apk}")

    from .projectgen import APKS_DIR, safe_name
    APKS_DIR.mkdir(parents=True, exist_ok=True)
    app_name = (project_dir / "app" / "src" / "main" / "res" / "values"
                / "strings.xml").read_text(encoding="utf-8")
    m = re.search(r">([^<]+)</string>", app_name)
    name = m.group(1) if m else "app"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    final = APKS_DIR / f"{safe_name(name)}_{build_type}_{stamp}.apk"
    shutil.copy2(apk, final)
    if progress:
        progress(100, "APK 打包完成")
    log(f"APK 已输出：{final}")
    return final
