#!/usr/bin/env python3
"""
videdit - 视频编辑工具
主入口文件
"""
import sys
import os

# ── 路径设置 ──────────────────────────────────
# PyInstaller 打包：--add-data "src:src" → _MEIPASS/src/ffmpeg_bin/
# 开发模式：脚本在项目根目录
if getattr(sys, 'frozen', False):
    _BASE = sys._MEIPASS
    _SRC = os.path.join(_BASE, 'src')      # ffmpeg_bin/ 在这里
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))
    _SRC = _BASE                            # 开发模式同目录

# ffmpeg_bin/ 在 _SRC/ 下
_ffmpeg_dir = os.path.join(_SRC, 'ffmpeg_bin')
if _ffmpeg_dir not in os.environ.get('PATH', ''):
    os.environ['PATH'] = _ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')

# 项目根目录加入 sys.path
if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

# ── 启动 ──────────────────────────────────────
from main_window import main

if __name__ == '__main__':
    main()
