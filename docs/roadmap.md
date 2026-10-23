# Roadmap

## Waiting on the owner

- [x] **GitHub repository + `gh` CLI.** See [Built on autopilot](autopilot.md). This enables real pull requests, AI review, auto-merge and
  GitHub releases.
- [ ] **Claude API key + budget.** Key received and verified; held back until the AI step is worth
  spending on (draw.io boards need no AI at all).
- [x] **Real board material.** 13 draw.io boards (imported exactly) and Miro screenshots
  (programming, math, electronics, databases; Serbian Cyrillic and Latin).
- [x] **Hetzner server.** Provisioned and deployed with Ansible (see [Deployment](deployment.md)).
- [x] **Domain.** Live at <https://chalkback.xyz> (DNS on Cloudflare, proxied).
- [x] **tldraw license.** 100-day evaluation key, live on chalkback.xyz. **Expires 2027-01-29**:
  decide on a commercial or hobby (watermarked) license before then.

## Next up

- [x] Alembic migrations (required before real data in production)
- [x] First AI reconstruction test on the two Miro screenshots ($0.37)
- [ ] Re-check that regions no longer overlap transcribed text (prompt rule added, unverified)
- [x] Telegram `/start <code>` deep-link to connect students without copying chat IDs
- [ ] Evaluate reconstruction quality on real boards. Build a small eval set and tune effort
- [ ] Per-lesson "ask about this lesson" chat for students, grounded in the boards
- [ ] Spaced repetition: a second reminder a week later with a mini quiz
- [ ] Teacher-side bulk import of a whole term of boards
