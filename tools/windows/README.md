# The D:\gta-media dropper (Windows)

Drop PNGs into `D:\gta-media`. Within five minutes they are on GitHub, and
the Convert cards workflow turns them into the cards Instagram needs.

## Set up once

1. Make a GitHub token: github.com → Settings → Developer settings →
   Personal access tokens → **Fine-grained tokens** → Generate new token.
   - Expiration: up to a year. Put the date in your calendar.
   - Repository access: **Only select repositories** → `chanhofai/gta-media`
   - Permissions → Repository → **Contents: Read and write**
   - Generate, and copy it.
2. Unzip this folder anywhere and double-click **install.bat**. If Windows
   says it protected your PC, click *More info* → *Run anyway*.
3. Paste the token when asked. It won't show while you paste. That's normal.

The token is stored encrypted for your Windows account only (Windows DPAPI).
Don't paste it anywhere else, including chat.

## Every day after that

- Drop images named like `gta-2026-11-07.png` (and carousel slides like
  `gta-2026-11-06-2.png`) straight into `D:\gta-media`, not a subfolder.
- Every five minutes, anything new goes up in one batch and moves into
  `D:\gta-media\uploaded`. Files there are deleted after 30 days.
- `D:\gta-media\upload-log.txt` says what went up, and why if something
  didn't.
- It only runs while you're logged in to the PC.

## When something goes wrong

| Log says | Do this |
|---|---|
| `GitHub rejected the token` | The token expired. Make a new one and run install.bat again. |
| `GitHub said 403` or `404` | The token is missing Contents: Read and write on gta-media. Make a new one. |
| `SKIPPED … over GitHub's limit` | Over 95 MB. Open it and save it as a JPG. |
| Nothing at all | Open Task Scheduler and look for **GTA card uploader**. Run install.bat again if it's not there. |

To stop it, double-click **uninstall.bat**. Your images are left alone.
