"""रहस्यलोक Studio — local control room for the video autopilots.

One small Flask app, two channels (रहस्यलोक / Terra Incognita), two run
modes:
  LOCAL  — runs pipeline/run.py on THIS machine with live stage progress
           (no 6h CI cap: long videos render in one continuous pass)
  GITHUB — dispatches the Actions workflows, watches runs, downloads
           release files (final.mp4, thumbnails, captions) to ~/Downloads

Start it:   python3 gui/app.py     (or double-click start-gui.command)
Then open:  http://127.0.0.1:8765

Security: binds to 127.0.0.1 only. The GitHub token you paste is kept in
memory and (only if you tick "remember") written to ~/.rahasyalok_studio.json
chmod 600. It is sent to api.github.com over HTTPS and nowhere else.
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time

import requests
from flask import Flask, jsonify, request, send_file, Response

APP_PORT = 8765
GUI_DIR = os.path.dirname(os.path.abspath(__file__))
SELF_REPO = os.path.dirname(GUI_DIR)
CONF_PATH = os.path.expanduser("~/.rahasyalok_studio.json")
DOWNLOADS = os.path.expanduser("~/Downloads/rahasyalok-studio")

DEFAULT_CHANNELS = {
    "rahasyalok": {
        "label": "रहस्यलोक — Bharat Ke Rahasya",
        "gh": "dwijptl/elsewhere-autopilot",
        "path": SELF_REPO,
        "accent": "#D8A24A",
        "workflows": [
            {"file": "make_long_video.yml", "label": "Long video (20-25 min)",
             "inputs": ["topic", "minutes"]},
            {"file": "make_video.yml", "label": "Standard video",
             "inputs": ["topic"]},
            {"file": "make_short.yml", "label": "Short", "inputs": ["topic"]},
        ],
    },
    "terra": {
        "label": "Terra Incognita",
        "gh": "dwijptl/faceless-autopilot",
        "path": os.path.join(os.path.dirname(SELF_REPO), "faceless-autopilot"),
        "accent": "#4AB8D8",
        "workflows": [
            {"file": "make_video.yml", "label": "Standard video",
             "inputs": ["topic"]},
            {"file": "make_short.yml", "label": "Short", "inputs": ["topic"]},
        ],
    },
}

app = Flask(__name__)
_state_lock = threading.Lock()
_run = {"proc": None, "channel": None, "log": None, "started": 0.0}


# ── config (token + channel paths) ───────────────────────────────────────
def _load_conf() -> dict:
    try:
        with open(CONF_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_conf(conf: dict) -> None:
    with open(CONF_PATH, "w", encoding="utf-8") as f:
        json.dump(conf, f, indent=2)
    os.chmod(CONF_PATH, 0o600)


def channels() -> dict:
    conf = _load_conf()
    out = json.loads(json.dumps(DEFAULT_CHANNELS))  # deep copy
    for key, override in (conf.get("paths") or {}).items():
        if key in out and override:
            out[key]["path"] = os.path.expanduser(override)
    return out


def _token() -> str:
    tok = app.config.get("GH_TOKEN") or _load_conf().get("token") or ""
    return tok.strip()


def _gh(path: str, channel: dict, method: str = "GET", payload=None,
        raw: bool = False):
    tok = _token()
    if not tok:
        return None, "no token — paste a GitHub token in the GitHub panel"
    url = f"https://api.github.com/repos/{channel['gh']}{path}"
    headers = {"Authorization": f"Bearer {tok}",
               "Accept": "application/octet-stream" if raw
               else "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    try:
        r = requests.request(method, url, headers=headers, json=payload,
                             timeout=60, stream=raw)
        if r.status_code >= 300:
            return None, f"GitHub {r.status_code}: {r.text[:200]}"
        return r, None
    except requests.RequestException as exc:
        return None, str(exc)


# ── local .env keys ──────────────────────────────────────────────────────
KEY_NAMES = ["GEMINI_API_KEY", "PEXELS_API_KEY", "SARVAM_API_KEY",
             "SARVAM_SPEAKER", "FAL_KEY"]


def _env_path(repo: str) -> str:
    return os.path.join(repo, ".env")


def _read_env(repo: str) -> dict:
    out = {}
    try:
        with open(_env_path(repo), encoding="utf-8") as f:
            for line in f:
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return out


# ── local runs ───────────────────────────────────────────────────────────
STAGES = ["research", "script", "factcheck", "voice", "assets", "render",
          "deliver"]


def _log_dir(repo: str) -> str:
    d = os.path.join(repo, "out", "gui_logs")
    os.makedirs(d, exist_ok=True)
    return d


def _start_local(channel_key: str, topic: str, minutes: str) -> tuple[bool, str]:
    with _state_lock:
        if _run["proc"] and _run["proc"].poll() is None:
            return False, "a local run is already in progress"
        ch = channels().get(channel_key)
        if not ch or not os.path.isdir(ch["path"]):
            return False, f"repo folder not found: {ch and ch['path']}"
        env = dict(os.environ)
        env.update(_read_env(ch["path"]))
        env["PYTHONUNBUFFERED"] = "1"
        if topic.strip():
            env["FORCED_TOPIC"] = topic.strip()
        if minutes.strip():
            env["LONG_TARGET_MINUTES"] = minutes.strip()
        env.pop("PIPELINE_STAGE", None)  # local = single continuous run
        stamp = time.strftime("%Y-%m-%d_%H%M")
        log_path = os.path.join(_log_dir(ch["path"]), f"run_{stamp}.log")
        log_f = open(log_path, "w", encoding="utf-8")
        cmd = [sys.executable, "pipeline/run.py"]  # same venv as the app
        if shutil.which("caffeinate"):  # macOS: don't sleep mid-render
            cmd = ["caffeinate", "-i"] + cmd
        proc = subprocess.Popen(
            cmd, cwd=ch["path"], env=env,
            stdout=log_f, stderr=subprocess.STDOUT,
            start_new_session=True)  # own process group -> clean cancel
        _run.update({"proc": proc, "channel": channel_key, "log": log_path,
                     "started": time.time()})
        return True, log_path


def _local_status() -> dict:
    proc, log_path = _run["proc"], _run["log"]
    if not proc:
        return {"state": "idle"}
    alive = proc.poll() is None
    tail, stage = "", None
    try:
        with open(log_path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        tail = text[-4000:]
        for m in re.finditer(r"\[stage\] (\w+)", text):
            stage = m.group(1)
        if "[render]" in text or "Rendered " in text:
            stage = "render"
        if "=== Done in" in text:
            stage = "deliver"
    except Exception:
        pass
    return {"state": "running" if alive else
            ("done" if proc.returncode == 0 else "failed"),
            "returncode": None if alive else proc.returncode,
            "channel": _run["channel"], "stage": stage,
            "stages": STAGES, "log_tail": tail,
            "minutes_elapsed": round((time.time() - _run["started"]) / 60, 1),
            "log_path": log_path}


# ── outputs on disk ──────────────────────────────────────────────────────
def _outputs(repo: str) -> list:
    root = os.path.join(repo, "out")
    items = []
    if not os.path.isdir(root):
        return items
    for name in sorted(os.listdir(root), reverse=True)[:20]:
        d = os.path.join(root, name)
        final = os.path.join(d, "final.mp4")
        if os.path.isdir(d) and os.path.exists(final):
            items.append({
                "stamp": name,
                "size_mb": round(os.path.getsize(final) / 1e6, 1),
                "files": sorted(fn for fn in os.listdir(d)
                                if os.path.isfile(os.path.join(d, fn))
                                and not fn.endswith((".log", ".pkl")))})
    return items


def _safe_out_path(repo: str, stamp: str, fname: str) -> str | None:
    p = os.path.realpath(os.path.join(repo, "out", stamp, fname))
    if p.startswith(os.path.realpath(os.path.join(repo, "out")) + os.sep):
        return p if os.path.isfile(p) else None
    return None


# ── API routes ───────────────────────────────────────────────────────────
@app.get("/api/state")
def api_state():
    chs = channels()
    key = request.args.get("channel", "rahasyalok")
    ch = chs.get(key, chs["rahasyalok"])
    envmap = _read_env(ch["path"])
    return jsonify({
        "channels": {k: {"label": c["label"], "gh": c["gh"], "path": c["path"],
                         "accent": c["accent"], "workflows": c["workflows"],
                         "path_ok": os.path.isdir(
                             os.path.join(c["path"], "pipeline"))}
                     for k, c in chs.items()},
        "keys": {k: bool(envmap.get(k) or os.environ.get(k))
                 for k in KEY_NAMES},
        "token_set": bool(_token()),
        "local": _local_status(),
        "outputs": _outputs(ch["path"]),
    })


@app.post("/api/run/local")
def api_run_local():
    d = request.get_json(force=True)
    ok, msg = _start_local(d.get("channel", "rahasyalok"),
                           d.get("topic", ""), str(d.get("minutes", "")))
    return jsonify({"ok": ok, "msg": msg})


@app.post("/api/run/cancel")
def api_run_cancel():
    with _state_lock:
        proc = _run["proc"]
        if proc and proc.poll() is None:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            return jsonify({"ok": True})
    return jsonify({"ok": False, "msg": "no run in progress"})


@app.post("/api/token")
def api_token():
    d = request.get_json(force=True)
    app.config["GH_TOKEN"] = d.get("token", "").strip()
    if d.get("remember"):
        conf = _load_conf()
        conf["token"] = app.config["GH_TOKEN"]
        _save_conf(conf)
    return jsonify({"ok": True})


@app.post("/api/paths")
def api_paths():
    d = request.get_json(force=True)
    conf = _load_conf()
    conf.setdefault("paths", {})[d["channel"]] = d["path"]
    _save_conf(conf)
    return jsonify({"ok": True})


@app.post("/api/env")
def api_env():
    d = request.get_json(force=True)
    ch = channels().get(d.get("channel", "rahasyalok"))
    cur = _read_env(ch["path"])
    for k in KEY_NAMES:
        if d.get(k):
            cur[k] = d[k].strip()
    with open(_env_path(ch["path"]), "w", encoding="utf-8") as f:
        f.write("".join(f"{k}={v}\n" for k, v in cur.items()))
    os.chmod(_env_path(ch["path"]), 0o600)
    return jsonify({"ok": True})


@app.get("/api/gh/runs")
def api_gh_runs():
    ch = channels().get(request.args.get("channel", "rahasyalok"))
    r, err = _gh("/actions/runs?per_page=12", ch)
    if err:
        return jsonify({"error": err})
    runs = [{"name": w["name"], "status": w["status"],
             "conclusion": w["conclusion"], "url": w["html_url"],
             "created": w["created_at"], "number": w["run_number"]}
            for w in r.json().get("workflow_runs", [])]
    return jsonify({"runs": runs})


@app.post("/api/gh/dispatch")
def api_gh_dispatch():
    d = request.get_json(force=True)
    ch = channels().get(d.get("channel", "rahasyalok"))
    inputs = {}
    if d.get("topic", "").strip():
        inputs["topic"] = d["topic"].strip()
    if d.get("minutes") and "minutes" in str(d.get("inputs", "")):
        inputs["minutes"] = str(d["minutes"])
    _, err = _gh(f"/actions/workflows/{d['workflow']}/dispatches", ch,
                 method="POST", payload={"ref": "main", "inputs": inputs})
    return jsonify({"ok": not err, "msg": err or "dispatched — check Runs"})


@app.get("/api/gh/releases")
def api_gh_releases():
    ch = channels().get(request.args.get("channel", "rahasyalok"))
    r, err = _gh("/releases?per_page=8", ch)
    if err:
        return jsonify({"error": err})
    rels = [{"tag": w.get("tag_name") or "(draft)", "name": w["name"],
             "draft": w["draft"], "id": w["id"],
             "assets": [{"id": a["id"], "name": a["name"],
                         "size_mb": round(a["size"] / 1e6, 1)}
                        for a in w.get("assets", [])]}
            for w in r.json()]
    return jsonify({"releases": rels})


@app.post("/api/gh/download")
def api_gh_download():
    d = request.get_json(force=True)
    ch = channels().get(d.get("channel", "rahasyalok"))
    r, err = _gh(f"/releases/assets/{d['asset_id']}", ch, raw=True)
    if err:
        return jsonify({"ok": False, "msg": err})
    folder = os.path.join(DOWNLOADS, re.sub(r"[^\w.-]+", "_", d.get("tag", "release")))
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, os.path.basename(d["name"]))
    with open(dest, "wb") as f:
        for chunk in r.iter_content(1 << 20):
            f.write(chunk)
    return jsonify({"ok": True, "msg": f"saved to {dest}"})


@app.get("/files/<channel>/<stamp>/<path:fname>")
def files(channel, stamp, fname):
    ch = channels().get(channel)
    p = ch and _safe_out_path(ch["path"], stamp, fname)
    if not p:
        return "not found", 404
    return send_file(p)


@app.get("/")
def index():
    return Response(PAGE, mimetype="text/html")


# ── the page ─────────────────────────────────────────────────────────────
PAGE = r"""<!doctype html><html lang="hi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>रहस्यलोक Studio</title><style>
:root{--gold:#D8A24A;--bg:#0a0812;--panel:#141020;--line:#2a2338;
--text:#efe9dc;--dim:#9a8f7c}
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--text);font:15px/1.55 -apple-system,
"Noto Sans Devanagari",Mukta,sans-serif;padding:26px 4vw 60px}
h1{font-size:26px;letter-spacing:.5px}
h1 b{color:var(--gold)} .sub{color:var(--dim);margin:2px 0 20px}
.tabs{display:flex;gap:10px;margin-bottom:22px}
.tab{padding:8px 18px;border:1px solid var(--line);border-radius:20px;
cursor:pointer;color:var(--dim)}
.tab.on{border-color:var(--gold);color:var(--gold)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));
gap:18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;
padding:18px}
.card h2{font-size:15px;color:var(--gold);margin-bottom:12px;
text-transform:uppercase;letter-spacing:1.5px}
label{display:block;color:var(--dim);font-size:12.5px;margin:10px 0 4px}
input,textarea,select{width:100%;background:#0d0a17;color:var(--text);
border:1px solid var(--line);border-radius:8px;padding:9px 11px;font:inherit}
textarea{min-height:64px;resize:vertical}
button{background:var(--gold);color:#1b1406;border:0;border-radius:8px;
padding:10px 18px;font:inherit;font-weight:700;cursor:pointer;margin-top:12px}
button.ghost{background:transparent;color:var(--gold);
border:1px solid var(--gold)}
button:disabled{opacity:.45;cursor:default}
.stepper{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}
.step{font-size:12px;padding:4px 10px;border-radius:12px;
border:1px solid var(--line);color:var(--dim)}
.step.done{border-color:var(--gold);color:var(--gold)}
.step.now{background:var(--gold);color:#1b1406;font-weight:700}
pre{background:#080611;border:1px solid var(--line);border-radius:8px;
padding:10px;font-size:11.5px;max-height:260px;overflow:auto;
white-space:pre-wrap;word-break:break-all}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.pill{font-size:11.5px;padding:3px 10px;border-radius:10px;
border:1px solid var(--line);color:var(--dim)}
.pill.ok{border-color:#3f9d5a;color:#7fd89a}
.pill.bad{border-color:#9d3f3f;color:#d87f7f}
table{width:100%;border-collapse:collapse;font-size:13px}
td,th{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left}
a{color:var(--gold)} .muted{color:var(--dim);font-size:12.5px}
video{width:100%;border-radius:10px;margin-top:8px}
.msg{margin-top:10px;font-size:13px;color:#7fd89a;min-height:18px}
</style></head><body>
<h1><b>रहस्यलोक</b> Studio</h1>
<div class="sub">दो चैनल · लोकल रन + GitHub क्लाउड — एक जगह से</div>
<div class="tabs" id="tabs"></div>
<div class="grid">

<div class="card"><h2>New run — this Mac</h2>
<label>Topic (खाली = auto-pick)</label>
<textarea id="topic" placeholder="सोन भंडार की गुफाएं: ..."></textarea>
<div id="minwrap"><label>Length (minutes, 8–30)</label>
<input id="minutes" type="number" value="22" min="8" max="30"></div>
<div class="row"><button id="startLocal">Start local run</button>
<button class="ghost" id="cancelLocal">Cancel</button></div>
<div class="msg" id="localMsg"></div>
<div class="stepper" id="stepper"></div>
<div class="muted" id="runMeta"></div>
<pre id="log" hidden></pre></div>

<div class="card"><h2>GitHub cloud</h2>
<div class="row"><span class="pill" id="tokPill">token: none</span></div>
<label>Personal access token (classic, repo+workflow)</label>
<input id="tok" type="password" placeholder="ghp_...">
<div class="row"><label style="margin:10px 0 0">
<input type="checkbox" id="tokSave" style="width:auto"> remember on this Mac
</label><button id="tokSet" style="margin-left:auto">Use token</button></div>
<label>Dispatch workflow</label>
<div class="row"><select id="wf" style="flex:1"></select>
<button id="dispatch" style="margin:0">Fire ▶</button></div>
<div class="msg" id="ghMsg"></div>
<h2 style="margin-top:16px">Recent runs</h2>
<table id="runs"><tr><td class="muted">paste a token to load</td></tr></table>
</div>

<div class="card"><h2>Releases → download to Mac</h2>
<button class="ghost" id="relRefresh" style="margin-top:0">Refresh</button>
<div id="rels" class="muted" style="margin-top:10px">—</div></div>

<div class="card"><h2>Local outputs</h2><div id="outs" class="muted">—</div>
</div>

<div class="card"><h2>Setup — API keys (.env)</h2>
<div class="row" id="keyPills"></div>
<div id="keyInputs"></div>
<button id="saveKeys">Save keys</button>
<label style="margin-top:14px">Repo folder for this channel</label>
<div class="row"><input id="repoPath" style="flex:1">
<button id="savePath" style="margin:0">Set</button></div>
<div class="msg" id="setupMsg"></div></div>

</div><script>
const $=id=>document.getElementById(id);
let CH='rahasyalok', STATE=null;
const KEYS=["GEMINI_API_KEY","PEXELS_API_KEY","SARVAM_API_KEY",
"SARVAM_SPEAKER","FAL_KEY"];
async function j(url,opts){const r=await fetch(url,opts);return r.json()}
async function post(url,body){return j(url,{method:'POST',
headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})}

function renderTabs(){const t=$('tabs');t.innerHTML='';
Object.entries(STATE.channels).forEach(([k,c])=>{
const d=document.createElement('div');d.className='tab'+(k===CH?' on':'');
d.textContent=c.label;d.onclick=()=>{CH=k;refresh(true)};t.appendChild(d)})}

function renderLocal(){const L=STATE.local,s=$('stepper');s.innerHTML='';
if(L.state==='idle'){$('runMeta').textContent='';$('log').hidden=true;return}
const idx=L.stages.indexOf(L.stage);
L.stages.forEach((st,i)=>{const d=document.createElement('span');
d.className='step'+(i<idx?' done':i===idx?' now':'');d.textContent=st;
s.appendChild(d)});
$('runMeta').textContent=`${L.state} · ${L.minutes_elapsed} min elapsed`+
(L.returncode!=null?` · exit ${L.returncode}`:'');
$('log').hidden=false;$('log').textContent=L.log_tail||'';
$('log').scrollTop=$('log').scrollHeight}

function renderOuts(){const ch=STATE.channels[CH];
$('outs').innerHTML=STATE.outputs.length?'':'no finished videos yet';
STATE.outputs.forEach(o=>{const d=document.createElement('div');
d.style.marginBottom='14px';
d.innerHTML=`<b>${o.stamp}</b> <span class="muted">(${o.size_mb} MB)</span>
<br>`+o.files.map(f=>
`<a href="/files/${CH}/${o.stamp}/${f}" target="_blank">${f}</a>`)
.join(' · ')+
`<video controls preload="none" src="/files/${CH}/${o.stamp}/final.mp4">`;
$('outs').appendChild(d)})}

function renderSetup(){const ch=STATE.channels[CH];
$('keyPills').innerHTML=KEYS.map(k=>`<span class="pill ${STATE.keys[k]?'ok':'bad'}">${k.replace('_API_KEY','').replace('_KEY','')}</span>`).join('');
$('keyInputs').innerHTML=KEYS.map(k=>`<label>${k}</label>
<input data-k="${k}" type="password" placeholder="${STATE.keys[k]?'(saved)':'paste value'}">`).join('');
$('repoPath').value=ch.path;
$('tokPill').textContent='token: '+(STATE.token_set?'set ✓':'none');
$('tokPill').className='pill '+(STATE.token_set?'ok':'bad');
const wf=$('wf');wf.innerHTML='';
ch.workflows.forEach(w=>{const o=document.createElement('option');
o.value=w.file;o.dataset.inputs=w.inputs.join(',');o.textContent=w.label;
wf.appendChild(o)});
$('minwrap').style.display=
ch.workflows.some(w=>w.inputs.includes('minutes'))?'':'none'}

async function refresh(full){STATE=await j('/api/state?channel='+CH);
if(full){renderTabs();renderSetup();renderOuts();loadRuns();loadRels()}
renderLocal()}

$('startLocal').onclick=async()=>{const r=await post('/api/run/local',
{channel:CH,topic:$('topic').value,minutes:$('minutes').value});
$('localMsg').textContent=r.ok?'started — log below':r.msg};
$('cancelLocal').onclick=async()=>{await post('/api/run/cancel',{})};
$('tokSet').onclick=async()=>{await post('/api/token',
{token:$('tok').value,remember:$('tokSave').checked});
$('tok').value='';refresh(true)};
$('dispatch').onclick=async()=>{const sel=$('wf').selectedOptions[0];
const r=await post('/api/gh/dispatch',{channel:CH,workflow:sel.value,
topic:$('topic').value,minutes:$('minutes').value,
inputs:sel.dataset.inputs});$('ghMsg').textContent=r.msg;
setTimeout(loadRuns,2500)};
$('relRefresh').onclick=()=>loadRels();
$('saveKeys').onclick=async()=>{const body={channel:CH};
document.querySelectorAll('#keyInputs input').forEach(i=>{
if(i.value)body[i.dataset.k]=i.value});
await post('/api/env',body);$('setupMsg').textContent='keys saved to .env';
refresh(true)};
$('savePath').onclick=async()=>{await post('/api/paths',
{channel:CH,path:$('repoPath').value});
$('setupMsg').textContent='path saved';refresh(true)};

async function loadRuns(){const r=await j('/api/gh/runs?channel='+CH);
const t=$('runs');
if(r.error){t.innerHTML=`<tr><td class="muted">${r.error}</td></tr>`;return}
t.innerHTML='<tr><th>#</th><th>workflow</th><th>status</th><th></th></tr>'+
r.runs.map(w=>`<tr><td>${w.number}</td><td>${w.name}</td>
<td>${w.conclusion||w.status}</td>
<td><a href="${w.url}" target="_blank">open</a></td></tr>`).join('')}

async function loadRels(){const r=await j('/api/gh/releases?channel='+CH);
const d=$('rels');
if(r.error){d.textContent=r.error;return}
d.innerHTML=r.releases.map(rel=>`<div style="margin-bottom:12px">
<b>${rel.name||rel.tag}</b>${rel.draft?' <span class="pill">draft</span>':''}
<br>`+rel.assets.map(a=>`<a href="#" onclick="dl(${a.id},'${rel.tag}',
'${a.name}');return false">${a.name}</a>
<span class="muted">(${a.size_mb} MB)</span>`).join(' · ')+'</div>').join('')
||'no releases yet'}

window.dl=async(id,tag,name)=>{$('ghMsg').textContent='downloading '+name+
' …';const r=await post('/api/gh/download',{channel:CH,asset_id:id,tag:tag,
name:name});$('ghMsg').textContent=r.msg};

refresh(true);setInterval(()=>refresh(false),3000);
setInterval(loadRuns,45000);
</script></body></html>"""


if __name__ == "__main__":
    os.makedirs(DOWNLOADS, exist_ok=True)
    print(f"रहस्यलोक Studio → http://127.0.0.1:{APP_PORT}")
    app.run(host="127.0.0.1", port=APP_PORT, debug=False)
