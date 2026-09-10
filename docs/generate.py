#!/usr/bin/env python3
"""
مولد بخش‌های ماشین‌خوانِ مستندات — و نگهبان تازگی آن‌ها.

چرا این فایل وجود دارد: بعضی از واقعیت‌های این پروژه آن‌قدر زیادند که
دستی‌نوشتنشان یعنی همان روزِ اول کهنه شدن — ۶۸ اندپوینت، ۲۴ جدول، ۶۴ کلید
تنظیمات. این‌ها مستقیم از خود کد خوانده می‌شوند تا نتوانند بی‌صدا از واقعیت
جدا شوند.

    python3 docs/generate.py           # فایل‌های تولیدی را می‌نویسد
    python3 docs/generate.py --check   # فقط بررسی می‌کند؛ اگر کهنه باشند exit 1

حالت --check در CI اجرا می‌شود (.github/workflows/tests.yml). اگر کسی یک
اندپوینت اضافه کند و مستندات را به‌روز نکند، CI قرمز می‌شود.

این اسکریپت هیچ وابستگی خارجی ندارد و پروژه را import نمی‌کند — فقط سورس را
با ast/regex می‌خواند، پس بدون venv و بدون .env هم کار می‌کند.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "bot" / "api" / "server.py"
SCHEMA = ROOT / "bot" / "database" / "schema.py"
SETTINGS_SERVICE = ROOT / "bot" / "services" / "settings_service.py"
DATA_MODEL_DOC = ROOT / "docs" / "03-data-model.md"
SETTINGS_PAGE = ROOT / "website" / "pages" / "admin" / "settings.html"

API_DOC = ROOT / "docs" / "04-api-reference.md"
SETTINGS_DOC = ROOT / "docs" / "_generated-settings.md"

BANNER = (
    "<!-- این فایل به‌صورت خودکار از روی کد تولید شده است. دستی ویرایشش نکن.\n"
    "     بازتولید:  python3 docs/generate.py  -->\n"
)


# ─────────────────────────────── endpoints ───────────────────────────────

def _readable_path(pattern: str) -> str:
    """r"^/api/v1/admin/events/(\\d+)$"  ->  /api/v1/admin/events/{id}"""
    p = pattern.lstrip("^").rstrip("$")
    p = p.replace(r"(\d+)", "{id}")
    p = re.sub(r"\(\[[^\]]+\]\+\)", "{slug}", p)   # ([\w%-]+) و مشابهش
    p = re.sub(r"\([^)]*\)", "{param}", p)          # هر گروه باقی‌مانده
    return p


def collect_endpoints() -> dict[str, list[str]]:
    """هر مسیری که در متدهای do_* واقعاً بررسی می‌شود، به ترتیب ظهور."""
    tree = ast.parse(SERVER.read_text(encoding="utf-8"))
    verbs: dict[str, list[str]] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("do_"):
            continue
        verb = node.name[3:]
        if verb == "OPTIONS":
            continue
        found: list[tuple[int, str]] = []
        for sub in ast.walk(node):
            # الگوی ۱:  if path == "/api/v1/..."
            if isinstance(sub, ast.Compare) and isinstance(sub.left, ast.Name) and sub.left.id == "path":
                for op, comp in zip(sub.ops, sub.comparators):
                    if isinstance(op, ast.Eq) and isinstance(comp, ast.Constant) and isinstance(comp.value, str):
                        if comp.value.startswith("/api/"):
                            found.append((sub.lineno, comp.value))
            # الگوی ۲:  m = re.match(r"^/api/v1/...$", path)
            if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                    and sub.func.attr == "match" and sub.args
                    and isinstance(sub.args[0], ast.Constant)
                    and isinstance(sub.args[0].value, str)
                    and sub.args[0].value.startswith("^/api/")):
                found.append((sub.lineno, _readable_path(sub.args[0].value)))
        seen: set[str] = set()
        ordered = []
        for _, path in sorted(found):
            if path not in seen:
                seen.add(path)
                ordered.append(path)
        verbs[verb] = ordered
    return verbs


def _auth_of(path: str) -> str:
    if "/admin/" in path or path.endswith("/admin"):
        return "ادمین (JWT)"
    if "/account/" in path:
        return "مشتری (JWT)"
    if "/auth/" in path:
        return "—"
    return "عمومی"


def render_api_doc(verbs: dict[str, list[str]]) -> str:
    total = sum(len(v) for v in verbs.values())
    order = ["GET", "POST", "PATCH", "DELETE"]
    out = [BANNER, "# ۰۴ — مرجع API\n"]
    out.append(
        f"همه‌ی مسیرها زیر `/api/v1` هستند. مجموع **{total}** مسیر: "
        + " · ".join(f"{len(verbs.get(v, []))} {v}" for v in order)
        + ".\n"
    )
    out.append(
        "پاسخ موفق همیشه `{\"data\": …}` است و خطا `{\"error\": \"…\"}` با کد وضعیت "
        "متناسب (`400` اعتبارسنجی، `401` احراز هویت، `404` نبودن، `409` تعارض).\n\n"
        "احراز هویت با هدر `Authorization: Bearer <token>` انجام می‌شود. توکن ادمین "
        "از `POST /api/v1/admin/login` و توکن مشتری از `POST /api/v1/auth/customer/verify-otp` "
        "گرفته می‌شود. جزئیات هر هندلر در `bot/api/server.py` است — مسیریابی دستی است، "
        "پس مسیر جدید باید صریحاً به متد `do_*` مربوطه اضافه شود وگرنه بی‌صدا ۴۰۴ می‌دهد.\n"
    )
    for verb in order:
        paths = verbs.get(verb, [])
        if not paths:
            continue
        out.append(f"\n## {verb}\n\n| مسیر | دسترسی |\n|---|---|\n")
        for p in paths:
            out.append(f"| `{p}` | {_auth_of(p)} |\n")
    out.append(
        "\n---\n\n> این فایل خودکار تولید می‌شود (`python3 docs/generate.py`). "
        "برای توضیح رفتار هر اندپوینت، خود `bot/api/server.py` را بخوان — "
        "پرکامنت است و دلیل تصمیم‌ها کنار کد نوشته شده.\n"
    )
    return "".join(out)


# ─────────────────────────────── settings ────────────────────────────────

def _dict_literal(source: str, name: str) -> dict:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        # هم `X = {...}` و هم `X: dict[str, str] = {...}`
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                return ast.literal_eval(node.value)
    raise SystemExit(f"{name} پیدا نشد")


def render_settings_doc() -> str:
    src = SETTINGS_SERVICE.read_text(encoding="utf-8")
    editable = _dict_literal(src, "EDITABLE_SETTINGS")
    types = _dict_literal(src, "SETTINGS_FIELD_TYPES")
    out = [BANNER, "# کلیدهای تنظیمات (تولید خودکار)\n\n"]
    out.append(
        f"**{len(editable)}** کلید در جدول `settings` که ادمین می‌تواند از پنل وب یا از "
        "منوی تنظیمات ربات عوض کند — بدون دیپلوی. تعریف در "
        "`bot/services/settings_service.py`، گروه‌بندی صفحه‌ی پنل در آرایه‌ی `TABS` در "
        "`website/pages/admin/settings.html`.\n\n"
    )
    out.append("| کلید | نوع | توضیح |\n|---|---|---|\n")
    for key, label in editable.items():
        label_one_line = " ".join(str(label).split())
        if len(label_one_line) > 110:
            label_one_line = label_one_line[:107] + "…"
        out.append(f"| `{key}` | {types.get(key, 'text')} | {label_one_line} |\n")
    return "".join(out)


# ──────────────────────────── freshness checks ───────────────────────────

def _schema_tables() -> list[str]:
    src = SCHEMA.read_text(encoding="utf-8")
    # پرانتز الزامی است تا جمله‌ی واقعی SQL از متن کامنت‌هایی که همین عبارت را
    # توضیح می‌دهند جدا شود (وگرنه «CREATE TABLE IF NOT EXISTS silently does…»
    # به‌عنوان جدولی به نام silently خوانده می‌شود).
    return sorted(set(re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)\s*\(", src)))


def invariant_failures() -> list[str]:
    """بررسی‌هایی که کپی‌شدن واقعیت را لازم ندارند، فقط از نبودنش خبر می‌دهند."""
    problems: list[str] = []

    doc = DATA_MODEL_DOC.read_text(encoding="utf-8")
    for table in _schema_tables():
        if table not in doc:
            problems.append(
                f"جدول `{table}` در schema.py هست ولی در docs/03-data-model.md اسمی از آن نیست"
            )

    # هر کلید قابل‌ویرایش باید جایی در صفحه‌ی تنظیمات پنل قابل دسترس باشد.
    editable = _dict_literal(SETTINGS_SERVICE.read_text(encoding="utf-8"), "EDITABLE_SETTINGS")
    page = SETTINGS_PAGE.read_text(encoding="utf-8")
    # این چهار کلید عمداً از بخش عمومی بیرون‌اند و باکس اختصاصی «قالب بلیت» دارند.
    ticket_box = {"ticket_template_title", "ticket_template_subtitle",
                  "ticket_template_footer", "ticket_template_logo"}
    for key in editable:
        if key not in page and key not in ticket_box:
            problems.append(
                f"کلید `{key}` قابل‌ویرایش است ولی در هیچ تبی از صفحه‌ی تنظیمات پنل نیامده"
            )
    return problems


# ──────────────────────────────── main ───────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="فقط بررسی کن که فایل‌های تولیدی به‌روزند")
    args = parser.parse_args()

    wanted = {
        API_DOC: render_api_doc(collect_endpoints()),
        SETTINGS_DOC: render_settings_doc(),
    }
    problems = invariant_failures()

    if args.check:
        for path, content in wanted.items():
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != content:
                problems.append(
                    f"{path.relative_to(ROOT)} کهنه است — `python3 docs/generate.py` را اجرا کن"
                )
        if problems:
            print("مستندات به‌روز نیستند:\n")
            for p in problems:
                print("  ✗ " + p)
            return 1
        print("✓ مستندات تولیدی به‌روزند و همه‌ی بررسی‌ها پاس شدند.")
        return 0

    for path, content in wanted.items():
        path.write_text(content, encoding="utf-8")
        print(f"نوشته شد: {path.relative_to(ROOT)}")
    if problems:
        print("\n⚠️  هشدارها:")
        for p in problems:
            print("  ✗ " + p)
        return 1
    print("✓ همه‌ی بررسی‌ها پاس شدند.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
