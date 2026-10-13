<script lang="ts">
  import type { Job } from '../lib/api';
  import { t, tf } from '../lib/i18n.svelte';
  import { isDesktop, saveAll, saveSvg } from '../lib/platform';
  import { report, store, type Media } from '../lib/store.svelte';
  import { toast } from '../lib/toast.svelte';
  import Button from './ui/Button.svelte';

  let { job, media }: { job: Job | undefined; media: Media | undefined } = $props();
  let copied = $state(false);
  let saving = $state(false);

  const doneIds = $derived(store.jobs.filter((j) => j.status === 'done' && !store.hidden[j.id]).map((j) => j.id));
  const ready = $derived(!!job && job.status === 'done' && !!media?.svgText);

  async function run(work: () => Promise<boolean | number | void>, done: (r: boolean | number | void) => void) {
    saving = true;
    try {
      done(await work());
    } catch (e) {
      report(e);
    } finally {
      saving = false;
    }
  }

  async function copy() {
    if (!media?.svgText) return;
    try {
      await navigator.clipboard.writeText(media.svgText);
      copied = true;
      setTimeout(() => (copied = false), 1600);
    } catch (e) {
      report(e);
    }
  }
</script>

{#if doneIds.length}
  <section class="panel" aria-labelledby="exp-title">
    <h2 id="exp-title">{t('export')}</h2>
    <div class="buttons">
      <Button
        variant="primary"
        icon="download"
        wide
        disabled={!ready || saving}
        onclick={() => job && media?.svgText && run(() => saveSvg(job.id, job.name, media.svgText!), (r) => isDesktop() && r && toast('success', t('t_saved')))}
        data-testid="save-svg">{t('saveSvg')}</Button
      >
      <Button
        variant="secondary"
        icon="download"
        wide
        disabled={saving}
        onclick={() => run(() => saveAll(doneIds), (n) => isDesktop() && typeof n === 'number' && n > 0 && toast('success', tf('t_savedAll', { n })))}
        data-testid="save-all">{tf('saveAll', { n: doneIds.length })}</Button
      >
      <Button variant="ghost" icon={copied ? 'check' : 'copy'} wide disabled={!ready} onclick={copy} data-testid="copy-svg"
        >{copied ? t('copied') : t('copySvg')}</Button
      >
    </div>
  </section>
{/if}

<style>
  .buttons {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
</style>
