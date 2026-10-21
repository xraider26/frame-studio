import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Frame Studio — Agent Workflow',
  description: 'Local content studio with MCP control, generator handoffs and configurable review steps.',
};

export default function StudioLayout({ children }: { children: React.ReactNode }) {
  return children;
}
