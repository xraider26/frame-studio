"""Read-only installed resources and separate writable studio state."""
import os
from pathlib import Path
import sys
import logging
import uuid


def resolve_writable_root(path: Path) -> Path:
    """Resolve through a real file, including packaged Windows virtualization.

    Only uniquely owned probe files are removed. Existing state is never moved.
    """
    requested = Path(path).absolute()
    requested.mkdir(parents=True, exist_ok=True)
    logical = requested.resolve()
    probe = requested / ('.orchestra-probe-' + uuid.uuid4().hex)
    verification = None
    probe_created = verification_created = False
    try:
        with probe.open('xb') as stream:
            probe_created = True
            stream.write(b'orchestra-root-probe')
        physical = probe.resolve(strict=True).parent
        physical.mkdir(parents=True, exist_ok=True)
        physical = physical.resolve(strict=True)
        if physical != logical:
            for name in ('workflow.db', 'agent.token', 'browser.token', 'connections.json'):
                left, right = logical/name, physical/name
                if left.exists() and left.resolve() != right.resolve():
                    raise ValueError('Data root has competing state; select one explicit physical STUDIO_DATA_DIR. No data was moved or merged.')
            logging.getLogger(__name__).warning('Studio writable root resolves differently through files; using physical root %s', physical)
        verification = physical / ('.orchestra-probe-' + uuid.uuid4().hex)
        with verification.open('xb') as stream:
            verification_created = True
            stream.write(b'orchestra-root-verification')
        if verification.resolve(strict=True).parent != physical:
            raise ValueError('Studio data root is not stable; select an explicit physical STUDIO_DATA_DIR.')
        return physical
    finally:
        if probe_created:
            probe.unlink(missing_ok=True)
        if verification_created:
            verification.unlink(missing_ok=True)


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
        return resolve_writable_root(Path(override))
    if getattr(sys, 'frozen', False):
        profile = os.environ.get('APPDATA')
        # Orchestra deliberately retains Frame Studio's installed data location:
        # existing projects and connection credentials must remain available.
        return resolve_writable_root((Path(profile) if profile else Path.home() / 'AppData' / 'Roaming') / 'Frame Studio' / 'studio_data')
    return resolve_writable_root(Path(__file__).resolve().parents[2] / 'studio_data')


def mcp_launch_configuration(root=None):
    """Publish launch details using an allowlist; credentials stay in the data folder."""
    root = resolve_writable_root(Path(root)) if root is not None else data_root()
    if getattr(sys, 'frozen', False):
        return {'command': sys.executable, 'args': ['mcp', '--data-dir', str(root)], 'env': {}, 'desktop': True}
    return {'command': sys.executable, 'args': [str(resource_root() / 'backend' / 'studio_mcp.py')],
            'env': {'STUDIO_DATA_DIR': str(root), 'STUDIO_API_URL': os.environ.get('STUDIO_API_URL', 'http://127.0.0.1:8010')}, 'desktop': False}
