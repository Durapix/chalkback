import {
  AssetRecordType,
  createShapeId,
  getIndices,
  toRichText,
  type Editor,
  type TLAssetId,
  type TLShapeId,
  type TLShapePartial,
} from 'tldraw'
import type { Board, SceneElement } from '../api'

/** Marks the locked background image so the UI can find and toggle it. */
export const ORIGINAL_META = { chalkback: 'original' }

function elementToShape(el: SceneElement): TLShapePartial | null {
  const id = createShapeId()
  switch (el.kind) {
    case 'text':
      return {
        id,
        type: 'text',
        x: el.x,
        y: el.y,
        props: {
          richText: toRichText(el.text),
          color: el.color,
          size: el.size,
          font: 'draw',
          autoSize: false,
          w: Math.max(el.w, 40),
        },
      }
    case 'math':
      return {
        id,
        type: 'math',
        x: el.x,
        y: el.y,
        props: { latex: el.latex, color: el.color, w: Math.max(el.w, 40), h: Math.max(el.h, 24) },
      }
    case 'geo':
      return {
        id,
        type: 'geo',
        x: el.x,
        y: el.y,
        props: {
          geo: el.geo,
          w: Math.max(el.w, 8),
          h: Math.max(el.h, 8),
          color: el.color,
          fill: 'none',
          richText: toRichText(el.label),
        },
      }
    case 'arrow':
      return {
        id,
        type: 'arrow',
        x: el.x1,
        y: el.y1,
        props: {
          start: { x: 0, y: 0 },
          end: { x: el.x2 - el.x1, y: el.y2 - el.y1 },
          color: el.color,
          richText: toRichText(el.label),
        },
      }
    case 'draw': {
      if (el.points.length < 2) return null
      const [origin] = el.points
      const indices = getIndices(el.points.length)
      const points = Object.fromEntries(
        el.points.map((p, i) => {
          const pid = `p${i}`
          return [pid, { id: pid, index: indices[i], x: p.x - origin.x, y: p.y - origin.y }]
        }),
      )
      return {
        id,
        type: 'line',
        x: origin.x,
        y: origin.y,
        props: { points, color: el.color, spline: el.points.length > 3 ? 'cubic' : 'line' },
      }
    }
  }
}

/** Build a fresh board: the original image as a locked layer, AI-extracted shapes on top. */
export function buildBoard(editor: Editor, board: Board) {
  const shapes: TLShapePartial[] = []
  if (board.image_url) {
    const assetId: TLAssetId = AssetRecordType.createId()
    editor.createAssets([
      {
        id: assetId,
        typeName: 'asset',
        type: 'image',
        meta: ORIGINAL_META,
        props: {
          name: `board-${board.id}.png`,
          src: board.image_url,
          w: board.width,
          h: board.height,
          mimeType: 'image/png',
          isAnimated: false,
        },
      },
    ])
    shapes.push({
      id: createShapeId(),
      type: 'image',
      x: 0,
      y: 0,
      isLocked: true,
      opacity: 0.35,
      meta: ORIGINAL_META,
      props: { assetId, w: board.width, h: board.height },
    })
  }
  for (const el of board.scene?.elements ?? []) {
    const shape = elementToShape(el)
    if (shape) shapes.push(shape)
  }
  editor.run(() => editor.createShapes(shapes))
}

/** Saved snapshots keep asset URLs; point the original image at the current URL. */
export function refreshOriginalAsset(editor: Editor, board: Board) {
  if (!board.image_url) return
  const stale = editor
    .getAssets()
    .filter((a) => a.meta.chalkback === ORIGINAL_META.chalkback && a.props.src !== board.image_url)
  if (stale.length) {
    editor.updateAssets(stale.map((a) => ({ ...a, props: { ...a.props, src: board.image_url } })))
  }
}

export function originalImageIds(editor: Editor): TLShapeId[] {
  return editor
    .getCurrentPageShapes()
    .filter((s) => s.meta.chalkback === ORIGINAL_META.chalkback)
    .map((s) => s.id)
}

export function setOriginalOpacity(editor: Editor, opacity: number) {
  const ids = originalImageIds(editor)
  editor.run(
    () => editor.updateShapes(ids.map((id) => ({ id, type: 'image', opacity }))),
    { ignoreShapeLock: true },
  )
}
