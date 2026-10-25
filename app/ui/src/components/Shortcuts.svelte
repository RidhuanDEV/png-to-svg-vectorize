<script lang="ts">
  // Keyboard shortcut sheet (press ?). The shortcuts themselves are handled in App and Compare.
  import { t, tk } from '../lib/i18n.svelte';
  import Button from './ui/Button.svelte';

  let { open = $bindable(false) }: { open?: boolean } = $props();
  let card: HTMLDivElement | undefined = $state();
  let previous: HTMLElement | null = null;

  const mac = /Mac|iPhone|iPad/.test(navigator.platform);
  const mod = mac ? '⌘' : 'Ctrl';
  const groups: { title: string; keys: [string, string][] }[] = [
    {
      title: 'sc_general',
      keys: [
        [`${mod} O`, 'sc_open'],
        [`${mod} V`, 'sc_paste'],
        [`${mod} Enter`, 'sc_process'],
        [`${mod} ,`, 'sc_settings'],
        ['?', 'sc_sheet'],
        ['Esc', 'sc_close'],
      ],
    },
    {
      title: 'sc_results',
      keys: [
        ['Alt ↑ / Alt ↓', 'sc_prevNext'],
        [`${mod} S`, 'sc_save'],
        [`${mod} Shift S`, 'sc_saveAll'],
        ['Delete', 'sc_remove'],
      ],
    },
    {
      title: 'sc_view',
      keys: [
        ['+ / −', 'sc_zoom'],
        ['0', 'sc_fit'],
        ['← ↑ → ↓', 'sc_pan'],
        ['E', 'sc_edit'],
        [`${mod} Z / ${mod} Shift Z`, 'sc_undo'],
      ],
    },
  ];

  $effect(() => {
    if (!open || !card) return;
    previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    card.focus();
    return () => previous?.focus?.();
  });
</script>

{#if open}
  <div class="scrim" role="presentation" onpointerdown={(e) => e.target === e.currentTarget && (open = false)}>
    <div
      bind:this={card}
      class="card"
      role="dialog"
      aria-modal="true"
      aria-labelledby="sc-title"
      tabindex="-1"
      onkeydown={(e) => {
        if (e.key === 'Escape' || e.key === '?') {
          e.preventDefault();
          e.stopPropagation();
          open = false;
        }
      }}
      data-testid="shortcuts"
    >
      <header>
        <h2 id="sc-title">{t('shortcuts')}</h2>
        <Button variant="ghost" size="sm" iconOnly icon="x" title={t('close')} onclick={() => (open = false)}>{t('close')}</Button>
      </header>
      <div class="groups">
        {#each groups as g (g.title)}
          <section>
            <h3>{tk(g.title)}</h3>
            <dl>
              {#each g.keys as [k, label] (label)}
                <dt>{#each k.split(' / ') as alt, i (i)}{#if i}<span class="or">/</span>{/if}{#each alt.split(' ') as part, j (j)}<kbd>{part}</kbd>{/each}{/each}</dt>
                <dd>{tk(label)}</dd>
              {/each}
            </dl>
          </section>
        {/each}
      </div>
    </div>
  </div>
{/if}

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 86;
    display: grid;
    place-items: center;
    background: var(--scrim);
    padding: 16px;
    animation: fade-in var(--medium) var(--ease);
  }
  .card {
    width: min(720px, 100%);
    max-height: calc(100vh - 32px);
    overflow: auto;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-lg);
    animation: pop-in var(--slow) var(--spring);
  }
  .card:focus {
    outline: none;
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
  .groups {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 18px;
    padding: 16px;
  }
  h3 {
    margin: 0 0 8px;
    font-size: calc(12px * var(--ts));
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--muted);
  }
  dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 6px 12px;
    margin: 0;
    align-items: center;
  }
  dt {
    display: flex;
    gap: 3px;
    flex-wrap: wrap;
    align-items: center;
  }
  dd {
    margin: 0;
    font-size: calc(13px * var(--ts));
  }
  kbd {
    min-width: 22px;
    padding: 2px 6px;
    border-radius: 5px;
    border: 1px solid var(--line-strong);
    border-bottom-width: 2px;
    background: var(--panel-2);
    font-family: var(--mono);
    font-size: calc(11.5px * var(--ts));
    text-align: center;
  }
  .or {
    color: var(--muted);
    padding: 0 2px;
  }
</style>
