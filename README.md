# videdit — 视频编辑工具

![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)
![Python](https://img.shields.io/badge/Python-3.10+-green)
![License](https://img.shields.io/badge/License-MIT-orange)

基于 **PyQt6** + **FFmpeg** 的全功能桌面视频编辑器，支持 Windows EXE 一键导出。

---

## 功能一览

### 🎬 剪辑
- 多轨道时间轴（视频轨 + 音频轨）
- 精确入点/出点裁剪（毫秒级精度）
- 片段切割、拆分、删除、复制、粘贴
- 撤销/重做（50步历史）
- J/K/L 键盘播放控制（倒放/暂停/正放）

### 🎨 22 种视频效果
倍速播放 · 慢动作 · 倒放 · 高斯模糊 · 锐化 · 亮度 · 对比度 · 饱和度 · 色相 · 灰度 · 反色 · 暗角 · 噪点 · 防抖 · 降噪 · 裁剪 · 旋转 · 缩放 · 淡入 · 淡出 · 垂直翻转 · 水平翻转

### 🔊 音频
- 音量调节（0% ~ 500%）
- 淡入/淡出 · 降噪 · 标准化
- 提取音频轨道（MP3/WAV/AAC/FLAC）

### 🌅 转场
溶解 · 滑入 · 推拉 · 缩放 · 模糊溶解 · 黑场过渡

### 📤 导出
- 格式：MP4 (H.264/H.265)、WebM (VP9)、MKV、AVI、MOV
- 分辨率：原始、4K、1080p、720p、480p
- 帧率：60/30/24/15 fps
- 4档质量预设 + CRF 精细控制
- 实时进度条 + 剩余时间

### 📁 项目管理
- `.videdit` 项目文件（双击打开）
- 自动保存（每5分钟）
- EDL 导入/导出

---

## 下载 EXE

👉 **[点击下载 Windows EXE (v1.0.0)](https://github.com/67273636/videdit/releases)**

下载后双击 `videdit.exe` 直接运行，无需安装。

---

## 快捷键

| 键 | 功能 |
|----|------|
| `Space` | 播放 / 暂停 |
| `J` / `K` / `L` | 倒放 / 暂停 / 正放 |
| `←` / `→` | 逐帧移动 |
| `I` / `O` | 设置入点 / 出点 |
| `S` | 在播放头位置切割 |
| `Delete` | 删除选中片段 |
| `Ctrl+Z` / `Ctrl+Y` | 撤销 / 重做 |
| `Ctrl+S` | 保存项目 |
| `Ctrl+E` | 导出 |
| `Ctrl+I` | 导入素材 |
| `+/-` | 时间轴缩放 |

---

## 自行构建

### Windows EXE

```bash
# 1. 克隆
git clone https://github.com/67273636/videdit.git
cd videdit

# 2. 安装依赖
pip install PyQt6 pyinstaller rich

# 3. 构建
pyinstaller --name videdit --onefile --noconsole src/main.py

# 4. 输出
dist/videdit.exe
```

### macOS / Linux

```bash
pip install PyQt6 rich
python3 src/main.py
```

---

## 依赖 FFmpeg

> ⚠️ videdit 需要系统已安装 FFmpeg

```bash
# macOS
brew install ffmpeg

# Windows
winget install ffmpeg
# 或: https://ffmpeg.org/download.html

# Ubuntu/Debian
sudo apt install ffmpeg
```

---

## 技术栈

| 层次 | 技术 |
|------|------|
| GUI | PyQt6 |
| 核心引擎 | FFmpeg |
| 打包 | PyInstaller |
| 构建 | GitHub Actions |

## License

MIT
