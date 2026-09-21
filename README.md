# gta-media
Image host for Gardening Tips Australia

## How cards get here

One image per post, in `cards/`, named after the post id:

```
cards/gta-2026-09-21.jpg
cards/gta-2026-09-22.jpg
```

**1080 × 1350, JPEG.** Instagram fetches media from a URL rather than accepting
uploaded bytes, which is why this repo is public and served over Pages.

Don't rename or resize by hand. Download the images from ChatGPT in run-sheet
order, leave the names alone, and run the importer in the main repo:

```bash
python3 publish/import_cards.py ~/Downloads --to ../gta-media/cards
python3 publish/import_cards.py ~/Downloads --to ../gta-media/cards --apply
```

First run is a dry run that prints the mapping — read it before applying. It
maps onto the next posts without a card, starting today; pass `--start` to
backfill a specific date.
