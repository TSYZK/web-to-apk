# -*- coding: utf-8 -*-
"""Android WebView 壳工程生成器。"""
import re
import shutil
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QImage, QPainter, QColor, QFont, QPainterPath

from . import environment as env
from .webcheck import normalize_url

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "android_template"
PROJECTS_DIR = env.WORKSPACE / "projects"
APKS_DIR = env.WORKSPACE / "apks"

PACKAGE_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
JAVA_KEYWORDS = {"abstract", "assert", "boolean", "break", "byte", "case",
                 "catch", "char", "class", "const", "continue", "default",
                 "do", "double", "else", "enum", "extends", "final",
                 "finally", "float", "for", "goto", "if", "implements",
                 "import", "instanceof", "int", "interface", "long",
                 "native", "new", "package", "private", "protected", "public",
                 "return", "short", "static", "strictfp", "super", "switch",
                 "synchronized", "this", "throw", "throws", "transient",
                 "try", "void", "volatile", "while", "true", "false", "null"}


def validate_package(pkg: str):
    if not PACKAGE_RE.match(pkg or ""):
        return "包名格式不正确，应为如 com.example.myapp（至少两段，小写字母/数字）"
    for part in pkg.split("."):
        if part in JAVA_KEYWORDS:
            return f"包名中不能使用 Java 关键字：{part}"
        if part[0].isdigit():
            return f"包名各段不能以数字开头：{part}"
    return ""


def safe_name(name: str) -> str:
    s = re.sub(r"[^\w一-龥\-]+", "_", (name or "app").strip())
    return s.strip("_") or "app"


def _load_icon_image(icon_path: str | None, size: int, letter: str,
                     theme_rgb: str) -> QImage:
    """加载用户图标并等比缩放进 size 画布；无图标则绘制默认字母图标。"""
    if icon_path:
        src = QImage(icon_path)
        if not src.isNull():
            src = src.convertToFormat(QImage.Format_RGBA8888)
            scaled = src.scaled(size, size, Qt.KeepAspectRatio,
                                Qt.SmoothTransformation)
            canvas = QImage(size, size, QImage.Format_RGBA8888)
            canvas.fill(Qt.transparent)
            p = QPainter(canvas)
            p.drawImage((size - scaled.width()) // 2,
                        (size - scaled.height()) // 2, scaled)
            p.end()
            return canvas
    return _default_icon(size, letter, theme_rgb)


def _default_icon(size: int, letter: str, theme_rgb: str) -> QImage:
    """无自定义图标时：透明底 + 白色圆 + 主题色内圆 + 首字母。"""
    img = QImage(size, size, QImage.Format_RGBA8888)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    margin = int(size * 0.08)
    rect = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
    path = QPainterPath()
    path.addEllipse(rect)
    p.fillPath(path, QColor("white"))
    # 简化地球：主题色圆
    inner = rect.adjusted(size * 0.10, size * 0.10, -size * 0.10, -size * 0.10)
    p.setPen(QColor("#" + theme_rgb))
    p.drawEllipse(inner)
    font = QFont("Arial", int(size * 0.42), QFont.Bold)
    p.setFont(font)
    p.setPen(QColor("white"))
    p.drawText(QRectF(0, 0, size, size), Qt.AlignCenter, letter[:1].upper())
    p.end()
    return img


def _make_foreground(icon_path: str | None, theme_rgb: str, letter: str) -> QImage:
    """adaptive icon 前景 432x432，图形居中并保留安全边距。"""
    canvas = QImage(432, 432, QImage.Format_RGBA8888)
    canvas.fill(Qt.transparent)
    icon = _load_icon_image(icon_path, 286, letter, theme_rgb)
    p = QPainter(canvas)
    p.drawImage((432 - icon.width()) // 2, (432 - icon.height()) // 2, icon)
    p.end()
    return canvas


def _make_legacy_icon(icon_path: str | None, theme_rgb: str, letter: str,
                      size: int) -> QImage:
    """老版本（< API26）启动图标：主题色底 + 居中图形。"""
    img = QImage(size, size, QImage.Format_RGBA8888)
    img.fill(QColor("#" + theme_rgb))
    inner_size = int(size * 0.72)
    icon = _load_icon_image(icon_path, inner_size, letter, theme_rgb)
    p = QPainter(img)
    p.drawImage((size - icon.width()) // 2, (size - icon.height()) // 2, icon)
    p.end()
    return img


def generate_project(config: dict, log=print) -> Path:
    """
    config 字段：
      url, app_name, package, version_code, version_name,
      theme_color(#RRGGBB), icon_path, fullscreen, keep_screen_on
    """
    url = normalize_url(config["url"])
    app_name = config["app_name"].strip()
    package = config["package"].strip()
    theme_rgb = config["theme_color"].lstrip("#")
    pkg_path = package.replace(".", "/")

    err = validate_package(package)
    if err:
        raise ValueError(err)
    if not app_name:
        raise ValueError("应用名称不能为空")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # 工程目录名必须为 ASCII（AGP/aapt 不支持非 ASCII 路径），用包名末段
    dir_base = package.split(".")[-1]
    project_dir = PROJECTS_DIR / f"{safe_name(dir_base)}_{stamp}"
    if project_dir.exists():
        shutil.rmtree(project_dir)
    project_dir.mkdir(parents=True)

    replacements = {
        "__APP_NAME__": app_name,
        "__PACKAGE__": package,
        "__URL__": url,
        "__VERSION_CODE__": str(int(config.get("version_code", 1))),
        "__VERSION_NAME__": str(config.get("version_name", "1.0")),
        "__THEME_RGB__": theme_rgb,
        "__FULLSCREEN__": "true" if config.get("fullscreen") else "false",
        "__KEEP_SCREEN_ON__": "true" if config.get("keep_screen_on") else "false",
    }

    def render(text: str) -> str:
        for k, v in replacements.items():
            text = text.replace(k, v)
        return text

    # 复制并渲染模板
    for src in TEMPLATE_DIR.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(TEMPLATE_DIR)
        parts = []
        for part in rel.parts:
            part = part.replace("PKG_PLACEHOLDER", pkg_path)
            if part.endswith(".tmpl"):
                part = part[:-5]
            parts.append(part)
        dest = project_dir.joinpath(*parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.name.endswith(".tmpl"):
            dest.write_text(render(src.read_text(encoding="utf-8")),
                            encoding="utf-8")
        else:
            shutil.copy2(src, dest)

    # 图标
    log("正在生成应用图标...")
    letter = app_name[:1]
    fg = _make_foreground(config.get("icon_path"), theme_rgb, letter)
    fg_dir = project_dir / "app" / "src" / "main" / "res" / "drawable-nodpi"
    fg_dir.mkdir(parents=True, exist_ok=True)
    fg.save(str(fg_dir / "ic_launcher_foreground.png"), "PNG")

    for dpi, px in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96),
                    ("xxhdpi", 144), ("xxxhdpi", 192)):
        d = project_dir / "app" / "src" / "main" / "res" / f"mipmap-{dpi}"
        d.mkdir(parents=True, exist_ok=True)
        ic = _make_legacy_icon(config.get("icon_path"), theme_rgb, letter, px)
        ic.save(str(d / "ic_launcher.png"), "PNG")
        ic.save(str(d / "ic_launcher_round.png"), "PNG")

    log(f"Android 工程已生成：{project_dir}")
    return project_dir


def write_local_properties(project_dir: Path, sdk_dir: str):
    # Properties 文件中使用正斜杠可避免转义问题
    sdk = sdk_dir.replace("\\", "/")
    (project_dir / "local.properties").write_text(
        f"sdk.dir={sdk}\n", encoding="utf-8")
