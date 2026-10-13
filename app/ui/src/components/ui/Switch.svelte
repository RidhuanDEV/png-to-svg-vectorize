<script lang="ts">
  let {
    checked,
    label,
    onchange,
    testid,
  }: { checked: boolean; label: string; onchange: (v: boolean) => void; testid?: string } = $props();
</script>

<button
  type="button"
  role="switch"
  aria-checked={checked}
  class="sw"
  class:on={checked}
  onclick={() => onchange(!checked)}
  data-testid={testid}
>
  <span class="text">{label}</span>
  <span class="track" aria-hidden="true"><span class="thumb"></span></span>
</button>

<style>
  .sw {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    width: 100%;
    padding: 6px 2px;
    border: 0;
    background: none;
    text-align: left;
    border-radius: var(--radius-sm);
  }
  .track {
    width: 40px;
    height: 24px;
    border-radius: 999px;
    background: var(--panel-3);
    border: 1px solid var(--line-strong);
    position: relative;
    flex: none;
    transition: background var(--medium) var(--ease), border-color var(--medium) var(--ease);
  }
  .thumb {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: var(--panel);
    box-shadow: var(--shadow);
    transition: transform var(--medium) var(--spring);
  }
  .on .track {
    background: var(--accent);
    border-color: var(--accent);
  }
  .on .thumb {
    transform: translateX(16px);
  }
</style>
