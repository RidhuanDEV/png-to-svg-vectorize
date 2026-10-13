<script lang="ts">
  // Empty start: one obvious action. The whole window also accepts dropped photos (App).
  import { t } from '../lib/i18n.svelte';
  import { pickFiles } from '../lib/picker';
  import Button from './ui/Button.svelte';
</script>

<div class="welcome" data-testid="dropzone">
  <svg class="art" viewBox="0 0 220 150" aria-hidden="true">
    <rect x="18" y="26" width="104" height="92" rx="14" class="card back" />
    <rect x="30" y="16" width="104" height="92" rx="14" class="card" />
    <circle cx="62" cy="48" r="10" class="sun" />
    <path d="M40 96l26-28 20 20 14-12 24 20z" class="hill" />
    <path d="M146 62h40" class="arrow" />
    <path d="M176 52l10 10-10 10" class="arrow" />
    <path d="M150 104c14-26 40-26 54 0" class="vec" />
    <circle cx="150" cy="104" r="4" class="node" />
    <circle cx="204" cy="104" r="4" class="node" />
    <circle cx="177" cy="85" r="4" class="node" />
  </svg>
  <h2>{t('addTitle')}</h2>
  <p>{t('addBody')}</p>
  <span data-tour="add">
    <Button variant="primary" size="lg" icon="upload" onclick={pickFiles} data-testid="add-photos">{t('addButton')}</Button>
  </span>
  <span class="muted small">{t('formats')}</span>
</div>

<style>
  .welcome {
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    text-align: center;
    padding: 32px;
    border-radius: var(--radius-lg);
    border: 2px dashed var(--line-strong);
    background:
      radial-gradient(circle at 50% 35%, var(--accent-soft), transparent 60%),
      var(--panel);
    animation: fade-in var(--slow) var(--ease);
  }
  .art {
    width: 220px;
    max-width: 70%;
    margin-bottom: 6px;
    animation: float 5s ease-in-out infinite;
  }
  .card {
    fill: var(--panel);
    stroke: var(--line-strong);
    stroke-width: 2;
  }
  .back {
    fill: var(--panel-2);
  }
  .sun {
    fill: #f6b73c;
  }
  .hill {
    fill: var(--accent);
    opacity: 0.85;
  }
  .arrow {
    fill: none;
    stroke: var(--muted);
    stroke-width: 3;
    stroke-linecap: round;
    stroke-linejoin: round;
  }
  .vec {
    fill: none;
    stroke: var(--accent);
    stroke-width: 3;
  }
  .node {
    fill: var(--panel);
    stroke: var(--accent);
    stroke-width: 2;
  }
  h2 {
    margin: 0;
    font-size: 22px;
  }
  p {
    margin: 0 0 8px;
    max-width: 440px;
    color: var(--muted);
  }
  .small {
    font-size: 12.5px;
  }
  @keyframes float {
    50% {
      transform: translateY(-6px);
    }
  }
</style>
