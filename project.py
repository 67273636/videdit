"""
videdit - 项目文件管理
.videdit JSON 格式读写、自动保存、备份
"""
import json
import os
import uuid
import copy
import datetime
from typing import Optional, List, Dict, Any


CURRENT_VERSION = "1.0"


def new_project(name: str = "Untitled") -> Dict:
    """创建新项目"""
    return {
        "version": CURRENT_VERSION,
        "name": name,
        "created_at": _now(),
        "modified_at": _now(),
        "settings": {
            "resolution": "1920x1080",
            "fps": 30,
            "sample_rate": 48000,
            "aspect_ratio": "16:9",
        },
        "clips": [],
        "audio_clips": [],
        "transitions": [],
        "markers": [],
    }


def _now() -> str:
    return datetime.datetime.now().isoformat()


def _clip_defaults() -> Dict:
    return {
        "id": str(uuid.uuid4()),
        "path": "",
        "filename": "",
        "track": 0,
        "start": 0.0,       # 在时间轴上的起始位置
        "end": 0.0,         # 在时间轴上的结束位置
        "in_point": 0.0,    # 源文件入点
        "out_point": 0.0,   # 源文件出点
        "volume": 1.0,
        "effects": [],
        "audio_muted": False,
        "speed": 1.0,
    }


def add_clip(project: Dict, path: str, media_info=None) -> Dict:
    """添加片段到项目"""
    clip = _clip_defaults()
    clip["path"] = os.path.abspath(path)
    clip["filename"] = os.path.basename(path)

    if media_info:
        clip["in_point"] = 0.0
        clip["out_point"] = media_info.duration
        clip["start"] = _next_start(project, 0)
        clip["end"] = clip["start"] + media_info.duration
    else:
        clip["start"] = _next_start(project, 0)
        clip["end"] = clip["start"]

    project["clips"].append(clip)
    project["modified_at"] = _now()
    return clip


def _next_start(project: Dict, track: int = 0) -> float:
    """计算下一个片段的起始时间（追加到末尾）"""
    clips = [c for c in project.get("clips", []) if c.get("track") == track]
    if not clips:
        return 0.0
    return max(c.get("end", 0) for c in clips)


def remove_clip(project: Dict, clip_id: str):
    """从项目中移除片段"""
    project["clips"] = [c for c in project["clips"] if c["id"] != clip_id]
    project["modified_at"] = _now()


def load_project(path: str) -> Optional[Dict]:
    """加载项目文件"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # 验证
        if "version" not in data:
            return None
        return data
    except Exception:
        return None


def save_project(project: Dict, path: str) -> bool:
    """保存项目文件"""
    try:
        project["modified_at"] = _now()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(project, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def get_project_duration(project: Dict) -> float:
    """获取项目总时长"""
    clips = project.get("clips", [])
    if not clips:
        return 0.0
    return max(c.get("end", 0) for c in clips)


def project_to_export_clips(project: Dict, clip_id: str = None) -> List[Dict]:
    """将项目片段转为导出格式"""
    clips = []
    for c in project.get("clips", []):
        if clip_id and c["id"] != clip_id:
            continue
        clips.append({
            "path": c["path"],
            "start": c.get("in_point", 0),
            "end": c.get("out_point", c.get("end", 0) - c.get("start", 0) + c.get("in_point", 0)),
            "volume": c.get("volume", 1.0),
            "effects": c.get("effects", []),
        })
    return clips


def apply_clip_effects(project: Dict, clip_id: str, effects: List[Dict]):
    """为片段设置效果列表"""
    for c in project.get("clips", []):
        if c["id"] == clip_id:
            c["effects"] = effects
            break
    project["modified_at"] = _now()


def set_clip_volume(project: Dict, clip_id: str, volume: float):
    """设置片段音量"""
    for c in project.get("clips", []):
        if c["id"] == clip_id:
            c["volume"] = max(0.0, min(5.0, volume))
            break
    project["modified_at"] = _now()


def set_clip_inout(project: Dict, clip_id: str, in_pt: float, out_pt: float):
    """设置入出点并调整片段时长"""
    for c in project.get("clips", []):
        if c["id"] == clip_id:
            old_dur = c["out_point"] - c["in_point"]
            c["in_point"] = max(0, in_pt)
            c["out_point"] = out_pt
            new_dur = c["out_point"] - c["in_point"]
            c["end"] = c["start"] + new_dur
            break
    project["modified_at"] = _now()


def duplicate_clip(project: Dict, clip_id: str) -> Optional[Dict]:
    """复制片段"""
    for c in project.get("clips", []):
        if c["id"] == clip_id:
            new_clip = copy.deepcopy(c)
            new_clip["id"] = str(uuid.uuid4())
            new_clip["start"] = c["end"]
            new_clip["end"] = c["end"] + (c["out_point"] - c["in_point"])
            project["clips"].append(new_clip)
            project["modified_at"] = _now()
            return new_clip
    return None


def add_marker(project: Dict, time: float, label: str = "", color: str = "red") -> Dict:
    """添加标记"""
    marker = {
        "id": str(uuid.uuid4()),
        "time": time,
        "label": label,
        "color": color,
    }
    project.setdefault("markers", []).append(marker)
    project["modified_at"] = _now()
    return marker


def get_recent_projects(max_count: int = 10) -> List[Dict]:
    """获取最近项目列表（从 ~/.videdit/recent.json）"""
    recent_file = os.path.join(os.path.expanduser("~"), ".videdit", "recent.json")
    if not os.path.exists(recent_file):
        return []
    try:
        with open(recent_file, 'r', encoding='utf-8') as f:
            return json.load(f)[:max_count]
    except:
        return []


def add_recent_project(path: str, name: str):
    """添加最近项目"""
    recent_dir = os.path.join(os.path.expanduser("~"), ".videdit")
    os.makedirs(recent_dir, exist_ok=True)
    recent_file = os.path.join(recent_dir, "recent.json")
    recent = get_recent_projects()
    # 去重
    recent = [r for r in recent if r.get("path") != path]
    recent.insert(0, {"path": path, "name": name, "opened_at": _now()})
    try:
        with open(recent_file, 'w', encoding='utf-8') as f:
            json.dump(recent[:10], f, indent=2)
    except:
        pass
