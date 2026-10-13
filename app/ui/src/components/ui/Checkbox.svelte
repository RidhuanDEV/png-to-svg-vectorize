<script lang="ts">
  // Custom checkbox: a real (visually hidden) input keeps keyboard, form and screen-reader behaviour.
  let {
    checked = $bindable(false),
    label,
    hideLabel = false,
    onchange,
    testid,
  }: { checked?: boolean; label: string; hideLabel?: boolean; onchange?: (v: boolean) => void; testid?: string } =
    $props();
</script>

<label class="cb" class:on={checked}>
  <input
    type="checkbox"
    class="sr-only"
    bind:checked
    onchange={() => onchange?.(checked)}
    data-testid={testid}
  />
  <span class="box" aria-hidden="true">
    <svg viewBox="0 0 24 24"><path d="M5 12.5 10 17 19 7" /></svg>
  </span>
  <span class:sr-only={hideLabel}>{label}</span>
</label>

<style>
  .cb {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    user-select: none;
  }
  .box {
    width: 22px;
    height: 22px;
    border-radius: 7px;
    border: 2px solid var(--line-strong);
    background: var(--panel);
    display: grid;
    place-items: center;
    flex: none;
    transition:
      background var(--fast) var(--ease),
      border-color var(--fast) var(--ease),
      transform var(--fast) var(--spring);
  }
  .cb:hover .box {
    border-color: var(--accent);
  }
  .cb:active .box {
    transform: scale(0.9);
  }
  .on .box {
    background: var(--accent);
    border-color: var(--accent);
  }
  svg {
    width: 16px;
    height: 16px;
    fill: none;
    stroke: var(--accent-text);
    stroke-width: 3;
    stroke-linecap: round;
    stroke-linejoin: round;
    stroke-dasharray: 22;
    stroke-dashoffset: 22;
    transition: stroke-dashoffset var(--medium) var(--ease);
  }
  .on svg {
    stroke-dashoffset: 0;
  }
  input:focus-visible + .box {
    box-shadow: var(--focus);
  }
</style>
