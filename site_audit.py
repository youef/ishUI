#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Low-impact, resumable website audit for explicitly authorized single-host targets."""
import ipaddress
import json
import os
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
USER_AGENT = "ISH-UI-Authorized-Audit/1.0"
TIMEOUT = 7
DELAY = 0.8
MAX_BODY = 256 * 1024

# Fixed, low-impact existence checks only. No credential attempts or payloads.
PUBLIC_PATHS = (
    "/", "/robots.txt", "/sitemap.xml", "/sitemap_index.xml",
    "/.well-known/security.txt", "/login", "/signin", "/admin",
    "/administrator", "/wp-admin/", "/wp-login.php",
    "/dashboard", "/api/", "/health", "/status"
)
SECURITY_HEADERS = (
    "content-security-policy", "strict-transport-security",
    "x-content-type-options", "referrer-policy",
    "permissions-policy", "cross-origin-opener-policy",
    "cross-origin-resource-policy"
)

def db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
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

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def normalize_target(raw):
    raw = raw.strip()
    if "://" not in raw:
        raw = "https://" + raw
    p = urllib.parse.urlsplit(raw)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("أدخل نطاقاً أو رابط HTTP/HTTPS صالحاً.")
    if p.username or p.password or p.query or p.fragment:
        raise ValueError("لا تقبل بيانات دخول أو query أو fragment في عنوان الهدف.")
    host = p.hostname.rstrip(".").lower()
    if not host or len(host) > 253 or any(c.isspace() for c in host):
        raise ValueError("اسم المضيف غير صالح.")
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            raise ValueError("العناوين الخاصة أو المحلية غير مسموحة.")
    except ValueError as exc:
        if "غير مسموحة" in str(exc):
            raise
        if "." not in host or host in ("localhost",):
            raise ValueError("استخدم نطاقاً عاماً أو عنوان IP عاماً.")
        if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
               or not all(ch.isalnum() or ch == "-" for ch in label)
               for label in host.split(".")):
            raise ValueError("صيغة النطاق غير صالحة.")
    return host, p.scheme

def resolve_public(host):
    rows = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    addresses = sorted({row[4][0] for row in rows})
    if not addresses:
        raise RuntimeError("لم يتم العثور على عنوان IP.")
    for value in addresses:
        ip = ipaddress.ip_address(value)
        if not ip.is_global:
            raise RuntimeError("رفض الفحص: DNS يشير إلى عنوان غير عام أو داخلي.")
    return addresses

class SameHostRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, host):
        self.host = host
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        p = urllib.parse.urlsplit(newurl)
        if p.hostname != self.host or p.scheme not in ("http", "https"):
            raise urllib.error.HTTPError(newurl, code, "Redirect خارج النطاق مرفوض", headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def request(host, scheme, path="/", method="GET"):
    url = scheme + "://" + host + path
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ssl.create_default_context()),
        SameHostRedirect(host)
    )
    req = urllib.request.Request(url, method=method, headers={
        "User-Agent": USER_AGENT, "Accept": "*/*",
        "Range": "bytes=0-65535", "Connection": "close"
    })
    try:
        response = opener.open(req, timeout=TIMEOUT)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        headers = {k.lower(): v for k, v in response.headers.items()}
        body = b""
        if method != "HEAD":
            body = response.read(MAX_BODY)
        return {"status": getattr(response, "status", response.code),
                "url": response.geturl(), "headers": headers, "body": body}

def tls_info(host):
    context = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=TIMEOUT) as raw:
        with context.wrap_socket(raw, server_hostname=host) as conn:
            cert = conn.getpeercert()
            return {
                "protocol": conn.version(),
                "cipher": conn.cipher()[0] if conn.cipher() else None,
                "issuer": cert.get("issuer"),
                "subject": cert.get("subject"),
                "valid_from": cert.get("notBefore"),
                "valid_until": cert.get("notAfter"),
                "san": [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"][:40]
            }

def cookie_audit(header):
    findings = []
    for item in header.split(",") if header else []:
        low = item.lower()
        if "set-cookie" in low:
            findings.append(item[:300])
    return findings

def save(con, job_id, stage, status=None, path_index=None, key=None, value=None):
    row = con.execute("SELECT results FROM jobs WHERE id=?", (job_id,)).fetchone()
    data = json.loads(row["results"] or "{}")
    if key is not None:
        data[key] = value
    fields = ["stage=?", "updated_at=?", "results=?"]
    args = [stage, now(), json.dumps(data, ensure_ascii=False)]
    if status:
        fields.append("status=?"); args.append(status)
    if path_index is not None:
        fields.append("path_index=?"); args.append(path_index)
    args.append(job_id)
    con.execute("UPDATE jobs SET " + ",".join(fields) + " WHERE id=?", args)
    con.commit()

def audit(job_id):
    con = db()
    row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        print("المهمة غير موجودة.")
        return
    host, scheme = row["host"], row["scheme"]
    data = json.loads(row["results"] or "{}")
    try:
        if row["stage"] in ("queued", "dns"):
            print("[1/5] DNS وIP الظاهر...")
            data["addresses"] = resolve_public(host)
            save(con, job_id, "tls", key="addresses", value=data["addresses"])
        row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        data = json.loads(row["results"] or "{}")
        if row["stage"] == "tls":
            print("[2/5] شهادة TLS...")
            try: data["tls"] = tls_info(host)
            except Exception as exc: data["tls_error"] = str(exc)[:240]
            save(con, job_id, "http", key="tls", value=data.get("tls", {"error":data.get("tls_error")}))
        row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        data = json.loads(row["results"] or "{}")
        if row["stage"] == "http":
            print("[3/5] ترويسات HTTP وملفات التعريف...")
            try:
                result = request(host, scheme, "/", "GET")
                h = result["headers"]
                data["http"] = {"status":result["status"], "final_url":result["url"],
                                "server_header":h.get("server"), "powered_by":h.get("x-powered-by"),
                                "security_headers":{k:h.get(k) for k in SECURITY_HEADERS},
                                "cookies":h.get("set-cookie"), "content_type":h.get("content-type")}
                save(con, job_id, "paths", key="http", value=data["http"])
            except Exception as exc:
                data["http_error"] = str(exc)[:240]
                save(con, job_id, "paths", key="http_error", value=data["http_error"])
        row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row["stage"] == "paths":
            print("[4/5] التحقق المحدود من مسارات عامة وصفحات دخول...")
            idx = row["path_index"]
            found = data.get("paths", [])
            for i in range(idx, len(PUBLIC_PATHS)):
                path = PUBLIC_PATHS[i]
                try:
                    result = request(host, scheme, path, "HEAD")
                    found.append({"path":path, "status":result["status"]})
                except Exception as exc:
                    found.append({"path":path, "error":str(exc)[:120]})
                save(con, job_id, "paths", path_index=i+1, key="paths", value=found)
                print(" ", path, "=>", found[-1].get("status", "تعذر"))
                time.sleep(DELAY)
            save(con, job_id, "review", key="paths", value=found)
        row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row["stage"] == "review":
            print("[5/5] تحليل مؤشرات إعدادات غير تدميري...")
            http = data.get("http", {})
            headers = http.get("security_headers", {})
            missing = [k for k,v in headers.items() if not v]
            cookies = (http.get("cookies") or "").lower()
            data["review"] = {
                "missing_security_headers": missing,
                "cookie_flags": {
                    "secure": "secure" in cookies,
                    "httponly": "httponly" in cookies,
                    "samesite": "samesite" in cookies
                },
                "admin_login_paths_are_existence_only": True,
                "injection_tests": "لم يتم إرسال payloads؛ هذا الفحص لا يثبت أو ينفي SQL injection."
            }
            save(con, job_id, "complete", status="complete", key="review", value=data["review"])
        print("\nاكتمل الفحص أو حُفظت آخر مرحلة.")
        print_report(job_id)
    except KeyboardInterrupt:
        con.execute("UPDATE jobs SET status='paused', updated_at=? WHERE id=?", (now(), job_id))
        con.commit()
        print("\nتم إيقاف المهمة وحفظ نقطة الاستئناف.")
    except Exception as exc:
        con.execute("UPDATE jobs SET status='paused', updated_at=? WHERE id=?", (now(), job_id))
        con.commit()
        print("توقفت المهمة مع حفظ التقدم:", str(exc)[:240])
    finally:
        con.close()

def print_report(job_id):
    con = db()
    row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if row:
        print("\nالمهمة:", row["id"], "|", row["host"], "|", row["status"], "| المرحلة:", row["stage"])
        print(json.dumps(json.loads(row["results"] or "{}"), ensure_ascii=False, indent=2)[:14000])
    con.close()

def run():
    while True:
        print("\n=== ISH UI | محرك فحص المواقع المصرح بها ===")
        print("1 إنشاء فحص جديد")
        print("2 استئناف/عرض المهام المحفوظة")
        print("0 رجوع")
        choice = input("اختيارك: ").strip()
        if choice == "0": return
        if choice == "1":
            try:
                host, scheme = normalize_target(input("النطاق المصرح به (دون wildcard): "))
                print("تنبيه: افحص المضيف المحدد فقط. لا يكشف هذا الفحص عنوان origin خلف CDN.")
                if input("أؤكد أن لدي ملكية أو تصريحاً مكتوباً لهذا المضيف (اكتب YES): ").strip() != "YES":
                    print("تم الإلغاء؛ لم تُنشأ مهمة.")
                    continue
                con = db()
                cur = con.execute("INSERT INTO jobs(host,scheme,status,stage,created_at,updated_at) VALUES(?,?,?,?,?,?)",
                                  (host,scheme,"queued","queued",now(),now()))
                job_id = cur.lastrowid
                con.commit(); con.close()
                audit(job_id)
            except Exception as exc:
                print("تعذر إنشاء المهمة:", str(exc))
        elif choice == "2":
            con = db()
            rows = con.execute("SELECT id,host,status,stage,updated_at FROM jobs ORDER BY id DESC LIMIT 20").fetchall()
            for r in rows:
                print("#{0} {1} | {2} | {3} | {4}".format(r["id"],r["host"],r["status"],r["stage"],r["updated_at"]))
            con.close()
            raw = input("رقم المهمة للاستئناف/عرض التقرير (Enter للرجوع): ").strip()
            if raw.isdigit():
                con = db()
                exists = con.execute("SELECT 1 FROM jobs WHERE id=?", (int(raw),)).fetchone()
                con.close()
                if exists:
                    action = input("اكتب R للاستئناف أو V للتقرير: ").strip().upper()
                    if action == "R": audit(int(raw))
                    elif action == "V": print_report(int(raw))
        else:
            print("اختيار غير صحيح.")

if __name__ == "__main__":
    run()
