"""
videdit - 主窗口
"""
import os
import traceback
import tempfile
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QMenuBar, QMenu, QToolBar, QStatusBar, QFileDialog,
    QMessageBox, QDockWidget, QLabel, QShortcut,
    QListWidget, QListWidgetItem, QSplitter, QFrame,
    QDialog, QGridLayout, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QPushButton, QGroupBox,
    QTextEdit, QTabWidget, QProgressBar, QSlider,
    QStyledItemDelegate, QStyleOptionViewItem,
)
from PyQt6.QtCore import (
    Qt, QTimer, QSize, QPoint, QThread, pyqtSignal,
    QMimeData, QSettings, QUrl,
)
from PyQt6.QtGui import (
    QAction, QKeySequence, QPixmap, QImage, QPainter,
    QPen, QColor, QBrush, QFont, QCursor, QDrag,
)
from ffmpeg_core import (
    probe, check_ffmpeg, generate_thumbnail,
    detect_scenes, extract_audio, export_video,
    get_frame_at_time, format_time, format_size,
    add_text_watermark,
)
from project import (
    new_project, load_project, save_project,
    add_clip, remove_clip, get_project_duration,
    set_clip_volume, set_clip_inout, add_marker,
    get_recent_projects, add_recent_project, duplicate_clip,
    apply_clip_effects, project_to_export_clips,
)
from shortcuts import SHORTCUTS
import uuid

APP_NAME = "videdit"
APP_VERSION = "1.0.0"
SUPPORTED_VIDEO = "Video Files (*.mp4 *.mov *.avi *.mkv *.webm *.wmv *.flv *.m4v *.mpg *.mpeg)"
SUPPORTED_AUDIO = "Audio Files (*.mp3 *.wav *.aac *.flac *.ogg *.m4a *.wma)"
SUPPORTED_ALL = f"{SUPPORTED_VIDEO};;{SUPPORTED_AUDIO}"


# ──────────────────────────────────────────────
# 预览区
# ──────────────────────────────────────────────

class PreviewArea(QFrame):
    """视频预览区域"""

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
        self.video_label.setMinimumSize(320, 180)
        self.video_label.setStyleSheet("background:#1a1a2e;color:#888;font-size:14px;")
        self.video_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_label.setText("拖入素材开始编辑")
        self.video_label.setScaledContents(False)

        # 控制栏
        controls = QHBoxLayout()

        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedWidth(40)
        self.play_btn.clicked.connect(self._on_play)

        self.stop_btn = QPushButton("■")
        self.stop_btn.setFixedWidth(30)
        self.stop_btn.clicked.connect(self._on_stop)

        self.prev_frame_btn = QPushButton("◀◀")
        self.prev_frame_btn.setFixedWidth(40)
        self.prev_frame_btn.clicked.connect(self._on_prev_frame)

        self.next_frame_btn = QPushButton("▶▶")
        self.next_frame_btn.setFixedWidth(40)
        self.next_frame_btn.clicked.connect(self._on_next_frame)

        self.time_slider = QSlider(Qt.Orientation.Horizontal)
        self.time_slider.setMinimum(0)
        self.time_slider.setMaximum(1000)
        self.time_slider.sliderMoved.connect(self._on_seek)

        self.time_label = QLabel("00:00:00.000")
        self.time_label.setFont(QFont("monospace"))

        vol_layout = QHBoxLayout()
        vol_layout.addWidget(QLabel("🔊"))
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setMinimum(0)
        self.vol_slider.setMaximum(200)
        self.vol_slider.setValue(100)
        self.vol_slider.setMaximumWidth(100)
        self.vol_label = QLabel("100%")

        controls.addWidget(self.play_btn)
        controls.addWidget(self.stop_btn)
        controls.addWidget(self.prev_frame_btn)
        controls.addWidget(self.next_frame_btn)
        controls.addWidget(self.time_slider)
        controls.addWidget(self.time_label)
        controls.addLayout(vol_layout)
        controls.addWidget(self.vol_slider)
        controls.addWidget(self.vol_label)
        controls.addStretch()

        layout.addWidget(self.video_label, 1)
        layout.addLayout(controls)

    def _on_play(self):
        if self.main:
            self.main.toggle_playback()

    def _on_stop(self):
        if self.main:
            self.main.stop_playback()

    def _on_prev_frame(self):
        if self.main:
            self.main.step_frame(-1)

    def _on_next_frame(self):
        if self.main:
            self.main.step_frame(1)

    def _on_seek(self, val):
        if self.main and self.main.project:
            dur = get_project_duration(self.main.project)
            if dur > 0:
                t = dur * val / 1000.0
                self.main.seek_to(t)

    def set_time(self, current: float, total: float):
        if total > 0:
            self.time_slider.blockSignals(True)
            self.time_slider.setValue(int(current / total * 1000))
            self.time_slider.blockSignals(False)
        self.time_label.setText(format_time(current))

    def show_frame(self, pixmap: QPixmap):
        if pixmap:
            self.video_label.setPixmap(pixmap.scaled(
                self.video_label.size(), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
            self.current_pixmap = pixmap

    def show_placeholder(self, text: str = "拖入素材开始编辑"):
        self.video_label.setText(text)
        self.video_label.setPixmap(QPixmap())


# ──────────────────────────────────────────────
# 时间轴
# ──────────────────────────────────────────────

class TimelineWidget(QFrame):
    """时间轴面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent
        self.playhead_pos = 0.0
        self.duration = 0.0
        self.zoom = 1.0
        self.pixels_per_second = 50
        self.dragging_playhead = False
        self.dragging_clip = None
        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("TimelineWidget { background:#16213e; border-top: 1px solid #0f3460; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 时间轴刻度
        self.ruler = TimeRuler(self)
        self.ruler.setFixedHeight(24)
        layout.addWidget(self.ruler)

        # 轨道区
        scroll = QScrollArea()
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(120)
        scroll.setStyleSheet("QScrollArea { border: none; background:#16213e; }")

        self.track_view = TrackView(self)
        scroll.setWidget(self.track_view)
        scroll.setWidgetResizable(False)
        layout.addWidget(scroll)

        # 缩放控制
        zoom_layout = QHBoxLayout()
        zoom_layout.addWidget(QLabel("缩放:"))
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(1)
        self.zoom_slider.setMaximum(20)
        self.zoom_slider.setValue(5)
        self.zoom_slider.setMaximumWidth(150)
        self.zoom_slider.valueChanged.connect(self._on_zoom)
        zoom_layout.addWidget(self.zoom_slider)
        zoom_layout.addStretch()

        self.add_track_btn = QPushButton("+ 添加视频轨")
        self.add_track_btn.clicked.connect(self._add_track)
        zoom_layout.addWidget(self.add_track_btn)
        layout.addLayout(zoom_layout)

        self.ruler.pps_changed.connect(self._update_pps)

    def _update_pps(self, pps):
        self.pixels_per_second = pps
        self.track_view.pixels_per_second = pps
        self.track_view.update()

    def _on_zoom(self, val):
        self.zoom = val
        self.pixels_per_second = val * 10
        self.ruler.pixels_per_second = self.pixels_per_second
        self.track_view.pixels_per_second = self.pixels_per_second
        self.ruler.update()
        self.track_view.update()
        if self.main:
            self.main.zoom_label.setText(f"缩放: {val * 20}%")

    def _add_track(self):
        pass  # 多轨支持

    def set_duration(self, dur: float):
        self.duration = dur
        w = max(int(dur * self.pixels_per_second) + 200, 800)
        self.track_view.setFixedWidth(w)
        self.ruler.setFixedWidth(w)
        self.ruler.duration = dur
        self.ruler.update()
        self.track_view.update()

    def set_playhead(self, t: float):
        self.playhead_pos = t
        self.ruler.playhead = t
        self.track_view.playhead = t
        self.ruler.update()
        self.track_view.update()

    def update_clips(self, clips):
        self.track_view.clips = clips
        self.track_view.update()


class TimeRuler(QWidget):
    """时间刻度尺"""
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
        p.fillRect(self.rect(), QColor("#1a1a3e"))

        p.setPen(QColor("#4a9eff"))
        p.setFont(QFont("monospace", 9))

        # 刻度
        interval = 1.0
        pps = self.pixels_per_second
        if pps < 20:
            interval = 5.0
        elif pps > 100:
            interval = 0.5

        t = 0.0
        while t <= self.duration + 1:
            x = int(t * pps)
            major = (t % (interval * 2)) < 0.01
            h = 12 if major else 6
            p.drawLine(x, 0, x, h)
            if major:
                p.drawText(x + 3, 14, format_time(t)[:8])
            t += interval

        # 播放头
        px = int(self.playhead * pps)
        p.setPen(QColor("#ff4444"))
        p.drawLine(px, 0, px, self.height())
        p.setBrush(QColor("#ff4444"))
        p.drawPolygon([QPoint(px - 6, 0), QPoint(px + 6, 0), QPoint(px, 8)])


class TrackView(QWidget):
    """轨道视图"""
    pixels_per_second = 50
    playhead = 0.0
    clips = []

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent
        self.setMinimumHeight(80)
        self.setStyleSheet("background:#16213e;")

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 轨道背景
        p.fillRect(self.rect(), QColor("#16213e"))

        # 轨道线
        p.setPen(QColor("#1f4068"))
        p.drawLine(0, 39, self.width(), 39)

        # 绘制片段
        for i, clip in enumerate(self.clips):
            self._draw_clip(p, clip, i)

        # 播放头
        px = int(self.playhead * self.pixels_per_second)
        p.setPen(QColor("#ff4444"))
        p.drawLine(px, 0, px, self.height())

    def _draw_clip(self, p, clip, index):
        pps = self.pixels_per_second
        x = int(clip.get("start", 0) * pps)
        dur = clip.get("out_point", 0) - clip.get("in_point", 0)
        w = max(int(dur * pps), 20)
        y = 2
        h = 36

        # 片段背景
        colors = ["#1f6feb", "#238636", "#8957e5", "#f0883e", "#da3633"]
        color = QColor(colors[index % len(colors)])
        color.setAlpha(180)
        p.setBrush(color)
        p.setPen(QPen(QColor("#ffffff"), 1))
        p.drawRoundedRect(x, y, w, h, 4, 4)

        # 文件名
        p.setPen(Qt.GlobalColor.white)
        font = QFont()
        font.setPointSize(8)
        p.setFont(font)
        name = clip.get("filename", "")[:20]
        dur_str = format_time(dur)[:8]
        p.drawText(x + 4, y + 14, f"{name}  {dur_str}")

        # 入出点标记
        p.setPen(QColor("#4ade80"))
        p.drawLine(x, y + h, x, y + h + 4)
        p.drawLine(x + w, y + h, x + w, y + h + 4)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            t = e.position().x() / self.pixels_per_second
            if self.main and self.main.main:
                self.main.main.seek_to(t)


# ──────────────────────────────────────────────
# 素材库
# ──────────────────────────────────────────────

class MediaBrowser(QFrame):
    """素材库面板"""

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
        import_btn = QPushButton("导入素材")
        import_btn.clicked.connect(lambda: self.main._import_media())
        folder_btn = QPushButton("导入文件夹")
        folder_btn.clicked.connect(lambda: self.main._import_folder())
        remove_btn = QPushButton("移除")
        remove_btn.clicked.connect(self._remove_selected)
        toolbar.addWidget(import_btn)
        toolbar.addWidget(folder_btn)
        toolbar.addWidget(remove_btn)
        layout.addLayout(toolbar)

        # 视图切换
        self.view_tabs = QTabWidget()
        self.view_tabs.addTab(self._make_list_view(), "列表")
        self.view_tabs.addTab(self._make_grid_view(), "缩略图")
        layout.addWidget(self.view_tabs)

        self.list_widget = self.view_tabs.findChild(QListWidget)

    def _make_list_view(self):
        w = QListWidget()
        w.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        w.itemDoubleClicked.connect(self._on_item_double)
        return w

    def _make_grid_view(self):
        w = QListWidget()
        w.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        w.setViewMode(QListWidget.ViewMode.IconMode)
        w.setIconSize(QSize(80, 60))
        return w

    def add_media(self, path: str):
        info = probe(path)
        item = QListWidgetItem(os.path.basename(path))
        item.setData(Qt.ItemDataRole.UserRole, path)
        if info:
            item.setText(f"{os.path.basename(path)}\n{format_time(info.duration)} | {info.width}x{info.height}")
            item.setToolTip(f"路径: {path}\n时长: {format_time(info.duration)}\n编码: {info.video_codec}")
        self.list_widget.addItem(item)

    def _on_item_double(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and self.main:
            clip = add_clip(self.main.project, path, probe(path))
            self.main.timeline.update_clips(self.main.project.get("clips", []))
            dur = get_project_duration(self.main.project)
            self.main.timeline.set_duration(dur)
            self.main.update_clip_count()

    def _remove_selected(self):
        for item in self.list_widget.selectedItems():
            self.list_widget.takeItem(self.list_widget.row(item))

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                self.add_media(path)


# ──────────────────────────────────────────────
# 属性面板
# ──────────────────────────────────────────────

class PropertiesPanel(QFrame):
    """属性面板"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main = parent
        self.current_clip = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        inner = QWidget()
        inner_layout = QVBoxLayout(inner)

        # 基本信息
        info_group = QGroupBox("片段信息")
        info_layout = QGridLayout(info_group)
        info_layout.addWidget(QLabel("文件名:"), 0, 0)
        self.filename_label = QLabel("-")
        info_layout.addWidget(self.filename_label, 0, 1)
        info_layout.addWidget(QLabel("路径:"), 1, 0)
        self.path_label = QLabel("-")
        self.path_label.setWordWrap(True)
        info_layout.addWidget(self.path_label, 1, 1)
        info_layout.addWidget(QLabel("时长:"), 2, 0)
        self.duration_label = QLabel("-")
        info_layout.addWidget(self.duration_label, 2, 1)
        info_layout.addWidget(QLabel("分辨率:"), 3, 0)
        self.resolution_label = QLabel("-")
        info_layout.addWidget(self.resolution_label, 3, 1)
        inner_layout.addWidget(info_group)

        # 入出点
        io_group = QGroupBox("入点 / 出点")
        io_layout = QGridLayout(io_group)
        io_layout.addWidget(QLabel("入点 (秒):"), 0, 0)
        self.in_point_spin = QDoubleSpinBox()
        self.in_point_spin.setRange(0, 99999)
        self.in_point_spin.setDecimals(3)
        self.in_point_spin.valueChanged.connect(self._on_io_changed)
        io_layout.addWidget(self.in_point_spin, 0, 1)
        io_layout.addWidget(QLabel("出点 (秒):"), 1, 0)
        self.out_point_spin = QDoubleSpinBox()
        self.out_point_spin.setRange(0, 99999)
        self.out_point_spin.setDecimals(3)
        self.out_point_spin.valueChanged.connect(self._on_io_changed)
        io_layout.addWidget(self.out_point_spin, 1, 1)
        inner_layout.addWidget(io_group)

        # 音量
        vol_group = QGroupBox("音频")
        vol_layout = QGridLayout(vol_group)
        vol_layout.addWidget(QLabel("音量:"), 0, 0)
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 500)
        self.volume_slider.setValue(100)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        vol_layout.addWidget(self.volume_slider, 0, 1)
        self.volume_label = QLabel("100%")
        vol_layout.addWidget(self.volume_label, 0, 2)
        self.mute_check = QCheckBox("静音")
        self.mute_check.toggled.connect(self._on_mute_toggled)
        vol_layout.addWidget(self.mute_check, 1, 1)
        inner_layout.addWidget(vol_group)

        # 特效
        fx_group = QGroupBox("视频效果")
        fx_layout = QVBoxLayout(fx_group)

        self.fx_list = QListWidget()
        self.fx_list.setMaximumHeight(120)
        fx_layout.addWidget(self.fx_list)

        fx_btn_layout = QHBoxLayout()
        add_fx_btn = QPushButton("+ 添加效果")
        add_fx_btn.clicked.connect(self._add_effect)
        remove_fx_btn = QPushButton("- 移除")
        remove_fx_btn.clicked.connect(self._remove_effect)
        fx_btn_layout.addWidget(add_fx_btn)
        fx_btn_layout.addWidget(remove_fx_btn)
        fx_layout.addLayout(fx_btn_layout)
        inner_layout.addWidget(fx_group)

        # 场景检测
        scene_btn = QPushButton("🔍 场景检测")
        scene_btn.clicked.connect(self._detect_scenes)
        inner_layout.addWidget(scene_btn)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    def load_clip(self, clip):
        self.current_clip = clip
        if not clip:
            return
        self.filename_label.setText(clip.get("filename", "-"))
        self.path_label.setText(clip.get("path", "-")[:50])
        dur = clip.get("out_point", 0) - clip.get("in_point", 0)
        self.duration_label.setText(format_time(dur))
        info = probe(clip.get("path", ""))
        if info:
            self.resolution_label.setText(f"{info.width}x{info.height} @ {info.fps:.2f}fps")
        self.in_point_spin.setValue(clip.get("in_point", 0))
        self.out_point_spin.setValue(clip.get("out_point", dur))

        self.fx_list.clear()
        for fx in clip.get("effects", []):
            self.fx_list.addItem(f"{fx['type']} | {fx.get('params', {})}")

    def _on_io_changed(self):
        if self.current_clip and self.main:
            in_pt = self.in_point_spin.value()
            out_pt = self.out_point_spin.value()
            set_clip_inout(self.main.project, self.current_clip["id"], in_pt, out_pt)
            dur = get_project_duration(self.main.project)
            self.main.timeline.set_duration(dur)
            self.main.timeline.update_clips(self.main.project.get("clips", []))

    def _on_volume_changed(self, val):
        self.volume_label.setText(f"{val}%")
        if self.current_clip and self.main:
            set_clip_volume(self.main.project, self.current_clip["id"], val / 100.0)

    def _on_mute_toggled(self, checked):
        if self.current_clip and self.main:
            self.current_clip["audio_muted"] = checked
            vol = 0 if checked else self.volume_slider.value() / 100.0
            set_clip_volume(self.main.project, self.current_clip["id"], vol)

    def _add_effect(self):
        if not self.current_clip or not self.main:
            return
        from PyQt6.QtWidgets import QInputDialog
        effects = [
            "speed", "blur", "brightness", "contrast", "saturation",
            "grayscale", "invert", "vignette", "denoise", "sharpen",
            "rotate", "zoom", "fade_in", "fade_out", "vflip", "hflip",
        ]
        fx, ok = QInputDialog.getItem(self, "添加效果", "选择效果类型:", effects, 0, False)
        if ok:
            params = {}
            if fx == "speed":
                sp, ok2 = QInputDialog.getDoubleSpinBox(self, "倍速", "倍数 (0.1~8):", 1.0, 0.1, 8, 2)
                if ok2:
                    params = {"factor": sp}
            elif fx == "blur":
                r, ok2 = QInputDialog.getInt(self, "模糊", "半径 (1~50):", 5, 1, 50)
                if ok2:
                    params = {"radius": r}
            elif fx == "brightness":
                v, ok2 = QInputDialog.getDoubleSpinBox(self, "亮度", "值 (-1.0~1.0):", 0.1, -1, 1, 2)
                if ok2:
                    params = {"value": v}
            elif fx == "contrast":
                v, ok2 = QInputDialog.getDoubleSpinBox(self, "对比度", "值 (0.5~2.0):", 1.3, 0.5, 2.0, 2)
                if ok2:
                    params = {"value": v}
            elif fx == "saturation":
                v, ok2 = QInputDialog.getDoubleSpinBox(self, "饱和度", "值 (0~3):", 1.5, 0, 3, 2)
                if ok2:
                    params = {"value": v}
            elif fx == "rotate":
                a, ok2 = QInputDialog.getInt(self, "旋转", "角度:", 90, -360, 360)
                if ok2:
                    params = {"angle": a}

            effect = {"type": fx, "params": params}
            self.current_clip.setdefault("effects", []).append(effect)
            apply_clip_effects(self.main.project, self.current_clip["id"], self.current_clip["effects"])
            self.fx_list.addItem(f"{fx} | {params}")
            self.main.status_label.setText(f"已添加效果: {fx}")

    def _remove_effect(self):
        row = self.fx_list.currentRow()
        if row >= 0 and self.current_clip:
            self.current_clip.get("effects", []).pop(row)
            self.fx_list.takeItem(row)
            if self.main:
                apply_clip_effects(self.main.project, self.current_clip["id"], self.current_clip.get("effects", []))

    def _detect_scenes(self):
        if not self.current_clip or not self.main:
            return
        from PyQt6.QtCore import QThread
        path = self.current_clip["path"]
        self.main.status_label.setText("正在检测场景切换...")
        QTimer.singleShot(100, lambda: self._do_detect(path))

    def _do_detect(self, path):
        scenes = detect_scenes(path)
        if scenes:
            self.main.status_label.setText(f"检测到 {len(scenes)} 个场景切换点")
            for ts in scenes:
                add_marker(self.main.project, ts)
            QMessageBox.information(self, "场景检测", f"检测到 {len(scenes)} 个场景切换:\n" + "\n".join(format_time(t) for t in scenes))
        else:
            self.main.status_label.setText("未检测到场景切换")


# ──────────────────────────────────────────────
# 主窗口（续）
# ──────────────────────────────────────────────

    def _init_menu(self):
        mb = self.menuBar()
        self._add_menu_action(mb.addMenu("文件(&F)"), "新建项目", "Ctrl+N", self._new_project)
        self._add_menu_action(mb.addMenu("文件(&F)"), "打开项目...", "Ctrl+O", self._open_project)
        self._add_menu_action(mb.addMenu("文件(&F)"), "保存", "Ctrl+S", self._save_project)
        self._add_menu_action(mb.addMenu("文件(&F)"), "另存为...", "", self._save_project_as)
        self._add_menu_action(mb.addMenu("文件(&F)"), "导入素材...", "Ctrl+I", self._import_media)
        self._add_menu_action(mb.addMenu("文件(&F)"), "导入文件夹...", "", self._import_folder)
        self._add_menu_action(mb.addMenu("文件(&F)"), "退出", "Ctrl+Q", self.close)

        self._add_menu_action(mb.addMenu("编辑(&E)"), "撤销", "Ctrl+Z", self._undo)
        self._add_menu_action(mb.addMenu("编辑(&E)"), "重做", "Ctrl+Y", self._redo)
        self._add_menu_action(mb.addMenu("编辑(&E)"), "删除片段", "Delete", self._delete_selected)
        self._add_menu_action(mb.addMenu("编辑(&E)"), "复制片段", "Ctrl+C", self._copy_clip)
        self._add_menu_action(mb.addMenu("编辑(&E)"), "粘贴片段", "Ctrl+V", self._paste_clip)

        self._add_menu_action(mb.addMenu("剪辑(&C)"), "设置入点", "I", self._set_in_point)
        self._add_menu_action(mb.addMenu("剪辑(&C)"), "设置出点", "O", self._set_out_point)
        self._add_menu_action(mb.addMenu("剪辑(&C)"), "切割片段", "S", self._split_at_playhead)
        self._add_menu_action(mb.addMenu("剪辑(&C)"), "合并片段", "Ctrl+M", self._merge_clips)
        self._add_menu_action(mb.addMenu("剪辑(&C)"), "提取音频", "", self._extract_audio)
        self._add_menu_action(mb.addMenu("剪辑(&C)"), "场景检测", "", self._detect_scenes)

        fx_menu = mb.addMenu("效果(&V)")
        effects = [
            ("倍速播放", self._apply_speed), ("模糊", self._apply_blur),
            ("亮度调整", self._apply_brightness), ("对比度", self._apply_contrast),
            ("饱和度", self._apply_saturation), ("灰度", self._apply_grayscale),
            ("暗角", self._apply_vignette), ("稳定", self._apply_stabilize),
            ("文字水印", self._add_text_watermark),
        ]
        for name, fn in effects:
            self._add_menu_action(fx_menu, name, "", fn)

        self._add_menu_action(mb.addMenu("导出(&X)"), "导出视频...", "Ctrl+E", self._show_export_dialog)
        self._add_menu_action(mb.addMenu("导出(&X)"), "导出当前片段", "", self._export_selected_clip)

        help_menu = mb.addMenu("帮助(&H)")
        self._add_menu_action(help_menu, "关于 videdit", "", self._show_about)

    def _add_menu_action(self, menu, text, shortcut, handler):
        act = QAction(text, self)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        act.triggered.connect(handler)
        menu.addAction(act)
        return act

    def _init_toolbar(self):
        tb = QToolBar("主工具栏")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        self.addToolBar(tb)
        tb.addAction("📂", self._import_media, "导入素材")
        tb.addAction("💾", self._save_project, "保存")
        tb.addSeparator()
        tb.addAction("✂️", self._split_at_playhead, "切割")
        tb.addAction("🔗", self._merge_clips, "合并")
        tb.addAction("🎬", self._show_export_dialog, "导出")
        tb.addSeparator()
        tb.addAction("⬅️", self._undo, "撤销")
        tb.addAction("➡️", self._redo, "重做")

    def _init_shortcuts(self):
        QShortcut(QKeySequence("Space"), self, self.toggle_playback)
        QShortcut(QKeySequence("J"), self, lambda: self._jkl("j"))
        QShortcut(QKeySequence("K"), self, lambda: self._jkl("k"))
        QShortcut(QKeySequence("L"), self, lambda: self._jkl("l"))
        QShortcut(QKeySequence("Left"), self, lambda: self.step_frame(-1))
        QShortcut(QKeySequence("Right"), self, lambda: self.step_frame(1))
        QShortcut(QKeySequence("I"), self, self._set_in_point)
        QShortcut(QKeySequence("O"), self, self._set_out_point)
        QShortcut(QKeySequence("S"), self, self._split_at_playhead)
        QShortcut(QKeySequence("Delete"), self, self._delete_selected)
        QShortcut(QKeySequence("+"), self, lambda: self.timeline.zoom_slider.setValue(self.timeline.zoom_slider.value() + 1))
        QShortcut(QKeySequence("-"), self, lambda: self.timeline.zoom_slider.setValue(self.timeline.zoom_slider.value() - 1))

    def _check_ffmpeg(self):
        ok, version = check_ffmpeg()
        if not ok:
            QMessageBox.warning(self, "FFmpeg 未找到",
                "videdit 需要 FFmpeg 才能工作。\n\n"
                "请安装 FFmpeg：\n"
                "Windows: winget install ffmpeg\n"
                "macOS: brew install ffmpeg\n"
                "Linux: sudo apt install ffmpeg\n\n"
                "安装后重启本程序。")
            self.status_label.setText("FFmpeg 未安装 - 请先安装 FFmpeg")

    # ── 播放控制 ──────────────────────────────

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
            self.is_playing = False
            self.preview_area.play_btn.setText("▶")
            return
        interval = 33  # ~30fps
        self.playback_timer.start(interval)

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
        frame_dur = 1.0 / fps
        self.current_time = max(0, min(self.current_time + direction * frame_dur, dur))
        self._update_playhead(self.current_time)

    def seek_to(self, t: float):
        self.current_time = max(0, t)
        self._update_playhead(self.current_time)

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
                self.current_time += 0.067  # 1.5x speed
            else:
                self._start_playback()

    # ── 项目操作 ──────────────────────────────

    def _new_project(self):
        self.project = new_project("未命名项目")
        self.project_path = None
        self.setWindowTitle(f"{APP_NAME} - 未命名项目")
        self.timeline.update_clips([])
        self.timeline.set_duration(0)
        self.media_browser.list_widget.clear()
        self.clip_thumbnails.clear()
        self.current_time = 0.0
        self._update_playhead(0)
        self.update_clip_count()
        self.status_label.setText("已创建新项目")

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "打开项目",
            "", "videdit Project (*.videdit);;JSON (*.json)")
        if not path:
            return
        proj = load_project(path)
        if proj:
            self.project = proj
            self.project_path = path
            self.setWindowTitle(f"{APP_NAME} - {proj['name']}")
            self._load_project_to_ui(proj)
            add_recent_project(path, proj.get('name', 'Unknown'))
            self.status_label.setText(f"已打开: {proj['name']}")
        else:
            QMessageBox.warning(self, "打开失败", "无法读取项目文件")

    def _load_project_to_ui(self, proj):
        self.timeline.update_clips(proj.get("clips", []))
        dur = get_project_duration(proj)
        self.timeline.set_duration(dur)
        self.current_time = 0.0
        self._update_playhead(0)
        self.update_clip_count()

    def _save_project(self):
        if not self.project:
            return
        if not self.project_path:
            self._save_project_as()
            return
        if save_project(self.project, self.project_path):
            self.status_label.setText(f"✓ 已保存: {self.project_path}")

    def _save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "另存为",
            self.project.get("name", "project") + ".videdit",
            "videdit Project (*.videdit)")
        if not path:
            return
        self.project_path = path
        if save_project(self.project, path):
            self.setWindowTitle(f"{APP_NAME} - {self.project['name']}")
            self.status_label.setText(f"✓ 已保存: {path}")
            add_recent_project(path, self.project.get("name", ""))

    def _auto_save(self):
        if self.project and self.project_path:
            save_project(self.project, self.project_path)

    def _show_recent(self):
        recent = get_recent_projects()
        if not recent:
            self.status_label.setText("无最近项目")
            return
        items = [f"{r['name']}\n{r['path']}" for r in recent]
        from PyQt6.QtWidgets import QInputDialog
        choice, ok = QInputDialog.getItem(self, "最近项目", "选择项目:", items, 0, False)
        if ok:
            path = recent[items.index(choice)]["path"]
            proj = load_project(path)
            if proj:
                self.project = proj
                self.project_path = path
                self.setWindowTitle(f"{APP_NAME} - {proj['name']}")
                self._load_project_to_ui(proj)

    # ── 素材操作 ──────────────────────────────

    def _import_media(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "导入素材",
            "", SUPPORTED_ALL)
        self._do_import(paths)

    def _import_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹")
        if not folder:
            return
        import glob
        files = []
        for ext in ["*.mp4", "*.mov", "*.avi", "*.mkv", "*.webm", "*.wmv",
                    "*.mp3", "*.wav", "*.aac", "*.flac", "*.ogg"]:
            files += glob.glob(os.path.join(folder, ext))
        self._do_import(files)

    def _do_import(self, paths):
        if not paths:
            return
        added = 0
        for path in paths:
            if not os.path.exists(path):
                continue
            info = probe(path)
            clip = add_clip(self.project, path, info)
            self.media_browser.add_media(path)
            added += 1
        self.timeline.update_clips(self.project.get("clips", []))
        dur = get_project_duration(self.project)
        self.timeline.set_duration(dur)
        self.update_clip_count()
        self.status_label.setText(f"已导入 {added} 个文件")
        self._save_project()

    def _extract_audio(self):
        clips = self.project.get("clips", [])
        if not clips:
            QMessageBox.information(self, "提示", "时间轴上没有片段")
            return
        clip = clips[0]
        path, _ = QFileDialog.getSaveFileName(self, "保存音频",
            clip["filename"].rsplit(".", 1)[0] + ".mp3",
            "MP3 (*.mp3);;WAV (*.wav)")
        if not path:
            return
        self.status_label.setText("正在提取音频...")
        from PyQt6.QtCore import QThread
        class Worker(QThread):
            done = pyqtSignal(bool, str)
            def run(self):
                ok = extract_audio(clip["path"], path)
                self.done.emit(ok, path)
        w = Worker(self)
        w.done.connect(lambda ok, p: (
            self.status_label.setText(f"{'✓' if ok else '✗'} 音频 {'已保存' if ok else '提取失败'}: {p}"),
            QMessageBox.information(self, "完成", f"音频已保存到:\n{p}") if ok else None
        ))
        w.start()

    def update_clip_count(self):
        n = len(self.project.get("clips", [])) if self.project else 0
        self.clip_count_label.setText(f"{n} 个片段")

    # ── 剪辑操作 ──────────────────────────────

    def _set_in_point(self):
        if self.project and self.project.get("clips"):
            clip = self.project["clips"][0]
            clip["in_point"] = self.current_time - clip.get("start", 0)
            self.status_label.setText(f"入点: {format_time(self.current_time)}")

    def _set_out_point(self):
        if self.project and self.project.get("clips"):
            clip = self.project["clips"][0]
            clip["out_point"] = self.current_time - clip.get("start", 0)
            dur = get_project_duration(self.project)
            self.timeline.set_duration(dur)
            self.status_label.setText(f"出点: {format_time(self.current_time)}")

    def _split_at_playhead(self):
        if not self.project or not self.project.get("clips"):
            return
        clips = self.project["clips"]
        split_time = self.current_time
        # 找到包含播放头的片段
        for clip in clips:
            if clip["start"] <= split_time <= clip["end"]:
                # 在此处切割
                in_pt = clip["in_point"]
                out_pt = clip["out_point"]
                dur = out_pt - in_pt
                split_relative = split_time - clip["start"]
                new_in_pt = in_pt + split_relative
                new_out_pt = out_pt
                clip["out_point"] = new_in_pt
                clip["end"] = split_time
                new_clip = {
                    "id": str(uuid.uuid4()),
                    "path": clip["path"],
                    "filename": clip["filename"],
                    "track": clip.get("track", 0),
                    "start": split_time,
                    "end": clip["start"] + dur,
                    "in_point": new_in_pt,
                    "out_point": new_out_pt,
                    "volume": clip.get("volume", 1.0),
                    "effects": [],
                    "audio_muted": clip.get("audio_muted", False),
                    "speed": clip.get("speed", 1.0),
                }
                self.project["clips"].append(new_clip)
                self.timeline.update_clips(self.project["clips"])
                dur_total = get_project_duration(self.project)
                self.timeline.set_duration(dur_total)
                self._save_project()
                self.status_label.setText(f"✓ 已在 {format_time(split_time)} 切割")
                return

    def _delete_selected(self):
        if not self.project or not self.project.get("clips"):
            return
        if self.project["clips"]:
            removed = self.project["clips"].pop(0)
            self.timeline.update_clips(self.project["clips"])
            dur = get_project_duration(self.project)
            self.timeline.set_duration(dur)
            self.update_clip_count()
            self._save_project()
            self.status_label.setText(f"已删除: {removed.get('filename', '')}")

    def _copy_clip(self):
        if self.project and self.project.get("clips"):
            self._copied_clip = self.project["clips"][-1] if self.project["clips"] else None

    def _paste_clip(self):
        if hasattr(self, "_copied_clip") and self._copied_clip and self.project:
            new_c = duplicate_clip(self.project, self._copied_clip["id"])
            if new_c:
                self.timeline.update_clips(self.project["clips"])
                dur = get_project_duration(self.project)
                self.timeline.set_duration(dur)
                self._save_project()
                self.status_label.setText("✓ 片段已粘贴")

    def _merge_clips(self):
        if not self.project or len(self.project.get("clips", [])) < 2:
            QMessageBox.information(self, "提示", "需要至少 2 个片段才能合并")
            return
        out_path, _ = QFileDialog.getSaveFileName(self, "合并导出",
            "merged_output.mp4", "MP4 (*.mp4)")
        if not out_path:
            return
        self._do_export(out_path, settings={
            "format": "mp4_h264", "resolution": "1920x1080",
            "fps": 30, "crf": 23, "preset": "fast",
            "audio_bitrate": "192k",
        })

    def _detect_scenes(self):
        clips = self.project.get("clips", []) if self.project else []
        if not clips:
            self.status_label.setText("无片段可检测")
            return
        clip = clips[0]
        scenes = detect_scenes(clip["path"])
        if scenes:
            for ts in scenes:
                add_marker(self.project, clip["start"] + ts)
            QMessageBox.information(self, "场景检测",
                f"检测到 {len(scenes)} 个场景:\n" +
                "\n".join(format_time(clip["start"] + t) for t in scenes[:20]))
            self.status_label.setText(f"检测到 {len(scenes)} 个场景切换")
        else:
            self.status_label.setText("未检测到场景切换")

    def _undo(self):
        self.status_label.setText("撤销 (需实现历史记录)")

    def _redo(self):
        self.status_label.setText("重做 (需实现历史记录)")

    # ── 效果 ──────────────────────────────────

    def _apply_speed(self):
        clips = self.project.get("clips", []) if self.project else []
        if clips:
            self.props_panel.load_clip(clips[0])
            self.props_panel._add_effect()

    def _apply_blur(self): self._quick_effect("blur", {"radius": 5})
    def _apply_brightness(self): self._quick_effect("brightness", {"value": 0.15})
    def _apply_contrast(self): self._quick_effect("contrast", {"value": 1.3})
    def _apply_saturation(self): self._quick_effect("saturation", {"value": 1.5})
    def _apply_grayscale(self): self._quick_effect("grayscale", {})
    def _apply_vignette(self): self._quick_effect("vignette", {"angle": "PI/4"})
    def _apply_stabilize(self): self._quick_effect("stabilize", {})

    def _quick_effect(self, fx_type, params):
        clips = self.project.get("clips", []) if self.project else []
        if not clips:
            self.status_label.setText("请先导入素材")
            return
        clips[0].setdefault("effects", []).append({"type": fx_type, "params": params})
        self.status_label.setText(f"✓ 已应用: {fx_type}")

    def _add_text_watermark(self):
        from PyQt6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, "文字水印", "输入水印文字:")
        if ok and text:
            clips = self.project.get("clips", []) if self.project else []
            if clips:
                clips[0].setdefault("effects", []).append({
                    "type": "watermark_text",
                    "params": {"text": text, "fontsize": 36, "color": "white", "x": 20, "y": 20}
                })
                self.status_label.setText(f"✓ 已添加文字水印: {text}")

    # ── 导出 ──────────────────────────────────

    def _show_export_dialog(self):
        if not self.project or not self.project.get("clips"):
            QMessageBox.information(self, "提示", "时间轴上没有片段")
            return
        dlg = ExportDialog(self.project, self)
        dlg.exec()

    def _export_selected_clip(self):
        clips = self.project.get("clips", []) if self.project else []
        if clips:
            out_path, _ = QFileDialog.getSaveFileName(self, "导出片段",
                clips[0]["filename"].rsplit(".", 1)[0] + "_edited.mp4",
                "MP4 (*.mp4)")
            if out_path:
                self._do_export(out_path, settings={
                    "format": "mp4_h264", "resolution": "1920x1080",
                    "fps": 30, "crf": 23, "preset": "fast",
                    "audio_bitrate": "192k",
                }, clip_id=clips[0]["id"])

    def _do_export(self, output_path: str, settings: dict, clip_id: str = None):
        export_clips = project_to_export_clips(self.project, clip_id)
        dlg = ExportProgressDialog(export_clips, output_path, settings, self)
        dlg.exec()


# ──────────────────────────────────────────────
# 导出对话框
# ──────────────────────────────────────────────

class ExportDialog(QDialog):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.main = parent
        self.setWindowTitle("导出设置")
        self.setMinimumWidth(500)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 格式
        fmt_group = QGroupBox("输出格式")
        fmt_layout = QGridLayout(fmt_group)
        fmt_layout.addWidget(QLabel("格式:"), 0, 0)
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems([
            "MP4 (H.264) - 最兼容", "MP4 (H.265/HEVC) - 更小体积",
            "WebM (VP9)", "MKV (H.264)", "MOV (H.264)",
        ])
        fmt_layout.addWidget(self.fmt_combo, 0, 1)

        fmt_layout.addWidget(QLabel("分辨率:"), 1, 0)
        self.res_combo = QComboBox()
        self.res_combo.addItems([
            "原始分辨率", "1920x1080 (1080p)", "1280x720 (720p)",
            "854x480 (480p)", "3840x2160 (4K)",
        ])
        fmt_layout.addWidget(self.res_combo, 1, 1)

        fmt_layout.addWidget(QLabel("帧率:"), 2, 0)
        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["原始帧率", "60 fps", "30 fps", "24 fps", "15 fps"])
        fmt_layout.addWidget(self.fps_combo, 2, 1)

        fmt_layout.addWidget(QLabel("质量:"), 3, 0)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems([
            "高质量 (CRF 18)", "标准 (CRF 23)",
            "较小文件 (CRF 28)", "快速预览 (CRF 30)",
        ])
        fmt_layout.addWidget(self.quality_combo, 3, 1)
        layout.addWidget(fmt_group)

        # 音频
        audio_group = QGroupBox("音频")
        audio_layout = QGridLayout(audio_group)
        audio_layout.addWidget(QLabel("编码器:"), 0, 0)
        self.audio_codec_combo = QComboBox()
        self.audio_codec_combo.addItems(["AAC 192k (推荐)", "AAC 256k", "AAC 320k", "MP3 192k"])
        audio_layout.addWidget(self.audio_codec_combo, 0, 1)
        layout.addWidget(audio_group)

        # 预估
        dur = get_project_duration(self.project)
        layout.addWidget(QLabel(f"总时长: {format_time(dur)}"))

        # 按钮
        btns = QHBoxLayout()
        start_btn = QPushButton("开始导出")
        start_btn.clicked.connect(self._start_export)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(start_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    def _start_export(self):
        formats = ["mp4_h264", "mp4_h265", "webm", "mkv", "mov"]
        resolutions = ["original", "1920x1080", "1280x720", "854x480", "3840x2160"]
        fps_vals = [0, 60, 30, 24, 15]
        crf_vals = [18, 23, 28, 30]
        audio_bitrate = ["192k", "256k", "320k", "192k"]

        path, _ = QFileDialog.getSaveFileName(self, "保存视频",
            f"{self.project.get('name', 'output')}.mp4",
            "MP4 (*.mp4);;WebM (*.webm);;MKV (*.mkv)")
        if not path:
            return

        settings = {
            "format": formats[self.fmt_combo.currentIndex()],
            "resolution": resolutions[self.res_combo.currentIndex()],
            "fps": fps_vals[self.fps_combo.currentIndex()],
            "crf": crf_vals[self.quality_combo.currentIndex()],
            "preset": "fast",
            "audio_bitrate": audio_bitrate[self.audio_codec_combo.currentIndex()],
        }
        clips = project_to_export_clips(self.project)
        dlg = ExportProgressDialog(clips, path, settings, self.main)
        dlg.exec()
        self.accept()


class ExportProgressDialog(QDialog):
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

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self._cancel)
        layout.addWidget(self.cancel_btn)

    def _cancel(self):
        self.cancelled = True
        self.reject()

    def _do_export(self):
        import threading
        total = sum(c["end"] - c["start"] for c in self.clips)

        def cb(current, total_dur):
            if self.cancelled:
                return
            pct = int(current / total_dur * 100) if total_dur else 0
            self.progress_bar.setValue(pct)
            self.status_label.setText(f"已处理: {format_time(current)} / {format_time(total_dur)}")

        def worker():
            from ffmpeg_core import export_video
            ok, err = export_video(self.clips, self.output_path, self.settings, cb)
            if self.cancelled:
                return
            if ok:
                size = os.path.getsize(self.output_path)
                self.status_label.setText(f"✓ 导出完成！")
                self.progress_bar.setValue(100)
                self.info_label.setText(f"大小: {format_size(size)}")
                self.cancel_btn.setText("关闭")
                if self.main:
                    self.main.status_label.setText(f"✓ 导出完成: {self.output_path}")
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.information(self, "导出完成",
                    f"视频已保存到:\n{self.output_path}\n\n大小: {format_size(size)}")
            else:
                self.status_label.setText(f"✗ 导出失败: {err}")

        t = threading.Thread(target=worker, daemon=True)
        t.start()


# ──────────────────────────────────────────────
# 关于
# ──────────────────────────────────────────────

    def _show_about(self):
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.about(self, "关于 videdit",
            f"<h2>videdit {APP_VERSION}</h2>"
            f"<p>轻量级视频编辑器</p>"
            f"<p>基于 <b>PyQt6</b> + <b>FFmpeg</b></p>"
            f"<p>支持 Windows / macOS / Linux</p>"
            f"<hr><p>快捷键: Space=播放 | J/K/L=倒放/暂停/正放 | "
            f"I=入点 | O=出点 | S=切割 | Delete=删除</p>")


# ──────────────────────────────────────────────
# 入口
# ──────────────────────────────────────────────

def main():
    import sys
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    # 设置样式
    app.setStyleSheet("""
        QMainWindow { background: #0d1117; color: #e6edf3; }
        QMenuBar { background: #161b22; color: #e6edf3; }
        QMenuBar::item:selected { background: #1f6feb; }
        QMenu { background: #161b22; color: #e6edf3; border: 1px solid #30363d; }
        QMenu::item:selected { background: #1f6feb; }
        QToolBar { background: #161b22; border: none; spacing: 4px; }
        QPushButton { background: #21262d; color: #e6edf3; border: 1px solid #30363d; padding: 4px 12px; border-radius: 4px; }
        QPushButton:hover { background: #30363d; }
        QPushButton:pressed { background: #1f6feb; }
        QLabel { color: #e6edf3; }
        QDockWidget { background: #0d1117; color: #e6edf3; border: 1px solid #30363d; }
        QDockWidget::title { background: #161b22; padding: 4px; }
        QStatusBar { background: #161b22; color: #8b949e; }
        QGroupBox { color: #e6edf3; border: 1px solid #30363d; margin-top: 8px; padding-top: 8px; }
        QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
        QScrollBar:vertical { background: #0d1117; width: 10px; }
        QScrollBar::handle:vertical { background: #30363d; border-radius: 5px; }
        QListWidget { background: #0d1117; color: #e6edf3; border: 1px solid #30363d; }
        QListWidget::item:selected { background: #1f6feb; }
        QComboBox { background: #21262d; color: #e6edf3; border: 1px solid #30363d; padding: 2px 8px; }
        QSpinBox, QDoubleSpinBox { background: #21262d; color: #e6edf3; border: 1px solid #30363d; }
        QSlider::groove:horizontal { background: #30363d; height: 4px; border-radius: 2px; }
        QSlider::handle:horizontal { background: #1f6feb; width: 14px; margin: -5px 0; border-radius: 7px; }
        QProgressBar { background: #21262d; border: none; border-radius: 4px; text-align: center; color: white; }
        QProgressBar::chunk { background: #1f6feb; border-radius: 4px; }
        QTabWidget::pane { border: 1px solid #30363d; background: #0d1117; }
        QTabBar::tab { background: #161b22; color: #8b949e; padding: 6px 16px; }
        QTabBar::tab:selected { background: #1f6feb; color: white; }
    """)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())
