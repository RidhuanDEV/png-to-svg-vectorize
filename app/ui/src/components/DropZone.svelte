<script lang="ts">
  import { t } from '../lib/i18n.svelte';
  import { openNative } from '../lib/platform';
  import { addFiles, adoptJobs } from '../lib/store.svelte';

  let input: HTMLInputElement;

  async function open() {
    const ids = await openNative();
    if (ids === null) input.click();
    else await adoptJobs(ids);
  }
</script>

<div class="panel zone" data-testid="dropzone">
  <svg viewBox="0 0 24 24" width="28" height="28" aria-hidden="true">
    <path d="M12 16V4m0 0-4 4m4-4 4 4M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" fill="none" stroke="currentColor"
      stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
  </svg>
  <p>{t('drop')}</p>
  <span class="muted">{t('orOpen')}</span>
  <button class="primary" onclick={open}>{t('open')}</button>
  <input
    bind:this={input}
    class="sr-only"
    type="file"
    multiple
    accept="image/png,image/webp,image/jpeg"
    data-testid="file-input"
    onchange={(e) => {
      const files = (e.currentTarget as HTMLInputElement).files;
      if (files?.length) void addFiles(Array.from(files));
      (e.currentTarget as HTMLInputElement).value = '';
    }}
  />
</div>

<style>
  .zone {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
    text-align: center;
    border-style: dashed;
    border-width: 2px;
    color: var(--muted);
  }
  p {
    margin: 0;
    color: var(--text);
  }
</style>
