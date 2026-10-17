<script lang="ts">
  import { onMount } from 'svelte';
  import { hasToken } from './lib/api';
  import { i18n, languages, setLang, t, type Lang } from './lib/i18n.svelte';
  import { registerFileInput } from './lib/picker';
  import { setCloseMessage } from './lib/platform';
  import { addFiles, finished, inQueue, init, selectedJob, staged, store } from './lib/store.svelte';
  import { startTour, tourSeen } from './lib/tour.svelte';
  import DropZone from './components/DropZone.svelte';
  import Workbench from './components/Workbench.svelte';
  import Queue from './components/Queue.svelte';
  import Compare from './components/Compare.svelte';
  import Settings from './components/Settings.svelte';
  import Stats from './components/Stats.svelte';
  import Export from './components/Export.svelte';
  import Tour from './components/Tour.svelte';
  import Preferences from './components/Preferences.svelte';
  import Button from './components/ui/Button.svelte';
  import Icon from './components/ui/Icon.svelte';
  import Select from './components/ui/Select.svelte';
  import Toasts from './components/ui/Toasts.svelte';

  const authed = hasToken();
  let dragging = $state(false);
  let depth = 0;
  let input: HTMLInputElement;
  let settingsOpen = $state(false);

  onMount(() => {
    document.documentElement.lang = i18n.lang;
    setCloseMessage(t('closeConfirm'));
    registerFileInput(() => input.click());
    if (!authed) return;
    void init().then(() => {
      if (!tourSeen()) startTour();
    });
  });

  const job = $derived(selectedJob());
  const media = $derived(job ? store.media[job.id] : undefined);
  const bench = $derived(staged());
  const queue = $derived(inQueue());
  const results = $derived(finished());
  const empty = $derived(!bench.length && !queue.length && !results.length);
  const showBench = $derived(bench.length > 0 && (store.focus === 'bench' || (!queue.length && !results.length)));

  // where the user is in the flow: 0 add, 1 choose, 2 process, 3 save
  const step = $derived(empty ? 0 : showBench ? 1 : queue.length ? 2 : 3);
  const steps = $derived([t('step_add'), t('step_pick'), t('step_queue'), t('step_save')]);

  function changeLang(l: Lang) {
    setLang(l);
    setCloseMessage(t('closeConfirm'));
  }

  function isFileDrag(e: DragEvent): boolean {
    return authed && !!e.dataTransfer && Array.from(e.dataTransfer.types).includes('Files');
  }
</script>

<svelte:window
  onkeydown={(e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === ',') {
      e.preventDefault();
      settingsOpen = true;
    }
  }}
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
    if (e.dataTransfer?.files.length) void addFiles(Array.from(e.dataTransfer.files));
  }}
/>

<input
  bind:this={input}
  class="sr-only"
  type="file"
  multiple
  tabindex="-1"
  aria-hidden="true"
  accept="image/png,image/webp,image/jpeg"
  data-testid="file-input"
  onchange={(e) => {
    const files = (e.currentTarget as HTMLInputElement).files;
    if (files?.length) void addFiles(Array.from(files));
    (e.currentTarget as HTMLInputElement).value = '';
  }}
/>

<div class="shell">
  <header>
    <div class="brand">
      <!-- brand mark: a vector curve with its pen nodes, in the theme's colors -->
      <svg class="mark" viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">
        <rect x="1" y="1" width="30" height="30" rx="8" class="mark-bg" />
        <path d="M7 23 C 11 9, 21 9, 25 17" class="mark-curve" />
        <path d="M7 23 L 11 12 M25 17 L 23 10" class="mark-handle" />
        <circle cx="7" cy="23" r="2.6" class="mark-node" />
        <circle cx="25" cy="17" r="2.6" class="mark-node" />
      </svg>
      <div class="title">
        <h1>{t('appName')}</h1>
        <span class="muted"><Icon name="lock" size={12} /> {t('privacy')}</span>
      </div>
    </div>

    {#if authed}
      <ol class="steps" aria-label="{t('step_add')} → {t('step_save')}">
        {#each steps as label, i (i)}
          <li class:done={i < step} class:now={i === step} aria-current={i === step ? 'step' : undefined}>
            <span class="num">{#if i < step}<Icon name="check" size={13} stroke={3} />{:else}{i + 1}{/if}</span>
            <span class="lbl">{label}</span>
          </li>
        {/each}
      </ol>
    {/if}

    <div class="right">
      {#if authed}
        <Button variant="ghost" size="sm" icon="help" onclick={startTour} data-testid="tour-open">{t('help')}</Button>
        <Button
          variant="ghost"
          size="sm"
          iconOnly
          icon="settings"
          title={t('settingsOpen')}
          onclick={() => (settingsOpen = true)}
          data-testid="settings-open">{t('settings')}</Button
        >
      {/if}
      <Select
        label={t('language')}
        icon="globe"
        value={i18n.lang}
        options={languages}
        onchange={changeLang}
        testid="lang"
      />
    </div>
  </header>

  {#if !authed}
    <p class="panel warn" role="alert">{t('noToken')}</p>
  {:else}
    <main class:empty>
      {#if !empty}
        <aside class="left">
          <Queue />
        </aside>
      {/if}
      <section class="center">
        {#if empty}
          <DropZone />
        {:else if showBench}
          <Workbench />
        {:else}
          <Compare {job} {media} />
        {/if}
      </section>
      <aside class="right-col">
        <!-- results view: saving comes first; the style stays below for "process again" -->
        {#if !showBench}
          <Export {job} {media} />
          <Stats {job} {media} />
        {/if}
        <Settings />
      </aside>
    </main>
  {/if}

  {#if dragging}
    <div class="drop-overlay" aria-hidden="true">
      <div class="drop-card">
        <Icon name="upload" size={40} />
        <span>{t('drop')}</span>
      </div>
    </div>
  {/if}
  <Toasts />
  <Tour />
  {#if authed}<Preferences bind:open={settingsOpen} />{/if}
</div>

<style>
  .shell {
    height: 100%;
    display: flex;
    flex-direction: column;
  }
  header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 8px 16px;
    padding: calc(10px * var(--d)) 16px;
    border-bottom: 1px solid var(--line);
    background: var(--panel);
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }
  .mark {
    flex: none;
  }
  .mark-bg {
    fill: var(--accent);
  }
  .mark-curve {
    fill: none;
    stroke: var(--accent-text);
    stroke-width: 2.4;
    stroke-linecap: round;
  }
  .mark-handle {
    fill: none;
    stroke: var(--accent-text);
    stroke-width: 1;
    opacity: 0.55;
  }
  .mark-node {
    fill: var(--accent);
    stroke: var(--node);
    stroke-width: 1.8;
  }
  :root[data-theme='paper'] .mark-node {
    fill: var(--accent-text);
  }
  .title {
    display: flex;
    flex-direction: column;
    line-height: 1.25;
    min-width: 0;
  }
  h1 {
    margin: 0;
    font-size: calc(15px * var(--ts));
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .title span {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: calc(12px * var(--ts));
    white-space: nowrap;
  }
  .steps {
    flex: 1;
    display: flex;
    justify-content: center;
    gap: 6px;
    list-style: none;
    margin: 0;
    padding: 0;
    min-width: 0;
  }
  .steps li {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px 4px 4px;
    border-radius: 999px;
    color: var(--muted);
    font-size: calc(13px * var(--ts));
    font-weight: 600;
    white-space: nowrap;
    transition:
      background var(--medium) var(--ease),
      color var(--medium) var(--ease);
  }
  .steps li + li::before {
    content: '';
    width: 18px;
    height: 2px;
    margin-right: 4px;
    margin-left: -10px;
    background: var(--line);
    border-radius: 2px;
  }
  .num {
    width: 22px;
    height: 22px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    font-size: calc(12px * var(--ts));
    background: var(--panel-2);
    border: 1px solid var(--line);
    transition:
      background var(--medium) var(--ease),
      color var(--medium) var(--ease);
  }
  .steps li.now {
    background: var(--accent-soft);
    color: var(--text);
  }
  .steps li.now .num {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--accent-text);
  }
  .steps li.done .num {
    background: var(--ok);
    border-color: var(--ok);
    color: var(--panel);
  }
  .right {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-left: auto;
  }
  main {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: 290px minmax(0, 1fr) 300px;
    gap: calc(14px * var(--d));
    padding: calc(14px * var(--d));
  }
  main.empty {
    grid-template-columns: minmax(0, 1fr) 300px;
  }
  .left,
  .right-col {
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
    z-index: 70;
    display: grid;
    place-items: center;
    background: color-mix(in srgb, var(--accent) 14%, transparent);
    backdrop-filter: blur(2px);
    pointer-events: none;
    animation: fade-in var(--fast) var(--ease);
  }
  .drop-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 10px;
    padding: 32px 40px;
    border-radius: var(--radius-lg);
    border: 3px dashed var(--accent);
    background: var(--panel);
    color: var(--accent);
    font-size: calc(18px * var(--ts));
    font-weight: 700;
    box-shadow: var(--shadow-lg);
    animation: pulse 1.2s ease-in-out infinite;
  }
  @keyframes pulse {
    50% {
      transform: scale(1.03);
    }
  }
  @media (max-width: 1180px) {
    .steps .lbl {
      display: none;
    }
    .steps li {
      padding: 4px;
    }
  }
  @media (max-width: 900px) {
    .steps {
      order: 3;
      flex-basis: 100%;
      justify-content: flex-start;
      overflow-x: auto;
    }
    .steps .lbl {
      display: inline;
    }
    .steps li {
      padding: 4px 10px 4px 4px;
    }
  }
  @media (max-width: 700px) {
    .title span {
      display: none;
    }
    .steps .lbl {
      display: none;
    }
  }
  @media (max-width: 1000px) {
    main,
    main.empty {
      grid-template-columns: 1fr;
      overflow: auto;
    }
    .center {
      min-height: 60vh;
    }
  }
</style>
