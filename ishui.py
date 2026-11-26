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
import time
import base64
import hashlib
import urllib.parse
import tarfile
import zipfile
from pathlib import Path
from datetime import datetime

APP_NAME = "ISH UI"
VERSION = "5.5.0"
AUTHOR = "يوسف الحازمي"
REPO = "https://github.com/youef/ishUI"
CONFIG_DIR = Path.home() / ".config" / "ishui"
CONFIG_FILE = CONFIG_DIR / "config.json"
WEB_SERVER_INFO = None
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
    defaults = {"colors": True, "show_clock": True, "theme": "ocean", "background_mode": "dark"}
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

THEMES = {
    "ocean": {"name": "المحيط الداكن", "cyan": "\033[96m", "blue": "\033[94m", "green": "\033[92m", "yellow": "\033[93m", "red": "\033[91m", "magenta": "\033[95m", "white": "\033[97m"},
    "matrix": {"name": "ماتريكس", "cyan": "\033[92m", "blue": "\033[32m", "green": "\033[92m", "yellow": "\033[93m", "red": "\033[91m", "magenta": "\033[32m", "white": "\033[97m"},
    "sunset": {"name": "الغروب", "cyan": "\033[95m", "blue": "\033[94m", "green": "\033[93m", "yellow": "\033[93m", "red": "\033[91m", "magenta": "\033[95m", "white": "\033[97m"},
    "mono": {"name": "أحادي داكن", "cyan": "\033[37m", "blue": "\033[90m", "green": "\033[37m", "yellow": "\033[97m", "red": "\033[97m", "magenta": "\033[90m", "white": "\033[97m"},
    "paper": {"name": "ورقي فاتح", "cyan": "\033[36m", "blue": "\033[34m", "green": "\033[32m", "yellow": "\033[33m", "red": "\033[31m", "magenta": "\033[35m", "white": "\033[30m"},
}

def color(value, shade=WHITE):
    """Apply foreground colors only; never paint the entire iSH terminal."""
    if not CONFIG.get("colors", True):
        return str(value)
    theme = THEMES.get(CONFIG.get("theme", "ocean"), THEMES["ocean"])
    shade_map = {CYAN: "cyan", BLUE: "blue", GREEN: "green", YELLOW: "yellow", RED: "red", MAGENTA: "magenta", WHITE: "white"}
    key = next((name for code, name in shade_map.items() if code in shade), None)
    emphasis = "".join(code for code in (BOLD, DIM) if code in shade)
    foreground = theme.get(key, "") if key else ""
    if CONFIG.get("background_mode") == "light" and key == "white":
        foreground = "\033[30m"
    return emphasis + foreground + str(value) + RESET

def clear():
    # Reset terminal attributes before clearing so no stale background color
    # can turn the whole iSH viewport into a solid black/white rectangle.
    sys.stdout.write("\033[0m\033[2J\033[H")
    sys.stdout.flush()

def width():
    return max(32, min(shutil.get_terminal_size((80, 24)).columns, 88))

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

def header(section="الرئيسية"):
    clear()
    print(color("ISH UI", BOLD + CYAN) + color("  /  iSH TOOLKIT", DIM))
    print(color("الإصدار " + VERSION + "   •   " + section, DIM))
    line("─")


def item(number, title, detail=""):
    # Minimal text-first menu: stable on narrow iPhone terminal screens.
    print("  " + color(str(number).rjust(2, "0"), CYAN) +
          color("  ›  ", DIM) + color(title, WHITE))


def storage_summary():
    usage = disk_usage()
    if not usage or not usage.total:
        return "غير متاح", 0
    used = usage.used / usage.total * 100
    return f"{usage.used // (1024**2)} / {usage.total // (1024**2)} MB", used


def welcome_screen():
    """Animated welcome and timed 30-second progress bar."""
    clear()
    frames = ["◐", "◓", "◑", "◒"]
    print()
    print(color("  ╔══════════════════════════════════╗", BOLD + CYAN))
    print(color("  ║             ISH UI 5.3           ║", BOLD + CYAN))
    print(color("  ╚══════════════════════════════════╝", BOLD + CYAN))
    print()
    print(color("       أهلاً بك في مركز أدوات iSH", BOLD + WHITE))
    print(color("       إدارة ذكية • تطوير • شبكات • أمن", DIM))
    print()
    print(color("       BY يوسف الحازمي", MAGENTA))
    print("\n  جارٍ تجهيز بيئة العمل...")
    for index in range(31):
        percent = int(index * 100 / 30)
        filled = int(index * 24 / 30)
        bar = "█" * filled + "░" * (24 - filled)
        sys.stdout.write("\r  " + color(frames[index % 4], CYAN) + " [" + bar + "] " + str(percent).rjust(3) + "%")
        sys.stdout.flush()
        if index < 30:
            time.sleep(1)
    print("\n")
    print(color("  اكتمل التجهيز — مرحباً بك!", GREEN + BOLD))
    time.sleep(0.8)
def dashboard():
    header("لوحة التحكم الذكية")
    storage, percent = storage_summary()
    print(color("  مركز التحكم  •  " + datetime.now().strftime("%H:%M:%S"), BOLD + WHITE))
    print("  " + platform.system() + " / Python " + platform.python_version())
    print("  التخزين: " + storage + (("  •  %.1f%% مستخدم" % percent) if percent else ""))
    print("  الثيم: " + THEMES.get(CONFIG.get("theme", "ocean"), THEMES["ocean"])["name"])
    if WEB_SERVER_INFO:
        web_port, web_token = WEB_SERVER_INFO
        print(color("  لوحة الويب: http://127.0.0.1:" + str(web_port), GREEN))
        print(color("  رمز الدخول: " + web_token, YELLOW))
    print()
    print(color("  النظام والإدارة", BOLD + CYAN))
    item(1, "مدير الحزم")
    item(2, "مستكشف الملفات")
    item(3, "طرفية الأوامر")
    item(4, "مراقبة النظام")
    item(5, "معلومات النظام")
    print()
    print(color("  مختبر الأمن والشبكات", BOLD + CYAN))
    item(6, "أدوات الشبكة")
    item(7, "مختبر فحص المواقع والأمن")
    item(8, "فحص النظام")
    item(18, "مختبر الأمن السيبراني المتقدم")
    item(19, "فحص النطاقات دفعة واحدة")
    print()
    print(color("  أدوات الإنتاجية والتطوير", BOLD + CYAN))
    item(9, "محرر النصوص")
    item(10, "مدير العمليات")
    item(11, "مدير الخدمات")
    item(12, "النسخ الاحتياطي")
    item(13, "مدير الأرشيف")
    item(16, "صندوق أدوات المطورين")
    print()
    print(color("  تخصيص وتحديث", BOLD + CYAN))
    item(14, "التحديث الذكي")
    item(15, "الإعدادات")
    item(17, "تغيير الثيم")
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

    # Protect local edits before pulling upstream changes.
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture_output=True, text=True
    )
    if status.returncode != 0:
        print(color("تعذر فحص حالة Git؛ أوقفنا التحديث حفاظاً على ملفاتك.", RED))
        pause()
        return

    stashed = False
    if status.stdout.strip():
        print(color("تم العثور على تعديلات محلية. سنحفظها مؤقتاً قبل التحديث.", YELLOW))
        stash = subprocess.run(
            ["git", "-C", str(root), "stash", "push", "--include-untracked",
             "-m", "ISH UI auto-update safety stash"],
            capture_output=True, text=True
        )
        if stash.returncode != 0:
            print(color("تعذر حفظ التعديلات؛ لم يتم تنفيذ التحديث.", RED))
            if stash.stderr:
                print(stash.stderr.strip())
            pause()
            return
        stashed = "No local changes" not in (stash.stdout or "")

    result = subprocess.run(["git", "-C", str(root), "pull", "--ff-only"])
    if result.returncode != 0:
        print(color("فشل التحديث. نحاول إعادة التعديلات المحلية.", RED))
        if stashed:
            subprocess.run(["git", "-C", str(root), "stash", "pop"])
        pause()
        return

    if stashed:
        restored = subprocess.run(["git", "-C", str(root), "stash", "pop"])
        if restored.returncode != 0:
            print(color("تم تحديث المشروع، لكن حدث تعارض عند استعادة تعديلاتك.", YELLOW))
            print("تعديلاتك محفوظة في Git stash ولم تُحذف. راجعها بالأمر: git stash list")
            pause()
            return

    print(color("تم التحديث بنجاح.", GREEN))
    pause()

def settings():
    while True:
        header("الإعدادات والمظهر")
        mode = CONFIG.get("background_mode", "dark")
        mode_label = {"dark": "داكن — خلفية سوداء", "light": "فاتح — خلفية بيضاء", "terminal": "حسب إعداد الطرفية"}.get(mode, "داكن")
        theme_name = THEMES.get(CONFIG.get("theme", "ocean"), THEMES["ocean"])["name"]
        item(1, "تبديل ألوان النصوص", "الحالة: " + ("مفعلة" if CONFIG.get("colors") else "متوقفة"))
        item(2, "تبديل الساعة", "الحالة: " + ("ظاهرة" if CONFIG.get("show_clock") else "مخفية"))
        item(3, "تغيير الخلفية", "الحالية: " + mode_label)
        item(4, "اختيار الثيم والألوان", "الحالي: " + theme_name)
        print(color("  الخلفية الحالية: " + mode_label, DIM))
        print(color("  الثيم الحالي: " + theme_name, DIM))
        print(color("  ألوان النصوص: " + ("مفعلة" if CONFIG.get("colors") else "متوقفة"), DIM))
        item(0, "رجوع")
        line()
        choice = ask("  اختيارك: ")
        if choice == "0":
            return
        if choice == "1":
            CONFIG["colors"] = not CONFIG.get("colors", True)
        elif choice == "2":
            CONFIG["show_clock"] = not CONFIG.get("show_clock", True)
        elif choice == "3":
            modes = ["dark", "light", "terminal"]
            CONFIG["background_mode"] = modes[(modes.index(mode) + 1) % len(modes)]
        elif choice == "4":
            theme_manager()
            continue
        else:
            continue
        save_config()
        print(color("تم حفظ الإعدادات. سيظهر التغيير على كامل الشاشة بعد إعادة رسمها.", GREEN))
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



def web_tool_manager():
    """Check and optionally install practical website diagnostic tools."""
    packages = [
        ("curl", "curl", "طلبات HTTP وفحص الترويسات"),
        ("wget", "wget", "تنزيل واختبار الوصول"),
        ("nslookup", "bind-tools", "استعلامات DNS"),
        ("openssl", "openssl", "فحص شهادات TLS"),
        ("update-ca-certificates", "ca-certificates", "شهادات الجهات الموثوقة"),
    ]
    while True:
        header("أدوات فحص المواقع")
        missing = []
        for command, package, description in packages:
            path = shutil.which(command)
            installed = bool(path)
            print("  " + color("✓" if installed else "○",
                               GREEN if installed else YELLOW) +
                  " " + command.ljust(25) +
                  color(description, DIM))
            if not installed:
                missing.append(package)
        line()
        item(1, "تثبيت الأدوات الناقصة", "apk add")
        item(2, "إعادة فحص الأدوات")
        item(0, "رجوع")
        choice = ask("  اختيارك: ")
        if choice == "0":
            return
        if choice == "2":
            continue
        if choice != "1":
            continue
        if not missing:
            print(color("كل الأدوات المطلوبة مثبتة بالفعل.", GREEN))
            pause()
            continue
        if not shutil.which("apk"):
            print(color("مدير apk غير متاح. ثبّت الأدوات يدوياً في بيئتك.", RED))
            pause()
            continue
        print("الحزم المطلوبة:", ", ".join(sorted(set(missing))))
        if confirm("سيتم تثبيت الحزم الناقصة عبر Alpine apk. متابعة؟"):
            result = run(["apk", "add"] + sorted(set(missing)), timeout=180)
            show_result(result, "انتهى التثبيت دون مخرجات.")
            print(color("أُعيد فحص الأدوات بعد التثبيت.", CYAN))
            for command, package, description in packages:
                ok = bool(shutil.which(command))
                print("  " + color("✓" if ok else "—",
                                   GREEN if ok else YELLOW) + " " + command)
        pause()


def website_inspector():
    """Safe, low-impact web posture checks for explicitly authorized sites."""
    import time
    import urllib.request
    import urllib.error
    import urllib.parse
    import ssl
    import http.cookiejar

    def fetch(url, method="GET", timeout=10):
        request = urllib.request.Request(
            url, method=method,
            headers={"User-Agent": "ISH-UI-Security-Audit/5.0",
                     "Accept": "*/*"})
        try:
            return urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as exc:
            return exc

    def print_finding(level, message):
        shade = RED if level == "مرتفع" else YELLOW if level == "مراجعة" else GREEN
        print("  " + color("[" + level + "]", shade) + " " + message)

    while True:
        header("تدقيق الويب")
        print(color("  للمواقع التي تملكها أو لديك تصريح صريح بفحصها فقط.", DIM))
        item(1, "تدقيق إعدادات موقع", "DNS · TLS · HTTPS · Headers · Cookies")
        item(2, "فحص ملفات التعريف العامة", "robots.txt · sitemap.xml · security.txt")
        item(3, "إدارة أدوات الفحص", "التحقق من أدوات الشبكة وتثبيت الناقص")
        item(0, "رجوع")
        choice = ask("  اختيارك: ")
        if choice == "0":
            return
        if choice == "3":
            web_tool_manager()
            continue
        if choice not in ("1", "2"):
            continue

        raw = ask("  نطاق/رابط الموقع: ")
        if not raw:
            continue
        if "://" not in raw:
            raw = "https://" + raw
        try:
            parsed = urllib.parse.urlsplit(raw)
            if parsed.scheme not in ("http", "https") or not parsed.hostname:
                raise ValueError("أدخل رابط HTTP أو HTTPS صحيحاً.")
            if parsed.username or parsed.password or any(ch.isspace() for ch in raw):
                raise ValueError("الرابط يحتوي بيانات دخول أو مسافات غير مسموحة.")
            host = parsed.hostname
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            base = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc,
                                            parsed.path or "/", "", ""))
        except Exception as exc:
            print(color("رابط غير صالح: " + str(exc), RED))
            pause()
            continue

        print()
        print(color("  الهدف: " + host, BOLD + CYAN))
        print(color("  تنبيه: الفحص محدود بطلبات HTTP قياسية ولا ينفذ استغلالاً.", DIM))
        line()

        if choice == "2":
            for path in ("/robots.txt", "/sitemap.xml", "/.well-known/security.txt"):
                url = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
                try:
                    response = fetch(url, timeout=8)
                    status = response.getcode()
                    ctype = response.headers.get("Content-Type", "غير معروف")
                    print("  ", path, "→ HTTP", status, "|", ctype)
                    response.close()
                except Exception as exc:
                    print("  ", path, "→ تعذر الفحص:", str(exc)[:100])
            pause()
            continue

        # DNS resolution
        print(color("  1. DNS", BOLD + CYAN))
        try:
            started = time.perf_counter()
            addresses = sorted(set(x[4][0] for x in socket.getaddrinfo(
                host, port, type=socket.SOCK_STREAM)))
            print_finding("سليم", "تم حل النطاق خلال %.0f ms" %
                          ((time.perf_counter() - started) * 1000))
            for address in addresses[:8]:
                print("     ", address)
        except Exception as exc:
            print_finding("مرتفع", "فشل حل DNS: " + str(exc))
            addresses = []

        # TLS validation and certificate lifetime
        if parsed.scheme == "https":
            print(color("\n  2. TLS والشهادة", BOLD + CYAN))
            try:
                context = ssl.create_default_context()
                with socket.create_connection((host, port), timeout=8) as sock:
                    with context.wrap_socket(sock, server_hostname=host) as secure:
                        cert = secure.getpeercert()
                        print_finding("سليم", "اتصال TLS موثوق — " + str(secure.version()))
                        expiry = cert.get("notAfter")
                        if expiry:
                            expiry_ts = ssl.cert_time_to_seconds(expiry)
                            days = int((expiry_ts - time.time()) / 86400)
                            print("     صلاحية الشهادة:", expiry, "(متبقي", days, "يوم)")
                            if days < 0:
                                print_finding("مرتفع", "الشهادة منتهية الصلاحية")
                            elif days < 21:
                                print_finding("مراجعة", "الشهادة تقترب من الانتهاء")
                        cipher = secure.cipher()
                        if cipher:
                            print("     مجموعة التشفير:", cipher[0])
            except Exception as exc:
                print_finding("مرتفع", "تعذر التحقق من TLS: " + str(exc))
        else:
            print_finding("مرتفع", "الرابط يستخدم HTTP غير المشفر")
            print("     اختبر نسخة HTTPS بعد تفعيلها.")

        # Main HTTP response and security headers
        print(color("\n  3. ترويسات واستجابة HTTP", BOLD + CYAN))
        response = None
        try:
            started = time.perf_counter()
            response = fetch(base, timeout=12)
            elapsed = (time.perf_counter() - started) * 1000
            headers = response.headers
            status = response.getcode()
            print("     HTTP", status, "| %.0f ms" % elapsed)
            print("     الوجهة النهائية:", response.geturl())

            required = [
                ("Strict-Transport-Security", "HSTS", parsed.scheme == "https"),
                ("Content-Security-Policy", "CSP", True),
                ("X-Content-Type-Options", "X-Content-Type-Options", True),
                ("Referrer-Policy", "Referrer-Policy", True),
                ("Permissions-Policy", "Permissions-Policy", True),
            ]
            for key, label, applicable in required:
                if not applicable:
                    continue
                value = headers.get(key)
                if value:
                    print_finding("سليم", label + " موجود")
                else:
                    print_finding("مراجعة", label + " غير موجود — راجع سياسة الموقع")

            if parsed.scheme == "https" and not headers.get("Strict-Transport-Security"):
                print_finding("مراجعة", "فعّل HSTS بعد التأكد من جاهزية جميع النطاقات الفرعية")
            if headers.get("Access-Control-Allow-Origin") == "*":
                print_finding("مراجعة", "CORS يسمح بأصل عام (*)؛ تحقق من عدم كشف بيانات حساسة")
            server = headers.get("Server")
            powered = headers.get("X-Powered-By")
            if server:
                print_finding("مراجعة", "الخادم يعلن معلومات: " + server[:100])
            if powered:
                print_finding("مراجعة", "X-Powered-By مكشوف: " + powered[:100])

            cookies = headers.get_all("Set-Cookie") or []
            for cookie in cookies[:10]:
                lower = cookie.lower()
                missing = []
                if "secure" not in lower:
                    missing.append("Secure")
                if "httponly" not in lower:
                    missing.append("HttpOnly")
                if "samesite" not in lower:
                    missing.append("SameSite")
                if missing:
                    print_finding("مراجعة", "كوكي يحتاج مراجعة خصائص: " + ", ".join(missing))
            if not cookies:
                print("     لم تُرسل كوكيز في الاستجابة الأولى.")
        except Exception as exc:
            print_finding("مرتفع", "تعذر طلب HTTP: " + str(exc))
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass

        # Verify plain HTTP redirects to HTTPS (one standard request only).
        if parsed.scheme == "http":
            print(color("\n  4. تحويل HTTPS", BOLD + CYAN))
            try:
                response = fetch(base, method="HEAD", timeout=8)
                final_scheme = urllib.parse.urlsplit(response.geturl()).scheme
                if final_scheme == "https":
                    print_finding("سليم", "يتم التحويل إلى HTTPS")
                else:
                    print_finding("مراجعة", "لم يتم رصد تحويل إلى HTTPS")
                response.close()
            except Exception as exc:
                print("     تعذر التحقق:", str(exc)[:100])

        print()
        print_finding("معلومة", "النتائج مؤشرات إعدادات وليست إثباتاً لوجود ثغرة.")
        print_finding("معلومة", "لا يتضمن هذا الفاحص استغلالاً أو تخمين كلمات مرور أو تجاوز صلاحيات.")
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


def theme_manager():
    while True:
        header("الثيمات والألوان")
        keys = list(THEMES.keys())
        for i, key in enumerate(keys, 1):
            current = "  ✓ الحالي" if CONFIG.get("theme") == key else ""
            print("  " + str(i) + ". " + THEMES[key]["name"] + current)
        print("  0. رجوع")
        choice = ask("  اختر الثيم: ")
        if choice == "0":
            return
        if choice.isdigit() and 1 <= int(choice) <= len(keys):
            CONFIG["theme"] = keys[int(choice) - 1]
            # Keep readable contrast by pairing the paper theme with a light background.
            CONFIG["background_mode"] = "light" if CONFIG["theme"] == "paper" else "dark"
            save_config()
            clear()
            print(color("  معاينة الثيم: " + THEMES[CONFIG["theme"]]["name"], BOLD + CYAN))
            print(color("  نص أبيض/ملون على خلفية داكنة أو فاتحة", WHITE))
            print(color("  عناوين • نجاح • تحذير • تنبيه", GREEN))
            print(color("  1234567890  ABC abc  العربية", YELLOW))
            print(color("تم تطبيق الثيم وحفظه.", GREEN))
        else:
            print(color("اختيار غير صحيح.", RED))
        pause()


def developer_tools():
    """Small standard-library developer toolbox."""
    while True:
        header("صندوق أدوات المطورين")
        item(1, "تنسيق JSON والتحقق منه")
        item(2, "Base64 ترميز / فك ترميز")
        item(3, "URL Encode / Decode")
        item(4, "حساب SHA-256 و SHA-512")
        item(5, "فك قراءة JWT محلياً")
        item(6, "اختبار API بطلب GET محدود")
        item(0, "رجوع")
        choice = ask("  اختيارك: ")
        if choice == "0":
            return
        if choice == "1":
            try:
                print(json.dumps(json.loads(ask("ألصق JSON: ")), ensure_ascii=False, indent=2))
            except Exception as exc:
                print(color("JSON غير صالح: " + str(exc), RED))
        elif choice == "2":
            raw = ask("النص أو Base64: ")
            mode = ask("e للترميز أو d لفك الترميز: ").lower()
            try:
                if mode == "e":
                    print(base64.b64encode(raw.encode("utf-8")).decode("ascii"))
                elif mode == "d":
                    print(base64.b64decode(raw.encode("ascii"), validate=True).decode("utf-8", errors="replace"))
                else:
                    print("اختيار غير صحيح.")
            except Exception as exc:
                print(color("تعذر التحويل: " + str(exc), RED))
        elif choice == "3":
            raw = ask("النص أو الرابط: ")
            mode = ask("e للترميز أو d لفك الترميز: ").lower()
            print(urllib.parse.quote(raw, safe="") if mode == "e" else urllib.parse.unquote(raw))
        elif choice == "4":
            raw = ask("النص: ").encode("utf-8")
            print("SHA-256:", hashlib.sha256(raw).hexdigest())
            print("SHA-512:", hashlib.sha512(raw).hexdigest())
        elif choice == "5":
            try:
                parts = ask("JWT: ").split(".")
                if len(parts) != 3:
                    raise ValueError("JWT يجب أن يتكون من ثلاثة أجزاء.")
                decoded = []
                for part in parts[:2]:
                    part += "=" * (-len(part) % 4)
                    decoded.append(json.dumps(json.loads(base64.urlsafe_b64decode(part)), ensure_ascii=False, indent=2))
                print("Header:\n" + decoded[0] + "\nPayload:\n" + decoded[1])
                print(color("فك القراءة لا يتحقق من التوقيع أو الصلاحية.", YELLOW))
            except Exception as exc:
                print(color("تعذر تحليل JWT: " + str(exc), RED))
        elif choice == "6":
            raw = ask("رابط API (HTTPS مفضل): ")
            try:
                parsed = urllib.parse.urlsplit(raw)
                if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
                    raise ValueError("رابط HTTP/HTTPS غير صالح أو يحتوي بيانات دخول.")
                import urllib.request
                req = urllib.request.Request(raw, headers={"User-Agent": "ISH-UI-DevTools/5.0", "Accept": "application/json"})
                with urllib.request.urlopen(req, timeout=8) as response:
                    body = response.read(65536).decode("utf-8", errors="replace")
                    print("HTTP", response.status, "|", response.headers.get("Content-Type", ""))
                    try:
                        print(json.dumps(json.loads(body), ensure_ascii=False, indent=2)[:12000])
                    except Exception:
                        print(body[:12000])
            except Exception as exc:
                print(color("فشل طلب API: " + str(exc), RED))
        else:
            print(color("اختيار غير صحيح.", RED))
        pause()

def security_lab():
    """Launch the optional standard-library security tools module."""
    try:
        from security_tools import run as run_security_lab
        run_security_lab()
    except Exception as exc:
        print(color("تعذر تشغيل مختبر الأمن: " + str(exc), RED))
        pause()


def batch_site_audit():
    """Open the batch domain audit directly from the main dashboard."""
    try:
        from site_audit import run as run_site_audit
        run_site_audit()
    except Exception as exc:
        print(color("تعذر تشغيل الفحص الدفعي: " + str(exc), RED))
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
    global WEB_SERVER_INFO
    try:
        from web_server import start as start_web_server
        WEB_SERVER_INFO = start_web_server()
    except Exception as exc:
        WEB_SERVER_INFO = None
        print(color("تعذر تشغيل خادم الويب المحلي: " + str(exc), YELLOW))
        time.sleep(1.5)
    welcome_screen()
    actions = {
        "1": package_manager,
        "2": file_manager,
        "3": command_console,
        "4": system_monitor,
        "5": system_info,
        "6": network_tools,
        "7": website_inspector,
        "8": system_diagnostics,
        "9": text_editor,
        "10": process_manager,
        "11": service_manager,
        "12": backup_manager,
        "13": archive_manager,
        "14": update_project,
        "15": settings,
        "16": developer_tools,
        "17": theme_manager,
        "18": security_lab,
        "19": batch_site_audit,
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
