<script lang="ts">
  import { t } from '../../lib/i18n.svelte';
  import { dismiss, toasts, type Toast } from '../../lib/toast.svelte';
  import Icon from './Icon.svelte';

  const icons = { success: 'check', error: 'warning', info: 'info' } as const;

  // each toast counts down on its own and pauses while hovered or focused
  function lifetime(node: HTMLElement, toast: Toast) {
    let left = toast.ms;
    let since = Date.now();
    let timer = setTimeout(() => dismiss(toast.id), left);
    const pause = () => {
      clearTimeout(timer);
      left -= Date.now() - since;
    };
    const resume = () => {
      since = Date.now();
      timer = setTimeout(() => dismiss(toast.id), Math.max(800, left));
    };
    node.addEventListener('pointerenter', pause);
    node.addEventListener('pointerleave', resume);
    node.addEventListener('focusin', pause);
    node.addEventListener('focusout', resume);
    return { destroy: () => clearTimeout(timer) };
  }
</script>

<div class="stack" aria-live="polite" data-testid="toasts">
  {#each toasts.list as toast (toast.id)}
    <div
      class="toast {toast.kind}"
      role={toast.kind === 'error' ? 'alert' : 'status'}
      use:lifetime={toast}
      data-testid="notice"
      data-kind={toast.kind}
    >
      <span class="ico"><Icon name={icons[toast.kind]} size={16} stroke={2.2} /></span>
      <span class="text">{toast.text}</span>
      {#if toast.action}
        <button
          class="action"
          onclick={() => {
            toast.action?.run();
            dismiss(toast.id);
          }}>{toast.action.label}</button
        >
      {/if}
      <button class="close" aria-label={t('close')} onclick={() => dismiss(toast.id)}>
        <Icon name="x" size={14} />
      </button>
      <span class="timer" style="animation-duration:{toast.ms}ms" aria-hidden="true"></span>
    </div>
  {/each}
</div>

<style>
  .stack {
    /* bottom centre: never covers the main buttons, which sit at the right */
    position: fixed;
    left: 50%;
    transform: translateX(-50%);
    bottom: 16px;
    z-index: 90;
    display: flex;
    flex-direction: column;
    gap: 8px;
    width: min(420px, calc(100vw - 32px));
    pointer-events: none;
  }
  .toast {
    position: relative;
    overflow: hidden;
    pointer-events: auto;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 12px 10px 12px 12px;
    border-radius: var(--radius);
    background: var(--panel);
    border: 1px solid var(--line);
    box-shadow: var(--shadow-lg);
    animation: slide-in var(--slow) var(--spring);
  }
  .ico {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    flex: none;
    background: var(--accent-soft);
    color: var(--accent);
  }
  .success .ico {
    background: var(--ok-soft);
    color: var(--ok);
  }
  .error .ico {
    background: var(--danger-soft);
    color: var(--danger);
  }
  .text {
    flex: 1;
    min-width: 0;
  }
  button {
    border: 0;
    background: none;
    border-radius: 8px;
  }
  .action {
    font-weight: 700;
    color: var(--accent);
    padding: 6px 10px;
  }
  .action:hover {
    background: var(--accent-soft);
  }
  .close {
    color: var(--muted);
    padding: 6px;
    display: grid;
  }
  .close:hover {
    background: var(--panel-2);
    color: var(--text);
  }
  .timer {
    position: absolute;
    left: 0;
    bottom: 0;
    height: 3px;
    width: 100%;
    background: color-mix(in srgb, var(--accent) 35%, transparent);
    transform-origin: left;
    animation: drain linear forwards;
  }
  .toast:hover .timer,
  .toast:focus-within .timer {
    animation-play-state: paused;
  }
  @keyframes slide-in {
    from {
      opacity: 0;
      transform: translateY(12px) scale(0.97);
    }
  }
  @keyframes drain {
    to {
      transform: scaleX(0);
    }
  }
</style>
