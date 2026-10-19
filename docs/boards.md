# Importing boards

Upload boards on a lesson page with **Upload boards**. Every file becomes one or more boards:

| What you upload | How it becomes a board | Cost |
|---|---|---|
| draw.io HTML export, `.drawio`, `.xml` | Imported **exactly**: one board per page, ready immediately | free |
| Screenshot or photo (PNG, JPEG, WebP) | Rebuilt by Claude over the original image | one AI request per image |
| PDF | One board per page, each rebuilt by Claude | one AI request per page |

## draw.io boards

The importer reads the diagram itself, not a picture of it, so nothing is guessed:

| draw.io | tldraw |
|---|---|
| Rectangles, ellipses, diamonds, triangles, trapezoids, parallelograms, hexagons, clouds | Geo shapes with the same size, colors (mapped to the nearest tldraw color) and labels |
| Text | Text, with draw.io's font size, alignment and padding |
| Connectors | Arrows **attached** to their shapes (move a box and its arrows follow); angled lines stay angled (elbow), curved stay curved; arrowheads and labels are kept |
| Free-floating arrows | Arrows at the same place |
| Tables / containers (swimlanes) and groups | Outlined containers with a header line; nested shapes keep their positions |
| Pen strokes | Real tldraw pen ink |
| Embedded PNG/JPEG images | Images |
| Faded elements (opacity) | Same opacity |

Embedded SVG images and images linked from the web are shown as dashed placeholders: they are
never downloaded or served, for safety.

The original file is stored outside the public `/files` folder. **Re-run** on a board imports it
again from that file, which is useful after importer improvements.

## Screenshots and photos (AI)

For pictures of boards (for example Miro screenshots), Claude describes what it sees using these
elements, and the app turns them into editable tldraw shapes over the original image:

| Element | Used for |
|---|---|
| `grid` | Aligned fields of sticky notes: arrays, matrices, number sieves. One grid instead of many notes keeps them aligned and keeps the request cheap |
| `note` | Single sticky notes |
| `shape` | Boxes, circles, diamonds and big hollow **block arrows** used as pointers (L, D, S) |
| `connector` | Lines and arrows; attached to the elements (or grid cells, `id:row:col`) they start and end at |
| `text` | Typed text, handwriting and **code** (monospace, indentation kept) |
| `math` | Formulas as LaTeX |
| `stroke` | Sketches, underlines, check marks, graphs |
| `region` | Dense content kept as a picture cut out of the original (pasted task statements, screenshots of other programs) |
| `frame` | Each separate part of a collage of screenshots |

Text is transcribed exactly as written (Cyrillic or Latin, mistakes included), never translated.
