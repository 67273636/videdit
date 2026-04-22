from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QMenuBar, QMenu, QToolBar, QStatusBar, QFileDialog,
    QMessageBox, QDockWidget, QLabel,
    QListWidget, QListWidgetItem, QSplitter, QFrame,
    QDialog, QGridLayout, QLineEdit, QSpinBox, QDoubleSpinBox,
    QComboBox, QCheckBox, QPushButton, QGroupBox,
    QTextEdit, QTabWidget, QProgressBar, QSlider,
    QStyledItemDelegate, QStyleOptionViewItem,
    QScrollArea, QTreeWidget, QTreeWidgetItem,
)
from PyQt6.QtCore import (
    Qt, QTimer, QSize, QPoint, QThread, pyqtSignal, pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot pyqtSlot,
    QMimeData, QSettings, QUrl,
)
from PyQt6.QtGui import (
    QAction, QKeySequence, QPixmap, QImage, QPainter,
    QPen, QColor, QBrush, QFont, QCursor, QDrag,
    QShortcut, QClipboard,
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
