"""
videdit - 快捷键定义
"""
from PyQt6.QtGui import QKeySequence
from PyQt6.QtCore import Qt


SHORTCUTS = {
    # 文件
    "新建项目":        ("Ctrl+N",         Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_N),
    "打开项目":        ("Ctrl+O",         Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_O),
    "保存项目":        ("Ctrl+S",         Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_S),
    "另存为":          ("Ctrl+Shift+S",   Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier | Qt.Key.Key_S),
    "导入素材":        ("Ctrl+I",         Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_I),
    "导出视频":        ("Ctrl+E",         Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_E),
    "退出":            ("Ctrl+Q",         Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_Q),

    # 编辑
    "撤销":            ("Ctrl+Z",         Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_Z),
    "重做":            ("Ctrl+Y",         Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_Y),
    "剪切":            ("Ctrl+X",         Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_X),
    "复制":            ("Ctrl+C",         Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_C),
    "粘贴":            ("Ctrl+V",         Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_V),
    "删除":            ("Delete",         Qt.Key.Key_Delete),
    "全选":            ("Ctrl+A",         Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_A),

    # 播放
    "播放/暂停":       ("Space",          Qt.Key.Key_Space),
    "停止":            ("K",              Qt.Key.Key_K),
    "倒放":            ("J",              Qt.KeyboardModifier.NoModifier | Qt.Key.Key_J),
    "正放":            ("L",              Qt.KeyboardModifier.NoModifier | Qt.Key.Key_L),
    "上一帧":          ("Left",           Qt.Key.Key_Left),
    "下一帧":          ("Right",          Qt.Key.Key_Right),
    "上一片段":        ("PageUp",         Qt.Key.Key_PageUp),
    "下一片段":        ("PageDown",       Qt.Key.Key_PageDown),
    "跳转开头":        ("Home",           Qt.Key.Key_Home),
    "跳转结尾":        ("End",            Qt.Key.Key_End),

    # 剪辑
    "设置入点":        ("I",              Qt.KeyboardModifier.NoModifier | Qt.Key.Key_I),
    "设置出点":        ("O",              Qt.KeyboardModifier.NoModifier | Qt.Key.Key_O),
    "切割":            ("S",              Qt.KeyboardModifier.NoModifier | Qt.Key.Key_S),
    "合并":            ("Ctrl+M",         Qt.KeyboardModifier.ControlModifier | Qt.Key.Key_M),

    # 视图
    "缩放+":           ("+",              Qt.Key.Key_Plus),
    "缩放-":           ("-",              Qt.Key.Key_Minus),
    "全屏预览":        ("F11",            Qt.Key.Key_F11),
    "切换素材库":      ("F3",             Qt.Key.Key_F3),
    "切换属性面板":    ("F4",             Qt.Key.Key_F4),
}


def get_shortcut(key: str) -> str:
    """获取快捷键文字描述"""
    shortcuts = SHORTCUTS.get(key, ('', None))
    return shortcuts[0] if shortcuts else ''
