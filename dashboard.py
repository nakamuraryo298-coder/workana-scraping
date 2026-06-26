#!/usr/bin/env python3
"""
Workana Job Dashboard
A small local web UI that displays jobs collected by the scraper (jobs.json)
as cards, with a ready-to-use draft proposal for each one.

The scraper (main.py) writes jobs.json; this app only reads it.
Run the scraper in another window (e.g. `python main.py -d -c`) to keep it fresh.

Usage:
    python dashboard.py
    -> open http://127.0.0.1:5000 in your browser
"""

import json
import os
from flask import Flask, jsonify, render_template_string

JOBS_STORE = "jobs.json"
REFRESH_SECONDS = 30

app = Flask(__name__)


def load_jobs():
    """Read jobs.json (newest first). Returns [] if missing/invalid."""
    if not os.path.exists(JOBS_STORE):
        return []
    try:
        with open(JOBS_STORE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


PAGE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Workana Jobs</title>
  <style>
    :root { --bg:#0f1115; --card:#1a1d24; --line:#2a2f3a; --txt:#e6e8eb;
            --muted:#9aa3b2; --accent:#43b581; --link:#4ea1ff; --warn:#f04747; }
    * { box-sizing: border-box; }
    body { margin:0; background:var(--bg); color:var(--txt);
           font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif; }
    header { position:sticky; top:0; background:#141720; border-bottom:1px solid var(--line);
             padding:14px 20px; display:flex; align-items:center; gap:14px; z-index:10; }
    header h1 { font-size:18px; margin:0; }
    header .meta { color:var(--muted); font-size:13px; }
    .wrap { max-width:1100px; margin:0 auto; padding:18px; }
    .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(330px,1fr)); gap:16px; }
    .card { background:var(--card); border:1px solid var(--line); border-left:4px solid var(--accent);
            border-radius:10px; padding:14px; display:flex; flex-direction:column; gap:10px; }
    .top { display:flex; gap:12px; }
    .avatar { width:52px; height:52px; border-radius:8px; object-fit:cover; background:#262b35; flex:none; }
    .title { font-size:15px; font-weight:600; line-height:1.3; }
    .title a { color:var(--link); text-decoration:none; }
    .title a:hover { text-decoration:underline; }
    .rows { display:grid; grid-template-columns:1fr 1fr; gap:4px 12px; font-size:13px; }
    .rows .k { color:var(--muted); }
    .badge { display:inline-block; padding:1px 7px; border-radius:20px; font-size:12px; }
    .ok { background:rgba(67,181,129,.15); color:var(--accent); }
    .no { background:rgba(240,71,71,.15); color:var(--warn); }
    .badge.new { background:rgba(78,161,255,.18); color:var(--link); margin-left:6px; vertical-align:middle; }
    .card.is-new { border-left-color:var(--link); box-shadow:0 0 0 1px rgba(78,161,255,.25); }
    .stats { display:flex; gap:8px; flex-wrap:wrap; }
    .stat { background:#1a1d24; border:1px solid var(--line); border-radius:20px; padding:2px 10px; font-size:13px; }
    .stat b { color:var(--txt); } .stat.newstat b { color:var(--link); }
    .skills { font-size:12px; color:var(--muted); }
    details { background:#12151c; border:1px solid var(--line); border-radius:8px; padding:8px 10px; }
    summary { cursor:pointer; font-size:13px; color:var(--link); }
    textarea { width:100%; min-height:150px; margin-top:8px; background:#0c0e13; color:var(--txt);
               border:1px solid var(--line); border-radius:6px; padding:8px; font-size:13px; resize:vertical; }
    .actions { display:flex; gap:8px; margin-top:8px; flex-wrap:wrap; }
    button, .btn { background:#2b6cb0; color:#fff; border:none; border-radius:6px; padding:7px 12px;
                   font-size:13px; cursor:pointer; text-decoration:none; display:inline-block; }
    .btn.bid { background:var(--accent); }
    button:hover, .btn:hover { filter:brightness(1.1); }
    .empty { color:var(--muted); text-align:center; padding:60px 0; }
    .footnote { color:var(--muted); font-size:12px; margin-top:18px; text-align:center; }
  </style>
</head>
<body>
  <header>
    <h1>Workana Jobs</h1>
    <div class="stats" id="stats"></div>
    <span class="meta">· auto-refresh {{refresh}}s</span>
  </header>
  <div class="wrap">
    <div class="grid" id="grid"></div>
    <div class="footnote">
      Draft proposals are templates &mdash; review and edit before submitting on Workana.
      Submitting a bid is always done by you.
    </div>
  </div>

<script>
const REFRESH = {{refresh}} * 1000;

function badge(verified){
  return verified
    ? '<span class="badge ok">✅ Verified</span>'
    : '<span class="badge no">❌ Not verified</span>';
}
function esc(s){ return (s||'').replace(/[&<>"]/g, c => (
  {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function bidCount(s){ const m=(s||'').match(/\d+/); return m?parseInt(m[0],10):0; }

function card(j, isNew){
  const skills = (j.skills||[]).slice(0,10).join(', ') || '-';
  const avatar = (j.authorAvatar && j.authorAvatar.startsWith('http') && !j.authorAvatar.toLowerCase().endsWith('.svg'))
    ? j.authorAvatar : 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg"/>';
  const newBadge = isNew ? '<span class="badge new">NEW</span>' : '';
  return `
  <div class="card${isNew ? ' is-new' : ''}">
    <div class="top">
      <img class="avatar" src="${esc(avatar)}" alt="" onerror="this.style.visibility='hidden'"/>
      <div class="title"><a href="${esc(j.job_url)}" target="_blank" rel="noopener">${esc(j.title)}</a>${newBadge}</div>
    </div>
    <div class="rows">
      <div><span class="k">Author:</span> ${esc(j.authorName)||'-'}</div>
      <div><span class="k">Rating:</span> ${esc(j.authorRating)||'-'}</div>
      <div><span class="k">Payment:</span> ${badge(j.hasVerifiedPaymentMethod)}</div>
      <div><span class="k">Budget:</span> ${esc(j.budget)||'-'}</div>
      <div><span class="k">Posted:</span> ${esc(j.postedDate)||'-'}</div>
      <div><span class="k">Bids:</span> ${esc(j.totalBids)||'-'}</div>
      <div><span class="k">Country:</span> ${esc(j.country)||'-'}</div>
      <div><span class="k">Found:</span> ${esc(j.detectedAt)||'-'}</div>
    </div>
    <div class="skills">🛠 ${esc(skills)}</div>
    <details>
      <summary>Draft proposal</summary>
      <textarea id="ta-${esc(j.job_url)}">${esc(j.proposal)}</textarea>
      <div class="actions">
        <button onclick="copyText('ta-${esc(j.job_url)}', this)">Copy proposal</button>
        <a class="btn bid" href="${esc(j.job_url)}" target="_blank" rel="noopener">Open to bid →</a>
      </div>
    </details>
  </div>`;
}

function copyText(id, btn){
  const ta = document.getElementById(id);
  ta.select(); navigator.clipboard.writeText(ta.value);
  const old = btn.textContent; btn.textContent = 'Copied!';
  setTimeout(()=>btn.textContent = old, 1200);
}

async function load(){
  try {
    const r = await fetch('/api/jobs'); const jobs = await r.json();
    // Newest batch = jobs sharing the most recent detectedAt timestamp
    const latest = jobs.reduce((a,j) => (j.detectedAt && j.detectedAt > a) ? j.detectedAt : a, '');
    const newCount = latest ? jobs.filter(j => j.detectedAt === latest).length : 0;
    const totalBids = jobs.reduce((s,j) => s + bidCount(j.totalBids), 0);
    document.getElementById('stats').innerHTML =
      `<span class="stat">Tasks so far: <b>${jobs.length}</b></span>` +
      `<span class="stat newstat">New: <b>${newCount}</b></span>` +
      `<span class="stat">Total bids: <b>${totalBids}</b></span>`;
    document.getElementById('grid').innerHTML = jobs.length
      ? jobs.map(j => card(j, latest && j.detectedAt === latest)).join('')
      : '<div class="empty">No jobs yet. Start the scraper: <code>python main.py -d -c</code></div>';
  } catch(e){ /* keep last view on transient error */ }
}
load();
setInterval(load, REFRESH);
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE, refresh=REFRESH_SECONDS)


@app.route("/api/jobs")
def api_jobs():
    return jsonify(load_jobs())


if __name__ == "__main__":
    print("Workana Dashboard -> http://127.0.0.1:5000  (Ctrl+C to stop)")
    app.run(host="127.0.0.1", port=5000, debug=False)
