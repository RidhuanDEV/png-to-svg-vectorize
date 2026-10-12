<script lang="ts">
  import { t, tk } from '../lib/i18n.svelte';
  import { cancelJob, removeJob, retryJob, store } from '../lib/store.svelte';
</script>

<div class="panel queue">
  <h2>{t('queue')}</h2>
  {#if store.jobs.length === 0}
    <p class="muted">{t('emptyQueue')}</p>
  {/if}
  <ul>
    {#each store.jobs as job (job.id)}
      {@const m = store.media[job.id]}
      <li class:selected={store.selected === job.id} data-testid="job" data-status={job.status}>
        <button class="pick" onclick={() => (store.selected = job.id)} aria-pressed={store.selected === job.id}>
          {#if m?.sourceUrl}
            <img src={m.sourceUrl} alt="" />
          {:else}
            <span class="thumb"></span>
          {/if}
          <span class="info">
            <span class="name" title={job.name}>{job.name}</span>
            <span class="status status-{job.status}">
              {tk('status_' + job.status)}{#if job.status === 'running' && job.stage}&nbsp;· {tk('stage_' + job.stage)}{/if}
            </span>
            {#if job.status === 'queued' || job.status === 'running'}
              <progress max="1" value={job.progress}></progress>
            {/if}
          </span>
        </button>
        <span class="actions">
          {#if job.status === 'queued' || job.status === 'running'}
            <button onclick={() => cancelJob(job.id)} title={t('cancel')} aria-label={t('cancel')}>■</button>
          {:else}
            <button onclick={() => retryJob(job.id)} title={t('retry')} aria-label={t('retry')}>↻</button>
          {/if}
          <button onclick={() => removeJob(job.id)} title={t('remove')} aria-label={t('remove')}>✕</button>
        </span>
      </li>
    {/each}
  </ul>
</div>

<style>
  .queue {
    min-height: 0;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  li {
    display: flex;
    align-items: center;
    gap: 6px;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 4px;
  }
  li.selected {
    border-color: var(--accent);
    background: var(--panel-2);
  }
  .pick {
    flex: 1;
    min-width: 0;
    display: flex;
    gap: 8px;
    align-items: center;
    border: 0;
    background: transparent;
    padding: 2px;
    text-align: left;
  }
  img,
  .thumb {
    width: 40px;
    height: 40px;
    object-fit: cover;
    border-radius: 6px;
    background: var(--panel-2);
    flex: none;
  }
  .info {
    display: flex;
    flex-direction: column;
    min-width: 0;
    flex: 1;
  }
  .name {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .status {
    font-size: 12px;
    color: var(--muted);
  }
  .status-done {
    color: var(--ok);
  }
  .status-error {
    color: var(--danger);
  }
  progress {
    width: 100%;
    height: 4px;
    accent-color: var(--accent);
  }
  .actions {
    display: flex;
    gap: 4px;
  }
  .actions button {
    padding: 2px 7px;
    font-size: 12px;
  }
</style>
