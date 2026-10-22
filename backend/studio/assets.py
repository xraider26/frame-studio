import json
import os
import shutil
import subprocess
from pathlib import Path

from PIL import Image

from .store import StudioError

MAX_ASSET_BYTES = 500 * 1024 * 1024


def checked_file(path, roots, kind):
    source = Path(path).resolve()
    if not any(source.is_relative_to(root.resolve()) for root in roots):
        raise StudioError('path_not_allowed', 'Save the output inside the configured studio inbox or project media folder first.')
    if not source.is_file() or source.stat().st_size > MAX_ASSET_BYTES:
        raise StudioError('invalid_asset', 'File is missing or exceeds the 500 MB local import limit.')
    try:
        if kind == 'image':
            with Image.open(source) as img:
                img.verify()
            with Image.open(source) as img:
                if img.format not in ['PNG', 'JPEG', 'WEBP']:
                    raise ValueError('Use PNG, JPEG or WebP images.')
                return source, {'width': img.width, 'height': img.height, 'mime': Image.MIME[img.format], 'suffix': '.' + {'PNG': 'png', 'JPEG': 'jpg', 'WEBP': 'webp'}[img.format]}
        if kind in ['video', 'final_video']:
            probe = shutil.which('ffprobe')
            if not probe:
                raise StudioError('ffprobe_missing', 'FFprobe is required to validate returned videos. Install FFmpeg and add it to PATH.')
            proc = subprocess.run([probe, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(source)], capture_output=True, timeout=25, check=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            data = json.loads(proc.stdout)
            video = next(s for s in data['streams'] if s['codec_type'] == 'video')
            if 'mp4' not in data['format']['format_name']:
                raise ValueError('Return an MP4 video.')
            return source, {'width': video['width'], 'height': video['height'], 'duration': float(data['format'].get('duration', 0)), 'mime': 'video/mp4', 'suffix': '.mp4'}
        raise ValueError('Unsupported media kind')
    except StudioError:
        raise
    except Exception as exc:
        raise StudioError('invalid_asset', 'Returned file is not valid media of the requested type.') from exc
