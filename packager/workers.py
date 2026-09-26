# -*- coding: utf-8 -*-
"""后台工作线程：网页检测、环境安装、工程生成 + 构建。"""
from PySide6.QtCore import QThread, Signal

from .core import environment as env
from .core.webcheck import check_website
from .core.projectgen import generate_project
from .core.builder import build_apk

# 步骤状态：0 等待 / 1 进行中 / 2 完成 / 3 失败
STEP_WAIT, STEP_RUN, STEP_DONE, STEP_FAIL = 0, 1, 2, 3

STEP_NAMES = ["检测网页", "生成 Android 工程", "准备构建环境", "编译打包 APK"]


class CheckWorker(QThread):
    log = Signal(str)
    result = Signal(object)

    def __init__(self, url: str):
        super().__init__()
        self.url = url

    def run(self):
        r = check_website(self.url)
        self.result.emit(r)


class EnvWorker(QThread):
    log = Signal(str)
    progress = Signal(int, str)
    step = Signal(int, int)
    finished_ok = Signal()
    failed = Signal(str)

    def run(self):
        try:
            self.step.emit(2, STEP_RUN)
            env.ensure_all(
                log=lambda m: self.log.emit(str(m)),
                progress=lambda p, t: self.progress.emit(int(p), str(t)),
                is_cancelled=lambda: False,
            )
            self.step.emit(2, STEP_DONE)
            self.finished_ok.emit()
        except Exception as e:
            self.step.emit(2, STEP_FAIL)
            self.failed.emit(str(e))


class BuildWorker(QThread):
    log = Signal(str)
    progress = Signal(int, str)
    step = Signal(int, int)          # 步骤索引, 状态
    finished_ok = Signal(dict)
    failed = Signal(str)

    def __init__(self, config: dict, do_check: bool, build_type: str = "release"):
        super().__init__()
        self.config = config
        self.do_check = do_check
        self.build_type = build_type

    def run(self):
        project_dir = None
        try:
            # 步骤 0：检测网页
            if self.do_check:
                self.step.emit(0, STEP_RUN)
                self.log.emit("正在检测网页是否可以正常打开 ...")
                r = check_website(self.config["url"])
                if not r.ok:
                    self.step.emit(0, STEP_FAIL)
                    raise RuntimeError(r.message)
                self.log.emit(
                    f"网页检测通过：HTTP {r.status}，耗时 {r.elapsed_ms}ms。{r.message}")
                self.step.emit(0, STEP_DONE)
            else:
                self.step.emit(0, STEP_DONE)

            # 步骤 1：生成工程
            self.step.emit(1, STEP_RUN)
            self.progress.emit(5, "正在生成 Android 工程 ...")
            project_dir = generate_project(
                self.config, log=lambda m: self.log.emit(str(m)))
            self.step.emit(1, STEP_DONE)

            # 步骤 2：确保环境就绪
            info = env.detect()
            if info["ready"]:
                self.log.emit("构建环境已就绪，跳过环境安装")
                self.step.emit(2, STEP_DONE)
            else:
                self.step.emit(2, STEP_RUN)
                self.log.emit("构建环境缺失，开始自动安装 JDK / Gradle / Android SDK ...")
                env.ensure_all(
                    log=lambda m: self.log.emit(str(m)),
                    progress=lambda p, t: self.progress.emit(int(p * 0.4), str(t)),
                    is_cancelled=lambda: False,
                )
                self.step.emit(2, STEP_DONE)

            # 步骤 3：编译打包
            self.step.emit(3, STEP_RUN)
            apk = build_apk(
                project_dir, self.build_type,
                log=lambda m: self.log.emit(str(m)),
                progress=lambda p, t: self.progress.emit(40 + int(p * 0.6), str(t)),
                is_cancelled=lambda: False,
            )
            self.step.emit(3, STEP_DONE)
            self.progress.emit(100, "全部完成")
            self.finished_ok.emit({"apk": str(apk),
                                   "project": str(project_dir)})
        except Exception as e:
            if project_dir is None:
                self.step.emit(1, STEP_FAIL)
            else:
                self.step.emit(3, STEP_FAIL)
            self.failed.emit(str(e))
