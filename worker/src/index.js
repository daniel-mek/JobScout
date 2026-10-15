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
    if (path === "/login") return request.method === "POST" ? login(request, env) : loginForm("");
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
    return loginForm("nope. try again.");
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
  const programs = rows.filter((m) => m.early_career === "strong" || m.role === "ambassador").length;
  await put(env, "last_visit", new Date().toISOString());

  const card = (m, isNew) => `
    <article class="card${isNew ? " is-new" : ""}" data-key="${esc(m.key)}">
      <div class="tags">
        <span class="tag">${esc(roleWord(m))}</span>
        ${m.tier <= 2 ? `<span class="tag ink">tier ${m.tier}</span>` : ""}
        ${m.early_career === "strong" ? '<span class="tag accent">freshman friendly</span>' : ""}
        ${m.eligibility === "ineligible" ? '<span class="tag red">not eligible</span>' : ""}
        ${isNew ? '<span class="tag accent">new</span>' : ""}
      </div>
      <div class="row"><h3>${esc(m.company)}</h3><span class="score">${m.score}</span></div>
      <div class="title">${esc(m.title)}</div>
      <div class="meta">${esc((m.locations || []).slice(0, 2).join(", ") || "location not listed")} · ${age(m.date_posted)}${m.eligibility_note && m.eligibility !== "unknown" ? " · " + esc(m.eligibility_note) : ""}</div>
      <details class="why"><summary>why ${m.score}?</summary><div class="meta mono">${esc(breakdown(m))}</div></details>
      <div class="actions">
        <button class="btn accent" data-act="queue" ${queued.has(m.key) ? "disabled" : ""}>${queued.has(m.key) ? "queued for /prep" : "prep this"}</button>
        <button class="btn" data-act="pass">pass</button>
        <a class="btn ghost" href="${esc(m.url)}" target="_blank" rel="noopener">posting ↗</a>
      </div>
    </article>`;

  const hero = `
    <div class="stat">
      <div class="stat-label">you have</div>
      <div class="stat-big">${rows.length}</div>
      <div class="stat-sub">open matches${fresh.length ? `, <b>${fresh.length} new</b> since your last visit` : ", none new since your last visit"}</div>
      <div class="stat-foot">${programs} freshman friendly · ${queue.length} queued for /prep · updated ${esc(when(data.generated_at))}</div>
    </div>`;

  const body = `
    ${hero}
    ${fresh.length ? `<h2>fresh off the lists</h2>${fresh.map((m) => card(m, true)).join("")}` : ""}
    <h2>${fresh.length ? "the rest, best first" : "best first"}</h2>
    ${rest.slice(0, 60).map((m) => card(m, false)).join("") || '<p class="note">nothing yet. the cron fills this in every three hours.</p>'}`;
  return page(body, { title: "New", page: "new", lead: "let's get", head: "you hired" });
}

async function programsPage(env) {
  const [pages, data, tracker, passed] = await Promise.all([get(env, "pages", {}), get(env, "matches", { matches: [] }), get(env, "tracker", {}), get(env, "passed", {})]);
  const watched = Object.entries(pages).map(([url, p]) => `
    <article class="card">
      <div class="tags"><span class="tag">${p.changed_at ? "changed " + age(p.changed_at) : "quiet"}</span>${p.failures ? `<span class="tag red">${p.failures} failed fetch${p.failures > 1 ? "es" : ""}</span>` : ""}</div>
      <h3>${esc(p.name || url)}</h3>
      <div class="meta">checked ${age(p.checked_at)} · ${p.text_len || 0} characters of text</div>
      <div class="actions"><a class="btn ghost" href="${esc(url)}" target="_blank" rel="noopener">open page ↗</a></div>
    </article>`).join("");
  const finds = data.matches.filter((m) => (m.early_career === "strong" || m.role === "ambassador") && !passed[m.key]).map((m) => `
    <article class="card">
      <div class="tags"><span class="tag accent">${m.role === "ambassador" ? "ambassador" : "freshman friendly"}</span>${tracker[m.key] ? `<span class="tag ink">${esc(tracker[m.key].state)}</span>` : ""}</div>
      <div class="row"><h3>${esc(m.company)}</h3><span class="score">${m.score}</span></div>
      <div class="title">${esc(m.title)}</div>
      <div class="meta">${esc((m.locations || []).slice(0, 2).join(", "))} · ${age(m.date_posted)}</div>
      <div class="actions"><a class="btn ghost" href="${esc(m.url)}" target="_blank" rel="noopener">posting ↗</a></div>
    </article>`).join("");
  const body = `
    <p class="note">these pages are where freshman programs show up first. scout reads them every three hours and pings you when the words change.</p>
    <h2>watched pages</h2>${watched || '<p class="note">no pages yet.</p>'}
    <h2>found in the lists</h2>${finds || '<p class="note">none in the lists right now. the pages above are the early warning.</p>'}`;
  return page(body, { title: "Programs", page: "programs", lead: "built for", head: "freshmen" });
}

async function trackerPage(env) {
  const tracker = await get(env, "tracker", {});
  const rows = Object.entries(tracker).filter(([, r]) => r.state !== "Passed").sort((a, b) => (b[1].updated || "").localeCompare(a[1].updated || ""));
  const counts = {};
  for (const [, r] of rows) counts[r.state] = (counts[r.state] || 0) + 1;
  const options = (cur) => STATES.filter((s) => s !== "Passed").map((s) => `<option ${s === cur ? "selected" : ""}>${s}</option>`).join("");
  const pipeline = ["Prepped", "Applied", "OA", "Interview", "Offer"].map((s) => `<span class="step${counts[s] ? " on" : ""}">${s}<b>${counts[s] || 0}</b></span>`).join("");
  const list = rows.map(([key, r]) => `
    <article class="card" data-key="${esc(key)}">
      <div class="tags"><span class="tag ${r.state === "Applied" || r.state === "Offer" ? "green" : r.state === "Rejected" ? "red" : "ink"}">${esc(r.state)}</span><span class="tag">${esc(r.updated || "")}</span></div>
      <div class="row"><h3>${esc(r.company)}</h3>${r.score != null ? `<span class="score">${r.score}</span>` : ""}</div>
      <div class="title">${esc(r.title)}</div>
      <div class="meta">${r.applied ? "applied " + esc(r.applied) + " · " : ""}${r.next ? "next: " + esc(r.next) : "no next action yet"}</div>
      <div class="actions wrap">
        <select data-act="state">${options(r.state)}</select>
        <input data-act="next" placeholder="next action" value="${esc(r.next || "")}">
        <button class="btn accent" data-act="save">save</button>
        ${r.url ? `<a class="btn ghost" href="${esc(r.url)}" target="_blank" rel="noopener">posting ↗</a>` : ""}
      </div>
    </article>`).join("");
  const body = `
    <div class="pipeline">${pipeline}</div>
    <p class="note">${rows.length} tracked. changes here reach the repo on the next cron run. you still click submit yourself.</p>
    ${list || '<p class="note">nothing tracked yet. tap "prep this" on New, or run /prep.</p>'}`;
  return page(body, { title: "Tracker", page: "tracker", lead: "where", head: "things stand" });
}

async function settingsPage(env) {
  const cfg = await get(env, "config_text", {});
  const block = (name, text) => `<h2>${esc(name)}</h2><pre>${esc(text || "(not pushed yet)")}</pre>`;
  const body = `<p class="note">read only. edit these files in the repo and the next cron run shows the change here.</p>${block("config/targets.yaml", cfg.targets)}${block("config/scoring.yaml", cfg.scoring)}${block("config/watch-pages.yaml", cfg.watch_pages)}`;
  return page(body, { title: "Settings", page: "settings", lead: "how scout", head: "thinks" });
}

/* ---------------------------------------------------------------- html */

function page(body, opts, status = 200) {
  const { title, page: name, lead, head, nav = true } = opts;
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="${PAGE_COLORS[name] || "#cf6a2e"}">
<link rel="icon" href="${FAVICON}"><title>Scout · ${esc(title)}</title><style>${tokens}${BASE_CSS}</style></head><body data-page="${esc(name)}">
<header><a class="brand" href="/"><i></i>scout</a>${nav ? '<a class="pill-link" href="/logout">log out</a>' : ""}</header>
<main>
  <h1><span class="lead">${esc(lead)}</span><span class="head">${esc(head)}</span></h1>
  ${body}
</main>
${nav ? NAV.replace(`href="/${name === "new" ? "" : name}"`, `href="/${name === "new" ? "" : name}" class="on"`) : ""}
${nav ? `<script>${CLIENT_JS}</script>` : ""}</body></html>`;
  return new Response(html, { status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
}

const FAVICON = "data:image/svg+xml," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="16" fill="#1a1333"/><circle cx="32" cy="32" r="14" fill="#ffc93c" stroke="#f6f9dc" stroke-width="4"/></svg>');

const PAGE_COLORS = { new: "#cf6a2e", programs: "#9b84d8", tracker: "#3fa9b5", settings: "#e7c98f", login: "#9b84d8" };

const NAV = `<nav class="dock"><a href="/">new</a><a href="/programs">programs</a><a href="/tracker">tracker</a><a href="/settings">settings</a></nav>`;

function loginForm(message) {
  return page(`<form method="post" action="/login" class="login">
    <label for="password">password</label>
    <input id="password" name="password" type="password" autocomplete="current-password" autofocus>
    <button class="btn accent big" type="submit">let me in</button>
    ${message ? `<p class="warn">${esc(message)}</p>` : '<p class="note">it stays unlocked for 30 days.</p>'}
  </form>`, { title: "Log in", page: "login", lead: "who goes", head: "there?", nav: false }, message ? 401 : 200);
}

// Layout only. Colors, sizes, and fonts come from tokens.css.
const BASE_CSS = `
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:500 var(--text)/1.4 var(--font);padding:0 16px 96px;overflow-x:hidden;-webkit-font-smoothing:antialiased}
body[data-page="new"]{--page:var(--orange)} body[data-page="programs"]{--page:var(--purple)} body[data-page="tracker"]{--page:var(--teal)} body[data-page="settings"]{--page:var(--sand);--on-page:var(--ink)} body[data-page="login"]{--page:var(--purple)}
main{max-width:640px;margin-inline:auto}
header{max-width:640px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;padding:18px 0 6px}
.brand{display:inline-flex;align-items:center;gap:8px;font-family:var(--display);font-size:22px;color:var(--ink);text-decoration:none;background:var(--cream);border:var(--line) solid var(--ink);border-radius:var(--radius-pill);padding:6px 16px 6px 12px;box-shadow:var(--shadow-sm);letter-spacing:.3px}
.brand i{width:14px;height:14px;border-radius:50%;background:var(--accent);border:var(--line) solid var(--ink);display:inline-block}
.pill-link{font-size:var(--small);font-weight:700;color:var(--ink);background:var(--cream);border:var(--line) solid var(--ink);border-radius:var(--radius-pill);padding:6px 14px;text-decoration:none;box-shadow:var(--shadow-sm)}
h1{font-family:var(--display);font-size:var(--h1);line-height:.92;text-transform:uppercase;margin:14px 0 20px;letter-spacing:0}
h1 .lead{display:block;color:var(--on-page)} h1 .head{display:inline-block;color:var(--ink);border-bottom:6px solid var(--accent);padding-bottom:2px}
h2{font-family:var(--display);font-size:20px;text-transform:uppercase;color:var(--on-page);margin:26px 0 10px;letter-spacing:0}
h3{font-family:var(--display);font-size:20px;margin:0;text-transform:uppercase;line-height:1.05;letter-spacing:0}
.note{color:var(--on-page);font-weight:700;margin:0 0 14px}
.stat{background:var(--cream);border:var(--line) solid var(--ink);border-radius:var(--radius);box-shadow:var(--shadow);padding:var(--pad);margin-bottom:8px}
.stat-label{font-family:var(--display);text-transform:uppercase;font-size:18px;letter-spacing:0}
.stat-big{font-family:var(--display);font-size:var(--big);line-height:.9;text-transform:uppercase;margin:4px 0 6px}
.stat-sub{font-weight:700;font-size:18px} .stat-sub b{background:var(--accent);border-radius:6px;padding:0 6px;border:2px solid var(--ink)}
.stat-foot{color:var(--muted);font-size:var(--small);font-weight:700;margin-top:10px}
.card{background:var(--cream);border:var(--line) solid var(--ink);border-radius:var(--radius);box-shadow:var(--shadow);padding:var(--pad);margin:0 0 16px;max-width:100%}
.card.is-new{outline:4px solid var(--accent);outline-offset:-7px}
.row{display:flex;justify-content:space-between;align-items:flex-start;gap:var(--gap)}
.title{font-weight:700;font-size:17px;margin:4px 0 6px} .meta{color:var(--muted);font-size:var(--small);font-weight:700;overflow-wrap:anywhere}
.mono{font-family:var(--mono);font-weight:500}
.score{font-family:var(--display);font-size:18px;background:var(--ink);color:var(--accent);border-radius:var(--radius-pill);padding:4px 12px;flex:none;line-height:1.1}
.tags{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
.tag{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;border:2px solid var(--ink);border-radius:var(--radius-tag);padding:3px 9px;background:var(--orange);color:var(--cream)}
.tag.accent{background:var(--accent);color:var(--ink)} .tag.ink{background:var(--ink);color:var(--cream)} .tag.red{background:var(--red);color:var(--cream)} .tag.green{background:var(--green);color:var(--ink)}
.why{margin-top:8px} .why summary{cursor:pointer;font-size:var(--small);font-weight:700;color:var(--muted)} .why summary::-webkit-details-marker{display:none}
.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;align-items:center}
.btn{appearance:none;font:700 15px/1 var(--font);color:var(--ink);background:var(--cream);border:var(--line) solid var(--ink);border-radius:var(--radius-pill);padding:11px 16px;box-shadow:var(--shadow-sm);text-decoration:none;cursor:pointer;transition:transform .08s,box-shadow .08s}
.btn:active{transform:translate(3px,3px);box-shadow:0 0 0 var(--ink)}
.btn.accent{background:var(--accent)} .btn.ghost{background:transparent;box-shadow:none} .btn.big{font-size:18px;padding:14px 22px}
.btn[disabled]{background:var(--sand);color:var(--muted);box-shadow:none;cursor:default;transform:none}
select,input{font:700 15px var(--font);padding:10px 12px;border:var(--line) solid var(--ink);border-radius:var(--radius-pill);background:#fff;color:var(--ink);max-width:100%;box-shadow:var(--shadow-sm)}
input{flex:1;min-width:150px}
.pipeline{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 14px}
.step{font-size:12px;font-weight:700;background:var(--cream);border:2px solid var(--ink);border-radius:var(--radius-pill);padding:5px 10px;color:var(--muted)} .step.on{color:var(--ink);background:var(--accent)} .step b{margin-left:6px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--cream);border:var(--line) solid var(--ink);border-radius:var(--radius);box-shadow:var(--shadow);padding:var(--pad);font-size:var(--small);font-weight:500}
.login{display:flex;flex-direction:column;gap:12px;max-width:360px;margin:10px auto 0;background:var(--cream);border:var(--line) solid var(--ink);border-radius:var(--radius);box-shadow:var(--shadow);padding:22px}
.login label{font-family:var(--display);text-transform:uppercase;font-size:18px} .login input{width:100%} .login .note{color:var(--muted);margin:0} .warn{color:var(--red);font-weight:700;margin:0}
.dock{position:fixed;left:0;right:0;bottom:0;display:flex;justify-content:center;gap:8px;padding:10px 12px calc(10px + env(safe-area-inset-bottom));background:var(--page);border-top:var(--line) solid var(--ink)}
.dock a{flex:1;max-width:150px;text-align:center;font:700 14px var(--font);color:var(--ink);background:var(--cream);border:var(--line) solid var(--ink);border-radius:var(--radius-pill);padding:11px 6px;text-decoration:none;box-shadow:var(--shadow-sm)}
.dock a.on{background:var(--accent)}
@media (min-width:700px){.dock{position:static;background:transparent;border:0;max-width:640px;margin:0 auto 20px;padding:0;justify-content:flex-start} body{padding-bottom:40px}}
/* Wider screens: use the room. The header, headline, and stat card stay full width; cards flow into columns. */
@media (min-width:900px){
  main,header,.dock{max-width:1120px}
  main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));column-gap:20px;align-items:start}
  main > h1,main > .stat,main > h2,main > .note,main > .pipeline,main > pre,main > form{grid-column:1 / -1}
  main > .card{margin-bottom:20px}
  h1{font-size:64px} .stat{display:grid;grid-template-columns:auto 1fr;column-gap:28px;align-items:end}
  .stat-label{grid-column:1} .stat-big{grid-column:1;grid-row:2} .stat-sub{grid-column:2;grid-row:2;padding-bottom:10px} .stat-foot{grid-column:1 / -1}
  .dock{justify-content:flex-start;gap:12px} .dock a{flex:none;min-width:150px}
}
@media (min-width:1400px){main{grid-template-columns:repeat(3,minmax(0,1fr))}}
`;

// The only JavaScript the pages need: send a tap to the API and update the card in place.
const CLIENT_JS = `
async function post(url, body){const r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});if(!r.ok){alert("that didn't save. try again.");throw new Error(r.status)}return r.json()}
document.addEventListener("click",async(e)=>{const b=e.target.closest("button[data-act]");if(!b)return;const card=b.closest("[data-key]");const key=card&&card.dataset.key;if(!key)return;
 if(b.dataset.act==="queue"){await post("/api/queue",{key});b.textContent="queued for /prep";b.disabled=true}
 else if(b.dataset.act==="pass"){await post("/api/pass",{key});card.style.opacity=.4;b.textContent="passed";b.disabled=true}
 else if(b.dataset.act==="save"){const state=card.querySelector('[data-act="state"]').value;const next=card.querySelector('[data-act="next"]').value;await post("/api/tracker",{key,state,next});b.textContent="saved";setTimeout(()=>b.textContent="save",1500)}
});`;

/* ---------------------------------------------------------------- small helpers */

function roleWord(m) {
  return { swe: "software", pm: "product", it: "IT", design: "design", ambassador: "ambassador", program: "program" }[m.role] || "match";
}

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
