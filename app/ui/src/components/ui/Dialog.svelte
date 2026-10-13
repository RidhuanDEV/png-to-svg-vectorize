<script lang="ts">
  // Confirmation dialog: focus moves into it and stays there, Esc cancels, focus returns afterwards.
  import Button from './Button.svelte';

  let {
    open,
    title,
    body,
    confirm,
    cancel,
    danger = false,
    onconfirm,
    oncancel,
  }: {
    open: boolean;
    title: string;
    body: string;
    confirm: string;
    cancel: string;
    danger?: boolean;
    onconfirm: () => void;
    oncancel: () => void;
  } = $props();

  let card: HTMLDivElement | undefined = $state();
  let previous: HTMLElement | null = null;

  $effect(() => {
    if (!open || !card) return;
    previous = document.activeElement as HTMLElement | null;
    card.querySelector<HTMLElement>('[data-autofocus] button, button')?.focus();
    return () => previous?.focus?.();
  });

  function trap(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault();
      oncancel();
      return;
    }
    if (e.key !== 'Tab' || !card) return;
    const items = Array.from(card.querySelectorAll<HTMLElement>('button:not(:disabled)'));
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }
</script>

{#if open}
  <div class="scrim" role="presentation" onpointerdown={(e) => e.target === e.currentTarget && oncancel()}>
    <div
      bind:this={card}
      class="card"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="dlg-title"
      aria-describedby="dlg-body"
      tabindex="-1"
      onkeydown={trap}
    >
      <h2 id="dlg-title">{title}</h2>
      <p id="dlg-body">{body}</p>
      <div class="actions">
        <span data-autofocus><Button variant="secondary" onclick={oncancel}>{cancel}</Button></span>
        <Button variant={danger ? 'danger' : 'primary'} onclick={onconfirm} data-testid="dialog-confirm">{confirm}</Button>
      </div>
    </div>
  </div>
{/if}

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 80;
    display: grid;
    place-items: center;
    background: var(--scrim);
    animation: fade-in var(--medium) var(--ease);
    padding: 16px;
  }
  .card {
    width: min(420px, 100%);
    background: var(--panel);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    padding: 22px;
    animation: pop-in var(--slow) var(--spring);
  }
  h2 {
    margin: 0 0 6px;
    font-size: 18px;
  }
  p {
    margin: 0 0 18px;
    color: var(--muted);
  }
  .actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
</style>
