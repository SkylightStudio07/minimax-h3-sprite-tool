/* Isolated browser regression: mocked API only; never creates production jobs.
 * Run with Playwright available in NODE_PATH: node tools/test_responsive_ui.cjs
 */
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const user = { id: 'ui-test', name: '테스트 팀원', role: 'admin', state: 'approved' };
const out = fs.mkdtempSync(path.join(os.tmpdir(), 'sprite-ui-'));
const files = { '/': 'team.html', '/studio': 'index.html', '/music': 'music.html', '/rigging': 'rigging.html' };
const engine = { comfy: true, modelsReady: true, licenseConfirmed: true, rigging: { comfy: true, modelsReady: true }, music: { ready: true, profile: 'test', gemini: { configured: true, model: 'test', provider: 'vertex' } } };
async function noOverflow(surface, label) {
  const size = await surface.evaluate(() => ({ viewport: document.documentElement.clientWidth, content: document.documentElement.scrollWidth }));
  assert(size.content <= size.viewport + 1, `${label}: horizontal overflow ${JSON.stringify(size)}`);
}
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const context = await browser.newContext();
    let signedIn = false, populated = false;
    const galleryJobs = [
      { id: 'sprite-test', jobType: 'sprite', owner: '테스트', animationType: 'Idle', created: 1700000000, loop: false },
      { id: 'music-test', jobType: 'music', owner: '테스트', animationType: '긴 이름의 게임 사운드트랙', created: 1700000000, audio: '/fixture-audio', vocalMode: 'lyrics', lyrics: 'long-lyric-'.repeat(80), resolvedPrompt: 'A peaceful forest theme.' }
    ];
    const errors = [];
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      assert.equal(url.hostname, 'sprite-lab.test', 'Unexpected external request');
      if (files[url.pathname]) return route.fulfill({ contentType: 'text/html; charset=utf-8', body: fs.readFileSync(path.join(root, 'web', files[url.pathname]), 'utf8') });
      let data;
      if (url.pathname === '/api/me') data = { user: signedIn ? user : null, setupRequired: false };
      else if (url.pathname === '/api/status') data = engine;
      else if (url.pathname === '/api/logout') { signedIn = false; data = {}; }
      else if (url.pathname === '/api/jobs') data = { jobs: [] };
      else if (url.pathname === '/api/users') data = { users: [user] };
      else if (url.pathname === '/api/gallery') { const jobs = populated ? galleryJobs.filter(job => signedIn || job.jobType !== 'music') : []; data = { jobs, page: 1, pages: 1, total: jobs.length }; }
      else return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ error: 'Unmocked endpoint' }) });
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) });
    });
    for (const width of [1440, 1024, 768, 390, 320]) {
      await page.setViewportSize({ width, height: 940 });
      populated = false;
      signedIn = false;
      await page.goto('http://sprite-lab.test/');
      await page.locator('#publicGalleryList .empty').waitFor();
      await noOverflow(page, `${width} guest`);
      await page.locator('#toggleAuth').click();
      assert(await page.locator('#displayName').isVisible());
      await page.locator('#toggleAuth').click();
      if ([1440, 390].includes(width)) await page.screenshot({ path: path.join(out, `landing-${width}.png`), fullPage: true });
      populated = true;
      signedIn = true;
      await page.reload();
      await page.locator('#app').waitFor();
      for (const pane of ['generate', 'music', 'rigging', 'queue', 'gallery', 'guide', 'admin']) {
        await page.locator(`[data-pane="${pane}"]`).click();
        await page.locator(`#${pane}Pane`).waitFor();
        await noOverflow(page, `${width} ${pane} shell`);
        if (pane === 'gallery') {
          await page.locator('#galleryList article').nth(1).waitFor();
          for (const summary of await page.locator('#galleryList summary').all()) await summary.click();
          await noOverflow(page, `${width} populated gallery`);
        }
        const id = { generate: 'studio', music: 'musicStudio', rigging: 'riggingStudio' }[pane];
        if (id) {
          const frame = await (await page.locator(`#${id}`).elementHandle()).contentFrame();
          await frame.locator('html.embedded-studio').waitFor();
          await noOverflow(frame, `${width} ${pane} frame`);
          if (pane === 'music') {
            await frame.locator('[name=mode][value=direct]').check();
            await frame.locator('[data-example]').first().click();
            assert((await frame.locator('#prompt').inputValue()).includes('Instrumental'));
            await frame.locator('#vocalMode').selectOption('lyrics');
            assert(await frame.locator('#lyrics').isVisible());
            await frame.locator('#vocalMode').selectOption('instrumental');
            assert(!(await frame.locator('#lyrics').isVisible()));
            await noOverflow(frame, `${width} direct prompt`);
          }
          await page.waitForFunction(id => {
            const frame = document.getElementById(id);
            return Math.abs(frame.getBoundingClientRect().height - frame.contentDocument.body.getBoundingClientRect().height - 4) < 5;
          }, id);
        }
        if ([1440, 390].includes(width) && ['generate', 'music'].includes(pane)) {
          await page.evaluate(() => window.scrollTo(0, 0));
          await page.screenshot({ path: path.join(out, `${pane}-${width}.png`) });
        }
      }
      await page.locator('#logout').click();
      await page.locator('#auth').waitFor();
      assert.equal(await page.locator('iframe[src]').count(), 0);
      console.log(`PASS ${width}px: guest, 7 panes, embedded height, BGM modes, logout`);
    }
    assert.deepEqual(errors, [], 'Browser JavaScript errors');
    console.log(`Screenshots: ${out}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
