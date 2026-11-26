#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ISH UI Security Lab — standard-library tools for iSH / Alpine."""
import hashlib
import ipaddress
import os
import re
import socket
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

def ask(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        return ""

def pause():
    try:
        input("\nاضغط Enter للمتابعة...")
    except (EOFError, KeyboardInterrupt):
        pass

def title(name):
    print("\n" + "=" * 42)
    print(" ISH UI | مختبر الأمن السيبراني")
    print(" " + name)
    print("=" * 42)

def host_value(raw):
    raw = raw.strip()
    if "://" in raw:
        parsed = urllib.parse.urlsplit(raw)
        host = parsed.hostname
    else:
        host = raw.split("/", 1)[0].split(":", 1)[0]
    if not host or len(host) > 253 or any(c.isspace() for c in host):
        raise ValueError("اسم نطاق أو عنوان غير صالح.")
    return host

def dns_lookup():
    title("استعلام DNS")
    host = host_value(ask("النطاق أو IP: "))
    try:
        rows = socket.getaddrinfo(host, None)
        found = sorted(set(row[4][0] for row in rows))
        for address in found:
            print(" ", address)
        if not found:
            print("لم يتم العثور على عناوين.")
    except Exception as exc:
        print("فشل DNS:", exc)
    pause()

def tls_check():
    title("فحص شهادة TLS")
    host = host_value(ask("اسم النطاق: "))
    try:
        context = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=7) as raw:
            with context.wrap_socket(raw, server_hostname=host) as conn:
                cert = conn.getpeercert()
                print("TLS:", conn.version())
                print("Cipher:", conn.cipher()[0] if conn.cipher() else "غير متاح")
                print("Subject:", cert.get("subject"))
                print("Issuer:", cert.get("issuer"))
                print("Valid from:", cert.get("notBefore"))
                print("Valid until:", cert.get("notAfter"))
                print("SAN:", cert.get("subjectAltName", ())[:8])
    except Exception as exc:
        print("تعذر التحقق من TLS:", exc)
    pause()

def http_headers():
    title("تحليل ترويسات HTTP")
    raw = ask("رابط الموقع (HTTPS مفضل): ")
    if "://" not in raw:
        raw = "https://" + raw
    try:
        p = urllib.parse.urlsplit(raw)
        if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
            raise ValueError("رابط غير صالح.")
        req = urllib.request.Request(raw, method="HEAD", headers={"User-Agent":"ISH-UI-SecurityLab/1.0"})
        try:
            response = urllib.request.urlopen(req, timeout=8)
        except Exception as exc:
            # Some servers reject HEAD; use one small GET as fallback.
            if getattr(exc, "code", None) is None:
                raise
            req = urllib.request.Request(raw, headers={"User-Agent":"ISH-UI-SecurityLab/1.0"})
            response = urllib.request.urlopen(req, timeout=8)
        with response:
            print("HTTP:", response.status, response.geturl())
            for key, value in response.headers.items():
                print(key + ":", value)
            print("\nمراجعة سريعة:")
            for key in ("Content-Security-Policy","Strict-Transport-Security",
                        "X-Content-Type-Options","Referrer-Policy","Permissions-Policy"):
                print(("✓ " if response.headers.get(key) else "○ ") + key)
    except Exception as exc:
        print("فشل الطلب:", exc)
    pause()

def port_check():
    title("فحص منافذ TCP محددة")
    print("للنطاقات والأجهزة التي تملكها أو لديك تصريح بفحصها فقط.")
    host = host_value(ask("اسم النطاق أو IP: "))
    raw = ask("المنافذ (مثال 22,80,443): ")
    try:
        ports = []
        for part in raw.split(","):
            if not part.strip():
                continue
            port = int(part.strip())
            if not 1 <= port <= 65535:
                raise ValueError("المنفذ خارج النطاق.")
            if port not in ports:
                ports.append(port)
        if not ports or len(ports) > 8:
            raise ValueError("أدخل من 1 إلى 8 منافذ فقط.")
        print("فحص اتصال TCP فقط، بمهلة قصيرة:")
        for port in ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.5)
            try:
                result = sock.connect_ex((host, port))
                print(" ", str(port).ljust(6), "مفتوح" if result == 0 else "غير متاح/مغلق")
            except OSError as exc:
                print(" ", port, "تعذر الفحص:", str(exc)[:90])
            finally:
                sock.close()
    except Exception as exc:
        print("إدخال غير صالح:", exc)
    pause()

def url_inspector():
    title("تحليل رابط دون فتحه")
    raw = ask("ألصق الرابط: ")
    try:
        p = urllib.parse.urlsplit(raw)
        if p.scheme not in ("http", "https") or not p.hostname:
            raise ValueError("يجب أن يكون رابط HTTP/HTTPS.")
        print("Scheme:", p.scheme)
        print("Host:", p.hostname)
        print("Port:", p.port or ("443" if p.scheme == "https" else "80"))
        print("Path:", p.path or "/")
        print("Query keys:", [x[0] for x in urllib.parse.parse_qsl(p.query)][:30])
        print("Contains username/password:", bool(p.username or p.password))
        print("Contains non-ASCII hostname:", not p.hostname.isascii())
        print("تنبيه: هذا تحليل بنيوي فقط ولا يثبت أن الرابط آمن.")
    except Exception as exc:
        print("رابط غير صالح:", exc)
    pause()

def hash_file():
    title("بصمة ملف SHA-256")
    path = Path(ask("مسار الملف: ")).expanduser()
    try:
        if not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("يجب اختيار ملف موجود لا يتجاوز 64MB.")
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        print("SHA-256:", digest.hexdigest())
    except Exception as exc:
        print("تعذر حساب البصمة:", exc)
    pause()

def password_audit():
    title("تقييم كلمة مرور محلياً")
    value = ask("أدخل كلمة المرور (لا تُرسل إلى أي جهة): ")
    if not value:
        print("لم يتم إدخال قيمة.")
        pause()
        return
    score = sum((len(value) >= n) for n in (8, 12, 16, 20))
    checks = [
        ("أحرف صغيرة", bool(re.search(r"[a-z]", value))),
        ("أحرف كبيرة", bool(re.search(r"[A-Z]", value))),
        ("أرقام", bool(re.search(r"\d", value))),
        ("رموز", bool(re.search(r"[^A-Za-z0-9]", value))),
    ]
    score += sum(ok for _, ok in checks)
    print("الطول:", len(value))
    for label, ok in checks:
        print(("✓ " if ok else "○ ") + label)
    print("التقييم التقريبي:", "قوي" if score >= 7 and len(value) >= 12 else "متوسط" if score >= 5 else "ضعيف")
    print("لا تحفظ هذه القيمة في سجل أو ملف.")
    pause()

def run():
    actions = {
        "1": dns_lookup,
        "2": tls_check,
        "3": http_headers,
        "4": port_check,
        "5": url_inspector,
        "6": hash_file,
        "7": password_audit,
    }
    while True:
        title("الأدوات")
        labels = [
            "1  DNS Lookup",
            "2  TLS / Certificate Checker",
            "3  HTTP Security Headers",
            "4  TCP Port Check (حتى 8 منافذ)",
            "5  URL Structure Analyzer",
            "6  SHA-256 File Hash",
            "7  Password Strength Auditor",
            "0  رجوع",
        ]
        for label in labels:
            print(" ", label)
        choice = ask("\nاختيارك: ")
        if choice == "0":
            return
        action = actions.get(choice)
        if action:
            action()
        else:
            print("اختيار غير صحيح.")
