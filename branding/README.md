# Branding

The Chalkback icon: a purple board with a white stroke and a yellow dot.

| File | Use |
| --- | --- |
| `icon.svg` | Master, rounded square (same as `web/public/favicon.svg`) |
| `icon-full.svg` | Full-bleed square for circle and mask crops; the drawing stays inside the central 80% circle |
| `out/telegram-bot-512.png` | Telegram bot profile picture (BotFather `/setuserpic`) |
| `out/apple-touch-icon.png` | iPhone home screen, 180 px |
| `out/icon-192.png`, `out/icon-512.png`, `out/icon-maskable-512.png` | Android / installed app (web manifest) |
| `out/favicon.ico`, `out/favicon-32.png` | Browser tabs where SVG favicons are not supported |

Regenerate everything after changing an SVG with `branding/render.sh` (needs Docker), then copy
the files into `web/public/` and `landing/` as before.
