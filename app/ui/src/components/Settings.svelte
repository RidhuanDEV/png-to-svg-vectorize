<script lang="ts">
  import type { OptionSpec, Overrides } from '../lib/api';
  import { t, tk } from '../lib/i18n.svelte';
  import { presetDefaults, retryJob, saveSettings, store } from '../lib/store.svelte';

  const defaults = $derived(presetDefaults(store.settings.preset));

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
</script>

<div class="panel">
  <h2>{t('settings')}</h2>
  <div class="presets" role="radiogroup" aria-label={t('preset')}>
    {#each store.info?.presets ?? [] as p (p.name)}
      <label class="preset" class:on={store.settings.preset === p.name} title={p.description}>
        <input
          type="radio"
          name="preset"
          value={p.name}
          checked={store.settings.preset === p.name}
          onchange={() => choosePreset(p.name)}
          data-testid="preset-{p.name}"
        />
        {tk('preset_' + p.name)}
      </label>
    {/each}
  </div>

  <details
    open={store.settings.advanced}
    ontoggle={(e) => {
      store.settings.advanced = (e.currentTarget as HTMLDetailsElement).open;
      saveSettings();
    }}
  >
    <summary>{t('advanced')}</summary>
    <div class="opts">
      {#each store.info?.options ?? [] as spec (spec.name)}
        {@const v = value(spec)}
        {#if spec.type === 'bool'}
          <label class="row check">
            <input type="checkbox" checked={!!v} onchange={(e) => set(spec.name, e.currentTarget.checked)}
              data-testid="opt-{spec.name}" />
            {tk('opt_' + spec.name)}
          </label>
        {:else if spec.name === 'scale'}
          <label class="row">
            <span>{tk('opt_scale')}</span>
            <select
              value={v === null ? 'auto' : String(v)}
              onchange={(e) => set('scale', e.currentTarget.value === 'auto' ? null : Number(e.currentTarget.value))}
              data-testid="opt-scale"
            >
              <option value="auto">{t('auto')}</option>
              {#each [1, 2, 3, 4] as n (n)}<option value={String(n)}>{n}×</option>{/each}
            </select>
          </label>
        {:else}
          <label class="row">
            <span>{tk('opt_' + spec.name)} <b>{Number(v).toFixed(spec.step && spec.step < 0.1 ? 2 : 1)}</b></span>
            <input
              type="range"
              min={spec.min}
              max={spec.max}
              step={spec.step}
              value={v ?? 0}
              oninput={(e) => set(spec.name, Number(e.currentTarget.value))}
              data-testid="opt-{spec.name}"
            />
          </label>
        {/if}
      {/each}
      <button onclick={() => { store.settings.overrides = {}; saveSettings(); }}>{t('resetPreset')}</button>
    </div>
  </details>

  <p class="muted hint">{t('newUploadsUse')}</p>
  <button
    class="primary wide"
    disabled={!store.selected}
    onclick={() => store.selected && retryJob(store.selected, true)}
    data-testid="apply-selected">{t('applySelected')}</button
  >
</div>

<style>
  .presets {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
  }
  .preset {
    display: flex;
    gap: 6px;
    align-items: center;
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 6px 8px;
    cursor: pointer;
  }
  .preset.on {
    border-color: var(--accent);
    background: var(--panel-2);
  }
  details {
    margin-top: 10px;
  }
  summary {
    cursor: pointer;
    color: var(--muted);
  }
  .opts {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-top: 8px;
  }
  .row {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .row.check {
    flex-direction: row;
    align-items: center;
    gap: 6px;
  }
  .row span {
    display: flex;
    justify-content: space-between;
  }
  input[type='range'] {
    accent-color: var(--accent);
  }
  .hint {
    font-size: 12px;
    margin: 10px 0 6px;
  }
  .wide {
    width: 100%;
  }
</style>
