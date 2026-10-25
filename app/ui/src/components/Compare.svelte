<script lang="ts">
  import type { Job } from '../lib/api';
  import { canRedo, canUndo, hitTest, recolor, redoEdit, removeShape, shapeInfo, undoEdit, viewBox } from '../lib/edit.svelte';
  import { t, tf, tk } from '../lib/i18n.svelte';
  import type { Media } from '../lib/store.svelte';
  import Button from './ui/Button.svelte';
  import ProgressRing from './ui/ProgressRing.svelte';
  import Segmented from './ui/Segmented.svelte';

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
  // light editing: pick a shape on the vector side, recolor / delete it, or give it another shape's color
  let editing = $state(false);
  let sel = $state<number | null>(null);
  let picking = $state(false);
  let busy = $state(false);
  const selInfo = $derived(editing && sel !== null && media?.svgText ? shapeInfo(media.svgText, sel) : null);
  const vb = $derived(media?.svgText ? viewBox(media.svgText) : [1, 1]);

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
      sel = null;
      picking = false;
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
  let press: { x: number; y: number } | null = null;
  function down(e: PointerEvent) {
    if ((e.target as HTMLElement).closest('.handle')) return;
    drag = { id: e.pointerId, x: e.clientX, y: e.clientY };
    press = { x: e.clientX, y: e.clientY };
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }

  /** A click (not a drag) on the vector side while editing selects the shape under the pointer. */
  async function pick(e: PointerEvent) {
    const start = press;
    press = null;
    if (!editing || !start || Math.hypot(e.clientX - start.x, e.clientY - start.y) > 4 || !media?.svgText || !job) return;
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const x = ((e.clientX - r.left - view.x) / (w * view.s)) * vb[0];
    const y = ((e.clientY - r.top - view.y) / (h * view.s)) * vb[1];
    const hit = hitTest(media.svgText, x, y, layer);
    if (picking && sel !== null) {
      picking = false;
      const color = hit !== null ? shapeInfo(media.svgText, hit)?.color : undefined;
      if (color) await change(() => recolor(job, sel ?? 0, color));
      return;
    }
    sel = hit;
  }

  async function change(work: () => Promise<unknown>) {
    busy = true;
    try {
      await work();
    } finally {
      busy = false;
    }
  }

  function toggleEdit() {
    editing = !editing;
    sel = null;
    picking = false;
    if (editing) mode = 'side';
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
    else if ((e.key === 'e' || e.key === 'E') && !e.ctrlKey && !e.metaKey && job?.status === 'done') toggleEdit();
    else if (e.key === 'Escape' && editing) {
      if (picking) picking = false;
      else if (sel !== null) sel = null;
      else editing = false;
    } else if ((e.key === 'Delete' || e.key === 'Backspace') && editing && sel !== null && job) {
      const i = sel;
      sel = null;
      void change(() => removeShape(job, i));
    }
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

<div class="panel compare" data-tour="compare">
  <div class="toolbar">
    <Segmented
      size="sm"
      label={t('compare')}
      value={mode}
      options={[
        { value: 'side', label: t('sideBySide') },
        { value: 'slider', label: t('slider') },
      ]}
      onchange={(m) => (mode = m)}
      testid="mode"
    />
    <span class="layers">
      <span class="muted">{t('layers')}</span>
      <Segmented
        size="sm"
        label={t('layers')}
        value={layer}
        options={[
          { value: 'all', label: t('layer_all') },
          { value: 'fill', label: t('layer_fill') },
          { value: 'outline', label: t('layer_outline') },
        ]}
        onchange={(l) => (layer = l)}
        testid="layer"
      />
    </span>
    <div class="zoom">
      <Button variant="ghost" size="sm" iconOnly icon="zoomOut" title={t('zoomOut')} onclick={() => zoomAt(0.8, paneW / 2, paneH / 2)}>{t('zoomOut')}</Button>
      <span class="pct num" data-testid="zoom">{Math.round(view.s * 100)}%</span>
      <Button variant="ghost" size="sm" iconOnly icon="zoomIn" title={t('zoomIn')} onclick={() => zoomAt(1.25, paneW / 2, paneH / 2)}>{t('zoomIn')}</Button>
      <Button variant="secondary" size="sm" icon="fit" onclick={fit}>{t('fit')}</Button>
      <Button
        variant={editing ? 'primary' : 'ghost'}
        size="sm"
        icon="pen"
        disabled={job?.status !== 'done'}
        aria-pressed={editing}
        onclick={toggleEdit}
        data-testid="edit-toggle">{t('edit')}</Button
      >
    </div>
  </div>

  {#if editing && job}
    <div class="editbar" data-testid="editbar" role="toolbar" aria-label={t('edit')}>
      {#if selInfo}
        <span class="swatch" style="background:{selInfo.color}" aria-hidden="true"></span>
        <label class="color">
          <span>{t('editColor')}</span>
          <input
            type="color"
            value={selInfo.color.toLowerCase()}
            disabled={busy}
            onchange={(e) => {
              const c = e.currentTarget.value.toUpperCase();
              const i = sel;
              if (i !== null) void change(() => recolor(job, i, c));
            }}
            data-testid="edit-color"
          />
        </label>
        <Button variant={picking ? 'primary' : 'ghost'} size="sm" icon="pipette" disabled={busy} aria-pressed={picking}
          onclick={() => (picking = !picking)} data-testid="edit-pick">{t('editTakeColor')}</Button
        >
        <Button variant="ghost" size="sm" icon="trash" disabled={busy} data-testid="edit-delete"
          onclick={() => {
            const i = sel;
            sel = null;
            if (i !== null) void change(() => removeShape(job, i));
          }}>{t('editDelete')}</Button
        >
        <span class="hint muted" role="status">{picking ? t('editPickHint') : ''}</span>
      {:else}
        <span class="hint muted" role="status">{t('editHint')}</span>
      {/if}
      <span class="undo">
        <Button variant="ghost" size="sm" iconOnly icon="undo" title={t('undo')} disabled={busy || !canUndo(job.id)}
          onclick={() => change(() => undoEdit(job))} data-testid="edit-undo">{t('undo')}</Button
        >
        <Button variant="ghost" size="sm" iconOnly icon="redo" title={t('redo')} disabled={busy || !canRedo(job.id)}
          onclick={() => change(() => redoEdit(job))} data-testid="edit-redo">{t('redo')}</Button
        >
      </span>
    </div>
  {/if}

  {#if !job}
    <div class="empty muted">{t('selectHint')}</div>
  {:else if job.status === 'queued' || job.status === 'running'}
    <div class="empty waiting" data-testid="compare-waiting">
      <ProgressRing value={job.status === 'running' ? job.progress : null} size={64} label={tk('status_' + job.status)} />
      <b>{job.name}</b>
      <span class="muted">
        {job.status === 'running'
          ? `${tk('status_running')} · ${tk('stage_' + (job.stage || 'start'))}`
          : job.position
            ? tf('waitingPos', { n: job.position })
            : t('waitingHere')}
      </span>
    </div>
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
            class:editing={editing && which === 'svg'}
            onpointerdown={down}
            onpointermove={move}
            onpointerup={(e) => {
              up();
              if (which === 'svg') void pick(e);
            }}
            onpointercancel={up}
            onkeydown={key}
          >
            {#if which === 'source' && media?.sourceUrl}
              <img src={media.sourceUrl} alt="" style={imgStyle} draggable="false" />
            {:else if which === 'svg' && svgUrl}
              <img src={svgUrl} alt="" style={imgStyle} draggable="false" data-testid="svg-image" />
              {#if selInfo}
                <svg class="overlay" viewBox="0 0 {vb[0]} {vb[1]}" style={imgStyle} aria-hidden="true" data-testid="edit-selection">
                  <path d={selInfo.d} class="sel-halo" vector-effect="non-scaling-stroke" />
                  <path d={selInfo.d} class="sel" vector-effect="non-scaling-stroke" />
                </svg>
              {/if}
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
  .viewport.editing {
    cursor: crosshair;
  }
  .overlay {
    position: absolute;
    pointer-events: none;
    overflow: visible;
  }
  .overlay path {
    fill: none;
    stroke-linejoin: round;
  }
  .sel-halo {
    stroke: var(--panel);
    stroke-width: 5px;
  }
  .sel {
    stroke: var(--accent);
    stroke-width: 2.5px;
    stroke-dasharray: 6 4;
    animation: march 0.8s linear infinite;
  }
  @keyframes march {
    to {
      stroke-dashoffset: -10;
    }
  }
  .editbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    border-radius: var(--radius-sm);
    background: var(--panel-2);
    border: 1px solid var(--line);
    animation: fade-in var(--medium) var(--ease);
  }
  .editbar .swatch {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid var(--line-strong);
  }
  .editbar .color {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: calc(13px * var(--ts));
  }
  .editbar input[type='color'] {
    width: 30px;
    height: 26px;
    padding: 0;
    border: 1px solid var(--line-strong);
    border-radius: 6px;
    background: none;
  }
  .editbar .hint {
    font-size: calc(12.5px * var(--ts));
  }
  .editbar .undo {
    margin-left: auto;
    display: inline-flex;
    gap: 2px;
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
    font-size: calc(12px * var(--ts));
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
  .waiting {
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 10px;
    animation: fade-in var(--medium) var(--ease);
  }
  @media (max-width: 700px) {
    .panes {
      grid-template-columns: 1fr;
      grid-template-rows: 1fr 1fr;
    }
  }
</style>
