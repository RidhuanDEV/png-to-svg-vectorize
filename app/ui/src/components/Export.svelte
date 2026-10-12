<script lang="ts">
  import type { Job } from '../lib/api';
  import { t } from '../lib/i18n.svelte';
  import { saveAll, saveSvg } from '../lib/platform';
  import { store, type Media } from '../lib/store.svelte';

  let { job, media }: { job: Job | undefined; media: Media | undefined } = $props();
  let copied = $state(false);

  const doneIds = $derived(store.jobs.filter((j) => j.status === 'done').map((j) => j.id));
  const ready = $derived(!!job && job.status === 'done' && !!media?.svgText);

  async function copy() {
    if (!media?.svgText) return;
    await navigator.clipboard.writeText(media.svgText);
    copied = true;
    setTimeout(() => (copied = false), 1500);
  }
</script>

<div class="panel">
  <h2>{t('export')}</h2>
  <div class="buttons">
    <button class="primary" disabled={!ready} onclick={() => job && media?.svgText && saveSvg(job.id, job.name, media.svgText)}
      data-testid="save-svg">{t('saveSvg')}</button>
    <button disabled={doneIds.length === 0} onclick={() => saveAll(doneIds)} data-testid="save-all"
      >{t('saveAll')} ({doneIds.length})</button>
    <button disabled={!ready} onclick={copy} data-testid="copy-svg">{copied ? t('copied') : t('copySvg')}</button>
  </div>
</div>

<style>
  .buttons {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
</style>
