#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ISH UI — يوسف الحازمي
A richer terminal control center for iSH / Alpine Linux.
Python standard library only.
"""
import os
import sys
import shutil
import platform
import subprocess
import textwrap
import json
import socket
import re
import tarfile
import zipfile
from pathlib import Path
from datetime import datetime

APP_NAME = "ISH UI"
VERSION = "3.0.0"
AUTHOR = "يوسف الحازمي"
REPO = "https://github.com/youef/ishUI"
CONFIG_DIR = Path.home() / ".config" / "ishui"
CONFIG_FILE = CONFIG_DIR / "config.json"
HISTORY_FILE = CONFIG_DIR / "history.txt"

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[96m"
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"

def load_config():
    defaults = {"colors": True, "show_clock": True}
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                defaults.update({k: v for k, v in data.items() if k in defaults})
    except Exception:
        pass
    return defaults

CONFIG = load_config()

def save_config():
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        print("تعذر حفظ الإعدادات: " + str(exc))

def color(value, shade=WHITE):
    if not CONFIG.get("colors", True):
        return str(value)
    return shade + str(value) + RESET

def clear():
    os.system("clear" if os.name != "nt" else "cls")

def width():
    return max(44, min(shutil.get_terminal_size((80, 24)).columns, 100))

def line(char="─"):
    print(color(char * width(), BLUE))

def pause():
    try:
        input(color("\nاضغط Enter للمتابعة...", DIM))
    except (EOFError, KeyboardInterrupt):
        pass

def ask(prompt):
    try:
        return input(color(prompt, CYAN)).strip()
    except (EOFError, KeyboardInterrupt):
        return ""

def confirm(prompt):
    return ask(prompt + " (y/N): ").lower() == "y"

def run(args, timeout=25):
    try:
        return subprocess.run(args, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=timeout)
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        print(color("انتهت مهلة تنفيذ العملية.", RED))
        return None
    except Exception as exc:
        print(color("خطأ: " + str(exc), RED))
        return None

def show_result(result, empty="لا توجد بيانات لعرضها."):
    if result is None:
        print(color("الأداة المطلوبة غير مثبتة أو غير متاحة.", RED))
    elif result.stdout.strip():
        print(result.stdout.rstrip())
    else:
        print(color(empty, DIM))

def disk_usage():
    try:
        return shutil.disk_usage(str(Path.home()))
    except Exception:
        return None

def header(section="مركز التحكم"):
    clear()
    w = width()
    print(color("╔" + "═" * (w - 2) + "╗", CYAN))
    print(color("║", CYAN) + color(" ISH UI  •  iSH CONTROL CENTER ".center(w - 2), BOLD + WHITE) + color("║", CYAN))
    sub = "يوسف الحازمي  |  v" + VERSION + "  |  " + section
    print(color("║", CYAN) + color(sub.center(w - 2), MAGENTA) + color("║", CYAN))
    print(color("╚" + "═" * (w - 2) + "╝", CYAN))
    if CONFIG.get("show_clock", True):
        print(color("  " + datetime.now().strftime("%Y-%m-%d  %H:%M:%S"), DIM))
    line()

def item(number, title, detail=""):
    print(color("  [" + str(number) + "] ", BOLD + CYAN) + color(title, WHITE) +
          (color("  ·  " + detail, DIM) if detail else ""))

def storage_summary():
    usage = disk_usage()
    if not usage or not usage.total:
        return "غير متاح", 0
    used = usage.used / usage.total * 100
    return f"{usage.used // (1024**2)} / {usage.total // (1024**2)} MB", used

def dashboard():
    header()
    storage, percent = storage_summary()
    print(color("  نظرة عامة", BOLD + GREEN))
    print("  النظام       :", platform.system(), platform.release())
    print("  المعمارية    :", platform.machine())
    print("  Python       :", platform.python_version())
    print("  المستخدم     :", os.environ.get("USER", "unknown"))
    print("  مساحة التخزين:", storage)
    bar_len = 25
    filled = int(bar_len * percent / 100)
    bar = "█" * filled + "░" * (bar_len - filled)
    print("  [" + color(bar, GREEN if percent < 80 else YELLOW) + f"] {percent:.1f}%")
    print()
    line()
    print(color("  الأدوات", BOLD + WHITE))
    item(1, "مدير الحزم", "تثبيت / حذف / بحث / تحديث")
    item(2, "مستكشف الملفات", "إنشاء وقراءة ونسخ ونقل وحذف")
    item(3, "طرفية الأوامر", "سجل أوامر ودعم أوامر shell")
    item(4, "مراقبة النظام", "العمليات والذاكرة والتخزين")
    item(5, "أدوات الشبكة", "عنوان IP وDNS وPing")
    item(6, "معلومات النظام", "تفاصيل بيئة التشغيل")
    item(7, "تحديث ISH UI", "التحديث من GitHub")
    item(8, "الإعدادات", "الألوان والساعة")
    item(9, "محرر النصوص", "إنشاء وتحرير ملفات نصية")
    item(10, "مدير العمليات", "عرض العمليات وإيقافها")
    item(11, "مدير الخدمات", "خدمات OpenRC في Alpine")
    item(12, "النسخ الاحتياطي", "إنشاء واستعادة نسخة مضغوطة")
    item(13, "مدير الأرشيف", "ZIP و TAR")
    item(14, "فحص النظام", "تشخيص الأدوات والبيئة")
    item(0, "خروج")
    line()

def package_manager():
    while True:
        header("مدير الحزم")
        item(1, "تحديث فهارس المستودعات", "apk update")
        item(2, "ترقية الحزم", "apk upgrade")
        item(3, "تثبيت حزمة", "apk add")
        item(4, "حذف حزمة", "apk del")
        item(5, "البحث عن حزمة", "apk search")
        item(6, "الحزم المثبتة", "apk info")
        item(0, "رجوع")
        line()
        choice = ask("  اختيارك: ")
        if choice == "0":
            return
        if not shutil.which("apk"):
            print(color("apk غير متاح في هذه البيئة.", RED))
            pause()
            continue
        if choice == "1":
            result = subprocess.run(["apk", "update"])
        elif choice == "2":
            if not confirm("سيتم ترقية الحزم المثبتة. متابعة؟"):
                continue
            result = subprocess.run(["apk", "upgrade"])
        elif choice in ("3", "4", "5"):
            name = ask("اسم الحزمة: ")
            if not name or name.startswith("-") or not re.fullmatch(r"[A-Za-z0-9+_.-]+", name):
                print(color("اسم حزمة غير صالح.", RED))
                pause()
                continue
            args = {"3": ["apk", "add", name], "4": ["apk", "del", name],
                    "5": ["apk", "search", name]}[choice]
            result = subprocess.run(args)
        elif choice == "6":
            show_result(run(["apk", "info"], timeout=40))
            pause()
            continue
        else:
            print(color("اختيار غير صحيح.", RED))
            pause()
            continue
        print(color("اكتملت العملية." if result.returncode == 0 else "انتهت العملية مع خطأ.", GREEN if result.returncode == 0 else RED))
        pause()

def safe_filename(name):
    if not name or name in (".", "..") or "/" in name or "\0" in name:
        return False
    return True

def file_manager():
    current = Path.home()
    while True:
        header("مستكشف الملفات")
        print(color("  المسار: " + str(current), CYAN))
        line()
        try:
            entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except Exception as exc:
            print(color("تعذر قراءة المجلد: " + str(exc), RED))
            pause()
            return
        shown = entries[:35]
        for i, path in enumerate(shown, 1):
            try:
                kind = "[مجلد]" if path.is_dir() else "[ملف]"
                size = "" if path.is_dir() else f"  {path.stat().st_size} B"
                print(f"  {color(str(i).rjust(2), CYAN)} {kind} {path.name}{size}")
            except OSError:
                print(f"  {i:>2} [غير متاح] {path.name}")
        if len(entries) > len(shown):
            print(color(f"  تم عرض {len(shown)} من {len(entries)} عنصر.", DIM))
        line()
        print("  رقم: فتح | u: للأعلى | n: مجلد جديد | f: ملف جديد")
        print("  c: نسخ ملف | m: نقل/إعادة تسمية | d: حذف | q: رجوع")
        action = ask("  > ").lower()
        if action == "q":
            return
        if action == "u":
            current = current.parent
            continue
        if action == "n":
            name = ask("اسم المجلد الجديد: ")
            if safe_filename(name):
                try:
                    (current / name).mkdir()
                    print(color("تم إنشاء المجلد.", GREEN))
                except Exception as exc:
                    print(color(str(exc), RED))
            pause()
            continue
        if action == "f":
            name = ask("اسم الملف الجديد: ")
            if safe_filename(name):
                try:
                    (current / name).touch(exist_ok=False)
                    print(color("تم إنشاء الملف.", GREEN))
                except Exception as exc:
                    print(color(str(exc), RED))
            pause()
            continue
        if action in ("c", "m", "d"):
            raw = ask("رقم الملف ضمن القائمة: ")
            if not raw.isdigit() or not 1 <= int(raw) <= len(shown):
                continue
            source = shown[int(raw) - 1]
            if source.is_dir():
                print(color("هذه العملية متاحة للملفات فقط في هذه النسخة.", YELLOW))
                pause()
                continue
            if action == "d":
                if confirm("حذف الملف " + source.name + " نهائياً؟"):
                    try:
                        source.unlink()
                        print(color("تم الحذف.", GREEN))
                    except Exception as exc:
                        print(color(str(exc), RED))
            else:
                dest_name = ask("اسم الملف الهدف (أو مسار نسبي): ")
                if not dest_name:
                    continue
                dest = Path(dest_name).expanduser()
                if not dest.is_absolute():
                    dest = current / dest
                try:
                    if action == "c":
                        shutil.copy2(str(source), str(dest))
                        print(color("تم نسخ الملف.", GREEN))
                    else:
                        shutil.move(str(source), str(dest))
                        print(color("تم نقل الملف.", GREEN))
                except Exception as exc:
                    print(color("تعذر إتمام العملية: " + str(exc), RED))
            pause()
            continue
        if action.isdigit():
            index = int(action) - 1
            if not 0 <= index < len(shown):
                continue
            target = shown[index]
            if target.is_dir():
                current = target
            elif target.is_file():
                try:
                    if target.stat().st_size > 512 * 1024:
                        print(color("الملف أكبر من 512KB؛ تم منع عرضه.", YELLOW))
                    else:
                        content = target.read_text(encoding="utf-8", errors="replace")
                        header("معاينة ملف")
                        print(color("  " + str(target), GREEN + BOLD))
                        line()
                        rows = content.splitlines()
                        for row in rows[:400]:
                            print(row[:width()])
                        if len(rows) > 400:
                            print(color("... تم اختصار المعاينة.", DIM))
                except Exception as exc:
                    print(color("تعذر فتح الملف: " + str(exc), RED))
                pause()

def command_console():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    while True:
        header("طرفية الأوامر")
        print(color("  نفّذ أوامر shell المعتادة. اكتب exit للعودة.", DIM))
        print(color("  سجل الأوامر محفوظ في: " + str(HISTORY_FILE), DIM))
        line()
        command = ask("  " + str(Path.cwd()) + " $ ")
        if command.lower() in ("exit", "back", "q"):
            return
        if not command:
            continue
        try:
            with HISTORY_FILE.open("a", encoding="utf-8") as history:
                history.write(datetime.now().isoformat(timespec="seconds") + "  " + command + "\n")
            completed = subprocess.run(command, shell=True, executable="/bin/sh")
            print(color("\nرمز الخروج: " + str(completed.returncode), DIM))
        except KeyboardInterrupt:
            print(color("\nتم إيقاف الأمر.", YELLOW))
        except Exception as exc:
            print(color("خطأ: " + str(exc), RED))
        pause()

def system_monitor():
    while True:
        header("مراقبة النظام")
        print(color("  مساحة التخزين", BOLD + GREEN))
        usage = disk_usage()
        if usage:
            print(f"  الإجمالي: {usage.total // (1024**2)} MB")
            print(f"  المستخدم: {usage.used // (1024**2)} MB")
            print(f"  المتاح:   {usage.free // (1024**2)} MB")
        print()
        print(color("  العمليات الجارية", BOLD + GREEN))
        ps = run(["ps"], timeout=10)
        show_result(ps, "تعذر الحصول على قائمة العمليات.")
        print()
        print(color("  الذاكرة", BOLD + GREEN))
        mem = Path("/proc/meminfo")
        if mem.exists():
            try:
                for row in mem.read_text(errors="replace").splitlines()[:8]:
                    print("  " + row)
            except Exception:
                print("  معلومات الذاكرة غير متاحة.")
        else:
            print("  /proc/meminfo غير متاح في هذه البيئة.")
        pause()
        return

def network_tools():
    while True:
        header("أدوات الشبكة")
        item(1, "عرض معلومات الشبكة", "ip addr / ifconfig")
        item(2, "اختبار الاتصال Ping", "إرسال 4 حزم")
        item(3, "استعلام DNS", "getent hosts")
        item(4, "اسم الجهاز")
        item(0, "رجوع")
        line()
        choice = ask("  اختيارك: ")
        if choice == "0":
            return
        if choice == "1":
            result = run(["ip", "addr"])
            if result is None:
                result = run(["ifconfig"])
            show_result(result)
            pause()
        elif choice == "2":
            host = ask("اسم النطاق أو عنوان IP: ")
            if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", host) or host.startswith("-"):
                print(color("عنوان غير صالح.", RED))
                pause()
                continue
            ping = shutil.which("ping")
            if not ping:
                print(color("ping غير مثبت. يمكنك تثبيت الحزمة المناسبة عبر apk.", RED))
            else:
                show_result(run([ping, "-c", "4", "-W", "3", host], timeout=18))
            pause()
        elif choice == "3":
            host = ask("اسم النطاق: ")
            if not re.fullmatch(r"[A-Za-z0-9.-]{1,253}", host) or host.startswith("-"):
                print(color("اسم نطاق غير صالح.", RED))
            else:
                result = run(["getent", "hosts", host])
                if result is None:
                    try:
                        print("DNS:", socket.gethostbyname_ex(host))
                    except Exception as exc:
                        print(color("فشل الاستعلام: " + str(exc), RED))
                else:
                    show_result(result, "لم يتم العثور على سجل.")
            pause()
        elif choice == "4":
            print("اسم الجهاز:", socket.gethostname())
            pause()

def system_info():
    header("معلومات النظام")
    values = [
        ("النظام", platform.platform()),
        ("النواة", platform.release()),
        ("المعمارية", platform.machine()),
        ("المعالج", platform.processor() or "غير متاح"),
        ("Python", platform.python_version()),
        ("مسار Python", sys.executable),
        ("المجلد الحالي", os.getcwd()),
        ("مجلد المستخدم", str(Path.home())),
        ("Shell", os.environ.get("SHELL", "/bin/sh")),
        ("اسم الجهاز", socket.gethostname()),
    ]
    for key, value in values:
        print("  " + color(key + ":", CYAN), value)
    print()
    for args in (["uname", "-a"], ["id"], ["df", "-h", str(Path.home())]):
        result = run(args)
        if result and result.stdout:
            print(color("  $ " + " ".join(args), YELLOW))
            print(textwrap.indent(result.stdout.strip(), "    "))
    pause()

def update_project():
    header("تحديث المشروع")
    root = Path(__file__).resolve().parent
    if not (root / ".git").exists():
        print(color("هذه النسخة ليست مستنسخة عبر Git.", YELLOW))
        print("أعد الاستيراد باستخدام git clone لتفعيل التحديث التلقائي.")
        pause()
        return
    if not shutil.which("git"):
        print(color("Git غير مثبت. نفّذ: apk add git", RED))
        pause()
        return
    if not confirm("سيتم جلب التحديثات من " + REPO + ". متابعة؟"):
        return
    result = subprocess.run(["git", "-C", str(root), "pull", "--ff-only"])
    print(color("تم التحديث." if result.returncode == 0 else "فشل التحديث؛ راجع رسائل Git.", GREEN if result.returncode == 0 else RED))
    pause()

def settings():
    while True:
        header("الإعدادات")
        item(1, "تبديل الألوان", "الحالة الحالية: " + ("مفعلة" if CONFIG.get("colors") else "متوقفة"))
        item(2, "تبديل الساعة", "الحالة الحالية: " + ("ظاهرة" if CONFIG.get("show_clock") else "مخفية"))
        item(0, "رجوع")
        line()
        choice = ask("  اختيارك: ")
        if choice == "0":
            return
        if choice == "1":
            CONFIG["colors"] = not CONFIG.get("colors", True)
        elif choice == "2":
            CONFIG["show_clock"] = not CONFIG.get("show_clock", True)
        else:
            continue
        save_config()
        print(color("تم حفظ الإعدادات.", GREEN))
        pause()



def text_editor():
    while True:
        header("محرر النصوص")
        raw = ask("  مسار الملف (q للرجوع): ")
        if raw.lower() in ("q", "quit", "back"):
            return
        if not raw:
            continue
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists() and (not path.is_file() or path.stat().st_size > 1024 * 1024):
                raise ValueError("الملف ليس ملفاً عادياً أو يتجاوز 1MB.")
            old = path.read_text(encoding="utf-8") if path.exists() else ""
            header("تحرير: " + path.name)
            print(color("  أدخل النص. اكتب .SAVE في سطر منفرد للحفظ أو .CANCEL للإلغاء.", DIM))
            if old:
                print(color("--- المحتوى الحالي ---", YELLOW))
                print(old)
                print(color("--- اكتب المحتوى الجديد بالكامل ---", YELLOW))
            rows = []
            while True:
                try:
                    row = input()
                except (EOFError, KeyboardInterrupt):
                    row = ".CANCEL"
                if row == ".SAVE":
                    break
                if row == ".CANCEL":
                    rows = None
                    break
                rows.append(row)
            if rows is None:
                print(color("تم إلغاء التعديل.", YELLOW))
            else:
                backup = path.with_name(path.name + ".bak")
                if path.exists():
                    shutil.copy2(str(path), str(backup))
                path.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
                print(color("تم الحفظ." + (" مع نسخة .bak" if backup.exists() else ""), GREEN))
        except Exception as exc:
            print(color("تعذر تحرير الملف: " + str(exc), RED))
        pause()


def process_manager():
    header("مدير العمليات")
    show_result(run(["ps", "-o", "pid,ppid,stat,comm"], timeout=10), "لم تتوفر قائمة العمليات.")
    line()
    if confirm("هل تريد إرسال SIGTERM إلى عملية؟"):
        raw = ask("رقم PID: ")
        if not raw.isdigit() or int(raw) <= 1 or int(raw) == os.getpid():
            print(color("رقم PID غير صالح أو محمي.", RED))
        else:
            try:
                os.kill(int(raw), 15)
                print(color("أُرسلت إشارة SIGTERM.", GREEN))
            except ProcessLookupError:
                print(color("العملية غير موجودة.", YELLOW))
            except PermissionError:
                print(color("لا تملك صلاحية إيقاف هذه العملية.", RED))
            except Exception as exc:
                print(color(str(exc), RED))
    pause()


def service_manager():
    header("مدير خدمات OpenRC")
    if not shutil.which("rc-service"):
        print(color("rc-service غير متاح في هذه البيئة.", YELLOW))
        pause()
        return
    show_result(run(["rc-status"], timeout=10), "لا توجد معلومات خدمات.")
    operation = ask("الإجراء (start/stop/restart) أو q: ").lower()
    if operation == "q":
        return
    if operation not in ("start", "stop", "restart"):
        print(color("إجراء غير صالح.", RED))
        pause()
        return
    service = ask("اسم الخدمة: ")
    if not re.fullmatch(r"[A-Za-z0-9_.@-]{1,80}", service):
        print(color("اسم خدمة غير صالح.", RED))
        pause()
        return
    if confirm("تنفيذ " + operation + " للخدمة " + service + "؟"):
        result = subprocess.run(["rc-service", service, operation])
        print(color("نجحت العملية." if result.returncode == 0 else "فشلت العملية.", GREEN if result.returncode == 0 else RED))
    pause()


def backup_manager():
    backup_dir = Path.home() / "ishui-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    header("النسخ الاحتياطي")
    print("  [1] إنشاء نسخة من ملف/مجلد")
    print("  [2] عرض النسخ")
    print("  [3] استعادة نسخة")
    print("  [0] رجوع")
    choice = ask("  اختيارك: ")
    if choice == "0":
        return
    files = sorted(backup_dir.glob("*.tar.gz"))
    if choice == "2":
        for p in files:
            print(" ", p.name, "-", p.stat().st_size, "bytes")
        if not files:
            print(color("لا توجد نسخ احتياطية.", DIM))
        pause()
        return
    if choice == "1":
        target = Path(ask("المسار المراد نسخه داخل مجلد المستخدم: ")).expanduser()
        if not target.is_absolute():
            target = Path.cwd() / target
        try:
            resolved = target.resolve(strict=True)
            home = Path.home().resolve()
            if resolved != home and home not in resolved.parents:
                raise ValueError("النسخ محصور داخل مجلد المستخدم.")
            if resolved == backup_dir.resolve() or backup_dir.resolve() in resolved.parents:
                raise ValueError("لا يمكن نسخ مجلد النسخ الاحتياطية إلى نفسه.")
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            archive = backup_dir / ("ishui-backup-" + stamp + ".tar.gz")
            with tarfile.open(str(archive), "w:gz") as tar:
                tar.add(str(resolved), arcname=resolved.relative_to(home).as_posix() or ".")
            print(color("تم إنشاء النسخة: " + str(archive), GREEN))
        except Exception as exc:
            print(color("فشل النسخ: " + str(exc), RED))
    elif choice == "3":
        for i, p in enumerate(files, 1):
            print(f"  {i}. {p.name}")
        raw = ask("رقم النسخة: ")
        if not raw.isdigit() or not 1 <= int(raw) <= len(files):
            return
        try:
            with tarfile.open(str(files[int(raw) - 1]), "r:gz") as tar:
                home = Path.home().resolve()
                safe = []
                for member in tar.getmembers():
                    dest = (home / member.name).resolve()
                    if (dest == home or home in dest.parents) and (member.isfile() or member.isdir()):
                        safe.append(member)
                print("عدد العناصر الآمنة:", len(safe))
                if confirm("قد تستبدل الاستعادة ملفات موجودة. متابعة؟"):
                    tar.extractall(str(home), members=safe)
                    print(color("اكتملت الاستعادة.", GREEN))
        except Exception as exc:
            print(color("فشلت الاستعادة: " + str(exc), RED))
    pause()


def archive_manager():
    header("مدير ZIP")
    print("  [1] إنشاء ZIP")
    print("  [2] استخراج ZIP")
    print("  [3] عرض المحتويات")
    choice = ask("  اختيارك (q للرجوع): ")
    if choice.lower() == "q":
        return
    try:
        if choice == "1":
            source = Path(ask("المسار: ")).expanduser()
            if not source.is_absolute():
                source = Path.cwd() / source
            output = Path(ask("اسم ملف ZIP: ")).expanduser()
            if not output.is_absolute():
                output = Path.cwd() / output
            if not source.exists() or output.suffix.lower() != ".zip":
                raise ValueError("تحقق من المسار وامتداد ZIP.")
            with zipfile.ZipFile(str(output), "w", zipfile.ZIP_DEFLATED) as zf:
                if source.is_dir():
                    for p in source.rglob("*"):
                        if p.is_file():
                            zf.write(str(p), str(p.relative_to(source.parent)))
                else:
                    zf.write(str(source), source.name)
            print(color("تم إنشاء الأرشيف.", GREEN))
        elif choice in ("2", "3"):
            archive = Path(ask("مسار ZIP: ")).expanduser()
            if not archive.is_absolute():
                archive = Path.cwd() / archive
            with zipfile.ZipFile(str(archive), "r") as zf:
                if choice == "3":
                    for name in zf.namelist()[:300]:
                        print(" ", name)
                else:
                    destination = Path(ask("مجلد الاستخراج: ")).expanduser()
                    if not destination.is_absolute():
                        destination = Path.cwd() / destination
                    destination.mkdir(parents=True, exist_ok=True)
                    root = destination.resolve()
                    safe = [n for n in zf.namelist() if (root / n).resolve() == root or root in (root / n).resolve().parents]
                    if confirm("استخراج " + str(len(safe)) + " ملف إلى " + str(root) + "؟"):
                        for name in safe:
                            zf.extract(name, str(root))
                        print(color("تم الاستخراج.", GREEN))
        else:
            print(color("اختيار غير صالح.", RED))
    except Exception as exc:
        print(color("تعذر التعامل مع الأرشيف: " + str(exc), RED))
    pause()


def system_diagnostics():
    header("فحص النظام")
    checks = [
        ("Python 3", shutil.which("python3")),
        ("Git", shutil.which("git")),
        ("apk", shutil.which("apk")),
        ("Ping", shutil.which("ping")),
        ("OpenRC", shutil.which("rc-service")),
        ("مجلد المستخدم قابل للكتابة", os.access(Path.home(), os.W_OK)),
    ]
    for label, value in checks:
        ok = bool(value)
        print("  " + color("✓" if ok else "—", GREEN if ok else YELLOW) + " " + label +
              ((" : " + str(value)) if isinstance(value, str) else ""))
    try:
        socket.getaddrinfo("github.com", 443)
        print(color("  ✓ DNS إلى GitHub يعمل", GREEN))
    except Exception:
        print(color("  — تعذر حل github.com؛ تحقق من الشبكة وDNS", YELLOW))
    print(color("  قد تختلف النتائج حسب إصدار iSH وصلاحياته.", DIM))
    pause()


def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ("--version", "-v"):
            print(APP_NAME, VERSION, "-", AUTHOR)
            return
        if arg in ("--help", "-h"):
            print("ISH UI " + VERSION + " | --help --version --doctor --backup")
            return
        if arg == "--doctor":
            system_diagnostics()
            return
        if arg == "--backup":
            backup_manager()
            return
    actions = {
        "1": package_manager,
        "2": file_manager,
        "3": command_console,
        "4": system_monitor,
        "5": network_tools,
        "6": system_info,
        "7": update_project,
        "8": settings,
        "9": text_editor,
        "10": process_manager,
        "11": service_manager,
        "12": backup_manager,
        "13": archive_manager,
        "14": system_diagnostics,
    }
    while True:
        dashboard()
        choice = ask("  اختيارك: ")
        if choice == "0":
            clear()
            print(color("شكراً لاستخدام ISH UI — يوسف الحازمي", CYAN))
            return
        action = actions.get(choice)
        if action:
            action()
        else:
            print(color("اختيار غير صحيح.", RED))
            pause()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        clear()
        print(color("\nتم إغلاق ISH UI.", YELLOW))
