# videdit — 完整产品规格说明书

## 1. 项目概述

**项目名称**：videdit
**项目类型**：桌面视频编辑器（GUI）
**核心功能**：基于 FFmpeg 的全功能视频剪辑工具，支持特效、转码、合并、切割，最终打包为单文件 Windows EXE。
**目标用户**：需要轻量级视频编辑的普通用户，无需专业背景。

---

## 2. 技术栈

| 层次 | 技术选型 | 说明 |
|------|---------|------|
| GUI 框架 | PyQt6 | 跨平台，控件丰富 |
| 核心引擎 | FFmpeg (libav*) | 视频处理底层 |
| 打包工具 | PyInstaller | 单文件 EXE 输出 |
| 构建平台 | GitHub Actions | Windows runner 自动构建 |
| Python 版本 | 3.10+ | Windows 原生支持 |

---

## 3. UI 结构

```
┌─────────────────────────────────────────────────────────────┐
│  菜单栏: 文件 | 编辑 | 视图 | 效果 | 导出 | 帮助              │
├─────────────────────────────────────────────────────────────┤
│  工具栏: [导入] [保存] [撤销] [重做] | [切割] [合并] [导出]   │
├──────────────────────┬──────────────────────────────────────┤
│                      │                                      │
│   素材库面板          │       预览窗口                         │
│   (左侧, 可折叠)      │       (ffplay 嵌入式)                │
│   - 文件列表          │       - 播放/暂停/进度条               │
│   - 缩略图            │       - 音量控制                       │
│   - 拖入时间轴        │       - 全屏                          │
│                      │                                      │
├──────────────────────┴──────────────────────────────────────┤
│                                                             │
│   时间轴面板                                                 │
│   - 轨道 1: 视频轨 [clip][clip][clip]                       │
│   - 轨道 2: 音频轨 [audio][audio]                           │
│   - 播放头 (红色竖线)                                        │
│   - 时间刻度 (秒)                                            │
│   - 缩放滑块                                                 │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│   属性面板 (底部, 可折叠)                                    │
│   - 当前片段: 入点/出点/音量/速度                            │
│   - 特效列表                                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 功能模块

### 4.1 素材管理
- 支持格式：mp4, mov, avi, mkv, webm, wmv, mp3, wav, aac, flac, ogg
- 导入方式：文件对话框、文件夹批量、拖拽到素材库
- 自动生成缩略图（使用 FFmpeg）
- 显示：文件名、时长、分辨率、编码格式
- 素材库支持列表/缩略图两种视图
- 右键菜单：删除、查看属性、添加到时间轴

### 4.2 时间轴
- 多轨道支持（视频轨 + 音频轨 + 字幕轨）
- 片段显示：缩略图 + 文件名 + 时长
- 播放头拖拽定位
- 片段操作：选择、移动、裁剪、删除
- 入点/出点拖拽调整
- 鼠标滚轮缩放时间轴
- 双击片段打开属性面板
- 键盘快捷键：Space=播放，J/K/L=倒放/暂停/正放，←/→=逐帧

### 4.3 预览窗口
- 基于 FFplay 的嵌入式预览
- 播放控制：播放/暂停(Space)、停止、上一帧、下一帧
- 进度条：显示播放头位置，可拖拽跳转
- 音量：0-200% 滑块调节
- 时间显示：当前时间 / 总时长
- 全屏播放（F11）
- 按播放头位置实时预览当前帧

### 4.4 剪辑功能
- 入点/出点精确设置（支持键盘输入精确到帧）
- 切割：在播放头位置切割当前片段
- 拆分：按场景检测自动拆分
- 删除：删除选中片段（留空，可填补）
- 合并：将选中片段或全部片段合并输出
- 复制/粘贴片段
- 撤销/重做（50步历史）

### 4.5 视频效果（全部实时预览）

| 效果 | 参数 | 说明 |
|------|------|------|
| 倍速 | 0.1x ~ 8x | 音调同步调整 |
| 慢速 | 0.1x ~ 1x | 慢动作 |
| 倒放 | on/off | 视频+音频同时倒放 |
| 模糊 | 半径 1~50 | 高斯模糊 |
| 锐化 | 强度 0.5~3 | USM锐化 |
| 亮度 | -1.0 ~ +1.0 | 曝光调整 |
| 对比度 | 0.5 ~ 2.0 | 对比度调整 |
| 饱和度 | 0.0 ~ 3.0 | 色彩饱和度 |
| 色相 | -180° ~ +180° | 色相偏移 |
| 灰度 | on/off | 去除色彩 |
| 反色 | on/off | 色彩反转 |
| 暗角 | 角度 0.5~3.0 | Vignette 效果 |
| 噪点 | 强度 0.01~0.1 | 添加噪点 |
| 稳定 | on/off | 视频防抖 |
| 裁剪 | W/H/X/Y | 自定义裁剪 |
| 旋转 | 度数 | 90/180/270/任意角度 |
| 缩放 | 倍数 | 放大/缩小 |
| 叠加文字 | 文字/字体/颜色/位置/大小/时间 | 文字水印/字幕 |

### 4.6 音频处理
- 音量调节：0% ~ 500%
- 静音：on/off
- 淡入/淡出：时长 0~10秒
- 提取音频为 MP3/WAV
- 替换音频轨道
- 降噪（使用 afftdn）
- 音频标准化

### 4.7 转场效果

| 转场 | 说明 |
|------|------|
| 溶解 (Dissolve) | 淡入淡出叠加 |
| 滑入 (Slide Left/Right) | 左右滑入 |
| 推拉 (Push) | 推出/拉入 |
| 缩放 (Zoom) | 放大缩小 |
| 模糊溶解 (Blur Dissolve) | 模糊过渡 |
| 黑场过渡 | 闪黑/闪白 |
| 像素化 | 像素溶解 |

### 4.8 导出设置
- 格式：MP4 (H.264)、MP4 (H.265/HEVC)、WebM (VP9)、AVI、MKV、MOV
- 分辨率：原始、4K、1080p、720p、480p、自定义
- 帧率：原始、60fps、30fps、24fps、15fps、自定义
- 编码质量：CRF 范围 18（最佳）~ 28（最小）
- 音频：MP3、AAC、WAV、FLAC
- 音频码率：128k / 192k / 256k / 320k
- 预设：快速/平衡/质量（对应 ffmpeg preset）
- 导出进度：百分比 + 当前帧 + 预估剩余时间
- 导出完成：通知 + 打开文件夹选项

### 4.9 项目管理
- 项目文件格式：`.videdit` (JSON)
- 自动保存（每5分钟 + 每次重要操作后）
- 最近项目列表
- 项目信息：创建时间、修改时间、总时长、片段数量
- 导入/导出 EDL (Edit Decision List)

### 4.10 快捷键

| 快捷键 | 功能 |
|--------|------|
| Space | 播放/暂停 |
| J | 倒放 |
| K | 暂停 |
| L | 正放（加速） |
| ← / → | 逐帧移动 |
| Home / End | 跳转到开头/结尾 |
| I | 设置入点 |
| O | 设置出点 |
| S | 切割片段 |
| Delete | 删除选中 |
| Ctrl+Z | 撤销 |
| Ctrl+Y | 重做 |
| Ctrl+S | 保存项目 |
| Ctrl+E | 导出 |
| Ctrl+I | 导入素材 |
| Ctrl+C/V | 复制/粘贴片段 |
| F11 | 全屏预览 |
| +/- | 缩放时间轴 |

---

## 5. 文件结构

```
videdit/
├── SPEC.md
├── README.md
├── requirements.txt
├── .gitignore
├── .github/
│   └── workflows/
│       ├── build-windows.yml    # Windows EXE 构建
│       └── build-all.yml        # 多平台构建
├── src/
│   ├── __init__.py
│   ├── main.py                  # 入口
│   ├── ffmpeg_core.py           # FFmpeg 封装（所有核心操作）
│   ├── project.py               # 项目文件读写
│   ├── shortcuts.py             # 快捷键定义
│   ├── main_window.py           # 主窗口
│   ├── timeline_widget.py       # 时间轴控件
│   ├── preview_widget.py        # 预览窗口
│   ├── media_browser.py         # 素材库面板
│   ├── effects_panel.py         # 特效配置面板
│   ├── export_dialog.py          # 导出对话框
│   ├── properties_panel.py      # 属性面板
│   └── styles.qss               # Qt 样式表
└── build/
    └── (PyInstaller 输出)
```

---

## 6. FFmpeg 命令参考

### 6.1 基础操作
```bash
# 获取视频信息
ffprobe -v quiet -print_format json -show_format -show_streams input.mp4

# 切割（精准切割，不重编码）
ffmpeg -i input.mp4 -ss 00:01:00 -to 00:02:00 -c copy output.mp4

# 合并（需要 concat 文件）
ffmpeg -f concat -safe 0 -i list.txt -c copy output.mp4

# 转码
ffmpeg -i input.mp4 -c:v libx264 -preset fast -crf 23 -c:a aac -b:a 128k output.mp4
```

### 6.2 特效滤镜链
```
# 倍速
-vf "setpts=0.5*PTS" -af "atempo=2.0"

# 模糊
-vf "boxblur=5:5"

# 文字叠加
-vf "drawtext=text='Hello':fontsize=48:fontcolor=white:x=100:y=100:enable='between(t,5,10)'"

# 转场（淡入淡出）
-vf "fade=t=in:st=0:d=1,fade=t=out:st=9:d=1"

# 稳定
-vf "deshake"

# 降噪
-af "afftdn=n=noise"

# 灰度
-vf "hue=s=0"

# 亮度/对比度
-vf "eq=brightness=0.1:contrast=1.3"

# 裁剪
-vf "crop=1920:800:0:140"

# 旋转
-vf "rotate=PI/2"
```

---

## 7. 项目文件格式 (.videdit)

```json
{
  "version": "1.0",
  "name": "My Project",
  "created_at": "2026-04-09T20:00:00",
  "modified_at": "2026-04-09T21:00:00",
  "settings": {
    "resolution": "1920x1080",
    "fps": 30,
    "sample_rate": 48000
  },
  "clips": [
    {
      "id": "uuid-string",
      "path": "/path/to/video.mp4",
      "track": 0,
      "start": 0.0,
      "end": 120.5,
      "in_point": 10.0,
      "out_point": 100.0,
      "volume": 1.0,
      "effects": [
        {"type": "speed", "params": {"factor": 1.5}},
        {"type": "brightness", "params": {"value": 0.1}}
      ],
      "transitions": {
        "in": {"type": "dissolve", "duration": 1.0},
        "out": null
      }
    }
  ],
  "audio_clips": [
    {
      "id": "uuid-string",
      "path": "/path/to/audio.mp3",
      "track": 1,
      "start": 0.0,
      "end": 120.0,
      "volume": 0.8
    }
  ]
}
```

---

## 8. 构建与分发

### 8.1 GitHub Actions 自动构建
- 触发条件：推送 tag 或 main 分支更新
- 构建矩阵：Windows (x64)、macOS (x64 + arm64)、Linux (x64)
- 输出物：可执行 EXE/AppImage/dmg
- Artifacts 保留 90 天

### 8.2 PyInstaller 配置
- 单文件模式 (`--onefile`)
- Windows：无控制台窗口（`--noconsole`）
- 包含 FFmpeg 二进制文件
- 启动画面（splash）

---

## 9. 错误处理

| 场景 | 处理方式 |
|------|---------|
| FFmpeg 未安装 | 启动时检测，提示下载链接 |
| 文件格式不支持 | 对话框提示，跳过该文件 |
| 导出磁盘空间不足 | 预估所需空间，提前告警 |
| 编码失败 | 显示 FFmpeg stderr 输出，提示解决方案 |
| 项目文件损坏 | 自动备份恢复，提示用户 |
| 网络超时（在线素材） | 重试 3 次，失败后提示 |

---

## 10. 性能目标

- 启动时间：< 3 秒（含 FFmpeg 检测）
- 缩略图生成：< 1 秒/张（480p）
- 时间轴缩放：60 FPS 流畅
- 预览延迟：< 200ms（已缓存帧）
- 导出速度：参考 FFmpeg 原生速度（可中断续传）
