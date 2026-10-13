<script lang="ts" generics="T extends string">
  // Custom dropdown (ARIA select-only combobox): trigger + popup listbox, keyboard (↑ ↓ Home End Enter Esc), click outside closes.
  import Icon, { type IconName } from './Icon.svelte';

  let {
    options,
    value,
    label,
    onchange,
    icon,
    testid,
  }: {
    options: { value: T; label: string }[];
    value: T;
    label: string;
    onchange: (v: T) => void;
    icon?: IconName;
    testid?: string;
  } = $props();

  const uid = `sel-${Math.random().toString(36).slice(2, 8)}`;
  let open = $state(false);
  let active = $state(0);
  let root: HTMLDivElement;
  let trigger: HTMLButtonElement;
  const current = $derived(options.find((o) => o.value === value) ?? options[0]);

  function show() {
    active = Math.max(0, options.findIndex((o) => o.value === value));
    open = true;
  }
  function choose(i: number) {
    onchange(options[i].value);
    open = false;
    trigger.focus();
  }
  function key(e: KeyboardEvent) {
    if (!open) {
      if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) {
        e.preventDefault();
        show();
      }
      return;
    }
    const moves: Record<string, number> = { ArrowDown: active + 1, ArrowUp: active - 1, Home: 0, End: options.length - 1 };
    if (e.key in moves) {
      e.preventDefault();
      active = Math.min(options.length - 1, Math.max(0, moves[e.key]));
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      choose(active);
    } else if (e.key === 'Escape' || e.key === 'Tab') {
      open = false;
    }
  }
  $effect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => {
      if (!root.contains(e.target as Node)) open = false;
    };
    window.addEventListener('pointerdown', away);
    return () => window.removeEventListener('pointerdown', away);
  });
</script>

<div class="sel" bind:this={root}>
  <button
    bind:this={trigger}
    type="button"
    role="combobox"
    class="trigger"
    class:open
    aria-haspopup="listbox"
    aria-expanded={open}
    aria-controls={uid}
    aria-label={label}
    aria-activedescendant={open ? `${uid}-${active}` : undefined}
    onclick={() => (open ? (open = false) : show())}
    onkeydown={key}
    data-testid={testid}
  >
    {#if icon}<Icon name={icon} size={16} />{/if}
    <span>{current?.label}</span>
    <span class="chev"><Icon name="chevronDown" size={14} /></span>
  </button>
  {#if open}
    <ul id={uid} role="listbox" aria-label={label} class="menu">
      {#each options as o, i (o.value)}
        <!-- options are chosen with the trigger's keyboard handler (aria-activedescendant) -->
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <li
          id="{uid}-{i}"
          role="option"
          aria-selected={o.value === value}
          class:active={i === active}
          onpointerenter={() => (active = i)}
          onclick={() => choose(i)}
          data-testid={testid ? `${testid}-${o.value}` : undefined}
        >
          <span>{o.label}</span>
          {#if o.value === value}<Icon name="check" size={15} />{/if}
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .sel {
    position: relative;
  }
  .trigger {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    height: 34px;
    padding: 0 10px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--line);
    background: var(--panel);
    font-weight: 600;
    font-size: 13px;
    transition: border-color var(--fast) var(--ease), background var(--fast) var(--ease);
  }
  .trigger:hover,
  .trigger.open {
    border-color: var(--line-strong);
    background: var(--panel-2);
  }
  .chev {
    color: var(--muted);
    transition: transform var(--medium) var(--ease);
  }
  .open .chev {
    transform: rotate(180deg);
  }
  .menu {
    position: absolute;
    right: 0;
    top: calc(100% + 6px);
    z-index: 50;
    min-width: 180px;
    margin: 0;
    padding: 4px;
    list-style: none;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    box-shadow: var(--shadow-lg);
    animation: pop-in var(--medium) var(--ease);
    transform-origin: top right;
  }
  li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 8px 10px;
    border-radius: 8px;
    cursor: pointer;
  }
  li.active {
    background: var(--panel-2);
  }
  li[aria-selected='true'] {
    color: var(--accent);
    font-weight: 600;
  }
</style>
