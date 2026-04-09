"""
videdit - FFmpeg 核心封装
所有视频/音频处理操作在此模块
"""
import subprocess
import json
import os
import re
import math
import uuid
import tempfile
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Callable
from dataclasses import dataclass, field


# ─────────────────────────────────────────────
# 路径 & 环境
# ─────────────────────────────────────────────

def _get_ffmpeg_path() -> str:
    """获取 ffmpeg 可执行文件路径"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # PyInstaller 打包后的路径
    if getattr(sys, '_MEIPASS', False):
        base = sys._MEIPASS
    bundled = os.path.join(base, 'ffmpeg_bin', 'bin')
    # 优先用打包的 ffprobe
    local_ffmpeg = os.path.join(bundled, 'ffmpeg.exe')
    if os.path.exists(local_ffmpeg):
        return bundled
    # 开发环境 PATH
    return ''


import sys
_ffmpeg_bin = _get_ffmpeg_path()
FFMPEG = os.path.join(_ffmpeg_bin, 'ffmpeg.exe') if _ffmpeg_bin else 'ffmpeg'
FFPROBE = os.path.join(_ffmpeg_bin, 'ffprobe.exe') if _ffmpeg_bin else 'ffprobe'
FFPLAY = os.path.join(_ffmpeg_bin, 'ffplay.exe') if _ffmpeg_bin else 'ffplay'


def _cmd(name: str, *args) -> List[str]:
    return [name, '-hide_banner', '-loglevel', 'error'] + list(args)


# ─────────────────────────────────────────────
# 数据结构
# ─────────────────────────────────────────────

@dataclass
class VideoStream:
    index: int
    codec_name: str
    width: int
    height: int
    fps: float
    bitrate: int
    duration: float
    pix_fmt: str


@dataclass
class AudioStream:
    index: int
    codec_name: str
    sample_rate: int
    channels: int
    bitrate: int
    duration: float


@dataclass
class MediaInfo:
    path: str
    duration: float
    size: int
    format_name: str
    video_streams: List[VideoStream] = field(default_factory=list)
    audio_streams: List[AudioStream] = field(default_factory=list)

    @property
    def width(self) -> int:
        return self.video_streams[0].width if self.video_streams else 0

    @property
    def height(self) -> int:
        return self.video_streams[0].height if self.video_streams else 0

    @property
    def fps(self) -> float:
        return self.video_streams[0].fps if self.video_streams else 0.0

    @property
    def has_audio(self) -> bool:
        return len(self.audio_streams) > 0

    @property
    def video_codec(self) -> str:
        return self.video_streams[0].codec_name if self.video_streams else 'none'

    @property
    def audio_codec(self) -> str:
        return self.audio_streams[0].codec_name if self.audio_streams else 'none'

    def format_time(self, secs: float) -> str:
        h = int(secs // 3600)
        m = int((secs % 3600) // 60)
        s = int(secs % 60)
        ms = int((secs % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


# ─────────────────────────────────────────────
# 探针
# ─────────────────────────────────────────────

def probe(path: str) -> Optional[MediaInfo]:
    """获取媒体文件详细信息"""
    if not os.path.exists(path):
        return None
    cmd = [FFPROBE, '-v', 'quiet', '-print_format', 'json',
           '-show_format', '-show_streams', path]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
    except Exception:
        return None

    fmt = data.get('format', {})
    duration = float(fmt.get('duration', 0) or 0)
    size = int(fmt.get('size', 0) or 0)
    format_name = fmt.get('format_name', '')

    video_streams = []
    audio_streams = []

    for s in data.get('streams', []):
        ct = s.get('codec_type', '')
        if ct == 'video':
            fps_str = s.get('r_frame_rate', '0/1')
            try:
                num, den = fps_str.split('/')
                fps = float(num) / float(den)
            except:
                fps = 0.0
            video_streams.append(VideoStream(
                index=s.get('index', 0),
                codec_name=s.get('codec_name', 'unknown'),
                width=int(s.get('width', 0) or 0),
                height=int(s.get('height', 0) or 0),
                fps=fps,
                bitrate=int(s.get('bit_rate', 0) or 0),
                duration=float(s.get('duration', 0) or 0),
                pix_fmt=s.get('pix_fmt', ''),
            ))
        elif ct == 'audio':
            audio_streams.append(AudioStream(
                index=s.get('index', 0),
                codec_name=s.get('codec_name', 'unknown'),
                sample_rate=int(s.get('sample_rate', 0) or 0),
                channels=int(s.get('channels', 0) or 0),
                bitrate=int(s.get('bit_rate', 0) or 0),
                duration=float(s.get('duration', 0) or 0),
            ))

    return MediaInfo(
        path=path,
        duration=duration,
        size=size,
        format_name=format_name,
        video_streams=video_streams,
        audio_streams=audio_streams,
    )


def check_ffmpeg() -> Tuple[bool, str]:
    """检测 FFmpeg 是否可用，返回 (可用, 版本信息)"""
    try:
        result = subprocess.run([FFMPEG, '-version'],
                               capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            return True, version_line
    except Exception as e:
        return False, str(e)
    return False, 'FFmpeg not found'


# ─────────────────────────────────────────────
# 缩略图
# ─────────────────────────────────────────────

def generate_thumbnail(video_path: str, output_path: str,
                       time: float = 0.0, width: int = 320) -> bool:
    """生成单张缩略图"""
    cmd = [
        FFMPEG, '-y',
        '-ss', str(time),
        '-i', video_path,
        '-vframes', '1',
        '-q:v', '2',
        '-vf', f'scale={width}:-1',
        output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        return result.returncode == 0
    except:
        return False


def generate_thumbnails_series(video_path: str, output_dir: str,
                                interval: float = 5.0, width: int = 160,
                                progress_cb: Callable[[int, float], None] = None
                                ) -> List[str]:
    """生成缩略图序列"""
    os.makedirs(output_dir, exist_ok=True)
    info = probe(video_path)
    if not info:
        return []
    dur = info.duration
    thumbs = []
    count = math.ceil(dur / interval)

    for i in range(count):
        t = i * interval
        out = os.path.join(output_dir, f'thumb_{i:06d}.jpg')
        if generate_thumbnail(video_path, out, t, width):
            thumbs.append(out)
        if progress_cb:
            progress_cb(i + 1, count)

    return thumbs


# ─────────────────────────────────────────────
# 基础剪辑
# ─────────────────────────────────────────────

def cut_clip(input_path: str, output_path: str,
             start: float, end: float,
             encode: bool = True,
             progress_cb: Callable[[float, float], None] = None
             ) -> bool:
    """切割视频片段"""
    dur = end - start
    if encode:
        cmd = [
            FFMPEG, '-y',
            '-ss', str(start),
            '-i', input_path,
            '-t', str(dur),
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
            '-c:a', 'aac', '-b:a', '128k',
            output_path,
        ]
    else:
        cmd = [
            FFMPEG, '-y',
            '-ss', str(start),
            '-i', input_path,
            '-t', str(dur),
            '-c', 'copy',
            output_path,
        ]

    return _run_with_progress(cmd, dur, progress_cb,
                               time_start=start)


def merge_clips(clips: List[Dict], output_path: str,
                progress_cb: Callable[[float, float], None] = None
                ) -> bool:
    """合并多个片段为最终视频"""
    if not clips:
        return False

    # 如果所有片段编码参数一致，可以 concat copy
    all_same = all(c.get('codec') == 'copy' for c in clips)
    concat_file = output_path + '.concat.txt'
    total = sum(c['end'] - c['start'] for c in clips)

    with open(concat_file, 'w', encoding='utf-8') as f:
        for c in clips:
            path = c['path'].replace('\\', '/').replace("'", "'\"'\"'")
            f.write(f"file '{path}'\n")
            f.write(f"inpoint {c['start']}\n")
            f.write(f"outpoint {c['end']}\n")

    try:
        if all_same:
            cmd = [FFMPEG, '-y', '-f', 'concat', '-safe', '0',
                   '-i', concat_file, '-c', 'copy', output_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=int(total * 2 + 10))
            return result.returncode == 0
        else:
            # 需要重新编码
            filter_parts = []
            map_parts = []
            for i, c in enumerate(clips):
                start = c['start']
                dur = c['end'] - c['start']
                filter_parts.append(
                    f'[{i}:v]trim=start={start}:end={c["end"]},setpts=PTS-STARTPTS,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30[v{i}]'
                )
                vol = c.get('volume', 1.0)
                filter_parts.append(
                    f'[{i}:a]atrim=start={start}:end={c["end"]},asetpts=PTS-STARTPTS,volume={vol}[a{i}]'
                )
                map_parts.extend([f'[v{i}]', f'[a{i}]'])

            cmd = []
            for c in clips:
                cmd += ['-i', c['path']]
            cmd += [
                '-filter_complex', ';'.join(filter_parts),
                '-map', ''.join(map_parts),
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                '-c:a', 'aac', '-b:a', '128k',
                '-y', output_path,
            ]
            return _run_with_progress(cmd, total, progress_cb)
    finally:
        try:
            os.remove(concat_file)
        except:
            pass
    return False


# ─────────────────────────────────────────────
# 视频效果
# ─────────────────────────────────────────────

EFFECT_FILTERS = {
    'speed': lambda p: f"setpts={1.0/p['factor']}*PTS,atempo={min(p['factor'], 2.0)}",
    'reverse': lambda p: 'reverse',
    'blur': lambda p: f"boxblur={p.get('radius',5)}:{p.get('radius',5)}",
    'sharpen': lambda p: f"unsharp=5:5:{p.get('strength',1.0)}:5:5:{p.get('strength',1.0)}",
    'brightness': lambda p: f"eq=brightness={p.get('value',0.1)}",
    'contrast': lambda p: f"eq=contrast={p.get('value',1.3)}",
    'saturation': lambda p: f"eq=saturation={p.get('value',1.5)}",
    'hue': lambda p: f"hue=h={p.get('angle',0)}",
    'grayscale': lambda p: 'hue=s=0',
    'invert': lambda p: 'negate',
    'vignette': lambda p: f"vignette=angle={p.get('angle','PI/4')}",
    'noise': lambda p: f"noise=alls={int(p.get('strength',10))}a=0",
    'stabilize': lambda p: 'deshake',
    'denoise': lambda p: f"hqdn3d={p.get('strength',4)}",
    'crop': lambda p: f"crop={p.get('w','iw')}:{p.get('h','ih')}:{p.get('x',0)}:{p.get('y',0)}",
    'rotate': lambda p: f"rotate={p.get('angle',0)}*PI/180:bilinear=0",
    'zoom': lambda p: f"scale={p.get('factor',1.5)}*iw:{p.get('factor',1.5)}*ih",
    'fade_in': lambda p: f"fade=t=in:st=0:d={p.get('duration',1)}",
    'fade_out': lambda p: f"fade=t=out:st={p.get('start_time',0)}:d={p.get('duration',1)}",
    'vflip': lambda p: 'vflip',
    'hflip': lambda p: 'hflip',
    'cartoon': lambda p: 'cartoon',
    'colorbalance': lambda p: f"colorbalance=rs={p.get('red_shadow',0)}:gs={p.get('green_shadow',0)}:bs={p.get('blue_shadow',0)}",
}


def build_effect_chain(effects: List[Dict]) -> Optional[str]:
    """根据效果列表构建 FFmpeg 滤镜链"""
    filters = []
    for eff in effects:
        eid = eff.get('type', '')
        params = eff.get('params', {})
        builder = EFFECT_FILTERS.get(eid)
        if builder:
            try:
                filters.append(builder(params))
            except Exception:
                pass
    return ','.join(filters) if filters else None


def apply_effects(
    input_path: str,
    output_path: str,
    effects: List[Dict],
    progress_cb: Callable[[float, float], None] = None,
    total_duration: float = 0,
) -> bool:
    """应用一系列效果到视频"""
    chain = build_effect_chain(effects)
    if not chain:
        # 无效果，直接复制
        cmd = [FFMPEG, '-y', '-i', input_path, '-c', 'copy', output_path]
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0

    cmd = [
        FFMPEG, '-y',
        '-i', input_path,
        '-vf', chain,
        '-c:a', 'aac', '-b:a', '128k',
        output_path,
    ]
    return _run_with_progress(cmd, total_duration, progress_cb)


# ─────────────────────────────────────────────
# 音频处理
# ─────────────────────────────────────────────

def extract_audio(video_path: str, output_path: str,
                  format: str = 'mp3', bitrate: str = '192k') -> bool:
    """提取音频轨道"""
    if format == 'mp3':
        codec = 'libmp3lame'
    elif format == 'wav':
        codec = 'pcm_s16le'
    elif format == 'aac':
        codec = 'aac'
    elif format == 'flac':
        codec = 'flac'
    else:
        codec = 'copy'

    cmd = [FFMPEG, '-y', '-i', video_path, '-vn',
           '-acodec', codec]
    if codec not in ('copy', 'pcm_s16le'):
        cmd += ['-b:a', bitrate]
    cmd.append(output_path)

    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def apply_audio_effects(
    input_path: str,
    output_path: str,
    effect: str,
    params: Dict,
    progress_cb: Callable[[float, float], None] = None,
    total_duration: float = 0,
) -> bool:
    """应用音频效果"""
    afilters = {
        'volume': lambda p: f"volume={p.get('factor', 1.0)}",
        'fade_in': lambda p: f"afade=t=in:st=0:d={p.get('duration', 1)}",
        'fade_out': lambda p: f"afade=t=out:st={p.get('start_time', 0)}:d={p.get('duration', 1)}",
        'denoise': lambda p: f"afftdn=n={p.get('strength', 'medium')}",
        'normalize': lambda p: 'loudnorm=I=-16:TP=-1.5:LRA=11',
        'pitch': lambda p: f"rubberband=pitch={p.get('semitones', 0)}",
        'delay': lambda p: f"adelay={p.get('ms', 500)}|{p.get('ms', 500)}",
        'tremolo': lambda p: f"tremolo=f={p.get('freq', 5)}:d={p.get('depth', 0.5)}",
        'phaser': lambda p: f"phaser=f={p.get('freq', 0.5)}",
        'chorus': lambda p: f"chorus=0.5:0.9:50:0.4:0.25:2",
    }

    builder = afilters.get(effect)
    if not builder:
        return False

    try:
        afilter = builder(params)
    except:
        return False

    cmd = [
        FFMPEG, '-y',
        '-i', input_path,
        '-af', afilter,
        output_path,
    ]
    return _run_with_progress(cmd, total_duration, progress_cb)


# ─────────────────────────────────────────────
# 转场
# ─────────────────────────────────────────────

def build_transition_filter(t1_path: str, t2_path: str,
                            transition: str, duration: float) -> Tuple[str, List[str]]:
    """构建转场滤镜"""
    if transition == 'dissolve':
        vf = f"[0:v][1:v]blend=all_expr='A*(if(lt(t,{duration}),1,t/{duration}))+B*(if(lt(t,{duration}),0,1))'"
    elif transition == 'fade':
        vf = f"[0:v]fade=t=out:st=0:d={duration}[v0];[1:v]fade=t=in:st=0:d={duration}[v1];[v0][v1]concat=n=2:v=1:a=0[v]"
        return vf, []
    elif transition == 'wipe_left':
        vf = f"[0:v][1:v]overlay=x='if(lt(t,{duration}),-W+W*t/{duration},NEG_INF)'[v]"
    elif transition == 'wipe_right':
        vf = f"[0:v][1:v]overlay=x='if(lt(t,{duration}),W-W*t/{duration},NEG_INF)'[v]"
    elif transition == 'slide_up':
        vf = f"[0:v][1:v]overlay=y='if(lt(t,{duration}),H-H*t/{duration},NEG_INF)'[v]"
    elif transition == 'slide_down':
        vf = f"[0:v][1:v]overlay=y='if(lt(t,{duration}),-H+H*t/{duration},NEG_INF)'[v]"
    elif transition == 'zoom':
        vf = f"[0:v]scale=1.5*iw:1.5*ih,fade=t=out:st=0:d={duration}[v0];[1:v][v0]overlay=0:0:shortest=1[v]"
    elif transition == 'blur_dissolve':
        vf = f"[0:v][1:v]fftfilt=real='hypot(re,im)*if(lt(t,{duration}),1-t/{duration},0)':imag='0'[v]"
    elif transition == 'pixelate':
        vf = f"[0:v][1:v]overlay=0:0:format=auto[v]"
    else:
        # 硬切
        return '', []

    return vf, []


# ─────────────────────────────────────────────
# 导出
# ─────────────────────────────────────────────

def export_video(
    clips: List[Dict],
    output_path: str,
    settings: Dict,
    progress_cb: Callable[[float, float], None] = None,
) -> Tuple[bool, str]:
    """
    导出最终视频
    settings: {format, resolution, fps, crf, preset, audio_codec, audio_bitrate}
    返回 (success, error_message)
    """
    if not clips:
        return False, 'No clips to export'

    format_map = {
        'mp4_h264': ('mp4', 'libx264', 'aac'),
        'mp4_h265': ('mp4', 'libx265', 'aac'),
        'webm': ('webm', 'libvpx-vp9', 'libopus'),
        'avi': ('avi', 'libx264', 'mp3'),
        'mkv': ('matroska', 'libx264', 'aac'),
        'mov': ('mov', 'libx264', 'aac'),
    }

    fmt, vcodec, acodec = format_map.get(settings.get('format', 'mp4_h264'),
                                          ('mp4', 'libx264', 'aac'))
    preset = settings.get('preset', 'fast')
    crf = settings.get('crf', 23)
    fps = settings.get('fps', 30)
    res = settings.get('resolution', '1920x1080')
    w, h = map(int, res.split('x'))
    audio_bitrate = settings.get('audio_bitrate', '192k')

    if len(clips) == 1:
        # 单片段直接处理
        c = clips[0]
        effects = c.get('effects', [])
        chain = build_effect_chain(effects)
        vol = c.get('volume', 1.0)

        cmd = [FFMPEG, '-y', '-ss', str(c['start']), '-i', c['path'],
               '-t', str(c['end'] - c['start'])]
        if chain:
            cmd += ['-vf', chain]
        cmd += [
            '-vf', f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,fps={fps}',
            '-r', str(fps),
            '-c:v', vcodec, '-preset', preset, '-crf', str(crf),
            '-c:a', acodec, '-b:a', audio_bitrate,
            '-af', f'volume={vol}',
            output_path,
        ]
    else:
        # 多片段 concat + 统一编码
        filter_parts = []
        for i, c in enumerate(clips):
            s, e = c['start'], c['end']
            vol = c.get('volume', 1.0)
            effects = c.get('effects', [])
            chain = build_effect_chain(effects)
            if chain:
                filter_parts.append(
                    f'[{i}:v]trim=start={s}:end={e},setpts=PTS-STARTPTS,{chain},scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,fps={fps}[v{i}]'
                )
            else:
                filter_parts.append(
                    f'[{i}:v]trim=start={s}:end={e},setpts=PTS-STARTPTS,scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,fps={fps}[v{i}]'
                )
            filter_parts.append(
                f'[{i}:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS,volume={vol}[a{i}]'
            )
        concat_parts = ''.join(
            [f'[v{i}][a{i}]' for i in range(len(clips))]
        )
        filter_parts.append(f'{concat_parts}concat=n={len(clips)}:v=1:a=1[v][a]')

        cmd = []
        for c in clips:
            cmd += ['-i', c['path']]
        cmd += [
            '-filter_complex', ';'.join(filter_parts),
            '-map', '[v]', '-map', '[a]',
            '-c:v', vcodec, '-preset', preset, '-crf', str(crf),
            '-c:a', acodec, '-b:a', audio_bitrate,
            '-y', output_path,
        ]

    total = sum(c['end'] - c['start'] for c in clips)
    ok = _run_with_progress(cmd, total, progress_cb)

    if ok:
        return True, ''
    else:
        return False, 'FFmpeg encoding failed'


# ─────────────────────────────────────────────
# 场景检测
# ─────────────────────────────────────────────

def detect_scenes(video_path: str, threshold: float = 30.0,
                  progress_cb: Callable[[float], None] = None
                  ) -> List[float]:
    """
    场景检测，返回时间戳列表（秒）
    threshold: 灵敏度 (0.0=最灵敏, 100=最不灵敏)
    """
    info = probe(video_path)
    if not info:
        return []
    thresh_float = threshold / 100.0

    cmd = [
        FFMPEG, '-i', video_path,
        '-filter_complex',
        f"select='gt(scene,{thresh_float})',showinfo",
        '-f', 'null', '-',
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=int(info.duration + 10))
    except:
        return []

    timestamps = []
    for line in result.stderr.split('\n'):
        if 'pts_time' in line:
            try:
                ts = line.split('pts_time:')[1].split()[0]
                timestamps.append(float(ts))
            except:
                pass
    return timestamps


# ─────────────────────────────────────────────
# 文字水印 / 字幕
# ─────────────────────────────────────────────

def add_text_watermark(
    input_path: str,
    output_path: str,
    text: str,
    x: int = 20,
    y: int = 20,
    font_size: int = 36,
    color: str = 'white',
    font_path: str = '',
    enable_start: float = 0,
    enable_end: float = -1,
    progress_cb: Callable[[float, float], None] = None,
) -> bool:
    """添加文字水印"""
    font_file = ''
    if font_path and os.path.exists(font_path):
        font_file = f":force_style='FontName={os.path.basename(font_path)}'"

    enable = f"enable='between(t,{enable_start},{enable_end})'" if enable_end > 0 else "enable='gte(t,{0})'".format(enable_start)
    vf = f"drawtext=text='{text}':fontsize={font_size}:fontcolor={color}:x={x}:y={y}:{enable}{font_file}"

    cmd = [
        FFMPEG, '-y',
        '-i', input_path,
        '-vf', vf,
        '-c:a', 'copy',
        output_path,
    ]
    info = probe(input_path)
    dur = info.duration if info else 0
    return _run_with_progress(cmd, dur, progress_cb)


# ─────────────────────────────────────────────
# 工具函数
# ─────────────────────────────────────────────

def _run_with_progress(
    cmd: List[str],
    total: float,
    progress_cb: Callable[[float, float], None] = None,
    time_start: float = 0,
) -> bool:
    """执行 FFmpeg 命令并报告进度"""
    import threading
    time_pat = re.compile(r'time=(\d+):(\d+):(\d+\.\d+)')

    progress = {'current': 0.0, 'done': False, 'returncode': None}

    def read_stderr(pipe, queue):
        for line in pipe:
            if progress['done']:
                break
            queue.put(line)

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        import queue as _queue
        q = _queue.Queue()
        t = threading.Thread(target=read_stderr, args=(proc.stderr, q), daemon=True)
        t.start()

        while proc.poll() is None:
            try:
                line = q.get(timeout=0.5)
            except _queue.Empty:
                continue

            if progress_cb:
                m = time_pat.search(line)
                if m:
                    h = float(m.group(1))
                    mn = float(m.group(2))
                    sec = float(m.group(3))
                    progress['current'] = h * 3600 + mn * 60 + sec - time_start
                    progress_cb(progress['current'], total)

        progress['done'] = True
        proc.wait()
        progress['returncode'] = proc.returncode
        if progress_cb and total > 0:
            progress_cb(total, total)
        return proc.returncode == 0

    except Exception:
        return False


def get_frame_at_time(video_path: str, time: float) -> Optional[bytes]:
    """获取指定时间的帧数据（用于预览）"""
    tmp = os.path.join(tempfile.gettempdir(), f'videdit_frame_{uuid.uuid4().hex[:8]}.jpg')
    try:
        ok = generate_thumbnail(video_path, tmp, time, width=480)
        if ok and os.path.exists(tmp):
            with open(tmp, 'rb') as f:
                data = f.read()
            return data
    finally:
        try:
            os.remove(tmp)
        except:
            pass
    return None


def get_audio_waveform(video_path: str, output_path: str,
                       width: int = 800, height: int = 100) -> bool:
    """生成音频波形图"""
    cmd = [
        FFMPEG, '-y',
        '-i', video_path,
        '-filter_complex',
        f"showwavespic=size={width}x{height}:colors=cyan",
        '-frames:v', '1',
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def format_time(secs: float) -> str:
    """格式化时间"""
    if secs <= 0:
        return '00:00.000'
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    s = int(secs % 60)
    ms = int((secs % 1) * 1000)
    return f'{h:02d}:{m:02d}:{s:02d}.{ms:03d}'


def format_size(b: int) -> str:
    """格式化文件大小"""
    if b < 1024:
        return f'{b}B'
    elif b < 1024**2:
        return f'{b/1024:.1f}KB'
    elif b < 1024**3:
        return f'{b/1024**2:.1f}MB'
    else:
        return f'{b/1024**3:.2f}GB'
