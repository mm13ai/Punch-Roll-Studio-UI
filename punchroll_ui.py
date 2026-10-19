#!/usr/bin/env python3
"""Punch & Roll Studio - a local web UI for daveshap/PunchAndRollAutomation.

Run from your project folder (the one holding raw/, markup/, edited/):
    python punchroll_ui.py            # opens http://127.0.0.1:8765
    python punchroll_ui.py --root D:/book --port 9000

Needs only the Python standard library. Commands run as
`<this python> -m punchroll ...`, so use the same environment you installed
punchroll into.
"""
import argparse, io, json, os, shutil, subprocess, sys, threading, urllib.request, uuid, webbrowser, zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ALLOWED = {"models", "transcript", "cut", "readback", "clicks", "lost", "markcheck", "declick",
           "standards", "verify", "batch", "scorecard", "said", "assemble", "picture"}
EXTS = {".wav", ".mp3", ".flac", ".m4a", ".md", ".toml", ".json", ".docx", ".txt", ".png"}
SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv", "src", "tests", "docs"}
ROOT = Path.cwd()
PORT = 8765
JOBS = {}


def safe(p):
    r = (ROOT / p).resolve()
    if r != ROOT and ROOT not in r.parents:
        raise ValueError("path is outside the project folder - use \"Change folder\" in the sidebar")
    return r


def start(argv):
    jid = uuid.uuid4().hex[:10]
    job = {"out": [], "done": False, "code": None, "proc": None}
    JOBS[jid] = job

    def run():
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}
        try:
            p = subprocess.Popen([sys.executable, "-m", "punchroll", *argv], cwd=ROOT, env=env,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding="utf-8", errors="replace", bufsize=1)
            job["proc"] = p
            for line in p.stdout:
                job["out"].append(line)
            p.wait()
            job["code"] = p.returncode
        except Exception as e:
            job["out"].append(f"Could not start: {e}\n")
            job["code"] = -1
        job["done"] = True

    threading.Thread(target=run, daemon=True).start()
    return jid


REPO_URL = "https://github.com/daveshap/PunchAndRollAutomation"
HERE = Path(__file__).resolve().parent


def installed():
    r = subprocess.run([sys.executable, "-c", "import punchroll"], capture_output=True, cwd=ROOT)
    return r.returncode == 0


def find_repo(explicit=None):
    cands = [Path(explicit)] if explicit else []
    cands += [ROOT / "PunchAndRollAutomation", ROOT, HERE / "PunchAndRollAutomation", HERE]
    for c in cands:
        if (c / "pyproject.toml").exists() and (c / "src" / "punchroll").exists():
            return c.resolve()
    return None


def setup(log, repo=None, cuda=True, models=True):
    """Download the repo if needed, install it with all extras, fetch models. Returns 0 on success."""
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"}

    def sh(cmd, cwd=None):
        log("$ " + " ".join(cmd) + "\n")
        p = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace", bufsize=1)
        for line in p.stdout:
            log(line)
        return p.wait()

    log(f"Python {sys.version.split()[0]} at {sys.executable}\n")
    if sys.version_info < (3, 10):
        log("Warning: Python 3.10+ is recommended (the README uses 3.13).\n")
    r = find_repo(repo)
    if r:
        log(f"[1/4] Using repo at {r}\n")
    else:
        log(f"[1/4] Downloading {REPO_URL} ...\n")
        data = urllib.request.urlopen(REPO_URL + "/archive/refs/heads/main.zip", timeout=180).read()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(HERE)
        r = HERE / "PunchAndRollAutomation"
        if r.exists():
            shutil.rmtree(r)
        (HERE / "PunchAndRollAutomation-main").rename(r)
        log(f"      extracted to {r}\n")
    if cuda and shutil.which("nvidia-smi"):
        log("[2/4] NVIDIA GPU found: installing CUDA build of PyTorch (large download)\n")
        if sh([sys.executable, "-m", "pip", "install", "torch", "torchaudio", "--index-url",
               "https://download.pytorch.org/whl/cu126"]):
            log("      CUDA PyTorch failed; continuing with the CPU build.\n")
    else:
        log("[2/4] Skipping GPU PyTorch (no NVIDIA GPU found, or skipped)\n")
    log("[3/4] Installing punchroll and dependencies\n")
    if sh([sys.executable, "-m", "pip", "install", "-e", ".[all,pictures,listen]"], cwd=r):
        log("\nInstall failed - see the errors above.\n")
        return 1
    if models:
        log("[4/4] Downloading speech models\n")
        if sh([sys.executable, "-m", "punchroll", "models"], cwd=ROOT):
            return 1
    else:
        log("[4/4] Skipping model download\n")
    log("\nAll set. Pick a step from the sidebar.\n")
    return 0


SETUP_AP = argparse.ArgumentParser()
SETUP_AP.add_argument("--repo")
SETUP_AP.add_argument("--no-cuda", action="store_true")
SETUP_AP.add_argument("--no-models", action="store_true")


def start_setup(args):
    o = SETUP_AP.parse_args(args)
    jid = uuid.uuid4().hex[:10]
    job = {"out": [], "done": False, "code": None, "proc": None}
    JOBS[jid] = job

    def run():
        try:
            job["code"] = setup(job["out"].append, o.repo or None, not o.no_cuda, not o.no_models)
        except Exception as e:
            job["out"].append(f"\nSetup failed: {e}\n")
            job["code"] = 1
        job["done"] = True

    threading.Thread(target=run, daemon=True).start()
    return jid


DIALOG = r'''
import sys
try:
    import tkinter as tk
    from tkinter import filedialog as fd
    root = tk.Tk()
except Exception:
    sys.exit(2)
mode, start, title = sys.argv[1:4]
root.withdraw()
root.attributes("-topmost", True)
root.update()
kw = {"title": title, "parent": root}
if start:
    kw["initialdir"] = start
if mode == "dir":
    p = fd.askdirectory(**kw)
elif mode == "save":
    p = fd.asksaveasfilename(**kw)
else:
    p = fd.askopenfilename(filetypes=[("Audio, mark-up, project files", "*.wav *.mp3 *.flac *.m4a *.md *.toml *.json *.docx *.txt"), ("All files", "*.*")], **kw)
print(p or "")
'''


# Native file/folder dialog: tkinter first (Windows/mac/Linux), then osascript / zenity / kdialog.
def pick(mode, start, title):
    d = ROOT
    try:
        sp = (ROOT / start) if start else ROOT
        d = sp if sp.is_dir() else (sp.parent if sp.parent.is_dir() else ROOT)
    except Exception:
        pass
    t = title.replace('"', "")
    cmds = [[sys.executable, "-c", DIALOG, mode, str(d), t]]
    if sys.platform == "darwin":
        verb = {"dir": "choose folder", "save": "choose file name"}.get(mode, "choose file")
        cmds.append(["osascript", "-e", f'POSIX path of ({verb} with prompt "{t}" default location POSIX file "{d}")'])
    elif sys.platform.startswith("linux"):
        extra = {"dir": ["--directory"], "save": ["--save", "--confirm-overwrite"]}.get(mode, [])
        cmds.append(["zenity", "--file-selection", f"--title={t}", f"--filename={d}/"] + extra)
        cmds.append(["kdialog", {"dir": "--getexistingdirectory", "save": "--getsavefilename"}.get(mode, "--getopenfilename"), str(d)])
    for i, c in enumerate(cmds):
        try:
            r = subprocess.run(c, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        except FileNotFoundError:
            continue
        if i == 0 and r.returncode != 0:
            continue
        out = r.stdout.strip().splitlines()
        return out[-1].strip() if r.returncode == 0 and out else ""
    raise RuntimeError("No file dialog available. Install tkinter (Linux: sudo apt install python3-tk) or type the path instead.")


def rel(p):
    q = Path(p).resolve()
    return q.relative_to(ROOT).as_posix() if (q == ROOT or ROOT in q.parents) else str(q)


def list_files():
    found = []
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP and not d.startswith(".")]
        if Path(dp).relative_to(ROOT).parts.__len__() > 3:
            dn[:] = []
        for f in fn:
            if Path(f).suffix.lower() in EXTS:
                found.append((Path(dp) / f).relative_to(ROOT).as_posix())
    return sorted(found)[:2000]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, body, ctype="application/json", code=200):
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def host_ok(self):
        return self.headers.get("Host", "") in (f"127.0.0.1:{PORT}", f"localhost:{PORT}")

    def do_GET(self):
        if not self.host_ok():
            return self.send({"error": "bad host"}, code=403)
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/":
                return self.send(PAGE.encode(), "text/html")
            if u.path == "/api/info":
                return self.send({"root": str(ROOT), "installed": installed(),
                                  "python": sys.executable})
            if u.path == "/api/files":
                return self.send(list_files())
            if u.path == "/api/read":
                return self.send({"text": safe(q["path"]).read_text(encoding="utf-8")})
            if u.path == "/api/job":
                j = JOBS[q["id"]]
                n = int(q.get("n", 0))
                return self.send({"out": "".join(j["out"][n:]), "n": len(j["out"]), "done": j["done"], "code": j["code"]})
        except Exception as e:
            return self.send({"error": str(e)}, code=400)
        self.send({"error": "not found"}, code=404)

    def do_POST(self):
        global ROOT
        if not self.host_ok() or "json" not in self.headers.get("Content-Type", ""):
            return self.send({"error": "forbidden"}, code=403)
        try:
            d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if self.path == "/api/run":
                if d["cmd"] == "setup":
                    return self.send({"id": start_setup(list(map(str, d.get("args", []))))})
                if d["cmd"] not in ALLOWED:
                    raise ValueError("command not allowed")
                return self.send({"id": start([d["cmd"], *map(str, d.get("args", []))])})
            if self.path == "/api/browse":
                p = pick(d.get("mode", "open"), d.get("start", ""), d.get("title", "Choose"))
                return self.send({"path": (str(Path(p).resolve()) if d.get("abs") else rel(p)) if p else ""})
            if self.path == "/api/root":
                r = Path(d["path"]).expanduser().resolve()
                if not r.is_dir():
                    raise ValueError("not a folder")
                ROOT = r
                return self.send({"root": str(r)})
            if self.path == "/api/cancel":
                p = JOBS[d["id"]]["proc"]
                if p and p.poll() is None:
                    p.terminate()
                return self.send({"ok": True})
            if self.path == "/api/write":
                f = safe(d["path"])
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(d["text"], encoding="utf-8")
                return self.send({"ok": True})
        except Exception as e:
            return self.send({"error": str(e)}, code=400)
        self.send({"error": "not found"}, code=404)


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Punch &amp; Roll Studio</title>
<style>
:root{color-scheme:light dark;--bg:#f6f5f2;--panel:#fff;--ink:#1d1d1f;--mute:#6b6b72;--line:#e2e0da;--acc:#c2410c;--accink:#fff;--con:#16171a;--conink:#d6d8dd}
@media(prefers-color-scheme:dark){:root{--bg:#121214;--panel:#1a1b1f;--ink:#ececee;--mute:#9a9aa3;--line:#2b2c32;--acc:#f08a4b;--accink:#1a1209}}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 system-ui,Segoe UI,sans-serif;background:var(--bg);color:var(--ink);display:flex;min-height:100vh}
nav{width:230px;flex:none;background:var(--panel);border-right:1px solid var(--line);padding:16px 10px;overflow:auto;height:100vh;position:sticky;top:0}
nav h1{font-size:15px;margin:0 8px 2px}nav .root{font-size:11px;color:var(--mute);margin:0 8px 14px;word-break:break-all}
.lnk{display:block;color:var(--acc);cursor:pointer;font-size:11.5px;margin:0 8px 14px}.lnk:hover{text-decoration:underline}
.pick{display:flex;gap:6px}.pick input{flex:1;min-width:0}.pick .btn{padding:6px 12px;white-space:nowrap;font-weight:500}
nav h2{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);margin:14px 8px 4px}
nav button{display:block;width:100%;text-align:left;background:none;border:0;color:inherit;padding:6px 8px;border-radius:6px;cursor:pointer;font:inherit}
nav button:hover{background:var(--bg)}nav button.on{background:var(--acc);color:var(--accink)}
main{flex:1;min-width:0;padding:22px 28px;max-width:980px}
h3{margin:0 0 4px;font-size:20px}p.d{margin:0 0 16px;color:var(--mute)}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:14px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
label{display:block;font-weight:600;font-size:12.5px;margin-bottom:3px}label small{font-weight:400;color:var(--mute)}
input[type=text],select,textarea{width:100%;padding:7px 9px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:inherit;font:inherit}
input:focus,select:focus,textarea:focus{outline:2px solid var(--acc);outline-offset:-1px}
.chk{display:flex;gap:8px;align-items:center;font-weight:500;margin-top:20px}
.bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.btn{background:var(--acc);color:var(--accink);border:0;padding:8px 16px;border-radius:7px;font:inherit;font-weight:600;cursor:pointer}
.btn.s{background:var(--bg);color:var(--ink);border:1px solid var(--line)}.btn:disabled{opacity:.5;cursor:default}
code.cmd{display:block;font:12px ui-monospace,Consolas,monospace;color:var(--mute);margin-top:12px;word-break:break-all}
#con{background:var(--con);color:var(--conink);border-radius:10px;padding:12px 14px;font:12.5px/1.5 ui-monospace,Consolas,monospace;white-space:pre-wrap;word-break:break-word;min-height:120px;max-height:50vh;overflow:auto;margin:0}
.st{font-size:12px;padding:2px 9px;border-radius:99px;border:1px solid var(--line);color:var(--mute)}.st.ok{color:#16a34a;border-color:#16a34a}.st.bad{color:#dc2626;border-color:#dc2626}.st.run{color:var(--acc);border-color:var(--acc)}
#warn{background:#fef3c7;color:#78350f;border-radius:8px;padding:10px 14px;margin-bottom:14px;display:none}
textarea{font:13px/1.55 ui-monospace,Consolas,monospace;min-height:340px;resize:vertical}
.legend td{padding:2px 14px 2px 0;font-size:12.5px;color:var(--mute)}.legend code{color:var(--ink)}
@media(max-width:760px){body{flex-direction:column}nav{width:auto;height:auto;position:static}}
</style></head><body>
<nav><h1>Punch &amp; Roll Studio</h1><div class="root" id="root" style="margin-bottom:4px"></div><span class="lnk" id="chroot">Change folder…</span><div id="nav"></div></nav>
<main><div id="warn"></div><div id="view"></div>
<div class="bar" style="margin:6px 0"><b>Output</b><span class="st" id="st">idle</span>
<button class="btn s" id="cancel" style="display:none">Stop</button><button class="btn s" id="clear">Clear</button></div>
<pre id="con"></pre></main>
<datalist id="files"></datalist>
<script>
const $=s=>document.querySelector(s);
const F=(k,l,o={})=>({k,l,...o});
const CMDS=[
['Setup',[{n:'setup',t:'Install / repair',d:'Downloads the repo if needed, installs punchroll with every dependency (GPU PyTorch if an NVIDIA card is found), then fetches the speech models. Safe to re-run.',
 pre:'Installs into the Python that started this UI',f:[
 F('repo','Repo folder (auto-detected, or downloaded for you)',{fl:'--repo',ex:'PunchAndRollAutomation',dir:1}),
 F('nc','Skip GPU (CUDA) PyTorch',{fl:'--no-cuda',bool:1}),F('nm','Skip speech-model download',{fl:'--no-models',bool:1})]},{n:'models',t:'Download speech models',d:'One-time download of the recognition models (cached afterwards).',f:[]}]],
['Edit',[
{n:'transcript',t:'1 · Transcribe',d:'Writes markup/<name>.transcript.md with words, timestamps, pauses and nonword sounds.',f:[F('raw','Recording',{p:1,ex:'raw/ch01.wav',file:1})]},
{n:'editor',t:'2 · Mark-up editor',d:'Open, adjust and validate a mark-up file.'},
{n:'cut',t:'3 · Render & master',d:'Applies the mark-up and writes WAV, MP3, report and edit map.',f:[
 F('raw','Recording',{p:1,ex:'raw/ch01.wav',file:1}),F('markup','Mark-up',{fl:'--markup',ex:'markup/ch01.md',file:1}),
 F('config','Settings',{fl:'--config',ex:'examples/settings.toml',file:1}),F('script','Manuscript (optional)',{fl:'--script',file:1}),
 F('from','From heading',{fl:'--from',ex:'Chapter 1'}),F('to','To heading',{fl:'--to',ex:'Chapter 2'}),
 F('ro','Preview report only (no render)',{fl:'--report-only',bool:1})]}]],
['Project',[
{n:'batch',t:'Batch',d:'Process every recording listed in a project TOML. Finished outputs are reused unless inputs change.',f:[
 F('project','Project file',{p:1,ex:'project.toml',file:1}),F('only','Only these recordings',{fl:'--only',ex:'ch01'}),
 F('force','Force rebuild',{fl:'--force',bool:1}),F('proof','Manuscript proof reports',{fl:'--proof',bool:1})]},
{n:'scorecard',t:'Scorecard',d:'Compare the finished files: clicks, noise floor, tone, pitch, pace.',f:[
 F('project','Project file',{p:1,ex:'project.toml',file:1}),F('l','Trained-listener estimates',{fl:'--listener',bool:1})]},
{n:'assemble',t:'Assemble pickups',d:'Combine passages across recordings using an assembly plan.',f:[
 F('plan','Assembly plan',{p:1,ex:'examples/assembly.json',file:1}),F('o','Output file',{fl:'-o',ex:'assembled/ch01.wav',file:1,sv:1})]},
{n:'said',t:'What was said',d:'Finished transcripts of what the reader actually said.',f:[
 F('sub','Step',{p:1,sel:['draft','build','changes']}),F('project','Project file',{p:1,ex:'project.toml',file:1}),
 F('into','Write changes into (changes only)',{fl:'--into',ex:'notes.md',file:1,sv:1})]}]],
['Check',[
{n:'readback',t:'Readback',d:'Every kept word checked against the finished audio: missing, doubled, returned.',f:[
 F('edited','Finished file',{p:1,ex:'edited/ch01.mp3',file:1}),F('markup','Mark-up',{fl:'--markup',ex:'markup/ch01.md',file:1})]},
{n:'clicks',t:'Clicks',d:'Count clicks in the finished file and trace them to the recording.',f:[
 F('raw','Recording',{p:1,file:1}),F('edited','Finished file',{p:1,file:1}),F('config','Settings',{fl:'--config',file:1})]},
{n:'lost',t:'Lost material',d:'Stretches cut from the recording that are never said again.',f:[
 F('raw','Recording',{p:1,file:1}),F('edited','Finished file',{p:1,file:1})]},
{n:'markcheck',t:'Mark-up check',d:'Validate a mark-up against its transcript and list what is left to judge.',f:[
 F('markup','Mark-up',{p:1,ex:'markup/ch01.md',file:1})]},
{n:'declick',t:'Declick mark-up',d:'Strike clicks in the mark-up. Without "write" this is a dry run.',f:[
 F('markup','Mark-up',{p:1,file:1}),F('raw','Recording',{fl:'--raw',file:1}),F('fin','Finished file',{fl:'--finished',file:1}),
 F('w','Write changes to the mark-up',{fl:'--write',bool:1})]},
{n:'standards',t:'Standards (ACX etc.)',d:'ACX / ElevenLabs measurements, pauses, click rate, tone, total duration.',f:[
 F('files','Files or glob',{p:1,ex:'edited/*.mp3',file:1}),F('o','Write report to',{fl:'-o',ex:'edited/standards.md',file:1,sv:1})]},
{n:'verify',t:'Verify vs manuscript',d:'Differences, pickups, missing lines and added material against a manuscript.',f:[
 F('file','Audio file',{p:1,file:1}),F('script','Manuscript',{fl:'--script',ex:'book.docx',file:1}),
 F('from','From heading',{fl:'--from'}),F('to','To heading',{fl:'--to'})]},
{n:'picture',t:'Spectrogram',d:'Spectrogram of a passage; optionally compare source and result.',f:[
 F('file','Audio file',{p:1,file:1}),F('at','At (m:ss)',{fl:'--at',ex:'3:08'}),F('with','Compare with',{fl:'--with',file:1}),F('wa','Compare at',{fl:'--with-at',ex:'3:14.5'})]}]]];
let cur,job=null,timer=null;
const el=(h)=>{const t=document.createElement('template');t.innerHTML=h.trim();return t.content.firstChild};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function api(p,b){const r=await fetch(p,b&&{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});return r.json()}
function nav(){const n=$('#nav');n.innerHTML='';CMDS.forEach(([g,list])=>{n.append(el(`<h2>${g}</h2>`));list.forEach(c=>{
 const b=el(`<button data-n="${c.n}">${esc(c.t)}</button>`);b.onclick=()=>show(c.n);n.append(b)})})}
function find(n){for(const[,l]of CMDS)for(const c of l)if(c.n===n)return c}
function show(n){cur=find(n);document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('on',b.dataset.n===n));
 const v=$('#view');v.innerHTML='';v.append(el(`<h3>${esc(cur.t)}</h3>`),el(`<p class="d">${esc(cur.d)}</p>`));
 if(n==='editor')return editor(v);
 const saved=JSON.parse(localStorage.getItem('pr_'+n)||'{}');
 const card=el('<div class="card"><div class="grid"></div></div>'),g=card.firstChild;
 cur.f.forEach(f=>{const id='f_'+f.k,val=saved[f.k]??'';let inp;
  if(f.bool)g.append(el(`<label class="chk"><input type="checkbox" id="${id}" ${val?'checked':''}> ${esc(f.l)}</label>`));
  else{inp=f.sel?`<select id="${id}">${f.sel.map(o=>`<option ${o===val?'selected':''}>${o}</option>`)}</select>`
   :`<input type="text" id="${id}" value="${esc(val)}" placeholder="${esc(f.ex||'')}" ${f.file?'list="files"':''} autocomplete="off">`;
   if(f.file||f.dir)inp=`<div class="pick">${inp}<button type="button" class="btn s" data-b="1">Browse…</button></div>`;
   const dv=el(`<div><label for="${id}">${esc(f.l)}${f.p?'':' <small>(optional)</small>'}</label>${inp}</div>`);g.append(dv);
   const bb=dv.querySelector('[data-b]');if(bb)bb.onclick=()=>browse(id,f.dir?'dir':f.sv?'save':'open','Select '+f.l,bb)}});
 const bar=el('<div class="bar" style="margin-top:14px"><button class="btn" id="run">Run</button></div>');
 card.append(bar,el('<code class="cmd" id="pre"></code>'));v.append(card);
 card.oninput=card.onchange=()=>{save();preview()};$('#run').onclick=run;preview()}
function vals(){const o={};cur.f.forEach(f=>{const e=$('#f_'+f.k);o[f.k]=f.bool?e.checked:e.value.trim()});return o}
function save(){localStorage.setItem('pr_'+cur.n,JSON.stringify(vals()))}
function argv(){const v=vals(),a=[];cur.f.filter(f=>f.p).forEach(f=>v[f.k]&&a.push(v[f.k]));
 cur.f.filter(f=>f.fl).forEach(f=>{if(f.bool){v[f.k]&&a.push(f.fl)}else if(v[f.k])a.push(f.fl,v[f.k])});return a}
function q(s){return /[\s*?]/.test(s)?`"${s}"`:s}
function preview(){$('#pre').textContent=cur.pre||'python -m punchroll '+[cur.n,...argv()].map(q).join(' ')}
function status(t,c){const s=$('#st');s.textContent=t;s.className='st '+(c||'')}
async function exec(cmd,args){if(job&&!job.done)return;$('#con').textContent='';status('running','run');$('#cancel').style.display='';
 const r=await api('/api/run',{cmd,args});if(r.error){status('error','bad');$('#con').textContent=r.error;return}
 job={id:r.id,n:0,done:false,cmd};poll()}
function run(){save();exec(cur.n,argv())}
async function poll(){const r=await api(`/api/job?id=${job.id}&n=${job.n}`),c=$('#con');
 if(r.out){const bottom=c.scrollTop+c.clientHeight>=c.scrollHeight-30;c.textContent+=r.out;if(bottom)c.scrollTop=c.scrollHeight}
 job.n=r.n;if(r.done){job.done=true;if(job.cmd==='setup')refresh();$('#cancel').style.display='none';status(r.code===0?'finished':'exit '+r.code,r.code===0?'ok':'bad');return}
 setTimeout(poll,400)}
$('#cancel').onclick=()=>job&&api('/api/cancel',{id:job.id});$('#clear').onclick=()=>{$('#con').textContent='';status('idle')};
async function browse(id,mode,title,btn){const e=$('#'+id);btn.disabled=true;btn.textContent='Choosing…';
 try{const r=await api('/api/browse',{mode,start:e.value.trim(),title});if(r.error)alert(r.error);
  else if(r.path){e.value=r.path;e.dispatchEvent(new Event('input',{bubbles:true}))}}finally{btn.disabled=false;btn.textContent='Browse…'}}
async function chroot(){const r=await api('/api/browse',{mode:'dir',abs:1,start:'',title:'Choose your project folder'});
 if(r.error)return alert(r.error);if(!r.path)return;const x=await api('/api/root',{path:r.path});
 if(x.error)return alert(x.error);await refresh();await loadFiles();show(cur.n)}
function editor(v){const saved=localStorage.getItem('pr_editor')||'';
 const c=el(`<div class="card"><label for="ep">Mark-up file</label><div class="bar"><input type="text" id="ep" list="files" value="${esc(saved)}" placeholder="markup/ch01.md" style="flex:1;min-width:220px">
 <button class="btn s" id="br">Browse…</button><button class="btn s" id="ld">Load</button><button class="btn" id="sv">Save</button><button class="btn s" id="ck">Save &amp; check</button><span class="st" id="es"></span></div>
 <textarea id="et" spellcheck="false" style="margin-top:12px" placeholder="Load a mark-up file to edit it"></textarea>
 <table class="legend" style="margin-top:10px"><tr><td><code>~~words~~</code></td><td>cut these words</td></tr><tr><td><code>~~{sound 0.11 -24}~~</code></td><td>cut a nonword sound</td></tr>
 <tr><td><code>{0.75} → {0.40}</code></td><td>change a pause (edit the number; insert <code>{0.60}</code> to add one)</td></tr></table></div>`);v.append(c);
 const msg=(t,k)=>{const s=$('#es');s.textContent=t;s.className='st '+(k||'')};
 const path=()=>{const p=$('#ep').value.trim();localStorage.setItem('pr_editor',p);return p};
 $('#ld').onclick=async()=>{const r=await api('/api/read?path='+encodeURIComponent(path()));if(r.error)return msg(r.error,'bad');$('#et').value=r.text;msg('loaded','ok')};
 $('#br').onclick=async()=>{await browse('ep','open','Choose a mark-up file',$('#br'));if($('#ep').value.trim())$('#ld').click()};
 const save=async()=>{const r=await api('/api/write',{path:path(),text:$('#et').value});r.error?msg(r.error,'bad'):msg('saved','ok');return !r.error};
 $('#sv').onclick=save;$('#ck').onclick=async()=>{if(await save())exec('markcheck',[path()])};
 $('#et').onkeydown=e=>{if((e.ctrlKey||e.metaKey)&&e.key==='s'){e.preventDefault();save()}}}
async function refresh(){const i=await api('/api/info');$('#root').textContent=i.root;const w=$('#warn');
 if(i.installed)w.style.display='none';else{w.style.display='block';w.textContent='punchroll is not installed in '+i.python+' yet. Open "Install / repair" and press Run: it downloads the repo if needed and installs everything.'}return i}
async function loadFiles(){const fl=await api('/api/files');$('#files').innerHTML=fl.map(f=>`<option value="${esc(f)}">`).join('')}
(async()=>{nav();$('#chroot').onclick=chroot;const i=await refresh();await loadFiles();show(i.installed?'transcript':'setup')})();
</script></body></html>"""


def main():
    global ROOT, PORT
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="project folder (default: current folder)")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--auto-setup", action="store_true", help="install punchroll first if it is missing")
    ap.add_argument("--setup", action="store_true", help="run install/repair now, then start the UI")
    ap.add_argument("--repo", help="existing PunchAndRollAutomation folder")
    ap.add_argument("--no-cuda", action="store_true", help="skip GPU PyTorch")
    ap.add_argument("--no-models", action="store_true", help="skip speech-model download")
    a = ap.parse_args()
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    ROOT, PORT = Path(a.root).resolve(), a.port
    if a.setup or (a.auto_setup and not installed()):
        print("Setting up punchroll (the first run can take several minutes)...\n")
        rc = setup(lambda t: print(t, end="", flush=True), a.repo, not a.no_cuda, not a.no_models)
        print("\nSetup finished.\n" if rc == 0 else "\nSetup hit errors; the UI will still start so you can retry.\n")
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    url = f"http://127.0.0.1:{PORT}"
    print(f"Punch & Roll Studio on {url}  (project folder: {ROOT})\nCtrl+C to stop.")
    if not a.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
