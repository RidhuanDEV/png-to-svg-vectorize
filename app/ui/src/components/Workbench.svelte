<script lang="ts">
  // Step 2: the photos waiting on the workbench. The user ticks which ones to process, then presses Process.
  import { t, tf, tk } from '../lib/i18n.svelte';
  import { pickFiles } from '../lib/picker';
  import { ensureThumb, pickAll, pickedIds, processPicked, removeJob, staged, store } from '../lib/store.svelte';
  import Button from './ui/Button.svelte';
  import Checkbox from './ui/Checkbox.svelte';
  import Icon from './ui/Icon.svelte';

  const items = $derived(staged());
  const chosen = $derived(pickedIds().length);
  const presetName = $derived(tk('preset_' + store.settings.preset));
  const mb = (n: number) => (n < 1024 * 1024 ? `${Math.max(1, Math.round(n / 1024))} KB` : `${(n / 1048576).toFixed(1)} MB`);

  $effect(() => {
    for (const j of items) void ensureThumb(j);
  });
</script>

<section class="bench panel" aria-labelledby="bench-title" data-testid="workbench">
  <header>
    <div>
      <h2 id="bench-title">{t('pickTitle')}</h2>
      <p class="muted">{t('pickHint')}</p>
    </div>
    <div class="tools">
      <Button variant="ghost" size="sm" onclick={() => pickAll(true)} data-testid="pick-all">{t('selectAll')}</Button>
      <Button variant="ghost" size="sm" onclick={() => pickAll(false)} data-testid="pick-none">{t('selectNone')}</Button>
      <Button variant="secondary" size="sm" icon="plus" onclick={pickFiles}>{t('addMore')}</Button>
    </div>
  </header>

  <ul class="grid">
    {#each items as job, i (job.id)}
      {@const src = store.media[job.id]?.sourceUrl}
      <li
        class="item"
        class:on={store.picked[job.id]}
        style="animation-delay:{Math.min(i, 12) * 30}ms"
        data-testid="staged"
        data-name={job.name}
      >
        <button
          class="thumb"
          tabindex="-1"
          aria-hidden="true"
          onclick={() => (store.picked[job.id] = !store.picked[job.id])}
        >
          {#if src}<img src={src} alt="" />{:else}<span class="ph"><Icon name="image" size={28} /></span>{/if}
        </button>
        <div class="check">
          <Checkbox
            label={job.name}
            hideLabel
            checked={!!store.picked[job.id]}
            onchange={(v) => (store.picked[job.id] = v)}
            testid="pick-{job.name}"
          />
        </div>
        <button class="remove" aria-label="{t('removeFromBench')}: {job.name}" title={t('removeFromBench')} onclick={() => removeJob(job.id)}>
          <Icon name="x" size={14} stroke={2.4} />
        </button>
        <div class="meta">
          <span class="name" title={job.name}>{job.name}</span>
          <span class="muted small">{job.width}×{job.height} · {mb(job.source_bytes)}</span>
        </div>
      </li>
    {/each}
  </ul>

  <footer>
    <span class="count" data-testid="picked-count">{tf('selectedCount', { n: chosen, m: items.length })}</span>
    <span class="style muted">{t('style')}: <b>{presetName}</b></span>
    <Button
      variant="primary"
      size="lg"
      icon="play"
      disabled={chosen === 0}
      loading={store.busy}
      onclick={processPicked}
      data-testid="process"
    >
      {chosen === 0 ? t('processNone') : chosen === 1 ? t('processOne') : tf('processMany', { n: chosen })}
    </Button>
  </footer>
</section>

<style>
  .bench {
    height: 100%;
    display: flex;
    flex-direction: column;
    padding: 0;
    overflow: hidden;
    animation: fade-in var(--medium) var(--ease);
  }
  header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
    padding: 16px 16px 8px;
    flex-wrap: wrap;
  }
  h2 {
    margin: 0;
    font-size: 18px;
  }
  header p {
    margin: 2px 0 0;
  }
  .tools {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
  .grid {
    flex: 1;
    min-height: 0;
    overflow: auto;
    list-style: none;
    margin: 0;
    padding: 8px 16px 16px;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    align-content: start;
    gap: 12px;
  }
  .item {
    position: relative;
    border-radius: var(--radius);
    border: 2px solid var(--line);
    background: var(--panel);
    overflow: hidden;
    animation: pop-in var(--slow) var(--ease) both;
    transition:
      border-color var(--fast) var(--ease),
      box-shadow var(--fast) var(--ease),
      transform var(--fast) var(--ease),
      opacity var(--fast) var(--ease);
  }
  .item:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow);
  }
  .item:not(.on) {
    opacity: 0.6;
  }
  .item.on {
    border-color: var(--accent);
  }
  .thumb {
    display: block;
    width: 100%;
    aspect-ratio: 4 / 3;
    padding: 0;
    border: 0;
    background: repeating-conic-gradient(var(--checker-a) 0 25%, var(--checker-b) 0 50%) 50% / 16px 16px;
  }
  .thumb img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
  }
  .ph {
    display: grid;
    place-items: center;
    height: 100%;
    color: var(--muted);
  }
  .check {
    position: absolute;
    top: 8px;
    left: 8px;
    padding: 2px;
    border-radius: 9px;
    background: color-mix(in srgb, var(--panel) 80%, transparent);
  }
  .remove {
    position: absolute;
    top: 8px;
    right: 8px;
    width: 28px;
    height: 28px;
    display: grid;
    place-items: center;
    border-radius: 50%;
    border: 0;
    background: color-mix(in srgb, var(--panel) 85%, transparent);
    color: var(--muted);
    opacity: 0;
    transition:
      opacity var(--fast) var(--ease),
      background var(--fast) var(--ease),
      color var(--fast) var(--ease);
  }
  .item:hover .remove,
  .remove:focus-visible {
    opacity: 1;
  }
  .remove:hover {
    background: var(--danger);
    color: var(--panel);
  }
  .meta {
    display: flex;
    flex-direction: column;
    padding: 8px 10px 10px;
    min-width: 0;
  }
  .name {
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .small {
    font-size: 12px;
  }
  footer {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 12px 16px;
    border-top: 1px solid var(--line);
    background: var(--panel-2);
    flex-wrap: wrap;
  }
  .count {
    font-weight: 650;
  }
  .style {
    flex: 1;
  }
</style>
