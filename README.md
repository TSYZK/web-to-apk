# 网页转 APK 打包工具 · Web To APK Packager

![platform](https://img.shields.io/badge/platform-Windows-0078d4)
![python](https://img.shields.io/badge/python-3.10%2B-3776ab)
![license](https://img.shields.io/badge/license-MIT-16a34a)

一个 Windows 桌面工具：**输入一个网页地址，先检测该网页能否正常打开，在内嵌浏览器中预览，然后一键把它打包成安卓 APK 安装包。** 打包出的 App 使用原生 Android WebView 加载网址，和普通 App 一样安装、使用。

---

## ✨ 功能特性

- **网页可用性检测**：HTTP 状态码、响应耗时、页面标题，绿灯/红灯提示；HTTPS 不通时自动回退尝试 HTTP
- **内嵌网页预览**：基于 Chromium 内核（Qt WebEngine），带前进 / 后退 / 刷新 / 地址栏 / 加载进度
- **一键打包 APK**：自动生成原生 Android WebView 壳工程并调用 Gradle 编译
- **构建环境全自动**：首次运行可一键下载配置 JDK 17、Gradle、Android SDK（国内镜像，全部放在程序目录，不污染系统）
- **丰富的 App 配置**：应用名称、包名、版本号 / 版本名、主题色、自定义图标、全屏、保持屏幕常亮、debug/release 构建类型
- **自动签名**：release 包使用自动生成的 keystore 签名，可直接分发安装
- **ADB 直装**：手机开启 USB 调试连线后，可一键安装到设备
- **完整工程输出**：每个 App 的 Android 工程源码都会保存，可用 Android Studio 二次开发

### 生成的 App 内置能力

JavaScript、DOM Storage、文件上传（相机/相册）、摄像头 / 麦克风 / 定位权限申请、下拉刷新、返回键回退网页历史、启动屏（Splash）、主题色状态栏、HTTP 明文与混合内容支持、外部协议（`tel:` `mailto:` 等）跳转系统应用。

---

## 🖥️ 界面

三栏布局：

- **左侧工作栏**：网址输入与检测、应用配置、构建环境状态、开始打包
- **中间网页预览**：实时显示 / 预览打开的网页
- **右侧转换进展**：4 个步骤状态（检测网页 → 生成工程 → 准备环境 → 编译打包）、总进度条、深色实时日志

---

## 🚀 快速开始

### 方式一：直接运行（推荐）

1. 下载或克隆本仓库
2. 双击运行 **`启动打包程序.bat`**
   - 首次启动会自动安装界面依赖 PySide6（约 200MB，需联网）
3. 在左侧输入网址，点击「检测网页」
4. 填写应用名称、包名等配置
5. 在「构建环境」中点击「一键安装构建环境」（仅首次，约 700MB）
6. 点击「开始打包 APK」，成功后 APK 位于 `workspace/apks/`

> 脚本会按以下顺序自动查找 Python：Doubao 自带运行时 → 常见安装目录 → PATH。
> 若提示找不到 Python，请先安装 [Python 3.10+](https://www.python.org/downloads/)（安装时勾选 *Add Python to PATH*）。

### 方式二：从源码运行

```bash
pip install -r requirements.txt
python -m packager.main
```

---

## 📦 使用步骤

1. **① 网页地址**：输入如 `https://m.example.com`，点击「检测网页」
   - 绿灯 = 可正常打开；红灯 = 按提示排查
2. **② 应用配置**：
   - 应用名称：桌面图标下显示的名字
   - 包名：形如 `com.company.myapp`（检测成功后会自动建议）
   - 主题色：状态栏与图标底色；应用图标：可自选方形图片
   - 构建类型：release（默认，可分发）/ debug
3. **③ 构建环境**：点击「一键安装构建环境」
4. **④ 开始打包 APK**：右侧查看实时步骤与日志

---

## 📁 项目结构

```
WebToApk/
├─ 启动打包程序.bat          # Windows 启动脚本（自动找 Python、装依赖）
├─ requirements.txt
├─ 使用说明.txt
├─ packager/
│  ├─ main.py                # 程序入口
│  ├─ main_window.py         # 三栏主界面
│  ├─ workers.py             # 后台线程（检测 / 环境安装 / 构建）
│  ├─ core/
│  │  ├─ webcheck.py         # 网页可用性检测
│  │  ├─ environment.py      # JDK / Gradle / Android SDK 检测与自动安装
│  │  ├─ projectgen.py       # Android 工程生成器（含图标处理）
│  │  └─ builder.py          # Gradle 构建封装与进度解析
│  └─ android_template/      # Android WebView 壳工程模板
└─ workspace/                # 运行时自动生成（已在 .gitignore）
   ├─ tools/                 # 自动下载的 JDK / SDK / Gradle
   ├─ projects/              # 生成的 Android 工程源码
   ├─ apks/                  # 打好的 APK
   └─ gradle-home/           # Gradle 依赖缓存
```

---

## ⚙️ 工作原理与版本

| 组件 | 版本 |
|---|---|
| Android Gradle Plugin | 8.5.2 |
| Gradle | 8.7 |
| JDK | 17 |
| compileSdk / targetSdk | 34 |
| minSdk | 24 |
| GUI | PySide6 (Qt 6.7+) |

构建依赖默认通过阿里云 Maven 镜像拉取，工具链通过华为云 / 腾讯云镜像下载，适合国内网络环境。

---

## ❓ 常见问题

**Q：打包出的 App 打开是空白？**
确认手机能联网；程序已默认允许 HTTP 明文与混合内容；部分站点有移动端 UA 限制，可用手机浏览器先验证。

**Q：环境安装失败？**
多为网络波动，重新点击「一键安装」即可，已下载部分会复用；`sdkmanager` 组件下载失败可多试几次。

**Q：想要完全离线、不联网也能打开的 App？**
当前为在线网址模式（与 PWABuilder 同类）。可在生成的工程中将静态资源放入 `app/src/main/assets` 后改为本地加载。

**Q：APK 怎么发给别人？**
release 版已自动签名，把 `workspace/apks` 里的 apk 发送给安卓用户，点击安装（需允许「安装未知来源应用」）。

---

## 📄 开源协议

本项目基于 [MIT License](LICENSE) 开源，可自由使用、修改与分发，请保留原始版权声明。

## ⚠️ 免责声明

请仅将本工具用于你拥有或被授权的网站；打包与分发 App 时请遵守目标网站的服务条款及当地法律法规。
