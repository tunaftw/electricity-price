/*
 * primora-feedback.js: knappen "Ge feedback" och dess dialog, gemensam för Primoras verktyg.
 * Samma fil finns i Nattariffer/web, AssetValue-Portfolio/web, FiMo-Webbverktyg/prototyp/web och
 * electricity prices/elpris/oversikt/web (Electricity Price). Ändra alla fyra.
 * Timeline har en egen React-version (app/src/lib/feedback.ts) med samma datamodell.
 * Standarden för verktygen: SveaSolarObsidianv2/Projects/Primora-Energy/verktygsstandard.md.
 *
 * Datamodell i artefaktens databas (db-kapabiliteten):
 *   feedback/<användar-id> = {
 *     authorName, updatedAt,
 *     items: { <id>: { text, category: 'fel'|'forslag'|'ovrigt', view, createdAt, status: 'ny'|'pagar'|'klar' } }
 *   }
 * Nycklarna för kategori och status är desamma på alla språk. Bara texterna följer lang.
 * Åtkomstreglerna (deklareras vid publicering) gör dokumentet läsbart bara för personen själv och ägaren:
 *   { path: 'feedback', read: 'owner', write: 'owner' },
 *   { path: 'feedback/{self}', read: 'interact', write: 'interact' }
 * Ägaren läser och ändrar status med ArtifactData. items är ett objekt (inte en lista), så att update()
 * slår ihop nya poster och statusändringar utan att skriva över varandra.
 *
 * Användning: PrimoraFeedback.mount(värdelement, { tool: 'Financial Model', view: () => 'Portfölj',
 *   theme: 'light' | 'auto', lang: 'sv' | 'en' })
 * theme: 'auto' följer data-theme på html-elementet (växlaren primora-tema.js) och annars systemets tema.
 * I fönster smalare än 600 px visas knappen som en ikon. Texten finns kvar för skärmläsare.
 */
(function (root) {
  'use strict';

  const TEXT = {
    sv: {
      knapp: 'Ge feedback',
      kategorier: { fel: ['Fel', 'Något räknar eller fungerar fel'], forslag: ['Förslag', 'Något som kan bli bättre'], ovrigt: ['Övrigt', 'Allt annat'] },
      status: { ny: 'Mottagen', pagar: 'Pågår', klar: 'Åtgärdad' },
      typ: 'Typ av feedback',
      rubrik: (tool) => `Feedback om ${tool}`,
      ingress: 'Allt du skickar läses och används för att förbättra verktyget. Du kan skicka hur många gånger du vill.',
      falt: 'Din feedback',
      platshallare: 'Beskriv vad som hände eller vad du önskar. Skriv gärna vilket projekt eller vilken siffra det gäller.',
      skicka: 'Skicka',
      stang: 'Stäng',
      historik: 'Din tidigare feedback',
      historikAntal: (n) => `Din tidigare feedback (${n})`,
      tom: 'Inget skickat än.',
      fran: 'Skickas från',
      tack: 'Tack! Din feedback är sparad.',
      ejInloggad: 'Feedback kan bara skickas när verktyget är öppnat på claude.ai och du är inloggad.',
      fel: {
        behorighet: 'Du har bara läsbehörighet till verktyget och kan därför inte skicka feedback. Be Pontus Skog om behörigheten "Kan interagera".',
        full: 'Feedbacklådan är full. Säg till Pontus Skog, så tömmer han den.',
        andrad: 'Din åtkomst till verktyget har ändrats. Ladda om sidan och försök igen.',
        ovrigt: 'Det gick inte att skicka just nu. Försök igen om en stund. Texten finns kvar.',
      },
      datum: 'sv-SE',
    },
    en: {
      knapp: 'Give feedback',
      kategorier: { fel: ['Bug', 'Something is calculated or works incorrectly'], forslag: ['Suggestion', 'Something that could be better'], ovrigt: ['Other', 'Anything else'] },
      status: { ny: 'Received', pagar: 'In progress', klar: 'Done' },
      typ: 'Type of feedback',
      rubrik: (tool) => `Feedback on ${tool}`,
      ingress: 'Everything you send is read and used to improve the tool. You can send as many times as you like.',
      falt: 'Your feedback',
      platshallare: 'Describe what happened or what you would like. Mention the project or figure it concerns, if you can.',
      skicka: 'Send',
      stang: 'Close',
      historik: 'Your earlier feedback',
      historikAntal: (n) => `Your earlier feedback (${n})`,
      tom: 'Nothing sent yet.',
      fran: 'Sent from',
      tack: 'Thank you. Your feedback is saved.',
      ejInloggad: 'Feedback can only be sent when the tool is opened on claude.ai and you are signed in.',
      fel: {
        behorighet: 'You have read-only access to the tool, so you cannot send feedback. Ask Pontus Skog for the "Can interact" permission.',
        full: 'The feedback box is full. Tell Pontus Skog so that it can be emptied.',
        andrad: 'Your access to the tool has changed. Reload the page and try again.',
        ovrigt: 'The feedback could not be sent right now. Try again in a moment. Your text is still here.',
      },
      datum: 'en-GB',
    },
  };
  const CATEGORY_KEYS = ['fel', 'forslag', 'ovrigt'];
  const STATUS_KEYS = ['ny', 'pagar', 'klar'];
  const MAX_TEXT = 2000;
  const COLLECTION = 'feedback';

  const CSS = `
.pfb,.pfb-btn{--pfb-surface:#fff;--pfb-surface-2:#eaf1f1;--pfb-rule:#d5e2e3;--pfb-field:#768f94;--pfb-ink:#073746;--pfb-ink-2:#415f67;--pfb-muted:#526c72;
  --pfb-accent:#073746;--pfb-accent-ink:#fff;--pfb-focus:#0b7a83;--pfb-ok:#1f6e45;--pfb-ok-soft:#e3f1ea;--pfb-warn:#7a4f00;--pfb-warn-soft:#fff4de;
  --pfb-crit:#b42318;--pfb-crit-soft:#fde8e7;--pfb-backdrop:rgba(7,55,70,.45);--pfb-btn:color-mix(in srgb,#fff 55%,transparent);--pfb-btn-hover:color-mix(in srgb,#fff 80%,transparent)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) :is(.pfb,.pfb-btn).pfb-auto{--pfb-surface:#0a3a47;--pfb-surface-2:#0d4452;--pfb-rule:#1d5563;--pfb-field:#6a98a2;
  --pfb-ink:#eaf1f1;--pfb-ink-2:#c3d6d8;--pfb-muted:#b0c6c9;--pfb-accent:#a6d4d1;--pfb-accent-ink:#073746;--pfb-focus:#a6d4d1;
  --pfb-ok:#9ad8b4;--pfb-ok-soft:#123f35;--pfb-warn:#f4c462;--pfb-warn-soft:#3d3314;--pfb-crit:#ff9b90;--pfb-crit-soft:#4a1f24;--pfb-backdrop:rgba(0,0,0,.55);
  --pfb-btn:color-mix(in srgb,#fff 8%,transparent);--pfb-btn-hover:color-mix(in srgb,#fff 16%,transparent)}}
:root[data-theme="dark"] :is(.pfb,.pfb-btn).pfb-auto{--pfb-surface:#0a3a47;--pfb-surface-2:#0d4452;--pfb-rule:#1d5563;--pfb-field:#6a98a2;
  --pfb-ink:#eaf1f1;--pfb-ink-2:#c3d6d8;--pfb-muted:#b0c6c9;--pfb-accent:#a6d4d1;--pfb-accent-ink:#073746;--pfb-focus:#a6d4d1;
  --pfb-ok:#9ad8b4;--pfb-ok-soft:#123f35;--pfb-warn:#f4c462;--pfb-warn-soft:#3d3314;--pfb-crit:#ff9b90;--pfb-crit-soft:#4a1f24;--pfb-backdrop:rgba(0,0,0,.55);
  --pfb-btn:color-mix(in srgb,#fff 8%,transparent);--pfb-btn-hover:color-mix(in srgb,#fff 16%,transparent)}
.pfb-btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:40px;border:1px solid color-mix(in srgb,currentColor 28%,transparent);
  background:var(--pfb-btn);color:inherit;border-radius:999px;padding:8px 16px 8px 13px;cursor:pointer;
  font:600 15px/1.2 "Figtree","Segoe UI",system-ui,sans-serif;white-space:nowrap}
.pfb-btn:hover{background:var(--pfb-btn-hover)}
.pfb-btn svg{width:20px;height:20px;flex:none}
.pfb-btn:focus-visible,.pfb :focus-visible{outline:2px solid var(--pfb-focus);outline-offset:2px}
@media (max-width:600px){
  .pfb-btn{width:40px;height:40px;padding:0}
  .pfb-btn .pfb-lbl-txt{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;border:0}
}
dialog.pfb{border:1px solid var(--pfb-rule);border-radius:14px;padding:0;background:var(--pfb-surface);color:var(--pfb-ink);
  width:min(560px,calc(100vw - 32px));max-height:calc(100vh - 48px);box-shadow:0 1px 2px rgba(7,55,70,.06),0 12px 36px rgba(7,55,70,.18);
  font:16px/1.5 "IBM Plex Sans","Segoe UI",system-ui,sans-serif}
dialog.pfb::backdrop{background:var(--pfb-backdrop)}
.pfb-in{display:flex;flex-direction:column;max-height:calc(100vh - 50px)}
.pfb-head{padding:20px 24px 12px;display:grid;gap:6px}
.pfb-head h2{margin:0;font:700 20px/1.25 "Figtree","Segoe UI",system-ui,sans-serif;color:var(--pfb-ink);text-wrap:balance}
.pfb-head p{margin:0;color:var(--pfb-ink-2);font-size:15px}
.pfb-body{padding:4px 24px 18px;overflow:auto;display:grid;gap:16px}
.pfb-seg{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.pfb-seg button{border:1px solid var(--pfb-field);background:var(--pfb-surface);color:var(--pfb-ink-2);border-radius:8px;padding:9px 12px;
  cursor:pointer;text-align:left;display:grid;gap:2px;font:inherit;min-height:44px}
.pfb-seg button b{font:600 15px/1.3 "Figtree","Segoe UI",system-ui,sans-serif;color:var(--pfb-ink)}
.pfb-seg button span{font-size:14px;color:var(--pfb-muted);line-height:1.35}
.pfb-seg button[aria-pressed="true"]{border-color:var(--pfb-accent);box-shadow:inset 0 0 0 1px var(--pfb-accent);background:var(--pfb-surface-2)}
@media (max-width:460px){.pfb-seg button span{display:none}.pfb-head,.pfb-foot{padding-inline:18px}.pfb-body{padding-inline:18px}}
.pfb-lbl{display:grid;gap:6px;font:600 15px/1.3 "Figtree","Segoe UI",system-ui,sans-serif;color:var(--pfb-ink)}
.pfb textarea{width:100%;box-sizing:border-box;min-height:128px;resize:vertical;border:1px solid var(--pfb-field);border-radius:8px;
  padding:10px 12px;background:var(--pfb-surface);color:var(--pfb-ink);font:16px/1.5 "IBM Plex Sans","Segoe UI",system-ui,sans-serif}
.pfb textarea::placeholder{color:var(--pfb-muted);opacity:1}
.pfb textarea:focus{outline:none;border-color:var(--pfb-focus);box-shadow:0 0 0 3px color-mix(in srgb,var(--pfb-focus) 20%,transparent)}
.pfb-meta{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-size:14px;color:var(--pfb-muted)}
.pfb-meta .pfb-count{font-family:"IBM Plex Mono",Consolas,monospace;font-variant-numeric:tabular-nums}
.pfb-msg{font-size:15px;border-radius:8px;padding:10px 12px}
.pfb-msg.ok{background:var(--pfb-ok-soft);color:var(--pfb-ok)}
.pfb-msg.err{background:var(--pfb-crit-soft);color:var(--pfb-crit)}
.pfb-msg.info{background:var(--pfb-surface-2);color:var(--pfb-ink-2)}
.pfb-foot{padding:14px 24px;border-top:1px solid var(--pfb-rule);display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap}
.pfb-foot button{border:1px solid var(--pfb-field);background:var(--pfb-surface);color:var(--pfb-ink);border-radius:8px;padding:9px 16px;min-height:42px;
  cursor:pointer;font:600 15px/1.2 "Figtree","Segoe UI",system-ui,sans-serif}
.pfb-foot button.pfb-primary{background:var(--pfb-accent);border-color:var(--pfb-accent);color:var(--pfb-accent-ink)}
.pfb-foot button:disabled{opacity:.5;cursor:not-allowed}
.pfb-hist{border-top:1px solid var(--pfb-rule);padding-top:14px;display:grid;gap:10px}
.pfb-hist h3{margin:0;font:600 16px/1.3 "Figtree","Segoe UI",system-ui,sans-serif;color:var(--pfb-ink)}
.pfb-hist ul{list-style:none;margin:0;padding:0;display:grid;gap:8px}
.pfb-hist li{border:1px solid var(--pfb-rule);border-radius:8px;padding:10px 12px;display:grid;gap:4px;background:var(--pfb-surface)}
.pfb-row{display:flex;gap:6px 10px;align-items:center;flex-wrap:wrap;font-size:14px;color:var(--pfb-muted)}
.pfb-chip{display:inline-flex;align-items:center;border-radius:6px;padding:1px 8px;font:600 13px/1.5 "Figtree","Segoe UI",system-ui,sans-serif;
  background:var(--pfb-surface-2);color:var(--pfb-ink-2)}
.pfb-chip.s-ny{background:var(--pfb-surface-2);color:var(--pfb-ink-2)}
.pfb-chip.s-pagar{background:var(--pfb-warn-soft);color:var(--pfb-warn)}
.pfb-chip.s-klar{background:var(--pfb-ok-soft);color:var(--pfb-ok)}
.pfb-txt{font-size:15px;color:var(--pfb-ink);white-space:pre-wrap;overflow-wrap:anywhere}
.pfb-empty{font-size:15px;color:var(--pfb-muted)}
`;

  // Iconoir Regular 7.12.1 (MIT): message-text.
  const ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">'
    + '<path d="M7 12L17 12"/><path d="M7 8L13 8"/>'
    + '<path d="M3 20.2895V5C3 3.89543 3.89543 3 5 3H19C20.1046 3 21 3.89543 21 5V15C21 16.1046 20.1046 17 19 17H7.96125C7.35368 17 6.77906 17.2762 6.39951 17.7506L4.06852 20.6643C3.71421 21.1072 3 20.8567 3 20.2895Z"/></svg>';

  function h(tag, attrs, ...kids) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v == null || v === false) continue;
      if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
      else if (k === 'html') e.innerHTML = v;
      else e.setAttribute(k, v === true ? '' : v);
    }
    for (const k of kids.flat()) if (k != null && k !== false) e.append(k.nodeType ? k : document.createTextNode(String(k)));
    return e;
  }

  const newId = () => Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
  const codeOf = (e) => (e && typeof e.code === 'string' && e.code) || 'unavailable';

  function errorText(T, code) {
    if (code === 'invalid_argument' || code === 'not_granted') return T.fel.behorighet;
    if (code === 'quota_exceeded') return T.fel.full;
    if (code === 'revoked') return T.fel.andrad;
    return T.fel.ovrigt;
  }

  /** Kapabiliteterna db och user, eller null. Frågar plattformen en gång. */
  let capsPromise = null;
  function caps() {
    if (!capsPromise) {
      capsPromise = (async () => {
        const c = root.claude;
        if (!c || typeof c.use !== 'function') return null;
        try {
          const [db, user] = await Promise.all([c.use('db'), c.use('user')]);
          if (!db || !user) return null;
          const uid = await user.id();
          return uid ? { db, user, uid } : null;
        } catch (e) { return null; }
      })();
    }
    return capsPromise;
  }

  let styled = false;
  function injectStyle() {
    if (styled) return;
    styled = true;
    document.head.append(h('style', { 'data-primora-feedback': '' }, CSS));
  }

  let mounts = 0;
  function mount(host, opts) {
    injectStyle();
    const T = TEXT[opts.lang === 'en' ? 'en' : 'sv'];
    const tool = opts.tool;
    const viewOf = typeof opts.view === 'function' ? opts.view : () => '';
    const themeCls = opts.theme === 'auto' ? 'pfb-auto' : '';
    const fmtDate = (iso) => {
      try { return new Date(iso).toLocaleString(T.datum, { dateStyle: 'medium', timeStyle: 'short' }); } catch (e) { return iso; }
    };
    const n = ++mounts;
    const ids = { title: `pfb-title-${n}`, text: `pfb-text-${n}` };

    const btn = h('button', { type: 'button', class: ('pfb-btn ' + themeCls).trim(), 'aria-haspopup': 'dialog', title: T.knapp, html: ICON },
      h('span', { class: 'pfb-lbl-txt' }, T.knapp));
    host.append(btn);

    let dlg = null, ui = null;
    let category = 'forslag';
    let docState = { exists: false, items: {} };
    let unsub = null, busy = false;

    function renderHistory() {
      const items = Object.entries(docState.items || {})
        .map(([id, it]) => ({ id, ...it }))
        .filter((it) => it && typeof it.text === 'string')
        .sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
      ui.histTitle.textContent = items.length ? T.historikAntal(items.length) : T.historik;
      ui.list.textContent = '';
      if (!items.length) { ui.list.append(h('li', { class: 'pfb-empty', style: 'border:0;padding:0' }, T.tom)); return; }
      for (const it of items) {
        const cat = CATEGORY_KEYS.includes(it.category) ? it.category : 'ovrigt';
        const st = STATUS_KEYS.includes(it.status) ? it.status : 'ny';
        ui.list.append(h('li', null,
          h('div', { class: 'pfb-row' },
            h('span', { class: 'pfb-chip' }, T.kategorier[cat][0]),
            h('span', { class: 'pfb-chip s-' + st }, T.status[st]),
            h('span', null, fmtDate(it.createdAt)),
            it.view ? h('span', null, '· ' + it.view) : null),
          h('div', { class: 'pfb-txt' }, it.text)));
      }
    }

    function setMsg(kind, text) {
      ui.msg.hidden = !text;
      ui.msg.className = 'pfb-msg ' + kind;
      ui.msg.textContent = text || '';
    }

    function syncSend() {
      const len = ui.text.value.trim().length;
      ui.count.textContent = `${ui.text.value.length} / ${MAX_TEXT}`;
      ui.send.disabled = busy || !ui.ready || len === 0 || ui.text.value.length > MAX_TEXT;
    }

    function build() {
      const seg = h('div', { class: 'pfb-seg', role: 'group', 'aria-label': T.typ },
        CATEGORY_KEYS.map((k) => h('button', {
          type: 'button', 'data-k': k, 'aria-pressed': String(k === category),
          onclick: () => { category = k; for (const b of seg.children) b.setAttribute('aria-pressed', String(b.dataset.k === category)); },
        }, h('b', null, T.kategorier[k][0]), h('span', null, T.kategorier[k][1]))));
      const text = h('textarea', { id: ids.text, maxlength: String(MAX_TEXT), placeholder: T.platshallare });
      const count = h('span', { class: 'pfb-count' }, '');
      const where = h('span', null, '');
      const msg = h('div', { class: 'pfb-msg', hidden: true, role: 'status', 'aria-live': 'polite' });
      const send = h('button', { type: 'button', class: 'pfb-primary', disabled: true }, T.skicka);
      const close = h('button', { type: 'button' }, T.stang);
      const histTitle = h('h3', null, T.historik);
      const list = h('ul');
      dlg = h('dialog', { class: ('pfb ' + themeCls).trim(), 'aria-labelledby': ids.title },
        h('div', { class: 'pfb-in' },
          h('div', { class: 'pfb-head' },
            h('h2', { id: ids.title }, T.rubrik(tool)),
            h('p', null, T.ingress)),
          h('div', { class: 'pfb-body' },
            seg,
            h('label', { class: 'pfb-lbl', for: ids.text }, T.falt, text),
            h('div', { class: 'pfb-meta' }, where, count),
            msg,
            h('section', { class: 'pfb-hist' }, histTitle, list)),
          h('div', { class: 'pfb-foot' }, close, send)));
      document.body.append(dlg);
      ui = { text, count, where, msg, send, list, histTitle, ready: false };
      text.addEventListener('input', () => { if (!ui.msg.classList.contains('info')) setMsg('', ''); syncSend(); });
      close.addEventListener('click', () => dlg.close());
      send.addEventListener('click', submit);
      renderHistory();
    }

    async function connect() {
      const c = await caps();
      if (!c) {
        ui.ready = false;
        setMsg('info', T.ejInloggad);
        syncSend();
        return;
      }
      ui.ready = true;
      syncSend();
      if (!unsub) {
        const ref = c.db.doc(`${COLLECTION}/${c.uid}`);
        unsub = ref.onSnapshot((snap) => {
          const d = snap.exists ? snap.data() : null;
          docState = { exists: !!snap.exists, items: (d && d.items) || {} };
          renderHistory();
        }, () => { unsub = null; });
      }
    }

    async function submit() {
      const value = ui.text.value.trim();
      if (!value || busy) return;
      const c = await caps();
      if (!c) return;
      busy = true; syncSend(); setMsg('', '');
      const now = new Date().toISOString();
      const entry = { text: value, category, view: ui.viewLabel || '', createdAt: now, status: 'ny' };
      const id = newId();
      const ref = c.db.doc(`${COLLECTION}/${c.uid}`);
      const write = async () => {
        let exists = docState.exists;
        if (!exists) { try { exists = (await ref.get()).exists; } catch (e) { exists = false; } }
        if (exists) {
          await ref.update({ items: { [id]: entry }, updatedAt: now });
        } else {
          let name = '';
          try { name = (await c.user.profiles([c.uid]))[c.uid]?.name || ''; } catch (e) { name = ''; }
          await ref.set({ authorName: name, updatedAt: now, items: { [id]: entry } });
        }
      };
      try {
        try { await write(); } catch (e) {
          if (codeOf(e) !== 'unavailable') throw e;
          await new Promise((r) => setTimeout(r, 600 + Math.random() * 600));
          await write();
        }
        docState = { exists: true, items: { ...docState.items, [id]: entry } };
        renderHistory();
        ui.text.value = '';
        setMsg('ok', T.tack);
      } catch (e) {
        setMsg('err', errorText(T, codeOf(e)));
      } finally {
        busy = false; syncSend();
      }
    }

    btn.addEventListener('click', () => {
      if (!dlg) build();
      ui.viewLabel = String(viewOf() || '').replace(/\s+/g, ' ').trim().slice(0, 200);
      ui.where.textContent = ui.viewLabel ? `${T.fran}: ${tool} › ${ui.viewLabel}` : `${T.fran}: ${tool}`;
      if (ui.msg.classList.contains('ok')) setMsg('', '');
      syncSend();
      dlg.showModal();
      ui.text.focus();
      connect();
    });
  }

  root.PrimoraFeedback = { mount };
})(typeof window !== 'undefined' ? window : globalThis);
