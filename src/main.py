#!/usr/bin/env python3
"""
videdit - 视频编辑工具
主入口文件
"""
import sys
import os

# 开发模式下添加 src 目录到 path
if __name__ == "__main__":
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包模式
        base = sys._MEIPASS
        sys.path.insert(0, os.path.join(base, 'src'))
    else:
        # 开发模式
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from main_window import main
    main()
