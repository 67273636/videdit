#!/usr/bin/env python3
"""videdit - 主入口"""
import sys, os

def _setup():
    if getattr(sys, 'frozen', False):
        _base = sys._MEIPASS
        _src = os.path.join(_base, 'src')
        # 把项目根加入 sys.path，这样 src/ 里的模块能 import 同级其他模块
        if _base not in sys.path:
            sys.path.insert(0, _base)
    else:
        _base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        _src = os.path.dirname(os.path.abspath(__file__))
        if _base not in sys.path:
            sys.path.insert(0, _base)

    _ffmpeg = os.path.join(_src, 'ffmpeg_bin')
    if _ffmpeg not in os.environ.get('PATH',''):
        os.environ['PATH'] = _ffmpeg + os.pathsep + os.environ.get('PATH','')

    from main_window import main
    main()

if __name__ == '__main__':
    _setup()
