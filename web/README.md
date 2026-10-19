# Chalkback web

React + Vite + TypeScript + [tldraw](https://tldraw.dev) app.

```bash
npm install
npm run dev        # http://localhost:5173 (proxies /api and /files to :8000)
npm run build      # typecheck + production build into dist/
```

## How a board is built

`src/board/sceneToShapes.ts` turns the scene returned by the API (see `api/app/scene.py`) into
tldraw shapes: text, code, KaTeX math (`src/board/MathShape.tsx`, double-click to edit LaTeX),
geo shapes, sticky notes, arrows, pen ink and lines, images, cut-outs of the original photo, and
frames. Connectors are then bound to the shapes they attach to, so they follow when shapes move.

After the first edit the full tldraw snapshot is autosaved to the API and loaded from then on.
In dev builds the editor is available as `window.editor` for debugging.
