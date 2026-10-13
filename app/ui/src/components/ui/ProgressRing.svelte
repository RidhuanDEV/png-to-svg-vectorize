<script lang="ts">
  // Circular progress. `value` null = waiting (a calm, slow pulse instead of a spinner).
  let { value, size = 36, label }: { value: number | null; size?: number; label: string } = $props();
  const r = 15;
  const c = 2 * Math.PI * r;
  const offset = $derived(value === null ? c : c * (1 - Math.min(1, Math.max(0, value))));
</script>

<span
  class="ring"
  class:waiting={value === null}
  style="width:{size}px;height:{size}px"
  role="progressbar"
  aria-label={label}
  aria-valuemin="0"
  aria-valuemax="100"
  aria-valuenow={value === null ? undefined : Math.round(value * 100)}
>
  <svg viewBox="0 0 36 36">
    <circle class="bg" cx="18" cy="18" r={r} />
    <circle class="fg" cx="18" cy="18" r={r} stroke-dasharray={c} stroke-dashoffset={offset} />
  </svg>
  {#if value !== null}<b>{Math.round(value * 100)}</b>{/if}
</span>

<style>
  .ring {
    position: relative;
    display: inline-grid;
    place-items: center;
    flex: none;
  }
  svg {
    position: absolute;
    inset: 0;
    transform: rotate(-90deg);
  }
  circle {
    fill: none;
    stroke-width: 3.5;
  }
  .bg {
    stroke: var(--panel-3);
  }
  .fg {
    stroke: var(--accent);
    stroke-linecap: round;
    transition: stroke-dashoffset var(--slow) var(--ease);
  }
  .waiting .bg {
    animation: breathe 1.8s ease-in-out infinite;
  }
  b {
    font-size: 10px;
    font-variant-numeric: tabular-nums;
    color: var(--muted);
  }
  @keyframes breathe {
    50% {
      stroke: var(--line-strong);
    }
  }
</style>
