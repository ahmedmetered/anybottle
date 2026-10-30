// Usage: node capture.mjs <preview.html> <out.png> [waitMs]
import { chromium } from 'playwright';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const raw = process.argv[2];
const preview = raw.startsWith('http') ? raw : path.resolve(raw);
const out = process.argv[3];
const wait = Number(process.argv[4] || 2500);
const browser = await chromium.launch({
  ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}),
  args: ['--enable-unsafe-swiftshader']
});
const page = await browser.newPage({ viewport: { width: 1000, height: 1000 } });
const errors = [];
page.on('pageerror', e => errors.push('pageerror: ' + e.message));
page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') errors.push(m.type() + ': ' + m.text()); });
const target = preview.startsWith('http') ? preview : pathToFileURL(preview).href;
const bust = target + (target.includes(String.fromCharCode(63)) ? String.fromCharCode(38) : String.fromCharCode(63)) + String.fromCharCode(98) + String.fromCharCode(61) + Date.now();
await page.goto(bust, { waitUntil: 'networkidle' });
await page.waitForTimeout(wait);
const hasCanvas = await page.evaluate(() => !!document.querySelector('canvas'));
console.log('canvas:', hasCanvas, '| errors:', errors.join('|').slice(0, 300) || 'none');
await page.screenshot({ path: out });
console.log('captured', out);
await browser.close();
