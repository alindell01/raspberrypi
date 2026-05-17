# Sabres Theme Logos

Drop image files here and they'll be picked up automatically when the
matching theme is active for the Buffalo Sabres.

## Expected files

| Theme                         | Filename (tried in order)                   |
|-------------------------------|---------------------------------------------|
| Sabres Goathead (black & red) | `goathead.svg`, then `goathead.png`         |
| Sabres Slug (red & silver)    | `slug.svg`, then `slug.png`                 |

If none of these are found, the scoreboard falls back to the modern
buffalo-head logo the NHL API returns. No app restart needed —
just drop the file in, hard-refresh the browser, and pick the matching
theme in the picker.

## Image tips

- **Transparent background.** PNG or SVG with alpha channel.
- **SVG is preferred** (scales crisply at any TV size). PNG works too;
  ~512×512 is a safe size for the scoreboard's logo slot.
- The logo only swaps for the away/home team panel where `abbrev == BUF`.
  The opponent always uses the NHL API logo.
