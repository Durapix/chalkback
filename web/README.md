# Chalkback web

React + Vite + TypeScript + [tldraw](https://tldraw.dev) app.

```bash
npm install
npm run dev        # http://localhost:5173 (proxies /api and /files to :8000)
npm run build      # typecheck + production build into dist/
```

## How a board is built

`src/board/sceneToShapes.ts` turns the scene returned by the API into tldraw shapes:

| Scene element | tldraw shape |
|---|---|
| original image | locked `image` shape (opacity adjustable from the toolbar) |
| `text` | `text` with the hand-drawn font |
| `math` | custom `math` shape (`src/board/MathShape.tsx`) rendered with KaTeX, double-click to edit LaTeX |
| `geo` | `geo` (rectangle, ellipse, triangle, diamond) |
| `arrow` | `arrow` |
| `draw` | `line` (cubic spline when it has more than three points) |

After the first edit the full tldraw snapshot is autosaved to the API and loaded from then on.
