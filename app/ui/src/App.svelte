<script lang="ts">
  import { onMount } from 'svelte';
  import { hasToken } from './lib/api';
  import { i18n, setLang, t, type Lang } from './lib/i18n.svelte';
  import { addFiles, init, selectedJob, store } from './lib/store.svelte';
  import DropZone from './components/DropZone.svelte';
  import Queue from './components/Queue.svelte';
  import Compare from './components/Compare.svelte';
  import Settings from './components/Settings.svelte';
  import Stats from './components/Stats.svelte';
  import Export from './components/Export.svelte';

  const authed = hasToken();
  let dragging = $state(false);
  let depth = 0;

  onMount(() => {
    document.documentElement.lang = i18n.lang;
    if (authed) void init();
  });

  const job = $derived(selectedJob());
  const media = $derived(job ? store.media[job.id] : undefined);

  function isFileDrag(e: DragEvent): boolean {
    return authed && !!e.dataTransfer && Array.from(e.dataTransfer.types).includes('Files');
  }
</script>

<svelte:window
  ondragenter={(e) => {
    if (!isFileDrag(e)) return;
    depth++;
    dragging = true;
  }}
  ondragleave={() => {
    depth = Math.max(0, depth - 1);
    if (depth === 0) dragging = false;
  }}
  ondragover={(e) => {
    if (isFileDrag(e)) e.preventDefault();
  }}
  ondrop={(e) => {
    if (!isFileDrag(e)) return;
    e.preventDefault();
    depth = 0;
    dragging = false;
    if (e.dataTransfer?.files.length) void addFiles(e.dataTransfer.files);
  }}
/>

<div class="shell">
  <header>
    <img src="./favicon.svg" alt="" width="28" height="28" />
    <div class="title">
      <h1>{t('appName')}</h1>
      <span class="muted">{t('privacy')}</span>
    </div>
    <label class="lang">
      <span class="sr-only">{t('language')}</span>
      <select
        value={i18n.lang}
        onchange={(e) => setLang((e.currentTarget as HTMLSelectElement).value as Lang)}
        aria-label={t('language')}
      >
        <option value="en">English</option>
        <option value="id">Bahasa Indonesia</option>
      </select>
    </label>
  </header>

  {#if !authed}
    <p class="panel warn" role="alert">{t('noToken')}</p>
  {:else}
    <main>
      <aside class="left">
        <DropZone />
        <Queue />
      </aside>
      <section class="center">
        <Compare {job} {media} />
      </section>
      <aside class="right">
        <Settings />
        <Stats {job} {media} />
        <Export {job} {media} />
      </aside>
    </main>
  {/if}

  {#if dragging}
    <div class="drop-overlay" aria-hidden="true"><span>{t('drop')}</span></div>
  {/if}
  {#if store.notice}
    <div class="toast" role="status" data-testid="notice">{t('rejected')} — {store.notice}</div>
  {/if}
</div>

<style>
  .shell {
    height: 100%;
    display: flex;
    flex-direction: column;
  }
  header {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 16px;
    border-bottom: 1px solid var(--line);
    background: var(--panel);
  }
  .title {
    display: flex;
    flex-direction: column;
    line-height: 1.2;
  }
  h1 {
    margin: 0;
    font-size: 16px;
  }
  .title span {
    font-size: 12px;
  }
  .lang {
    margin-left: auto;
  }
  main {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: 280px minmax(0, 1fr) 300px;
    gap: 12px;
    padding: 12px;
  }
  .left,
  .right {
    display: flex;
    flex-direction: column;
    gap: 12px;
    min-height: 0;
    overflow: auto;
  }
  .center {
    min-height: 0;
    min-width: 0;
  }
  .warn {
    margin: 24px;
  }
  .drop-overlay {
    position: fixed;
    inset: 0;
    display: grid;
    place-items: center;
    background: color-mix(in srgb, var(--accent) 18%, transparent);
    border: 3px dashed var(--accent);
    pointer-events: none;
    font-size: 20px;
    font-weight: 600;
  }
  .toast {
    position: fixed;
    bottom: 16px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--text);
    color: var(--bg);
    padding: 8px 14px;
    border-radius: 8px;
    max-width: min(90vw, 640px);
  }
  @media (max-width: 1000px) {
    main {
      grid-template-columns: 1fr;
      overflow: auto;
    }
    .center {
      min-height: 60vh;
    }
  }
</style>
