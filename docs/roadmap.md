# Roadmap

## Waiting on the owner

- [x] **GitHub repository + `gh` CLI.** See [Built on autopilot](autopilot.md). This enables real pull requests, AI review, auto-merge and
  GitHub releases.
- [ ] **Claude API key + budget.** Key received and verified; held back until the AI step is worth
  spending on (draw.io boards need no AI at all).
- [x] **Real board material.** 13 draw.io boards (imported exactly) and Miro screenshots
  (programming, math, electronics, databases; Serbian Cyrillic and Latin).
- [ ] **Hetzner server + domain.** First production deploy (see [Deployment](deployment.md)).
- [ ] **tldraw license.** Decide on a production license key vs. the watermarked option.

## Next up

- [ ] Alembic migrations (required before real data in production)
- [ ] Evaluate AI reconstruction on the Miro screenshots, once the budget is released
- [ ] Telegram `/start <code>` deep-link to connect students without copying chat IDs
- [ ] Evaluate reconstruction quality on real boards. Build a small eval set and tune effort
- [ ] Per-lesson "ask about this lesson" chat for students, grounded in the boards
- [ ] Spaced repetition: a second reminder a week later with a mini quiz
- [ ] Teacher-side bulk import of a whole term of boards
