<script lang="ts" generics="T extends string">
  // Segmented control (single choice) with a sliding highlight. Arrow keys move between options.
  let {
    options,
    value,
    label,
    onchange,
    testid,
    size = 'md',
  }: {
    options: { value: T; label: string }[];
    value: T;
    label: string;
    onchange: (v: T) => void;
    testid?: string;
    size?: 'sm' | 'md';
  } = $props();

  let buttons: HTMLButtonElement[] = $state([]);
  const index = $derived(Math.max(0, options.findIndex((o) => o.value === value)));
  // Equal-width segments: the highlight is positioned with CSS only, so it never goes stale on resize/relabel.
  const pill = $derived(`width:calc((100% - 6px) / ${options.length});transform:translateX(${index * 100}%)`);

  function key(e: KeyboardEvent) {
    const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const next = (index + d + options.length) % options.length;
    onchange(options[next].value);
    buttons[next]?.focus();
  }
</script>

<div class="seg {size}" style="grid-template-columns:repeat({options.length},minmax(0,1fr))" role="radiogroup" aria-label={label} tabindex="-1" onkeydown={key} data-testid={testid}>
  <span class="pill" style={pill} aria-hidden="true"></span>
  {#each options as o, i (o.value)}
    <button
      bind:this={buttons[i]}
      type="button"
      role="radio"
      aria-checked={o.value === value}
      tabindex={o.value === value ? 0 : -1}
      class:on={o.value === value}
      onclick={() => onchange(o.value)}
      data-testid={testid ? `${testid}-${o.value}` : undefined}>{o.label}</button
    >
  {/each}
</div>

<style>
  .seg {
    position: relative;
    display: inline-grid;
    padding: 3px;
    border-radius: 10px;
    background: var(--panel-2);
    border: 1px solid var(--line);
    max-width: 100%;
  }
  .pill {
    position: absolute;
    top: 3px;
    bottom: 3px;
    left: 3px;
    border-radius: 8px;
    background: var(--seg-on);
    box-shadow: var(--shadow);
    transition:
      transform var(--medium) var(--ease),
      width var(--medium) var(--ease);
  }
  button {
    position: relative;
    z-index: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    border: 0;
    background: none;
    padding: 6px 12px;
    border-radius: 8px;
    font-weight: 600;
    font-size: calc(13px * var(--ts));
    color: var(--muted);
    white-space: nowrap;
    transition: color var(--fast) var(--ease);
  }
  .sm button {
    padding: 4px 10px;
    font-size: calc(12.5px * var(--ts));
  }
  button:hover {
    color: var(--text);
  }
  button.on {
    color: var(--text);
  }
</style>
