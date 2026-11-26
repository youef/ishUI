#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ISH UI — يوسف الحازمي
Interactive terminal control panel for iSH / Alpine Linux.
Uses only Python standard library.
"""

import os
import sys
import shutil
import platform
import subprocess
import shlex
import textwrap
from pathlib import Path
from datetime import datetime

APP_NAME = "ISH UI"
VERSION = "1.0.0"
AUTHOR = "يوسف الحازمي"

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

def color(text, shade=WHITE):
    return shade + str(text) + RESET

def clear():
    os.system("clear" if os.name != "nt" else "cls")

def terminal_width():
    return max(48, min(shutil.get_terminal_size((80, 24)).columns, 100))

def line(char="─"):
    print(color(char * terminal_width(), BLUE))

def pause():
    try:
        input(color("\\nاضغط Enter للمتابعة...", DIM))
    except (EOFError, KeyboardInterrupt):
        pass

def safe_run(args, timeout=20):
    try:
        return subprocess.run(
            args, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=timeout
        )
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        print(color("انتهت مهلة تنفيذ الأمر.", RED))
        return None
    except Exception as exc:
        print(color("تعذر تنفيذ الأمر: " + str(exc), RED))
        return None

def get_storage():
    try:
        usage = shutil.disk_usage(str(Path.home()))
        return usage
    except Exception:
        return None

def header():
    clear()
    width = terminal_width()
    print(color("╔" + "═" * (width - 2) + "╗", CYAN))
    title = "ISH UI  •  iSH CONTROL CENTER"
    print(color("║", CYAN) + color(title.center(width - 2), BOLD + WHITE) + color("║", CYAN))
    subtitle = "يوسف الحازمي  |  الإصدار " + VERSION
    print(color("║", CYAN) + color(subtitle.center(width - 2), MAGENTA) + color("║", CYAN))
    print(color("╚" + "═" * (width - 2) + "╝", CYAN))
    print(color("  " + datetime.now().strftime("%Y-%m-%d  %H:%M"), DIM))
    line()

def menu_item(number, title, description=""):
    left = color(" [" + str(number) + "] ", CYAN + BOLD)
    print(left + color(title, WHITE) + (color(" — " + description, DIM) if description else ""))

def dashboard():
    header()
    storage = get_storage()
    print(color("  لوحة التحكم الرئيسية", BOLD + GREEN))
    print()
    print("  " + color("النظام:", CYAN), platform.system(), platform.release())
    print("  " + color("المعمارية:", CYAN), platform.machine())
    print("  " + color("Python:", CYAN), platform.python_version())
    print("  " + color("المستخدم:", CYAN), os.environ.get("USER", "unknown"))
    print("  " + color("المجلد:", CYAN), str(Path.home()))
    if storage:
        used = storage.used / storage.total * 100 if storage.total else 0
        print("  " + color("التخزين:", CYAN),
              f"{storage.used // (1024**2)} MB مستخدم / {storage.total // (1024**2)} MB")
        bar_width = 28
        filled = int(bar_width * used / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        print("  [" + color(bar, GREEN if used < 80 else YELLOW) + f"] {used:.1f}%")
    print()
    line()
    print(color("  اختر إحدى الأدوات:", BOLD + WHITE))
    menu_item(1, "إدارة الحزم", "تحديث وتثبيت وحذف حزم Alpine")
    menu_item(2, "مستكشف الملفات", "عرض المجلدات والملفات وقراءة النصوص")
    menu_item(3, "منفذ الأوامر", "تشغيل أوامر Linux")
    menu_item(4, "معلومات النظام", "تفاصيل بيئة iSH")
    menu_item(5, "تحديث المشروع", "جلب آخر نسخة من GitHub")
    menu_item(0, "خروج", "إغلاق الواجهة")
    line()

def package_manager():
    while True:
        header()
        print(color("  مدير الحزم Alpine (apk)", BOLD + GREEN))
        print()
        menu_item(1, "تحديث فهارس الحزم", "apk update")
        menu_item(2, "ترقية الحزم المثبتة", "apk upgrade")
        menu_item(3, "تثبيت حزمة", "apk add")
        menu_item(4, "حذف حزمة", "apk del")
        menu_item(5, "البحث عن حزمة", "apk search")
        menu_item(6, "عرض الحزم المثبتة", "apk info")
        menu_item(0, "رجوع")
        line()
        choice = input(color("  اختيارك: ", CYAN)).strip()
        if choice == "0":
            return
        if not shutil.which("apk"):
            print(color("الأمر apk غير متاح في هذه البيئة.", RED))
            pause()
            continue
        if choice in ("1", "2"):
            args = ["apk", "update"] if choice == "1" else ["apk", "upgrade"]
            if choice == "2":
                confirm = input(color("قد يتم تحديث عدة حزم. متابعة؟ (y/N): ", YELLOW)).lower()
                if confirm != "y":
                    continue
            print(color("\\nجاري التنفيذ...\\n", YELLOW))
            subprocess.run(args)
        elif choice in ("3", "4", "5"):
            name = input(color("  اسم الحزمة: ", CYAN)).strip()
            if not name or name.startswith("-"):
                continue
            args = {"3": ["apk", "add", name],
                    "4": ["apk", "del", name],
                    "5": ["apk", "search", name]}[choice]
            subprocess.run(args)
        elif choice == "6":
            result = safe_run(["apk", "info"], timeout=30)
            print(result.stdout if result else "تعذر قراءة القائمة.")
        else:
            print(color("اختيار غير صحيح.", RED))
        pause()

def file_browser():
    current = Path.home()
    while True:
        header()
        print(color("  مستكشف الملفات", BOLD + GREEN))
        print(color("  المسار: " + str(current), CYAN))
        line()
        try:
            entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            print(color("لا تملك صلاحية قراءة هذا المجلد.", RED))
            pause()
            return
        except Exception as exc:
            print(color(str(exc), RED))
            pause()
            return
        shown = entries[:40]
        for index, entry in enumerate(shown, 1):
            marker = "📁" if entry.is_dir() else "📄"
            name = entry.name + ("/" if entry.is_dir() else "")
            print(f"  {color(str(index).rjust(2), CYAN)} {marker} {name}")
        if len(entries) > 40:
            print(color(f"  ... يوجد {len(entries) - 40} عنصر إضافي", DIM))
        line()
        print("  اكتب رقم العنصر لفتحه، (u) للأعلى، (r) لتحديث، (q) رجوع")
        action = input(color("  > ", CYAN)).strip().lower()
        if action == "q":
            return
        if action == "u":
            current = current.parent
            continue
        if action == "r":
            continue
        if not action.isdigit():
            continue
        index = int(action) - 1
        if index < 0 or index >= len(shown):
            continue
        target = shown[index]
        if target.is_dir():
            current = target
        elif target.is_file():
            try:
                if target.stat().st_size > 256 * 1024:
                    print(color("الملف أكبر من 256KB ولن يُعرض داخل المستكشف.", YELLOW))
                    pause()
                    continue
                data = target.read_text(encoding="utf-8", errors="replace")
                header()
                print(color("  " + target.name, BOLD + GREEN))
                line()
                for row in data.splitlines()[:300]:
                    print(row[:terminal_width()])
                if len(data.splitlines()) > 300:
                    print(color("\\n... تم اختصار العرض", DIM))
            except Exception as exc:
                print(color("تعذر فتح الملف: " + str(exc), RED))
            pause()

def command_runner():
    while True:
        header()
        print(color("  منفذ أوامر Linux", BOLD + GREEN))
        print(color("  اكتب الأمر كما تكتبه في الطرفية. اكتب exit للرجوع.", DIM))
        line()
        try:
            command = input(color("  " + str(Path.home()) + " $ ", CYAN)).strip()
        except (EOFError, KeyboardInterrupt):
            return
        if command.lower() in ("exit", "back", "q"):
            return
        if not command:
            continue
        print()
        try:
            # Run through the user's shell so pipes, redirects and shell syntax work.
            subprocess.run(command, shell=True, executable="/bin/sh")
        except KeyboardInterrupt:
            print(color("\\nتم إيقاف الأمر.", YELLOW))
        except Exception as exc:
            print(color("خطأ: " + str(exc), RED))
        pause()

def system_info():
    header()
    print(color("  معلومات النظام", BOLD + GREEN))
    print()
    values = [
        ("النظام", platform.platform()),
        ("إصدار النواة", platform.release()),
        ("المعمارية", platform.machine()),
        ("المعالج", platform.processor() or "غير متاح"),
        ("Python", platform.python_version()),
        ("مسار Python", sys.executable),
        ("المجلد الحالي", os.getcwd()),
        ("مجلد المستخدم", str(Path.home())),
        ("Shell", os.environ.get("SHELL", "/bin/sh")),
    ]
    for key, value in values:
        print("  " + color(key + ":", CYAN), value)
    print()
    for cmd in (["uname", "-a"], ["id"], ["df", "-h", str(Path.home())]):
        result = safe_run(cmd)
        if result and result.stdout:
            print(color("  $ " + " ".join(cmd), YELLOW))
            print(textwrap.indent(result.stdout.strip(), "    "))
    pause()

def update_project():
    header()
    print(color("  تحديث ISH UI من GitHub", BOLD + GREEN))
    root = Path(__file__).resolve().parent
    if not (root / ".git").exists():
        print(color("المجلد الحالي ليس نسخة Git. أعد الاستيراد باستخدام git clone.", YELLOW))
        pause()
        return
    if not shutil.which("git"):
        print(color("Git غير مثبت. نفّذ: apk add git", RED))
        pause()
        return
    confirm = input(color("سيتم تنزيل آخر تحديثات المشروع. متابعة؟ (y/N): ", YELLOW)).lower()
    if confirm != "y":
        return
    result = subprocess.run(["git", "-C", str(root), "pull", "--ff-only"])
    print(color("اكتمل التحديث." if result.returncode == 0 else "فشل التحديث؛ راجع رسالة Git أعلاه.", GREEN if result.returncode == 0 else RED))
    pause()

def main():
    while True:
        dashboard()
        try:
            choice = input(color("  اختيارك: ", CYAN)).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if choice == "0":
            clear()
            print(color("شكراً لاستخدام ISH UI — يوسف الحازمي", CYAN))
            return
        elif choice == "1":
            package_manager()
        elif choice == "2":
            file_browser()
        elif choice == "3":
            command_runner()
        elif choice == "4":
            system_info()
        elif choice == "5":
            update_project()
        else:
            print(color("اختيار غير صحيح.", RED))
            pause()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        clear()
        print(color("\\nتم إغلاق ISH UI.", YELLOW))
