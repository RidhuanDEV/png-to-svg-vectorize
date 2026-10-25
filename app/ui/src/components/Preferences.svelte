<script lang="ts">
  // Settings (Ctrl+,): appearance, processing limits, how results are saved, privacy, about. Changes apply at once.
  import { onMount } from 'svelte';
  import { api, type UpdateInfo } from '../lib/api';
  import { i18n, languages, setLang, t, tf, tk, type Key } from '../lib/i18n.svelte';
  import { desktop, openExternal, setCloseMessage, type DesktopPrefs } from '../lib/platform';
  import { MAX_SIDES, MAX_STAGED, prefs, previewName, savePrefs, TEXT_SCALES, THEMES, type ThemeChoice } from '../lib/prefs.svelte';
  import { aiModelAction, refreshAi, saveSettings, setSpeed, store, updateService } from '../lib/store.svelte';
  import { chooseWatchFolder, refreshWatch, startWatch, stopWatch, watch } from '../lib/watch.svelte';
  import type { WatchFormat } from '../lib/platform';
  import { startTour } from '../lib/tour.svelte';
  import themes from '../theme/themes.json';
  import Button from './ui/Button.svelte';
  import Icon, { type IconName } from './ui/Icon.svelte';
  import Segmented from './ui/Segmented.svelte';
  import Select from './ui/Select.svelte';
  import Switch from './ui/Switch.svelte';

  let { open = $bindable(false) }: { open?: boolean } = $props();

  type Section = 'appearance' | 'processing' | 'output' | 'automation' | 'privacy' | 'about';
  const sections: { id: Section; icon: IconName }[] = [
    { id: 'appearance', icon: 'sparkles' },
    { id: 'processing', icon: 'gauge' },
    { id: 'output', icon: 'download' },
    { id: 'automation', icon: 'folder' },
    { id: 'privacy', icon: 'lock' },
    { id: 'about', icon: 'info' },
  ];
  let section = $state<Section>('appearance');
  let card: HTMLDivElement | undefined = $state();
  let previous: HTMLElement | null = null;
  let pattern = $state(prefs.namePattern);
  let patternError = $state(false);
  let version = $state('');
  let update = $state<{ state: 'idle' | 'busy' | 'done' | 'failed'; info?: UpdateInfo }>({ state: 'idle' });
  let dprefs = $state<DesktopPrefs | null>(null);
  let watchFormat = $state<WatchFormat>('svg');
  const isDesktop = $derived(!!desktop());

  onMount(async () => {
    try {
      version = (await api.health()).version;
    } catch {
      /* shown as empty */
    }
  });

  $effect(() => {
    if (!open || !card) return;
    previous = document.activeElement as HTMLElement | null;
    card.querySelector<HTMLElement>('[role="tab"][aria-selected="true"]')?.focus();
    pattern = prefs.namePattern;
    const d = desktop();
    if (d) void d.get_prefs().then((p) => (dprefs = p));
    void refreshAi();
    void refreshWatch();
    return () => previous?.focus?.();
  });

  function close() {
    open = false;
  }

  function key(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault();
      close();
      return;
    }
    if (e.key !== 'Tab' || !card) return;
    const items = Array.from(card.querySelectorAll<HTMLElement>('button:not(:disabled), input, [tabindex="0"]')).filter(
      (el) => el.offsetParent !== null,
    );
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }

  function navKey(e: KeyboardEvent) {
    const i = sections.findIndex((s) => s.id === section);
    const d = e.key === 'ArrowDown' ? 1 : e.key === 'ArrowUp' ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    section = sections[(i + d + sections.length) % sections.length].id;
    card?.querySelector<HTMLElement>(`[data-testid="nav-${section}"]`)?.focus();
  }

  function set<K extends keyof typeof prefs>(k: K, v: (typeof prefs)[K]) {
    prefs[k] = v;
    savePrefs();
  }

  function changeLang(l: string) {
    setLang(l);
    setCloseMessage(t('closeConfirm'));
  }

  function commitPattern() {
    const p = pattern.trim();
    patternError = !p || p.length > 80;
    if (patternError || p === prefs.namePattern) return;
    set('namePattern', p);
    void updateService({ name_pattern: p });
  }

  async function checkUpdates() {
    update = { state: 'busy' };
    try {
      update = { state: 'done', info: await api.checkUpdate() };
    } catch {
      update = { state: 'failed' };
    }
  }

  async function desk(fn: (d: NonNullable<ReturnType<typeof desktop>>) => Promise<DesktopPrefs>) {
    const d = desktop();
    if (d) dprefs = await fn(d);
  }

  const themeChoices: ThemeChoice[] = ['system', ...THEMES];
  const swatch = (name: keyof typeof themes) => {
    const k = themes[name].tokens;
    return [k.bg, k.panel, k.text, k.accent, k.node];
  };
  // execution provider -> the name people know
  const GPU_NAMES: Record<string, string> = {
    DmlExecutionProvider: 'DirectML',
    CoreMLExecutionProvider: 'Core ML',
    CUDAExecutionProvider: 'NVIDIA CUDA',
  };
  const mb = (n: number) => `${(n / 1048576).toFixed(0)} MB`;
  const REPO = 'https://github.com/RidhuanDEV/png-to-svg-vectorize';
  const LICENSES = [
    ['numpy, SciPy', 'BSD-3-Clause'],
    ['Pillow', 'MIT-CMU (HPND)'],
    ['FastAPI, Pydantic', 'MIT'],
    ['Uvicorn, pywebview', 'BSD-3-Clause'],
    ['Svelte', 'MIT'],
    ['IBM Plex Sans / Mono', 'SIL OFL 1.1'],
    ['ONNX Runtime', 'MIT'],
    ['Real-ESRGAN (AI models)', 'BSD-3-Clause'],
  ];
</script>

{#if open}
  <div class="scrim" role="presentation" onpointerdown={(e) => e.target === e.currentTarget && close()}>
    <div
      bind:this={card}
      class="card"
      role="dialog"
      aria-modal="true"
      aria-labelledby="prefs-title"
      tabindex="-1"
      onkeydown={key}
      data-testid="settings-dialog"
    >
      <header>
        <h2 id="prefs-title">{t('settings')}</h2>
        <Button variant="ghost" size="sm" iconOnly icon="x" title={t('close')} onclick={close} data-testid="settings-close">{t('close')}</Button>
      </header>

      <div class="body">
        <div class="nav" role="tablist" aria-orientation="vertical" aria-label={t('settings')} tabindex="-1" onkeydown={navKey}>
          {#each sections as s (s.id)}
            <button
              role="tab"
              id="tab-{s.id}"
              aria-selected={section === s.id}
              aria-controls="panel-{s.id}"
              tabindex={section === s.id ? 0 : -1}
              class:on={section === s.id}
              onclick={() => (section = s.id)}
              data-testid="nav-{s.id}"
            >
              <Icon name={s.icon} size={16} />
              <span>{t(('sec_' + s.id) as Key)}</span>
            </button>
          {/each}
        </div>

        <div class="content" role="tabpanel" id="panel-{section}" aria-labelledby="tab-{section}">
          {#if section === 'appearance'}
            <div class="row">
              <span class="lbl">{t('language')}</span>
              <Select label={t('language')} icon="globe" value={i18n.lang} options={languages} onchange={changeLang} testid="settings-lang" />
            </div>

            <div class="field">
              <span class="lbl">{t('theme')}</span>
              <div class="themes" role="radiogroup" aria-label={t('theme')}>
                {#each themeChoices as th (th)}
                  {@const on = prefs.theme === th}
                  <button
                    type="button"
                    role="radio"
                    aria-checked={on}
                    class="theme"
                    class:on
                    onclick={() => set('theme', th)}
                    data-testid="theme-{th}"
                  >
                    <span class="swatch" aria-hidden="true">
                      {#if th === 'system'}
                        <!-- half Paper & ink (light), half Lightbox (dark) -->
                        <i style="background:{themes.paper.tokens.bg}"><b style="background:{themes.paper.tokens.node}"></b></i>
                        <i style="background:{themes.lightbox.tokens.bg}"><b style="background:{themes.lightbox.tokens.accent}"></b></i>
                      {:else}
                        {#each swatch(th) as c, i (i)}<i style="background:{c}"></i>{/each}
                      {/if}
                    </span>
                    <span class="name">{tk('theme_' + th)}</span>
                    {#if on}<span class="tick"><Icon name="check" size={12} stroke={3} /></span>{/if}
                  </button>
                {/each}
              </div>
              <p class="hint">{t('themeHint')}</p>
            </div>

            <div class="row">
              <span class="lbl">{t('density')}</span>
              <Segmented
                size="sm"
                label={t('density')}
                value={prefs.density}
                options={[
                  { value: 'comfortable', label: t('density_comfortable') },
                  { value: 'compact', label: t('density_compact') },
                ]}
                onchange={(v) => set('density', v)}
                testid="density"
              />
            </div>
            <div class="row">
              <span class="lbl">{t('textSize')}</span>
              <Segmented
                size="sm"
                label={t('textSize')}
                value={String(prefs.textScale)}
                options={TEXT_SCALES.map((s) => ({ value: String(s), label: `${Math.round(s * 100)}%` }))}
                onchange={(v) => set('textScale', Number(v))}
                testid="text-size"
              />
            </div>
            <div class="row">
              <span class="lbl">{t('motion')}</span>
              <Segmented
                size="sm"
                label={t('motion')}
                value={prefs.motion}
                options={[
                  { value: 'system', label: t('motion_system') },
                  { value: 'reduce', label: t('motion_reduce') },
                ]}
                onchange={(v) => set('motion', v)}
                testid="motion"
              />
            </div>
            <Button
              variant="secondary"
              icon="help"
              onclick={() => {
                close();
                startTour();
              }}
              data-testid="replay-tour">{t('replayTour')}</Button
            >
          {:else if section === 'processing'}
            {#if store.service}
              <div class="field">
                <span class="lbl">{t('speed')}</span>
                <Segmented
                  size="sm"
                  label={t('speed')}
                  value={store.service.speed}
                  options={(['auto', 'saver', 'balanced', 'fast'] as const).map((s) => ({ value: s, label: tk('speed_' + s) }))}
                  onchange={(s) => setSpeed(s)}
                  testid="settings-speed"
                />
              </div>
            {/if}
            <div class="field">
              <span class="lbl">{t('maxSide')}</span>
              <Segmented
                size="sm"
                label={t('maxSide')}
                value={String(prefs.maxSide)}
                options={MAX_SIDES.map((n) => ({ value: String(n), label: `${n} px` }))}
                onchange={(v) => {
                  set('maxSide', Number(v));
                  void updateService({ max_side: Number(v) });
                }}
                testid="max-side"
              />
              <p class="hint">{t('maxSideHint')}</p>
            </div>
            <div class="field">
              <span class="lbl">{t('maxStaged')}</span>
              <Segmented
                size="sm"
                label={t('maxStaged')}
                value={String(prefs.maxStaged)}
                options={MAX_STAGED.map((n) => ({ value: String(n), label: String(n) }))}
                onchange={(v) => {
                  set('maxStaged', Number(v));
                  void updateService({ max_staged: Number(v) });
                }}
                testid="max-staged"
              />
              <p class="hint">{t('maxStagedHint')}</p>
            </div>

            {#if store.ai?.runtime}
              {@const ai = store.ai}
              <div class="field" data-testid="ai-section">
                <span class="lbl"><Icon name="sparkles" size={14} /> {t('aiModel')}</span>
                <p class="hint">{t('aiHint')}</p>
                <div class="models" role="radiogroup" aria-label={t('aiModel')}>
                  {#each ai.models as m (m.name)}
                    {@const on = prefs.aiModel === m.name}
                    <div class="model" class:on data-testid="ai-model-{m.name}" data-state={m.state}>
                      <button type="button" role="radio" aria-checked={on} class="pick" onclick={() => set('aiModel', m.name)}>
                        <span class="radio" aria-hidden="true"></span>
                        <span class="txt">
                          <b>{tk('aiModel_' + m.name)}</b>
                          <span class="muted">{tk('aiModelDesc_' + m.name)}</span>
                        </span>
                      </button>
                      <div class="mstate">
                        {#if m.state === 'installed'}
                          <span class="ok"><Icon name="check" size={14} stroke={2.6} /> {t('aiInstalled')}</span>
                          <Button variant="ghost" size="sm" iconOnly icon="trash" title={t('remove')} onclick={() => aiModelAction('remove', m.name)} data-testid="ai-remove-{m.name}">{t('remove')}</Button>
                        {:else if m.state === 'downloading'}
                          <span class="bar" aria-hidden="true"><span style="width:{Math.round(m.progress * 100)}%"></span></span>
                          <span class="num" role="status">{tf('aiDownloading', { p: Math.round(m.progress * 100) })}</span>
                          <Button variant="ghost" size="sm" iconOnly icon="x" title={t('cancel')} onclick={() => aiModelAction('cancel', m.name)} data-testid="ai-cancel-{m.name}">{t('cancel')}</Button>
                        {:else}
                          <Button variant="secondary" size="sm" icon="download" onclick={() => aiModelAction('download', m.name)} data-testid="ai-download-{m.name}">{tf('aiDownload', { size: mb(m.bytes) })}</Button>
                        {/if}
                      </div>
                      {#if m.state === 'error'}
                        <p class="err" role="alert">{m.error === 'checksum' ? t('aiFailedChecksum') : t('aiFailedNetwork')}</p>
                      {/if}
                    </div>
                  {/each}
                </div>
                <p class="hint">{t('aiDownloadNote')}</p>
              </div>
              <div class="field">
                <span class="lbl">{t('aiAccel')}</span>
                <Segmented
                  size="sm"
                  label={t('aiAccel')}
                  value={prefs.aiAccel}
                  options={(['auto', 'gpu', 'cpu'] as const).map((a) => ({ value: a, label: tk('aiAccel_' + a) }))}
                  onchange={(v) => {
                    set('aiAccel', v);
                    void updateService({ ai_accel: v });
                  }}
                  testid="ai-accel"
                />
                <p class="hint" data-testid="ai-gpu">
                  {ai.gpu.length ? tf('aiGpuFound', { name: ai.gpu.map((g) => GPU_NAMES[g] ?? g).join(', ') }) : t('aiGpuNone')}
                </p>
              </div>
            {:else if store.ai}
              <p class="hint" data-testid="ai-unavailable">{t('aiUnavailable')}</p>
            {/if}
          {:else if section === 'output'}
            <div class="row">
              <span class="lbl">{t('defaultStyle')}</span>
              <Select
                label={t('defaultStyle')}
                value={store.settings.preset}
                options={(store.info?.presets ?? []).map((p) => ({ value: p.name, label: tk('preset_' + p.name) }))}
                onchange={(v) => {
                  store.settings.preset = v;
                  store.settings.overrides = {};
                  saveSettings();
                }}
                testid="default-style"
              />
            </div>

            <div class="field">
              <span class="lbl">{t('saveFolder')}</span>
              {#if isDesktop && dprefs}
                <div class="folder">
                  <span class="path num" data-testid="save-dir">{dprefs.save_dir ?? t('saveFolderNone')}</span>
                  <Button variant="secondary" size="sm" icon="image" onclick={() => desk((d) => d.choose_save_dir())}>{t('chooseFolder')}</Button>
                  {#if dprefs.save_dir}
                    <Button variant="ghost" size="sm" iconOnly icon="x" title={t('remove')} onclick={() => desk((d) => d.clear_save_dir())}>{t('remove')}</Button>
                  {/if}
                </div>
                {#if dprefs.save_dir}
                  <Switch checked={dprefs.ask_each_time} label={t('askEachTime')} onchange={(v) => desk((d) => d.set_pref('ask_each_time', v))} testid="ask-each-time" />
                {/if}
              {:else}
                <p class="hint">{t('desktopOnly')}</p>
              {/if}
            </div>

            <div class="field">
              <label class="lbl" for="name-pattern">{t('namePattern')}</label>
              <input
                id="name-pattern"
                class="text"
                class:invalid={patternError}
                bind:value={pattern}
                maxlength="80"
                spellcheck="false"
                aria-invalid={patternError}
                aria-describedby="name-hint"
                onblur={commitPattern}
                onkeydown={(e) => e.key === 'Enter' && commitPattern()}
                data-testid="name-pattern"
              />
              <p class="hint" id="name-hint">{t('namePatternHint')}</p>
              <p class="preview num" data-testid="name-preview">
                {tf('namePreview', { file: previewName(pattern, 'kucing.png', store.settings.preset) })}
              </p>
            </div>

            <div class="field">
              <span class="lbl">{t('decimals')}</span>
              <Segmented
                size="sm"
                label={t('decimals')}
                value={String(prefs.decimals)}
                options={[0, 1, 2, 3].map((n) => ({ value: String(n), label: String(n) }))}
                onchange={(v) => set('decimals', Number(v))}
                testid="decimals"
              />
              <p class="hint">{t('decimalsHint')}</p>
            </div>

            <div class="field">
              <Switch
                checked={prefs.sizeAttrs}
                label={t('sizeAttrs')}
                onchange={(v) => {
                  set('sizeAttrs', v);
                  void updateService({ size_attrs: v });
                }}
                testid="size-attrs"
              />
              <p class="hint">{t('sizeAttrsHint')}</p>
            </div>
          {:else if section === 'automation'}
            <div class="field">
              <span class="lbl">{t('watchFolder')}</span>
              <p class="hint">{t('watchHint')}</p>
              {#if isDesktop && watch.status}
                {@const ws = watch.status}
                {#each [['source', ws.source, 'watchSource'], ['target', ws.target, 'watchTarget']] as const as [which, path, label] (which)}
                  <div class="folder">
                    <span class="wlbl">{t(label)}</span>
                    <span class="path num" data-testid="watch-{which}">{path ?? t('saveFolderNone')}</span>
                    <Button variant="secondary" size="sm" icon="folder" disabled={ws.watching} onclick={() => chooseWatchFolder(which)}
                      data-testid="watch-choose-{which}">{t('chooseFolder')}</Button
                    >
                  </div>
                {/each}
                <div class="row">
                  <span class="lbl">{t('format')}</span>
                  <Segmented
                    size="sm"
                    label={t('format')}
                    value={watchFormat}
                    options={(['svg', 'pdf', 'eps', 'dxf'] as const).map((f) => ({ value: f, label: f.toUpperCase() }))}
                    onchange={(f) => (watchFormat = f)}
                    testid="watch-format"
                  />
                </div>
                <p class="hint">{tf('watchStyle', { style: tk('preset_' + store.settings.preset) })}</p>
                <div class="folder">
                  {#if ws.watching}
                    <Button variant="danger" icon="stop" onclick={stopWatch} data-testid="watch-stop">{t('watchStop')}</Button>
                  {:else}
                    <Button variant="primary" icon="play" disabled={!ws.source || !ws.target} onclick={() => startWatch(watchFormat)}
                      data-testid="watch-start">{t('watchStart')}</Button
                    >
                  {/if}
                </div>
                <p class="status" role="status" data-testid="watch-status">
                  {#if ws.watching}{tf('watchRunning', { n: ws.converted, f: ws.failed, w: ws.waiting })}
                  {:else if ws.converted || ws.failed}{tf('watchStopped', { n: ws.converted, f: ws.failed })}{/if}
                </p>
                {#if watch.error || ws.last_error}<p class="hint err">{watch.error || ws.last_error}</p>{/if}
              {:else}
                <p class="hint">{t('desktopOnly')}</p>
              {/if}
              <p class="hint">{t('watchCli')}</p>
            </div>
          {:else if section === 'privacy'}
            <div class="note">
              <Icon name="lock" size={18} />
              <p>{t('memoryOnly')}</p>
            </div>
            <div class="field">
              {#if isDesktop && dprefs}
                <Switch checked={dprefs.log} label={t('diagLog')} onchange={(v) => desk((d) => d.set_pref('log', v))} testid="diag-log" />
                <p class="hint">{t('diagLogHint')}</p>
                <Button variant="secondary" size="sm" onclick={() => desktop()?.open_log_folder()}>{t('openLogFolder')}</Button>
              {:else}
                <span class="lbl">{t('diagLog')}</span>
                <p class="hint">{t('desktopOnly')}</p>
              {/if}
            </div>
          {:else}
            <div class="about">
              <img src="./favicon.svg" alt="" width="44" height="44" />
              <div>
                <b>{t('appName')}</b>
                <p class="muted">{t('version')} <span class="num" data-testid="version">{version}</span></p>
                <p class="muted">{t('appLicense')}</p>
              </div>
            </div>
            <div class="field">
              <div class="folder">
                <Button variant="secondary" icon="retry" loading={update.state === 'busy'} onclick={checkUpdates} data-testid="check-updates">{t('checkUpdates')}</Button>
                <Button variant="ghost" icon="globe" onclick={() => openExternal(REPO)}>{t('openRepo')}</Button>
              </div>
              <p class="status" role="status" data-testid="update-status">
                {#if update.state === 'failed'}{t('updateFailed')}
                {:else if update.state === 'done' && update.info}
                  {#if update.info.latest === null}{t('updateNoRelease')}
                  {:else if update.info.newer}
                    {tf('updateAvailable', { v: update.info.latest })}
                    {#if update.info.url}
                      <Button variant="ghost" size="sm" icon="download" onclick={() => openExternal(update.info!.url!)}>{t('download')}</Button>
                    {/if}
                  {:else}{t('updateNone')}{/if}
                {/if}
              </p>
              <p class="hint">{t('updateNote')}</p>
            </div>
            <div class="field">
              <span class="lbl">{t('licenses')}</span>
              <dl class="licenses">
                {#each LICENSES as [name, lic] (name)}<dt>{name}</dt><dd>{lic}</dd>{/each}
              </dl>
            </div>
          {/if}
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 85;
    display: grid;
    place-items: center;
    background: var(--scrim);
    padding: 16px;
    animation: fade-in var(--medium) var(--ease);
  }
  .card {
    width: min(760px, 100%);
    height: min(600px, calc(100vh - 32px));
    display: flex;
    flex-direction: column;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    animation: pop-in var(--slow) var(--spring);
    overflow: hidden;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 16px;
    border-bottom: 1px solid var(--line);
  }
  h2 {
    margin: 0;
    font-size: calc(17px * var(--ts));
  }
  .body {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: 200px minmax(0, 1fr);
  }
  .nav {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 10px;
    border-right: 1px solid var(--line);
    background: var(--panel-2);
  }
  .nav button {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 9px 10px;
    border: 0;
    border-radius: var(--radius-sm);
    background: none;
    color: var(--muted);
    font-weight: 600;
    text-align: left;
    transition:
      background var(--fast) var(--ease),
      color var(--fast) var(--ease);
  }
  .nav button:hover {
    color: var(--text);
    background: var(--panel-3);
  }
  .nav button.on {
    color: var(--text);
    background: var(--panel);
    box-shadow: inset 3px 0 0 var(--node);
  }
  .content {
    overflow: auto;
    padding: 18px 20px;
    display: flex;
    flex-direction: column;
    gap: 18px;
    animation: fade-in var(--medium) var(--ease);
  }
  .row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }
  .field {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .lbl {
    font-weight: 600;
  }
  .hint {
    margin: 0;
    font-size: calc(12.5px * var(--ts));
    color: var(--muted);
  }
  .themes {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 8px;
  }
  .theme {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 8px;
    border-radius: var(--radius);
    border: 1.5px solid var(--line);
    background: var(--panel);
    text-align: left;
    transition:
      border-color var(--fast) var(--ease),
      transform var(--fast) var(--ease);
  }
  .theme:hover {
    border-color: var(--line-strong);
    transform: translateY(-1px);
  }
  .theme.on {
    border-color: var(--accent);
  }
  .swatch {
    display: flex;
    height: 34px;
    border-radius: 6px;
    overflow: hidden;
    border: 1px solid var(--line);
  }
  .swatch i {
    flex: 1;
    display: grid;
    place-items: center;
  }
  .swatch b {
    width: 10px;
    height: 10px;
    border-radius: 50%;
  }
  .name {
    font-weight: 600;
    font-size: calc(13px * var(--ts));
  }
  .tick {
    position: absolute;
    top: 6px;
    right: 6px;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    background: var(--accent);
    color: var(--accent-text);
    animation: pop-in var(--medium) var(--spring);
  }
  .text {
    height: 36px;
    padding: 0 10px;
    border-radius: var(--radius-sm);
    border: 1.5px solid var(--line-strong);
    background: var(--panel);
    font-family: var(--mono);
    transition: border-color var(--fast) var(--ease);
  }
  .text:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: var(--focus);
  }
  .text.invalid {
    border-color: var(--danger);
  }
  .preview {
    margin: 0;
    padding: 6px 10px;
    border-radius: var(--radius-sm);
    background: var(--panel-2);
    font-size: calc(13px * var(--ts));
  }
  .folder {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }
  .path {
    flex: 1;
    min-width: 0;
    padding: 6px 10px;
    border-radius: var(--radius-sm);
    background: var(--panel-2);
    font-size: calc(12.5px * var(--ts));
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .note {
    display: flex;
    gap: 10px;
    padding: 12px;
    border-radius: var(--radius);
    background: var(--ok-soft);
    color: var(--ok);
  }
  .note p {
    margin: 0;
    color: var(--text);
  }
  .about {
    display: flex;
    gap: 14px;
    align-items: center;
  }
  .about p {
    margin: 2px 0 0;
  }
  .status {
    margin: 0;
    min-height: 1.5em;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .models {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .model {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 6px 12px;
    padding: 8px 10px;
    border-radius: var(--radius);
    border: 1.5px solid var(--line);
    transition: border-color var(--fast) var(--ease);
  }
  .model.on {
    border-color: var(--accent);
  }
  .pick {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 0;
    border: 0;
    background: none;
    text-align: left;
    min-width: 0;
  }
  .radio {
    flex: none;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    border: 1.5px solid var(--line-strong);
    transition:
      border-color var(--fast) var(--ease),
      border-width var(--fast) var(--ease);
  }
  .on .radio {
    border: 5px solid var(--accent);
  }
  .pick .txt {
    display: flex;
    flex-direction: column;
    line-height: 1.3;
    min-width: 0;
  }
  .pick .muted {
    font-size: calc(12px * var(--ts));
  }
  .mstate {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: calc(12.5px * var(--ts));
  }
  .mstate .ok {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: var(--ok);
    font-weight: 600;
  }
  .bar {
    width: 90px;
    height: 6px;
    border-radius: 999px;
    background: var(--panel-3);
    overflow: hidden;
  }
  .bar span {
    display: block;
    height: 100%;
    background: var(--accent);
    transition: width var(--medium) var(--ease);
  }
  .model .err {
    grid-column: 1 / -1;
    margin: 0;
    color: var(--danger);
    font-size: calc(12.5px * var(--ts));
  }
  .wlbl {
    min-width: 90px;
    font-size: calc(13px * var(--ts));
  }
  .err {
    color: var(--danger);
  }
  .licenses {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 4px 16px;
    margin: 0;
    font-size: calc(13px * var(--ts));
  }
  .licenses dt {
    color: var(--muted);
  }
  .licenses dd {
    margin: 0;
  }
  @media (max-width: 640px) {
    .body {
      grid-template-columns: 1fr;
    }
    .nav {
      flex-direction: row;
      overflow-x: auto;
      border-right: 0;
      border-bottom: 1px solid var(--line);
    }
  }
</style>
