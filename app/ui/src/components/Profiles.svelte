<script lang="ts">
  // Style profiles in the style panel: pick a saved one, save the current style under a name, import or export a
  // `.pngsvg-profile.json` file (the command line reads the same file with --profile).
  import type { Overrides } from '../lib/api';
  import { ApiError } from '../lib/api';
  import { t, tf } from '../lib/i18n.svelte';
  import { applyProfile, exportProfile, importProfile, profiles, removeProfile, saveCurrent } from '../lib/profiles.svelte';
  import { report, store } from '../lib/store.svelte';
  import { toast } from '../lib/toast.svelte';
  import Button from './ui/Button.svelte';
  import Select from './ui/Select.svelte';

  let naming = $state(false);
  let name = $state('');
  let file: HTMLInputElement | undefined = $state();

  const key = (o: Partial<Overrides>) =>
    JSON.stringify(
      Object.entries(o)
        .filter(([k]) => k !== 'ai' && k !== 'ai_auto')
        .sort(([a], [b]) => a.localeCompare(b)),
    );
  // the profile that matches the current style exactly (none once the user changes something)
  const active = $derived(
    profiles.list.find((p) => p.preset === store.settings.preset && key(p.options) === key(store.settings.overrides))?.name ?? '',
  );
  const options = $derived([{ value: '', label: t('profileNone') }, ...profiles.list.map((p) => ({ value: p.name, label: p.name }))]);

  function choose(v: string) {
    const p = profiles.list.find((x) => x.name === v);
    if (p) applyProfile(p);
  }

  function save(e: SubmitEvent) {
    e.preventDefault();
    const n = name.trim().slice(0, 80);
    if (!n) return;
    saveCurrent(n);
    naming = false;
    name = '';
    toast('success', tf('t_profileSaved', { name: n }));
  }

  async function onFile() {
    const f = file?.files?.[0];
    if (file) file.value = '';
    if (!f) return;
    try {
      const p = await importProfile(f);
      toast('success', tf('t_profileImported', { name: p.name }));
    } catch (err) {
      toast('error', tf('profileInvalid', { detail: err instanceof ApiError ? err.message : t('profileTooLarge') }));
    }
  }

  async function exportCurrent() {
    try {
      if (await exportProfile(active || t('profileDefaultName'))) toast('success', t('t_saved'));
    } catch (err) {
      report(err);
    }
  }
</script>

<div class="profiles" data-testid="profiles">
  <span class="lbl">{t('profile')}</span>
  <div class="row">
    <div class="pick"><Select label={t('profile')} value={active} {options} onchange={choose} testid="profile-select" /></div>
    <Button variant="ghost" size="sm" iconOnly icon="plus" title={t('profileSave')} onclick={() => (naming = !naming)} data-testid="profile-new"
      >{t('profileSave')}</Button
    >
    <Button variant="ghost" size="sm" iconOnly icon="download" title={t('profileExport')} onclick={exportCurrent} data-testid="profile-export"
      >{t('profileExport')}</Button
    >
    <Button variant="ghost" size="sm" iconOnly icon="upload" title={t('profileImport')} onclick={() => file?.click()} data-testid="profile-import"
      >{t('profileImport')}</Button
    >
    {#if active}
      <Button variant="ghost" size="sm" iconOnly icon="trash" title={t('profileDelete')} onclick={() => removeProfile(active)} data-testid="profile-delete"
        >{t('profileDelete')}</Button
      >
    {/if}
  </div>
  {#if naming}
    <form class="row" onsubmit={save}>
      <!-- svelte-ignore a11y_autofocus -->
      <input class="text" bind:value={name} maxlength="80" placeholder={t('profileName')} aria-label={t('profileName')} autofocus data-testid="profile-name" />
      <Button variant="primary" size="sm" type="submit" disabled={!name.trim()} data-testid="profile-save">{t('save')}</Button>
    </form>
  {/if}
  <input
    bind:this={file}
    class="sr-only"
    type="file"
    accept=".json,application/json"
    tabindex="-1"
    aria-hidden="true"
    onchange={onFile}
    data-testid="profile-file"
  />
</div>

<style>
  .profiles {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 10px;
  }
  .lbl {
    font-weight: 600;
    font-size: calc(13px * var(--ts));
  }
  .row {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .pick {
    flex: 1;
    min-width: 0;
  }
  .text {
    flex: 1;
    min-width: 0;
    height: 32px;
    padding: 0 10px;
    border-radius: var(--radius-sm);
    border: 1.5px solid var(--line-strong);
    background: var(--panel);
    transition: border-color var(--fast) var(--ease);
  }
  .text:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: var(--focus);
  }
</style>
