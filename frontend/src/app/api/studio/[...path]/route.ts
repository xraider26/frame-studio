import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { NextRequest } from 'next/server';

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const parts = (await context.params).path;
  const isCommand = parts.length === 1 && parts[0] === 'command' && request.method === 'POST';
  const isMedia = parts.length === 3 && parts[0] === 'media' && request.method === 'GET' &&
    /^[a-f0-9]{32}$/.test(parts[1]) && /^[a-f0-9]{32}\.(png|jpg|webp|mp4)$/.test(parts[2]);
  const isExport = parts.length === 3 && parts[0] === 'export' && request.method === 'GET' &&
    /^[a-f0-9]{32}$/.test(parts[1]) && /^[a-f0-9]{32}\.zip$/.test(parts[2]);
  if (!isCommand && !isMedia && !isExport) return Response.json({ message: 'Not found' }, { status: 404 });
  const own = new URL(request.url);
  const publicUrl = new URL(`${own.protocol}//${request.headers.get('host') || own.host}`);
  if (!['127.0.0.1', 'localhost', '[::1]'].includes(publicUrl.hostname)) {
    return Response.json({ message: 'This studio is available on the local machine only.' }, { status: 403 });
  }
  if (isCommand && request.headers.get('origin') !== publicUrl.origin) {
    return Response.json({ message: 'Open the studio page to use browser controls.' }, { status: 403 });
  }
  try {
    const dataDir = process.env.STUDIO_DATA_DIR || path.resolve(process.cwd(), '..', 'studio_data');
    const token = (await readFile(path.join(dataDir, 'browser.token'), 'utf8')).trim();
    const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
    if (isCommand) headers['Content-Type'] = 'application/json';
    if (request.headers.has('range')) headers.Range = request.headers.get('range')!;
    const backend = process.env.STUDIO_API_URL || 'http://127.0.0.1:8010';
    const response = await fetch(`${backend}/studio/v1/${parts.map(encodeURIComponent).join('/')}`, {
      method: request.method, headers, body: isCommand ? await request.text() : undefined,
      cache: 'no-store', signal: AbortSignal.timeout(45000), redirect: 'error',
    });
    const outgoing = new Headers();
    for (const key of ['content-type', 'content-length', 'content-range', 'accept-ranges', 'content-disposition']) {
      if (response.headers.has(key)) outgoing.set(key, response.headers.get(key)!);
    }
    outgoing.set('Cache-Control', 'no-store');
    outgoing.set('X-Content-Type-Options', 'nosniff');
    return new Response(response.body, { status: response.status, headers: outgoing });
  } catch {
    return Response.json({ error: 'backend_unavailable', message: 'Studio backend is offline. Reopen Frame Studio, or run launch-studio.ps1 when using a source checkout.' }, { status: 503 });
  }
}

export const POST = proxy;
export const GET = proxy;
