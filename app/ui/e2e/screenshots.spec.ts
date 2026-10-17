// Documentation screenshots (docs/images). Not part of the normal test run:
//     SCREENSHOTS=1 npx playwright test e2e/screenshots.spec.ts
import { expect, test, type Page } from '@playwright/test';
import { fileURLToPath } from 'node:url';

const OUT = fileURLToPath(new URL('../../../docs/images/', import.meta.url));
const fixture = (name: string) => fileURLToPath(new URL(`./fixtures/${name}`, import.meta.url));
const H = { 'X-Token': 'e2e' };

test.skip(!process.env.SCREENSHOTS, 'set SCREENSHOTS=1 to refresh the documentation screenshots');
test.use({ viewport: { width: 1360, height: 820 }, deviceScaleFactor: 1 });

test.beforeEach(async ({ request }) => {
  const res = await request.get('/api/jobs', { headers: H });
  for (const j of (await res.json()).jobs) await request.delete(`/api/jobs/${j.id}`, { headers: H });
  await request.put('/api/settings', { headers: H, data: { speed: 'auto' } });
});

async function open(page: Page, lang: 'en' | 'id', tour = false, theme = 'system') {
  await page.addInitScript(
    ([l, t, th]) => {
      localStorage.clear();
      localStorage.setItem('pngsvg.lang', l as string);
      localStorage.setItem('pngsvg.prefs', JSON.stringify({ theme: th }));
      if (!t) localStorage.setItem('pngsvg.tour.v1', 'done');
    },
    [lang, tour, theme] as const,
  );
  await page.goto('/#t=e2e');
}

async function stage(page: Page) {
  await page.getByTestId('file-input').setInputFiles([fixture('face-large.webp'), fixture('badge.png'), fixture('face.png')]);
  await expect(page.getByTestId('staged')).toHaveCount(3);
}

async function results(page: Page) {
  await stage(page);
  await page.getByTestId('process').click();
  await expect(page.getByTestId('job')).toHaveCount(3);
  for (const job of await page.getByTestId('job').all()) await expect(job).toHaveAttribute('data-status', 'done');
  await page.getByTestId('job').filter({ hasText: 'face-large.webp' }).locator('button.pick').click();
  await expect(page.getByTestId('score')).toHaveText(/\d+\.\d\d %/);
  await page.waitForTimeout(5000); // let the toasts fade
}

test('welcome with the guide (light, English)', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' });
  await open(page, 'en', true);
  await page.getByTestId('tour-next').click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: `${OUT}app-tour.png` });
});

test('workbench (blueprint, Indonesian)', async ({ page }) => {
  await open(page, 'id', false, 'blueprint');
  await stage(page);
  await page.locator('[data-testid="staged"][data-name="face.png"] .check label').click();
  await page.waitForTimeout(5000);
  await page.screenshot({ path: `${OUT}app-workbench.png` });
});

test('overview (light, English)', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' });
  await open(page, 'en');
  await results(page);
  await page.screenshot({ path: `${OUT}app-overview.png` });
});

test('slider, zoomed (dark, Indonesian)', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await open(page, 'id');
  await results(page);
  await page.getByTestId('mode-slider').click();
  const vp = page.getByTestId('viewport-slider');
  const box = (await vp.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.55);
  await page.mouse.wheel(0, -500);
  await page.screenshot({ path: `${OUT}app-slider-dark.png` });
});

test('settings (paper, Indonesian)', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' });
  await open(page, 'id');
  await page.getByTestId('settings-open').click();
  await page.waitForTimeout(600);
  await page.screenshot({ path: `${OUT}app-settings.png` });
});
