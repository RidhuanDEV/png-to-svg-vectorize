// Documentation screenshots (docs/images). Not part of the normal test run:
//     SCREENSHOTS=1 npx playwright test e2e/screenshots.spec.ts
import { expect, test } from '@playwright/test';
import { fileURLToPath } from 'node:url';

const OUT = fileURLToPath(new URL('../../../docs/images/', import.meta.url));
const fixture = (name: string) => fileURLToPath(new URL(`./fixtures/${name}`, import.meta.url));

test.skip(!process.env.SCREENSHOTS, 'set SCREENSHOTS=1 to refresh the documentation screenshots');
test.use({ viewport: { width: 1360, height: 820 }, deviceScaleFactor: 1 });

test.beforeEach(async ({ request, page }) => {
  const res = await request.get('/api/jobs', { headers: { 'X-Token': 'e2e' } });
  for (const j of (await res.json()).jobs) await request.delete(`/api/jobs/${j.id}`, { headers: { 'X-Token': 'e2e' } });
  await page.addInitScript(() => localStorage.clear());
});

async function load(page: import('@playwright/test').Page, lang: 'en' | 'id') {
  await page.addInitScript((l) => localStorage.setItem('pngsvg.lang', l), lang);
  await page.goto('/#t=e2e');
  await page.getByTestId('file-input').setInputFiles([fixture('face-large.webp'), fixture('badge.png')]);
  await expect(page.getByTestId('job')).toHaveCount(2);
  for (const job of await page.getByTestId('job').all()) await expect(job).toHaveAttribute('data-status', 'done');
  await page.getByTestId('job').first().locator('button.pick').click();
  await expect(page.getByTestId('score')).toHaveText(/\d+\.\d\d %/);
}

test('overview (light, English)', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'light' });
  await load(page, 'en');
  await page.screenshot({ path: `${OUT}app-overview.png` });
});

test('slider, zoomed (dark, Indonesian)', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await load(page, 'id');
  await page.getByTestId('mode-slider').click();
  const vp = page.getByTestId('viewport-slider');
  const box = (await vp.boundingBox())!;
  await page.mouse.move(box.x + box.width * 0.5, box.y + box.height * 0.55);
  await page.mouse.wheel(0, -500);
  await page.screenshot({ path: `${OUT}app-slider-dark.png` });
});
