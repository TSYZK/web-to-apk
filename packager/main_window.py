# -*- coding: utf-8 -*-
"""主窗口：左侧工作栏 / 中间网页预览 / 右侧打包进展。"""
import os
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QSize
from PySide6.QtGui import QColor, QFont, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter, QLabel,
    QLineEdit, QPushButton, QGroupBox, QFormLayout, QSpinBox, QCheckBox,
    QComboBox, QFileDialog, QColorDialog, QProgressBar, QPlainTextEdit,
    QScrollArea, QMessageBox, QFrame, QSizePolicy, QApplication,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

from . import workers
from .core import environment as env
from .core.webcheck import normalize_url

PRIMARY = "#2563eb"
PRIMARY_DARK = "#1d4ed8"
BG = "#f5f7fb"
STEP_COLORS = {
    workers.STEP_WAIT: ("#9ca3af", "等待中"),
    workers.STEP_RUN: ("#2563eb", "进行中..."),
    workers.STEP_DONE: ("#16a34a", "已完成"),
    workers.STEP_FAIL: ("#dc2626", "失败"),
}


class StepRow(QWidget):
    """右侧的单个步骤指示行。"""

    def __init__(self, index: int, name: str):
        super().__init__()
        self.index = index
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)
        self.badge = QLabel(str(index + 1))
        self.badge.setFixedSize(28, 28)
        self.badge.setAlignment(Qt.AlignCenter)
        self.name = QLabel(name)
        self.name.setFont(QFont("Microsoft YaHei UI", 10))
        self.status = QLabel("等待中")
        self.status.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status.setFont(QFont("Microsoft YaHei UI", 9))
        lay.addWidget(self.badge)
        lay.addWidget(self.name, 1)
        lay.addWidget(self.status)
        self.set_state(workers.STEP_WAIT)

    def set_state(self, state: int):
        color, text = STEP_COLORS[state]
        self.badge.setStyleSheet(
            f"background:{color};color:white;border-radius:14px;"
            "font-weight:bold;")
        self.status.setStyleSheet(f"color:{color};font-weight:bold;")
        self.status.setText(text)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("网页转 APK 打包工具  -  Web To APK Packager")
        self.resize(1420, 880)
        self.setMinimumSize(1150, 720)
        self.icon_path = None
        self.theme_color = "#2563eb"
        self.worker = None
        self.env_worker = None
        self.check_worker = None
        self.last_apk = None

        self._build_ui()
        self.refresh_env_status()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        central = QWidget()
        central.setStyleSheet(f"QWidget{{font-family:'Microsoft YaHei UI';}}")
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left())
        splitter.addWidget(self._build_center())
        splitter.addWidget(self._build_right())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([330, 640, 410])
        splitter.setHandleWidth(6)

        root.addWidget(splitter)
        self.setCentralWidget(central)

    # ---------- 左侧：工作栏 ----------
    def _build_left(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(330)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}")

        holder = QWidget()
        holder.setStyleSheet(f"background:{BG};")
        v = QVBoxLayout(holder)
        v.setSpacing(10)
        v.setContentsMargins(10, 10, 10, 14)

        title = QLabel("网页转 APK")
        title.setFont(QFont("Microsoft YaHei UI", 17, QFont.Bold))
        title.setStyleSheet(f"color:{PRIMARY_DARK};")
        sub = QLabel("输入网址 · 检测 · 一键打包成安卓应用")
        sub.setStyleSheet("color:#6b7280;font-size:11px;")
        v.addWidget(title)
        v.addWidget(sub)

        # 网址组
        g_url = QGroupBox("① 网页地址")
        f = QVBoxLayout(g_url)
        url_row = QHBoxLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("例如 https://www.example.com")
        self.url_edit.returnPressed.connect(self.on_check)
        url_row.addWidget(self.url_edit)
        f.addLayout(url_row)
        btn_row = QHBoxLayout()
        self.btn_check = QPushButton("检测网页")
        self.btn_check.setCursor(Qt.PointingHandCursor)
        self.btn_check.setStyleSheet(self._btn_style(PRIMARY))
        self.btn_check.clicked.connect(self.on_check)
        btn_row.addWidget(self.btn_check)
        f.addLayout(btn_row)
        self.check_light = QLabel("● 尚未检测")
        self.check_light.setStyleSheet("color:#9ca3af;font-weight:bold;")
        f.addWidget(self.check_light)
        v.addWidget(g_url)

        # 应用配置组
        g_app = QGroupBox("② 应用配置")
        form = QFormLayout(g_app)
        form.setLabelAlignment(Qt.AlignRight)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("手机桌面上显示的名称")
        form.addRow("应用名称：", self.name_edit)
        self.pkg_edit = QLineEdit()
        self.pkg_edit.setPlaceholderText("com.example.myapp")
        form.addRow("包名：", self.pkg_edit)
        ver_row = QHBoxLayout()
        self.code_spin = QSpinBox()
        self.code_spin.setRange(1, 999999)
        self.code_spin.setValue(1)
        self.vername_edit = QLineEdit("1.0")
        self.vername_edit.setFixedWidth(90)
        ver_row.addWidget(QLabel("版本号"))
        ver_row.addWidget(self.code_spin)
        ver_row.addWidget(QLabel("版本名"))
        ver_row.addWidget(self.vername_edit)
        ver_row.addStretch()
        form.addRow("版本：", ver_row)

        color_row = QHBoxLayout()
        self.btn_color = QPushButton("  选择主题色")
        self.btn_color.setCursor(Qt.PointingHandCursor)
        self._update_color_btn()
        self.btn_color.clicked.connect(self.pick_color)
        color_row.addWidget(self.btn_color)
        form.addRow("主题色：", color_row)

        icon_row = QHBoxLayout()
        self.btn_icon = QPushButton("选择图标图片")
        self.btn_icon.setCursor(Qt.PointingHandCursor)
        self.btn_icon.clicked.connect(self.pick_icon)
        icon_row.addWidget(self.btn_icon)
        form.addRow("应用图标：", icon_row)
        self.icon_label = QLabel("未选择（使用默认图标）")
        self.icon_label.setStyleSheet("color:#6b7280;font-size:10px;")
        self.icon_label.setWordWrap(True)
        form.addRow("", self.icon_label)

        self.chk_fullscreen = QCheckBox("全屏显示（隐藏状态栏）")
        form.addRow("", self.chk_fullscreen)
        self.chk_keepon = QCheckBox("保持屏幕常亮")
        form.addRow("", self.chk_keepon)

        self.combo_build = QComboBox()
        self.combo_build.addItems(["release（正式版，可分发）", "debug（调试版）"])
        form.addRow("构建类型：", self.combo_build)
        v.addWidget(g_app)

        # 环境组
        g_env = QGroupBox("③ 构建环境")
        ev = QVBoxLayout(g_env)
        self.env_labels = {}
        for key, text in (("java", "JDK 17"), ("sdk", "Android SDK 34"),
                          ("gradle", "Gradle 8.7")):
            row = QHBoxLayout()
            dot = QLabel("●")
            name = QLabel(text)
            row.addWidget(dot)
            row.addWidget(name, 1)
            ev.addLayout(row)
            self.env_labels[key] = dot
        self.btn_env = QPushButton("一键安装构建环境")
        self.btn_env.setCursor(Qt.PointingHandCursor)
        self.btn_env.setStyleSheet(self._btn_style("#0ea5e9"))
        self.btn_env.clicked.connect(self.install_env)
        ev.addWidget(self.btn_env)
        v.addWidget(g_env)

        # 打包按钮
        self.btn_build = QPushButton("④ 开始打包 APK")
        self.btn_build.setCursor(Qt.PointingHandCursor)
        self.btn_build.setFixedHeight(46)
        self.btn_build.setFont(QFont("Microsoft YaHei UI", 13, QFont.Bold))
        self.btn_build.setStyleSheet(
            f"QPushButton{{background:{PRIMARY};color:white;border:none;"
            f"border-radius:8px;}}QPushButton:hover{{background:{PRIMARY_DARK};}}"
            "QPushButton:disabled{background:#9ca3af;}")
        self.btn_build.clicked.connect(self.start_build)
        v.addWidget(self.btn_build)

        v.addStretch()
        scroll.setWidget(holder)
        return scroll

    # ---------- 中间：网页预览 ----------
    def _build_center(self):
        frame = QFrame()
        frame.setStyleSheet("QFrame{background:white;border:1px solid #e5e7eb;"
                            "border-radius:8px;}")
        v = QVBoxLayout(frame)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(8, 6, 8, 6)
        self.btn_back = QPushButton("←")
        self.btn_fwd = QPushButton("→")
        self.btn_reload = QPushButton("⟳")
        self.btn_home = QPushButton("主页")
        for b in (self.btn_back, self.btn_fwd, self.btn_reload, self.btn_home):
            b.setFixedWidth(40 if b.text() not in ("主页",) else 56)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(
                "QPushButton{background:#f3f4f6;border:none;border-radius:6px;"
                "padding:5px;}QPushButton:hover{background:#e5e7eb;}")
        self.btn_back.clicked.connect(lambda: self.webview.back())
        self.btn_fwd.clicked.connect(lambda: self.webview.forward())
        self.btn_reload.clicked.connect(lambda: self.webview.reload())
        self.btn_home.clicked.connect(self._load_preview)
        toolbar.addWidget(self.btn_back)
        toolbar.addWidget(self.btn_fwd)
        toolbar.addWidget(self.btn_reload)
        toolbar.addWidget(self.btn_home)
        self.addr_edit = QLineEdit()
        self.addr_edit.setStyleSheet(
            "QLineEdit{background:#f3f4f6;border:1px solid #e5e7eb;"
            "border-radius:6px;padding:5px 8px;}")
        self.addr_edit.returnPressed.connect(self._load_preview)
        toolbar.addWidget(self.addr_edit, 1)
        v.addLayout(toolbar)

        self.preview_progress = QProgressBar()
        self.preview_progress.setFixedHeight(3)
        self.preview_progress.setTextVisible(False)
        self.preview_progress.setStyleSheet(
            "QProgressBar{background:transparent;}QProgressBar::chunk{"
            f"background:{PRIMARY};}}")
        v.addWidget(self.preview_progress)

        self.webview = QWebEngineView()
        self.webview.loadStarted.connect(
            lambda: self.preview_hint.setVisible(False))
        self.webview.loadProgress.connect(self.preview_progress.setValue)
        self.webview.urlChanged.connect(
            lambda u: self.addr_edit.setText(u.toString()))
        self.webview.loadFinished.connect(self._preview_loaded)
        v.addWidget(self.webview, 1)

        self.preview_hint = QLabel(
            "中间区域用于预览网页\n\n请在左侧输入网址，点击「检测网页」\n"
            "网页能正常打开后即可打包成 APK")
        self.preview_hint.setAlignment(Qt.AlignCenter)
        self.preview_hint.setStyleSheet("color:#9ca3af;font-size:15px;"
                                        "background:white;")
        v.addWidget(self.preview_hint)
        self.preview_hint.setAttribute(Qt.WA_TransparentForMouseEvents)
        return frame

    # ---------- 右侧：打包进展 ----------
    def _build_right(self):
        frame = QFrame()
        frame.setFixedWidth(410)
        frame.setStyleSheet("QFrame{background:white;border:1px solid #e5e7eb;"
                            "border-radius:8px;}")
        v = QVBoxLayout(frame)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        t = QLabel("转换进展")
        t.setFont(QFont("Microsoft YaHei UI", 14, QFont.Bold))
        t.setStyleSheet(f"color:{PRIMARY_DARK};")
        v.addWidget(t)

        self.step_rows = []
        for i, name in enumerate(workers.STEP_NAMES):
            row = StepRow(i, name)
            v.addWidget(row)
            self.step_rows.append(row)

        self.total_progress = QProgressBar()
        self.total_progress.setFixedHeight(16)
        self.total_progress.setValue(0)
        self.total_progress.setFormat("%p%")
        self.total_progress.setStyleSheet(
            "QProgressBar{background:#e5e7eb;border-radius:8px;text-align:center;"
            "color:#111;font-size:10px;}QProgressBar::chunk{"
            f"background:{PRIMARY};border-radius:8px;}}")
        v.addWidget(self.total_progress)
        self.progress_text = QLabel("待开始")
        self.progress_text.setStyleSheet("color:#6b7280;font-size:10px;")
        v.addWidget(self.progress_text)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:#e5e7eb;")
        v.addWidget(line)

        log_label = QLabel("实时日志")
        log_label.setFont(QFont("Microsoft YaHei UI", 10, QFont.Bold))
        v.addWidget(log_label)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setStyleSheet(
            "QPlainTextEdit{background:#0f172a;color:#d1e7ff;"
            "border:none;border-radius:6px;font-family:Consolas;"
            "font-size:11px;padding:6px;}")
        v.addWidget(self.log_view, 1)

        # 结果区
        self.result_box = QWidget()
        rv = QHBoxLayout(self.result_box)
        rv.setContentsMargins(0, 0, 0, 0)
        self.btn_open_dir = QPushButton("打开 APK 所在文件夹")
        self.btn_open_dir.setCursor(Qt.PointingHandCursor)
        self.btn_open_dir.setStyleSheet(self._btn_style("#16a34a"))
        self.btn_open_dir.clicked.connect(self.open_apk_dir)
        self.btn_install = QPushButton("安装到手机")
        self.btn_install.setCursor(Qt.PointingHandCursor)
        self.btn_install.setStyleSheet(self._btnStyle_secondary())
        self.btn_install.clicked.connect(self.install_to_phone)
        rv.addWidget(self.btn_open_dir)
        rv.addWidget(self.btn_install)
        self.result_box.setVisible(False)
        v.addWidget(self.result_box)
        return frame

    # ------------------------------------------------------------ 样式工具
    @staticmethod
    def _btn_style(color):
        return (f"QPushButton{{background:{color};color:white;border:none;"
                "border-radius:6px;padding:7px;font-weight:bold;}"
                f"QPushButton:hover{{background:{color};opacity:0.9;}}"
                "QPushButton:disabled{background:#9ca3af;}")

    @staticmethod
    def _btnStyle_secondary():
        return ("QPushButton{background:white;color:#374151;border:1px solid #d1d5db;"
                "border-radius:6px;padding:7px;font-weight:bold;}"
                "QPushButton:hover{background:#f3f4f6;}")

    def _update_color_btn(self):
        self.btn_color.setText("  选择主题色")
        self.btn_color.setStyleSheet(
            f"QPushButton{{background:{self.theme_color};color:white;"
            "border:none;border-radius:6px;padding:7px;font-weight:bold;}")

    # ------------------------------------------------------------ 动作处理
    def pick_color(self):
        c = QColorDialog.getColor(QColor(self.theme_color), self, "选择主题色")
        if c.isValid():
            self.theme_color = c.name()
            self._update_color_btn()

    def pick_icon(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择应用图标", "",
            "图片文件 (*.png *.jpg *.jpeg *.webp *.bmp *.ico)")
        if path:
            self.icon_path = path
            self.icon_label.setText(Path(path).name)

    def append_log(self, text):
        self.log_view.appendPlainText(text)
        sb = self.log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _set_busy(self, busy: bool):
        for w in (self.btn_check, self.btn_build, self.btn_env, self.url_edit):
            w.setEnabled(not busy)

    # ---------- 网页检测 ----------
    def on_check(self):
        raw = self.url_edit.text().strip()
        if not raw:
            QMessageBox.warning(self, "提示", "请先输入网页地址")
            return
        url = normalize_url(raw)
        self.url_edit.setText(url)
        self.check_light.setText("● 正在检测...")
        self.check_light.setStyleSheet("color:#f59e0b;font-weight:bold;")
        self.append_log(f"开始检测网页：{url}")
        self._load_preview()

        self.check_worker = workers.CheckWorker(url)
        self.check_worker.result.connect(self.on_check_result)
        self.check_worker.start()

    def on_check_result(self, r):
        if r.ok:
            self.check_light.setText(
                f"● 可正常打开（HTTP {r.status}，{r.elapsed_ms}ms）")
            self.check_light.setStyleSheet(
                "color:#16a34a;font-weight:bold;")
            self.append_log(f"✓ {r.message}  最终地址：{r.final_url}")
            if r.title and not self.name_edit.text().strip():
                self.name_edit.setText(r.title[:20])
                # 生成一个默认包名建议
                host = QUrl(r.final_url).host().replace("www.", "")
                if host and not self.pkg_edit.text().strip():
                    parts = host.split(".")
                    if len(parts) >= 2:
                        suggested = "com." + parts[-2] + ".app"
                        self.pkg_edit.setText(suggested)
        else:
            self.check_light.setText(f"● 无法打开：{r.message}")
            self.check_light.setStyleSheet(
                "color:#dc2626;font-weight:bold;")
            self.append_log(f"✗ {r.message}")

    def _preview_loaded(self, ok):
        self.preview_hint.setVisible(False)

    def _load_preview(self):
        raw = self.addr_edit.text().strip() or self.url_edit.text().strip()
        if not raw:
            return
        url = normalize_url(raw)
        self.addr_edit.setText(url)
        if self.url_edit.text().strip() != url:
            self.url_edit.setText(url)
        self.preview_hint.setVisible(False)
        self.webview.setUrl(QUrl(url))

    # ---------- 环境状态 ----------
    def refresh_env_status(self):
        info = env.detect()
        states = {"java": bool(info["java"]),
                  "sdk": info["sdk_complete"],
                  "gradle": bool(info["gradle"])}
        for key, ok in states.items():
            dot = self.env_labels[key]
            dot.setText("●")
            dot.setStyleSheet(
                f"color:{'#16a34a' if ok else '#dc2626'};font-size:14px;")
        self.btn_env.setText("环境已就绪 ✓" if info["ready"]
                             else "一键安装构建环境")
        return info

    def install_env(self):
        info = env.detect()
        if info["ready"]:
            QMessageBox.information(self, "提示", "构建环境已经就绪，无需重复安装")
            return
        self._set_busy(True)
        self.append_log("开始自动安装构建环境（JDK / Gradle / Android SDK）...")
        self.env_worker = workers.EnvWorker()
        self.env_worker.log.connect(self.append_log)
        self.env_worker.progress.connect(self._on_env_progress)
        self.env_worker.step.connect(self._on_step)
        self.env_worker.finished_ok.connect(self._on_env_done)
        self.env_worker.failed.connect(self._on_env_fail)
        self.env_worker.start()

    def _on_env_progress(self, pct, text):
        # 环境安装进度映射到右侧总进度（0-70 区间，因为不含打包）
        self.total_progress.setValue(int(pct * 0.7))
        self.progress_text.setText(text)

    def _on_env_done(self):
        self._set_busy(False)
        self.refresh_env_status()
        self.append_log("✓ 构建环境安装完成")
        QMessageBox.information(self, "完成", "构建环境安装完成，可以开始打包了")

    def _on_env_fail(self, err):
        self._set_busy(False)
        self.refresh_env_status()
        self.append_log(f"✗ 环境安装失败：{err}")
        QMessageBox.critical(self, "环境安装失败",
                             f"{err}\n\n可检查网络后重试，或手动安装 JDK17 + Android SDK。")

    # ---------- 打包 ----------
    def _collect_config(self):
        url = normalize_url(self.url_edit.text().strip())
        name = self.name_edit.text().strip()
        pkg = self.pkg_edit.text().strip()
        vername = self.vername_edit.text().strip() or "1.0"
        if not url:
            raise ValueError("请输入网页地址")
        if not name:
            raise ValueError("请输入应用名称")
        from .core.projectgen import validate_package
        perr = validate_package(pkg)
        if perr:
            raise ValueError(perr)
        return {
            "url": url, "app_name": name, "package": pkg,
            "version_code": self.code_spin.value(),
            "version_name": vername,
            "theme_color": self.theme_color,
            "icon_path": self.icon_path,
            "fullscreen": self.chk_fullscreen.isChecked(),
            "keep_screen_on": self.chk_keepon.isChecked(),
        }

    def start_build(self):
        try:
            config = self._collect_config()
        except ValueError as e:
            QMessageBox.warning(self, "配置有误", str(e))
            return

        # 若检测灯不是通过状态，则流程内先检测
        do_check = not self.check_light.text().startswith("● 可正常打开")

        self.log_view.clear()
        for row in self.step_rows:
            row.set_state(workers.STEP_WAIT)
        self.total_progress.setValue(0)
        self.result_box.setVisible(False)
        self._set_busy(True)
        self.append_log(f"开始为「{config['app_name']}」打包 APK ...")

        build_type = "release" if self.combo_build.currentIndex() == 0 else "debug"
        self.worker = workers.BuildWorker(config, do_check, build_type)
        self.worker.log.connect(self.append_log)
        self.worker.progress.connect(self._on_build_progress)
        self.worker.step.connect(self._on_step)
        self.worker.finished_ok.connect(self._on_build_done)
        self.worker.failed.connect(self._on_build_fail)
        self.worker.start()

    def _on_step(self, idx, state):
        self.step_rows[idx].set_state(state)

    def _on_build_progress(self, pct, text):
        self.total_progress.setValue(int(pct))
        self.progress_text.setText(text)

    def _on_build_done(self, result):
        self._set_busy(False)
        self.refresh_env_status()
        self.last_apk = result["apk"]
        self.result_box.setVisible(True)
        self.append_log(f"✓ 打包完成！APK：{result['apk']}")
        QMessageBox.information(
            self, "打包成功",
            f"APK 已生成：\n{result['apk']}\n\n可传到安卓手机安装，或连接手机后点「安装到手机」。")

    def _on_build_fail(self, err):
        self._set_busy(False)
        self.refresh_env_status()
        self.append_log(f"✗ 打包失败：{err}")
        QMessageBox.critical(self, "打包失败",
                             f"{err}\n\n请查看右侧日志定位原因。")

    # ---------- 结果操作 ----------
    def open_apk_dir(self):
        if self.last_apk and Path(self.last_apk).is_file():
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(Path(self.last_apk).parent)))
        else:
            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(env.APKS_DIR)))

    def install_to_phone(self):
        if not self.last_apk or not Path(self.last_apk).is_file():
            QMessageBox.warning(self, "提示", "还没有已生成的 APK")
            return
        adb = env.SDK_DIR / "platform-tools" / "adb.exe"
        if not adb.is_file():
            QMessageBox.warning(self, "提示",
                                "未找到 adb，请先安装构建环境中的 platform-tools")
            return
        self.append_log("正在查找已连接的安卓设备 ...")
        try:
            devs = subprocess.run([str(adb), "devices"], capture_output=True,
                                  text=True, encoding="utf-8",
                                  creationflags=getattr(
                                      subprocess, "CREATE_NO_WINDOW", 0))
            self.append_log(devs.stdout.strip())
            lines = [l for l in devs.stdout.splitlines()[1:]
                     if l.strip().endswith("device")]
            if not lines:
                QMessageBox.warning(
                    self, "未检测到设备",
                    "请用数据线连接安卓手机，并开启「USB 调试」后重试。")
                return
            self.append_log(f"正在安装 {Path(self.last_apk).name} ...")
            r = subprocess.run(
                [str(adb), "install", "-r", self.last_apk],
                capture_output=True, text=True, encoding="utf-8",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.append_log((r.stdout or "") + (r.stderr or ""))
            if r.returncode == 0 and "Success" in (r.stdout or ""):
                QMessageBox.information(self, "成功", "已安装到手机，请在桌面查看")
            else:
                QMessageBox.warning(self, "安装失败",
                                    "请查看日志（可能需要在手机上确认安装）")
        except Exception as e:
            QMessageBox.critical(self, "错误", str(e))
