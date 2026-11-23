// Captures the dashboard walkthrough as timed frames (no model calls; label POSTs are blocked).
import { createRequire } from 'node:module'
import { writeFileSync } from 'node:fs'
// Playwright comes from the ui-verify cache; set PLAYWRIGHT_HOME to use another install.
const require = createRequire(`${process.env.PLAYWRIGHT_HOME ?? `${process.env.HOME}/.cache/anay-ui-verify`}/package.json`)
const { chromium } = require('playwright')
const BASE = 'http://localhost:5173'
const OUT = process.argv[2]
const NAIVE = 'iuhNsY5ravgZBbKfWsNGp3', GUARD = 'F29XAP2r2UyorWG8PrdHLM'

const browser = await chromium.launch()
const ctx = await browser.newContext({ viewport: { width: 1200, height: 760 }, colorScheme: 'light', reducedMotion: 'no-preference' })
await ctx.addInitScript(() => { try { localStorage.setItem('examiner-theme', 'light') } catch {} })
const page = await ctx.newPage()
await page.route('**/api/labels', (r) => (r.request().method() === 'POST' ? r.abort() : r.continue()))

let n = 0
const frames = []
async function caption(text) {
  await page.evaluate((t) => {
    let el = document.getElementById('demo-cap')
    if (!el) {
      el = document.createElement('div')
      el.id = 'demo-cap'
      el.style.cssText = 'position:fixed;left:50%;bottom:22px;transform:translateX(-50%);max-width:880px;width:max-content;padding:10px 18px;background:#1b1a18;color:#faf9f6;font:500 17px/1.4 "Public Sans",system-ui,sans-serif;border-radius:8px;z-index:9999;box-shadow:0 6px 24px rgba(0,0,0,.18);text-align:center'
      document.body.appendChild(el)
    }
    el.textContent = t
    el.style.display = t ? 'block' : 'none'
  }, text)
}
async function shot(ms) {
  const f = `${OUT}/f${String(n++).padStart(3, '0')}.png`
  await page.screenshot({ path: f })
  frames.push({ f, ms })
}
async function go(url, sel) {
  await page.goto(BASE + url)
  await page.waitForSelector(sel)
  await page.waitForTimeout(500)
}
async function scrollTo(y, steps = 4, ms = 120) {
  const from = await page.evaluate(() => scrollY)
  for (let i = 1; i <= steps; i++) {
    await page.evaluate((v) => scrollTo(0, v), from + ((y - from) * i) / steps)
    await page.waitForTimeout(60)
    await shot(ms)
  }
}

// 1. Runs list
await go('/', 'table')
await caption('Examiner runs 127 cited bank-compliance scenarios against a chatbot and grades every reply.')
await shot(5000)
await caption('Same pack, three bots: naive 20.5%, guarded 90.6%, and a deliberately wrong one for calibration.')
await shot(5000)

// 2. Naive scorecard
await go(`/runs/${NAIVE}`, '#scorecard-h')
await caption('Naive bot: rarely false, but it dodges. Fee disclosure is almost never given.')
await shot(5500)
await scrollTo(430)
await caption('Each failure is listed with the rule it breaks.')
await shot(3500)

// 3. Guarded scorecard
await go(`/runs/${GUARD}`, '#scorecard-h')
await caption('Guarded bot: grounded on the fee schedule and its Reg E disclosure, with rules against promises.')
await shot(5500)

// 4. Diff with the wave
await page.goto(`${BASE}/diff?a=${NAIVE}&b=${GUARD}&check=overall`)
await page.waitForSelector('[role=toolbar] .tick')
await caption('Diff: one tick per scenario. Run B flips from naive to guarded verdicts.')
for (let i = 0; i < 6; i++) { await shot(90); await page.waitForTimeout(50) }
await shot(5500)
await caption('Fixed 90, broke 1. The ringed tick is the one regression.')
await shot(4000)
await page.locator('[role=toolbar] .tick.ring').first().click()
await page.waitForSelector('#cmp-h')
await page.waitForTimeout(800)
await page.evaluate(() => { document.getElementById('cmp-h')?.scrollIntoView({ block: 'start' }); scrollBy(0, -20) })
await caption('Click it to read both transcripts side by side.')
await shot(5500)

// 5. A failing finding with its cited rule
await go(`/runs/${GUARD}/results/rege-013?epoch=1&from=status%3Dfail`, '.finding-lead')
await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur())
await caption('A finding leads with why it failed, in the judge’s words.')
await shot(5500)
await scrollTo(560, 5)
await caption('The cited rule is the official Reg E text, linked to eCFR. No paraphrase.')
await shot(5500)

// 6. Label screen
await go('/label?rubric=factual', '.label-actions')
await caption('Labeling is blind: no judge verdict on screen. Y / N / S on the keyboard.')
await shot(5500)
await caption('Human labels give Cohen’s kappa per rubric: how far to trust the judge.')
await shot(5000)

writeFileSync(`${OUT}/frames.json`, JSON.stringify(frames))
await browser.close()
console.log(`${frames.length} frames, ${(frames.reduce((s, f) => s + f.ms, 0) / 1000).toFixed(1)} s`)
