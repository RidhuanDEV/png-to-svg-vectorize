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
  await request.put('/api/settings', { headers: H, data: { speed: 'auto' } });
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
