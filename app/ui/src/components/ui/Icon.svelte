<script lang="ts" module>
  // Simple 24×24 stroke icons drawn for this app (no external icon font or library).
  export const ICONS = {
    plus: 'M12 5v14M5 12h14',
    upload: 'M12 15V4m0 0-4 4m4-4 4 4M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3',
    check: 'M5 12.5 10 17 19 7',
    x: 'M6 6l12 12M18 6 6 18',
    trash: 'M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3',
    play: 'M8 5v14l11-7z',
    stop: 'M7 7h10v10H7z',
    retry: 'M4 12a8 8 0 1 0 2.3-5.6M4 4v4h4',
    help: 'M9.1 9a3 3 0 0 1 5.8 1c0 2-3 2.5-3 4.5M12 18h.01M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z',
    download: 'M12 4v11m0 0-4-4m4 4 4-4M4 19h16',
    copy: 'M9 9h10v11H9zM5 15V4h10',
    zoomIn: 'M11 8v6M8 11h6M20 20l-4.3-4.3M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z',
    zoomOut: 'M8 11h6M20 20l-4.3-4.3M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z',
    fit: 'M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5',
    image: 'M4 5h16v14H4zM4 16l5-5 4 4 3-3 4 4M15 9h.01',
    gauge: 'M12 14l4-4M4 18a9 9 0 1 1 16 0',
    chevronDown: 'M6 9l6 6 6-6',
    chevronLeft: 'M15 6l-6 6 6 6',
    chevronRight: 'M9 6l6 6-6 6',
    info: 'M12 16v-5M12 8h.01M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z',
    warning: 'M12 9v4M12 17h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z',
    sparkles: 'M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8zM19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z',
    globe: 'M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20zM2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20',
    lock: 'M6 11h12v10H6zM8 11V7a4 4 0 0 1 8 0v4',
    sliders: 'M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0M14 4v4M8 10v4M16 16v4',
    layers: 'M12 3 2 8l10 5 10-5zM2 13l10 5 10-5',
  } as const;
  export type IconName = keyof typeof ICONS;
</script>

<script lang="ts">
  let { name, size = 18, stroke = 1.8, label }: { name: IconName; size?: number; stroke?: number; label?: string } =
    $props();
  const filled = $derived(name === 'play' || name === 'stop');
</script>

<svg
  viewBox="0 0 24 24"
  width={size}
  height={size}
  fill={filled ? 'currentColor' : 'none'}
  stroke="currentColor"
  stroke-width={stroke}
  stroke-linecap="round"
  stroke-linejoin="round"
  role={label ? 'img' : undefined}
  aria-label={label}
  aria-hidden={label ? undefined : 'true'}
  focusable="false"
>
  <path d={ICONS[name]} />
</svg>

<style>
  svg {
    flex: none;
    display: block;
  }
</style>
