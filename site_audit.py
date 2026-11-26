#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Resumable, low-impact batch audit for explicitly authorized public hosts."""
import ipaddress
import json
import os
import re
import socket
import sqlite3
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path.home() / ".config" / "ishui"
DB_PATH = DATA_DIR / "security_jobs.sqlite3"
SCOPE_PATH = DATA_DIR / "authorized_scope.json"
REPORT_DIR = DATA_DIR / "reports"
USER_AGENT = "ISH-UI-Authorized-Audit/2.0"
TIMEOUT = 7
DELAY = 0.7
MAX_BODY = 65536
MAX_CANDIDATES = 100
PUBLIC_PATHS = (
    "/", "/robots.txt", "/sitemap.xml", "/sitemap_index.xml",
    "/.well-known/security.txt", "/login", "/signin", "/admin",
    "/administrator", "/wp-admin/", "/wp-login.php", "/dashboard",
    "/api/", "/health", "/status"
)
SECURITY_HEADERS = (
    "content-security-policy", "strict-transport-security",
    "x-content-type-options", "referrer-policy", "permissions-policy",
    "cross-origin-opener-policy", "cross-origin-resource-policy"
)

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, host TEXT NOT NULL,
        scheme TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        results TEXT NOT NULL DEFAULT '{}', path_index INTEGER NOT NULL DEFAULT 0
    )""")
    con.commit()
    return con

def normalize_host(raw):
    value = raw.strip()
    if "://" in value:
        p = urllib.parse.urlsplit(value)
        if p.scheme not in ("http", "https") or p.username or p.password or p.query or p.fragment:
            raise ValueError("رابط غير صالح.")
        if p.path not in ("", "/"):
            raise ValueError("أدخل اسم النطاق فقط دون مسار.")
        if p.port and p.port != (443 if p.scheme == "https" else 80):
            raise ValueError("المنافذ المخصصة غير مدعومة في الفحص الدفعي.")
        host = p.hostname or ""
        scheme = p.scheme
    else:
        if any(x in value for x in ("/", "?", "#", "@")):
            raise ValueError("أدخل اسم المضيف فقط.")
        host, scheme = value, "https"
    host = host.rstrip(".").lower()
    if not host or len(host) > 253 or any(c.isspace() for c in host):
        raise ValueError("اسم المضيف غير صالح.")
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            raise ValueError("العناوين الخاصة والمحلية غير مسموحة.")
    except ValueError as exc:
        if "غير مسموحة" in str(exc):
            raise
        try:
            host = host.encode("idna").decode("ascii")
        except UnicodeError:
            raise ValueError("اسم النطاق غير صالح.")
        labels = host.split(".")
        if len(labels) < 2 or any(
            not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
            or not re.fullmatch(r"[a-z0-9-]+", label) for label in labels
        ):
            raise ValueError("استخدم نطاقاً عاماً صالحاً.")
    return host, scheme

def resolve_public(host):
    rows = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    addresses = sorted({row[4][0].split("%", 1)[0] for row in rows})
    if not addresses:
        raise RuntimeError("لا توجد عناوين DNS.")
    for value in addresses:
        if not ipaddress.ip_address(value).is_global:
            raise RuntimeError("رفض النطاق: DNS يتضمن عنواناً غير عام.")
    return addresses

def load_scope():
    try:
        data = json.loads(SCOPE_PATH.read_text(encoding="utf-8"))
        return sorted(set(data.get("domains", [])))
    except Exception:
        return []

def save_scope(domains):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SCOPE_PATH.write_text(
        json.dumps({"domains": sorted(set(domains)), "updated_at": now()},
                   ensure_ascii=False, indent=2), encoding="utf-8"
    )

def edit_scope():
    current = load_scope()
    print("\nقائمة النطاقات المصرح بفحصها (نطاق في كل سطر، أو مفصولة بفواصل).")
    print("المحفوظ حالياً:", ", ".join(current) if current else "لا توجد قائمة.")
    raw = input("أدخل القائمة الجديدة؛ اتركها فارغة للإبقاء على الحالية: ").strip()
    if not raw:
        return current
    domains = []
    for item in re.split(r"[,;\s]+", raw):
        if item:
            host, _ = normalize_host(item)
            if host not in domains:
                domains.append(host)
    if not domains:
        raise ValueError("القائمة فارغة.")
    save_scope(domains)
    print("تم حفظ", len(domains), "نطاقاً في قائمة النطاقات المصرح بها.")
    return domains

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, host, port):
        self.host, self.port = host, port
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        p = urllib.parse.urlsplit(newurl)
        target_port = p.port or (443 if p.scheme == "https" else 80)
        if p.hostname != self.host or p.scheme not in ("http", "https") or target_port not in (80, 443):
            raise urllib.error.HTTPError(newurl, code, "تم رفض تحويل خارج المضيف/المنفذ المحدد", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def request(host, scheme, path="/", method="HEAD"):
    # Revalidate DNS before every request and disable environment proxy settings.
    resolve_public(host)
    port = 443 if scheme == "https" else 80
    url = scheme + "://" + ( "[" + host + "]" if ":" in host else host) + path
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        SafeRedirect(host, port)
    )
    req = urllib.request.Request(url, method=method, headers={
        "User-Agent": USER_AGENT, "Accept": "*/*", "Connection": "close"
    })
    try:
        response = opener.open(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        headers = {k.lower(): v for k, v in response.headers.items()}
        body = response.read(MAX_BODY) if method == "GET" else b""
        return {"status": getattr(response, "status", response.code),
                "url": response.geturl(), "headers": headers, "body": body}

def tls_info(host):
    resolve_public(host)
    context = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=TIMEOUT) as raw:
        with context.wrap_socket(raw, server_hostname=host) as conn:
            cert = conn.getpeercert()
            return {
                "protocol": conn.version(),
                "cipher": conn.cipher()[0] if conn.cipher() else None,
                "issuer": cert.get("issuer"), "subject": cert.get("subject"),
                "valid_from": cert.get("notBefore"), "valid_until": cert.get("notAfter"),
                "san": [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"][:60]
            }

def discover_reverse_ip(address):
    """Passive reverse-IP lookup; the queried public IP is sent to HackerTarget."""
    endpoint = "https://api.hackertarget.com/reverseiplookup/?q=" + urllib.parse.quote(address)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(endpoint, headers={"User-Agent": USER_AGENT})
    with opener.open(req, timeout=8) as response:
        raw = response.read(128 * 1024).decode("utf-8", errors="replace")
    if "error" in raw.lower()[:100] or "api count exceeded" in raw.lower():
        return []
    found = []
    for line in raw.splitlines():
        candidate = line.strip().split(",")[0].lower().rstrip(".")
        if not candidate or candidate.startswith("error") or "/" in candidate:
            continue
        try:
            host, _ = normalize_host(candidate)
            if host not in found:
                found.append(host)
        except Exception:
            continue
        if len(found) >= MAX_CANDIDATES:
            break
    return found

def discover_candidates(host, addresses, use_provider):
    candidates = {host}
    sources = {host: ["النطاق الأساسي"]}
    try:
        cert = tls_info(host)
        for name in cert.get("san", []):
            if "*" not in name:
                try:
                    candidate, _ = normalize_host(name)
                    candidates.add(candidate)
                    sources.setdefault(candidate, []).append("شهادة TLS (SAN)")
                except Exception:
                    pass
    except Exception:
        pass
    for address in addresses:
        try:
            ptr = socket.gethostbyaddr(address)[0].rstrip(".").lower()
            candidate, _ = normalize_host(ptr)
            candidates.add(candidate)
            sources.setdefault(candidate, []).append("Reverse DNS / PTR")
        except Exception:
            pass
        if use_provider:
            try:
                for candidate in discover_reverse_ip(address):
                    candidates.add(candidate)
                    sources.setdefault(candidate, []).append("Reverse-IP lookup")
            except Exception as exc:
                print("تعذر مصدر Reverse-IP:", str(exc)[:100])
    return sorted(candidates), sources

def save_job(con, job_id, stage, status=None, path_index=None, key=None, value=None):
    row = con.execute("SELECT results FROM jobs WHERE id=?", (job_id,)).fetchone()
    data = json.loads(row["results"] or "{}")
    if key is not None:
        data[key] = value
    fields, args = ["stage=?", "updated_at=?", "results=?"], [stage, now(), json.dumps(data, ensure_ascii=False)]
    if status:
        fields.append("status=?"); args.append(status)
    if path_index is not None:
        fields.append("path_index=?"); args.append(path_index)
    args.append(job_id)
    con.execute("UPDATE jobs SET " + ",".join(fields) + " WHERE id=?", args)
    con.commit()

def export_report(row, data):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / ("audit_" + str(row["id"]) + "_" + row["host"].replace(":", "_") + ".json")
    path.write_text(json.dumps({
        "id": row["id"], "host": row["host"], "status": row["status"],
        "created_at": row["created_at"], "updated_at": now(), "results": data
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)

def audit(job_id):
    con = db()
    try:
        row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            print("المهمة غير موجودة."); return
        host, scheme = row["host"], row["scheme"]
        con.execute("UPDATE jobs SET status='running', updated_at=? WHERE id=?", (now(), job_id))
        con.commit()
        data = json.loads(row["results"] or "{}")
        if row["stage"] in ("queued", "dns"):
            print("[1/5] DNS وIP...")
            data["addresses"] = resolve_public(host)
            save_job(con, job_id, "tls", key="addresses", value=data["addresses"])
        row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        data = json.loads(row["results"] or "{}")
        if row["stage"] == "tls":
            print("[2/5] TLS...")
            try: data["tls"] = tls_info(host)
            except Exception as exc: data["tls_error"] = str(exc)[:200]
            save_job(con, job_id, "http", key="tls", value=data.get("tls", {"error":data.get("tls_error")}))
        row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        data = json.loads(row["results"] or "{}")
        if row["stage"] == "http":
            print("[3/5] HTTP headers and cookies...")
            try:
                result = request(host, scheme, "/", "GET")
                h = result["headers"]
                data["http"] = {
                    "status": result["status"], "final_url": result["url"],
                    "server": h.get("server"), "powered_by": h.get("x-powered-by"),
                    "content_type": h.get("content-type"),
                    "security_headers": {k:h.get(k) for k in SECURITY_HEADERS},
                    "set_cookie_present": bool(h.get("set-cookie"))
                }
                save_job(con, job_id, "paths", key="http", value=data["http"])
            except Exception as exc:
                data["http_error"] = str(exc)[:200]
                save_job(con, job_id, "paths", key="http_error", value=data["http_error"])
        row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        data = json.loads(row["results"] or "{}")
        if row["stage"] == "paths":
            print("[4/5] Existence-only checks for common public paths...")
            found, start = data.get("paths", []), row["path_index"]
            for index in range(start, len(PUBLIC_PATHS)):
                path = PUBLIC_PATHS[index]
                try:
                    result = request(host, scheme, path, "HEAD")
                    found.append({"path":path, "status":result["status"]})
                except Exception as exc:
                    found.append({"path":path, "error":str(exc)[:100]})
                save_job(con, job_id, "paths", path_index=index+1, key="paths", value=found)
                print(" ", path, "=>", found[-1].get("status", "تعذر"))
                time.sleep(DELAY)
            save_job(con, job_id, "review", key="paths", value=found)
        row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        data = json.loads(row["results"] or "{}")
        if row["stage"] == "review":
            headers = data.get("http", {}).get("security_headers", {})
            data["review"] = {
                "missing_security_headers": [k for k,v in headers.items() if not v],
                "login_admin_paths_are_existence_only": True,
                "injection_tests": "لم يتم إرسال payloads؛ لا يمكن استنتاج وجود/غياب SQLi من هذا الفحص."
            }
            save_job(con, job_id, "complete", status="complete", key="review", value=data["review"])
        row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        data = json.loads(row["results"] or "{}")
        path = export_report(row, data)
        print("اكتمل:", host, "| تقرير JSON:", path)
        print(json.dumps(data, ensure_ascii=False, indent=2)[:5000])
    except KeyboardInterrupt:
        con.execute("UPDATE jobs SET status='paused', updated_at=? WHERE id=?", (now(), job_id))
        con.commit()
        print("\nتم الإيقاف وحفظ نقطة الاستئناف.")
    except Exception as exc:
        con.execute("UPDATE jobs SET status='paused', updated_at=? WHERE id=?", (now(), job_id))
        con.commit()
        print("توقفت المهمة مع حفظ التقدم:", str(exc)[:200])
    finally:
        con.close()

def create_job(host, scheme):
    con = db()
    cur = con.execute(
        "INSERT INTO jobs(host,scheme,status,stage,created_at,updated_at) VALUES(?,?,?,?,?,?)",
        (host, scheme, "queued", "queued", now(), now())
    )
    job_id = cur.lastrowid
    con.commit(); con.close()
    return job_id

def batch_scan(primary, primary_scheme, scope, use_provider):
    try:
        addresses = resolve_public(primary)
    except Exception as exc:
        print("تعذر DNS للنطاق الأساسي:", str(exc)); return
    print("عناوين IP الظاهرة:", ", ".join(addresses))
    candidates, sources = discover_candidates(primary, addresses, use_provider)
    allowed = set(scope)
    selected = [host for host in candidates if host in allowed or host == primary]
    print("\nالنطاقات المرشحة:", len(candidates))
    for host in candidates:
        print(" ", host, "|", "، ".join(sources.get(host, [])),
              "|", "مصرح ضمن القائمة" if host in allowed or host == primary else "خارج النطاق — لن يُفحص")
    if len(selected) > 1:
        print("\nسيتم فحص", len(selected), "نطاقات مصرح بها بالتتابع.")
    else:
        print("\nسيتم فحص النطاق الأساسي فقط. أضف النطاقات الأخرى لقائمة التصريح إذا كانت ضمن ملكيتك/تصريحك.")
    for host in selected:
        try:
            scheme = primary_scheme if host == primary else "https"
            # Require fresh public DNS validation for every selected hostname.
            resolve_public(host)
            job_id = create_job(host, scheme)
            print("\n===== بدء فحص", host, "| المهمة #" + str(job_id), "=====")
            audit(job_id)
        except Exception as exc:
            print("تجاوز", host, ":", str(exc)[:140])

def resume_jobs():
    con = db()
    rows = con.execute("SELECT id,host,status,stage,updated_at FROM jobs ORDER BY id DESC LIMIT 25").fetchall()
    for r in rows:
        print("#{0} {1} | {2} | {3} | {4}".format(r["id"],r["host"],r["status"],r["stage"],r["updated_at"]))
    con.close()
    raw = input("رقم المهمة للاستئناف (Enter للرجوع): ").strip()
    if raw.isdigit():
        audit(int(raw))

def run():
    while True:
        print("\n=== ISH UI | الفحص الذكي الدفعي للمواقع ===")
        print("1 فحص تلقائي شامل لنطاق")
        print("2 إدارة قائمة النطاقات المصرح بها")
        print("3 استئناف مهمة محفوظة")
        print("0 رجوع")
        choice = input("اختيارك: ").strip()
        if choice == "0": return
        if choice == "2":
            try: edit_scope()
            except Exception as exc: print("تعذر تحديث القائمة:", exc)
            continue
        if choice == "3":
            resume_jobs(); continue
        if choice != "1":
            print("اختيار غير صحيح."); continue
        try:
            primary, primary_scheme = normalize_host(input("أدخل النطاق الأساسي: "))
            scope = load_scope()
            if not scope:
                print("أول تشغيل: أدخل جميع النطاقات التي تملكها أو لديك تصريح مكتوب لفحصها.")
                scope = edit_scope()
            if primary not in scope:
                print("سيُضاف النطاق الأساسي إلى نطاق هذه المهمة فقط بعد تأكيد التصريح.")
            print("\nتنبيه خصوصية: يمكن استخدام HackerTarget للبحث العكسي عن النطاقات على IP؛")
            print("سيُرسل عنوان IP العام إلى مزود خارجي. اكتب YES للموافقة أو Enter للتخطي.")
            use_provider = input("السماح بالبحث العكسي الخارجي؟ ").strip() == "YES"
            print("\nتأكيد: أفحص فقط النطاقات التي أملكها أو لدي تصريح صريح بفحصها.")
            if input("اكتب YES للبدء: ").strip() != "YES":
                print("تم الإلغاء."); continue
            if primary not in scope:
                scope.append(primary)
                save_scope(scope)
            batch_scan(primary, primary_scheme, scope, use_provider)
        except KeyboardInterrupt:
            print("\nتم الإلغاء.")
        except Exception as exc:
            print("تعذر بدء الفحص:", str(exc)[:200])

if __name__ == "__main__":
    run()
