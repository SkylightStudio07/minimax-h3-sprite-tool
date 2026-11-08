/* Isolated browser regression: mocked API only; never creates production jobs.
 * Run with Playwright available in NODE_PATH: node tools/test_responsive_ui.cjs
 */
const { chromium } = require('playwright');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const user = { id: 'ui-test', username: 'ui-test', name: '테스트 팀원', role: 'admin', state: 'approved' };
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
    let signedIn = false, populated = false, jobState = 'generating';
    let shares = [{ token: 'tok1', jobId: 'rig-test', created: 1700000000, url: '/share/rig/tok1', title: null, composite: '/fixture-rig', rigRevision: 0 }];
    const myJob = () => ({ id: 'run-1', jobType: 'video', userId: 'ui-test', owner: '테스트 팀원', animationType: 'Idle', width: 832, height: 1216, created: 1700000000, state: jobState });
    const galleryJobs = [
      { id: 'sprite-test', jobType: 'video', owner: '테스트', userId: 'ui-test', animationType: 'idle', created: 1700000000, loop: false, video: '/fixture-video', spriteSheet: '/fixture-sheet', settings: { subjectType: 'human', animationType: 'idle', duration: 3, frameCount: 16, prompt: '숨을 고르며 망토가 흔들린다' } },
      { id: 'rig-test', jobType: 'rigging', owner: '테스트', userId: 'ui-test', animationType: '2D 리깅', created: 1700000000, rigRevision: 0, composite: '/fixture-rig', psd: '/fixture-psd', package: '/fixture-v1', packageV2: '/fixture-v2' },
      { id: 'music-test', jobType: 'music', owner: '테스트', animationType: '긴 이름의 게임 사운드트랙', created: 1700000000, audio: '/fixture-audio', vocalMode: 'lyrics', lyrics: 'long-lyric-'.repeat(80), resolvedPrompt: 'A peaceful forest theme.' }
    ];
    const errors = [];
    // Sidebar links live in an off-canvas drawer below 900px; open it first when needed.
    async function openMenuIfNeeded(target) {
      if (!(await target.isVisible())) { await page.locator('#menuToggle').click(); await target.waitFor(); }
    }
    async function go(pane) {
      const link = page.locator(`#sideNav [data-pane="${pane}"]`);
      await openMenuIfNeeded(link);
      await link.click();
    }
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      assert.equal(url.hostname, 'sprite-lab.test', 'Unexpected external request');
      if (/^\/live2d\/[^/]+\/player$/.test(url.pathname)) {
        assert.equal(url.searchParams.get('obs'), '1', 'Hero player runs in OBS mode');
        return route.fulfill({ contentType: 'text/html; charset=utf-8', body: `<!doctype html><html><body style="margin:0"><div id="drop"></div><canvas id="cv" width="300" height="400" style="width:100%;height:100%"></canvas><button id="tgMouse" class="tg"></button><button id="btnPause"></button><script>window.moves=0;window.paused=false;document.getElementById('cv').addEventListener('mousemove',()=>window.moves++);document.getElementById('tgMouse').addEventListener('click',e=>e.target.classList.toggle('on'));document.getElementById('btnPause').addEventListener('click',()=>{window.paused=!window.paused});setTimeout(()=>document.getElementById('drop').classList.add('hidden'),200)</script></body></html>` });
      }
      if (files[url.pathname]) return route.fulfill({ contentType: 'text/html; charset=utf-8', body: fs.readFileSync(path.join(root, 'web', files[url.pathname]), 'utf8') });
      if (url.pathname.startsWith('/assets/')) {
        const assets = path.join(root, 'web', 'assets'), file = path.resolve(assets, '.' + decodeURIComponent(url.pathname.slice(7)));
        assert(file.startsWith(assets + path.sep) && fs.existsSync(file), `Missing asset ${url.pathname}`);
        const types = { '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.woff2': 'font/woff2', '.svg': 'image/svg+xml' };
        return route.fulfill({ contentType: types[path.extname(file)] || 'application/octet-stream', body: fs.readFileSync(file) });
      }
      let data;
      const body = request.method() === 'POST' ? request.postDataJSON() : null;
      if (url.pathname === '/api/me') data = { user: signedIn ? user : null, setupRequired: false };
      else if (url.pathname === '/api/public-live2d') data = { items: ['pub1', 'pub2'].map((token, index) => ({ token, title: index ? '아리스' : '유키노', url: `/live2d/${token}`, preview: `/live2d/${token}/preview.png`, updated: 1700000000 })) };
      else if (url.pathname === '/api/me/summary') data = { counts: { video: 1, rigging: 1, music: 0 }, active: 1, activeLimit: 3, shares, publicLive2d: [] };
      else if (url.pathname === '/api/me/profile') { user.name = body.name; data = { user }; }
      else if (url.pathname === '/api/me/password') { if (body.currentPassword !== 'current-password') return route.fulfill({ status: 403, contentType: 'application/json', body: JSON.stringify({ error: '현재 비밀번호가 맞지 않습니다.' }) }); data = { ok: true }; }
      else if (url.pathname === '/api/shares/tok1/revoke') { shares = []; data = { ok: true }; }
      else if (url.pathname === '/api/jobs/rig-test/title') { galleryJobs[1].title = body.title || null; data = { title: body.title || null }; }
      else if (url.pathname === '/api/status') data = engine;
      else if (url.pathname === '/api/logout') { signedIn = false; data = {}; }
      else if (url.pathname === '/api/jobs') data = { jobs: populated && signedIn ? [myJob()] : [] };
      else if (url.pathname === '/api/users') data = { users: [user] };
      else if (url.pathname.startsWith('/api/gallery/')) { const job = galleryJobs.find(item => item.id === decodeURIComponent(url.pathname.slice(13))); if (!job) return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ error: '결과를 찾을 수 없습니다.' }) }); data = { job: { settings: {}, ...job } }; }
      else if (url.pathname === '/api/gallery') { const jobs = populated ? galleryJobs.filter(job => signedIn || job.jobType !== 'music') : []; data = { jobs, page: 1, pages: 1, total: jobs.length }; }
      else return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ error: 'Unmocked endpoint' }) });
      return route.fulfill({ contentType: 'application/json', body: JSON.stringify(data) });
    });
    for (const width of [1440, 1024, 768, 390, 320]) {
      await page.setViewportSize({ width, height: 940 });
      populated = false;
      signedIn = false;
      await page.goto('http://sprite-lab.test/');
      await page.evaluate(() => localStorage.setItem('sprite-theme', 'light'));
      await page.reload();
      await page.locator('#publicGalleryList .empty').waitFor();
      // Hero: the public character goes live and follows the mouse; it pauses off screen.
      await page.locator('#heroStage.is-live').waitFor();
      assert.equal(await page.locator('#heroStage .l-loading').evaluate(el => getComputedStyle(el).getPropertyValue('--p').trim()), '100.0%', 'Loading bar completes when the character goes live');
      const hero = await (await page.locator('#heroPlayer').elementHandle()).contentFrame();
      assert(await hero.locator('#tgMouse.on').count(), 'Mouse look is switched on');
      await page.mouse.move(width * .2, 200); await page.mouse.move(width * .8, 300);
      await page.waitForFunction(() => document.getElementById('heroPlayer').contentWindow.moves > 0);
      assert.equal(await page.locator('#heroDots button').count(), 2);
      assert.equal(await page.locator('#charThumbs button').count(), 2);
      await page.locator('#charThumbs button').nth(1).click();
      assert.equal(await page.locator('#charName').textContent(), '아리스');
      if (width >= 1024) {
        await page.locator('#tools').scrollIntoViewIfNeeded();
        // Cards follow the pipeline: 캐릭터 원화 → 스프라이트 → 2D 리깅 → BGM.
        assert.equal(await page.locator('#toolImage').getAttribute('aria-current'), 'true');
        assert.equal(await page.locator('#toolImageMedia img').count(), 4, 'one character in four styles');
        assert.equal(await page.locator('#toolDots button').count(), 4);
        await page.locator('#toolNext').click();
        assert.equal(await page.locator('.l-tool').nth(1).getAttribute('aria-current'), 'true');
        await page.locator('#toolNext').click();
        // The rigging card plays a small live character once it is the centred card.
        await page.locator('#toolRigMedia.is-live').waitFor();
        assert.equal(await page.locator('#toolRigPlayer').evaluate(f => new URL(f.src).searchParams.get('obs')), '1');
        await page.locator('#toolNext').click();
        await page.waitForFunction(() => document.getElementById('toolRigPlayer').contentWindow.paused === true);
      }
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await page.waitForFunction(() => document.getElementById('heroPlayer').contentWindow.paused === true);
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.waitForFunction(() => document.getElementById('heroPlayer').contentWindow.paused === false);
      await noOverflow(page, `${width} guest`);
      await page.evaluate(() => document.querySelectorAll('[data-reveal]').forEach(el => el.classList.add('is-in')));
      await page.locator('#auth [data-theme-toggle]').click();
      assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
      await noOverflow(page, `${width} dark guest`);
      if ([1440, 390].includes(width)) await page.screenshot({ path: path.join(out, `landing-dark-${width}.png`), fullPage: true });
      if (width === 1440) {
        await page.reload();
        assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark', 'Dark preference persists');
      }
      await page.locator('#auth [data-theme-toggle]').click();
      await page.evaluate(() => document.querySelectorAll('[data-reveal]').forEach(el => el.classList.add('is-in')));
      await page.locator('#landingNav [data-auth-open="login"]').click();
      assert(await page.locator('#authDialog').evaluate(d => d.open), 'Login opens in a dialog');
      await page.locator('#toggleAuth').click();
      assert(await page.locator('#displayName').isVisible());
      await page.locator('#toggleAuth').click();
      if ([1440, 390].includes(width)) await page.screenshot({ path: path.join(out, `login-${width}.png`) });
      await page.keyboard.press('Escape');
      if ([1440, 390].includes(width)) await page.screenshot({ path: path.join(out, `landing-${width}.png`), fullPage: true });
      populated = true;
      signedIn = true;
      await page.reload();
      await page.locator('#app').waitFor();
      await page.locator('#homePane').waitFor();
      assert.equal(new URL(page.url()).hash, '#/home', 'Signed-in users land on the home dashboard');
      await page.locator('#homeActive .job-row').waitFor();
      assert.match(await page.locator('#jobIndicatorLabel').textContent(), /내 작업 1개/);
      if (width === 1440) {
        jobState = 'complete';
        await page.locator('.ui-toast', { hasText: '완료' }).waitFor({ timeout: 8000 });
        jobState = 'generating';
      }
      for (const pane of ['home', 'generate', 'music', 'rigging', 'my', 'settings', 'queue', 'gallery', 'guide', 'admin']) {
        await go(pane);
        await page.locator(`#${pane}Pane`).waitFor();
        assert(await page.locator('#sideNav').evaluate(el => !document.body.classList.contains('nav-open')), 'Menu closes after navigation');
        await noOverflow(page, `${width} ${pane} shell`);
        if (pane === 'gallery') {
          await page.locator('#galleryList .result-card').nth(2).waitFor();
          assert.equal(await page.getByRole('link', { name: 'Unity 임포터 받기' }).count(), 1);
          // Secondary actions moved into each card's menu.
          // Every menu item must be clickable: not clipped by the card, covered by the next card or the mobile tab bar.
          for (const kind of ['video', 'rigging', 'music']) {
            const card = page.locator(`#galleryList [data-kind="${kind}"]`);
            await card.scrollIntoViewIfNeeded();
            await card.locator('.menu-wrap > button').click();
            if (kind === 'rigging') await page.getByRole('menuitem', { name: 'Unity에서 열기' }).waitFor();
            for (const item of await page.locator('.menu:not([hidden]) .menu-item').all()) {
              const box = await item.boundingBox();
              const hit = await page.evaluate(({ x, y }) => document.elementFromPoint(x, y)?.closest('.menu-item')?.textContent, { x: box.x + box.width / 2, y: box.y + box.height / 2 });
              assert.equal(hit, await item.textContent(), `${width} ${kind}: menu item hidden or covered`);
            }
            await page.keyboard.press('Escape');
          }
          assert.equal(await page.locator('.menu:not([hidden])').count(), 0, 'Escape closes the card menu');
          await noOverflow(page, `${width} populated gallery`);
          // Rigging detail: studio entry, mode shortcuts, exports and sharing in one place.
          await page.locator('#galleryList [data-kind="rigging"] .result-title').click();
          await page.locator('#jobPane #jobDetail h1').waitFor();
          assert.equal(new URL(page.url()).hash, '#/jobs/rig-test');
          assert.match(await page.getByRole('link', { name: '리깅 스튜디오 열기' }).getAttribute('href'), /rigging-editor\?job=rig-test$/);
          assert.equal(await page.locator('.studio-mode').count(), 5);
          assert.match(await page.locator('.studio-mode').nth(4).getAttribute('href'), /mode=quality/);
          assert.match(await page.locator('.studio-mode').nth(2).getAttribute('href'), /mode=bones/);
          assert.equal(await page.getByRole('button', { name: 'Unity에서 열기' }).count(), 1);
          await noOverflow(page, `${width} rig detail`);
          if ([1440, 390].includes(width)) await page.screenshot({ path: path.join(out, `detail-rig-${width}.png`), fullPage: true });
          if (width === 1440) {
            await page.getByRole('button', { name: '이름 바꾸기' }).first().click();
            await page.locator('dialog.ui-modal[open] input').fill('후드 캐릭터');
            await page.locator('dialog.ui-modal[open]').getByRole('button', { name: '저장' }).click();
            await page.locator('#jobDetail h1', { hasText: '후드 캐릭터' }).waitFor();
            galleryJobs[1].title = null;
          }
          await page.locator('.detail-back').click();
          await page.locator('#galleryPane').waitFor();
          if (width === 1440) {
            // "이 설정으로 다시 만들기" fills the embedded sprite form from the stored settings.
            await page.evaluate(() => { location.hash = '#/jobs/sprite-test'; });
            await page.getByRole('link', { name: '이 설정으로 다시 만들기' }).click();
            await page.locator('#generatePane').waitFor();
            await page.locator('.ui-toast', { hasText: '설정을 불러왔어요' }).waitFor();
            const studio = await (await page.locator('#studio').elementHandle()).contentFrame();
            assert.equal(await studio.locator('#frames').inputValue(), '16');
            assert.equal(await studio.locator('#duration').inputValue(), '3');
            assert.equal(await studio.locator('#prompt').inputValue(), '숨을 고르며 망토가 흔들린다');
            assert.equal(new URL(page.url()).hash, '#/create/sprite', 'Recreate parameter is one-shot');
            await go('gallery');
            await page.locator('#galleryList .result-card').nth(2).waitFor();
          }
          if (width === 1440) {
            await page.reload();
            await page.locator('#galleryPane').waitFor();
            assert.equal(new URL(page.url()).hash, '#/gallery', 'Route survives reload');
          }
        }
        const id = { generate: 'studio', music: 'musicStudio', rigging: 'riggingStudio' }[pane];
        if (id) {
          const frame = await (await page.locator(`#${id}`).elementHandle()).contentFrame();
          await frame.locator('html.embedded-studio').waitFor();
          await noOverflow(frame, `${width} ${pane} frame`);
          if (pane === 'generate') {
            await page.locator('#app [data-theme-toggle]').click();
            assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
            assert.equal(await frame.locator('html').getAttribute('data-theme'), 'dark', 'Dark theme reaches embedded studio');
            await noOverflow(page, `${width} dark generate shell`);
            await noOverflow(frame, `${width} dark generate frame`);
            if ([1440, 390].includes(width)) await page.screenshot({ path: path.join(out, `generate-dark-${width}.png`) });
            await page.locator('#app [data-theme-toggle]').click();
            assert.equal(await frame.locator('html').getAttribute('data-theme'), 'light');
          }
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
        if (pane === 'settings') {
          await page.locator('#shareRows .share-row').first().waitFor();
          assert.equal(await page.locator('#usageActive').textContent(), '1 / 3');
          assert(await page.locator('#notifySwitch').isDisabled(), 'Notifications need HTTPS; the switch explains why instead');
          assert.match(await page.locator('#notifyHint').textContent(), /HTTPS/);
          if (width === 1440) {
            await page.locator('#profileName').fill('새 이름');
            await page.locator('#profileForm button[type=submit]').click();
            await page.locator('.ui-toast', { hasText: '이름을 바꿨습니다' }).waitFor();
            assert.equal(await page.locator('#who').textContent(), '새 이름');
            await page.locator('#currentPassword').fill('current-password');
            await page.locator('#newPassword').fill('new-password-1');
            await page.locator('#confirmPassword').fill('new-password-2');
            await page.locator('#passwordForm button[type=submit]').click();
            assert.match(await page.locator('#passwordError').textContent(), /서로 다릅니다/);
            await page.locator('#currentPassword').fill('wrong-password');
            await page.locator('#confirmPassword').fill('new-password-1');
            await page.locator('#passwordForm button[type=submit]').click();
            await page.locator('#passwordError', { hasText: '현재 비밀번호가 맞지 않습니다' }).waitFor();
            await page.locator('#currentPassword').fill('current-password');
            await page.locator('#passwordForm button[type=submit]').click();
            await page.locator('.ui-toast', { hasText: '비밀번호를 바꿨습니다' }).waitFor();
            assert.equal(await page.locator('#newPassword').inputValue(), '', 'Password fields clear after a change');
            await page.locator('#themeChoice [data-theme-value="dark"]').click();
            assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
            assert.equal(await page.locator('#themeChoice [data-theme-value="dark"]').getAttribute('aria-pressed'), 'true');
            await page.screenshot({ path: path.join(out, 'settings-dark-1440.png'), fullPage: true });
            await page.locator('#themeChoice [data-theme-value="light"]').click();
            await page.locator('#shareRows .share-row').getByRole('button', { name: '해제' }).click();
            await page.locator('dialog.ui-modal[open]').getByRole('button', { name: '링크 해제' }).click();
            await page.locator('#shareRows .empty').waitFor();
            user.name = '테스트 팀원';
            shares = [{ token: 'tok1', jobId: 'rig-test', created: 1700000000, url: '/share/rig/tok1', title: null, composite: '/fixture-rig', rigRevision: 0 }];
          }
        }
        if (pane === 'my') {
          await page.locator('#myList .result-card').first().waitFor();
          await page.locator('#myTabs [data-tab="active"]').click();
          await page.locator('#myJobs .job-row').waitFor();
          await page.locator('#myTabs [data-tab="done"]').click();
          await page.locator('#myDone').waitFor();
        }
        if ([1440, 390].includes(width) && ['home', 'generate', 'rigging', 'music', 'my', 'settings', 'queue', 'gallery', 'guide', 'admin'].includes(pane)) {
          await page.evaluate(() => window.scrollTo(0, 0));
          await page.screenshot({ path: path.join(out, `${pane}-${width}.png`) });
        }
      }
      await openMenuIfNeeded(page.locator('#logout'));
      await page.locator('#logout').click();
      await page.locator('#auth').waitFor();
      assert.equal(await page.locator('iframe.studio-frame[src]').count(), 0, 'Logout releases the embedded studios');
      console.log(`PASS ${width}px: themes, guest, live hero, landing, home, job indicator, 10 routes, my work, settings, card menu, rig detail, embedded height, BGM modes, logout`);
    }
    assert.deepEqual(errors, [], 'Browser JavaScript errors');
    console.log(`Screenshots: ${out}`);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
