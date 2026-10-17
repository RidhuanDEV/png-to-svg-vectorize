<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { HTMLButtonAttributes } from 'svelte/elements';
  import Icon, { type IconName } from './Icon.svelte';

  type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
  let {
    variant = 'secondary',
    size = 'md',
    icon,
    loading = false,
    wide = false,
    iconOnly = false,
    children,
    disabled,
    ...rest
  }: HTMLButtonAttributes & {
    variant?: Variant;
    size?: 'sm' | 'md' | 'lg';
    icon?: IconName;
    loading?: boolean;
    wide?: boolean;
    /** Icon button: the text is the accessible name only (also shown as a tooltip). */
    iconOnly?: boolean;
    children?: Snippet;
  } = $props();
</script>

<button
  {...rest}
  class="btn {variant} {size}"
  class:wide
  class:icon-only={iconOnly}
  disabled={disabled || loading}
  aria-busy={loading || undefined}
>
  {#if loading}
    <span class="spinner" aria-hidden="true"></span>
  {:else if icon}
    <Icon name={icon} size={size === 'sm' ? 15 : 18} />
  {/if}
  {#if children}
    <span class:sr-only={iconOnly}>{@render children()}</span>
  {/if}
</button>

<style>
  .btn {
    --h: calc(36px * var(--d));
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    min-height: var(--h);
    padding: 0 14px;
    border-radius: var(--radius-sm);
    border: 1px solid transparent;
    font-weight: 600;
    font-size: calc(14px * var(--ts));
    line-height: 1.2;
    white-space: nowrap;
    user-select: none;
    transition:
      background var(--fast) var(--ease),
      border-color var(--fast) var(--ease),
      box-shadow var(--fast) var(--ease),
      transform var(--fast) var(--ease),
      color var(--fast) var(--ease);
  }
  .btn:active:not(:disabled) {
    transform: scale(0.97);
  }
  .btn:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }
  .sm {
    --h: calc(30px * var(--d));
    padding: 0 10px;
    font-size: calc(13px * var(--ts));
    gap: 6px;
  }
  .lg {
    --h: calc(44px * var(--d));
    padding: 0 20px;
    font-size: calc(15px * var(--ts));
    border-radius: var(--radius);
  }
  .wide {
    width: 100%;
  }
  .icon-only {
    padding: 0;
    width: var(--h);
  }
  .primary {
    background: var(--accent);
    color: var(--accent-text);
    box-shadow: 0 1px 2px color-mix(in srgb, var(--accent) 30%, transparent);
  }
  .primary:hover:not(:disabled) {
    background: var(--accent-hover);
    box-shadow: 0 4px 14px color-mix(in srgb, var(--accent) 30%, transparent);
  }
  .secondary {
    background: var(--panel);
    border-color: var(--line);
    color: var(--text);
  }
  .secondary:hover:not(:disabled) {
    border-color: var(--line-strong);
    background: var(--panel-2);
  }
  .ghost {
    background: transparent;
    color: var(--muted);
  }
  .ghost:hover:not(:disabled) {
    background: var(--panel-2);
    color: var(--text);
  }
  .danger {
    background: var(--danger-soft);
    color: var(--danger);
  }
  .danger:hover:not(:disabled) {
    background: var(--danger);
    color: var(--panel);
  }
  .spinner {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    border: 2px solid currentColor;
    border-right-color: transparent;
    animation: spin 0.7s linear infinite;
  }
  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
