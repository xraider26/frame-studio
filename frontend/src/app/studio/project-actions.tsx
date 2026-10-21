'use client';

import { useState } from 'react';
import { Copy, Trash2, X, RotateCcw } from 'lucide-react';
import { studioApi } from './client';

type Project = { id: string; name: string; revision: number };

export function ProjectActions({ project, onSelect, onRemoved }: { project: Project | null; onSelect: (id: string) => Promise<void>; onRemoved: () => Promise<void> }) {
  const [dialog, setDialog] = useState('');
  const [name, setName] = useState('');
  const [trash, setTrash] = useState<Project[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function perform(fn: () => Promise<void>) {
    setBusy(true); setError('');
    try { await fn(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <><div className="fs-project-actions">{project && <><button title="Duplicate project" onClick={() => { setName(project.name + ' (copy)'); setDialog('duplicate'); setError(''); }}><Copy size={12} /> Duplicate</button><button title="Delete project" onClick={() => { setDialog('delete'); setError(''); }}><Trash2 size={12} /> Delete</button></>}<button title="Open Trash" onClick={() => perform(async () => { setTrash(await studioApi<Project[]>('list_deleted')); setDialog('trash'); })}><RotateCcw size={12} /> Trash</button></div>
    {dialog && <div className="fs-modal-backdrop"><section className="fs-modal" role="dialog" aria-modal="true" aria-label={dialog === 'duplicate' ? 'Duplicate project' : dialog === 'delete' ? 'Delete project' : 'Project Trash'}><button className="fs-close" aria-label="Close project actions" onClick={() => setDialog('')}><X size={18} /></button><div className="fs-eyebrow">PROJECT ACTIONS</div><h2>{dialog === 'duplicate' ? 'Make a fresh copy.' : dialog === 'delete' ? 'Move project to Trash?' : 'Project Trash'}</h2>{error && <p role="alert" className="fs-body">{error}</p>}
      {dialog === 'duplicate' && <><label className="fs-label">New project name<input value={name} onChange={e => setName(e.target.value)} /></label><p className="fs-body">Copies the brief, script, shot plan, settings and references. Generated takes and jobs start fresh. Approval is enabled at every step in the new copy.</p><button className="fs-primary" disabled={busy || !name.trim() || !project} onClick={() => perform(async () => { const copy = await studioApi<Project>('duplicate_project', { project_id: project!.id, name }); setDialog(''); await onSelect(copy.id); })}><Copy size={14} /> Duplicate project</button></>}
      {dialog === 'delete' && <><p className="fs-body"><strong>{project?.name}</strong> will be removed from your active projects. Its files stay on this computer. You can restore it from Trash.</p><button className="fs-primary" disabled={busy || !project} onClick={() => perform(async () => { await studioApi('delete_project', { project_id: project!.id, expected_revision: project!.revision }); setDialog(''); await onRemoved(); })}><Trash2 size={14} /> Move to Trash</button></>}
      {dialog === 'trash' && <>{trash.length === 0 && <p className="fs-body">Trash is empty.</p>}{trash.map(p => <div className="fs-connection-item" key={p.id}><strong>{p.name}</strong><button disabled={busy} className="fs-link" onClick={() => perform(async () => { await studioApi('restore_project', { project_id: p.id }); setTrash(await studioApi<Project[]>('list_deleted')); await onRemoved(); })}>Restore project</button></div>)}</>}
    </section></div>}
  </>;
}
