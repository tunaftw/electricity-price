#!/usr/bin/env node
// Granskar en genererad sida i huvudlös Chrome via DevTools-protokollet (Node 22+, inga beroenden).
// Tar helsidesbilder per bredd och tema och rapporterar konsolfel och sidledsrullning.
//
//   node scripts/granska_sidan.mjs <url> <utkatalog> [bredder=1440,390] [teman=light,dark,system] [hash=]
//
// Temat sätts som växlaren gör (localStorage 'primora-tema'); 'system' följer den emulerade
// prefers-color-scheme, som då sätts till dark så att båda vägarna till mörkt tema provas.
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const [url, out, widthsArg = '1440,390', themesArg = 'light,dark,system', hash = ''] = process.argv.slice(2);
const CHROME = process.env.CHROME || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PORT = 9300 + Math.floor(Math.random() * 500);
mkdirSync(out, { recursive: true });
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--hide-scrollbars', `--remote-debugging-port=${PORT}`,
  `--user-data-dir=${join(out, '.profil')}`, 'about:blank'], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function target() {
  for (let i = 0; i < 50; i++) {
    try { const list = await (await fetch(`http://127.0.0.1:${PORT}/json`)).json(); const p = list.find((t) => t.type === 'page'); if (p) return p; } catch {}
    await sleep(200);
  }
  throw new Error('Chrome svarar inte');
}
const page = await target();
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r, { once: true }));
let id = 0; const waiting = new Map(); const errors = [];
ws.addEventListener('message', (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && waiting.has(msg.id)) { waiting.get(msg.id)(msg); waiting.delete(msg.id); }
  if (msg.method === 'Runtime.exceptionThrown') errors.push(msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text);
  if (msg.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(msg.params.type)) errors.push(msg.params.type + ': ' + msg.params.args.map((a) => a.value ?? a.description).join(' '));
  if (msg.method === 'Log.entryAdded' && msg.params.entry.level === 'error') errors.push('log: ' + msg.params.entry.text);
});
const send = (method, params = {}) => new Promise((r) => { const i = ++id; waiting.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
await send('Runtime.enable'); await send('Log.enable'); await send('Page.enable');

const report = [];
for (const width of widthsArg.split(',').map(Number)) {
  for (const theme of themesArg.split(',')) {
    errors.length = 0;
    await send('Emulation.setDeviceMetricsOverride', { width, height: 900, deviceScaleFactor: 1, mobile: width < 600 });
    await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: theme === 'light' ? 'light' : 'dark' }] });
    const script = await send('Page.addScriptToEvaluateOnNewDocument', { source: `try { localStorage.setItem('primora-tema', '${theme}'); } catch (e) {}` });
    await send('Page.navigate', { url: url + (hash ? '#' + hash : '') });
    await sleep(3500);
    const res = await send('Runtime.evaluate', { returnByValue: true, expression: `({scrollW: document.documentElement.scrollWidth, vw: document.documentElement.clientWidth,
      h: document.documentElement.scrollHeight, theme: getComputedStyle(document.body).backgroundColor, lang: document.documentElement.lang,
      band: document.querySelector('.band') && document.querySelector('.band').getBoundingClientRect().height})` });
    const m = res.result.result.value;
    await send('Emulation.setDeviceMetricsOverride', { width, height: Math.min(m.h, 16000), deviceScaleFactor: 1, mobile: width < 600 });
    await sleep(800);
    const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
    const name = `${width}_${theme}${hash ? '_' + hash.replace(/[^a-z0-9]+/gi, '-') : ''}.png`;
    writeFileSync(join(out, name), Buffer.from(shot.result.data, 'base64'));
    await send('Page.removeScriptToEvaluateOnNewDocument', { identifier: script.result.identifier });
    report.push({ width, theme, ...m, errors: [...errors], file: name });
  }
}
console.log(JSON.stringify(report, null, 1));
ws.close(); chrome.kill();
