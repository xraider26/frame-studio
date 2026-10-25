"""Frozen desktop service entry point; MCP discovers an already running desktop."""
import argparse
import json
import os
from pathlib import Path
import sys
import secrets
from urllib.parse import urlsplit

from studio.paths import data_root, resolve_writable_root
from studio.desktop_connection import publish_connection, read_connection, remove_connection


UNAVAILABLE = 'backend_unavailable: Open Orchestra and retry the MCP connection.'


def load_desktop_runtime(root):
    try:
        runtime = json.loads((Path(root) / 'desktop-runtime.json').read_text(encoding='utf-8'))
        return validate_desktop_runtime(runtime, root)
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(UNAVAILABLE) from exc


def validate_desktop_runtime(runtime, root):
    try:
        if not isinstance(runtime, dict):
            raise ValueError('Runtime must be an object')
        url = runtime.get('api_url')
        nonce = runtime.get('instance_id')
        if not isinstance(url, str) or not isinstance(nonce, str) or not nonce.strip():
            raise ValueError('Missing runtime URL or instance')
        parsed = urlsplit(url)
        if (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}
                or not parsed.port or not 1 <= parsed.port <= 65535
                or parsed.username is not None or parsed.password is not None
                or parsed.path or '?' in url or '#' in url or url != url.strip()
                or any(ord(char) < 33 for char in url)):
            raise ValueError('Runtime URL must be a loopback HTTP origin with an explicit port')
        result = {'api_url': url, 'instance_id': nonce}
        if runtime.get('schema_version', 1) >= 2:
            pid = runtime.get('service_pid')
            if (runtime.get('ready') is not True or type(pid) is not int or pid <= 0
                    or not isinstance(runtime.get('data_root'), str)
                    or Path(runtime['data_root']).resolve() != Path(root).resolve()):
                raise ValueError('Runtime is unready or belongs to another root/process')
            result.update(service_pid=pid, data_root=runtime['data_root'])
        return result
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(UNAVAILABLE) from exc


def discover_desktop(root):
    # Discovery is read-only: a writable probe inside a packaged MCP client can
    # select a different AppData overlay from the running desktop's own state.
    try:
        connection = read_connection(root)
        runtime = (validate_desktop_runtime(connection['runtime'], root)
                   if connection else load_desktop_runtime(root))
        verify_desktop_runtime(runtime)
        return runtime, connection['agent_token'] if connection else None
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(f'{UNAVAILABLE} Discovery root: {root}. Reconnect MCP after upgrading Orchestra.') from exc


def verify_desktop_runtime(runtime):
    import httpx
    try:
        with httpx.Client(timeout=3, trust_env=False) as client:
            response = client.get(runtime['api_url'] + '/health')
            response.raise_for_status()
            health = response.json()
        if (not isinstance(health, dict) or health.get('service') != 'frame-studio'
                or health.get('status') != 'ok' or health.get('instance_id') != runtime['instance_id']
                or ('service_pid' in runtime and health.get('service_pid') != runtime['service_pid'])
                or ('data_root' in runtime and health.get('data_root') != runtime['data_root'])):
            raise ValueError('Desktop instance has changed')
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise ValueError(UNAVAILABLE) from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description='Orchestra desktop service')
    commands = parser.add_subparsers(dest='command', required=True)
    serve = commands.add_parser('serve', help='Run the local desktop API')
    serve.add_argument('--host', default='127.0.0.1', choices=['127.0.0.1', 'localhost', '::1'])
    serve.add_argument('--port', type=int, required=True)
    serve.add_argument('--data-dir', type=Path)
    mcp = commands.add_parser('mcp', help='Bridge MCP to the running desktop')
    mcp.add_argument('--data-dir', type=Path)
    args = parser.parse_args(argv)
    if args.data_dir is not None and args.command == 'serve':
        os.environ['STUDIO_DATA_DIR'] = str(resolve_writable_root(args.data_dir))
    if args.command == 'serve':
        import uvicorn
        from studio.api import create_app
        bridge_token = secrets.token_urlsafe(36)
        app = create_app(bridge_token=bridge_token)
        root = app.state.data_root
        instance = os.environ.get('STUDIO_DESKTOP_INSTANCE') or secrets.token_hex(16)
        os.environ['STUDIO_DESKTOP_INSTANCE'] = instance
        host = f'[{args.host}]' if args.host == '::1' else args.host
        runtime = dict(api_url=f'http://{host}:{args.port}', instance_id=instance,
                       data_root=str(root), service_pid=os.getpid(), schema_version=2, ready=True)
        publish_connection(runtime, bridge_token)
        try:
            uvicorn.run(app, host=args.host, port=args.port, log_config=None)
        finally:
            remove_connection(root, instance)
        return 0
    try:
        root = args.data_dir or Path(os.environ.get('STUDIO_DATA_DIR') or
                    str(Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming')) / 'Frame Studio' / 'studio_data'))
        runtime, bridge_token = discover_desktop(root)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    os.environ['STUDIO_API_URL'] = runtime['api_url']
    os.environ['STUDIO_DESKTOP_INSTANCE'] = runtime['instance_id']
    os.environ['STUDIO_DATA_DIR'] = runtime.get('data_root', str(root))
    if bridge_token:
        os.environ['STUDIO_AGENT_TOKEN'] = bridge_token
    from studio_mcp import mcp as server
    server.run(transport='stdio')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
