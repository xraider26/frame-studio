"""Frozen desktop service entry point; MCP discovers an already running desktop."""
import argparse
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

from studio.paths import data_root


UNAVAILABLE = 'backend_unavailable: Open Orchestra and retry the MCP connection.'


def load_desktop_runtime(root):
    try:
        runtime = json.loads((Path(root) / 'desktop-runtime.json').read_text(encoding='utf-8'))
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
        return {'api_url': url, 'instance_id': nonce}
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(UNAVAILABLE) from exc


def verify_desktop_runtime(runtime):
    import httpx
    try:
        with httpx.Client(timeout=3, trust_env=False) as client:
            response = client.get(runtime['api_url'] + '/health')
            response.raise_for_status()
            health = response.json()
        if (not isinstance(health, dict) or health.get('service') != 'frame-studio'
                or health.get('status') != 'ok' or health.get('instance_id') != runtime['instance_id']):
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
    if args.data_dir is not None:
        os.environ['STUDIO_DATA_DIR'] = str(args.data_dir.resolve())
    if args.command == 'serve':
        import uvicorn
        from studio.api import create_app
        uvicorn.run(create_app(), host=args.host, port=args.port, log_config=None)
        return 0
    try:
        runtime = load_desktop_runtime(data_root())
        verify_desktop_runtime(runtime)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    os.environ['STUDIO_API_URL'] = runtime['api_url']
    os.environ['STUDIO_DESKTOP_INSTANCE'] = runtime['instance_id']
    from studio_mcp import mcp as server
    server.run(transport='stdio')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
