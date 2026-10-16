# Architecture

```mermaid
flowchart LR
  subgraph Browser
    W[React + tldraw app]
    L[Landing page]
  end
  subgraph Server["Hetzner server (Docker Compose)"]
    C[Caddy<br/>HTTPS, static files]
    A[FastAPI]
    S[(PostgreSQL)]
    F[(uploads volume)]
  end
  W -- /api --> C --> A
  L --> C
  A --> S
  A --> F
  A -- vision + structured outputs --> Claude[Claude API]
  A -- reminders --> T[Telegram Bot API]
  A -- reminders --> R[Resend]
```

## Data model

| Table | Purpose |
|---|---|
| `users` | Teachers and students. Students belong to one teacher and carry reminder settings (language, Telegram chat ID, channels, next lesson time). |
| `lessons` | One tutoring session: title, subject, time, tutor notes, AI summary and its status. |
| `boards` | One whiteboard image of a lesson: the stored PNG, AI scene, tldraw snapshot and status. |
| `reminders` | Log of every reminder attempt per channel. It is also the dedup key for scheduled reminders. |

Tables are created on startup (`Base.metadata.create_all`). Alembic migrations are on the
[roadmap](roadmap.md) before real data goes into production.

## Request flow: uploading a board

```mermaid
sequenceDiagram
  participant T as Teacher (web)
  participant A as API
  participant C as Claude
  T->>A: POST /api/lessons/{id}/boards (images / PDF)
  A->>A: normalize to PNG, one board per page
  A-->>T: 201 boards (status: pending)
  A->>C: image + system prompt, output_format=Scene
  C-->>A: validated Scene JSON
  A->>A: scale coordinates, status: ready
  T->>A: poll GET /api/lessons/{id}
  T->>A: GET /api/boards/{id} -> scene
  T->>T: build tldraw shapes, autosave snapshot
```

Background work runs in-process via FastAPI `BackgroundTasks`. Each job opens its own DB
session and records failures on the row instead of raising. A dedicated queue (Redis + arq) is
only worth it once a single server can't keep up.

## Board rendering

The scene is deliberately simpler than tldraw's own record format. The model describes **what**
is on the board and **where**, and `web/src/board/sceneToShapes.ts` maps it to shapes:

| Scene element | tldraw shape |
|---|---|
| original image | locked `image` shape, opacity adjustable |
| `text` | `text` (hand-drawn font) |
| `math` | custom `math` shape, KaTeX-rendered, LaTeX-editable |
| `geo` | `geo` |
| `arrow` | `arrow` |
| `draw` | `line` (cubic spline) |

After the first user edit, the full tldraw snapshot is stored and becomes the source of truth for
that board. Re-running reconstruction clears the snapshot and rebuilds the board from the new
scene.
