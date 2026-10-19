import {
  AssetRecordType,
  b64Vecs,
  createShapeId,
  getIndices,
  toRichText,
  type Editor,
  type TLArrowBinding,
  type TLAssetId,
  type TLBindingCreate,
  type TLShapeId,
  type TLShapePartial,
} from 'tldraw'
import type { Arrowhead, Board, Pt, SceneElement } from '../api'

/** Marks the locked background image so the UI can find and toggle it. */
export const ORIGINAL_META = { chalkback: 'original' }

const FILES = '/files/'
const S_FONT_PX = 18 // tldraw font size "s"
const LINE_HEIGHT = 1.35

type Ctx = {
  ids: Map<string, TLShapeId>
  originalAsset: TLAssetId | null
  board: Board
}

/** tldraw rotates around a shape's top-left corner; scenes rotate around the center. */
function placed(x: number, y: number, w: number, h: number, degrees: number) {
  if (!degrees) return { x, y, rotation: 0 }
  const r = (degrees * Math.PI) / 180
  const cx = x + w / 2
  const cy = y + h / 2
  return {
    x: cx - (w / 2) * Math.cos(r) + (h / 2) * Math.sin(r),
    y: cy - (w / 2) * Math.sin(r) - (h / 2) * Math.cos(r),
    rotation: r,
  }
}

function idFor(el: SceneElement, ctx: Ctx): TLShapeId {
  const id = createShapeId()
  if (el.id && !ctx.ids.has(el.id)) ctx.ids.set(el.id, id)
  return id
}

const head = (h: Arrowhead | undefined) => (h === 'triangle' ? 'triangle' : (h ?? 'none'))

function elementToShape(el: SceneElement, ctx: Ctx): TLShapePartial | null {
  const id = idFor(el, ctx)
  switch (el.kind) {
    case 'text': {
      const scale = el.scale || 1
      // Vertically center the text in its box, as draw.io does.
      const lines = el.text.split('\n').length
      const textH = lines * S_FONT_PX * LINE_HEIGHT * scale
      const dy = el.h > textH ? (el.h - textH) / 2 : 0
      return {
        id,
        type: 'text',
        ...placed(el.x, el.y + dy, el.w, Math.min(el.h || textH, textH), el.rotation),
        props: {
          richText: toRichText(el.text),
          color: el.color,
          size: el.font === 'sans' ? 's' : el.size,
          font: el.font,
          textAlign: el.align,
          // Unwrapped, left-aligned text keeps its own lines (AI text); boxes wrap (draw.io).
          autoSize: !el.wrap && el.align === 'start',
          w: Math.max(el.w / scale, 8),
          scale,
        },
      }
    }
    case 'code': {
      const scale = el.scale || 1
      return {
        id,
        type: 'text',
        x: el.x,
        y: el.y,
        props: {
          richText: toRichText(el.text),
          color: el.color,
          size: 's',
          font: 'mono',
          textAlign: 'start',
          autoSize: true, // code keeps its own line breaks
          w: Math.max(el.w / scale, 8),
          scale,
        },
      }
    }
    case 'math':
      return {
        id,
        type: 'math',
        ...placed(el.x, el.y, el.w, el.h, el.rotation),
        props: { latex: el.latex, color: el.color, w: Math.max(el.w, 40), h: Math.max(el.h, 24) },
      }
    case 'geo':
      return {
        id,
        type: 'geo',
        ...placed(el.x, el.y, el.w, el.h, el.rotation),
        props: {
          geo: el.geo as never,
          w: Math.max(el.w, 1),
          h: Math.max(el.h, 1),
          color: el.color,
          labelColor: el.label_color ?? 'black',
          fill: el.fill,
          dash: el.dash,
          font: el.font,
          size: el.size,
          align: el.align,
          verticalAlign: el.valign,
          scale: el.scale || 1,
          richText: toRichText(el.label),
        },
      }
    case 'note': {
      // Miro-style sticker: a flat colored square whose text fills it, readable even when
      // the sticker is small (tldraw's own notes shrink their text with the note).
      const side = Math.max(el.w, 8)
      const textLines = el.text.split('\n')
      const longest = Math.max(1, ...textLines.map((l) => l.length))
      const lines = textLines.length
      // tldraw pads geo labels by LABEL_PAD (scaled) on each side; fit text inside that.
      const LABEL_PAD = 16
      const scale =
        0.95 *
        Math.min(
          (side * 0.4) / S_FONT_PX,
          side / (longest * 0.62 * S_FONT_PX + 2 * LABEL_PAD),
          side / (lines * LINE_HEIGHT * S_FONT_PX + 2 * LABEL_PAD),
        )
      return {
        id,
        type: 'geo',
        x: el.x,
        y: el.y,
        props: {
          geo: 'rectangle',
          w: side,
          h: side,
          color: el.color,
          labelColor: 'black',
          fill: 'solid',
          font: el.font,
          size: 's',
          scale: Math.max(scale, 0.05),
          richText: toRichText(el.text),
        },
      }
    }
    case 'connector':
    case 'arrow': {
      const dx = el.x2 - el.x1
      const dy = el.y2 - el.y1
      const length = Math.hypot(dx, dy)
      return {
        id,
        type: 'arrow',
        x: el.x1,
        y: el.y1,
        props: {
          kind: el.route === 'elbow' ? 'elbow' : 'arc',
          start: { x: 0, y: 0 },
          end: { x: dx, y: dy },
          bend: el.route === 'curved' ? el.bend || length * 0.2 : 0,
          arrowheadStart: head(el.start_head),
          arrowheadEnd: head(el.end_head ?? 'arrow'),
          color: el.color,
          dash: el.dash ?? 'solid',
          scale: el.scale || 1,
          richText: toRichText(el.label ?? ''),
        },
      }
    }
    case 'draw': {
      if (el.points.length < 2) return null
      const [origin] = el.points
      const rel = el.points.map((p: Pt) => ({ x: p.x - origin.x, y: p.y - origin.y }))
      if (el.freehand) {
        return {
          id,
          type: 'draw',
          x: origin.x,
          y: origin.y,
          props: {
            segments: [{ type: 'free', path: b64Vecs.encodePoints(rel.map((p) => ({ ...p, z: 0.5 }))) }],
            color: el.color,
            size: el.size,
            isComplete: true,
            isClosed: el.closed || el.filled,
            // A filled outline is how draw.io stores pen ink.
            fill: el.filled ? 'fill' : 'none',
          },
        }
      }
      const indices = getIndices(rel.length)
      const points = Object.fromEntries(
        rel.map((p, i) => [`p${i}`, { id: `p${i}`, index: indices[i], x: p.x, y: p.y }]),
      )
      return {
        id,
        type: 'line',
        x: origin.x,
        y: origin.y,
        props: { points, color: el.color, size: el.size, spline: rel.length > 3 ? 'cubic' : 'line' },
      }
    }
    case 'image': {
      const { board } = ctx
      if (el.crop && ctx.originalAsset && board.width && board.height) {
        return {
          id,
          type: 'image',
          x: el.x,
          y: el.y,
          props: {
            assetId: ctx.originalAsset,
            w: el.w,
            h: el.h,
            altText: el.alt,
            crop: {
              topLeft: { x: el.crop.x / board.width, y: el.crop.y / board.height },
              bottomRight: {
                x: (el.crop.x + el.crop.w) / board.width,
                y: (el.crop.y + el.crop.h) / board.height,
              },
            },
          },
        }
      }
      if (!el.file) return null
      return { id, type: 'image', x: el.x, y: el.y, props: { w: el.w, h: el.h, altText: el.alt } }
    }
    case 'frame':
      return { id, type: 'frame', x: el.x, y: el.y, props: { w: el.w, h: el.h, name: el.name } }
  }
}

function imageAsset(editor: Editor, src: string, w: number, h: number, meta = {}): TLAssetId {
  const id: TLAssetId = AssetRecordType.createId()
  editor.createAssets([
    {
      id,
      typeName: 'asset',
      type: 'image',
      meta,
      props: { name: src.split('/').pop() ?? 'image.png', src, w, h, mimeType: 'image/png', isAnimated: false },
    },
  ])
  return id
}

/** Build a fresh board: the original image (if any) as a locked layer, scene shapes on top,
 * then the connector bindings that keep arrows attached when shapes are moved. */
export function buildBoard(editor: Editor, board: Board) {
  const shapes: TLShapePartial[] = []
  const ctx: Ctx = { ids: new Map(), originalAsset: null, board }
  if (board.image_url) {
    ctx.originalAsset = imageAsset(editor, board.image_url, board.width, board.height, ORIGINAL_META)
    shapes.push({
      id: createShapeId(),
      type: 'image',
      x: 0,
      y: 0,
      isLocked: true,
      opacity: 0.35,
      meta: ORIGINAL_META,
      props: { assetId: ctx.originalAsset, w: board.width, h: board.height },
    })
  }
  const elements = board.scene?.elements ?? []
  for (const el of elements) {
    const shape = elementToShape(el, ctx)
    if (!shape) continue
    if (el.opacity < 1) shape.opacity = el.opacity
    if (el.kind === 'image' && el.file && !el.crop) {
      shape.props = { ...shape.props, assetId: imageAsset(editor, FILES + el.file, el.w, el.h) }
    }
    shapes.push(shape)
  }

  const bindings: TLBindingCreate<TLArrowBinding>[] = []
  for (const el of elements) {
    if (el.kind !== 'connector' && el.kind !== 'arrow') continue
    const arrowId = el.id ? ctx.ids.get(el.id) : undefined
    if (!arrowId) continue
    for (const [terminal, target, anchor] of [
      ['start', el.from_id, el.from_anchor],
      ['end', el.to_id, el.to_anchor],
    ] as const) {
      const toId = target ? ctx.ids.get(target) : undefined
      if (!toId) continue
      bindings.push({
        type: 'arrow',
        fromId: arrowId,
        toId,
        props: {
          terminal,
          normalizedAnchor: anchor ?? { x: 0.5, y: 0.5 },
          isPrecise: !!anchor,
          isExact: false,
          snap: 'none',
        },
      })
    }
  }

  editor.run(() => {
    editor.createShapes(shapes)
    if (bindings.length) editor.createBindings(bindings)
  })
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
