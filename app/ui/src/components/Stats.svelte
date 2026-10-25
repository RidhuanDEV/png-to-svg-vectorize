<script lang="ts">
  import type { Job } from '../lib/api';
  import { t } from '../lib/i18n.svelte';
  import { saveSettings, store, type Media } from '../lib/store.svelte';
  import { toast } from '../lib/toast.svelte';
  import Button from './ui/Button.svelte';
  import Icon from './ui/Icon.svelte';

  let { job, media }: { job: Job | undefined; media: Media | undefined } = $props();

  const kb = (n: number | null) => (n === null ? '—' : n < 1024 * 1024 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1048576).toFixed(2)} MB`);
  const score = $derived(media?.score);

  /** Lock the colors of this result: they become the palette of the next runs, ready to edit. */
  function usePalette(colors: string[]) {
    store.settings.overrides = { ...store.settings.overrides, palette: [...colors] };
    store.settings.advanced = true;
    saveSettings();
    toast('info', t('t_paletteLocked'));
  }
</script>

{#if job && (job.status === 'done' || job.status === 'error')}
  <section class="panel" aria-labelledby="res-title">
    <h2 id="res-title">{t('result')}</h2>
    {#if job.status === 'done'}
      <div class="score">
        <span class="muted">{t('similarity')}</span>
        <b class="num" data-testid="score">{score !== undefined ? `${score.toFixed(2)} %` : t('measuring')}</b>
        <span class="meter" aria-hidden="true"><span style="width:{score ?? 0}%"></span></span>
      </div>
      <dl class="num-values" data-testid="stats">
        <dt>{t('regions')}</dt>
        <dd>{job.stats.regions ?? '—'}</dd>
        <dt>{t('gradients')}</dt>
        <dd>{job.stats.gradients ?? '—'}</dd>
        <dt>{t('outlines')}</dt>
        <dd>{job.stats.outline_paths ?? '—'}</dd>
        <dt>{t('size')}</dt>
        <dd>{kb(job.bytes)}</dd>
        <dt>{t('time')}</dt>
        <dd>{job.seconds?.toFixed(1)} s</dd>
        {#if job.stats.palette?.length}
          <dt>{t('palette')}</dt>
          <dd class="swatches" data-testid="result-palette">
            {#each job.stats.palette as c (c)}<i style="background:{c}" title={c}></i>{/each}
          </dd>
        {/if}
        {#if job.stats.ai !== undefined}
          <dt>{t('aiUsed')}</dt>
          <dd data-testid="stat-ai">{job.stats.ai ? t('yes') : t('no')}</dd>
        {/if}
      </dl>
      {#if job.stats.warnings?.length}
        <p class="warn" role="note" data-testid="result-warning"><Icon name="warning" size={14} /> {t('notFlatLogo')}</p>
      {/if}
      {#if job.stats.palette?.length}
        <Button variant="ghost" size="sm" icon="sliders" onclick={() => usePalette(job.stats.palette ?? [])} data-testid="use-palette"
          >{t('paletteUse')}</Button
        >
      {/if}
    {:else}
      <p class="err" role="alert"><Icon name="warning" size={16} /> {t('failedHelp')}</p>
    {/if}
  </section>
{/if}

<style>
  .score {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 4px 8px;
    align-items: baseline;
    margin-bottom: 10px;
  }
  .score b {
    font-size: calc(20px * var(--ts));
    font-variant-numeric: tabular-nums;
  }
  .meter {
    grid-column: 1 / -1;
    height: 6px;
    border-radius: 999px;
    background: var(--panel-3);
    overflow: hidden;
  }
  .meter span {
    display: block;
    height: 100%;
    background: linear-gradient(90deg, var(--accent), var(--ok));
    transition: width 700ms var(--ease);
  }
  dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 4px 12px;
    margin: 0;
    font-size: calc(13px * var(--ts));
  }
  dt {
    color: var(--muted);
  }
  dd {
    margin: 0;
    text-align: right;
    font-family: var(--mono);
    font-variant-numeric: tabular-nums;
  }
  .swatches {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 3px;
  }
  .swatches i {
    width: 14px;
    height: 14px;
    border-radius: 4px;
    border: 1px solid var(--line-strong);
  }
  .warn {
    display: flex;
    gap: 6px;
    margin: 8px 0 0;
    font-size: calc(12.5px * var(--ts));
    color: var(--warn);
  }
  .err {
    display: flex;
    gap: 8px;
    margin: 0;
    color: var(--danger);
  }
</style>
