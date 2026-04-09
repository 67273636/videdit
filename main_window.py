"""
videdit - 主窗口（完整增强版）
"""
import os
import copy
import uuid
import subprocess
import threading
import tempfile
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QMenuBar, QMenu, QToolBar, QStatusBar, QFileDialog,
    QMessageBox, QDockWidget, QLabel, QFrame,
    QListWidget, QListWidgetItem, QSplitter,
    QDialog, QGridLayout, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QPushButton, QGroupBox,
    QTextEdit, QTabWidget, QProgressBar, QSlider,
    QScrollArea, QTreeWidget, QTreeWidgetItem,
    QColorDialog, QFontDialog, QInputDialog,
    QWizard, QWizardPage,
    QAbstractItemView,
)
from PyQt6.QtCore import (
    Qt, QTimer, QSize, QPoint, QThread, pyqtSignal,
    QMimeData, QSettings, QUrl,
)
from PyQt6.QtGui import (
    QAction, QKeySequence, QPixmap, QImage, QPainter,
    QPen, QColor, QBrush, QFont, QCursor, QDrag,
    QShortcut, QClipboard,
)
from ffmpeg_core import (
    probe, check_ffmpeg, generate_thumbnail,
    generate_thumbnails_series, detect_scenes,
    extract_audio, export_video,
    get_frame_at_time, format_time, format_size,
    add_text_watermark, build_effect_chain,
    apply_effects as core_apply_effects,
    get_audio_waveform,
)
from project import (
    new_project, load_project, save_project,
    add_clip, remove_clip, get_project_duration,
    set_clip_volume, set_clip_inout, add_marker,
    get_recent_projects, add_recent_project,
    duplicate_clip, apply_clip_effects, project_to_export_clips,
)
from shortcuts import SHORTCUTS

APP_NAME = "videdit"
APP_VERSION = "1.2.0"
SUPPORTED_VIDEO = "Video Files (*.mp4 *.mov *.avi *.mkv *.webm *.wmv *.flv *.m4v *.mpg *.mpeg)"
SUPPORTED_AUDIO = "Audio Files (*.mp3 *.wav *.aac *.flac *.ogg *.m4a *.wma)"
SUPPORTED_ALL = f"{SUPPORTED_VIDEO};;{SUPPORTED_AUDIO}"


# ──────────────────────────────────────────────
# 撤销/重做系统
# ──────────────────────────────────────────────

class HistoryManager:
    """撤销/重做管理器，支持 100 步历史"""

    def __init__(self, max_history=100):
        self._undo_stack = []
        self._redo_stack = []
        self._max = max_history

    def snapshot(self, label: str, state: dict):
        """保存当前状态快照"""
        # 深拷贝，避免引用污染
        snapshot = {
            "label": label,
            "state": copy.deepcopy(state),
        }
        self._undo_stack.append(snapshot)
        if len(self._undo_stack) > self._max:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        return len(self._undo_stack)

    def undo(self) -> dict:
        """撤销，返回上一状态"""
        if not self._undo_stack:
            return None
        state = self._undo_stack.pop()
        self._redo_stack.append(state)
        if self._undo_stack:
            return copy.deepcopy(self._undo_stack[-1]["state"])
        return None

    def redo(self) -> dict:
        """重做，返回下一状态"""
        if not self._redo_stack:
            return None
        state = self._redo_stack.pop()
        self._undo_stack.append(state)
        return copy.deepcopy(state["state"])

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 1

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def describe(self) -> tuple:
        """返回 (撤销描述, 重做描述)"""
        undo_label = self._undo_stack[-2]["label"] if len(self._undo_stack) > 1 else None
        redo_label = self._redo_stack[-1]["label"] if self._redo_stack else None
        return undo_label, redo_label

    def clear(self):
        self._undo_stack.clear()
        self._redo_stack.clear()


# ──────────────────────────────────────────────
# 音频波形组件
# ──────────────────────────────────────────────

class WaveformWidget(QWidget):
    """音频波形显示组件"""

    def __init__(self, parent=None, audio_path=None, color="#4ade80"):
        super().__init__(parent)
        self.audio_path = audio_path
        self.color = QColor(color)
        self.peaks = []  # 波形峰值数据
        self.setMinimumHeight(30)
        self.setMaximumHeight(50)

    def generate_waveform(self):
        """生成波形数据"""
        if not self.audio_path or not os.path.exists(self.audio_path):
            return
        tmp = os.path.join(tempfile.gettempdir(), f"wf_{uuid.uuid4().hex[:8]}.png")
        try:
            ok = get_audio_waveform(self.audio_path, tmp, width=800, height=40)
            if ok and os.path.exists(tmp):
                img = QImage(tmp)
                if not img.isNull():
                    self.peaks = self._extract_peaks(img)
        finally:
            try:
                os.remove(tmp)
            except:
                pass

    def _extract_peaks(self, img: QImage) -> list:
        """从图像提取峰值数据"""
        w = img.width()
        h = img.height()
        peaks = []
        ptr = img.bits()
        if ptr is None:
            return peaks
        ptr.setsize(w * h * 4)
        buf = ptr.tobytes()
        for x in range(min(w, 800)):
            col = buf[x * 4:(x + 1) * 4]
            max_val = max(col[0], col[1], col[2]) if len(col) >= 3 else 0
            peaks.append(max_val / 255.0)
        return peaks

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#1a1a2e"))
        if not self.peaks:
            p.setPen(QColor("#333"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "无波形")
            return
        p.setPen(QColor("#4ade80"))
        w = self.width()
        h = self.height()
        step = len(self.peaks) / w
        for x in range(w):
            idx = int(x * step)
            val = self.peaks[idx] if idx < len(self.peaks) else 0
            bar_h = int(val * h * 0.8)
            p.drawLine(x, h // 2 - bar_h // 2, x, h // 2 + bar_h // 2)


# ──────────────────────────────────────────────
# 时间轴片段组件
# ──────────────────────────────────────────────

class ClipBlock(QWidget):
    """时间轴上的片段方块"""

    clicked = pyqtSignal(str)   # clip_id
    double_clicked = pyqtSignal(str)
    drag_finished = pyqtSignal(str, float)  # clip_id, new_start

    def __init__(self, clip_data, parent=None):
        super().__init__(parent)
        self.clip_data = clip_data
        self.clip_id = clip_data.get("id", "")
        self.dragging = False
        self.drag_start_x = 0
        self.original_start = 0
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self._setup_ui()

    def _setup_ui(self):
        clip = self.clip_data
        colors = ["#3b82f6", "#22c55e", "#a855f7", "#f97316", "#ef4444", "#14b8a6", "#ec4899"]
        idx = clip.get("id", "")[-8:] if clip.get("id") else "0"
        color_int = sum(ord(c) for c in idx)
        self.bg_color = QColor(colors[color_int % len(colors)])
        self.setToolTip(
            f"{clip.get('filename','')}\n"
            f"入点: {format_time(clip.get('in_point', 0))}\n"
            f"出点: {format_time(clip.get('out_point', 0))}\n"
            f"音量: {clip.get('volume', 1.0) * 100:.0f}%"
        )

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()

        # 主体
        c = QColor(self.bg_color)
        c.setAlpha(200)
        p.setBrush(c)
        p.setPen(QPen(Qt.GlobalColor.white, 1))
        p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)

        # 特效条（底部）
        effects = self.clip_data.get("effects", [])
        if effects:
            fx_h = min(6, rect.height() // 4)
            p.setBrush(QColor("#f59e0b"))
            p.drawRect(0, rect.height() - fx_h, rect.width(), fx_h)

        # 文件名
        p.setPen(Qt.GlobalColor.white)
        font = QFont("Arial", 8)
        font.setBold(True)
        p.setFont(font)
        name = self.clip_data.get("filename", "")[:18]
        dur = format_time(self.clip_data.get("out_point", 0) - self.clip_data.get("in_point", 0))[:8]
        p.drawText(rect.adjusted(4, 3, -4, -4), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, name)
        p.setFont(QFont("Arial", 7))
        p.setPen(QColor("#aaa"))
        p.drawText(rect.adjusted(4, 0, -4, -4), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom, dur)

        # 入点手柄
        p.setBrush(QColor("#4ade80"))
        p.drawRect(0, 0, 3, rect.height())

        # 出点手柄
        p.setBrush(QColor("#f87171"))
        p.drawRect(rect.width() - 3, 0, 3, rect.height())

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_start_x = e.globalPosition().x()
            self.original_start = self.clip_data.get("start", 0)

    def mouseMoveEvent(self, e):
        if self.dragging:
            dx = e.globalPosition().x() - self.drag_start_x
            # 更新位置（通过 parent 重新布局）
            pass

    def mouseReleaseEvent(self, e):
        if self.dragging:
            self.dragging = False
            dx = e.globalPosition().x() - self.drag_start_x
            # 通知 parent 重新布局
            if abs(dx) > 2:
                self.drag_finished.emit(self.clip_id, self.original_start)

    def mouseDoubleClickEvent(self, e):
        self.double_clicked.emit(self.clip_id)


# ──────────────────────────────────────────────
# 时间轴组件
# ──────────────────────────────────────────────

class TimelineWidget(QFrame):
    """增强版时间轴面板"""

    PIXELS_PER_SECOND_BASE = 50
    CLIP_HEIGHT = 64
    TRACK_HEIGHT = 72

    clip_selected = pyqtSignal(str)
    clip_double_clicked = pyqtSignal(str)
    playhead_moved = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent
        self.duration = 0.0
        self.zoom = 1.0
        self.pixels_per_second = self.PIXELS_PER_SECOND_BASE
        self.playhead = 0.0
        self.selected_clip_id = None
        self.clips = []
        self.clip_widgets = {}
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("TimelineWidget { background:#0f172a; border-top: 1px solid #1e3a5f; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 时间刻度尺
        self.ruler = TimeRulerEnhanced(self)
        self.ruler.setFixedHeight(28)
        self.ruler.pps_changed.connect(self._on_pps_changed)
        layout.addWidget(self.ruler)

        # 轨道区域（可滚动）
        scroll = QScrollArea()
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(self.TRACK_HEIGHT * 2 + 40)
        scroll.setStyleSheet("QScrollArea { border: none; background:#0f172a; }")

        self.track_area = QWidget()
        self.track_layout = QVBoxLayout(self.track_area)
        self.track_layout.setContentsMargins(0, 4, 0, 4)
        self.track_layout.setSpacing(4)

        # 视频轨
        self.video_track = TrackContainer("视频轨", self)
        self.track_layout.addWidget(self.video_track)

        # 音频轨
        self.audio_track = TrackContainer("音频轨", self)
        self.track_layout.addWidget(self.audio_track)

        scroll.setWidget(self.track_area)
        layout.addWidget(scroll)

        # 控制栏
        ctrl_layout = QHBoxLayout()
        ctrl_layout.setContentsMargins(4, 4, 4, 4)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(1, 20)
        self.zoom_slider.setValue(5)
        self.zoom_slider.setMaximumWidth(140)
        self.zoom_slider.valueChanged.connect(self._on_zoom)
        ctrl_layout.addWidget(QLabel("🔍"))
        ctrl_layout.addWidget(self.zoom_slider)
        ctrl_layout.addSpacing(10)

        self.time_label = QLabel("00:00:00.000 / 00:00:00.000")
        self.time_label.setFont(QFont("monospace", 9))
        self.time_label.setStyleSheet("color:#94a3b8;")
        ctrl_layout.addWidget(self.time_label)
        ctrl_layout.addStretch()

        # 缩略图生成按钮
        gen_btn = QPushButton("📷 生成缩略图")
        gen_btn.setFixedWidth(110)
        gen_btn.clicked.connect(self._gen_thumbnails)
        ctrl_layout.addWidget(gen_btn)

        layout.addLayout(ctrl_layout)

    def _on_zoom(self, val):
        self.zoom = val
        self.pixels_per_second = val * 10
        self.ruler.pixels_per_second = self.pixels_per_second
        self.ruler.update()
        self._rebuild_clips()

    def _on_pps_changed(self, pps):
        self.pixels_per_second = pps
        self._rebuild_clips()

    def set_duration(self, dur: float):
        self.duration = dur
        w = max(int(dur * self.pixels_per_second) + 400, 800)
        self.ruler.duration = dur
        self.ruler.setFixedWidth(w)
        self.track_area.setFixedWidth(w)
        self.ruler.update()

    def set_playhead(self, t: float):
        self.playhead = t
        self.ruler.playhead = t
        # 滚动到播放头可见
        x = int(t * self.pixels_per_second)
        parent = self.findChild(QScrollArea)
        if parent:
            vw = parent.viewport().width()
            parent.horizontalScrollBar().setValue(max(0, x - vw // 2))
        self.ruler.update()
        self._update_time_label()

    def _update_time_label(self):
        self.time_label.setText(
            f"{format_time(self.playhead)} / {format_time(self.duration)}"
        )

    def update_clips(self, clips):
        self.clips = clips
        self._rebuild_clips()

    def _rebuild_clips(self):
        # 清空轨道
        for w in self.findChildren(TrackContainer):
            while w.layout().count():
                child = w.layout().takeAt(0)
                if child and child.widget():
                    child.widget().deleteLater()

        # 重建片段
        for clip in self.clips:
            self._add_clip_widget(clip)

    def _add_clip_widget(self, clip):
        dur = clip.get("out_point", 0) - clip.get("in_point", 0)
        x = int(clip.get("start", 0) * self.pixels_per_second)
        w = max(int(dur * self.pixels_per_second), 20)

        block = ClipBlock(clip)
        block.setFixedSize(w, self.CLIP_HEIGHT)
        block.move(x, 4)
        block.clicked.connect(self._on_clip_clicked)
        block.double_clicked.connect(self._on_clip_double_clicked)
        block.drag_finished.connect(self._on_clip_dragged)
        self.clip_widgets[clip.get("id", "")] = block
        self.video_track.layout().addWidget(block)

    def _on_clip_clicked(self, clip_id):
        self.selected_clip_id = clip_id
        self.clip_selected.emit(clip_id)

    def _on_clip_double_clicked(self, clip_id):
        self.clip_double_clicked.emit(clip_id)

    def _on_clip_dragged(self, clip_id, new_start):
        if self.main and self.main.project:
            for c in self.main.project["clips"]:
                if c.get("id") == clip_id:
                    dur = c.get("out_point", 0) - c.get("in_point", 0)
                    c["start"] = max(0, new_start)
                    c["end"] = c["start"] + dur
                    break
            self.main.history.snapshot("移动片段", self.main.project)
            self.main._save_project()

    def _gen_thumbnails(self):
        """为时间轴片段生成缩略图"""
        from ffmpeg_core import get_frame_accurate_thumbnails
        clips = self.clips
        if not clips:
            return
        # 取第一个片段生成
        clip = clips[0]
        out_dir = tempfile.mkdtemp(prefix="videdit_thumbs_")
        thumbs = get_frame_accurate_thumbnails(clip.get("path", ""), out_dir, interval=5.0)
        if thumbs:
            QMessageBox.information(self, "缩略图",
                f"已生成 {len(thumbs)} 张缩略图到:\n{out_dir}")
        else:
            QMessageBox.warning(self, "缩略图", "缩略图生成失败")

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#0f172a"))


class TimeRulerEnhanced(QWidget):
    """增强版时间刻度尺"""
    pixels_per_second = 50
    duration = 0.0
    playhead = 0.0
    pps_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#1e293b"))

        p.setPen(QColor("#60a5fa"))
        p.setFont(QFont("monospace", 8))

        pps = self.pixels_per_second
        if pps < 20:
            interval = 5.0
        elif pps < 50:
            interval = 2.0
        elif pps > 100:
            interval = 0.5
        else:
            interval = 1.0

        t = 0.0
        while t <= self.duration + 1:
            x = int(t * pps)
            major = (t % (interval * 2)) < 0.01
            h = 14 if major else 7
            p.drawLine(x, 0, x, h)
            if major:
                p.drawText(x + 2, 22, format_time(t)[:8])
            t += interval

        # 播放头
        px = int(self.playhead * pps)
        p.setPen(QColor("#ff3b3b"))
        p.drawLine(px, 0, px, self.height())
        p.setBrush(QColor("#ff3b3b"))
        p.drawPolygon([
            QPoint(px - 7, 0), QPoint(px + 7, 0), QPoint(px, 10)
        ])

        # 鼠标滚轮缩放
        # (在 mousePressEvent 中通过鼠标位置计算)


class TrackContainer(QFrame):
    """轨道容器"""
    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(TimelineWidget.TRACK_HEIGHT)
        self.setStyleSheet(f"""
            TrackContainer {{
                background: #16213e;
                border: 1px solid #1e3a5f;
                border-radius: 4px;
                margin: 2px 4px;
            }}
        """)
        self._name = name
        l = QHBoxLayout(self)
        l.setContentsMargins(2, 2, 2, 2)
        l.setSpacing(4)

        # 轨道标签
        label = QLabel(self._name)
        label.setFixedWidth(50)
        label.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        label.setStyleSheet("color:#60a5fa; background:transparent;")
        l.addWidget(label)

    def paintEvent(self, e):
        super().paintEvent(e)


# ──────────────────────────────────────────────
# 特效对话框
# ──────────────────────────────────────────────

class EffectConfigDialog(QDialog):
    """可视化特效配置对话框"""

    def __init__(self, effect_type: str, current_params: dict, parent=None):
        super().__init__(parent)
        self.effect_type = effect_type
        self.params = dict(current_params)
        self.setWindowTitle(f"特效配置 - {effect_type}")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 参数控件字典
        self.widgets = {}

        if self.effect_type == "speed":
            self._add_slider("倍速", "factor", 0.1, 8.0, self.params.get("factor", 1.0), 0.1, "x")
            self._add_checkbox("音调同步", "pitch_correction", self.params.get("pitch_correction", True))

        elif self.effect_type == "blur":
            self._add_slider("模糊半径", "radius", 1, 50, self.params.get("radius", 5), 1)

        elif self.effect_type == "brightness":
            self._add_slider("亮度", "value", -1.0, 1.0, self.params.get("value", 0.1), 0.05)

        elif self.effect_type == "contrast":
            self._add_slider("对比度", "value", 0.5, 2.5, self.params.get("value", 1.3), 0.05)

        elif self.effect_type == "saturation":
            self._add_slider("饱和度", "value", 0.0, 3.0, self.params.get("value", 1.5), 0.1)

        elif self.effect_type == "hue":
            self._add_slider("色相", "angle", -180, 180, self.params.get("angle", 0), 5, "°")

        elif self.effect_type == "vignette":
            self._add_slider("暗角强度", "angle", 0.1, 3.0, self.params.get("angle", "PI/4"), 0.1)

        elif self.effect_type == "rotate":
            items = ["0° (无旋转)", "90° 顺时针", "180°", "270° 顺时针"]
            vals = [0, 90, 180, 270]
            self._add_combo("旋转角度", "angle", items, vals, self.params.get("angle", 0))

        elif self.effect_type == "zoom":
            self._add_slider("缩放倍数", "factor", 0.5, 5.0, self.params.get("factor", 1.0), 0.1, "x")

        elif self.effect_type == "fade_in":
            self._add_slider("淡入时长", "duration", 0.1, 5.0, self.params.get("duration", 1.0), 0.1, "秒")

        elif self.effect_type == "fade_out":
            self._add_slider("淡出时长", "duration", 0.1, 5.0, self.params.get("duration", 1.0), 0.1, "秒")
            self._add_slider("开始时间", "start_time", 0, 9999, self.params.get("start_time", 0), 0.5, "秒")

        elif self.effect_type == "crop":
            self._add_number("裁剪宽度", "w", 100, 3840, self.params.get("w", 1920))
            self._add_number("裁剪高度", "h", 100, 2160, self.params.get("h", 1080))
            self._add_number("X 偏移", "x", 0, 1920, self.params.get("x", 0))
            self._add_number("Y 偏移", "y", 0, 1080, self.params.get("y", 0))

        elif self.effect_type == "watermark_text":
            self._add_text("水印文字", "text", self.params.get("text", "videdit"))
            self._add_number("字体大小", "fontsize", 10, 200, self.params.get("fontsize", 36))
            self._add_color("文字颜色", "color", self.params.get("color", "#ffffff"))
            self._add_number("X 位置", "x", 0, 1920, self.params.get("x", 20))
            self._add_number("Y 位置", "y", 0, 1080, self.params.get("y", 20))

        elif self.effect_type == "colorbalance":
            self._add_slider("红色阴影", "red_shadow", -1.0, 1.0, self.params.get("red_shadow", 0), 0.05)
            self._add_slider("绿色阴影", "green_shadow", -1.0, 1.0, self.params.get("green_shadow", 0), 0.05)
            self._add_slider("蓝色阴影", "blue_shadow", -1.0, 1.0, self.params.get("blue_shadow", 0), 0.05)

        else:
            layout.addWidget(QLabel(f"特效 '{self.effect_type}' 无可配置参数"))

        # 预览按钮
        preview_btn = QPushButton("👁 预览效果")
        preview_btn.clicked.connect(self._on_preview)
        layout.addWidget(preview_btn)

        # 确认/取消
        btns = QHBoxLayout()
        ok = QPushButton("✓ 确认")
        ok.clicked.connect(self._on_ok)
        cancel = QPushButton("✗ 取消")
        cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def _add_slider(self, label, key, min_v, max_v, default, step, unit=""):
        from PyQt6.QtWidgets import QSlider
        row = QGridLayout()
        lbl = QLabel(f"{label}: {default:.2f}{unit}")
        lbl.setFont(QFont("Arial", 9))
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(int(min_v / step), int(max_v / step))
        slider.setValue(int(default / step))
        slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        slider.valueChanged.connect(
            lambda v: (lbl.setText(f"{label}: {v * step:.2f}{unit}"),
                      self.params.update({key: v * step}))
        )
        row.addWidget(lbl, 0, 0, 1, 2)
        row.addWidget(slider, 1, 0, 1, 2)
        self.layout().addLayout(row)
        self.widgets[key] = slider
        self.params[key] = default

    def _add_number(self, label, key, min_v, max_v, default):
        row = QGridLayout()
        row.addWidget(QLabel(label + ":"), 0, 0)
        sb = QSpinBox()
        sb.setRange(min_v, max_v)
        sb.setValue(int(default))
        sb.valueChanged.connect(lambda v: self.params.update({key: v}))
        row.addWidget(sb, 0, 1)
        self.layout().addLayout(row)
        self.widgets[key] = sb
        self.params[key] = default

    def _add_text(self, label, key, default):
        row = QGridLayout()
        row.addWidget(QLabel(label + ":"), 0, 0)
        le = QLineEdit(default)
        le.textChanged.connect(lambda v: self.params.update({key: v}))
        row.addWidget(le, 0, 1)
        self.layout().addLayout(row)
        self.widgets[key] = le
        self.params[key] = default

    def _add_color(self, label, key, default):
        row = QGridLayout()
        row.addWidget(QLabel(label + ":"), 0, 0)
        color_btn = QPushButton(default)
        color_btn.setStyleSheet(f"background:{default}; color:white;")
        color_btn.clicked.connect(lambda: self._pick_color(key, color_btn))
        row.addWidget(color_btn, 0, 1)
        self.layout().addLayout(row)
        self.widgets[key] = color_btn
        self.params[key] = default

    def _add_combo(self, label, key, items, values, default):
        row = QGridLayout()
        row.addWidget(QLabel(label + ":"), 0, 0)
        combo = QComboBox()
        combo.addItems(items)
        try:
            idx = values.index(default)
            combo.setCurrentIndex(idx)
        except ValueError:
            pass
        combo.currentIndexChanged.connect(
            lambda i: self.params.update({key: values[i]})
        )
        row.addWidget(combo, 0, 1)
        self.layout().addLayout(row)
        self.widgets[key] = combo
        self.params[key] = default

    def _add_checkbox(self, label, key, default):
        row = QHBoxLayout()
        cb = QCheckBox(label)
        cb.setChecked(default)
        cb.toggled.connect(lambda v: self.params.update({key: v}))
        row.addWidget(cb)
        self.layout().addLayout(row)
        self.widgets[key] = cb
        self.params[key] = default

    def _pick_color(self, key, btn):
        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            hex_color = color.name()
            btn.setStyleSheet(f"background:{hex_color}; color:white;")
            self.params[key] = hex_color

    def _on_preview(self):
        QMessageBox.information(self, "预览", "请在预览窗口查看效果")

    def _on_ok(self):
        self.accept()

    def get_result(self):
        return self.params


# ──────────────────────────────────────────────
# 转场选择对话框
# ──────────────────────────────────────────────

class TransitionPickerDialog(QDialog):
    """选择转场效果"""

    TRANSITIONS = [
        ("dissolve",      "溶解",      "两个片段淡入淡出叠加"),
        ("fade",          "淡入淡出",  "前片段淡出 + 后片段淡入"),
        ("wipe_left",     "左滑入",    "后片段从左侧滑入"),
        ("wipe_right",    "右滑入",    "后片段从右侧滑入"),
        ("slide_up",      "上滑入",    "后片段从上方滑入"),
        ("slide_down",    "下滑入",    "后片段从下方滑入"),
        ("zoom",          "缩放转场",  "放大缩小过渡"),
        ("blur_dissolve", "模糊溶解",  "模糊过渡"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_transition = None
        self.transition_duration = 1.0
        self.setWindowTitle("添加转场")
        self.setMinimumWidth(400)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("选择转场效果："))
        self.list_widget = QListWidget()
        for tid, name, desc in self.TRANSITIONS:
            item = QListWidgetItem(f"{name}  —  {desc}")
            item.setData(Qt.ItemDataRole.UserRole, tid)
            self.list_widget.addItem(item)
        self.list_widget.setCurrentRow(0)
        layout.addWidget(self.list_widget)

        dur_layout = QHBoxLayout()
        dur_layout.addWidget(QLabel("转场时长:"))
        self.dur_spin = QDoubleSpinBox()
        self.dur_spin.setRange(0.1, 10.0)
        self.dur_spin.setValue(1.0)
        self.dur_spin.setSuffix(" 秒")
        dur_layout.addWidget(self.dur_spin)
        dur_layout.addStretch()
        layout.addLayout(dur_layout)

        btns = QHBoxLayout()
        ok = QPushButton("✓ 添加转场")
        ok.clicked.connect(self._on_ok)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def _on_ok(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.selected_transition = self.TRANSITIONS[row][0]
            self.transition_duration = self.dur_spin.value()
            self.accept()
        else:
            QMessageBox.warning(self, "提示", "请选择一个转场效果")


# ──────────────────────────────────────────────
# 历史记录面板
# ──────────────────────────────────────────────

class HistoryPanel(QFrame):
    """历史记录面板 (撤销/重做历史列表)"""

    def __init__(self, history_manager, parent=None):
        super().__init__(parent)
        self.history = history_manager
        self.setWindowTitle("历史记录")
        self.setMinimumWidth(200)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(QLabel("历史记录"))

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._on_item_double)
        layout.addWidget(self.list_widget)

        btns = QHBoxLayout()
        undo_btn = QPushButton("↩ 撤销")
        undo_btn.clicked.connect(self._on_undo)
        redo_btn = QPushButton("↪ 重做")
        redo_btn.clicked.connect(self._on_redo)
        btns.addWidget(undo_btn)
        btns.addWidget(redo_btn)
        layout.addLayout(btns)

    def refresh(self):
        self.list_widget.clear()
        for item in self.history._undo_stack:
            self.list_widget.addItem(f"• {item['label']}")
        for item in self.history._redo_stack:
            self.list_widget.addItem(f"○ {item['label']} (可重做)")

    def _on_undo(self):
        self.parent()._undo()

    def _on_redo(self):
        self.parent()._redo()

    def _on_item_double(self, item):
        pass


# ──────────────────────────────────────────────
# 素材库（增强版）
# ──────────────────────────────────────────────

class MediaBrowser(QFrame):
    """增强版素材库"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent
        self._setup_ui()
        self.setAcceptDrops(True)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # 工具栏
        toolbar = QHBoxLayout()
        for label, fn in [("📂 导入", "import"), ("📂 文件夹", "folder"), ("🗑 移除", "remove")]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, f=fn: getattr(self, f"_on_{f}")())
            btn.setFixedWidth(70)
            toolbar.addWidget(btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 视图切换
        self.view_tabs = QTabWidget()
        self.list_view = QListWidget()
        self.list_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_view.itemDoubleClicked.connect(self._on_item_double)

        self.thumb_view = QListWidget()
        self.thumb_view.setViewMode(QListWidget.ViewMode.IconMode)
        self.thumb_view.setIconSize(QSize(100, 75))
        self.thumb_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.thumb_view.itemDoubleClicked.connect(self._on_item_double)

        self.view_tabs.addTab(self.list_view, "📋 列表")
        self.view_tabs.addTab(self.thumb_view, "🖼 缩略图")
        layout.addWidget(self.view_tabs)

        # 片段信息
        self.info_label = QLabel("拖入文件到素材库")
        self.info_label.setStyleSheet("color:#64748b; font-size:11px;")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

    def add_media(self, path: str, thumbnail_path: str = None):
        info = probe(path)
        filename = os.path.basename(path)

        # 列表视图
        item = QListWidgetItem(filename)
        item.setData(Qt.ItemDataRole.UserRole, path)
        if info:
            item.setText(f"{filename}\n  {format_time(info.duration)} | {info.width}x{info.height} | {info.video_codec}")
            item.setToolTip(
                f"路径: {path}\n"
                f"时长: {format_time(info.duration)}\n"
                f"分辨率: {info.width}x{info.height}\n"
                f"帧率: {info.fps:.2f}fps\n"
                f"视频编码: {info.video_codec}\n"
                f"音频编码: {info.audio_codec}\n"
                f"文件大小: {format_size(info.size)}"
            )
        self.list_view.addItem(item)

        # 缩略图视图
        if thumbnail_path and os.path.exists(thumbnail_path):
            thumb_item = QListWidgetItem(QPixmap(thumbnail_path).scaled(100, 75), filename)
            thumb_item.setData(Qt.ItemDataRole.UserRole, path)
            self.thumb_view.addItem(thumb_item)
        else:
            thumb_item = QListWidgetItem(filename)
            thumb_item.setData(Qt.ItemDataRole.UserRole, path)
            self.thumb_view.addItem(thumb_item)

    def _on_item_double(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and self.main:
            info = probe(path)
            clip = add_clip(self.main.project, path, info)
            self.main.history.snapshot("添加片段", self.main.project)
            self.main._refresh_timeline()
            self.main.status_label.setText(f"✓ 已添加: {os.path.basename(path)}")

    def _on_import(self):
        paths, _ = QFileDialog.getOpenFileNames(self.main, "导入素材",
            "", SUPPORTED_ALL)
        self._import_paths(paths)

    def _on_folder(self):
        folder = QFileDialog.getExistingDirectory(self.main, "导入文件夹")
        if folder:
            import glob
            files = []
            for ext in ["*.mp4", "*.mov", "*.avi", "*.mkv", "*.webm", "*.wmv",
                        "*.mp3", "*.wav", "*.aac", "*.flac", "*.ogg"]:
                files += glob.glob(os.path.join(folder, ext))
            self._import_paths(files)

    def _import_paths(self, paths):
        if not paths:
            return
        self.main.status_label.setText(f"正在导入 {len(paths)} 个文件...")
        thumb_dir = tempfile.mkdtemp(prefix="videdit_thumbs_")
        added = 0

        def worker():
            for path in paths:
                info = probe(path)
                # 生成缩略图
                thumb_path = os.path.join(thumb_dir, f"{uuid.uuid4().hex[:8]}.jpg")
                if info:
                    generate_thumbnail(path, thumb_path, width=100)
                    if os.path.exists(thumb_path):
                        pass  # thumb_path passed to add_media
                clip = add_clip(self.main.project, path, info)
                from PyQt6.QtCore import QMetaObject
                QMetaObject.invokeMethod(self, "_add_item",
                    Qt.ConnectionType.QueuedConnection,
                    None)
                added += 1

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        for path in paths[:10]:  # 限制并发
            info = probe(path)
            thumb_path = os.path.join(thumb_dir, f"{uuid.uuid4().hex[:8]}.jpg")
            if info:
                generate_thumbnail(path, thumb_path, width=100)
            self._add_item_sync(path, thumb_path if os.path.exists(thumb_path) else None)
            added += 1
        self.main.status_label.setText(f"✓ 已导入 {added} 个文件")

    @pyqtSlot()
    def _add_item(self):
        pass

    def _add_item_sync(self, path, thumb_path):
        self.add_media(path, thumb_path)
        if self.main:
            self.main._refresh_timeline()

    def _on_remove(self):
        for item in self.list_view.selectedItems() + self.thumb_view.selectedItems():
            row = self.list_view.row(item) if item.listWidget() == self.list_view else -1
            if row >= 0:
                self.list_view.takeItem(row)
            else:
                r = self.thumb_view.row(item)
                if r >= 0:
                    self.thumb_view.takeItem(r)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                self._import_paths([path])


# ──────────────────────────────────────────────
# 属性面板（增强版）
# ──────────────────────────────────────────────

class PropertiesPanel(QFrame):
    """增强版属性面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent
        self.current_clip = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)

        # 片段信息
        info_group = QGroupBox("📄 片段信息")
        info_layout = QGridLayout(info_group)
        self.filename_label = QLabel("-")
        self.filename_label.setStyleSheet("font-weight:bold; color:#60a5fa;")
        self.path_label = QLabel("-")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("color:#64748b; font-size:10px;")
        self.duration_label = QLabel("-")
        self.resolution_label = QLabel("-")
        self.codec_label = QLabel("-")
        info_layout.addWidget(QLabel("文件:"), 0, 0)
        info_layout.addWidget(self.filename_label, 0, 1)
        info_layout.addWidget(QLabel("路径:"), 1, 0)
        info_layout.addWidget(self.path_label, 1, 1)
        info_layout.addWidget(QLabel("时长:"), 2, 0)
        info_layout.addWidget(self.duration_label, 2, 1)
        info_layout.addWidget(QLabel("分辨率:"), 3, 0)
        info_layout.addWidget(self.resolution_label, 3, 1)
        info_layout.addWidget(QLabel("编码:"), 4, 0)
        info_layout.addWidget(self.codec_label, 4, 1)
        inner_layout.addWidget(info_group)

        # 入出点
        io_group = QGroupBox("✂️ 入点 / 出点")
        io_layout = QGridLayout(io_group)
        io_layout.addWidget(QLabel("入点:"), 0, 0)
        self.in_spin = QDoubleSpinBox()
        self.in_spin.setRange(0, 99999)
        self.in_spin.setDecimals(3)
        self.in_spin.setSuffix(" 秒")
        self.in_spin.valueChanged.connect(self._on_io_changed)
        io_layout.addWidget(self.in_spin, 0, 1)

        io_layout.addWidget(QLabel("出点:"), 1, 0)
        self.out_spin = QDoubleSpinBox()
        self.out_spin.setRange(0, 99999)
        self.out_spin.setDecimals(3)
        self.out_spin.setSuffix(" 秒")
        self.out_spin.valueChanged.connect(self._on_io_changed)
        io_layout.addWidget(self.out_spin, 1, 1)

        dur_lbl = QLabel("片段时长: -")
        dur_lbl.setStyleSheet("color:#4ade80;")
        io_layout.addWidget(dur_lbl, 2, 0, 1, 2)
        self.dur_lbl = dur_lbl
        inner_layout.addWidget(io_group)

        # 音量
        vol_group = QGroupBox("🔊 音频")
        vol_layout = QGridLayout(vol_group)
        vol_layout.addWidget(QLabel("音量:"), 0, 0)
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 500)
        self.vol_slider.setValue(100)
        self.vol_slider.valueChanged.connect(self._on_volume_changed)
        vol_layout.addWidget(self.vol_slider, 0, 1)
        self.vol_label = QLabel("100%")
        vol_layout.addWidget(self.vol_label, 0, 2)
        self.mute_cb = QCheckBox("静音")
        self.mute_cb.toggled.connect(self._on_mute_toggled)
        vol_layout.addWidget(self.mute_cb, 1, 1)
        inner_layout.addWidget(vol_group)

        # 速度
        speed_group = QGroupBox("⚡ 播放速度")
        speed_layout = QHBoxLayout(speed_group)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(1, 80)  # 0.1x ~ 8x (×10)
        self.speed_slider.setValue(10)
        self.speed_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        speed_layout.addWidget(self.speed_slider)
        self.speed_label = QLabel("1.0x")
        speed_layout.addWidget(self.speed_label)
        inner_layout.addWidget(speed_group)

        # 特效列表
        fx_group = QGroupBox("🎨 视频效果")
        fx_layout = QVBoxLayout(fx_group)
        self.fx_list = QListWidget()
        self.fx_list.setMaximumHeight(100)
        fx_layout.addWidget(self.fx_list)

        fx_btn_layout = QGridLayout()
        add_btn = QPushButton("+ 添加效果")
        add_btn.clicked.connect(self._add_effect)
        rem_btn = QPushButton("- 移除")
        rem_btn.clicked.connect(self._remove_effect)
        move_up = QPushButton("▲ 上移")
        move_up.clicked.connect(self._move_effect_up)
        move_dn = QPushButton("▼ 下移")
        move_dn.clicked.connect(self._move_effect_down)
        fx_btn_layout.addWidget(add_btn, 0, 0)
        fx_btn_layout.addWidget(rem_btn, 0, 1)
        fx_btn_layout.addWidget(move_up, 1, 0)
        fx_btn_layout.addWidget(move_dn, 1, 1)
        fx_layout.addLayout(fx_btn_layout)
        inner_layout.addWidget(fx_group)

        # 操作按钮
        action_group = QGroupBox("🛠 操作")
        action_layout = QGridLayout(action_group)
        scene_btn = QPushButton("🔍 场景检测")
        scene_btn.clicked.connect(self._detect_scenes)
        extract_btn = QPushButton("🎵 提取音频")
        extract_btn.clicked.connect(self._extract_audio)
        split_btn = QPushButton("✂️ 切割片段")
        split_btn.clicked.connect(self._split_at_current)
        dup_btn = QPushButton("📋 复制片段")
        dup_btn.clicked.connect(self._duplicate_clip)
        action_layout.addWidget(scene_btn, 0, 0)
        action_layout.addWidget(extract_btn, 0, 1)
        action_layout.addWidget(split_btn, 1, 0)
        action_layout.addWidget(dup_btn, 1, 1)
        inner_layout.addWidget(action_group)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    def load_clip(self, clip):
        self.current_clip = clip
        if not clip:
            self._clear()
            return

        self.filename_label.setText(clip.get("filename", "-"))
        self.path_label.setText(clip.get("path", "-")[:50])
        info = probe(clip.get("path", ""))
        dur = clip.get("out_point", 0) - clip.get("in_point", 0)
        self.duration_label.setText(format_time(dur))
        if info:
            self.resolution_label.setText(f"{info.width}x{info.height} @ {info.fps:.2f}fps")
            self.codec_label.setText(f"{info.video_codec} / {info.audio_codec}")

        self.in_spin.setValue(clip.get("in_point", 0))
        self.out_spin.setValue(clip.get("out_point", 0))
        self._update_dur_label()

        vol = clip.get("volume", 1.0)
        self.vol_slider.setValue(int(vol * 100))
        self.vol_label.setText(f"{vol * 100:.0f}%")

        speed = clip.get("speed", 1.0)
        self.speed_slider.setValue(int(speed * 10))
        self.speed_label.setText(f"{speed:.1f}x")

        self.fx_list.clear()
        for fx in clip.get("effects", []):
            p = fx.get("params", {})
            param_str = " | ".join(f"{k}={v}" for k, v in p.items())
            self.fx_list.addItem(f"✨ {fx['type']} {param_str}")

    def _clear(self):
        self.filename_label.setText("-")
        self.path_label.setText("-")
        self.duration_label.setText("-")
        self.resolution_label.setText("-")
        self.codec_label.setText("-")
        self.fx_list.clear()

    def _update_dur_label(self):
        if self.current_clip:
            dur = self.out_spin.value() - self.in_spin.value()
            self.dur_lbl.setText(f"片段时长: {format_time(dur)}")

    def _on_io_changed(self):
        if not self.current_clip or not self.main:
            return
        in_pt = self.in_spin.value()
        out_pt = self.out_spin.value()
        if out_pt <= in_pt:
            out_pt = in_pt + 0.1
            self.out_spin.setValue(out_pt)
        set_clip_inout(self.main.project, self.current_clip["id"], in_pt, out_pt)
        self._update_dur_label()
        self.main._refresh_timeline()
        self.main.history.snapshot("调整入出点", self.main.project)

    def _on_volume_changed(self, val):
        self.vol_label.setText(f"{val}%")
        if self.current_clip and self.main:
            set_clip_volume(self.main.project, self.current_clip["id"], val / 100.0)

    def _on_mute_toggled(self, checked):
        if self.current_clip and self.main:
            vol = 0 if checked else self.vol_slider.value() / 100.0
            set_clip_volume(self.main.project, self.current_clip["id"], vol)

    def _on_speed_changed(self, val):
        speed = val / 10.0
        self.speed_label.setText(f"{speed:.1f}x")
        if self.current_clip and self.main:
            self.current_clip["speed"] = speed
            # 更新 effect 中的 speed
            effects = self.current_clip.get("effects", [])
            speed_fx = next((e for e in effects if e["type"] == "speed"), None)
            if speed_fx:
                speed_fx["params"]["factor"] = speed
            elif speed != 1.0:
                effects.append({"type": "speed", "params": {"factor": speed}})
                self.fx_list.addItem(f"✨ speed | factor={speed}")

    def _add_effect(self):
        if not self.current_clip:
            return
        effects = [
            ("speed", "倍速播放"), ("blur", "模糊"), ("brightness", "亮度"),
            ("contrast", "对比度"), ("saturation", "饱和度"), ("grayscale", "灰度"),
            ("invert", "反色"), ("vignette", "暗角"), ("rotate", "旋转"),
            ("zoom", "缩放"), ("fade_in", "淡入"), ("fade_out", "淡出"),
            ("denoise", "降噪"), ("sharpen", "锐化"), ("hue", "色相"),
            ("watermark_text", "文字水印"),
        ]
        names = [f"{e[1]} ({e[0]})" for e in effects]
        choice, ok = QInputDialog.getItem(self, "添加效果", "选择效果:", names, 0, False)
        if not ok:
            return
        fx_id = effects[names.index(choice)][0]

        params = {}
        if fx_id == "speed":
            params = {"factor": 1.5}
        elif fx_id == "blur":
            params = {"radius": 5}
        elif fx_id == "watermark_text":
            params = {"text": "videdit", "fontsize": 36, "color": "#ffffff", "x": 20, "y": 20}

        dlg = EffectConfigDialog(fx_id, params, self)
        if dlg.exec():
            params = dlg.get_result()
            effect = {"type": fx_id, "params": params}
            self.current_clip.setdefault("effects", []).append(effect)
            apply_clip_effects(self.main.project, self.current_clip["id"], self.current_clip["effects"])
            self.main.history.snapshot(f"添加效果: {fx_id}", self.main.project)
            self._refresh_fx_list()

    def _remove_effect(self):
        row = self.fx_list.currentRow()
        if row < 0 or not self.current_clip:
            return
        self.current_clip.get("effects", []).pop(row)
        apply_clip_effects(self.main.project, self.current_clip["id"], self.current_clip.get("effects", []))
        self.main.history.snapshot("移除效果", self.main.project)
        self._refresh_fx_list()

    def _move_effect_up(self):
        row = self.fx_list.currentRow()
        if row <= 0 or not self.current_clip:
            return
        effects = self.current_clip.get("effects", [])
        effects[row], effects[row - 1] = effects[row - 1], effects[row]
        self._refresh_fx_list()

    def _move_effect_down(self):
        row = self.fx_list.currentRow()
        if row < 0 or not self.current_clip:
            return
        effects = self.current_clip.get("effects", [])
        if row < len(effects) - 1:
            effects[row], effects[row + 1] = effects[row + 1], effects[row]
            self._refresh_fx_list()

    def _refresh_fx_list(self):
        if not self.current_clip:
            return
        self.fx_list.clear()
        for fx in self.current_clip.get("effects", []):
            p = fx.get("params", {})
            param_str = " | ".join(f"{k}={v}" for k, v in p.items())
            self.fx_list.addItem(f"✨ {fx['type']} {param_str}")

    def _detect_scenes(self):
        if not self.current_clip or not self.main:
            return
        path = self.current_clip["path"]
        self.main.status_label.setText("正在检测场景...")
        def worker():
            scenes = detect_scenes(path)
            from PyQt6.QtCore import QMetaObject
            QMetaObject.invokeMethod(self.main, "_on_scenes_detected",
                Qt.ConnectionType.QueuedConnection, object, list)
        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _extract_audio(self):
        if not self.current_clip or not self.main:
            return
        path, _ = QFileDialog.getSaveFileName(self.main, "提取音频",
            self.current_clip["filename"].rsplit(".", 1)[0] + ".mp3",
            "MP3 (*.mp3);;WAV (*.wav);;AAC (*.aac)")
        if not path:
            return
        self.main.status_label.setText("正在提取音频...")
        def worker():
            ok = extract_audio(self.current_clip["path"], path)
            from PyQt6.QtWidgets import QMessageBox
            from PyQt6.QtCore import QMetaObject
            QMetaObject.invokeMethod(self.main, "_on_audio_extracted",
                Qt.ConnectionType.QueuedConnection,
                object, object, object)
        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def _split_at_current(self):
        if self.main:
            self.main._split_at_playhead()

    def _duplicate_clip(self):
        if self.main and self.current_clip:
            new_clip = duplicate_clip(self.main.project, self.current_clip["id"])
            if new_clip:
                self.main.history.snapshot("复制片段", self.main.project)
                self.main._refresh_timeline()


# ──────────────────────────────────────────────
# 预览区
# ──────────────────────────────────────────────

class PreviewArea(QFrame):
    """增强版视频预览"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent
        self.current_pixmap = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # 视频画面
        self.video_label = QLabel()
        self.video_label.setMinimumSize(320, 200)
        self.video_label.setStyleSheet(
            "background:#0a0a0a; color:#444; font-size:16px; border-radius:4px;")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setText("📹 拖入素材开始")
        self.video_label.setScaledContents(False)

        # 右键菜单
        self.video_label.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        fullscreen_action = QAction("全屏预览 (F11)", self)
        fullscreen_action.triggered.connect(self._toggle_fullscreen)
        self.video_label.addAction(fullscreen_action)

        layout.addWidget(self.video_label, 1)

        # 控制栏
        controls = QHBoxLayout()
        controls.setSpacing(4)

        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedWidth(36)
        self.play_btn.setStyleSheet("font-size:14px; padding:2px;")
        self.play_btn.clicked.connect(self._on_play)

        self.stop_btn = QPushButton("■")
        self.stop_btn.setFixedWidth(28)
        self.stop_btn.clicked.connect(self._on_stop)

        self.prev_btn = QPushButton("◀◀")
        self.prev_btn.setFixedWidth(36)
        self.prev_btn.clicked.connect(self._on_prev)

        self.next_btn = QPushButton("▶▶")
        self.next_btn.setFixedWidth(36)
        self.next_btn.clicked.connect(self._on_next)

        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setMinimum(0)
        self.time_slider.setMaximum(1000)
        self.time_slider.sliderMoved.connect(self._on_seek)

        self.time_label = QLabel("00:00:00.000")
        self.time_label.setFont(QFont("monospace", 9))
        self.time_label.setMinimumWidth(100)

        vol_lbl = QLabel("🔊")
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 200)
        self.vol_slider.setValue(100)
        self.vol_slider.setMaximumWidth(100)
        self.vol_label = QLabel("100%")

        controls.addWidget(self.play_btn)
        controls.addWidget(self.stop_btn)
        controls.addWidget(self.prev_btn)
        controls.addWidget(self.next_btn)
        controls.addWidget(self.time_slider)
        controls.addWidget(self.time_label)
        controls.addWidget(vol_lbl)
        controls.addWidget(self.vol_slider)
        controls.addWidget(self.vol_label)
        controls.addStretch()

        layout.addLayout(controls)

    def set_time(self, current: float, total: float):
        if total > 0:
            self.time_slider.blockSignals(True)
            self.time_slider.setValue(int(current / total * 1000))
            self.time_slider.blockSignals(False)
        self.time_label.setText(format_time(current))

    def show_frame(self, pixmap: QPixmap):
        if not pixmap or pixmap.isNull():
            self.show_placeholder()
            return
        self.video_label.setPixmap(pixmap.scaled(
            self.video_label.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def show_placeholder(self, text="📹 拖入素材开始"):
        self.video_label.setText(f'<span style="font-size:48px">🎬</span><br>{text}')

    def _on_play(self):
        if self.main:
            self.main.toggle_playback()

    def _on_stop(self):
        if self.main:
            self.main.stop_playback()
            self.main.seek_to(0)

    def _on_prev(self):
        if self.main:
            self.main.step_frame(-1)

    def _on_next(self):
        if self.main:
            self.main.step_frame(1)

    def _on_seek(self, val):
        if self.main and self.main.project:
            dur = get_project_duration(self.main.project)
            if dur > 0:
                self.main.seek_to(dur * val / 1000.0)

    def _toggle_fullscreen(self):
        if self.main:
            self.main._toggle_fullscreen()


# ──────────────────────────────────────────────
# 导出对话框（增强版）
# ──────────────────────────────────────────────

class ExportDialog(QDialog):
    """完整导出设置对话框"""

    PRESETS = [
        ("网络分享 (MP4 H.264)", "mp4_h264", "1920x1080", 30, 23, "fast", "192k"),
        ("高清存档 (MP4 H.264 HQ)", "mp4_h264", "1920x1080", 30, 18, "slow", "256k"),
        ("微信压缩 (MP4 H.264 小)", "mp4_h264", "1280x720", 30, 28, "fast", "128k"),
        ("4K 超清 (H.265)", "mp4_h265", "3840x2160", 30, 22, "medium", "256k"),
        ("网络视频 (WebM VP9)", "webm", "1920x1080", 30, 25, "medium", "192k"),
        ("原始质量 (无压缩)", "mov", "original", 0, 0, "veryslow", "320k"),
        ("自定义", "", "custom", 0, 23, "fast", "192k"),
    ]

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.main = parent
        self.setWindowTitle("导出设置")
        self.setMinimumWidth(520)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 预设选择
        preset_group = QGroupBox("📦 导出预设")
        preset_layout = QVBoxLayout(preset_group)
        self.preset_combo = QComboBox()
        for name, *_ in self.PRESETS:
            self.preset_combo.addItem(name)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(self.preset_combo)
        layout.addWidget(preset_group)

        # 参数
        param_group = QGroupBox("📋 输出参数")
        param_layout = QGridLayout(param_group)

        param_layout.addWidget(QLabel("格式:"), 0, 0)
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["MP4 (H.264)", "MP4 (H.265/HEVC)", "WebM (VP9)", "MKV", "MOV", "AVI"])
        param_layout.addWidget(self.fmt_combo, 0, 1)

        param_layout.addWidget(QLabel("分辨率:"), 1, 0)
        self.res_combo = QComboBox()
        self.res_combo.addItems(["原始分辨率", "3840x2160 (4K)", "1920x1080 (1080p)",
                                   "1280x720 (720p)", "854x480 (480p)", "自定义..."])
        self.res_combo.currentIndexChanged.connect(self._on_res_changed)
        param_layout.addWidget(self.res_combo, 1, 1)

        param_layout.addWidget(QLabel("帧率:"), 2, 0)
        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["原始帧率", "60 fps", "30 fps", "24 fps", "15 fps"])
        param_layout.addWidget(self.fps_combo, 2, 1)

        param_layout.addWidget(QLabel("质量 (CRF):"), 3, 0)
        self.crf_slider = QSlider(Qt.Orientation.Horizontal)
        self.crf_slider.setRange(0, 51)
        self.crf_slider.setValue(23)
        self.crf_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.crf_label = QLabel("23 (标准)")
        crf_layout = QHBoxLayout()
        crf_layout.addWidget(self.crf_slider)
        crf_layout.addWidget(self.crf_label)
        self.crf_slider.valueChanged.connect(
            lambda v: self.crf_label.setText(f"{v} ({'最佳' if v<18 else '标准' if v<25 else '较小' if v<30 else '最小'})")
        )
        param_layout.addLayout(crf_layout, 3, 1)

        param_layout.addWidget(QLabel("音频码率:"), 4, 0)
        self.audio_bitrate_combo = QComboBox()
        self.audio_bitrate_combo.addItems(["128 kbps", "192 kbps (推荐)", "256 kbps", "320 kbps"])
        param_layout.addWidget(self.audio_bitrate_combo, 4, 1)

        param_layout.addWidget(QLabel("编码预设:"), 5, 0)
        self.preset_combo2 = QComboBox()
        self.preset_combo2.addItems(["ultrafast", "superfast", "veryfast", "faster", "fast (推荐)", "medium", "slow", "slower", "veryslow"])
        self.preset_combo2.setCurrentIndex(4)
        param_layout.addWidget(self.preset_combo2, 5, 1)
        layout.addWidget(param_group)

        # 估算
        dur = get_project_duration(self.project)
        self.info_label = QLabel(
            f"总时长: {format_time(dur)}  |  片段数: {len(self.project.get('clips', []))}"
        )
        self.info_label.setStyleSheet("color:#60a5fa; font-size:12px;")
        layout.addWidget(self.info_label)

        # 按钮
        btns = QHBoxLayout()
        start_btn = QPushButton("🚀 开始导出")
        start_btn.setStyleSheet("background:#3b82f6; color:white; font-weight:bold; padding:6px;")
        start_btn.clicked.connect(self._start_export)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(start_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    def _on_preset_changed(self, idx):
        presets_vals = [
            ("mp4_h264", "1920x1080", 30, 23, "fast", "192k"),
            ("mp4_h264", "1920x1080", 30, 18, "slow", "256k"),
            ("mp4_h264", "1280x720", 30, 28, "fast", "128k"),
            ("mp4_h265", "3840x2160", 30, 22, "medium", "256k"),
            ("webm", "1920x1080", 30, 25, "medium", "192k"),
            ("mov", "original", 0, 0, "veryslow", "320k"),
        ]
        if idx < len(presets_vals):
            fmt_map = {"mp4_h264": 0, "mp4_h265": 1, "webm": 2, "mkv": 3, "mov": 4, "avi": 5}
            fmt, res, fps, crf, preset, abr = presets_vals[idx]
            self.fmt_combo.setCurrentIndex(fmt_map.get(fmt, 0))
            self.crf_slider.setValue(crf)
            self.preset_combo2.setCurrentText(preset)

    def _on_res_changed(self, idx):
        if idx == 5:  # 自定义
            w, ok1 = QInputDialog.getInt(self, "分辨率", "宽度:", 1920, 320, 7680)
            if ok1:
                h, ok2 = QInputDialog.getInt(self, "分辨率", "高度:", 1080, 240, 4320)
                if ok2:
                    self.res_combo.setItemText(5, f"自定义 {w}x{h}")

    def _start_export(self):
        formats = ["mp4_h264", "mp4_h265", "webm", "mkv", "mov", "avi"]
        resolutions = ["original", "3840x2160", "1920x1080", "1280x720", "854x480"]
        fps_vals = [0, 60, 30, 24, 15]
        bitrate_vals = ["128k", "192k", "256k", "320k"]

        path, _ = QFileDialog.getSaveFileName(self.main, "保存视频",
            f"{self.project.get('name', 'output')}.mp4",
            "MP4 (*.mp4);;WebM (*.webm);;MKV (*.mkv)")
        if not path:
            return

        settings = {
            "format": formats[self.fmt_combo.currentIndex()],
            "resolution": resolutions[self.res_combo.currentIndex()],
            "fps": fps_vals[self.fps_combo.currentIndex()],
            "crf": self.crf_slider.value(),
            "preset": self.preset_combo2.currentText(),
            "audio_bitrate": bitrate_vals[self.audio_bitrate_combo.currentIndex()],
        }
        clips = project_to_export_clips(self.project)
        dlg = ExportProgressDialog(clips, path, settings, self.main)
        dlg.exec()
        if dlg.success:
            self.accept()


class ExportProgressDialog(QDialog):
    """导出进度对话框"""

    success = False

    def __init__(self, clips, output_path, settings, parent=None):
        super().__init__(parent)
        self.clips = clips
        self.output_path = output_path
        self.settings = settings
        self.main = parent
        self.cancelled = False
        self.setWindowTitle("正在导出...")
        self.setMinimumWidth(500)
        self._setup_ui()
        QTimer.singleShot(100, self._do_export)

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self.info_label = QLabel(f"输出: {os.path.basename(self.output_path)}")
        layout.addWidget(self.info_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("准备中...")
        layout.addWidget(self.status_label)

        self.time_label = QLabel("剩余时间: 计算中...")
        layout.addWidget(self.time_label)

        self.speed_label = QLabel("速度: -")
        layout.addWidget(self.speed_label)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self._cancel)
        layout.addWidget(self.cancel_btn)

    def _cancel(self):
        self.cancelled = True
        self.reject()

    def _do_export(self):
        total = sum(c["end"] - c["start"] for c in self.clips) if self.clips else 0
        import time
        self._start_time = time.time()
        self._last_update = 0

        def cb(current, total_dur):
            if self.cancelled:
                return
            pct = int(current / total_dur * 100) if total_dur else 0
            elapsed = time.time() - self._start_time
            speed = current / elapsed if elapsed > 0.5 else 0
            remain = (total_dur - current) / speed if speed > 0 else 0
            self.progress_bar.setValue(pct)
            self.status_label.setText(f"已处理: {format_time(current)} / {format_time(total_dur)}")
            self.time_label.setText(f"剩余: ~{format_time(remain)}")
            self.speed_label.setText(f"速度: {speed:.1f}x 实时")

        def worker():
            from ffmpeg_core import export_video
            ok, err = export_video(self.clips, self.output_path, self.settings, cb)
            if self.cancelled:
                return
            if ok:
                self.success = True
                size = os.path.getsize(self.output_path)
                self.status_label.setText("✓ 导出完成！")
                self.progress_bar.setValue(100)
                self.time_label.setText(f"文件大小: {format_size(size)}")
                self.cancel_btn.setText("关闭")
                if self.main:
                    self.main.status_label.setText(f"✓ 导出完成: {self.output_path}")
                    QMessageBox.information(self, "导出完成",
                        f"视频已保存:\n{self.output_path}\n\n大小: {format_size(size)}")
            else:
                self.status_label.setText(f"✗ 导出失败: {err}")
                QMessageBox.critical(self, "导出失败", f"编码失败:\n{err}")

        t = threading.Thread(target=worker, daemon=True)
        t.start()


# ──────────────────────────────────────────────
# 主窗口
# ──────────────────────────────────────────────

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.project = None
        self.project_path = None
        self.current_time = 0.0
        self.is_playing = False
        self.history = HistoryManager(100)
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self._auto_save)
        self.auto_save_timer.start(5 * 60 * 1000)

        self._init_ui()
        self._init_menu()
        self._init_toolbar()
        self._init_shortcuts()
        self._check_ffmpeg()
        self._new_project()

    def _init_ui(self):
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION} — 无标题")
        self.setMinimumSize(1200, 800)
        self.resize(1600, 900)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 预览区
        self.preview_area = PreviewArea(self)
        main_layout.addWidget(self.preview_area, stretch=3)

        # 时间轴
        self.timeline = TimelineWidget(self)
        main_layout.addWidget(self.timeline, stretch=2)

        # 状态栏
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("就绪")
        self.timecode_label = QLabel("00:00:00.000")
        self.clip_count_label = QLabel("0 个片段")
        self.zoom_label = QLabel("缩放: 50%")
        self.history_label = QLabel("")
        self.status_bar.addWidget(self.status_label, 1)
        self.status_bar.addPermanentWidget(self.history_label)
        self.status_bar.addPermanentWidget(self.zoom_label)
        self.status_bar.addPermanentWidget(self.clip_count_label)
        self.status_bar.addPermanentWidget(self.timecode_label)

        # 素材库 dock
        self.media_browser = MediaBrowser(self)
        media_dock = QDockWidget("📂 素材库", self)
        media_dock.setWidget(self.media_browser)
        media_dock.setMinimumWidth(260)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, media_dock)

        # 属性面板 dock
        self.props_panel = PropertiesPanel(self)
        props_dock = QDockWidget("⚙ 属性", self)
        props_dock.setWidget(self.props_panel)
        props_dock.setMinimumWidth(280)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, props_dock)

        # 时间轴点击
        self.timeline.clip_selected.connect(self._on_clip_selected)
        self.timeline.clip_double_clicked.connect(self._on_clip_double_clicked)

        # 播放头更新
        self.playback_timer = QTimer()
        self.playback_timer.timeout.connect(self._playback_tick)

    def _init_menu(self):
        mb = self.menuBar()

        # 文件菜单
        file_menu = mb.addMenu("文件(&F)")
        self._add_action(file_menu, "新建项目", "Ctrl+N", self._new_project)
        self._add_action(file_menu, "打开项目...", "Ctrl+O", self._open_project)
        file_menu.addSeparator()
        self._add_action(file_menu, "保存", "Ctrl+S", self._save_project)
        self._add_action(file_menu, "另存为...", "Ctrl+Shift+S", self._save_project_as)
        file_menu.addSeparator()
        self._add_action(file_menu, "导入素材...", "Ctrl+I", self._import_media)
        self._add_action(file_menu, "导入文件夹...", "", self._import_folder)
        file_menu.addSeparator()
        self._add_action(file_menu, "最近项目", "", self._show_recent)
        self._add_action(file_menu, "项目设置", "", self._show_project_settings)
        file_menu.addSeparator()
        self._add_action(file_menu, "退出", "Ctrl+Q", self.close)

        # 编辑菜单
        edit_menu = mb.addMenu("编辑(&E)")
        self._add_action(edit_menu, "撤销", "Ctrl+Z", self._undo)
        self._add_action(edit_menu, "重做", "Ctrl+Y", self._redo)
        edit_menu.addSeparator()
        self._add_action(edit_menu, "剪切", "Ctrl+X", self._cut_clip)
        self._add_action(edit_menu, "复制", "Ctrl+C", self._copy_clip)
        self._add_action(edit_menu, "粘贴", "Ctrl+V", self._paste_clip)
        self._add_action(edit_menu, "删除片段", "Delete", self._delete_selected)

        # 剪辑菜单
        clip_menu = mb.addMenu("剪辑(&C)")
        self._add_action(clip_menu, "设置入点", "I", self._set_in_point)
        self._add_action(clip_menu, "设置出点", "O", self._set_out_point)
        self._add_action(clip_menu, "在播放头切割", "S", self._split_at_playhead)
        self._add_action(clip_menu, "合并所有片段", "Ctrl+M", self._merge_clips)
        clip_menu.addSeparator()
        self._add_action(clip_menu, "提取音频", "", self._extract_audio)
        self._add_action(clip_menu, "场景检测", "", self._detect_scenes)
        self._add_action(clip_menu, "添加转场", "", self._add_transition)
        clip_menu.addSeparator()
        self._add_action(clip_menu, "复制片段", "", self._copy_clip)
        self._add_action(clip_menu, "删除片段", "Delete", self._delete_selected)

        # 效果菜单
        fx_menu = mb.addMenu("效果(&V)")
        for name, fn in [
            ("倍速播放", lambda: self._quick_effect("speed", {"factor": 2.0})),
            ("慢动作", lambda: self._quick_effect("speed", {"factor": 0.5})),
            ("模糊", lambda: self._quick_effect("blur", {"radius": 8})),
            ("亮度调整", lambda: self._quick_effect("brightness", {"value": 0.15})),
            ("对比度", lambda: self._quick_effect("contrast", {"value": 1.4})),
            ("饱和度+", lambda: self._quick_effect("saturation", {"value": 1.8})),
            ("灰度", lambda: self._quick_effect("grayscale", {})),
            ("暗角", lambda: self._quick_effect("vignette", {"angle": "PI/4"})),
            ("防抖", lambda: self._quick_effect("stabilize", {})),
            ("降噪", lambda: self._quick_effect("denoise", {"strength": 4})),
            ("锐化", lambda: self._quick_effect("sharpen", {"strength": 1.5})),
            ("文字水印", self._add_text_watermark),
            ("淡入", lambda: self._quick_effect("fade_in", {"duration": 1.5})),
            ("淡出", lambda: self._quick_effect("fade_out", {"duration": 1.5, "start_time": 0})),
        ]:
            self._add_action(fx_menu, name, "", fn)

        # 视图菜单
        view_menu = mb.addMenu("视图(&V)")
        self._add_action(view_menu, "放大时间轴", "+", lambda: self.timeline.zoom_slider.setValue(self.timeline.zoom_slider.value() + 1))
        self._add_action(view_menu, "缩小时间轴", "-", lambda: self.timeline.zoom_slider.setValue(self.timeline.zoom_slider.value() - 1))
        self._add_action(view_menu, "全屏预览", "F11", self._toggle_fullscreen)
        self._add_action(view_menu, "跳转到开头", "Home", lambda: self.seek_to(0))
        self._add_action(view_menu, "跳转到结尾", "End", self._go_to_end)

        # 导出菜单
        export_menu = mb.addMenu("导出(&X)")
        self._add_action(export_menu, "导出视频...", "Ctrl+E", self._show_export_dialog)
        self._add_action(export_menu, "导出当前片段", "", self._export_selected_clip)
        self._add_action(export_menu, "导出音频轨道", "", self._extract_audio)

        # 帮助菜单
        help_menu = mb.addMenu("帮助(&H)")
        self._add_action(help_menu, "关于 videdit", "", self._show_about)
        self._add_action(help_menu, "快捷键", "", self._show_shortcuts)

    def _add_action(self, menu, text, shortcut, handler):
        act = QAction(text, self)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        if handler:
            act.triggered.connect(handler)
        menu.addAction(act)
        return act

    def _init_toolbar(self):
        tb = QToolBar("主工具栏")
        tb.setMovable(False)
        tb.setIconSize(QSize(22, 22))
        self.addToolBar(tb)
        tb.setStyleSheet("QToolBar { background:#1e293b; border:none; spacing:2px; padding:2px; }")

        for icon, tooltip, fn in [
            ("📂", "导入素材", self._import_media),
            ("💾", "保存项目", self._save_project),
            ("↩", "撤销", self._undo),
            ("↪", "重做", self._redo),
            ("✂️", "切割", self._split_at_playhead),
            ("🔗", "合并", self._merge_clips),
            ("🎬", "导出", self._show_export_dialog),
        ]:
            btn = QPushButton(icon)
            btn.setToolTip(tooltip)
            btn.setFixedSize(36, 32)
            btn.clicked.connect(fn)
            tb.addWidget(btn)
            tb.addSeparator()

    def _init_shortcuts(self):
        shortcuts_map = {
            "Space": self.toggle_playback,
            "J": lambda: self._jkl("j"),
            "K": lambda: self._jkl("k"),
            "L": lambda: self._jkl("l"),
            "Left": lambda: self.step_frame(-1),
            "Right": lambda: self.step_frame(1),
            "I": self._set_in_point,
            "O": self._set_out_point,
            "S": self._split_at_playhead,
            "Delete": self._delete_selected,
        }
        for key, fn in shortcuts_map.items():
            QShortcut(QKeySequence(key), self).activated.connect(fn)

        # + / - 缩放
        QShortcut(QKeySequence("+"), self).activated.connect(
            lambda: self.timeline.zoom_slider.setValue(self.timeline.zoom_slider.value() + 1))
        QShortcut(QKeySequence("-"), self).activated.connect(
            lambda: self.timeline.zoom_slider.setValue(self.timeline.zoom_slider.value() - 1))

    def _check_ffmpeg(self):
        ok, version = check_ffmpeg()
        if not ok:
            QMessageBox.critical(self, "FFmpeg 未找到",
                "videdit 需要 FFmpeg 才能工作。\n\n"
                "请先安装 FFmpeg：\n"
                "Windows: winget install ffmpeg\n"
                "macOS: brew install ffmpeg\n"
                "Linux: sudo apt install ffmpeg")
            self.status_label.setText("⚠ FFmpeg 未安装")

    # ── 播放控制 ──────────────────────────────────

    def toggle_playback(self):
        if self.is_playing:
            self.stop_playback()
        else:
            self._start_playback()

    def _start_playback(self):
        self.is_playing = True
        self.preview_area.play_btn.setText("⏸")
        dur = get_project_duration(self.project) if self.project else 0
        if dur <= 0:
            self.stop_playback()
            return
        self.playback_timer.start(33)

    def stop_playback(self):
        self.is_playing = False
        self.playback_timer.stop()
        self.preview_area.play_btn.setText("▶")

    def _playback_tick(self):
        if not self.project:
            return
        dur = get_project_duration(self.project)
        if dur <= 0:
            self.stop_playback()
            return
        self.current_time += 0.033
        if self.current_time >= dur:
            self.current_time = 0.0
            self.stop_playback()
        self._update_playhead(self.current_time)

    def step_frame(self, direction: int):
        dur = get_project_duration(self.project) if self.project else 0
        if dur <= 0:
            return
        fps = 30
        self.current_time = max(0, min(self.current_time + direction / fps, dur))
        self._update_playhead(self.current_time)

    def seek_to(self, t: float):
        self.current_time = max(0, t)
        self._update_playhead(self.current_time)

    def _go_to_end(self):
        dur = get_project_duration(self.project) if self.project else 0
        self.seek_to(dur)

    def _update_playhead(self, t: float):
        dur = get_project_duration(self.project) if self.project else 0
        self.timecode_label.setText(format_time(t))
        self.preview_area.set_time(t, dur)
        self.timeline.set_playhead(t)

    def _jkl(self, key: str):
        if key == "j":
            self.step_frame(-1)
        elif key == "k":
            self.stop_playback()
        elif key == "l":
            if self.is_playing:
                self.current_time += 0.067
            else:
                self._start_playback()

    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ── 项目操作 ──────────────────────────────────

    def _new_project(self):
        self.project = new_project("未命名项目")
        self.project_path = None
        self.history.clear()
        self.history.snapshot("新建项目", self.project)
        self.setWindowTitle(f"{APP_NAME} — 未命名项目")
        self._refresh_timeline()
        self.media_browser.list_view.clear()
        self.media_browser.thumb_view.clear()
        self.current_time = 0.0
        self._update_playhead(0)
        self.update_clip_count()
        self.status_label.setText("✓ 新项目已创建")

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开项目", "",
            "videdit Project (*.videdit);;JSON (*.json)")
        if not path:
            return
        proj = load_project(path)
        if proj:
            self.project = proj
            self.project_path = path
            self.history.clear()
            self.history.snapshot("打开项目", self.project)
            self.setWindowTitle(f"{APP_NAME} — {proj['name']}")
            self._load_project_to_ui(proj)
            add_recent_project(path, proj.get('name', ''))
            self.status_label.setText(f"✓ 已打开: {proj['name']}")
        else:
            QMessageBox.warning(self, "打开失败", "无法读取项目文件")

    def _load_project_to_ui(self, proj):
        self._refresh_timeline()
        dur = get_project_duration(proj)
        self.current_time = 0.0
        self._update_playhead(0)
        self.update_clip_count()

    def _save_project(self):
        if not self.project:
            return
        if not self.project_path:
            return self._save_project_as()
        if save_project(self.project, self.project_path):
            self.status_label.setText(f"✓ 已保存: {self.project_path}")

    def _save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "另存为",
            (self.project.get("name", "project") or "project") + ".videdit",
            "videdit Project (*.videdit)")
        if not path:
            return
        self.project_path = path
        if save_project(self.project, path):
            self.setWindowTitle(f"{APP_NAME} — {self.project['name']}")
            self.status_label.setText(f"✓ 已保存: {path}")
            add_recent_project(path, self.project.get("name", ""))

    def _auto_save(self):
        if self.project and self.project_path:
            save_project(self.project, self.project_path)
            self.status_bar.showMessage(f"自动保存: {self.project_path}", 3000)

    def _show_recent(self):
        recent = get