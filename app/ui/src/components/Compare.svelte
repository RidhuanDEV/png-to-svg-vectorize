<script lang="ts">
  import type { Job } from '../lib/api';
  import { t } from '../lib/i18n.svelte';
  import type { Media } from '../lib/store.svelte';

  let { job, media }: { job: Job | undefined; media: Media | undefined } = $props();

  type Mode = 'side' | 'slider';
  type Layer = 'all' | 'fill' | 'outline';
  const MAX_ZOOM = 8; // 800 % of the image's own pixels

  let mode = $state<Mode>('side');
  let layer = $state<Layer>('all');
  let view = $state({ s: 1, x: 0, y: 0 });
  let paneW = $state(0);
  let paneH = $state(0);
  let split = $state(0.5);
  let manual = false; // the user zoomed or panned: stop re-fitting on resize
  let shownJob: string | undefined;

  const w = $derived(job?.width ?? 1);
  const h = $derived(job?.height ?? 1);
  const svgUrl = $derived(layer === 'fill' ? media?.fillUrl : layer === 'outline' ? media?.outlineUrl : media?.svgUrl);
  const minZoom = $derived(Math.min(0.05, fitScale() / 2));

  function fitScale(): number {
    if (!paneW || !paneH) return 1;
    return Math.min(paneW / w, paneH / h) * 0.95;
  }

  function fit(): void {
    manual = false;
    const s = fitScale();
    view = { s, x: (paneW - w * s) / 2, y: (paneH - h * s) / 2 };
  }

  // fit a new image, and keep it fitted while the panes resize until the user zooms or pans
  $effect(() => {
    if (job?.id !== shownJob) {
      shownJob = job?.id;
      manual = false;
    }
    if (job && paneW && paneH && !manual) fit();
  });

  function zoomAt(factor: number, cx: number, cy: number): void {
    const s = Math.min(MAX_ZOOM, Math.max(minZoom, view.s * factor));
    const k = s / view.s;
    manual = true;
    view = { s, x: cx - (cx - view.x) * k, y: cy - (cy - view.y) * k };
  }

  // wheel must be non-passive to stop the page from scrolling while zooming
  function wheelZoom(node: HTMLElement) {
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = node.getBoundingClientRect();
      zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
    };
    node.addEventListener('wheel', onWheel, { passive: false });
    return { destroy: () => node.removeEventListener('wheel', onWheel) };
  }

  let drag: { id: number; x: number; y: number } | null = null;
  function down(e: PointerEvent) {
    if ((e.target as HTMLElement).closest('.handle')) return;
    drag = { id: e.pointerId, x: e.clientX, y: e.clientY };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }
  function move(e: PointerEvent) {
    if (!drag || drag.id !== e.pointerId) return;
    manual = true;
    view = { ...view, x: view.x + e.clientX - drag.x, y: view.y + e.clientY - drag.y };
    drag = { id: e.pointerId, x: e.clientX, y: e.clientY };
  }
  function up() {
    drag = null;
  }

  let sliding = false;
  function slideMove(e: PointerEvent) {
    if (!sliding) return;
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    split = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width));
  }

  function key(e: KeyboardEvent) {
    const pan: Record<string, [number, number]> = { ArrowLeft: [40, 0], ArrowRight: [-40, 0], ArrowUp: [0, 40], ArrowDown: [0, -40] };
    if (e.key === '+' || e.key === '=') zoomAt(1.25, paneW / 2, paneH / 2);
    else if (e.key === '-') zoomAt(0.8, paneW / 2, paneH / 2);
    else if (e.key === '0') fit();
    else if (pan[e.key]) {
      manual = true;
      view = { ...view, x: view.x + pan[e.key][0], y: view.y + pan[e.key][1] };
    } else return;
    e.preventDefault();
  }

  const imgStyle = $derived(
    `left:${view.x}px;top:${view.y}px;width:${w * view.s}px;height:${h * view.s}px;` +
      (view.s >= 2 ? 'image-rendering:pixelated;' : ''),
  );
</script>

<div class="panel compare">
  <div class="toolbar">
    <div class="seg" role="group" aria-label={t('compare')}>
      <button class:on={mode === 'side'} aria-pressed={mode === 'side'} onclick={() => (mode = 'side')}
        data-testid="mode-side">{t('sideBySide')}</button>
      <button class:on={mode === 'slider'} aria-pressed={mode === 'slider'} onclick={() => (mode = 'slider')}
        data-testid="mode-slider">{t('slider')}</button>
    </div>
    <label class="layers">
      <span class="muted">{t('layers')}</span>
      <select bind:value={layer} data-testid="layer">
        <option value="all">{t('layer_all')}</option>
        <option value="fill">{t('layer_fill')}</option>
        <option value="outline">{t('layer_outline')}</option>
      </select>
    </label>
    <div class="zoom">
      <button onclick={() => zoomAt(0.8, paneW / 2, paneH / 2)} aria-label={t('zoomOut')}>−</button>
      <span class="pct" data-testid="zoom">{Math.round(view.s * 100)}%</span>
      <button onclick={() => zoomAt(1.25, paneW / 2, paneH / 2)} aria-label={t('zoomIn')}>+</button>
      <button onclick={fit}>{t('fit')}</button>
    </div>
  </div>

  {#if !job}
    <div class="empty muted">{t('selectHint')}</div>
  {:else if mode === 'side'}
    <div class="panes">
      {#each ['source', 'svg'] as which (which)}
        <div class="pane">
          <span class="label">{which === 'source' ? t('original') : t('vector')}</span>
          <!-- pan/zoom canvas with its own keyboard handling (role=application); Svelte counts that role as non-interactive -->
          <!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
          <div
            class="viewport"
            data-testid="viewport-{which}"
            role="application"
            aria-label={which === 'source' ? t('original') : t('vector')}
            tabindex="0"
            bind:clientWidth={paneW}
            bind:clientHeight={paneH}
            use:wheelZoom
            onpointerdown={down}
            onpointermove={move}
            onpointerup={up}
            onpointercancel={up}
            onkeydown={key}
          >
            {#if which === 'source' && media?.sourceUrl}
              <img src={media.sourceUrl} alt="" style={imgStyle} draggable="false" />
            {:else if which === 'svg' && svgUrl}
              <img src={svgUrl} alt="" style={imgStyle} draggable="false" data-testid="svg-image" />
            {:else if which === 'svg'}
              <div class="empty muted">{t('notReady')}</div>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {:else}
    <!-- pan/zoom canvas with its own keyboard handling (role=application); Svelte counts that role as non-interactive -->
    <!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
    <div
      class="viewport single"
      data-testid="viewport-slider"
      role="application"
      aria-label={t('slider')}
      tabindex="0"
      bind:clientWidth={paneW}
      bind:clientHeight={paneH}
      use:wheelZoom
      onpointerdown={down}
      onpointermove={(e) => {
        move(e);
        slideMove(e);
      }}
      onpointerup={() => {
        up();
        sliding = false;
      }}
      onpointercancel={up}
      onkeydown={key}
    >
      {#if media?.sourceUrl}
        <img src={media.sourceUrl} alt="" style={imgStyle} draggable="false" />
      {/if}
      {#if svgUrl}
        <img src={svgUrl} alt="" draggable="false" style="{imgStyle}clip-path:inset(0 0 0 {split * paneW - view.x}px);" />
      {/if}
      <span class="label">{t('original')}</span>
      <span class="label right">{t('vector')}</span>
      <div
        class="handle"
        style="left:{split * 100}%"
        role="slider"
        aria-label={t('slider')}
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow={Math.round(split * 100)}
        tabindex="0"
        data-testid="slider-handle"
        onpointerdown={(e) => {
          sliding = true;
          (e.currentTarget as HTMLElement).parentElement?.setPointerCapture(e.pointerId);
        }}
        onkeydown={(e) => {
          if (e.key === 'ArrowLeft') split = Math.max(0, split - 0.02);
          else if (e.key === 'ArrowRight') split = Math.min(1, split + 0.02);
        }}
      ></div>
    </div>
  {/if}
</div>

<style>
  .compare {
    height: 100%;
    display: flex;
    flex-direction: column;
    gap: 10px;
    min-height: 360px;
  }
  .toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
  }
  .seg {
    display: inline-flex;
  }
  .seg button {
    border-radius: 0;
  }
  .seg button:first-child {
    border-radius: 8px 0 0 8px;
  }
  .seg button:last-child {
    border-radius: 0 8px 8px 0;
    margin-left: -1px;
  }
  .seg button.on {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--accent-text);
  }
  .layers {
    display: inline-flex;
    gap: 6px;
    align-items: center;
  }
  .zoom {
    margin-left: auto;
    display: inline-flex;
    gap: 4px;
    align-items: center;
  }
  .pct {
    min-width: 52px;
    text-align: center;
    font-variant-numeric: tabular-nums;
  }
  .panes {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .pane {
    position: relative;
    min-height: 0;
    display: flex;
  }
  .viewport {
    position: relative;
    flex: 1;
    overflow: hidden;
    border-radius: 8px;
    border: 1px solid var(--line);
    cursor: grab;
    touch-action: none;
    background: repeating-conic-gradient(var(--checker-a) 0% 25%, var(--checker-b) 0% 50%) 0 0 / 20px 20px;
  }
  .viewport.single {
    flex: 1;
    min-height: 0;
  }
  .viewport:active {
    cursor: grabbing;
  }
  .viewport img {
    position: absolute;
    max-width: none;
    user-select: none;
    pointer-events: none;
  }
  .label {
    position: absolute;
    top: 8px;
    left: 8px;
    z-index: 2;
    background: color-mix(in srgb, var(--panel) 85%, transparent);
    border: 1px solid var(--line);
    border-radius: 6px;
    padding: 1px 8px;
    font-size: 12px;
  }
  .label.right {
    left: auto;
    right: 8px;
  }
  .handle {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 4px;
    margin-left: -2px;
    background: var(--accent);
    cursor: ew-resize;
    z-index: 3;
  }
  .handle::after {
    content: '';
    position: absolute;
    top: 50%;
    left: -8px;
    width: 20px;
    height: 20px;
    margin-top: -10px;
    border-radius: 50%;
    background: var(--accent);
    border: 2px solid var(--panel);
  }
  .empty {
    display: grid;
    place-items: center;
    height: 100%;
    flex: 1;
    text-align: center;
    padding: 16px;
  }
  @media (max-width: 700px) {
    .panes {
      grid-template-columns: 1fr;
      grid-template-rows: 1fr 1fr;
    }
  }
</style>
