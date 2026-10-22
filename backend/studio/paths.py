"""Read-only installed resources and separate writable studio state."""
import os
from pathlib import Path
import sys


def resource_root():
    override = os.environ.get('STUDIO_RESOURCE_ROOT')
    if override:
        return Path(override).resolve()
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent.parent / 'studio'
    return Path(__file__).resolve().parents[2]


def data_root():
    override = os.environ.get('STUDIO_DATA_DIR')
    if override:
        return Path(override).resolve()
    if getattr(sys, 'frozen', False):
        profile = os.environ.get('APPDATA')
        return (Path(profile) if profile else Path.home() / 'AppData' / 'Roaming') / 'Frame Studio' / 'studio_data'
    return Path(__file__).resolve().parents[2] / 'studio_data'


def mcp_launch_configuration(root=None):
    """Publish launch details using an allowlist; credentials stay in the data folder."""
    root = Path(root).resolve() if root is not None else data_root()
    if getattr(sys, 'frozen', False):
        return {'command': sys.executable, 'args': ['mcp', '--data-dir', str(root)], 'env': {}, 'desktop': True}
    return {'command': sys.executable, 'args': [str(resource_root() / 'backend' / 'studio_mcp.py')],
            'env': {'STUDIO_DATA_DIR': str(root), 'STUDIO_API_URL': os.environ.get('STUDIO_API_URL', 'http://127.0.0.1:8010')}, 'desktop': False}
