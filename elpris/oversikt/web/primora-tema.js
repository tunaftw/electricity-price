/*
 * primora-tema.js: växlaren mellan ljust och mörkt tema, gemensam för Primoras verktyg.
 * Samma fil finns i Nattariffer/web, AssetValue-Portfolio/web, FiMo-Webbverktyg/prototyp/web och
 * electricity prices/elpris/oversikt/web (Electricity Price). Ändra alla fyra.
 * Filen är också inbakad oförändrad i startsidan Primora Verktyg (https://claude.ai/artifact/WTeshECjaQFDJELpV5ZHRF).
 * Standarden för verktygen: SveaSolarObsidianv2/Projects/Primora-Energy/verktygsstandard.md.
 *
 * Val: 'light' (Ljust), 'dark' (Mörkt) eller 'system' (Följ systemet, standard). Valet sparas i localStorage
 * under nyckeln 'primora-tema'. Lagringen kan saknas (privat fönster, förhandsvisning), så varje läsning och
 * skrivning ligger i try/catch och sidan fungerar utan den.
 *
 * Temat sätts som data-theme på html-elementet, så att verktygets CSS gäller som den är skriven:
 *   :root { ljusa tokens }
 *   @media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { mörka tokens } }
 *   :root[data-theme="dark"] { mörka tokens }
 * claude.ai sätter själv data-theme när tittaren har valt tema i plattformen och inget annars. I läget
 * Följ systemet rör filen inte attributet, så plattformens val och sedan operativsystemets gäller. Ljust och
 * Mörkt skriver attributet och skriver tillbaka det om plattformen ändrar det, så att användarens val gäller.
 *
 * Filen tillämpar det sparade valet så fort den körs. Lägg den därför tidigt på sidan, före sidhuvudet, så att
 * sidan inte blinkar i fel tema.
 *
 * Användning:
 *   const avmontera = PrimoraTema.mount(värdelement, { lang: 'sv' | 'en' })   knappen och menyn i sidhuvudet
 *   PrimoraTema.get()        → { val: 'light'|'dark'|'system', tema: 'light'|'dark' }  (tema är det som visas)
 *   PrimoraTema.set(val)
 *   PrimoraTema.onChange(fn) → avregistrera; fn({ val, tema })
 * Händelsen 'primora-tema' (CustomEvent på window, detail { val, tema }) skickas när valet eller det visade
 * temat ändras, även när systemets tema ändras i läget Följ systemet. Diagram som läser färger med
 * getComputedStyle ritas om då. Diagram som färgas med CSS-variabler följer med utan att lyssna.
 */
(function (root) {
  'use strict';

  const NYCKEL = 'primora-tema';
  const VAL = ['light', 'dark', 'system'];
  const TEXT = {
    sv: { tema: 'Tema', light: 'Ljust', dark: 'Mörkt', system: 'Följ systemet' },
    en: { tema: 'Theme', light: 'Light', dark: 'Dark', system: 'Match system' },
  };
  // Iconoir Regular 7.12.1 (MIT): sun-light, half-moon, computer och check.
  const IKON = {
    light: ['M12 18C15.3137 18 18 15.3137 18 12C18 8.68629 15.3137 6 12 6C8.68629 6 6 8.68629 6 12C6 15.3137 8.68629 18 12 18Z',
      'M22 12L23 12', 'M12 2V1', 'M12 23V22', 'M20 20L19 19', 'M20 4L19 5', 'M4 20L5 19', 'M4 4L5 5', 'M1 12L2 12'],
    dark: ['M3 11.5066C3 16.7497 7.25034 21 12.4934 21C16.2209 21 19.4466 18.8518 21 15.7259C12.4934 15.7259 8.27411 11.5066 8.27411 3C5.14821 4.55344 3 7.77915 3 11.5066Z'],
    system: ['M2 21L17 21', 'M21 21L22 21',
      'M2 16.4V3.6C2 3.26863 2.26863 3 2.6 3H21.4C21.7314 3 22 3.26863 22 3.6V16.4C22 16.7314 21.7314 17 21.4 17H2.6C2.26863 17 2 16.7314 2 16.4Z'],
    check: ['M5 13L9 17L19 7'],
  };

  const CSS = `
.pt{--pt-surface:#fff;--pt-surface-2:#eaf1f1;--pt-rule:#d5e2e3;--pt-ink:#073746;--pt-muted:#526c72;--pt-accent:#0b7a83;--pt-focus:#0b7a83;
  --pt-btn:color-mix(in srgb,#fff 55%,transparent);--pt-btn-hover:color-mix(in srgb,#fff 80%,transparent);position:relative;display:inline-flex}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .pt{--pt-surface:#0a3a47;--pt-surface-2:#0d4452;--pt-rule:#1d5563;--pt-ink:#eaf1f1;
  --pt-muted:#b0c6c9;--pt-accent:#a6d4d1;--pt-focus:#a6d4d1;--pt-btn:color-mix(in srgb,#fff 8%,transparent);--pt-btn-hover:color-mix(in srgb,#fff 16%,transparent)}}
:root[data-theme="dark"] .pt{--pt-surface:#0a3a47;--pt-surface-2:#0d4452;--pt-rule:#1d5563;--pt-ink:#eaf1f1;
  --pt-muted:#b0c6c9;--pt-accent:#a6d4d1;--pt-focus:#a6d4d1;--pt-btn:color-mix(in srgb,#fff 8%,transparent);--pt-btn-hover:color-mix(in srgb,#fff 16%,transparent)}
.pt-btn{display:inline-grid;place-items:center;width:40px;height:40px;padding:0;border-radius:999px;cursor:pointer;color:inherit;
  border:1px solid color-mix(in srgb,currentColor 28%,transparent);background:var(--pt-btn)}
.pt-btn:hover,.pt-btn[aria-expanded="true"]{background:var(--pt-btn-hover)}
.pt svg{width:20px;height:20px;flex:none}
.pt :focus-visible{outline:2px solid var(--pt-focus);outline-offset:2px}
.pt-meny{position:absolute;top:calc(100% + 6px);right:0;z-index:60;min-width:200px;margin:0;padding:6px;list-style:none;
  background:var(--pt-surface);color:var(--pt-ink);border:1px solid var(--pt-rule);border-radius:10px;
  box-shadow:0 1px 2px rgba(7,55,70,.06),0 12px 36px rgba(7,55,70,.18)}
.pt-meny[hidden]{display:none}
.pt-rubrik{padding:6px 10px 4px;font:600 14px/1.3 "Figtree","Segoe UI",system-ui,sans-serif;color:var(--pt-muted)}
.pt-val{display:flex;align-items:center;gap:10px;width:100%;min-height:40px;padding:8px 10px;border:0;border-radius:7px;background:transparent;
  color:var(--pt-ink);cursor:pointer;text-align:left;font:600 15px/1.3 "Figtree","Segoe UI",system-ui,sans-serif}
.pt-val:hover,.pt-val:focus{background:var(--pt-surface-2)}
.pt-val:focus-visible{outline-offset:-2px}
.pt-val .pt-bock{margin-left:auto;color:var(--pt-accent);visibility:hidden}
.pt-val[aria-checked="true"] .pt-bock{visibility:visible}
`;

  const doc = root.document;
  const html = doc && doc.documentElement;
  const mq = typeof root.matchMedia === 'function' ? root.matchMedia('(prefers-color-scheme: dark)') : null;

  function lasVal() {
    try {
      const v = root.localStorage.getItem(NYCKEL);
      return VAL.includes(v) ? v : 'system';
    } catch (e) { return 'system'; }
  }
  function sparaVal(v) {
    try {
      if (v === 'system') root.localStorage.removeItem(NYCKEL);
      else root.localStorage.setItem(NYCKEL, v);
    } catch (e) { /* lagringen saknas: valet gäller tills sidan laddas om */ }
  }

  let val = lasVal();
  // Plattformens data-theme (claude.ai), som gäller i läget Följ systemet.
  let plattform = html ? html.getAttribute('data-theme') : null;
  let senast = null;
  const lyssnare = new Set();

  function visatTema() {
    const a = html ? html.getAttribute('data-theme') : null;
    if (a === 'light' || a === 'dark') return a;
    return mq && mq.matches ? 'dark' : 'light';
  }
  function get() { return { val, tema: visatTema() }; }

  function meddela() {
    const nu = get();
    if (senast && senast.val === nu.val && senast.tema === nu.tema) return;
    senast = nu;
    for (const fn of lyssnare) { try { fn(nu); } catch (e) { /* en trasig lyssnare stoppar inte de andra */ } }
    if (typeof root.dispatchEvent === 'function' && typeof root.CustomEvent === 'function') {
      root.dispatchEvent(new root.CustomEvent('primora-tema', { detail: nu }));
    }
  }

  /** Skriver data-theme för valet: eget val, eller plattformens värde i läget Följ systemet. */
  function tillampa() {
    if (!html) return;
    const mal = val === 'system' ? plattform : val;
    const nu = html.getAttribute('data-theme');
    if (mal === nu) return;
    if (mal == null) html.removeAttribute('data-theme');
    else html.setAttribute('data-theme', mal);
  }

  function set(v) {
    if (!VAL.includes(v)) throw new TypeError(`PrimoraTema.set: okänt val ${JSON.stringify(v)}`);
    val = v;
    sparaVal(v);
    tillampa();
    meddela();
  }

  function onChange(fn) {
    lyssnare.add(fn);
    return () => lyssnare.delete(fn);
  }

  tillampa();
  senast = get();

  // Plattformen ändrar data-theme när tittaren byter tema i claude.ai.
  if (html && typeof root.MutationObserver === 'function') {
    new root.MutationObserver(() => {
      const a = html.getAttribute('data-theme');
      if (val === 'system') plattform = a;
      else if (a !== val) { plattform = a; tillampa(); }
      meddela();
    }).observe(html, { attributes: true, attributeFilter: ['data-theme'] });
  }
  if (mq) {
    const nar = () => meddela();
    if (typeof mq.addEventListener === 'function') mq.addEventListener('change', nar);
    else if (typeof mq.addListener === 'function') mq.addListener(nar);
  }

  // ------------------------------------------------------------ knappen och menyn
  const SVGNS = 'http://www.w3.org/2000/svg';
  function ikon(namn, klass) {
    const s = doc.createElementNS(SVGNS, 'svg');
    for (const [k, v] of [['viewBox', '0 0 24 24'], ['fill', 'none'], ['stroke', 'currentColor'], ['stroke-width', '1.5'],
      ['stroke-linecap', 'round'], ['stroke-linejoin', 'round'], ['aria-hidden', 'true'], ['focusable', 'false']]) s.setAttribute(k, v);
    if (klass) s.setAttribute('class', klass);
    for (const d of IKON[namn]) {
      const p = doc.createElementNS(SVGNS, 'path');
      p.setAttribute('d', d);
      s.append(p);
    }
    return s;
  }

  let styled = false;
  function injectStyle() {
    if (styled) return;
    styled = true;
    const st = doc.createElement('style');
    st.setAttribute('data-primora-tema', '');
    st.textContent = CSS;
    doc.head.append(st);
  }

  let nasta = 0;
  function mount(host, opts) {
    injectStyle();
    const T = TEXT[(opts && opts.lang) === 'en' ? 'en' : 'sv'];
    const id = `pt-meny-${++nasta}`;
    const wrap = doc.createElement('div');
    wrap.className = 'pt';
    const btn = doc.createElement('button');
    btn.type = 'button';
    btn.className = 'pt-btn';
    btn.setAttribute('aria-haspopup', 'menu');
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-controls', id);
    const meny = doc.createElement('ul');
    meny.className = 'pt-meny';
    meny.id = id;
    meny.hidden = true;
    meny.setAttribute('role', 'menu');
    meny.setAttribute('aria-label', T.tema);
    const rubrik = doc.createElement('li');
    rubrik.className = 'pt-rubrik';
    rubrik.setAttribute('role', 'presentation');
    rubrik.setAttribute('aria-hidden', 'true');
    rubrik.textContent = T.tema;
    meny.append(rubrik);
    const knappar = VAL.map((v) => {
      const li = doc.createElement('li');
      li.setAttribute('role', 'none');
      const b = doc.createElement('button');
      b.type = 'button';
      b.className = 'pt-val';
      b.tabIndex = -1;
      b.dataset.val = v;
      b.setAttribute('role', 'menuitemradio');
      const namn = doc.createElement('span');
      namn.textContent = T[v];
      b.append(ikon(v), namn, ikon('check', 'pt-bock'));
      b.addEventListener('click', () => { set(v); stang(true); });
      li.append(b);
      meny.append(li);
      return b;
    });
    wrap.append(btn, meny);
    host.append(wrap);

    function synka() {
      const namn = `${T.tema}: ${T[val]}`;
      btn.setAttribute('aria-label', namn);
      btn.title = namn;
      btn.replaceChildren(ikon(val));
      for (const b of knappar) b.setAttribute('aria-checked', String(b.dataset.val === val));
    }
    function oppna() {
      meny.hidden = false;
      btn.setAttribute('aria-expanded', 'true');
      (knappar.find((b) => b.dataset.val === val) || knappar[0]).focus();
      doc.addEventListener('pointerdown', utanfor, true);
    }
    function stang(fokus) {
      if (meny.hidden) return;
      meny.hidden = true;
      btn.setAttribute('aria-expanded', 'false');
      doc.removeEventListener('pointerdown', utanfor, true);
      if (fokus) btn.focus();
    }
    function utanfor(e) { if (!wrap.contains(e.target)) stang(false); }

    btn.addEventListener('click', () => (meny.hidden ? oppna() : stang(true)));
    btn.addEventListener('keydown', (e) => {
      if ((e.key === 'ArrowDown' || e.key === 'ArrowUp') && meny.hidden) { e.preventDefault(); oppna(); }
    });
    meny.addEventListener('keydown', (e) => {
      const i = knappar.indexOf(doc.activeElement);
      const flytta = (j) => { e.preventDefault(); knappar[(j + knappar.length) % knappar.length].focus(); };
      if (e.key === 'ArrowDown') flytta(i + 1);
      else if (e.key === 'ArrowUp') flytta(i - 1);
      else if (e.key === 'Home') flytta(0);
      else if (e.key === 'End') flytta(knappar.length - 1);
      else if (e.key === 'Escape') { e.preventDefault(); stang(true); }
      else if (e.key === 'Tab') stang(false);
    });

    synka();
    const av = onChange(synka);
    return () => { av(); stang(false); wrap.remove(); };
  }

  root.PrimoraTema = { mount, get, set, onChange };
})(typeof window !== 'undefined' ? window : globalThis);
