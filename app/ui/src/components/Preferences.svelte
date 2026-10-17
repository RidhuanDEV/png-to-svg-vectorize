<script lang="ts">
  // Settings (Ctrl+,): appearance, processing limits, how results are saved, privacy, about. Changes apply at once.
  import { onMount } from 'svelte';
  import { api, type UpdateInfo } from '../lib/api';
  import { i18n, languages, setLang, t, tf, tk, type Key } from '../lib/i18n.svelte';
  import { desktop, openExternal, setCloseMessage, type DesktopPrefs } from '../lib/platform';
  import { MAX_SIDES, MAX_STAGED, prefs, previewName, savePrefs, TEXT_SCALES, THEMES, type ThemeChoice } from '../lib/prefs.svelte';
  import { saveSettings, setSpeed, store, updateService } from '../lib/store.svelte';
  import { startTour } from '../lib/tour.svelte';
  import themes from '../theme/themes.json';
  import Button from './ui/Button.svelte';
  import Icon, { type IconName } from './ui/Icon.svelte';
  import Segmented from './ui/Segmented.svelte';
  import Select from './ui/Select.svelte';
  import Switch from './ui/Switch.svelte';

  let { open = $bindable(false) }: { open?: boolean } = $props();

  type Section = 'appearance' | 'processing' | 'output' | 'privacy' | 'about';
  const sections: { id: Section; icon: IconName }[] = [
    { id: 'appearance', icon: 'sparkles' },
    { id: 'processing', icon: 'gauge' },
    { id: 'output', icon: 'download' },
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
  const REPO = 'https://github.com/RidhuanDEV/png-to-svg-vectorize';
  const LICENSES = [
    ['numpy, SciPy', 'BSD-3-Clause'],
    ['Pillow', 'MIT-CMU (HPND)'],
    ['FastAPI, Pydantic', 'MIT'],
    ['Uvicorn, pywebview', 'BSD-3-Clause'],
    ['Svelte', 'MIT'],
    ['IBM Plex Sans / Mono', 'SIL OFL 1.1'],
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
