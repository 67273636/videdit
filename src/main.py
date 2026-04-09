#!/usr/bin/env python3
"""
videdit - 视频编辑工具
主入口文件
"""
import sys
import os


def _setup_path():
    """设置模块搜索路径，让 import 在开发模式和 PyInstaller 打包模式都能工作"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包模式：--add-data "src:src" 把 src/ 放入 _MEIPASS/src/
        base = sys._MEIPASS
    else:
        # 开发模式：脚本在 src/main.py，往上一级是项目根
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 把项目根加入 sys.path，这样 "from main_window import" 可以找到 src/main_window
    if base not in sys.path:
        sys.path.insert(0, base)


if __name__ == "__main__":
    _setup_path()
    # PyInstaller --add-data "src:src" 打包后，src/ 在 _MEIPASS/src/，
    # 所以这里直接 from main_window 而不是 from src.main_window
    from main_window import main
    main()
