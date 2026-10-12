import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const fixture = (name: string) => fileURLToPath(new URL(`./fixtures/${name}`, import.meta.url));

async function openApp(page: Page) {
  await page.goto('/#t=e2e');
  await expect(page.getByTestId('dropzone')).toBeVisible();
}

async function uploadAndWait(page: Page, name = 'face.png') {
  await page.getByTestId('file-input').setInputFiles(fixture(name));
  const job = page.getByTestId('job').filter({ hasText: name }).last();
  await expect(job).toHaveAttribute('data-status', 'done');
  return job;
}

test.beforeEach(async ({ page, request }) => {
  // start every test from an empty queue
  const res = await request.get('/api/jobs', { headers: { 'X-Token': 'e2e' } });
  for (const j of (await res.json()).jobs) await request.delete(`/api/jobs/${j.id}`, { headers: { 'X-Token': 'e2e' } });
  await page.addInitScript(() => localStorage.clear());
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

test('upload, progress, result, similarity score', async ({ page }) => {
  await openApp(page);
  await uploadAndWait(page);
  await expect(page.getByTestId('svg-image')).toBeVisible();
  await expect(page.getByTestId('score')).toHaveText(/\d+\.\d\d %/);
  const score = parseFloat((await page.getByTestId('score').textContent()) ?? '0');
  expect(score).toBeGreaterThan(95);
});

test('drag and drop anywhere on the window', async ({ page }) => {
  await openApp(page);
  const bytes = readFileSync(fixture('badge.png')).toString('base64');
  await page.evaluate(async (b64) => {
    const bin = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const dt = new DataTransfer();
    dt.items.add(new File([bin], 'dropped.png', { type: 'image/png' }));
    window.dispatchEvent(new DragEvent('dragenter', { dataTransfer: dt, bubbles: true }));
    window.dispatchEvent(new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true }));
  }, bytes);
  await expect(page.getByTestId('job').filter({ hasText: 'dropped.png' })).toHaveAttribute('data-status', 'done');
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
  await page.getByTestId('layer').selectOption('fill');
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

test('preset change and re-process selected image', async ({ page }) => {
  await openApp(page);
  await uploadAndWait(page, 'badge.png');
  await page.getByTestId('preset-logo').check();
  await page.getByTestId('apply-selected').click();
  // the old job is replaced by a new one: wait until the service shows exactly the finished logo job
  await expect
    .poll(async () => {
      const res = await page.request.get('/api/jobs', { headers: { 'X-Token': 'e2e' } });
      return (await res.json()).jobs.map((j: { preset: string; status: string }) => `${j.preset}:${j.status}`);
    })
    .toEqual(['logo:done']);
  await expect(page.getByTestId('job')).toHaveCount(1);
  await expect(page.getByTestId('job').first()).toHaveAttribute('data-status', 'done');
});

test('language switch', async ({ page }) => {
  await openApp(page);
  await page.getByRole('combobox', { name: /language|bahasa/i }).selectOption('id');
  await expect(page.getByTestId('dropzone')).toContainText('Seret gambar');
  await page.getByRole('combobox', { name: /language|bahasa/i }).selectOption('en');
  await expect(page.getByTestId('dropzone')).toContainText('Drop PNG');
});

test('a non-image file is rejected with a message', async ({ page }) => {
  await openApp(page);
  await page.getByTestId('file-input').setInputFiles({ name: 'fake.png', mimeType: 'image/png', buffer: Buffer.from('hello') });
  await expect(page.getByTestId('notice')).toContainText('fake.png');
  await expect(page.getByTestId('job')).toHaveCount(0);
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
