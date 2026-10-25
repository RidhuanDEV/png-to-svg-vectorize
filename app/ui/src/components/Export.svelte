<script lang="ts">
  // Save the selected result as SVG, PDF, EPS, DXF or PNG (rendered from the vector at any scale), save all, copy.
  import type { Job } from '../lib/api';
  import { t, tf } from '../lib/i18n.svelte';
  import { isDesktop, renderPng, saveAll, savePng, saveReport, saveResult } from '../lib/platform';
  import { reportRow, toCsv, toJson } from '../lib/report';
  import { EXPORT_CHOICES, PNG_SCALES, prefs, savePrefs } from '../lib/prefs.svelte';
  import { ensureMedia, report, store, type Media } from '../lib/store.svelte';
  import { toast } from '../lib/toast.svelte';
  import Button from './ui/Button.svelte';
  import Segmented from './ui/Segmented.svelte';

  let { job, media }: { job: Job | undefined; media: Media | undefined } = $props();
  let copied = $state<'svg' | 'png' | null>(null);
  let saving = $state(false);

  const doneIds = $derived(store.jobs.filter((j) => j.status === 'done' && !store.hidden[j.id]).map((j) => j.id));
  const ready = $derived(!!job && job.status === 'done' && !!media?.svgText);
  const fmt = $derived(prefs.exportFormat);
  const FMT = $derived(fmt.toUpperCase());

  async function run<R>(work: () => Promise<R>, done: (r: R) => void) {
    saving = true;
    try {
      done(await work());
    } catch (e) {
      report(e);
    } finally {
      saving = false;
    }
  }

  async function png(j: Job, svg: string): Promise<boolean> {
    const r = await renderPng(svg, j.width, j.height, prefs.pngScale);
    if (r.scale < prefs.pngScale) toast('info', tf('t_pngScaled', { s: r.scale.toFixed(1) }));
    return savePng(r.png, j.filename);
  }

  function saveOne() {
    const j = job;
    const svg = media?.svgText;
    if (!j || !svg) return;
    const f = prefs.exportFormat;
    run(() => (f === 'png' ? png(j, svg) : saveResult(j.id, j.filename, f)), (ok) => isDesktop() && ok && toast('success', t('t_saved')));
  }

  function saveEvery() {
    const f = prefs.exportFormat;
    if (f === 'png') return;
    run(() => saveAll(doneIds, f), (n) => isDesktop() && n > 0 && toast('success', tf('t_savedAll', { n })));
  }

  /** Batch report of every finished result; scores are measured first for results not opened yet. */
  function saveBatchReport(kind: 'csv' | 'json') {
    run(
      async () => {
        const done = store.jobs.filter((j) => j.status === 'done' && !store.hidden[j.id]);
        for (const j of done) if (store.media[j.id]?.score === undefined) await ensureMedia(j);
        const rows = done.map((j) => reportRow(j, store.media[j.id]?.score));
        return saveReport(`png2svg-report.${kind}`, kind === 'csv' ? toCsv(rows) : toJson(rows));
      },
      (ok) => isDesktop() && ok && toast('success', t('t_saved')),
    );
  }

  async function copy(kind: 'svg' | 'png') {
    const j = job;
    const svg = media?.svgText;
    if (!j || !svg) return;
    try {
      if (kind === 'svg') await navigator.clipboard.writeText(svg);
      else {
        const r = await renderPng(svg, j.width, j.height, prefs.pngScale);
        await navigator.clipboard.write([new ClipboardItem({ 'image/png': r.png })]);
      }
      copied = kind;
      setTimeout(() => (copied = null), 1600);
    } catch (e) {
      report(e);
    }
  }
</script>

{#if doneIds.length}
  <section class="panel" aria-labelledby="exp-title">
    <h2 id="exp-title">{t('export')}</h2>
    <div class="formats">
      <Segmented
        size="sm"
        label={t('format')}
        value={prefs.exportFormat}
        options={EXPORT_CHOICES.map((f) => ({ value: f, label: f.toUpperCase() }))}
        onchange={(f) => {
          prefs.exportFormat = f;
          savePrefs();
        }}
        testid="export-format"
      />
      {#if fmt === 'png'}
        <Segmented
          size="sm"
          label={t('pngScale')}
          value={String(prefs.pngScale)}
          options={PNG_SCALES.map((s) => ({ value: String(s), label: `${s}×` }))}
          onchange={(s) => {
            prefs.pngScale = Number(s);
            savePrefs();
          }}
          testid="png-scale"
        />
      {/if}
      <p class="hint muted" data-testid="format-hint">{t(('formatHint_' + fmt) as 'formatHint_svg')}</p>
    </div>
    <div class="buttons">
      <Button variant="primary" icon="download" wide disabled={!ready || saving} onclick={saveOne} data-testid="save-svg"
        >{tf('saveAs', { f: FMT })}</Button
      >
      <Button
        variant="secondary"
        icon="download"
        wide
        disabled={saving || fmt === 'png'}
        title={fmt === 'png' ? t('saveAllNoPng') : undefined}
        onclick={saveEvery}
        data-testid="save-all">{tf('saveAll', { n: doneIds.length })}</Button
      >
      <div class="copy">
        <Button variant="ghost" icon={copied === 'svg' ? 'check' : 'copy'} wide disabled={!ready} onclick={() => copy('svg')} data-testid="copy-svg"
          >{copied === 'svg' ? t('copied') : t('copySvg')}</Button
        >
        <Button variant="ghost" icon={copied === 'png' ? 'check' : 'image'} wide disabled={!ready} onclick={() => copy('png')} data-testid="copy-png"
          >{copied === 'png' ? t('copied') : t('copyPng')}</Button
        >
      </div>
      <div class="report">
        <span class="muted">{t('report')}</span>
        <Button variant="ghost" size="sm" disabled={saving} onclick={() => saveBatchReport('csv')} data-testid="report-csv">CSV</Button>
        <Button variant="ghost" size="sm" disabled={saving} onclick={() => saveBatchReport('json')} data-testid="report-json">JSON</Button>
      </div>
    </div>
  </section>
{/if}

<style>
  .formats {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 10px;
  }
  .hint {
    margin: 0;
    font-size: calc(12px * var(--ts));
  }
  .buttons {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .report {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: calc(13px * var(--ts));
  }
  .report .muted {
    margin-right: auto;
  }
  .copy {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
  }
</style>
