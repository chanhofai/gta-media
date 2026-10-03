"""The converter, end to end, against throwaway git repos.

    python3 tools/test_convert_cards.py

Runs before every conversion in the workflow: a Pillow upgrade that changes
what comes out should stop the run, not quietly write odd cards.
"""
import io, os, pathlib, subprocess, sys, tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import convert_cards as C  # noqa: E402
from PIL import Image, ImageCms  # noqa: E402

FAILS = []


def check(label, ok):
    if ok:
        print(f"  PASS  {label}")
    else:
        FAILS.append(label)
        print(f"  FAIL  {label}")


def git(root, *args, when=None):
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    if when:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = f"@{when} +0000"
    subprocess.run(["git", "-C", str(root), *args], check=True, env=env,
                   capture_output=True)


def repo():
    root = pathlib.Path(tempfile.mkdtemp())
    git(root, "init", "-q")
    (root / "cards").mkdir()
    return root


def commit(root, when):
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "upload", when=when)


def png(path, size=(1122, 1402), colour=(40, 120, 60), mode="RGB"):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new(mode, size, colour).save(path, "PNG")


def card(path, colour=(200, 30, 30)):
    Image.new("RGB", (1080, 1350), colour).save(path, "JPEG", quality=88)


def pixel(path, xy=(540, 675)):
    with Image.open(path) as im:
        return im.convert("RGB").getpixel(xy)


def close(a, b, tol=12):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def is_jpeg_card(path):
    with Image.open(path) as im:
        return im.format == "JPEG" and im.size == (1080, 1350) and im.mode == "RGB"


print("names")
for name, want in [
    ("gta-2026-10-07.png", ("2026-10-07", 0)),
    ("gta-2026-10-07.jpg.png", ("2026-10-07", 0)),
    ("GTA-2026-10-07.PNG", ("2026-10-07", 0)),
    ("gta-2026-10-07 (1).png", ("2026-10-07", 1)),
    ("gta_2026-10-07.webp", ("2026-10-07", 0)),
    ("2026-10-07.png", ("2026-10-07", 0)),
    ("gta-2026-10-07", ("2026-10-07", 0)),
    ("gta-2026-02-30.png", None),
    ("ChatGPT Image Sep 22, 2026, 12_01_52 AM.png", None),
    ("2026-09-16-spring-mulch.jpg", None),
    ("gta-2026-10-07.md", None),
    (".gta-2026-10-07.jpg.tmp", None),
]:
    check(f"{name!r} -> {want}", C.parse_name(name) == want)

print("\nconversion")
r = repo()
card(r / "cards/gta-2026-10-01.jpg")                       # already right
png(r / "gta-2026-10-02.png")                              # PNG at the top level
png(r / "cards/gta-2026-10-03.jpg.png", size=(1024, 1536))  # double extension, 2:3
png(r / "cards/gta-2026-10-04.jpg")                        # a PNG renamed .jpg
card(r / "cards/gta-2026-10-05.jpg", colour=(200, 30, 30))  # to be replaced...
rgba = Image.new("RGBA", (1122, 1402), (0, 0, 0, 0))       # transparent background
rgba.paste((30, 60, 200, 255), (300, 300, 800, 1100))
rgba.save(r / "gta-2026-10-06.png")
(r / "cards/gta-2026-10-08.png").write_bytes(b"not an image at all")
png(r / "ChatGPT Image Oct 3, 2026, 09_14_02 AM.png")
(r / "README.md").write_text("x")
commit(r, 1_790_000_000)
png(r / "cards/gta-2026-10-05.png", colour=(30, 200, 30))   # ...by this, later
png(r / "gta-2026-10-09.png", colour=(10, 10, 10))          # two at once for the 9th:
png(r / "gta-2026-10-09 (1).png", colour=(250, 250, 250))   # the later download wins
commit(r, 1_790_000_100)

before = (r / "cards/gta-2026-10-01.jpg").read_bytes()
dry = C.run(r, apply=False, changed=["ChatGPT Image Oct 3, 2026, 09_14_02 AM.png"])
check("a dry run writes nothing",
      not (r / "cards/gta-2026-10-02.jpg").exists() and (r / "gta-2026-10-02.png").exists())
res = C.run(r, apply=True, changed=["ChatGPT Image Oct 3, 2026, 09_14_02 AM.png",
                                    "gta-2026-10-09.png", "gta-2026-10-09 (1).png"])
check("a dry run and a real run agree on what to do",
      [d["dest"] for d in dry.done] == [d["dest"] for d in res.done])
done = {d["day"]: d for d in res.done}

check("leaves a card that is already right byte-for-byte alone",
      "2026-10-01" not in done and (r / "cards/gta-2026-10-01.jpg").read_bytes() == before)
check("turns a top-level PNG into cards/gta-2026-10-02.jpg and removes the upload",
      is_jpeg_card(r / "cards/gta-2026-10-02.jpg") and not (r / "gta-2026-10-02.png").exists())
check("matches gta-2026-10-03.jpg.png",
      is_jpeg_card(r / "cards/gta-2026-10-03.jpg")
      and not (r / "cards/gta-2026-10-03.jpg.png").exists())
check("crops a 2:3 image to 4:5 and says to check the edges",
      "check the edges" in done["2026-10-03"]["note"])
check("fixes a PNG renamed .jpg in place",
      is_jpeg_card(r / "cards/gta-2026-10-04.jpg") and done["2026-10-04"]["note"] == "fixed in place")
check("a new upload replaces the card that was there",
      close(pixel(r / "cards/gta-2026-10-05.jpg"), (30, 200, 30))
      and not (r / "cards/gta-2026-10-05.png").exists()
      and "replaces" in done["2026-10-05"]["note"])
check("puts a transparent background on white, not black",
      close(pixel(r / "cards/gta-2026-10-06.jpg", (20, 20)), (255, 255, 255))
      and close(pixel(r / "cards/gta-2026-10-06.jpg"), (30, 60, 200)))
check("leaves an unreadable upload in place and says so",
      (r / "cards/gta-2026-10-08.png").exists()
      and any("gta-2026-10-08.png" in p and "could not be read" in p for p in res.problems))
check("two uploads for one day: the later download wins",
      close(pixel(r / "cards/gta-2026-10-09.jpg"), (250, 250, 250))
      and not (r / "gta-2026-10-09.png").exists()
      and not (r / "gta-2026-10-09 (1).png").exists())
check("...and that is flagged, not silent",
      any("2 uploads for 2026-10-09" in p for p in res.problems))
check("an upload with no date in its name is left alone and flagged",
      (r / "ChatGPT Image Oct 3, 2026, 09_14_02 AM.png").exists()
      and any("does not say which day" in p for p in res.problems))
check("never touches a file whose name is not a card's",
      (r / "README.md").read_text() == "x")
check("every card is under Instagram's 8MB",
      all((r / d["dest"]).stat().st_size < C.MAX_BYTES for d in res.done))
check("no temporary files left behind",
      not any(p.name.endswith(".tmp") for p in r.rglob("*")))
again = C.run(r, apply=True, changed=[])
check("a second run finds nothing left to do except the unreadable file",
      again.done == [] and len(again.problems) == 1)

print("\nordering")
r = repo()
png(r / "gta-2026-10-10 (3).png", colour=(10, 10, 10))
commit(r, 1_790_000_000)
png(r / "gta-2026-10-10.png", colour=(250, 250, 250))
commit(r, 1_790_000_500)
C.run(r, apply=True)
check("a later commit beats a higher (n) from an earlier one",
      close(pixel(r / "cards/gta-2026-10-10.jpg"), (250, 250, 250)))

print("\ncolour")
r = repo()
srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
Image.new("RGB", (1122, 1402), (180, 90, 40)).save(r / "gta-2026-10-11.png", icc_profile=srgb)
Image.new("CMYK", (1080, 1350), (0, 255, 255, 0)).save(r / "gta-2026-10-12.jpg", "JPEG")
Image.new("P", (800, 1000), 0).save(r / "gta-2026-10-13.gif")
commit(r, 1_790_000_000)
C.run(r, apply=True)
check("an image carrying a colour profile converts cleanly",
      close(pixel(r / "cards/gta-2026-10-11.jpg"), (180, 90, 40)))
check("a CMYK JPEG comes out RGB",
      is_jpeg_card(r / "cards/gta-2026-10-12.jpg"))
check("a palette GIF comes out RGB",
      is_jpeg_card(r / "cards/gta-2026-10-13.jpg"))

print(f"\n{'ALL PASSED' if not FAILS else f'{len(FAILS)} FAILED: ' + ', '.join(FAILS)}")
sys.exit(1 if FAILS else 0)
