<script lang="ts">
  // Left column: add photos, the workbench, what is being processed (the queue) and the finished results.
  import type { Job } from '../lib/api';
  import { t, tf, tk } from '../lib/i18n.svelte';
  import { pickFiles } from '../lib/picker';
  import { cancelJob, ensureThumb, finished, inQueue, removeJob, retryJob, staged, stopAll, store } from '../lib/store.svelte';
  import Button from './ui/Button.svelte';
  import Dialog from './ui/Dialog.svelte';
  import Icon from './ui/Icon.svelte';
  import ProgressRing from './ui/ProgressRing.svelte';

  const bench = $derived(staged());
  const queue = $derived(inQueue());
  const results = $derived(finished());
  let confirmStop = $state(false);

  $effect(() => {
    for (const j of [...queue, ...results]) if (j.status !== 'done') void ensureThumb(j);
  });

  function select(job: Job) {
    store.selected = job.id;
    store.focus = 'result';
  }

  function line(job: Job): string {
    if (job.status === 'queued') return job.position ? tf('waitingPos', { n: job.position }) : tk('status_queued');
    if (job.status === 'running') return `${tk('status_running')} · ${tk('stage_' + (job.stage || 'start'))}`;
    return tk('status_' + job.status);
  }
</script>

<div class="side">
  <span data-tour={bench.length || queue.length || results.length ? 'add' : undefined}>
    <Button variant="primary" icon="upload" wide onclick={pickFiles} data-testid="add-more">{t('addButton')}</Button>
  </span>

  {#if bench.length}
    <button
      class="bench-link"
      class:on={store.focus === 'bench'}
      onclick={() => (store.focus = 'bench')}
      data-testid="open-workbench"
    >
      <span class="badge">{bench.length}</span>
      <span class="grow">
        <b>{t('workbench')}</b>
        <span class="muted small">{tf('selectedCount', { n: bench.filter((j) => store.picked[j.id]).length, m: bench.length })}</span>
      </span>
      <Icon name="chevronRight" size={16} />
    </button>
  {/if}

  {#if queue.length}
    <section class="panel group" aria-labelledby="q-title">
      <div class="head">
        <h2 id="q-title" class="section-title">{t('queueTitle')} · {queue.length}</h2>
        <Button variant="ghost" size="sm" icon="stop" onclick={() => (confirmStop = true)} data-testid="stop-all">{t('stopAll')}</Button>
      </div>
      <ul>
        {#each queue as job (job.id)}
          {@const src = store.media[job.id]?.sourceUrl}
          <li data-testid="job" data-status={job.status} class:selected={store.selected === job.id}>
            <button class="pick" onclick={() => select(job)} aria-current={store.selected === job.id}>
              <span class="thumb">
                {#if src}<img src={src} alt="" />{/if}
                <span class="ring"><ProgressRing value={job.status === 'running' ? job.progress : null} size={30} label={line(job)} /></span>
              </span>
              <span class="info">
                <span class="name" title={job.name}>{job.name}</span>
                <span class="status">{line(job)}</span>
              </span>
            </button>
            <Button variant="ghost" size="sm" iconOnly icon="x" title={t('cancel')} onclick={() => cancelJob(job.id)}>{t('cancel')}</Button>
          </li>
        {/each}
      </ul>
    </section>
  {/if}

  {#if results.length}
    <section class="panel group results" aria-labelledby="r-title">
      <h2 id="r-title" class="section-title">{t('resultsTitle')} · {results.length}</h2>
      <ul>
        {#each results as job (job.id)}
          {@const src = store.media[job.id]?.sourceUrl}
          <li
            data-testid="job"
            data-status={job.status}
            class:selected={store.selected === job.id && store.focus === 'result'}
            class:fresh={store.fresh[job.id]}
          >
            <button class="pick" onclick={() => select(job)} aria-current={store.selected === job.id}>
              <span class="thumb">
                {#if src}<img src={src} alt="" />{/if}
                {#if job.status === 'done'}
                  <span class="tick"><Icon name="check" size={12} stroke={3} /></span>
                {/if}
              </span>
              <span class="info">
                <span class="name" title={job.name}>{job.name}</span>
                <span class="status status-{job.status}">{line(job)}</span>
              </span>
            </button>
            <span class="actions">
              <Button variant="ghost" size="sm" iconOnly icon="retry" title={t('retry')} onclick={() => retryJob(job.id)}>{t('retry')}</Button>
              <Button variant="ghost" size="sm" iconOnly icon="trash" title={t('remove')} onclick={() => removeJob(job.id)}>{t('remove')}</Button>
            </span>
          </li>
        {/each}
      </ul>
    </section>
  {/if}
</div>

<Dialog
  open={confirmStop}
  title={t('confirmStopTitle')}
  body={t('confirmStopBody')}
  confirm={t('stopAll')}
  cancel={t('keepGoing')}
  danger
  oncancel={() => (confirmStop = false)}
  onconfirm={() => {
    confirmStop = false;
    void stopAll();
  }}
/>

<style>
  .side {
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-height: 0;
  }
  .bench-link {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    border-radius: var(--radius);
    border: 1px solid var(--line);
    background: var(--panel);
    text-align: left;
    transition:
      border-color var(--fast) var(--ease),
      background var(--fast) var(--ease),
      transform var(--fast) var(--ease);
    animation: pop-in var(--medium) var(--ease);
  }
  .bench-link:hover {
    border-color: var(--line-strong);
    transform: translateY(-1px);
  }
  .bench-link.on {
    border-color: var(--accent);
    background: var(--accent-soft);
  }
  .badge {
    min-width: 28px;
    height: 28px;
    padding: 0 8px;
    border-radius: 999px;
    display: grid;
    place-items: center;
    background: var(--accent);
    color: var(--accent-text);
    font-weight: 700;
    font-size: 13px;
  }
  .grow {
    flex: 1;
    display: flex;
    flex-direction: column;
    line-height: 1.3;
  }
  .small {
    font-size: 12px;
  }
  .group {
    padding: 12px;
    animation: pop-in var(--medium) var(--ease);
  }
  .results {
    min-height: 0;
    overflow: auto;
  }
  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
  }
  .head h2 {
    margin: 0;
  }
  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  li {
    display: flex;
    align-items: center;
    gap: 4px;
    border-radius: 10px;
    padding: 3px;
    border: 1px solid transparent;
    transition:
      background var(--fast) var(--ease),
      border-color var(--fast) var(--ease);
    animation: pop-in var(--medium) var(--ease);
  }
  li:hover {
    background: var(--panel-2);
  }
  li.selected {
    background: var(--accent-soft);
    border-color: color-mix(in srgb, var(--accent) 40%, transparent);
  }
  li.fresh {
    animation: celebrate 1.2s var(--ease);
  }
  .pick {
    flex: 1;
    min-width: 0;
    display: flex;
    gap: 10px;
    align-items: center;
    border: 0;
    background: transparent;
    padding: 2px;
    text-align: left;
    border-radius: 8px;
  }
  .thumb {
    position: relative;
    width: 44px;
    height: 44px;
    border-radius: 8px;
    background: var(--panel-2);
    flex: none;
    overflow: hidden;
  }
  .thumb img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .ring {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    background: color-mix(in srgb, var(--panel) 55%, transparent);
  }
  .tick {
    position: absolute;
    right: 2px;
    bottom: 2px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    background: var(--ok);
    color: var(--panel);
    animation: pop-in var(--slow) var(--spring);
  }
  .info {
    display: flex;
    flex-direction: column;
    min-width: 0;
    flex: 1;
    line-height: 1.35;
  }
  .name {
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-weight: 600;
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
  .actions {
    display: flex;
    opacity: 0.55;
    transition: opacity var(--fast) var(--ease);
  }
  li:hover .actions,
  li:focus-within .actions {
    opacity: 1;
  }
  @keyframes celebrate {
    0% {
      background: var(--ok-soft);
      transform: scale(1);
    }
    30% {
      transform: scale(1.02);
    }
    100% {
      background: transparent;
    }
  }
</style>
