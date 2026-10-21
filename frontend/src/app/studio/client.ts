export async function studioApi<T>(operation: string, args: Record<string, unknown> = {}): Promise<T> {
  const res = await fetch('/api/studio/command', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ operation, arguments: args, actor: 'user' }) });
  const data = await res.json();
  if (!res.ok) throw new Error(data.message || data.detail || 'Studio request failed');
  return data;
}
