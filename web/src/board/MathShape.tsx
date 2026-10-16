import katex from 'katex'
import 'katex/dist/katex.min.css'
import { useEffect, useMemo, useRef } from 'react'
import {
  BaseBoxShapeUtil,
  DefaultColorStyle,
  HTMLContainer,
  T,
  useEditor,
  useIsEditing,
  type RecordProps,
  type TLDefaultColorStyle,
  type TLShape,
} from 'tldraw'

const MATH_TYPE = 'math'

declare module 'tldraw' {
  export interface TLGlobalShapePropsMap {
    [MATH_TYPE]: { w: number; h: number; latex: string; color: TLDefaultColorStyle }
  }
}

export type MathShape = TLShape<typeof MATH_TYPE>

const INK: Record<string, string> = {
  black: 'var(--cb-ink)',
  grey: '#9fa8b2',
  blue: '#4465e9',
  'light-blue': '#4ba1f1',
  green: '#099268',
  'light-green': '#4cb05e',
  red: '#e03131',
  'light-red': '#f87777',
  orange: '#e16919',
  yellow: '#f1ac4b',
  violet: '#ae3ec9',
  'light-violet': '#e085f4',
  white: '#ffffff',
}

function MathView({ shape }: { shape: MathShape }) {
  const editing = useIsEditing(shape.id)
  const html = useMemo(
    () =>
      katex.renderToString(shape.props.latex || '\\square', {
        throwOnError: false,
        displayMode: true,
      }),
    [shape.props.latex],
  )
  return (
    <HTMLContainer
      className="cb-math"
      style={{
        width: shape.props.w,
        height: shape.props.h,
        color: INK[shape.props.color],
        // Scale the formula with its box so it lines up with the handwriting underneath.
        fontSize: Math.max(14, shape.props.h * 0.42),
      }}
    >
      {editing ? (
        <MathInput shape={shape} />
      ) : (
        <div className="cb-math-render" dangerouslySetInnerHTML={{ __html: html }} />
      )}
    </HTMLContainer>
  )
}

function MathInput({ shape }: { shape: MathShape }) {
  // Editing happens in a plain LaTeX textarea; KaTeX renders it again when editing ends.
  const editor = useEditor()
  const ref = useRef<HTMLTextAreaElement>(null)
  useEffect(() => {
    // The canvas reclaims focus at the end of the double-click; take it back afterwards.
    const t = window.setTimeout(() => {
      ref.current?.focus()
      ref.current?.select()
    }, 0)
    return () => window.clearTimeout(t)
  }, [])
  return (
    <textarea
      ref={ref}
      className="cb-math-input"
      defaultValue={shape.props.latex}
      onPointerDown={(e) => e.stopPropagation()}
      onKeyDown={(e) => {
        if (e.key !== 'Escape') e.stopPropagation()
      }}
      onChange={(e) =>
        editor.updateShape<MathShape>({
          id: shape.id,
          type: MATH_TYPE,
          props: { latex: e.target.value },
        })
      }
    />
  )
}

export class MathShapeUtil extends BaseBoxShapeUtil<MathShape> {
  static override type = MATH_TYPE
  static override props: RecordProps<MathShape> = {
    w: T.number,
    h: T.number,
    latex: T.string,
    color: DefaultColorStyle,
  }

  getDefaultProps(): MathShape['props'] {
    return { w: 240, h: 80, latex: 'a^2 + b^2 = c^2', color: 'black' }
  }

  override canEdit() {
    return true
  }

  component(shape: MathShape) {
    return <MathView shape={shape} />
  }

  getIndicatorPath(shape: MathShape) {
    const path = new Path2D()
    path.rect(0, 0, shape.props.w, shape.props.h)
    return path
  }
}
