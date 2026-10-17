<script lang="ts">
  import type { Job } from '../lib/api';
  import { t } from '../lib/i18n.svelte';
  import type { Media } from '../lib/store.svelte';
  import Icon from './ui/Icon.svelte';

  let { job, media }: { job: Job | undefined; media: Media | undefined } = $props();

  const kb = (n: number | null) => (n === null ? '—' : n < 1024 * 1024 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1048576).toFixed(2)} MB`);
  const score = $derived(media?.score);
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
      </dl>
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
  .err {
    display: flex;
    gap: 8px;
    margin: 0;
    color: var(--danger);
  }
</style>
