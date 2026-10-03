# gta-media
Image host for Gardening Tips Australia

## How cards get here

Generate the image in ChatGPT, download it, rename it after the day it is for,
and upload it. **A PNG is fine**:

```
gta-2026-10-07.png
```

Drop it into `cards/`, or anywhere else in the repo; it gets moved. Within a
minute or two the **Convert cards** workflow turns it into the card Instagram
needs and removes the upload:

```
cards/gta-2026-10-07.jpg      1080 × 1350, JPEG
```

Instagram only accepts JPEG, and it fetches each card from this repo's Pages
URL instead of taking uploaded bytes. That is why this repo is public, and why
the conversion has to happen here.

### What it accepts

- **Any common format**: PNG, JPG, WebP, GIF, TIFF. Not HEIC (iPhone photos);
  export those as JPG first.
- **Any size.** It is centre-cropped to 4:5 and resized. ChatGPT's portrait
  output is already close to 4:5 and loses almost nothing. A 2:3 image loses
  about a sixth off the top and bottom, and the run summary says "check the
  edges".
- **Sloppy names.** `gta-2026-10-07.jpg.png`, `gta-2026-10-07 (1).png`,
  `GTA-2026-10-07.PNG` and plain `2026-10-07.png` all work.

### What to know

- **Re-uploading replaces.** A new upload for a day always wins over the card
  already there, so that is how you swap an image.
- **A name with no date is left alone.** `ChatGPT Image Oct 3, 2026….png`
  could be for any day, so the workflow doesn't guess. The run goes red and
  its summary names the file. Delete it and upload it again with the right
  name.
- **A red run emails you.** Open it from the Actions tab; the summary at the
  top says what needs a look. It still converts everything it can.
- **You can run it by hand** from Actions → Convert cards → Run workflow if a
  card ever looks wrong. It re-checks every card and only touches the broken
  ones.

To batch-convert on your own machine instead, `publish/import_cards.py` in the
main repo makes byte-identical cards. `tools/convert_cards.py` here works too:

```bash
python3 tools/convert_cards.py            # dry run
python3 tools/convert_cards.py --apply
```
