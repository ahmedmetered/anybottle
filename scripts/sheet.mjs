// Usage: node sheet.mjs <out.png> <img1> <img2> ...   (paths relative to images/)
import { chromium } from 'playwright';
import { writeFileSync } from 'node:fs';
const out = process.argv[2];
const files = process.argv.slice(3);
const cols = Math.ceil(Math.sqrt(files.length));
const cells = files.map(f => `<div style="display:flex;flex-direction:column;height:100%"><div style="flex:1;min-height:0;display:flex;align-items:center;justify-content:center"><img src="images/${f}" style="max-width:100%;max-height:100%;object-fit:contain"></div><span style="color:#fff;font:14px sans-serif;text-align:center;padding:4px;background:#111">${f}</span></div>`).join('');
writeFileSync('_sheet.html', `<!DOCTYPE html><html><body style="margin:0;background:#222;display:grid;grid-template-columns:repeat(${cols},1fr);grid-auto-rows:88vh;height:auto">${cells}</body></html>`);
const cwd = process.cwd().split('\\').join('/');
const browser = await chromium.launch({ ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) });
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
await page.goto('file://' + cwd + '/_sheet.html');
await page.waitForTimeout(1200);
await page.screenshot({ path: out, fullPage: true });
await browser.close();
console.log('sheet ->', out);
