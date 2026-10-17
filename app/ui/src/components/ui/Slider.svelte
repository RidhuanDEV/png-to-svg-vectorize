<script lang="ts">
  // Custom slider (ARIA slider): pointer drag on the track, arrows / PageUp / PageDown / Home / End.
  let {
    value,
    min,
    max,
    step,
    label,
    format = (v: number) => String(v),
    onchange,
    testid,
  }: {
    value: number;
    min: number;
    max: number;
    step: number;
    label: string;
    format?: (v: number) => string;
    onchange: (v: number) => void;
    testid?: string;
  } = $props();

  let track: HTMLDivElement;
  let dragging = $state(false);
  const pct = $derived(((value - min) / (max - min)) * 100);

  function snap(v: number): number {
    const s = Math.round((v - min) / step) * step + min;
    return Number(Math.min(max, Math.max(min, s)).toFixed(4));
  }
  function fromPointer(e: PointerEvent) {
    const r = track.getBoundingClientRect();
    onchange(snap(min + ((e.clientX - r.left) / r.width) * (max - min)));
  }
  function key(e: KeyboardEvent) {
    const big = (max - min) / 10;
    const map: Record<string, number> = {
      ArrowRight: value + step,
      ArrowUp: value + step,
      ArrowLeft: value - step,
      ArrowDown: value - step,
      PageUp: value + big,
      PageDown: value - big,
      Home: min,
      End: max,
    };
    if (!(e.key in map)) return;
    e.preventDefault();
    onchange(snap(map[e.key]));
  }
</script>

<div class="slider">
  <div class="head">
    <span>{label}</span>
    <b class="val">{format(value)}</b>
  </div>
  <div
    bind:this={track}
    class="track"
    class:dragging
    role="slider"
    tabindex="0"
    aria-label={label}
    aria-valuemin={min}
    aria-valuemax={max}
    aria-valuenow={value}
    aria-valuetext={format(value)}
    onkeydown={key}
    onpointerdown={(e) => {
      dragging = true;
      (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
      fromPointer(e);
    }}
    onpointermove={(e) => dragging && fromPointer(e)}
    onpointerup={() => (dragging = false)}
    onpointercancel={() => (dragging = false)}
    data-testid={testid}
  >
    <span class="rail"><span class="fill" style="width:{pct}%"></span></span>
    <span class="thumb" style="left:{pct}%"></span>
  </div>
</div>

<style>
  .slider {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .head {
    display: flex;
    justify-content: space-between;
    gap: 8px;
    font-size: calc(13px * var(--ts));
  }
  .val {
    font-family: var(--mono);
    font-variant-numeric: tabular-nums;
    color: var(--accent);
  }
  .track {
    position: relative;
    height: 24px;
    cursor: pointer;
    touch-action: none;
    border-radius: 999px;
  }
  .rail {
    position: absolute;
    left: 0;
    right: 0;
    top: 50%;
    height: 6px;
    transform: translateY(-50%);
    border-radius: 999px;
    background: var(--panel-3);
    overflow: hidden;
  }
  .fill {
    display: block;
    height: 100%;
    background: var(--accent);
  }
  .thumb {
    position: absolute;
    top: 50%;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--panel);
    border: 2px solid var(--accent);
    box-shadow: var(--shadow);
    transform: translate(-50%, -50%);
    transition: transform var(--fast) var(--spring);
  }
  .track:hover .thumb,
  .dragging .thumb {
    transform: translate(-50%, -50%) scale(1.15);
  }
</style>
