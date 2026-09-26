# -*- coding: utf-8 -*-
"""网页转 APK 打包工具 —— 程序入口。"""
import os
import sys
import traceback
from pathlib import Path


def _write_crash_log():
    try:
        p = Path(__file__).resolve().parents[1] / "crash.log"
        p.write_text(traceback.format_exc(), encoding="utf-8")
    except Exception:
        pass


def main():
    # 虚拟机 / 远程桌面环境兼容：禁用 GPU 与沙箱，防止 WebEngine 黑屏崩溃
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS",
                          "--disable-gpu --no-sandbox --enable-unsafe-swiftshader")
    os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtGui import QFont
    from .main_window import MainWindow

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Microsoft YaHei UI", 9))

    # 全局异常兜底弹窗
    def excepthook(etype, value, tb):
        traceback.print_exception(etype, value, tb)
        _write_crash_log()
        QMessageBox.critical(None, "程序异常",
                             f"{value}\n\n详情已写入 crash.log")
    sys.excepthook = excepthook

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
