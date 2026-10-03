#!/usr/bin/env python3
"""Turn whatever was uploaded into the card Instagram will actually take.

Instagram only accepts JPEG, and it fetches each card from this repo's Pages
URL, so every card has to end up at cards/gta-YYYY-MM-DD.jpg as a real
1080 x 1350 JPEG. ChatGPT downloads PNGs. This closes the gap: any image whose
name says which day it is for becomes that day's card, and the upload is
removed once the card exists. All of these work, in cards/ or at the top level:

    gta-2026-10-07.png          gta-2026-10-07.jpg.png
    gta-2026-10-07 (1).png      2026-10-07.webp

An upload always replaces the card already there for that day — re-uploading
is how you swap an image. A file whose name does not say which day it is for
is left alone and reported, because there is no safe way to guess.

    python3 tools/convert_cards.py            # dry run: say what would change
    python3 tools/convert_cards.py --apply    # do it

Runs by itself on every upload (.github/workflows/convert-cards.yml).
Needs Pillow:  pip install pillow
"""
from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

try:
    from PIL import Image, ImageCms, ImageOps
except ImportError:
    sys.exit("This needs Pillow.  pip install pillow")

# The same numbers as publish/import_cards.py in the main repo. Change both or
# neither, or cards made by hand and cards made here stop matching.
WIDTH, HEIGHT = 1080, 1350
RATIO = WIDTH / HEIGHT
QUALITY = 88
MAX_BYTES = 8 * 1024 * 1024          # Instagram's ceiling
CROP_WARN = 0.15                     # past this, text near an edge may be lost

CARDS = "cards"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".jfif", ".webp", ".gif", ".bmp",
                  ".tif", ".tiff", ".heic", ".heif", ".avif"}
SKIP_TOP = {"tools"}                 # dot-folders (.git, .github) are skipped too
DAY = re.compile(r"^(?:gta[-_ ]?)?(\d{4})-(\d{2})-(\d{2})(?:\s*\((\d+)\))?$", re.I)


def parse_name(name: str) -> tuple[str, int] | None:
    """The post date a filename is for, plus its "(n)" download-copy number.

    Peels off any stack of image extensions first, because renaming a download
    by hand so often produces gta-2026-10-07.jpg.png.
    """
    stem = name.strip()
    while True:
        head, dot, ext = stem.rpartition(".")
        if dot and head and f".{ext.lower()}" in IMAGE_SUFFIXES:
            stem = head.strip()
        else:
            break
    m = DAY.match(stem)
    if not m:
        return None
    try:
        day = date(int(m[1]), int(m[2]), int(m[3])).isoformat()
    except ValueError:
        return None
    return day, int(m[4] or 0)


def is_image_name(name: str) -> bool:
    return Path(name).suffix.lower() in IMAGE_SUFFIXES


def scan(root: Path) -> dict[str, list[Path]]:
    """Every file anywhere in the repo whose name says which day it is for."""
    found: dict[str, list[Path]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        top = Path(dirpath) == root
        dirnames[:] = sorted(d for d in dirnames
                             if not d.startswith(".") and not (top and d in SKIP_TOP))
        for f in sorted(filenames):
            parsed = parse_name(f)
            if parsed:
                found.setdefault(parsed[0], []).append(Path(dirpath, f))
    return found


def is_card(path: Path) -> bool:
    """Already exactly what Instagram needs — then leave it byte-for-byte alone."""
    try:
        if path.stat().st_size > MAX_BYTES:
            return False
        with Image.open(path) as im:
            return (im.format == "JPEG" and im.size == (WIDTH, HEIGHT)
                    and im.mode == "RGB")
    except Exception:
        return False


def committed_at(root: Path, path: Path) -> float:
    """When this file last arrived. Git keeps that; a fresh checkout's mtimes
    are all "just now", so they only stand in outside a repo."""
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "log", "-1", "--format=%ct", "--",
             str(path.relative_to(root))],
            capture_output=True, text=True, timeout=30).stdout.strip()
        if out:
            return float(out)
    except Exception:
        pass
    return path.stat().st_mtime


def crop_box(size: tuple[int, int]) -> tuple[int, int, int, int]:
    """The largest 4:5 rectangle in the middle of the image."""
    w, h = size
    if w / h > RATIO:
        new_w = round(h * RATIO)
        left = (w - new_w) // 2
        return (left, 0, left + new_w, h)
    new_h = round(w / RATIO)
    top = (h - new_h) // 2
    return (0, top, w, top + new_h)


SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))


def to_rgb(im: Image.Image, icc: bytes | None) -> Image.Image:
    """Flat sRGB, whatever came in.

    Transparency goes onto white: dropping the alpha channel instead leaves
    whatever colour the invisible pixels happened to hold, usually black. A
    colour profile (a phone screenshot in Display P3, a CMYK export) is
    converted rather than stripped — stripping it shifts every colour.
    """
    if im.mode in ("RGBA", "LA", "PA", "RGBa", "La") or \
            (im.mode == "P" and "transparency" in im.info):
        rgba = im.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (255, 255, 255))
        flat.paste(rgba, mask=rgba.getchannel("A"))
        im = flat
    if icc:
        try:
            if im.mode not in ("RGB", "CMYK", "L"):
                im = im.convert("RGB")
            im = ImageCms.profileToProfile(
                im, ImageCms.ImageCmsProfile(io.BytesIO(icc)), SRGB,
                outputMode="RGB")
        except Exception:
            pass                     # an unreadable profile: treat it as sRGB
    return im.convert("RGB")


def convert(src: Path, dest: Path, apply: bool) -> dict:
    """Make the card. Writes beside the destination and swaps it in, so a
    failure halfway never leaves a truncated card where Instagram will look."""
    with Image.open(src) as raw:
        fmt = raw.format or "?"
        icc = raw.info.get("icc_profile")
        im = to_rgb(ImageOps.exif_transpose(raw), icc)
    w, h = im.size
    box = crop_box(im.size)
    lost = 1 - (box[2] - box[0]) * (box[3] - box[1]) / (w * h)
    out = im.crop(box).resize((WIDTH, HEIGHT), Image.LANCZOS)
    size = None
    if apply:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(f".{dest.name}.tmp")
        out.save(tmp, "JPEG", quality=QUALITY, optimize=True, progressive=True,
                 subsampling=0)
        size = tmp.stat().st_size
        os.replace(tmp, dest)
    return {"format": fmt, "size": (w, h), "lost": lost, "bytes": size}


@dataclass
class Result:
    done: list[dict] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def run(root: Path, apply: bool, changed: list[str] | None = None) -> Result:
    root = root.resolve()
    res = Result()
    for day, paths in sorted(scan(root).items()):
        dest = root / CARDS / f"gta-{day}.jpg"
        sources = [p for p in paths if not (p == dest and is_card(p))]
        if not sources:
            continue
        # Newest upload wins; between two in the same commit, the higher
        # "(n)" — that is the browser's name for the later download.
        ranked = sorted(sources, key=lambda p: (committed_at(root, p),
                                                parse_name(p.name)[1], p.name))
        src = ranked[-1]
        others = [p for p in ranked[:-1] if p != dest]
        replacing = dest.exists() and src != dest
        try:
            info = convert(src, dest, apply)
        except Exception as e:
            res.problems.append(
                f"`{rel(src, root)}` could not be read as an image "
                f"({type(e).__name__}). Delete it and upload a PNG or JPG.")
            continue
        if apply:
            for p in [src, *others]:
                if p != dest and p.exists():
                    p.unlink()
        if others:
            res.problems.append(
                f"{len(ranked)} uploads for {day} at once — used "
                f"`{rel(src, root)}`, removed "
                + ", ".join(f"`{rel(p, root)}`" for p in others)
                + ". If one was meant for another day, upload it again "
                  "under that day's name (it is still in the history).")
        note = []
        if info["lost"] > 0.01:
            note.append(f"cropped {info['lost']:.0%}")
            if info["lost"] > CROP_WARN:
                note.append("check the edges")
        if replacing:
            note.append("replaces the card that was there")
        elif src == dest:
            note.append("fixed in place")
        res.done.append({"day": day, "src": rel(src, root), "dest": rel(dest, root),
                         "was": f"{info['size'][0]}x{info['size'][1]} {info['format']}",
                         "note": ", ".join(note), "bytes": info["bytes"]})

    for name in changed or []:
        p = root / name
        if (is_image_name(name) and p.is_file() and not parse_name(p.name)
                and not name.startswith((".", "tools/"))):
            res.problems.append(
                f"`{name}` does not say which day it is for, so it was left "
                f"alone. Delete it and upload it again named after the post, "
                f"e.g. `gta-2026-10-07.png`.")
    return res


def rel(p: Path, root: Path) -> str:
    return str(p.relative_to(root))


def commit_message(res: Result) -> str:
    n = len(res.done)
    title = (f"Convert {res.done[0]['src']} into a card" if n == 1
             else f"Convert {n} uploads into cards")
    lines = [f"{d['src']} -> {d['dest']} ({d['was']}"
             + (f", {d['note']}" if d["note"] else "") + ")" for d in res.done]
    return title + "\n\n" + "\n".join(lines) + "\n"


def summary(res: Result, apply: bool) -> str:
    out = []
    if res.done:
        out += ["### Cards" + ("" if apply else " (dry run)"), "",
                "| Upload | Card | Was | Note |", "|---|---|---|---|"]
        out += [f"| `{d['src']}` | `{d['dest']}` | {d['was']} | {d['note']} |"
                for d in res.done]
    else:
        out.append("Nothing to convert — every card is already a 1080×1350 JPEG.")
    if res.problems:
        out += ["", "### Needs a look", ""] + [f"- {p}" for p in res.problems]
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="write the cards and remove the uploads (default: dry run)")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                    help="the gta-media checkout (default: this script's repo)")
    ap.add_argument("--changed-from", type=Path,
                    help="NUL-separated paths this push added, from git diff -z; "
                         "an image among them that names no day is reported")
    ap.add_argument("--commit-message", type=Path,
                    help="write a commit message here when anything changed")
    args = ap.parse_args()

    changed = None
    if args.changed_from and args.changed_from.exists():
        changed = [n for n in args.changed_from.read_text().split("\0") if n]
    res = run(args.root, args.apply, changed)

    for d in res.done:
        print(f"{d['src']:<44} -> {d['dest']:<26} {d['was']:<16} {d['note']}")
    if not res.done:
        print("nothing to convert")
    for p in res.problems:
        print(f"PROBLEM: {p.replace('`', '')}")
    if not args.apply and res.done:
        print("\nDry run — nothing written. Re-run with --apply.")

    report = os.environ.get("GITHUB_STEP_SUMMARY")
    if report:
        with open(report, "a") as f:
            f.write(summary(res, args.apply))
    if args.commit_message and res.done and args.apply:
        args.commit_message.write_text(commit_message(res))
    return 1 if res.problems else 0


if __name__ == "__main__":
    sys.exit(main())
