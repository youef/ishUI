#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local ISH UI web console. Loopback-only; no arbitrary shell endpoint."""
import json
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE = Path.home() / ".config" / "ishui"
REPORTS = BASE / "reports"
HOST = "127.0.0.1"
PORTS = range(8765, 8771)
MAX_REQUEST = 16384
MAX_OUTPUT = 12000
_SERVER = None
_SERVER_STARTED_AT = time.time()
_PAUSED = False

PAGE = r"""<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="dark"><title>ISH UI Control Center</title>
<style>
:root{font-family:system-ui,-apple-system,sans-serif;color:#e8eefb;background:#0a1020}*{box-sizing:border-box}
body{margin:0;background:radial-gradient(circle at 90% 0,#142b4b 0,transparent 35%),#0a1020}
header{padding:22px max(18px,calc((100% - 1120px)/2));border-bottom:1px solid #25344d;background:#0d1728dd;position:sticky;top:0;backdrop-filter:blur(14px)}
h1{font-size:22px;margin:0}header p{margin:5px 0 0;color:#91a4c2;font-size:13px}
main{max-width:1120px;margin:22px auto;padding:0 16px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px}
.card{background:#111d31;border:1px solid #273953;border-radius:16px;padding:17px;box-shadow:0 12px 35px #0002}
h2{font-size:16px;margin:0 0 13px}.muted{color:#91a4c2;font-size:13px}.stat{font-size:26px;font-weight:700;margin:8px 0}
input,select,button{font:inherit;border-radius:10px;padding:11px;border:1px solid #344965;background:#0b1526;color:#edf4ff;width:100%;margin:5px 0}
button{background:#1768a8;border:0;font-weight:650;cursor:pointer}button.secondary{background:#263b57}button.warn{background:#8a4b20}
.row{display:flex;gap:8px;align-items:center}.row>*{flex:1}.out{white-space:pre-wrap;overflow-wrap:anywhere;background:#07101d;border:1px solid #263750;padding:12px;border-radius:10px;min-height:55px;max-height:300px;overflow:auto;font:12px ui-monospace,monospace}
.list{display:grid;gap:8px}.item{padding:10px;border-radius:10px;background:#0b1627;border:1px solid #253750}
nav{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 14px}nav button{width:auto;padding:8px 13px}
section{margin:14px 0}.hidden{display:none}.status{color:#8ce0b2}.danger{color:#ffc28b}small{color:#91a4c2}
</style></head><body>
<header><h1>ISH UI <span style="color:#71c7ff">/ WEB CONTROL</span></h1><p>لوحة إدارة محلية — متاحة مباشرة على هذا الجهاز</p></header>
<main><div id="app">
<nav><button onclick="show('home')">الرئيسية</button><button onclick="show('tools')">الأدوات والأوامر</button><button onclick="show('audit')">فحص النطاق</button><button onclick="show('reports')">التقارير</button></nav>
<section id="home"><div class="card"><h2>التحكم بالخادم</h2><p class="muted">إيقاف الخدمة يوقف استقبال أوامر الأدوات والفحوصات، مع إبقاء صفحة التحكم متاحة لإعادة التشغيل.</p><div class="row"><button class="warn" onclick="serverAction('stop')">إيقاف الخدمة</button><button onclick="serverAction('start')">تشغيل الخدمة</button></div><div id="servermsg" class="muted"></div></div><div class="grid"><div class="card"><h2>حالة الخادم</h2><div class="stat status" id="server">متصل</div><div class="muted" id="sys"></div></div><div class="card"><h2>المهام المحفوظة</h2><div class="stat" id="jobs">—</div><div class="muted">مهام الفحص في قاعدة البيانات المحلية</div></div><div class="card"><h2>التقارير</h2><div class="stat" id="reportcount">—</div><div class="muted">ملفات JSON المحفوظة</div></div></div><div class="card" style="margin-top:14px"><h2>آخر التقارير</h2><div id="recent" class="list"></div></div></section>
<section id="tools" class="hidden"><div class="grid"><div class="card"><h2>أوامر النظام المسموحة</h2><p class="muted">قائمة محددة فقط؛ لا يوجد تنفيذ shell عشوائي من المتصفح.</p><select id="cmd"><option value="system">ملخص النظام والتخزين</option><option value="processes">العمليات</option><option value="network">معلومات الشبكة</option><option value="packages">الحزم المثبتة</option></select><button onclick="runCommand()">تنفيذ</button><div id="cmdout" class="out"></div></div>
<div class="card"><h2>البحث عن حزمة</h2><input id="searchpkg" placeholder="اسم الحزمة"><button class="secondary" onclick="searchPackage()">بحث في apk</button><div id="pkgout" class="out"></div></div>
<div class="card"><h2>تثبيت أداة / حزمة</h2><p class="muted">التثبيت يغيّر بيئة iSH. راجع اسم الحزمة قبل الموافقة.</p><input id="installpkg" placeholder="مثال: curl"><label class="muted"><input id="installconfirm" type="checkbox" style="width:auto"> أوافق على تثبيت هذه الحزمة</label><button class="warn" onclick="installPackage()">تثبيت الحزمة</button><div id="installout" class="out"></div></div></div></section>
<section id="audit" class="hidden"><div class="card"><h2>إدارة النطاقات المصرح بها</h2><p class="muted">أضف فقط النطاقات التي تملكها أو لديك تصريح صريح بفحصها. تحفظ القائمة محلياً على الجهاز.</p><div class="row"><input id="newdomain" placeholder="example.com"><button onclick="scopeAction('add')">إضافة النطاق</button></div><div id="scopeout" class="list"></div></div><div class="card"><h2>بدء فحص نطاق مصرح به</h2><p class="muted">يفحص فقط النطاقات المحفوظة في قائمة التصريح. الفحص منخفض التأثير ولا ينفذ استغلالاً.</p><input id="domain" placeholder="example.com"><button onclick="startAudit()">بدء الفحص</button><div id="auditout" class="out"></div></div></section>
<section id="reports" class="hidden"><div class="card"><h2>مكتبة التقارير</h2><button class="secondary" onclick="loadReports()">تحديث القائمة</button><div id="reportlist" class="list"></div><pre id="reportview" class="out"></pre></div></section>
</div></main>
<script>
async function api(path,body){let r=await fetch(path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});let j=await r.json();if(!r.ok)throw Error(j.error||'Request failed');return j}
function show(id){document.querySelectorAll('main section').forEach(x=>x.classList.add('hidden'));document.getElementById(id).classList.remove('hidden');if(id==='reports')loadReports();if(id==='audit')loadScope()}
function put(id,v){document.getElementById(id).textContent=v}
async function refresh(){try{let s=await api('/api/status');put('server',s.paused?'متوقف مؤقتاً':'يعمل');put('sys',s.platform+' · Python '+s.python+' · '+s.storage+' · مدة العملية '+s.uptime);put('jobs',s.jobs);put('reportcount',s.reports);let r=await api('/api/reports');renderRecent(r.files.slice(0,5));loadScope()}catch(e){put('server','غير متاح')}}
async function serverAction(action){try{let r=await api('/api/server',{action});put('servermsg',r.message);refresh()}catch(e){put('servermsg',e.message)}}
async function loadScope(){try{let r=await api('/api/scope');let el=document.getElementById('scopeout');el.innerHTML='';if(!r.domains.length){el.textContent='لا توجد نطاقات مصرح بها بعد.';return}r.domains.forEach(host=>{let d=document.createElement('div');d.className='item row';let t=document.createElement('span');t.textContent=host;let b=document.createElement('button');b.className='warn';b.textContent='حذف';b.onclick=()=>scopeAction('remove',host);d.append(t,b);el.appendChild(d)})}catch(e){put('scopeout',e.message)}}
async function scopeAction(action,domain){try{domain=domain||document.getElementById('newdomain').value;let r=await api('/api/scope',{action,domain,authorized:true});put('scopeout',r.message);document.getElementById('newdomain').value='';loadScope()}catch(e){put('scopeout',e.message)}}
function renderRecent(files){let el=document.getElementById('recent');el.innerHTML='';files.forEach(f=>{let d=document.createElement('div');d.className='item';d.textContent=f.name+' · '+f.modified;el.appendChild(d)})}
async function runCommand(){try{let r=await api('/api/command',{name:document.getElementById('cmd').value});put('cmdout',r.output)}catch(e){put('cmdout',e.message)}}
async function searchPackage(){try{let r=await api('/api/command',{name:'apk_search',query:document.getElementById('searchpkg').value});put('pkgout',r.output)}catch(e){put('pkgout',e.message)}}
async function installPackage(){if(!document.getElementById('installconfirm').checked){put('installout','فعّل مربع الموافقة أولاً.');return}try{let r=await api('/api/install',{package:document.getElementById('installpkg').value,confirm:true});put('installout',r.output)}catch(e){put('installout',e.message)}}
async function startAudit(){try{let r=await api('/api/audit',{domain:document.getElementById('domain').value});put('auditout','بدأت المهمة #'+r.job_id+' للنطاق '+r.domain+'. راجع التقارير بعد اكتمالها.')}catch(e){put('auditout',e.message)}}
async function loadReports(){try{let r=await api('/api/reports');let el=document.getElementById('reportlist');el.innerHTML='';r.files.forEach(f=>{let b=document.createElement('button');b.className='secondary';b.textContent=f.name;b.onclick=()=>viewReport(f.name);el.appendChild(b)})}catch(e){put('reportview',e.message)}}
async function viewReport(name){try{let r=await api('/api/report',{name});put('reportview',JSON.stringify(r.report,null,2))}catch(e){put('reportview',e.message)}}
refresh()
</script></body></html>"""

def _run(args, timeout=20):
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, timeout=timeout, check=False)
        return (p.stdout or "(لا توجد مخرجات)")[:MAX_OUTPUT]
    except Exception as exc:
        return "تعذر التنفيذ: " + str(exc)[:300]

def _audit_worker(job_id):
    log_path = BASE / ("web_audit_" + str(job_id) + ".log")
    script = Path(__file__).with_name("site_audit.py")
    try:
        with log_path.open("a", encoding="utf-8") as stream:
            subprocess.run([__import__("sys").executable, str(script), "--job", str(job_id)],
                           stdout=stream, stderr=subprocess.STDOUT, timeout=None, check=False)
    except Exception as exc:
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write("Audit worker error: " + str(exc)[:300] + "\n")

def _reports():
    REPORTS.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in sorted(REPORTS.glob("audit_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:100]:
        try:
            rows.append({"name": p.name, "modified": int(p.stat().st_mtime)})
        except OSError:
            pass
    return rows

def _status():
    usage = shutil.disk_usage(str(Path.home()))
    con = sqlite3.connect(str(BASE / "security_jobs.sqlite3"))
    try:
        jobs = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    except sqlite3.Error:
        jobs = 0
    finally:
        con.close()
    return {"platform": os.uname().sysname if hasattr(os, "uname") else "iSH",
            "python": __import__("platform").python_version(),
            "storage": str(usage.free // (1024 * 1024)) + " MB free",
            "jobs": jobs, "reports": len(_reports()), "paused": _PAUSED,
            "uptime": str(int(max(0, time.time() - _SERVER_STARTED_AT))) + " ثانية"}

class Handler(BaseHTTPRequestHandler):
    server_version = "ISHUI-Local/1.0"
    def log_message(self, fmt, *args):
        return
    def _json(self, code, data):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)
    def _body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length < 1 or length > MAX_REQUEST:
            raise ValueError("حجم الطلب غير صالح.")
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("صيغة الطلب غير صالحة.")
        return value
    def _authorized(self):
        return True
    def do_GET(self):
        if self.path == "/":
            raw = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)
            return
        if self.path == "/api/status":
            self._json(200, _status())
        elif self.path == "/api/scope":
            from site_audit import load_scope
            self._json(200, {"domains": load_scope()})
        elif self.path == "/api/reports":
            self._json(200, {"files": _reports()})
        else:
            self._json(404, {"error": "المسار غير موجود."})
    def do_POST(self):
        try:
            data = self._body()
            if self.path == "/api/server":
                global _PAUSED
                action = data.get("action")
                if action == "stop":
                    _PAUSED = True
                    self._json(200, {"paused": True, "message": "تم إيقاف الخدمة مؤقتاً. يمكنك إعادة تشغيلها من هذه الصفحة."})
                elif action == "start":
                    _PAUSED = False
                    self._json(200, {"paused": False, "message": "الخدمة تعمل الآن."})
                else:
                    raise ValueError("إجراء خادم غير صالح.")
            elif self.path == "/api/scope":
                from site_audit import normalize_host, load_scope, save_scope
                action = data.get("action")
                if data.get("authorized") is not True:
                    raise ValueError("أكد أنك تملك النطاق أو لديك تصريح صريح بفحصه.")
                host, _scheme = normalize_host(str(data.get("domain", "")))
                domains = set(load_scope())
                if action == "add":
                    domains.add(host)
                    save_scope(domains)
                    self._json(200, {"message": "تمت إضافة " + host + " إلى قائمة التصريح."})
                elif action == "remove":
                    domains.discard(host)
                    save_scope(domains)
                    self._json(200, {"message": "تم حذف " + host + " من قائمة التصريح."})
                else:
                    raise ValueError("إجراء نطاق غير صالح.")
            elif self.path == "/api/command":
                if _PAUSED:
                    raise ValueError("الخدمة متوقفة مؤقتاً. أعد تشغيلها من تبويب الرئيسية.")
                name = data.get("name")
                commands = {
                    "system": [["uname", "-a"], ["df", "-h"]],
                    "processes": [["ps"]],
                    "network": [["ip", "addr"]],
                    "packages": [["apk", "info"]],
                }
                if name == "apk_search":
                    query = str(data.get("query", "")).strip()
                    if not re.fullmatch(r"[A-Za-z0-9+_.-]{1,80}", query):
                        raise ValueError("اسم حزمة غير صالح.")
                    output = _run(["apk", "search", query])
                elif name in commands:
                    output = "\n\n".join(_run(cmd) for cmd in commands[name] if shutil.which(cmd[0]))
                else:
                    raise ValueError("الأمر غير موجود في قائمة الأوامر المسموحة.")
                self._json(200, {"output": output})
            elif self.path == "/api/install":
                if _PAUSED:
                    raise ValueError("الخدمة متوقفة مؤقتاً. أعد تشغيلها من تبويب الرئيسية.")
                package = str(data.get("package", "")).strip()
                if data.get("confirm") is not True:
                    raise ValueError("يتطلب التثبيت موافقة صريحة.")
                if not re.fullmatch(r"[A-Za-z0-9+_.-]{1,80}", package):
                    raise ValueError("اسم الحزمة غير صالح.")
                if not shutil.which("apk"):
                    raise ValueError("مدير apk غير متاح.")
                self._json(200, {"output": _run(["apk", "add", package], timeout=180)})
            elif self.path == "/api/audit":
                if _PAUSED:
                    raise ValueError("الخدمة متوقفة مؤقتاً. أعد تشغيلها من تبويب الرئيسية.")
                domain = str(data.get("domain", "")).strip()
                from site_audit import normalize_host, load_scope, create_job
                host, scheme = normalize_host(domain)
                if host not in set(load_scope()):
                    raise ValueError("النطاق غير موجود في قائمة التصريح. أضفه من ISH UI أولاً.")
                job_id = create_job(host, scheme)
                threading.Thread(target=_audit_worker, args=(job_id,), daemon=True).start()
                self._json(202, {"job_id": job_id, "domain": host})
            elif self.path == "/api/report":
                name = str(data.get("name", ""))
                if not re.fullmatch(r"audit_[A-Za-z0-9_.-]+\.json", name):
                    raise ValueError("اسم تقرير غير صالح.")
                path = REPORTS / name
                if not path.is_file() or path.stat().st_size > 1024 * 1024:
                    raise ValueError("التقرير غير موجود أو يتجاوز الحد.")
                self._json(200, {"report": json.loads(path.read_text(encoding="utf-8"))})
            else:
                self._json(404, {"error": "المسار غير موجود."})
        except Exception as exc:
            self._json(400, {"error": str(exc)[:300]})
    def do_HEAD(self):
        self.send_error(405)

def keep_alive():
    """Keep the local server process alive after the text dashboard exits."""
    if _SERVER is None:
        return
    print("\\nخادم الويب المحلي ما زال يعمل. افتح لوحة التحكم من المتصفح.")
    print("للإيقاف المؤقت أو الاستئناف استخدم أزرار التحكم داخل اللوحة.")
    print("للخروج الكامل من عملية iSH اضغط Ctrl+C في هذه الجلسة.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\\nتم إنهاء عملية خادم الويب.")


def start():
    global _SERVER
    if _SERVER is not None:
        return _SERVER.server_address[1], ""
    for port in PORTS:
        try:
            _SERVER = ThreadingHTTPServer((HOST, port), Handler)
            break
        except OSError:
            continue
    if _SERVER is None:
        raise RuntimeError("تعذر تشغيل الخادم على المنافذ 8765–8770.")
    _SERVER.daemon_threads = True
    thread = threading.Thread(target=_SERVER.serve_forever, name="ishui-web", daemon=True)
    thread.start()
    return _SERVER.server_address[1], ""
