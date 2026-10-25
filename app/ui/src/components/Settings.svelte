<script lang="ts">
  // Right column, top: the result style (visual cards + optional fine-tuning) and the processing speed.
  import type { OptionSpec, Overrides, Speed } from '../lib/api';
  import { t, tf, tk } from '../lib/i18n.svelte';
  import { prefs, savePrefs } from '../lib/prefs.svelte';
  import { aiReady, presetDefaults, retryJob, saveSettings, selectedJob, setSpeed, store } from '../lib/store.svelte';
  import Button from './ui/Button.svelte';
  import Icon from './ui/Icon.svelte';
  import Segmented from './ui/Segmented.svelte';
  import Slider from './ui/Slider.svelte';
  import Switch from './ui/Switch.svelte';

  const defaults = $derived(presetDefaults(store.settings.preset));
  const job = $derived(selectedJob());
  const canReprocess = $derived(!!job && store.focus === 'result' && (job.status === 'done' || job.status === 'error'));

  // a tiny preview glyph per style, so the choice is visual and not only words
  const glyph: Record<string, string> = {
    cartoon: 'M6 18c2-6 4-9 6-9s4 3 6 9M9 9a3 3 0 1 1 6 0',
    flat: 'M4 16l5-6 4 4 3-3 4 5z',
    logo: 'M12 4l7 4v8l-7 4-7-4V8z',
    poster: 'M5 5h14v14H5zM5 15l4-4 3 3 3-2 4 3',
  };

  function value(spec: OptionSpec): boolean | number | null {
    const o = store.settings.overrides[spec.name];
    return (o ?? defaults?.[spec.name] ?? null) as boolean | number | null;
  }

  function set(name: keyof Overrides, v: boolean | number | null) {
    const next = { ...store.settings.overrides } as Record<string, unknown>;
    if (defaults && defaults[name] === v) delete next[name];
    else next[name] = v;
    store.settings.overrides = next as Partial<Overrides>;
    saveSettings();
  }

  function choosePreset(name: string) {
    store.settings.preset = name;
    store.settings.overrides = {};
    saveSettings();
  }

  const speeds: Speed[] = ['auto', 'saver', 'balanced', 'fast'];
  const level = { saver: 1, balanced: 2, fast: 3 } as const;
  const speedHelp = $derived.by(() => {
    const s = store.service;
    if (!s) return '';
    if (s.speed === 'auto') return tf('speedHelp_auto', { mode: tk('speed_' + s.effective), n: s.concurrency });
    return tf(('speedHelp_' + s.speed) as 'speedHelp_saver', { n: s.speeds[s.speed as 'fast'] ?? s.concurrency });
  });
  const changed = $derived(Object.keys(store.settings.overrides).length > 0);
</script>

<section class="panel" data-tour="style" aria-labelledby="style-title">
  <h2 id="style-title">{t('style')}</h2>
  <div class="presets" role="radiogroup" aria-label={t('style')}>
    {#each store.info?.presets ?? [] as p (p.name)}
      {@const on = store.settings.preset === p.name}
      <button
        type="button"
        role="radio"
        aria-checked={on}
        class="preset"
        class:on
        onclick={() => choosePreset(p.name)}
        title={p.description}
        data-testid="preset-{p.name}"
      >
        <span class="glyph" aria-hidden="true">
          <svg viewBox="0 0 24 24"><path d={glyph[p.name] ?? glyph.flat} /></svg>
        </span>
        <span class="txt">
          <b>{tk('preset_' + p.name)}</b>
          <span class="muted">{tk('desc_' + p.name)}</span>
        </span>
        {#if on}<span class="dot"><Icon name="check" size={12} stroke={3} /></span>{/if}
      </button>
    {/each}
  </div>

  <button
    class="more"
    aria-expanded={store.settings.advanced}
    onclick={() => {
      store.settings.advanced = !store.settings.advanced;
      saveSettings();
    }}
    data-testid="advanced-toggle"
  >
    <Icon name="sliders" size={16} />
    <span>{t('advanced')}</span>
    {#if changed}<span class="changed" aria-hidden="true"></span>{/if}
    <span class="chev" class:open={store.settings.advanced}><Icon name="chevronDown" size={15} /></span>
  </button>

  {#if store.settings.advanced}
    <div class="opts">
      {#each store.info?.options ?? [] as spec (spec.name)}
        {@const v = value(spec)}
        {#if spec.type === 'bool'}
          <Switch checked={!!v} label={tk('opt_' + spec.name)} onchange={(c) => set(spec.name, c)} testid="opt-{spec.name}" />
        {:else if spec.name === 'scale'}
          <div class="row">
            <span class="lbl">{tk('opt_scale')}</span>
            <Segmented
              size="sm"
              label={tk('opt_scale')}
              value={v === null ? 'auto' : String(v)}
              options={[{ value: 'auto', label: t('auto') }, ...[1, 2, 3, 4].map((n) => ({ value: String(n), label: `${n}×` }))]}
              onchange={(x) => set('scale', x === 'auto' ? null : Number(x))}
              testid="opt-scale"
            />
          </div>
        {:else}
          <Slider
            label={tk('opt_' + spec.name)}
            min={spec.min ?? 0}
            max={spec.max ?? 1}
            step={spec.step ?? 0.1}
            value={Number(v ?? 0)}
            format={(x) => x.toFixed(spec.step && spec.step < 0.1 ? 2 : 1)}
            onchange={(x) => set(spec.name, x)}
            testid="opt-{spec.name}"
          />
        {/if}
      {/each}
      <Button variant="ghost" size="sm" icon="retry" disabled={!changed} onclick={() => {
        store.settings.overrides = {};
        saveSettings();
      }}>{t('resetPreset')}</Button>
    </div>
  {/if}

  {#if store.ai?.runtime}
    <div class="ai" data-testid="ai-mode-box">
      <span class="lbl"><Icon name="sparkles" size={14} /> {t('ai')}</span>
      {#if aiReady()}
        <Segmented
          size="sm"
          label={t('ai')}
          value={prefs.aiMode}
          options={(['off', 'auto', 'always'] as const).map((m) => ({ value: m, label: tk('ai_' + m) }))}
          onchange={(v) => {
            prefs.aiMode = v;
            savePrefs();
          }}
          testid="ai-mode"
        />
        <p class="note muted">{prefs.aiMode === 'auto' ? t('aiAutoHint') : t('aiHint')}</p>
      {:else}
        <p class="note muted" data-testid="ai-needs-model">{t('aiNeedsModel')}</p>
      {/if}
    </div>
  {/if}

  <p class="note muted">{t('styleNote')}</p>
  {#if canReprocess && job}
    <Button variant="secondary" wide icon="retry" onclick={() => retryJob(job.id, true)} data-testid="apply-selected">{t('reprocess')}</Button>
  {/if}
</section>

<section class="panel" data-tour="speed" aria-labelledby="speed-title">
  <h2 id="speed-title"><Icon name="gauge" size={14} /> {t('speed')}</h2>
  {#if store.service}
    {@const svc = store.service}
    <div class="speeds" role="radiogroup" aria-label={t('speed')} data-testid="speed">
      {#each speeds as sp (sp)}
        {@const on = svc.speed === sp}
        <button
          type="button"
          role="radio"
          aria-checked={on}
          class="speed"
          class:on
          onclick={() => setSpeed(sp)}
          data-testid="speed-{sp}"
        >
          <span class="bars" aria-hidden="true">
            {#each [1, 2, 3] as b (b)}
              <i class:lit={b <= level[sp === 'auto' ? svc.auto : sp]}></i>
            {/each}
          </span>
          <b>{tk('speed_' + sp)}</b>
          <span class="muted">{svc.speeds[sp === 'auto' ? svc.auto : sp]}×</span>
        </button>
      {/each}
    </div>
    <p class="note muted" data-testid="speed-help">{speedHelp}</p>
  {/if}
</section>

<style>
  section h2 {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .ai {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid var(--line);
  }
  .ai .lbl {
    display: flex;
    align-items: center;
    gap: 6px;
    font-weight: 600;
  }
  .ai .note {
    margin: 0;
  }
  .presets {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .preset {
    position: relative;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 10px;
    border-radius: var(--radius-sm);
    border: 1.5px solid var(--line);
    background: var(--panel);
    text-align: left;
    transition:
      border-color var(--fast) var(--ease),
      background var(--fast) var(--ease),
      transform var(--fast) var(--ease);
  }
  .preset:hover {
    border-color: var(--line-strong);
    transform: translateX(2px);
  }
  .preset:active {
    transform: scale(0.98);
  }
  .preset.on {
    border-color: var(--accent);
    background: var(--accent-soft);
  }
  .glyph {
    width: 34px;
    height: 34px;
    border-radius: 9px;
    display: grid;
    place-items: center;
    background: var(--panel-2);
    flex: none;
  }
  .on .glyph {
    background: var(--accent);
  }
  .glyph svg {
    width: 20px;
    height: 20px;
    fill: none;
    stroke: var(--muted);
    stroke-width: 1.8;
    stroke-linejoin: round;
    stroke-linecap: round;
  }
  .on .glyph svg {
    stroke: var(--accent-text);
  }
  .txt {
    display: flex;
    flex-direction: column;
    line-height: 1.3;
    min-width: 0;
  }
  .txt .muted {
    font-size: calc(12px * var(--ts));
  }
  .dot {
    margin-left: auto;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    display: grid;
    place-items: center;
    background: var(--accent);
    color: var(--accent-text);
    animation: pop-in var(--medium) var(--spring);
  }
  .more {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    margin-top: 10px;
    padding: 8px 6px;
    border: 0;
    border-radius: var(--radius-sm);
    background: none;
    color: var(--muted);
    font-weight: 600;
  }
  .more:hover {
    background: var(--panel-2);
    color: var(--text);
  }
  .changed {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--accent);
  }
  .chev {
    margin-left: auto;
    transition: transform var(--medium) var(--ease);
  }
  .chev.open {
    transform: rotate(180deg);
  }
  .opts {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 6px 4px 2px;
    animation: pop-in var(--medium) var(--ease);
  }
  .row {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .lbl {
    font-size: calc(13px * var(--ts));
  }
  .note {
    font-size: calc(12.5px * var(--ts));
    margin: 10px 0 8px;
  }
  .speeds {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
  }
  .speed {
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    border-radius: var(--radius-sm);
    border: 1.5px solid var(--line);
    background: var(--panel);
    text-align: left;
    font-size: calc(13px * var(--ts));
    transition:
      border-color var(--fast) var(--ease),
      background var(--fast) var(--ease),
      transform var(--fast) var(--ease);
  }
  .speed:hover {
    border-color: var(--line-strong);
  }
  .speed:active {
    transform: scale(0.97);
  }
  .speed.on {
    border-color: var(--accent);
    background: var(--accent-soft);
  }
  .speed .muted {
    font-size: calc(12px * var(--ts));
    font-variant-numeric: tabular-nums;
  }
  .bars {
    display: flex;
    align-items: flex-end;
    gap: 2px;
    height: 14px;
  }
  .bars i {
    width: 4px;
    border-radius: 2px;
    background: var(--panel-3);
    transition: background var(--medium) var(--ease);
  }
  .bars i:nth-child(1) {
    height: 6px;
  }
  .bars i:nth-child(2) {
    height: 10px;
  }
  .bars i:nth-child(3) {
    height: 14px;
  }
  .bars i.lit {
    background: var(--accent);
  }
</style>
