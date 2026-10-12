<script lang="ts">
  import type { Job } from '../lib/api';
  import { t } from '../lib/i18n.svelte';
  import type { Media } from '../lib/store.svelte';

  let { job, media }: { job: Job | undefined; media: Media | undefined } = $props();

  const kb = (n: number | null) => (n === null ? '—' : n < 1024 * 1024 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1048576).toFixed(2)} MB`);
</script>

<div class="panel">
  <h2>{t('result')}</h2>
  {#if job && job.status === 'done'}
    <dl data-testid="stats">
      <dt>{t('similarity')}</dt>
      <dd data-testid="score">{media?.score !== undefined ? `${media.score.toFixed(2)} %` : t('measuring')}</dd>
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
  {:else if job?.status === 'error'}
    <p class="err" role="alert">{job.error}</p>
  {:else}
    <p class="muted">—</p>
  {/if}
</div>

<style>
  dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 4px 12px;
    margin: 0;
  }
  dt {
    color: var(--muted);
  }
  dd {
    margin: 0;
    text-align: right;
    font-variant-numeric: tabular-nums;
  }
  .err {
    color: var(--danger);
    word-break: break-word;
  }
</style>
