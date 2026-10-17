<script lang="ts">
  // Coach marks: each step highlights a real part of the screen ([data-tour=...]) and explains it in one or two
  // sentences. Without a target (or when it is hidden) the card is centred. Esc or "Skip" ends the tour.
  import { t, tf, type Key } from '../lib/i18n.svelte';
  import { finishTour, tour } from '../lib/tour.svelte';
  import Button from './ui/Button.svelte';

  const steps: { target?: string; title: Key; body: Key }[] = [
    { title: 'tour1_title', body: 'tour1_body' },
    { target: 'add', title: 'tour2_title', body: 'tour2_body' },
    { target: 'style', title: 'tour3_title', body: 'tour3_body' },
    { target: 'speed', title: 'tour4_title', body: 'tour4_body' },
    { target: 'compare', title: 'tour5_title', body: 'tour5_body' },
  ];

  let rect = $state<DOMRect | null>(null);
  let card: HTMLDivElement | undefined = $state();
  let vw = $state(window.innerWidth);
  let vh = $state(window.innerHeight);
  const step = $derived(steps[tour.step]);
  const last = $derived(tour.step === steps.length - 1);

  function measure() {
    vw = window.innerWidth;
    vh = window.innerHeight;
    const el = step?.target ? document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`) : null;
    const r = el?.getBoundingClientRect();
    rect = r && r.width > 0 && r.height > 0 ? r : null;
    el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  $effect(() => {
    if (!tour.open) return;
    void tour.step;
    measure();
    card?.focus();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  });

  const PAD = 8;
  const W = 340;
  const hole = $derived(
    rect ? `left:${rect.left - PAD}px;top:${rect.top - PAD}px;width:${rect.width + PAD * 2}px;height:${rect.height + PAD * 2}px` : '',
  );
  // put the card beside the highlighted area where it fits: right, left, below, above, else centred
  const place = $derived.by(() => {
    if (!rect) return `left:${(vw - W) / 2}px;top:${Math.max(16, vh / 2 - 120)}px`;
    const top = Math.min(Math.max(16, rect.top), vh - 260);
    if (rect.right + 16 + W < vw) return `left:${rect.right + 16}px;top:${top}px`;
    if (rect.left - 16 - W > 0) return `left:${rect.left - 16 - W}px;top:${top}px`;
    const left = Math.min(Math.max(16, rect.left), vw - W - 16);
    if (rect.bottom + 230 < vh) return `left:${left}px;top:${rect.bottom + 16}px`;
    return `left:${left}px;top:${Math.max(16, rect.top - 236)}px`;
  });

  function key(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.preventDefault();
      finishTour();
    } else if (e.key === 'ArrowRight' && !last) tour.step++;
    else if (e.key === 'ArrowLeft' && tour.step > 0) tour.step--;
    else if (e.key === 'Tab' && card) {
      const items = Array.from(card.querySelectorAll<HTMLElement>('button'));
      const i = items.indexOf(document.activeElement as HTMLElement);
      if (e.shiftKey && i <= 0) {
        e.preventDefault();
        items[items.length - 1].focus();
      } else if (!e.shiftKey && i === items.length - 1) {
        e.preventDefault();
        items[0].focus();
      }
    }
  }
</script>

{#if tour.open && step}
  <div class="tour" data-testid="tour">
    {#if rect}
      <div class="hole" style={hole} aria-hidden="true"></div>
    {:else}
      <div class="dim" aria-hidden="true"></div>
    {/if}
    <!-- the card is a dialog with its own keyboard handling -->
    <div
      bind:this={card}
      class="card"
      style="{place};width:{W}px"
      role="dialog"
      aria-modal="true"
      aria-labelledby="tour-title"
      aria-describedby="tour-body"
      tabindex="-1"
      onkeydown={key}
    >
      {#key tour.step}
        <div class="content">
          <span class="count">{tf('tour_step', { n: tour.step + 1, m: steps.length })}</span>
          <h2 id="tour-title">{t(step.title)}</h2>
          <p id="tour-body">{t(step.body)}</p>
        </div>
      {/key}
      <div class="dots" aria-hidden="true">
        {#each steps as _, i (i)}<span class:on={i === tour.step}></span>{/each}
      </div>
      <div class="actions">
        <Button variant="ghost" size="sm" onclick={finishTour} data-testid="tour-skip">{t('tour_skip')}</Button>
        <span class="grow"></span>
        {#if tour.step > 0}
          <Button variant="secondary" size="sm" onclick={() => tour.step--}>{t('tour_back')}</Button>
        {/if}
        {#if last}
          <Button variant="primary" size="sm" onclick={finishTour} data-testid="tour-done">{t('tour_done')}</Button>
        {:else}
          <Button variant="primary" size="sm" onclick={() => tour.step++} data-testid="tour-next">{t('tour_next')}</Button>
        {/if}
      </div>
    </div>
  </div>
{/if}

<style>
  .tour {
    position: fixed;
    inset: 0;
    z-index: 100;
  }
  .dim {
    position: absolute;
    inset: 0;
    background: var(--scrim);
    animation: fade-in var(--medium) var(--ease);
  }
  .hole {
    position: absolute;
    border-radius: var(--radius);
    box-shadow:
      0 0 0 3px var(--accent),
      0 0 0 9999px var(--scrim);
    transition:
      left var(--slow) var(--ease),
      top var(--slow) var(--ease),
      width var(--slow) var(--ease),
      height var(--slow) var(--ease);
    pointer-events: none;
  }
  .card {
    position: absolute;
    max-width: calc(100vw - 32px);
    background: var(--panel);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    padding: 18px;
    animation: pop-in var(--slow) var(--spring);
  }
  .content {
    animation: fade-in var(--medium) var(--ease);
  }
  .count {
    font-size: calc(12px * var(--ts));
    font-weight: 600;
    color: var(--accent);
  }
  h2 {
    margin: 4px 0 6px;
    font-size: calc(17px * var(--ts));
  }
  p {
    margin: 0;
    color: var(--muted);
  }
  .dots {
    display: flex;
    gap: 6px;
    margin: 14px 0 12px;
  }
  .dots span {
    width: 6px;
    height: 6px;
    border-radius: 999px;
    background: var(--panel-3);
    transition:
      width var(--medium) var(--ease),
      background var(--medium) var(--ease);
  }
  .dots span.on {
    width: 18px;
    background: var(--accent);
  }
  .actions {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .grow {
    flex: 1;
  }
</style>
