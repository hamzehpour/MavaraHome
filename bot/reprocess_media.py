#!/usr/bin/env python3
"""
Shrink images that were uploaded BEFORE the server started resizing.

Everything in bot/media/ (and optionally bot/private_media/receipts/) was
stored exactly as uploaded. This walks those files and re-encodes them
through the same profiles utils/image_processing.py applies to new uploads.

WHY THE EXTENSION NEVER CHANGES:
The file's path is stored in the database — events.poster, portfolio.poster,
team_members.photo, the `gallery` JSON arrays, payments.receipt_file_id.
Converting a .jpg to .webp would rename the file and break every one of
those pointers. So each file keeps its name and format and only loses
pixels. That forgoes WebP's extra 10-14%, but the dimension cap is nearly
all of the saving anyway, and it means this script touches no database rows
at all.

Usage:
    python3 reprocess_media.py                 # dry run — report only
    python3 reprocess_media.py --apply         # rewrite, after backing up
    python3 reprocess_media.py --apply --receipts   # include private receipts
"""
import os
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.image_processing import UPLOAD_PROFILES  # noqa: E402

BOT_ROOT = os.path.dirname(os.path.abspath(__file__))
MEDIA_ROOT = os.path.join(BOT_ROOT, "media")
RECEIPTS_ROOT = os.path.join(BOT_ROOT, "private_media", "receipts")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _fmt(n: int) -> str:
    return f"{n / 1024:.1f} KB" if n < 1024 * 1024 else f"{n / 1024 / 1024:.2f} MB"


def shrink(path: str, kind: str) -> bytes | None:
    """Re-encoded bytes in the file's ORIGINAL format, or None to leave it."""
    from PIL import Image, ImageOps
    import io

    profile = UPLOAD_PROFILES.get(kind)
    if profile is None:
        return None

    with open(path, "rb") as f:
        raw = f.read()
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            src_format = probe.format
            if getattr(probe, "n_frames", 1) > 1:
                return None          # animated — leave it alone
        with Image.open(io.BytesIO(raw)) as img:
            img = ImageOps.exif_transpose(img)
            if img.size[0] <= profile.box[0] and img.size[1] <= profile.box[1]:
                return None          # already within the cap
            img.thumbnail(profile.box, Image.Resampling.LANCZOS)
            has_alpha = img.mode in ("RGBA", "LA") or (
                img.mode == "P" and "transparency" in img.info
            )
            out = io.BytesIO()
            if src_format == "PNG":
                img.convert("RGBA" if has_alpha else "RGB").save(out, "PNG", optimize=True)
            elif src_format == "WEBP":
                img.convert("RGBA" if has_alpha else "RGB").save(out, "WEBP", quality=profile.quality, method=4)
            else:
                img.convert("RGB").save(out, "JPEG", quality=profile.quality, optimize=True)
            processed = out.getvalue()
    except Exception as exc:
        print(f"  ! skipped (cannot process): {path} — {type(exc).__name__}: {exc}")
        return None

    return processed if len(processed) < len(raw) else None


def collect() -> list[tuple[str, str]]:
    """(path, kind) for every image under a directory named after a profile."""
    found = []
    for root, _dirs, files in os.walk(MEDIA_ROOT):
        kind = os.path.basename(root)
        if kind not in UPLOAD_PROFILES:
            continue          # media/mansour/ and any other legacy folder
        for name in files:
            if os.path.splitext(name)[1].lower() in IMAGE_EXTS:
                found.append((os.path.join(root, name), kind))
    return found


def main() -> None:
    apply = "--apply" in sys.argv
    include_receipts = "--receipts" in sys.argv

    targets = collect()
    if include_receipts and os.path.isdir(RECEIPTS_ROOT):
        targets += [
            (os.path.join(RECEIPTS_ROOT, n), "receipt")
            for n in os.listdir(RECEIPTS_ROOT)
            if os.path.splitext(n)[1].lower() in IMAGE_EXTS
        ]

    if not targets:
        print("No images found to process.")
        return

    backup_dir = None
    if apply:
        backup_dir = os.path.join(BOT_ROOT, f"media_backup_{datetime.now():%Y-%m-%d_%H%M}")
        print(f"Backups → {backup_dir}\n")

    before = after = changed = 0
    for path, kind in sorted(targets):
        original = os.path.getsize(path)
        processed = shrink(path, kind)
        before += original
        if processed is None:
            after += original
            continue
        changed += 1
        after += len(processed)
        rel = os.path.relpath(path, BOT_ROOT)
        print(f"  {rel}  [{kind}]  {_fmt(original)} → {_fmt(len(processed))}")
        if apply:
            dest = os.path.join(backup_dir, rel)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(path, dest)
            with open(path, "wb") as f:
                f.write(processed)

    saved = before - after
    pct = (100 * saved / before) if before else 0
    print(f"\n{len(targets)} image(s) scanned, {changed} {'rewritten' if apply else 'would change'}")
    print(f"{_fmt(before)} → {_fmt(after)}   (saving {_fmt(saved)}, {pct:.1f}%)")
    if not apply:
        print("\nDry run — nothing was written. Re-run with --apply to rewrite "
              "(originals are copied to a backup folder first).")


if __name__ == "__main__":
    main()
