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
import { ICONS } from "./icons.js";

const STATES = ["Found", "Saved", "Prepped", "Applied", "OA", "Interview", "Offer", "Rejected", "Withdrawn", "Passed"];
const COOKIE = "scout";
const COOKIE_DAYS = 30;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    // Home-screen icons and the web app manifest are public: iOS fetches them without the login cookie.
    if (ICONS[path]) return png(ICONS[path]);
    if (path === "/manifest.webmanifest") return manifest();
    if (path === "/api/health") return json({ ok: true, time: new Date().toISOString() });
    if (path === "/login") return request.method === "POST" ? login(request, env) : loginForm("");
    if (path === "/about") return aboutPage(await validCookie(request, env));
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
  const today = nyDate();
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
        <button class="btn accent" data-act="queue" ${queued.has(m.key) ? "disabled" : ""}>${queued.has(m.key) ? "queued ✓" : "prep this"}</button>
        <button class="btn" data-act="pass">pass</button>
        <a class="btn ghost" href="${esc(m.url)}" target="_blank" rel="noopener">posting ↗</a>
      </div>
    </article>`;

  const hero = `
    <div class="stat">
      <div class="stat-main">
        <div class="stat-label">you have</div>
        <div class="stat-big" id="open-count">${rows.length}</div>
        <div class="stat-sub">open matches</div>
      </div>
      <div class="stat-tiles">
        <div class="tile${fresh.length ? " hot" : ""}"><b>${fresh.length}</b><span>new since your last visit</span></div>
        <div class="tile"><b>${programs}</b><span>freshman friendly</span></div>
        <div class="tile"><b>${queue.length}</b><span>queued for /prep</span></div>
      </div>
      <div class="stat-foot">updated ${esc(when(data.generated_at))}</div>
    </div>`;


  const passedRows = data.matches.filter((m) => passed[m.key] && !tracker[m.key]);
  const passedCard = (m) => `
    <article class="card passed" data-key="${esc(m.key)}">
      <div class="row"><h3>${esc(m.company)}</h3><span class="score">${m.score}</span></div>
      <div class="title">${esc(m.title)}</div>
      <div class="meta">passed ${age(passed[m.key])}</div>
      <div class="actions"><button class="btn accent" data-act="unpass">unpass</button><a class="btn ghost" href="${esc(m.url)}" target="_blank" rel="noopener">posting ↗</a></div>
    </article>`;

  const body = `
    ${hero}
    ${fresh.length ? `<h2>fresh off the lists</h2>${fresh.map((m) => card(m, true)).join("")}` : ""}
    <h2>${fresh.length ? "the rest, best first" : "best first"}</h2>
    ${rest.slice(0, 60).map((m) => card(m, false)).join("") || '<p class="note">nothing yet. scout checks the lists every hour.</p>'}
    <details class="passed-list" id="passed" ${passedRows.length ? "" : "hidden"}><summary><h2>passed (<span id="passed-count">${passedRows.length}</span>)</h2></summary><p class="note">changed your mind? unpass puts it back in the list.</p><div id="passed-cards">${passedRows.map(passedCard).join("")}</div></details>`;
  return page(body, { title: "New", page: "new", lead: "let's get", head: "you hired" });
}

async function programsPage(env) {
  const [pages, data, tracker, passed] = await Promise.all([get(env, "pages", {}), get(env, "matches", { matches: [] }), get(env, "tracker", {}), get(env, "passed", {})]);
  const watched = Object.entries(pages).map(([url, p]) => `
    <article class="card">
      <div class="tags"><span class="tag${p.changed_at ? " accent" : ""}">${p.changed_at ? "new words " + age(p.changed_at) : "no changes yet"}</span>${p.failures ? `<span class="tag red">${p.failures} failed fetch${p.failures > 1 ? "es" : ""}</span>` : ""}</div>
      <h3>${esc(p.name || url)}</h3>
      ${p.last_change ? `<div class="change"><b>what changed:</b>${esc(p.last_change).replace(/\n/g, "<br>")}</div><div class="meta">a change means go look. it does not mean applications are open.</div>` : ""}<div class="meta">checked ${age(p.checked_at)}</div>
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
    <p class="note">these pages are where freshman programs show up first. scout reads them every hour and pings you when the words change.</p>
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
        <textarea data-act="next" rows="1" placeholder="next action">${esc(r.next || "")}</textarea>
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

/* ---------------------------------------------------------------- about (public: no personal data) */

function aboutPage(loggedIn) {
  const body = `
    <article class="card">
      <h3>the short version</h3>
      <p>Scout watches the public internship lists every hour, scores every posting against what you're looking for, and pings your phone when a strong one shows up. When you pick one, it builds a prep kit: a tailored one page resume, a cover letter if the posting wants one, and draft answers, all from facts you've already confirmed. <b>You always click submit yourself.</b> Scout never applies for you.</p>
    </article>

    <h2>how it works</h2>
    <ol class="steps">
      <li class="card"><h3>find</h3><p>Every hour a free GitHub Actions job pulls two public internship lists (Simplify and Pitt CSC, plus a community list) and reads a handful of company program pages, like Microsoft Explore and NVIDIA's university page, for changes.</p></li>
      <li class="card"><h3>score</h3><p>Each posting gets a score out of 100 from plain rules you can read and change: the role (software, product, IT, design, ambassador), the company tier, whether it's built for freshmen and sophomores, the degree it asks for, where it is, and how fresh it is. Tap "why 86?" on any card to see the math.</p></li>
      <li class="card"><h3>alert</h3><p>Big companies with a strong score, any freshman or sophomore program, any ambassador role, and any change on a watched program page push to your phone right away through the free ntfy app. Everything else waits for one digest at 7:00 PM.</p></li>
      <li class="card"><h3>prep</h3><p>Tap "prep this" and the posting waits in a queue. Next time you open Claude Code, /prep reads the posting, checks whether you're eligible, drafts the kit from your master profile, and then a second reviewer pass checks every line against what you've actually done before you see it.</p></li>
      <li class="card"><h3>track</h3><p>The tracker follows each application from prepped to applied, online assessment, interview, and offer, and you can update it from your phone.</p></li>
    </ol>

    <h2>the rules it follows</h2>
    <article class="card"><ul>
      <li><b>It never applies for you</b>, never logs into a job site, and never creates accounts.</li>
      <li><b>It never invents experience.</b> A tailored resume can only pick, reorder, and reword facts you've confirmed. If a posting wants something you don't have, it says so instead of faking it.</li>
      <li><b>Postings are just text.</b> If a posting contains instructions, Scout ignores them.</li>
      <li><b>It costs nothing.</b> GitHub Actions, Cloudflare, and ntfy on their free tiers, and the AI parts run inside a Claude Code session you start.</li>
      <li><b>Your data stays yours.</b> Your resume, answers, and applications never go into the public code.</li>
    </ul></article>

    <h2>where it's going</h2>
    <article class="card"><p>Right now Scout is tuned for one first-year computer science student looking at tech internships. The plan is for it to work for anyone looking for an internship or a job, whatever their major or career: the scoring is already driven by an editable config file, so the next step is more sources for more fields and a setup that asks what you're looking for and writes that config for you.</p>
      <div class="actions"><a class="btn accent" href="https://github.com/jeremiah123-luma/scout" target="_blank" rel="noopener">see the code ↗</a>${loggedIn ? '<a class="btn" href="/">back to scout</a>' : '<a class="btn" href="/login">log in</a>'}</div>
    </article>`;
  return page(body, { title: "What is Scout", page: "about", lead: "what is", head: "scout?", nav: loggedIn });
}

/* ---------------------------------------------------------------- html */

function page(body, opts, status = 200) {
  const { title, page: name, lead, head, nav = true } = opts;
  const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="${PAGE_COLORS[name] || "#cf6a2e"}">
<link rel="icon" href="${FAVICON}"><link rel="apple-touch-icon" href="/apple-touch-icon.png"><link rel="manifest" href="/manifest.webmanifest"><meta name="apple-mobile-web-app-title" content="Scout"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-status-bar-style" content="default"><title>Scout · ${esc(title)}</title><style>${tokens}${BASE_CSS}</style></head><body data-page="${esc(name)}">
<header><a class="brand" href="/" aria-label="scout">sc<svg class="o" viewBox="0 0 62 62" aria-hidden="true"><circle cx="31" cy="31" r="26.5" fill="#ffc93c" stroke="#1a1333" stroke-width="9"/><circle cx="31" cy="31" r="11" fill="#f6f9dc" stroke="#1a1333" stroke-width="6"/><circle cx="31" cy="31" r="4" fill="#1a1333"/></svg>ut</a><span class="head-links">${name === "about" ? (nav ? "" : '<a class="pill-link" href="/login">log in</a>') : nav ? '<a class="pill-link q" href="/about" aria-label="what is scout?"><span class="long">what is scout?</span><span class="short">?</span></a>' : ""}${nav ? '<a class="pill-link" href="/logout">log out</a>' : ""}</span></header>
<main>
  <h1><span class="lead">${esc(lead)}</span><span class="head">${esc(head)}</span></h1>
  ${body}
</main>
${nav ? NAV.replace(`href="/${name === "new" ? "" : name}"`, `href="/${name === "new" ? "" : name}" class="on"`) : ""}
${nav ? `<script>${CLIENT_JS}</script>` : ""}<script>${CYCLE_JS}</script></body></html>`;
  return new Response(html, { status, headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store" } });
}

const FAVICON = "data:image/svg+xml," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><circle cx="32" cy="32" r="28" fill="#ffc93c" stroke="#1a1333" stroke-width="7"/><circle cx="32" cy="32" r="12" fill="#f6f9dc" stroke="#1a1333" stroke-width="5"/><circle cx="32" cy="32" r="4.5" fill="#1a1333"/></svg>');

// Rotates the headline decoration: zigzag, highlighter, circle, loops. Each draws in, holds, and hands off.
const CYCLE_JS = `(function(){var h=document.querySelector("h1 .head");if(!h)return;var s=["u-zig","u-highlight","u-circle","u-loops"];var i=Math.floor(Math.random()*s.length);
function show(){h.classList.remove("draw","u-zig","u-highlight","u-circle","u-loops");void h.offsetWidth;h.classList.add(s[i],"draw")}
show();if(window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches)return;setInterval(function(){i=(i+1)%s.length;show()},4500)})();`;

const PAGE_COLORS = { about: "#3fa9b5", new: "#cf6a2e", programs: "#9b84d8", tracker: "#3fa9b5", settings: "#e7c98f", login: "#9b84d8" };

const NAV = `<nav class="dock"><a href="/">new</a><a href="/programs">programs</a><a href="/tracker">tracker</a><a href="/settings">settings</a></nav>`;

function loginForm(message) {
  return page(`<form method="post" action="/login" class="login">
    <label for="password">password</label>
    <input id="password" name="password" type="password" autocomplete="current-password" autofocus>
    <button class="btn accent big" type="submit">let me in</button>
    ${message ? `<p class="warn">${esc(message)}</p>` : '<p class="note">it stays unlocked for 30 days. <a href="/about">what is scout?</a></p>'}
  </form>`, { title: "Log in", page: "login", lead: "who goes", head: "there?", nav: false }, message ? 401 : 200);
}

// Layout only. Colors, sizes, and fonts come from tokens.css.
const BASE_CSS = `
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:500 var(--text)/1.4 var(--font);padding:0 16px 96px;overflow-x:hidden;-webkit-font-smoothing:antialiased}
body[data-page="about"]{--page:var(--teal)} body[data-page="new"]{--page:var(--orange)} body[data-page="programs"]{--page:var(--purple)} body[data-page="tracker"]{--page:var(--teal)} body[data-page="settings"]{--page:var(--sand);--on-page:var(--ink)} body[data-page="login"]{--page:var(--purple)}
main{max-width:640px;margin-inline:auto}
header{max-width:640px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;padding:18px 0 6px}
.brand{display:inline-flex;align-items:baseline;font-family:var(--logo);font-size:40px;line-height:1;color:var(--ink);text-decoration:none;letter-spacing:.5px}
.brand .o{width:.56em;height:.56em;margin:0 .015em;flex:none}
body[data-page="about"] main{display:block} @media (min-width:900px){body[data-page="about"] main,body[data-page="about"] header,body[data-page="about"] .dock{max-width:860px} body[data-page="about"] .steps{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 20px}}
.head-links{display:flex;gap:8px;align-items:center} .pill-link .short{display:none} @media (max-width:560px){.pill-link.q .long{display:none} .pill-link.q .short{display:inline}}
.steps{counter-reset:step;list-style:none;padding:0;margin:0}
.steps li{counter-increment:step;position:relative;padding-left:58px}
.steps li::before{content:counter(step);position:absolute;left:18px;top:18px;width:30px;height:30px;border-radius:50%;background:var(--accent);border:var(--line) solid var(--ink);font-family:var(--display);font-size:15px;display:flex;align-items:center;justify-content:center}
.card p{margin:6px 0 0} .change{background:#fff;border:2px solid var(--ink);border-radius:12px;padding:10px 12px;margin:8px 0 6px;font-size:var(--small);font-weight:500;overflow-wrap:anywhere} .change b{display:block;margin-bottom:4px} .card ul{margin:8px 0 0;padding-left:18px} .card li+li{margin-top:4px} .login a,.card a.inline{color:var(--ink);font-weight:700}
.pill-link{font-size:var(--small);font-weight:700;color:var(--ink);background:var(--cream);border:var(--line) solid var(--ink);border-radius:var(--radius-pill);padding:6px 14px;text-decoration:none;box-shadow:var(--shadow-sm)}
h1{font-family:var(--display);font-size:var(--h1);line-height:.92;text-transform:uppercase;margin:14px 0 20px;letter-spacing:0}
h1 .lead{display:block;color:var(--on-page)} h1 .head{display:inline-block;color:var(--ink);padding-bottom:22px;position:relative;isolation:isolate}
/* The headline decoration lives in its own layer (::after) so swapping styles never moves the text. */
h1 .head::after{content:"";position:absolute;z-index:-1;pointer-events:none;left:0;right:0;bottom:0;height:30px;background:url('data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%27%20viewBox%3D%270%200%20400%2038%27%20preserveAspectRatio%3D%27none%27%3E%3Cpath%20d%3D%27M3.0%206.9%20Q%203.0%206.9%208.0%2018.6%20Q%2012.9%2030.2%2017.6%2019.2%20Q%2022.3%208.2%2027.9%2016.8%20Q%2033.5%2025.5%2039.6%2015.3%20Q%2045.6%205.2%2051.4%2015.4%20Q%2057.2%2025.6%2062.0%2016.6%20Q%2066.7%207.5%2073.7%2016.8%20Q%2080.7%2026.0%2085.9%2017.4%20Q%2091.0%208.8%2098.4%2019.2%20Q%20105.7%2029.6%20111.4%2020.2%20Q%20117.1%2010.9%20121.7%2021.4%20Q%20126.4%2031.9%20131.7%2018.9%20Q%20137.1%205.9%20142.0%2016.7%20Q%20146.8%2027.5%20153.8%2016.8%20Q%20160.7%206.1%20167.0%2018.1%20Q%20173.2%2030.1%20178.8%2019.2%20Q%20184.4%208.3%20189.1%2016.9%20Q%20193.8%2025.5%20198.9%2017.3%20Q%20204.0%209.1%20209.8%2018.3%20Q%20215.6%2027.5%20221.9%2017.6%20Q%20228.1%207.7%20233.5%2019.5%20Q%20238.9%2031.4%20245.5%2018.9%20Q%20252.1%206.5%20258.3%2017.8%20Q%20264.6%2029.2%20271.7%2019.3%20Q%20278.8%209.4%20284.2%2021.1%20Q%20289.5%2032.8%20294.4%2020.2%20Q%20299.3%207.5%20306.0%2016.9%20Q%20312.8%2026.2%20318.8%2015.7%20Q%20324.7%205.2%20331.2%2018.2%20Q%20337.7%2031.1%20344.0%2020.7%20Q%20350.2%2010.3%20355.6%2020.4%20Q%20361.1%2030.6%20367.3%2019.5%20Q%20373.6%208.5%20379.5%2020.1%20T%20385.4%2031.7%27%20fill%3D%27none%27%20stroke%3D%27%23ffc93c%27%20stroke-width%3D%274.5%27%20stroke-linecap%3D%27round%27%20stroke-linejoin%3D%27round%27%2F%3E%3C%2Fsvg%3E') no-repeat center/100% 100%}
h1 .head.u-loops::after{background-image:url('data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%27%20viewBox%3D%270%200%20400%2038%27%20preserveAspectRatio%3D%27none%27%3E%3Cpath%20d%3D%27M4%2026%20C%2021.1%2026%2C%2024.9%207.5%2C%2015.4%207.5%20C%205.9%207.5%2C%209.7%2030%2C%2028.7%2027%20C%2041.3%2026%2C%2045.4%206.3%2C%2035.2%206.3%20C%2025.0%206.3%2C%2029.1%2030%2C%2049.5%2027%20C%2061.3%2026%2C%2065.3%206.5%2C%2055.3%206.5%20C%2045.3%206.5%2C%2049.3%2030%2C%2069.2%2027%20C%2076.1%2026%2C%2078.9%209.2%2C%2071.8%209.2%20C%2064.7%209.2%2C%2067.5%2030%2C%2081.8%2027%20C%2096.9%2026%2C%20101.2%208.1%2C%2090.4%208.1%20C%2079.7%208.1%2C%2084.0%2030%2C%20105.5%2027%20C%20118.1%2026%2C%20122.4%2011.3%2C%20111.8%2011.3%20C%20101.2%2011.3%2C%20105.4%2030%2C%20126.6%2027%20C%20136.2%2026%2C%20139.8%2010.5%2C%20130.9%2010.5%20C%20122.0%2010.5%2C%20125.6%2030%2C%20143.3%2027%20C%20154.5%2026%2C%20158.2%208.6%2C%20149.0%208.6%20C%20139.8%208.6%2C%20143.5%2030%2C%20161.9%2027%20C%20169.0%2026%2C%20171.9%2010.7%2C%20164.8%2010.7%20C%20157.8%2010.7%2C%20160.6%2030%2C%20174.7%2027%20C%20185.1%2026%2C%20188.3%206.5%2C%20180.2%206.5%20C%20172.1%206.5%2C%20175.3%2030%2C%20191.6%2027%20C%20204.8%2026%2C%20208.8%2011.0%2C%20198.8%2011.0%20C%20188.7%2011.0%2C%20192.7%2030%2C%20212.9%2027%20C%20225.2%2026%2C%20229.2%2011.2%2C%20219.0%2011.2%20C%20208.9%2011.2%2C%20212.9%2030%2C%20233.3%2027%20C%20244.2%2026%2C%20248.0%2011.2%2C%20238.6%2011.2%20C%20229.1%2011.2%2C%20232.9%2030%2C%20251.8%2027%20C%20258.7%2026%2C%20261.6%206.8%2C%20254.5%206.8%20C%20247.5%206.8%2C%20250.3%2030%2C%20264.4%2027%20C%20274.3%2026%2C%20277.4%2010.7%2C%20269.6%2010.7%20C%20261.7%2010.7%2C%20264.9%2030%2C%20280.5%2027%20C%20295.5%2026%2C%20299.9%206.8%2C%20288.9%206.8%20C%20278.0%206.8%2C%20282.4%2030%2C%20304.2%2027%20C%20312.4%2026%2C%20315.6%206.2%2C%20307.5%206.2%20C%20299.3%206.2%2C%20302.6%2030%2C%20318.9%2027%20C%20330.5%2026%2C%20334.1%207.9%2C%20325.0%207.9%20C%20315.8%207.9%2C%20319.5%2030%2C%20337.8%2027%20C%20346.4%2026%2C%20349.5%206.4%2C%20341.7%206.4%20C%20333.9%206.4%2C%20337.0%2030%2C%20352.6%2027%20C%20365.5%2026%2C%20369.4%206.2%2C%20359.7%206.2%20C%20349.9%206.2%2C%20353.8%2030%2C%20373.3%2027%20C%20386.5%2026%2C%20390.7%2010.2%2C%20380.2%2010.2%20C%20369.6%2010.2%2C%20373.8%2030%2C%20395.0%2027%20C%20388%2025%2C%20392%2024%2C%20396%2022%27%20fill%3D%27none%27%20stroke%3D%27%23ffc93c%27%20stroke-width%3D%274.5%27%20stroke-linecap%3D%27round%27%2F%3E%3C%2Fsvg%3E')}
h1 .head.u-highlight::after{left:-6px;right:-6px;top:calc(50% - 6px);bottom:16px;height:auto;background:#ffc93c;transform:rotate(-1deg);border-radius:3px}
h1 .head.u-circle::after{left:-20px;right:-20px;top:-10px;bottom:10px;height:auto;background:url('data:image/svg+xml,%3Csvg%20xmlns%3D%27http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%27%20viewBox%3D%270%200%20400%20120%27%20preserveAspectRatio%3D%27none%27%3E%3Cpath%20d%3D%27M60%2018%20C%20150%204%2C%20330%206%2C%20384%2034%20C%20410%2050%2C%20396%2092%2C%20300%20108%20C%20190%20122%2C%2050%20116%2C%2018%2086%20C%20-4%2064%2C%2020%2030%2C%20120%2016%20C%20160%2011%2C%20210%2010%2C%20250%2012%27%20fill%3D%27none%27%20stroke%3D%27%23ffc93c%27%20stroke-width%3D%277%27%20stroke-linecap%3D%27round%27%2F%3E%3C%2Fsvg%3E') no-repeat center/100% 100%}
h1 .head.draw::after{animation:wipe .8s cubic-bezier(.6,0,.2,1) both}
@keyframes wipe{from{clip-path:inset(0 100% 0 0)}to{clip-path:inset(0 0 0 0)}}
h2{font-family:var(--display);font-size:20px;text-transform:uppercase;color:var(--on-page);margin:26px 0 10px;letter-spacing:0}
h3{font-family:var(--display);font-size:20px;margin:0;text-transform:uppercase;line-height:1.05;letter-spacing:0}
.note{color:var(--on-page);font-weight:700;margin:0 0 14px}
.stat{background:var(--cream);border:var(--line) solid var(--ink);border-radius:var(--radius);box-shadow:var(--shadow);padding:var(--pad);margin-bottom:8px}
.stat-label{font-family:var(--display);text-transform:uppercase;font-size:18px;letter-spacing:0}
.stat-big{font-family:var(--display);font-size:var(--big);line-height:.9;text-transform:uppercase;margin:4px 0 6px}
.stat{display:grid;gap:16px;position:relative}
.stat-sub{font-weight:700;font-size:18px}
.stat-tiles{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.tile{background:#fff;border:2px solid var(--ink);border-radius:14px;padding:12px;display:flex;flex-direction:column;gap:4px;min-width:0}
.tile b{font-family:var(--display);font-size:34px;line-height:1} .tile span{font-size:var(--small);font-weight:700;color:var(--muted);line-height:1.2}
.tile.hot{background:var(--accent)} .tile.hot span{color:var(--ink)}
.stat-foot{color:var(--muted);font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.5px}
.card{background:var(--cream);border:var(--line) solid var(--ink);border-radius:var(--radius);box-shadow:var(--shadow);padding:var(--pad);margin:0 0 16px;max-width:100%}
.card.dim > :not(.actions){opacity:.35} .passed-list > summary{list-style:none;cursor:pointer} .passed-list > summary::-webkit-details-marker{display:none} .passed-list > summary h2::after{content:" ▸"} .passed-list[open] > summary h2::after{content:" ▾"} .card.passed{opacity:.92}
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
select,input,textarea{font:700 15px var(--font);padding:10px 12px;border:var(--line) solid var(--ink);border-radius:var(--radius-pill);background:#fff;color:var(--ink);max-width:100%;box-shadow:var(--shadow-sm)}
input{flex:1;min-width:150px}
.pipeline{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 14px}
.step{font-size:12px;font-weight:700;background:var(--cream);border:2px solid var(--ink);border-radius:var(--radius-pill);padding:5px 10px;color:var(--muted)} .step.on{color:var(--ink);background:var(--accent)} .step b{margin-left:6px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:var(--cream);border:var(--line) solid var(--ink);border-radius:var(--radius);box-shadow:var(--shadow);padding:var(--pad);font-size:var(--small);font-weight:500}
body[data-page="login"] main,body[data-page="login"] header{max-width:420px} body[data-page="login"] header{justify-content:center} body[data-page="login"] main{display:block} body[data-page="login"] h1{text-align:center} body[data-page="login"] h1 .head{display:inline-block}
.login{display:flex;flex-direction:column;gap:12px;max-width:360px;margin:10px auto 0;background:var(--cream);border:var(--line) solid var(--ink);border-radius:var(--radius);box-shadow:var(--shadow);padding:22px}
.login label{font-family:var(--display);text-transform:uppercase;font-size:18px} .login input{width:100%} .login .note{color:var(--muted);margin:0} .warn{color:var(--red);font-weight:700;margin:0}
.dock{position:fixed;left:0;right:0;bottom:0;display:flex;justify-content:center;gap:8px;padding:10px 12px calc(10px + env(safe-area-inset-bottom));background:var(--page);border-top:var(--line) solid var(--ink)}
.dock a{flex:1;max-width:150px;text-align:center;font:700 14px var(--font);color:var(--ink);background:var(--cream);border:var(--line) solid var(--ink);border-radius:var(--radius-pill);padding:11px 6px;text-decoration:none;box-shadow:var(--shadow-sm)}
.dock a.on{background:var(--accent)}
/* Wider screens: the dock moves to the top, right under the logo. The body becomes a column so order can place it. */
@media (min-width:700px){body{display:flex;flex-direction:column;padding-bottom:40px} header{order:0;width:100%} .dock{order:1;position:static;background:transparent;border:0;width:100%;max-width:640px;margin:6px auto 4px;padding:0;justify-content:flex-start} main{order:2;width:100%}}
/* Wider screens: use the room. The header, headline, and stat card stay full width; cards flow into columns. */
@media (min-width:900px){
  main,header,.dock{max-width:1120px}
  main{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));column-gap:20px;align-items:start}
  main > h1,main > .stat,main > h2,main > .note,main > .pipeline,main > pre,main > form,main > .passed-list{grid-column:1 / -1}
  main > .card{margin-bottom:20px}
  h1{font-size:64px} .stat{grid-template-columns:auto 1fr;column-gap:40px;align-items:center}
  .stat-tiles{gap:14px} .tile{padding:16px 18px} .tile b{font-size:48px}
  .stat-foot{position:absolute;top:var(--pad);right:var(--pad)}
  .dock{justify-content:flex-start;gap:12px} .dock a{flex:none;min-width:150px}
}
@media (min-width:1400px){main{grid-template-columns:repeat(3,minmax(0,1fr))}}
/* ---------- life: gradient backgrounds and motion. Everything here is decoration; reduced-motion users get none of the movement. ---------- */
body{--page-hi:color-mix(in srgb,var(--page) 62%,#fff);--page-lo:color-mix(in srgb,var(--page) 72%,#1a1333);--page-pop:color-mix(in srgb,var(--page) 55%,var(--accent))}
body::before{content:"";position:fixed;inset:-25%;z-index:-1;pointer-events:none;
  background:radial-gradient(circle at 18% 12%,var(--page-hi) 0,transparent 38%),radial-gradient(circle at 85% 30%,var(--page-pop) 0,transparent 34%),radial-gradient(circle at 70% 90%,var(--page-lo) 0,transparent 45%),var(--page);
  animation:drift 22s ease-in-out infinite alternate}
@keyframes drift{0%{transform:translate(0,0) rotate(0)}50%{transform:translate(3%,-2%) rotate(4deg)}100%{transform:translate(-3%,2%) rotate(-3deg)}}
/* cards rise in one after another on load */
main > *{animation:rise .5s cubic-bezier(.2,.9,.3,1.2) both}
main > *:nth-child(2){animation-delay:.04s} main > *:nth-child(3){animation-delay:.08s} main > *:nth-child(4){animation-delay:.12s} main > *:nth-child(5){animation-delay:.16s} main > *:nth-child(6){animation-delay:.2s} main > *:nth-child(7){animation-delay:.24s} main > *:nth-child(n+8){animation-delay:.28s}
@keyframes rise{from{opacity:0;transform:translateY(18px) scale(.98)}to{opacity:1;transform:none}}
/* the scribble draws itself left to right */
/* the headline decoration draws itself in; see CYCLE_JS for the rotation */
/* buttons lift on hover, squash when pressed */
.btn,.dock a,.pill-link{transition:transform .15s cubic-bezier(.3,1.6,.5,1),box-shadow .15s ease,background-color .2s}
@media (hover:hover){.btn:hover:not([disabled]),.dock a:hover,.pill-link:hover{transform:translate(-2px,-2px) rotate(-1deg);box-shadow:6px 6px 0 var(--ink)} .btn.ghost:hover{box-shadow:4px 4px 0 var(--ink)}}
.btn:active:not([disabled]),.dock a:active,.pill-link:active{transform:translate(3px,3px) scale(.97);box-shadow:0 0 0 var(--ink)}
.btn.accent:not([disabled]){background-image:linear-gradient(120deg,transparent 30%,rgba(255,255,255,.55) 45%,transparent 60%);background-size:250% 100%;background-position:120% 0}
@media (hover:hover){.btn.accent:hover:not([disabled]){animation:shine .8s ease}}
@keyframes shine{from{background-position:120% 0}to{background-position:-30% 0}}
.dock a.on{animation:pop .45s cubic-bezier(.3,1.8,.5,1)}
@keyframes pop{0%{transform:scale(.9)}60%{transform:scale(1.06)}100%{transform:scale(1)}}
/* cards tilt up a touch on hover, score pills pop in */
.card{transition:transform .2s cubic-bezier(.3,1.5,.5,1),box-shadow .2s}
@media (hover:hover){main > .card:hover{transform:translate(-2px,-3px);box-shadow:9px 9px 0 var(--ink)}}
.score{animation:pop .5s .35s cubic-bezier(.3,1.8,.5,1) both}
/* the logo's bullseye spins on hover and when the page loads */
.brand .o{transition:transform .5s cubic-bezier(.3,1.6,.5,1);animation:spin-in .9s .1s cubic-bezier(.3,1.4,.5,1) both}
@media (hover:hover){.brand:hover .o{transform:rotate(200deg) scale(1.15)}}
@keyframes spin-in{from{transform:rotate(-180deg) scale(.4)}to{transform:none}}
/* a tapped pass/undo/save button gives a little wiggle */
.btn.tapped{animation:wiggle .35s ease}
@keyframes wiggle{25%{transform:rotate(-3deg)}75%{transform:rotate(3deg)}}
.card.dim{transition:opacity .3s}
/* the next-action box takes its own line and grows with the text, so nothing gets cut off */
textarea[data-act="next"]{flex:1 1 100%;width:100%;order:-1;resize:none;overflow:hidden;line-height:1.35;border-radius:18px;padding:11px 16px;min-height:44px}
/* the hero card: a sheen sweeps across, the number pops and counts up (CLIENT_JS), the tiles bounce in one by one */
.stat{overflow:hidden;isolation:isolate}
.stat::after{content:"";position:absolute;inset:0;z-index:-1;pointer-events:none;background:linear-gradient(105deg,transparent 35%,rgba(255,255,255,.7) 50%,transparent 65%);background-size:300% 100%;animation:sweep 6s 1s ease-in-out infinite}
@keyframes sweep{0%{background-position:150% 0}40%,100%{background-position:-50% 0}}
.stat-big{display:inline-block;transform-origin:20% 80%;animation:big-in .8s .15s cubic-bezier(.3,1.7,.5,1) both}
@keyframes big-in{from{transform:scale(.3) rotate(-12deg);opacity:0}to{transform:none;opacity:1}}
@media (hover:hover){.stat-big:hover{animation:jelly .6s ease}}
@keyframes jelly{30%{transform:scale(1.12,.88)}50%{transform:scale(.92,1.08)}70%{transform:scale(1.04,.96)}100%{transform:none}}
.stat-label,.stat-sub{animation:slide-in .5s cubic-bezier(.2,.9,.3,1.2) both} .stat-label{animation-delay:.05s} .stat-sub{animation-delay:.3s}
@keyframes slide-in{from{opacity:0;transform:translateX(-16px)}to{opacity:1;transform:none}}
.tile{animation:tile-in .6s cubic-bezier(.3,1.6,.5,1) both;transition:transform .2s cubic-bezier(.3,1.6,.5,1),box-shadow .2s}
.tile:nth-child(1){animation-delay:.35s} .tile:nth-child(2){animation-delay:.47s} .tile:nth-child(3){animation-delay:.59s}
@keyframes tile-in{from{opacity:0;transform:translateY(24px) rotate(4deg) scale(.85)}to{opacity:1;transform:none}}
@media (hover:hover){.tile:hover{transform:translate(-2px,-3px) rotate(-2deg);box-shadow:5px 5px 0 var(--ink)} .tile:nth-child(2):hover{transform:translate(-2px,-3px) rotate(2deg)}}
.tile.hot{animation:tile-in .6s .35s cubic-bezier(.3,1.6,.5,1) both,glow 1.8s 1.2s ease-in-out infinite}
@keyframes glow{0%,100%{box-shadow:0 0 0 0 var(--ink)}50%{box-shadow:0 0 0 6px color-mix(in srgb,var(--accent) 45%,transparent)}}
.stat-foot::before{content:"";display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--green);border:2px solid var(--ink);margin-right:7px;vertical-align:0;animation:beat 2s ease-in-out infinite}
@keyframes beat{0%,100%{transform:scale(1)}50%{transform:scale(1.35)}}
/* section headings draw an underline in */
h2{position:relative;width:fit-content}
h2::after{content:"";position:absolute;left:0;right:0;bottom:-4px;height:4px;border-radius:4px;background:var(--accent);transform-origin:left;animation:underline .7s .4s cubic-bezier(.3,1.4,.5,1) both}
@keyframes underline{from{transform:scaleX(0)}to{transform:scaleX(1)}}
/* tags pop in one after another; the "new" tag keeps a little wiggle */
.tag{display:inline-block;animation:pop .45s cubic-bezier(.3,1.8,.5,1) both} .tag:nth-child(1){animation-delay:.2s} .tag:nth-child(2){animation-delay:.28s} .tag:nth-child(3){animation-delay:.36s} .tag:nth-child(n+4){animation-delay:.44s}
.card.is-new .tag.accent:last-child{animation:pop .45s .44s cubic-bezier(.3,1.8,.5,1) both,nudge 2.4s 1.2s ease-in-out infinite}
@keyframes nudge{0%,80%,100%{transform:none}85%{transform:rotate(-6deg) scale(1.08)}90%{transform:rotate(6deg) scale(1.08)}95%{transform:rotate(-3deg)}}
/* the dock buttons bounce in */
.dock a{animation:pop .5s cubic-bezier(.3,1.8,.5,1) both} .dock a:nth-child(2){animation-delay:.06s} .dock a:nth-child(3){animation-delay:.12s} .dock a:nth-child(4){animation-delay:.18s}
@media (prefers-reduced-motion:reduce){*,*::before,*::after{animation:none !important;transition:none !important}}
`;

// The only JavaScript the pages need: send a tap to the API and update the card in place.
const CLIENT_JS = `
// The next-action box grows to fit its text instead of cutting it off.
document.querySelectorAll('textarea[data-act="next"]').forEach(function(t){const fit=function(){t.style.height="auto";t.style.height=t.scrollHeight+t.offsetHeight-t.clientHeight+"px"};fit();t.addEventListener("input",fit)});
// The hero numbers count up from zero on load (about a second, done before anyone can tap pass).
(function(){if(window.matchMedia&&matchMedia("(prefers-reduced-motion: reduce)").matches)return;document.querySelectorAll(".stat-big,.tile b").forEach(function(el,n){const end=parseInt(el.textContent,10);if(!(end>0))return;const t0=performance.now()+150+n*120,dur=end>20?1100:600;el.textContent="0";requestAnimationFrame(function tick(t){const k=Math.min(1,Math.max(0,(t-t0)/dur));el.textContent=Math.round(end*(1-Math.pow(1-k,3)));if(k<1)requestAnimationFrame(tick)})})})();
async function post(url, body){const r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});if(!r.ok){alert("that didn't save. try again.");throw new Error(r.status)}return r.json()}
function bump(id,d){const el=document.getElementById(id);if(el)el.textContent=Math.max(0,(parseInt(el.textContent,10)||0)+d)}
function syncPassed(){const box=document.getElementById("passed");const n=parseInt((document.getElementById("passed-count")||{}).textContent,10)||0;if(box){box.hidden=n===0;if(n===0)box.open=false}}
function passedClone(card,key){const a=document.createElement("article");a.className="card passed";a.dataset.key=key;a.dataset.origin="main";
 const row=document.createElement("div");row.className="row";const h=document.createElement("h3");h.textContent=(card.querySelector("h3")||{}).textContent||"";const sc=document.createElement("span");sc.className="score";sc.textContent=(card.querySelector(".score")||{}).textContent||"";row.append(h,sc);
 const t=document.createElement("div");t.className="title";t.textContent=(card.querySelector(".title")||{}).textContent||"";
 const m=document.createElement("div");m.className="meta";m.textContent="passed just now";
 const acts=document.createElement("div");acts.className="actions";const u=document.createElement("button");u.className="btn accent";u.dataset.act="unpass";u.textContent="unpass";acts.append(u);
 const link=card.querySelector("a.btn");if(link){const l=link.cloneNode(true);acts.append(l)}
 a.append(row,t,m,acts);return a}
function mainCard(key){return [...document.querySelectorAll("main > .card[data-key]")].find(c=>c.dataset.key===key)}
function clonesFor(key){return [...document.querySelectorAll("#passed-cards .card")].filter(c=>c.dataset.key===key)}
document.addEventListener("click",async(e)=>{const b=e.target.closest("button[data-act]");if(!b||b.disabled)return;b.classList.remove("tapped");void b.offsetWidth;b.classList.add("tapped");const card=b.closest("[data-key]");const key=card&&card.dataset.key;if(!key)return;b.disabled=true;
 try{
 if(b.dataset.act==="queue"){await post("/api/queue",{key});b.textContent="queued ✓";return}
 if(b.dataset.act==="pass"){await post("/api/pass",{key});card.classList.add("dim");b.textContent="undo";b.dataset.act="unpass";bump("open-count",-1);bump("passed-count",1);const box=document.getElementById("passed-cards");if(box)box.prepend(passedClone(card,key));syncPassed()}
 else if(b.dataset.act==="unpass"){await post("/api/pass",{key,undo:true});bump("passed-count",-1);bump("open-count",1);
  if(card.classList.contains("passed")){clonesFor(key).forEach(c=>c.remove());card.remove();const mc=mainCard(key);if(mc){mc.classList.remove("dim");const pb=mc.querySelector('button[data-act="unpass"]');if(pb){pb.textContent="pass";pb.dataset.act="pass"}}else{syncPassed();location.reload();return}}
  else{card.classList.remove("dim");b.textContent="pass";b.dataset.act="pass";clonesFor(key).forEach(c=>c.remove())}
  syncPassed()}
 else if(b.dataset.act==="save"){const state=card.querySelector('[data-act="state"]').value;const next=card.querySelector('[data-act="next"]').value;await post("/api/tracker",{key,state,next});b.textContent="saved";setTimeout(()=>location.reload(),400)}
 }finally{b.disabled=b.dataset.act==="queue"&&b.textContent.startsWith("queued")}
});`;

/* ---------------------------------------------------------------- small helpers */

// Today's date in New York (YYYY-MM-DD). The server runs in UTC, which is already tomorrow after 8 PM ET.
function nyDate() {
  return new Date().toLocaleDateString("en-CA", { timeZone: "America/New_York" });
}

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
function png(b64) {
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  return new Response(bytes, { headers: { "Content-Type": "image/png", "Cache-Control": "public, max-age=86400" } });
}
function manifest() {
  return new Response(JSON.stringify({
    name: "Scout", short_name: "Scout", start_url: "/", scope: "/", display: "standalone",
    background_color: "#ffffff", theme_color: "#d2612a",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
      { src: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" },
    ],
  }), { headers: { "Content-Type": "application/manifest+json", "Cache-Control": "public, max-age=86400" } });
}
function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), { status, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
}
function redirect(to, headers = {}) {
  return new Response(null, { status: 302, headers: { Location: to, ...headers } });
}
