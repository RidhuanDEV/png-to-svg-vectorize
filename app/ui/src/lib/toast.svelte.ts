// Toast messages: short, stacked, auto-dismissed (paused while hovered), with an optional action such as Undo.

export type ToastKind = 'success' | 'error' | 'info';

export interface Toast {
  id: number;
  kind: ToastKind;
  text: string;
  action?: { label: string; run: () => void };
  ms: number;
}

export const toasts = $state({ list: [] as Toast[] });

let next = 1;
const MAX = 4;

export function toast(kind: ToastKind, text: string, opts: { action?: Toast['action']; ms?: number } = {}): number {
  const id = next++;
  const ms = opts.ms ?? (kind === 'error' ? 8000 : 4500);
  toasts.list = [...toasts.list, { id, kind, text, action: opts.action, ms }].slice(-MAX);
  return id;
}

export function dismiss(id: number): void {
  toasts.list = toasts.list.filter((t) => t.id !== id);
}
