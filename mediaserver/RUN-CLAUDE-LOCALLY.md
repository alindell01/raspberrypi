# Run Claude Code locally (so it can run PowerShell on this PC)

Right now this project is often worked on through **Claude Code on the web**,
which runs in a **cloud container** connected to the GitHub repo. That cloud
shell can't touch this Windows PC — which is why setup has been done by
copy-pasting commands and screenshots back and forth.

Running Claude Code **locally on this PC** fixes that: its terminal *is* this
computer's terminal, so it runs PowerShell / Docker commands directly and reads
the output itself. No more copy-paste.

## One-time install (run on the PC, not a phone)

1. **Install Node.js** (LTS) from https://nodejs.org if you don't already have it.
2. In **PowerShell**:
   ```powershell
   npm install -g @anthropic-ai/claude-code
   ```

## Each time you want to work on the media server

```powershell
cd C:\raspberrypi\mediaserver
claude
```
Log in with your Claude account the first time. Then just ask in plain English,
e.g. "run docker compose ps" or "why won't Sonarr connect to qBittorrent" — it
runs the commands here and sees the results.

## Notes

- **Permissions:** by default Claude asks before running each command. You can
  approve per-command or loosen it so routine commands (like `docker compose ...`)
  run without a prompt every time.
- **Same repo:** the repo is already cloned at `C:\raspberrypi`, so local Claude
  Code picks up right where the web session left off. Keep them in sync with
  `git pull` / `git push`.
- **Prefer an editor?** There's also a **Claude Code VS Code extension** — same
  local-execution benefit, inside an editor instead of a bare terminal.

## Why local is the right tool for THIS project

This media server is a lot of "run this, check that, fix, re-run" loops
(Docker, drive mounts, app config). Doing those locally is far faster than the
web session, because Claude can run and read each command itself instead of
waiting for a screenshot.
