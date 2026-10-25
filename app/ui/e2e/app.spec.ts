import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const fixture = (name: string) => fileURLToPath(new URL(`./fixtures/${name}`, import.meta.url));
const H = { 'X-Token': 'e2e' };

async function openApp(page: Page) {
  await page.goto('/#t=e2e');
  await expect(page.getByTestId('dropzone').or(page.getByTestId('add-more'))).toBeVisible();
}

/** Step 1: put photos on the workbench (nothing is processed yet). */
async function addPhotos(page: Page, names: string[]) {
  await page.getByTestId('file-input').setInputFiles(names.map(fixture));
  for (const n of names) await expect(page.locator(`[data-testid="staged"][data-name="${n}"]`)).toBeVisible();
}

/** Steps 1–3 for one photo, then wait for its result and select it. */
async function uploadAndWait(page: Page, name = 'face.png') {
  await addPhotos(page, [name]);
  await page.getByTestId('process').click();
  const job = page.getByTestId('job').filter({ hasText: name }).last();
  await expect(job).toHaveAttribute('data-status', 'done');
  await job.locator('button.pick').click();
  return job;
}

async function serviceJobs(page: Page): Promise<{ id: string; name: string; status: string; preset: string }[]> {
  const res = await page.request.get('/api/jobs', { headers: H });
  return (await res.json()).jobs;
}

test.beforeEach(async ({ page, request }, info) => {
  // every test starts from an empty service and fresh page storage (once per test, not on reloads)
  const res = await request.get('/api/jobs', { headers: H });
  for (const j of (await res.json()).jobs) await request.delete(`/api/jobs/${j.id}`, { headers: H });
  await request.put('/api/settings', {
    headers: H,
    data: { speed: 'auto', name_pattern: '{name}', size_attrs: false, max_side: 8000, max_staged: 100, ai_accel: 'auto' },
  });
  const showTour = info.title.includes('tour');
  await page.addInitScript((tour) => {
    if (sessionStorage.getItem('e2e-init')) return;
    sessionStorage.setItem('e2e-init', '1');
    localStorage.clear();
    if (!tour) localStorage.setItem('pngsvg.tour.v1', 'done');
  }, showTour);
});

test('token is taken from the fragment and removed from the address bar', async ({ page }) => {
  await openApp(page);
  expect(page.url()).not.toContain('e2e');
});

test('without the session link the page explains what to do', async ({ page, context }) => {
  await context.clearCookies();
  await page.goto('/');
  await page.evaluate(() => sessionStorage.clear());
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('png2svg serve');
});

test('first-run tour: shown once, skippable, available again from Guide', async ({ page }) => {
  await openApp(page);
  const tour = page.getByTestId('tour');
  await expect(tour).toBeVisible();
  await page.getByTestId('tour-next').click();
  await expect(tour.getByRole('dialog')).toContainText('1 · Add photos');
  await page.getByTestId('tour-skip').click();
  await expect(tour).toHaveCount(0);

  await page.reload();
  await expect(page.getByTestId('dropzone')).toBeVisible();
  await expect(tour).toHaveCount(0, { timeout: 2000 });

  await page.getByTestId('tour-open').click();
  await expect(tour).toBeVisible();
  for (let i = 0; i < 4; i++) await page.getByTestId('tour-next').click();
  await page.getByTestId('tour-done').click();
  await expect(tour).toHaveCount(0);

  await page.getByTestId('tour-open').click();
  await page.keyboard.press('Escape');
  await expect(tour).toHaveCount(0);
});

test('photos wait on the workbench; only the ticked ones are processed', async ({ page }) => {
  await openApp(page);
  await addPhotos(page, ['face.png', 'badge.png']);
  await expect(page.getByTestId('picked-count')).toHaveText('2 of 2 selected');
  await page.waitForTimeout(800);
  expect((await serviceJobs(page)).map((j) => j.status)).toEqual(['staged', 'staged']);

  // click the visible custom checkbox, like a user does
  await page.locator('[data-testid="staged"][data-name="badge.png"] .check label').click();
  await expect(page.getByTestId('pick-badge.png')).not.toBeChecked();
  await expect(page.getByTestId('picked-count')).toHaveText('1 of 2 selected');
  await expect(page.getByTestId('process')).toHaveText('Process 1 photo');
  await page.getByTestId('process').click();
  await expect(page.getByTestId('job').filter({ hasText: 'face.png' })).toHaveAttribute('data-status', 'done');
  await expect
    .poll(async () => Object.fromEntries((await serviceJobs(page)).map((j) => [j.name, j.status])))
    .toEqual({ 'face.png': 'done', 'badge.png': 'staged' });

  await page.getByTestId('open-workbench').click();
  await expect(page.locator('[data-testid="staged"][data-name="badge.png"]')).toBeVisible();
  await page.getByTestId('pick-none').click();
  await expect(page.getByTestId('process')).toBeDisabled();
});

test('upload, progress, result, similarity score', async ({ page }) => {
  await openApp(page);
  await uploadAndWait(page);
  await expect(page.getByTestId('svg-image')).toBeVisible();
  await expect(page.getByTestId('score')).toHaveText(/\d+\.\d\d %/);
  const score = parseFloat((await page.getByTestId('score').textContent()) ?? '0');
  expect(score).toBeGreaterThan(95);
  await expect(page.getByTestId('notice').filter({ hasText: 'ready to save' })).toBeVisible();
});

test('drag and drop anywhere on the window puts photos on the workbench', async ({ page }) => {
  await openApp(page);
  const bytes = readFileSync(fixture('badge.png')).toString('base64');
  await page.evaluate(async (b64) => {
    const bin = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const dt = new DataTransfer();
    dt.items.add(new File([bin], 'dropped.png', { type: 'image/png' }));
    window.dispatchEvent(new DragEvent('dragenter', { dataTransfer: dt, bubbles: true }));
    window.dispatchEvent(new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true }));
  }, bytes);
  await expect(page.locator('[data-testid="staged"][data-name="dropped.png"]')).toBeVisible();
});

test('zoom is synchronized, slider and layer views work', async ({ page }) => {
  await openApp(page);
  await uploadAndWait(page);
  const before = await page.getByTestId('zoom').textContent();
  const pane = page.getByTestId('viewport-source');
  const box = (await pane.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.wheel(0, -600);
  await expect(page.getByTestId('zoom')).not.toHaveText(before ?? '');
  const styles = await page.locator('.viewport img').evaluateAll((els) => els.map((e) => (e as HTMLElement).style.width));
  expect(new Set(styles).size).toBe(1); // both panes show the same zoom

  const all = await page.getByTestId('svg-image').getAttribute('src');
  await page.getByTestId('layer-fill').click();
  await expect(page.getByTestId('svg-image')).not.toHaveAttribute('src', all ?? '');

  await page.getByTestId('mode-slider').click();
  await expect(page.getByTestId('slider-handle')).toBeVisible();
  await page.getByTestId('slider-handle').focus();
  await page.keyboard.press('ArrowLeft');
  await expect(page.getByTestId('slider-handle')).toHaveAttribute('aria-valuenow', '48');
});

test('save SVG downloads a file, copy puts SVG on the clipboard', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await openApp(page);
  await uploadAndWait(page);
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByTestId('save-svg').click()]);
  expect(download.suggestedFilename()).toBe('face.svg');
  const [zip] = await Promise.all([page.waitForEvent('download'), page.getByTestId('save-all').click()]);
  expect(zip.suggestedFilename()).toBe('png2svg-results.zip');
  await page.getByTestId('copy-svg').click();
  const text = await page.evaluate(() => navigator.clipboard.readText());
  expect(text.startsWith('<svg')).toBe(true);
});

test('style change and process again', async ({ page }) => {
  await openApp(page);
  await uploadAndWait(page, 'badge.png');
  await page.getByTestId('preset-logo').click();
  await expect(page.getByTestId('preset-logo')).toHaveAttribute('aria-checked', 'true');
  await page.getByTestId('apply-selected').click();
  // the old job is replaced by a new one: wait until the service shows exactly the finished logo job
  await expect
    .poll(async () => (await serviceJobs(page)).map((j) => `${j.preset}:${j.status}`))
    .toEqual(['logo:done']);
  await expect(page.getByTestId('job')).toHaveCount(1);
  await expect(page.getByTestId('job').first()).toHaveAttribute('data-status', 'done');
});

test('fine-tune controls are custom and keyboard operable', async ({ page }) => {
  await openApp(page);
  await page.getByTestId('advanced-toggle').click();
  const slider = page.getByTestId('opt-tolerance');
  const start = Number(await slider.getAttribute('aria-valuenow'));
  await slider.focus();
  await page.keyboard.press('ArrowRight');
  await expect(slider).toHaveAttribute('aria-valuenow', String(Number((start + 0.05).toFixed(4))));
  const sw = page.getByTestId('opt-outlines');
  const was = await sw.getAttribute('aria-checked');
  await sw.click();
  await expect(sw).not.toHaveAttribute('aria-checked', was ?? '');
});

test('processing speed is a setting of the service', async ({ page }) => {
  await openApp(page);
  await page.getByTestId('speed-saver').click();
  await expect(page.getByTestId('speed-saver')).toHaveAttribute('aria-checked', 'true');
  await expect(page.getByTestId('speed-help')).toContainText('One photo at a time');
  const s = await (await page.request.get('/api/settings', { headers: H })).json();
  expect(s.speed).toBe('saver');
  await page.getByTestId('speed-auto').click();
  await expect(page.getByTestId('speed-help')).toContainText('Picked for this computer');
});

test('stop all asks first, then empties the queue', async ({ page }) => {
  await openApp(page);
  await addPhotos(page, ['face-large.webp', 'face.png', 'badge.png']);
  await page.getByTestId('process').click();
  await page.getByTestId('stop-all').click();
  await expect(page.getByRole('alertdialog')).toBeVisible();
  await page.getByTestId('dialog-confirm').click();
  await expect(page.getByRole('alertdialog')).toHaveCount(0);
  await expect
    .poll(async () => (await serviceJobs(page)).every((j) => j.status === 'cancelled' || j.status === 'done'))
    .toBe(true);
});

test('removing a result can be undone; otherwise it is deleted', async ({ page }) => {
  await openApp(page);
  await uploadAndWait(page);
  const row = page.getByTestId('job').filter({ hasText: 'face.png' });
  await row.getByRole('button', { name: 'Remove' }).click();
  await expect(row).toHaveCount(0);
  await page.getByTestId('notice').getByRole('button', { name: 'Undo' }).click();
  await expect(row).toHaveCount(1);
  await page.waitForTimeout(5600);
  expect((await serviceJobs(page)).length).toBe(1);

  await row.getByRole('button', { name: 'Remove' }).click();
  await expect.poll(async () => (await serviceJobs(page)).length, { timeout: 10_000 }).toBe(0);
});

test('language switch (custom dropdown)', async ({ page }) => {
  await openApp(page);
  await page.getByRole('combobox', { name: /language|bahasa/i }).click();
  await page.getByTestId('lang-id').click();
  await expect(page.getByTestId('dropzone')).toContainText('Tambahkan foto');
  const lang = page.getByRole('combobox', { name: /language|bahasa/i });
  await lang.focus();
  await page.keyboard.press('ArrowDown');
  await expect(page.getByRole('listbox')).toBeVisible();
  await page.keyboard.press('Home');
  await expect(page.getByTestId('lang-en')).toHaveClass(/active/);
  await page.keyboard.press('Enter');
  await expect(page.getByRole('listbox')).toHaveCount(0);
  await expect(page.getByTestId('dropzone')).toContainText('Add photos');
});

test('a non-image file is rejected with a plain-language message', async ({ page }) => {
  await openApp(page);
  await page.getByTestId('file-input').setInputFiles({ name: 'fake.png', mimeType: 'image/png', buffer: Buffer.from('hello') });
  await expect(page.getByTestId('notice')).toContainText('“fake.png” is not a PNG, WebP or JPEG photo');
  await expect(page.getByTestId('staged')).toHaveCount(0);
});

test('a session link pasted into an open tab is picked up (fragment change reloads)', async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => sessionStorage.clear());
  await page.reload();
  await expect(page.getByRole('alert')).toBeVisible();
  await page.evaluate(() => (location.hash = '#t=e2e'));
  await expect(page.getByTestId('dropzone')).toBeVisible();
});

test('the image stays fitted when the window is resized, until the user zooms', async ({ page }) => {
  await openApp(page);
  await uploadAndWait(page);
  const fits = async () =>
    page.getByTestId('viewport-source').evaluate((vp) => {
      const img = vp.querySelector('img') as HTMLElement;
      const r = Math.max(img.offsetWidth / vp.clientWidth, img.offsetHeight / vp.clientHeight);
      return r > 0.9 && r <= 1.0;
    });
  await expect.poll(fits).toBe(true);
  await page.setViewportSize({ width: 900, height: 700 });
  await expect.poll(fits).toBe(true);
});


// -- M8: Settings ------------------------------------------------------------------------------------------------

async function openSettings(page: Page, section?: string) {
  await page.getByTestId('settings-open').click();
  await expect(page.getByTestId('settings-dialog')).toBeVisible();
  if (section) await page.getByTestId(`nav-${section}`).click();
}

test('settings open from the gear and Ctrl+comma, Esc closes', async ({ page }) => {
  await openApp(page);
  await openSettings(page);
  await page.keyboard.press('Escape');
  await expect(page.getByTestId('settings-dialog')).toHaveCount(0);
  await page.keyboard.press('Control+Comma');
  await expect(page.getByTestId('settings-dialog')).toBeVisible();
  await page.getByTestId('nav-appearance').focus();
  await page.keyboard.press('ArrowDown');
  await expect(page.getByTestId('nav-processing')).toHaveAttribute('aria-selected', 'true');
  await page.getByTestId('settings-close').click();
  await expect(page.getByTestId('settings-dialog')).toHaveCount(0);
});

test('themes: three to choose from, "match system" follows light and dark, remembered', async ({ page }) => {
  const html = page.locator('html');
  await page.emulateMedia({ colorScheme: 'light' });
  await openApp(page);
  await expect(html).toHaveAttribute('data-theme', 'paper');
  await page.emulateMedia({ colorScheme: 'dark' });
  await expect(html).toHaveAttribute('data-theme', 'lightbox');

  await openSettings(page);
  for (const th of ['paper', 'lightbox', 'blueprint']) {
    await page.getByTestId(`theme-${th}`).click();
    await expect(html).toHaveAttribute('data-theme', th);
    await expect(page.getByTestId(`theme-${th}`)).toHaveAttribute('aria-checked', 'true');
  }
  const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(bg).toBe('rgb(14, 42, 68)'); // blueprint --bg
  await page.reload();
  await expect(html).toHaveAttribute('data-theme', 'blueprint');
});

test('density, text size and animation preferences apply to the whole app', async ({ page }) => {
  await openApp(page);
  await openSettings(page);
  await page.getByTestId('density-compact').click();
  await expect(page.locator('html')).toHaveAttribute('data-density', 'compact');
  await page.getByTestId('text-size-1.3').click();
  const size = await page.evaluate(() => getComputedStyle(document.body).fontSize);
  expect(size).toBe('18.2px'); // 14 px × 1.3
  await page.getByTestId('motion-reduce').click();
  await expect(page.locator('html')).toHaveAttribute('data-motion', 'reduce');
  const t = await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--medium').trim());
  expect(t).toBe('1ms');
});

test('language can be changed in Settings; every language file is offered', async ({ page }) => {
  await openApp(page);
  await openSettings(page);
  await page.getByTestId('settings-lang').click();
  await expect(page.getByRole('option')).toHaveCount(2);
  await page.getByTestId('settings-lang-id').click();
  await expect(page.getByTestId('settings-dialog')).toContainText('Tampilan');
  await expect(page.getByTestId('nav-output')).toContainText('Hasil');
});

test('results: file name pattern, size attributes and precision shape the saved SVG', async ({ page }) => {
  await openApp(page);
  await openSettings(page, 'output');
  const field = page.getByTestId('name-pattern');
  await field.fill('{name}-{style}');
  await expect(page.getByTestId('name-preview')).toHaveText('Example: kucing-cartoon.svg');
  await field.press('Enter');
  await page.getByTestId('size-attrs').click();
  await page.getByTestId('decimals-0').click();
  await expect(page.getByTestId('save-dir')).toHaveCount(0); // web mode: desktop-only note instead
  await expect(page.getByTestId('settings-dialog')).toContainText('Available in the desktop app');
  await page.keyboard.press('Escape');

  await uploadAndWait(page);
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByTestId('save-svg').click()]);
  expect(download.suggestedFilename()).toBe('face-cartoon.svg');
  const svg = readFileSync(await download.path(), 'utf8');
  expect(svg.startsWith('<svg width="')).toBe(true);
  const d = [...svg.matchAll(/ d="([^"]+)"/g)].map((m) => m[1]).join(' ');
  expect(d).not.toContain('.');

  await openSettings(page, 'output');
  await page.getByTestId('name-pattern').fill('');
  await page.getByTestId('name-pattern').press('Enter');
  await expect(page.getByTestId('name-pattern')).toHaveAttribute('aria-invalid', 'true');
});

test('processing limits are sent to the service', async ({ page }) => {
  await openApp(page);
  await openSettings(page, 'processing');
  await page.getByTestId('max-staged-25').click();
  await page.getByTestId('max-side-4000').click();
  await expect
    .poll(async () => {
      const s = await (await page.request.get('/api/settings', { headers: H })).json();
      return `${s.max_staged}/${s.max_side}`;
    })
    .toBe('25/4000');
  await page.reload();
  // a fresh page pushes the saved preferences again (as after a desktop restart)
  await request_settings_reset(page);
  await page.reload();
  await expect
    .poll(async () => (await (await page.request.get('/api/settings', { headers: H })).json()).max_staged)
    .toBe(25);
});

async function request_settings_reset(page: Page) {
  await page.request.put('/api/settings', { headers: H, data: { max_staged: 100, max_side: 8000 } });
}

test('about shows the version; the guide can be replayed from Settings', async ({ page }) => {
  await openApp(page);
  const health = await (await page.request.get('/api/health', { headers: H })).json();
  await openSettings(page, 'about');
  await expect(page.getByTestId('version')).toHaveText(health.version);
  await expect(page.getByTestId('check-updates')).toBeVisible(); // not clicked: no network in tests
  await page.getByTestId('nav-appearance').click();
  await page.getByTestId('replay-tour').click();
  await expect(page.getByTestId('tour')).toBeVisible();
});

// -- M9: optional AI step ----------------------------------------------------------------------------------------
// The service runs with the real ONNX runtime but no model; nothing is downloaded in tests. The "installed" state is
// shown by answering /api/ai in the page, the service itself still refuses AI jobs without the model.

test('AI: model cards offer a download (nothing fetched until clicked), the accelerator is a service setting', async ({ page }) => {
  await openApp(page);
  await expect(page.getByTestId('ai-needs-model')).toBeVisible();
  await openSettings(page, 'processing');
  for (const name of ['illustration', 'general']) {
    const card = page.getByTestId(`ai-model-${name}`);
    await expect(card).toHaveAttribute('data-state', 'missing');
    await expect(page.getByTestId(`ai-download-${name}`)).toContainText('MB');
  }
  await expect(page.getByTestId('ai-gpu')).not.toBeEmpty();
  await page.getByTestId('ai-model-general').getByRole('radio').click();
  await expect(page.getByTestId('ai-model-general')).toHaveClass(/on/);
  await page.getByTestId('ai-accel-cpu').click();
  await expect
    .poll(async () => (await (await page.request.get('/api/settings', { headers: H })).json()).ai_accel)
    .toBe('cpu');
});

test('AI: with a model installed, the style panel offers Off/Automatic/Always and processing asks for it', async ({ page }) => {
  await page.route('**/api/ai', async (route) => {
    const res = await route.fetch();
    const body = await res.json();
    body.models = body.models.map((m: { name: string }) =>
      m.name === 'illustration' ? { ...m, state: 'installed', progress: 1 } : m,
    );
    await route.fulfill({ response: res, json: body });
  });
  await openApp(page);
  const mode = page.getByTestId('ai-mode');
  await expect(mode).toBeVisible();
  await expect(page.getByTestId('ai-mode-auto')).toHaveAttribute('aria-checked', 'true');
  await page.getByTestId('ai-mode-always').click();

  await addPhotos(page, ['face.png']);
  const start = page.waitForRequest((r) => r.url().endsWith('/api/jobs/start'));
  await page.getByTestId('process').click();
  const sent = (await start).postDataJSON();
  expect(sent.options.ai).toBe('illustration');
  expect(sent.options.ai_auto).toBeUndefined();
  // the real service has no model file, so it refuses in plain words instead of running without AI
  await expect(page.getByText(/Download an AI model|Unduh model AI/).first()).toBeVisible();

  await page.getByTestId('ai-mode-off').click();
  await page.reload();
  await expect(page.getByTestId('ai-mode-off')).toHaveAttribute('aria-checked', 'true');
});

test('AI: a finished job shows whether AI was used', async ({ page }) => {
  await openApp(page);
  await uploadAndWait(page);
  await expect(page.getByTestId('stat-ai')).toHaveText(/No|Tidak/);
});

// -- M10: studio features ----------------------------------------------------------------------------------------

async function serviceJob(page: Page): Promise<{ options: Record<string, unknown>; status: string }> {
  const res = await page.request.get('/api/jobs', { headers: H });
  const jobs = (await res.json()).jobs;
  return jobs[jobs.length - 1];
}

test('studio: colors, transparent background and cut-out shapes reach the service; a palette can be locked and edited', async ({ page }) => {
  await openApp(page);
  await page.getByTestId('advanced-toggle').click();
  await page.getByTestId('opt-max_colors').click();
  await page.getByTestId('opt-max_colors-4').click();
  await page.getByTestId('opt-remove_bg').click();
  await page.getByTestId('opt-layout-cutout').click();
  await uploadAndWait(page, 'badge.png');
  expect((await serviceJob(page)).options).toMatchObject({ max_colors: 4, remove_bg: true, layout: 'cutout' });

  const swatches = page.getByTestId('result-palette').locator('i');
  const n = await swatches.count();
  expect(n).toBeGreaterThan(1);
  expect(n).toBeLessThanOrEqual(4);
  await page.getByTestId('use-palette').click();
  await expect(page.getByTestId('palette-color')).toHaveCount(n);
  await expect(page.getByTestId('opt-max_colors')).toHaveCount(0);
  await page.getByTestId('palette-color').first().hover();
  await page.getByRole('button', { name: /Remove this color/ }).first().click();
  await expect(page.getByTestId('palette-color')).toHaveCount(n - 1);
  await page.getByTestId('apply-selected').click();
  await expect.poll(async () => (await serviceJob(page)).status).toBe('done');
  const palette = (await serviceJob(page)).options.palette;
  expect(Array.isArray(palette) && palette.length).toBe(n - 1);

  await page.getByTestId('opt-color_mode-bw').click();
  await expect(page.getByTestId('opt-threshold')).toBeVisible();
  await expect(page.getByTestId('palette-editor')).toHaveCount(0);
});

test('export: PDF, EPS, DXF and a PNG rendered at 2x', async ({ page }) => {
  await openApp(page);
  await uploadAndWait(page);
  for (const f of ['pdf', 'eps', 'dxf']) {
    await page.getByTestId(`export-format-${f}`).click();
    await expect(page.getByTestId('save-svg')).toContainText(f.toUpperCase());
    const [download] = await Promise.all([page.waitForEvent('download'), page.getByTestId('save-svg').click()]);
    expect(download.suggestedFilename()).toBe(`face.${f}`);
  }
  const [zip] = await Promise.all([page.waitForEvent('download'), page.getByTestId('save-all').click()]);
  expect(zip.suggestedFilename()).toBe('png2svg-results.zip');

  await page.getByTestId('export-format-png').click();
  await page.getByTestId('png-scale-2').click();
  await expect(page.getByTestId('save-all')).toBeDisabled();
  const [png] = await Promise.all([page.waitForEvent('download'), page.getByTestId('save-svg').click()]);
  expect(png.suggestedFilename()).toBe('face.png');
  const bytes = readFileSync(await png.path());
  const job = (await serviceJobs(page))[0];
  const res = await page.request.get(`/api/jobs/${job.id}`, { headers: H });
  const { width, height } = await res.json();
  expect([bytes.readUInt32BE(16), bytes.readUInt32BE(20)]).toEqual([width * 2, height * 2]);
});

test('paste: a picture on the clipboard goes on the workbench (Ctrl+V)', async ({ page }) => {
  await openApp(page);
  const data = readFileSync(fixture('badge.png')).toString('base64');
  await page.evaluate((b64) => {
    const bin = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const dt = new DataTransfer();
    dt.items.add(new File([bin], 'image.png', { type: 'image/png' }));
    window.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt }));
  }, data);
  await expect(page.locator('[data-testid="staged"][data-name^="pasted-"]')).toBeVisible();
});

test('profiles: save a style, apply it again, export and import a file', async ({ page }) => {
  await openApp(page);
  await page.getByTestId('preset-logo').click();
  await page.getByTestId('advanced-toggle').click();
  await page.getByTestId('opt-layout-cutout').click();
  await page.getByTestId('profile-new').click();
  await page.getByTestId('profile-name').fill('Brand');
  await page.getByTestId('profile-save').click();
  await expect(page.getByTestId('profile-select')).toContainText('Brand');

  await page.getByTestId('preset-cartoon').click();
  await expect(page.getByTestId('profile-select')).not.toContainText('Brand');
  await page.getByTestId('profile-select').click();
  await page.getByTestId('profile-select-Brand').click();
  await expect(page.getByTestId('preset-logo')).toHaveAttribute('aria-checked', 'true');
  await expect(page.getByTestId('opt-layout-cutout')).toHaveAttribute('aria-checked', 'true');

  const [file] = await Promise.all([page.waitForEvent('download'), page.getByTestId('profile-export').click()]);
  expect(file.suggestedFilename()).toBe('Brand.pngsvg-profile.json');
  const saved = JSON.parse(readFileSync(await file.path(), 'utf-8'));
  expect(saved).toMatchObject({ format: 'pngsvg-profile', version: 1, preset: 'logo', options: { layout: 'cutout' } });

  saved.name = 'Team';
  saved.options = { max_colors: 3 };
  await page.getByTestId('profile-file').setInputFiles({ name: 'team.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(saved)) });
  await expect(page.getByTestId('profile-select')).toContainText('Team');
  await page.getByTestId('profile-file').setInputFiles({ name: 'bad.json', mimeType: 'application/json', buffer: Buffer.from('{"format":"x"}') });
  await expect(page.getByText(/not a valid style profile/)).toBeVisible();
});
