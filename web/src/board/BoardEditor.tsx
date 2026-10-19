import { useRef, useState } from 'react'
import { Tldraw, getSnapshot, loadSnapshot, type Editor, type TLEditorSnapshot } from 'tldraw'
import 'tldraw/tldraw.css'
import { api, type Board } from '../api'
import { MathShapeUtil } from './MathShape'
import { buildBoard, refreshOriginalAsset, setOriginalOpacity } from './sceneToShapes'

const shapeUtils = [MathShapeUtil]
const SAVE_DELAY_MS = 1200
const LICENSE_KEY = import.meta.env.VITE_TLDRAW_LICENSE_KEY as string | undefined
const SAVE_LABEL = {
  saved: 'Saved',
  dirty: 'Unsaved changes',
  saving: 'Saving…',
  error: 'Save failed',
} as const

export function BoardEditor({ board }: { board: Board }) {
  const editorRef = useRef<Editor | null>(null)
  const [save, setSave] = useState<keyof typeof SAVE_LABEL>('saved')
  const [opacity, setOpacity] = useState(0.35)

  const onMount = (editor: Editor) => {
    editorRef.current = editor
    // Dev builds expose the editor for debugging and visual checks from the console.
    if (import.meta.env.DEV) (window as unknown as { editor: Editor }).editor = editor
    if (board.snapshot) {
      loadSnapshot(editor.store, board.snapshot as Partial<TLEditorSnapshot>)
      refreshOriginalAsset(editor, board)
    } else if (editor.getCurrentPageShapeIds().size === 0) {
      // onMount can run twice for the same store (React StrictMode); build only once.
      buildBoard(editor, board)
    }
    editor.zoomToFit({ animation: { duration: 0 } })

    // Debounced autosave of user edits to the document.
    let timer: number | undefined
    const unlisten = editor.store.listen(
      () => {
        setSave('dirty')
        window.clearTimeout(timer)
        timer = window.setTimeout(async () => {
          setSave('saving')
          try {
            await api.saveSnapshot(board.id, getSnapshot(editor.store))
            setSave('saved')
          } catch {
            setSave('error')
          }
        }, SAVE_DELAY_MS)
      },
      { source: 'user', scope: 'document' },
    )
    return () => {
      window.clearTimeout(timer)
      unlisten()
    }
  }

  const changeOpacity = (value: number) => {
    setOpacity(value)
    if (editorRef.current) setOriginalOpacity(editorRef.current, value)
  }

  return (
    <div className="cb-board">
      <div className="cb-board-toolbar">
        {board.image_url && (
          <label className="cb-opacity">
            Original photo
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={opacity}
              onChange={(e) => changeOpacity(Number(e.target.value))}
            />
          </label>
        )}
        <span className={`cb-save cb-save-${save}`}>{SAVE_LABEL[save]}</span>
      </div>
      <div className="cb-board-canvas">
        <Tldraw key={board.id} shapeUtils={shapeUtils} onMount={onMount} licenseKey={LICENSE_KEY} />
      </div>
    </div>
  )
}
