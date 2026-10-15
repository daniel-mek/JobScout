/* Scout dashboard. One Cloudflare Worker, one KV namespace, four pages, a password.
 *
 * Where the data comes from: the GitHub Actions cron (scout/sync.py push) POSTs each run's matches,
 * page-watcher state, and config text to /api/ingest with the INGEST_SECRET. The Worker keeps them in KV.
 * Where the data goes: tracker changes, "Prep this" taps, and "Pass" taps are stored in KV and pulled
 * back into data/ by the next cron run (scout/sync.py pull), so the repo stays the long-term record.
 *
 * Pages (all behind the password):   /  New   /programs   /tracker   /settings
 * JSON (cookie):                     POST /api/tracker  POST /api/queue  POST /api/pass
 * JSON (secret header):              POST /api/ingest   GET /api/export
 * Open:                              GET /login  POST /login  GET /logout  GET /api/health
 */

import tokens from "./tokens.css";

const STATES = ["Found", "Saved", "Prepped", "Applied", "OA", "Interview", "Offer", "Rejected", "Withdrawn", "Passed"];
const COOKIE = "scout";
const COOKIE_DAYS = 30;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (path === "/api/health") return json({ ok: true, time: new Date().toISOString() });
    if (path === "/login") return request.method === "POST" ? login(request, env) : page(loginForm(""), "Scout", false);
    if (path === "/logout") return redirect("/login", { "Set-Cookie": `${COOKIE}=; Path=/; Max-Age=0` });

    // Cron endpoints: a shared secret, no cookie.
    if (path === "/api/ingest" || path === "/api/export") {
      if (!env.INGEST_SECRET || request.headers.get("x-scout-secret") !== env.INGEST_SECRET) return json({ error: "unauthorized" }, 401);
      return path === "/api/ingest" ? ingest(request, env) : exportState(env);
    }

    // Everything else needs the login cookie.
    if (!(await validCookie(request, env))) {
      return path.startsWith("/api/") ? json({ error: "unauthorized" }, 401) : redirect("/login");
    }
    if (request.method === "POST") {
      if (path === "/api/tracker") return setTracker(request, env);
      if (path === "/api/queue") return setQueue(request, env);
      if (path === "/api/pass") return setPassed(request, env);
      return json({ error: "not found" }, 404);
    }
    if (path === "/") return newPage(env);
    if (path === "/programs") return programsPage(env);
    if (path === "/tracker") return trackerPage(env);
    if (path === "/settings") return settingsPage(env);
    return new Response("not found", { status: 404 });
  },
};

/* ---------------------------------------------------------------- auth */

async function login(request, env) {
  const form = await request.formData();
  const given = String(form.get("password") || "");
  if (!env.DASH_PASSWORD || !(await sameSecret(given, env.DASH_PASSWORD))) {
    return page(loginForm("Wrong password."), "Scout", false, 401);
  }
  const expires = Date.now() + COOKIE_DAYS * 86400e3;
  const token = `${expires}.${await hmac(env.SESSION_SECRET, String(expires))}`;
  return redirect("/", {
    "Set-Cookie": `${COOKIE}=${token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${COOKIE_DAYS * 86400}`,
  });
}

async function validCookie(request, env) {
  const raw = (request.headers.get("Cookie") || "").split(";").map((c) => c.trim()).find((c) => c.startsWith(COOKIE + "="));
  if (!raw || !env.SESSION_SECRET) return false;
  const [expires, sig] = raw.slice(COOKIE.length + 1).split(".");
  if (!expires || !sig || Number(expires) < Date.now()) return false;
  return sameSecret(sig, await hmac(env.SESSION_SECRET, expires));
}

async function hmac(secret, text) {
  const key = await crypto.subtle.importKey("raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(text));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Compare two strings without leaking their length or where they differ: hash both, compare the hashes.
async function sameSecret(a, b) {
  const h = async (s) => new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)));
  const [x, y] = await Promise.all([h(a), h(b)]);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

/* ---------------------------------------------------------------- KV helpers */

const get = (env, key, fallback) => env.SCOUT.get(key, "json").then((v) => v ?? fallback);
const put = (env, key, value) => env.SCOUT.put(key, JSON.stringify(value));

/* ---------------------------------------------------------------- cron endpoints */

async function ingest(request, env) {
  const body = await request.json().catch(() => null);
  if (!body || !Array.isArray(body.matches)) return json({ error: "expected { matches: [...] }" }, 400);
  await Promise.all([
    put(env, "matches", { generated_at: body.generated_at || new Date().toISOString(), counts: body.counts || {}, matches: body.matches }),
    put(env, "pages", body.pages || {}),
    put(env, "config_text", body.config_text || {}),
  ]);
  // The repo is the long-term record for the tracker; the cron pushes its copy up so edits made
  // through /status on the Mac also show here. Phone edits are newer when their "updated" is later.
  if (body.tracker) {
    const mine = await get(env, "tracker", {});
    for (const [key, row] of Object.entries(body.tracker)) {
      if (!mine[key] || (row.updated || "") >= (mine[key].updated || "")) mine[key] = row;
    }
    await put(env, "tracker", mine);
  }
  return json({ ok: true, matches: body.matches.length });
}

async function exportState(env) {
  const [tracker, queue, passed] = await Promise.all([get(env, "tracker", {}), get(env, "queue", []), get(env, "passed", {})]);
  return json({ tracker, queue, passed });
}

/* ---------------------------------------------------------------- phone actions */

async function setTracker(request, env) {
  const body = await request.json().catch(() => ({}));
  const { key, state, next } = body;
  if (!key || !STATES.includes(state)) return json({ error: "need key and a known state" }, 400);
  const [tracker, data] = await Promise.all([get(env, "tracker", {}), get(env, "matches", { matches: [] })]);
  const match = data.matches.find((m) => m.key === key) || {};
  const today = new Date().toISOString().slice(0, 10);
  const row = tracker[key] || { company: match.company || "", title: match.title || "", url: match.url || "", score: match.score ?? null, history: [] };
  row.state = state;
  row.updated = today;
  if (state === "Applied" && !row.applied) row.applied = today;
  if (typeof next === "string") row.next = next;
  row.history.push({ date: today, state });
  tracker[key] = row;
  await put(env, "tracker", tracker);
  return json({ ok: true, row });
}

async function setQueue(request, env) {
  const { key, action } = await request.json().catch(() => ({}));
  if (!key) return json({ error: "need key" }, 400);
  let queue = await get(env, "queue", []);
  queue = queue.filter((q) => q.key !== key);
  if (action !== "remove") queue.push({ key, at: new Date().toISOString() });
  await put(env, "queue", queue);
  return json({ ok: true, queued: action !== "remove" });
}

async function setPassed(request, env) {
  const { key, undo } = await request.json().catch(() => ({}));
  if (!key) return json({ error: "need key" }, 400);
  const passed = await get(env, "passed", {});
  if (undo) delete passed[key]; else passed[key] = new Date().toISOString();
  await put(env, "passed", passed);
  return json({ ok: true, passed: !undo });
}

/* ---------------------------------------------------------------- pages */

async function newPage(env) {
  const [data, tracker, queue, passed, lastVisit] = await Promise.all([
    get(env, "matches", { matches: [], counts: {}, generated_at: "" }), get(env, "tracker", {}), get(env, "queue", []), get(env, "passed", {}), get(env, "last_visit", ""),
  ]);
  const queued = new Set(queue.map((q) => q.key));
  const rows = data.matches.filter((m) => !tracker[m.key] && !passed[m.key]);
  const fresh = rows.filter((m) => m.first_seen && m.first_seen > lastVisit);
  const rest = rows.filter((m) => !fresh.includes(m));
  await put(env, "last_visit", new Date().toISOString());

  const card = (m) => `
    <article class="card" data-key="${esc(m.key)}">
      <div class="row"><strong>${esc(m.company)}</strong><span class="score">${m.score}</span></div>
      <div class="title">${esc(m.title)}</div>
      <div class="meta">${esc((m.locations || []).slice(0, 2).join(", ") || "location not listed")} · ${age(m.date_posted)} · ${esc(m.eligibility || "unknown")}</div>
      <div class="meta mono">${esc(breakdown(m))}</div>
      ${m.early_career === "strong" ? '<div class="tag">freshman / sophomore program</div>' : ""}
      <div class="actions">
        <a class="btn ghost" href="${esc(m.url)}" target="_blank" rel="noopener">Open posting</a>
        <button class="btn" data-act="queue" ${queued.has(m.key) ? "disabled" : ""}>${queued.has(m.key) ? "Queued for /prep" : "Prep this"}</button>
        <button class="btn ghost" data-act="pass">Pass</button>
      </div>
    </article>`;

  const body = `
    <p class="muted">${rows.length} open matches · updated ${esc(when(data.generated_at))} · ${queue.length} queued for /prep</p>
    ${fresh.length ? `<h2>New since your last visit (${fresh.length})</h2>${fresh.map(card).join("")}` : ""}
    <h2>${fresh.length ? "Everything else" : "Top matches"}</h2>
    ${rest.slice(0, 60).map(card).join("") || '<p class="muted">Nothing yet. The cron fills this in.</p>'}`;
  return page(body, "New");
}

async function programsPage(env) {
  const [pages, data, tracker, passed] = await Promise.all([get(env, "pages", {}), get(env, "matches", { matches: [] }), get(env, "tracker", {}), get(env, "passed", {})]);
  const watched = Object.entries(pages).map(([url, p]) => `
    <article class="card">
      <div class="row"><strong>${esc(p.name || url)}</strong><span class="meta">${p.changed_at ? "changed " + age(p.changed_at) : "no change yet"}</span></div>
      <div class="meta">checked ${age(p.checked_at)} · ${p.text_len || 0} chars${p.failures ? ` · <span class="warn">${p.failures} failed fetch(es)</span>` : ""}</div>
      <div class="actions"><a class="btn ghost" href="${esc(url)}" target="_blank" rel="noopener">Open page</a></div>
    </article>`).join("");
  const finds = data.matches.filter((m) => (m.early_career === "strong" || m.role === "ambassador") && !passed[m.key]).map((m) => `
    <article class="card">
      <div class="row"><strong>${esc(m.company)}</strong><span class="score">${m.score}</span></div>
      <div class="title">${esc(m.title)}</div>
      <div class="meta">${esc((m.locations || []).slice(0, 2).join(", "))} · ${age(m.date_posted)} · ${tracker[m.key] ? esc(tracker[m.key].state) : "not tracked"}</div>
      <div class="actions"><a class="btn ghost" href="${esc(m.url)}" target="_blank" rel="noopener">Open posting</a></div>
    </article>`).join("");
  return page(`<h2>Watched program pages</h2>${watched || '<p class="muted">No pages yet.</p>'}<h2>Early-career finds in the lists</h2>${finds || '<p class="muted">None in the lists right now. The watched pages above are where these usually show up first.</p>'}`, "Programs");
}

async function trackerPage(env) {
  const tracker = await get(env, "tracker", {});
  const rows = Object.entries(tracker).filter(([, r]) => r.state !== "Passed").sort((a, b) => (b[1].updated || "").localeCompare(a[1].updated || ""));
  const options = (cur) => STATES.filter((s) => s !== "Passed").map((s) => `<option ${s === cur ? "selected" : ""}>${s}</option>`).join("");
  const list = rows.map(([key, r]) => `
    <article class="card" data-key="${esc(key)}">
      <div class="row"><strong>${esc(r.company)}</strong><span class="meta">${esc(r.updated || "")}</span></div>
      <div class="title">${esc(r.title)}</div>
      <div class="meta">${r.applied ? "applied " + esc(r.applied) + " · " : ""}${r.next ? "next: " + esc(r.next) : ""}</div>
      <div class="actions">
        <select data-act="state">${options(r.state)}</select>
        <input data-act="next" placeholder="next action" value="${esc(r.next || "")}">
        <button class="btn" data-act="save">Save</button>
        ${r.url ? `<a class="btn ghost" href="${esc(r.url)}" target="_blank" rel="noopener">Posting</a>` : ""}
      </div>
    </article>`).join("");
  return page(`<p class="muted">${rows.length} tracked. Changes here reach the repo on the next cron run.</p>${list || '<p class="muted">Nothing tracked yet. Tap "Prep this" on the New page, or run /prep.</p>'}`, "Tracker");
}

async function settingsPage(env) {
  const cfg = await get(env, "config_text", {});
  const block = (name, text) => `<h2>${esc(name)}</h2><pre>${esc(text || "(not pushed yet)")}</pre>`;
  return page(`<p class="muted">Read-only. Edit these files in the repo; the next cron run shows the change here.</p>${block("config/targets.yaml", cfg.targets)}${block("config/scoring.yaml", cfg.scoring)}${block("config/watch-pages.yaml", cfg.watch_pages)}`, "Settings");
}

/* ---------------------------------------------------------------- html */

function page(body, title, nav = true, status = 200) {
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Scout · ${esc(title)}</title><style>${tokens}${BASE_CSS}</style></head><body>
<header><a class="brand" href="/">Scout</a>${nav ? NAV : ""}</header>
<main>${nav ? `<h1>${esc(title)}</h1>` : ""}${body}</main>
${nav ? `<script>${CLIENT_JS}</script>` : ""}</body></html>`;
  return new Response(html, { status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
}

const NAV = `<nav><a href="/">New</a><a href="/programs">Programs</a><a href="/tracker">Tracker</a><a href="/settings">Settings</a><a href="/logout" class="muted">Log out</a></nav>`;

function loginForm(message) {
  return `<form method="post" action="/login" class="login">
    <label for="password">Password</label>
    <input id="password" name="password" type="password" autocomplete="current-password" autofocus>
    <button class="btn" type="submit">Unlock</button>
    ${message ? `<p class="warn">${esc(message)}</p>` : ""}
  </form>`;
}

// Base layout. Colors and sizes come from tokens.css; this only arranges things.
const BASE_CSS = `
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:var(--text)/1.45 var(--font);max-width:720px;margin-inline:auto;padding:0 var(--pad) 48px;overflow-x:hidden}
header{display:flex;align-items:center;justify-content:space-between;gap:var(--gap);padding:14px 0;border-bottom:1px solid var(--line);flex-wrap:wrap}
.brand{font-weight:700;text-decoration:none;color:var(--ink);font-size:18px}
nav{display:flex;gap:14px;flex-wrap:wrap} nav a{color:var(--accent);text-decoration:none;font-weight:600} nav a.muted{color:var(--muted);font-weight:400}
h1{font-size:var(--title);margin:18px 0 6px} h2{font-size:var(--text);color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin:22px 0 8px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:var(--pad);margin:0 0 var(--gap);max-width:100%}
.row{display:flex;justify-content:space-between;align-items:baseline;gap:var(--gap)} .title{margin:2px 0 4px} .meta{color:var(--muted);font-size:var(--small);margin-top:2px;overflow-wrap:anywhere}
.mono{font-family:var(--mono)} .score{font-family:var(--mono);font-weight:700;color:var(--accent)} .muted{color:var(--muted)} .warn{color:var(--warn)}
.tag{display:inline-block;margin-top:6px;padding:2px 8px;border-radius:999px;background:var(--accent);color:var(--accent-ink);font-size:var(--small);font-weight:600}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;align-items:center}
.btn{appearance:none;border:1px solid var(--accent);background:var(--accent);color:var(--accent-ink);border-radius:999px;padding:8px 14px;font:inherit;font-size:var(--small);font-weight:600;text-decoration:none;cursor:pointer}
.btn.ghost{background:transparent;color:var(--accent)} .btn[disabled]{opacity:.55;cursor:default}
select,input{font:inherit;font-size:var(--small);padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--ink);max-width:100%}
input{flex:1;min-width:140px} pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);padding:var(--pad);font-size:var(--small)}
.login{display:flex;flex-direction:column;gap:10px;max-width:320px;margin:60px auto} .login label{font-weight:600}
`;

// The only JavaScript the pages need: send a tap to the API and update the card in place.
const CLIENT_JS = `
async function post(url, body){const r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});if(!r.ok){alert("That didn't save. Try again.");throw new Error(r.status)}return r.json()}
document.addEventListener("click",async(e)=>{const b=e.target.closest("button[data-act]");if(!b)return;const card=b.closest("[data-key]");const key=card&&card.dataset.key;if(!key)return;
 if(b.dataset.act==="queue"){await post("/api/queue",{key});b.textContent="Queued for /prep";b.disabled=true}
 else if(b.dataset.act==="pass"){await post("/api/pass",{key});card.style.opacity=.35;b.textContent="Passed"}
 else if(b.dataset.act==="save"){const state=card.querySelector('[data-act="state"]').value;const next=card.querySelector('[data-act="next"]').value;await post("/api/tracker",{key,state,next});b.textContent="Saved";setTimeout(()=>b.textContent="Save",1500)}
});`;

/* ---------------------------------------------------------------- small helpers */

function breakdown(m) {
  const b = m.breakdown || {};
  return `role ${m.role} ${b.role ?? 0} + tier ${m.tier} ${b.tier ?? 0} + early ${b.early_career ?? 0} + deg ${b.degrees ?? 0} + loc ${b.location ?? 0} + fresh ${b.freshness ?? 0} + kw ${b.keywords ?? 0}`;
}
function age(ts) {
  if (!ts) return "?";
  const sec = typeof ts === "number" ? ts : Date.parse(ts) / 1000;
  const days = Math.floor((Date.now() / 1000 - sec) / 86400);
  return days <= 0 ? "today" : days === 1 ? "1 day ago" : `${days} days ago`;
}
function when(iso) {
  if (!iso) return "never";
  return new Date(iso).toLocaleString("en-US", { timeZone: "America/New_York", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}
function redirect(to, headers = {}) {
  return new Response(null, { status: 302, headers: { Location: to, ...headers } });
}
