# Architecture Overview

High-level description of how PDFree is structured, how modules relate to each other, and how data flows through the system.

---

## Module Map

```
PDFree/
├── main.py               # App entry point, home dashboard, tool router
├── library_page.py       # Document library (files, folders, favorites, trash)
├── view_tool.py          # PDF viewer + full annotation suite
├── split_tool.py         # PDF splitter with visual cut-line preview
├── excerpt_tool.py       # Multi-PDF region capture → new PDF
├── pdf_to_csv_tool.py    # Table extraction → CSV files
├── utils.py              # Shared Qt + fitz helpers
├── colors.py             # Central color palette
├── icons.py              # Lucide SVG icon library
└── docs/
    ├── PR_STANDARDS.md
    ├── DESIGN_STANDARDS.md
    └── project-state/
        ├── FEATURES.md   # (this file's companion)
        └── ARCHITECTURE.md
```

---

## Application Layers

```
┌─────────────────────────────────────────────────────┐
│                      main.py                        │
│   PDFreeApp (QMainWindow)                           │
│   Home screen / tool browser / navigation shell    │
│   Dynamic tool loading  ·  Unsaved-changes guard   │
└──────────┬──────────────────────────────────────────┘
           │ instantiates on demand
     ┌─────┴────────────────────────────────────┐
     │           Tool Widgets (QWidget)          │
     │  view_tool  │  split_tool  │ excerpt_tool │
     │  pdf_to_csv_tool  │  library_page         │
     └─────────────────────────────────────────┘
           │ all share
     ┌─────┴────────────────────────────────────┐
     │           Shared Infrastructure           │
     │   utils.py  ·  colors.py  ·  icons.py    │
     └──────────────────────────────────────────┘
           │ all use
     ┌─────┴────────────────────────────────────┐
     │              PDF Backends                 │
     │  fitz (PyMuPDF)  ·  pypdf  ·  pdfplumber │
     └──────────────────────────────────────────┘
```

---

## main.py — App Shell

`PDFreeApp` owns the application window and the single `QStackedWidget` that holds either the home screen (index 0) or an active tool (index 1).

### Tool lifecycle
1. User clicks a `ToolCard` → `_open_tool(tool_id)` is called.
2. If a tool is already active and `_has_unsaved_changes()` is True, the user is prompted to Save / Discard / Cancel.
3. The target module is imported dynamically (`importlib`) and a new widget is instantiated.
4. The widget is added to the stacked widget and made visible.
5. On back navigation, `cleanup()` is called on the tool (closes fitz documents, frees resources).

### Home screen regions
```
┌─────────────────────────────────────────────────────┐
│  Header bar (search · tab filter)                   │
├──────────┬──────────────────────────────────────────┤
│  Sidebar │  Hero banner (recent PDF)                │
│  (nav /  │  Quick-Start drop zone                   │
│  recent  │  Tool grid  (filtered by tab + search)   │
│  tools)  │                                          │
└──────────┴──────────────────────────────────────────┘
```

### Tool discovery
Tools are defined in `CATEGORIES` (list of category dicts with title, color, tools list). `IMPLEMENTED` is a set of tool IDs that are currently active. Unimplemented tools render disabled. `TOOL_DESCRIPTIONS` maps tool ID → one-line description shown on the card.

---

## library_page.py — Document Library

`LibraryState` is a JSON-backed data store that tracks every PDF the user has interacted with. It is a plain Python class (not a Qt object) and is instantiated by `main.py` as a persistent singleton.

### Persistence
State is stored at `~/.pdfree/library.json` (path overridable via `PDFREE_STATE_DIR`). Writes are deferred with a 1 s `QTimer` to batch rapid changes.

### Data model (library.json)
```json
{
  "files": {
    "/path/to/file.pdf": {
      "name": "file.pdf",
      "path": "/path/to/file.pdf",
      "last_opened": "2026-03-15T10:00:00Z",
      "favorite": false,
      "trashed": false
    }
  },
  "folders": {
    "/path/to/folder": {
      "color": "#3B82F6"
    }
  }
}
```

### Relationship to other modules
`library_page.py` is loaded as a tool widget just like `view_tool` or `split_tool`. It does not directly call other tools — it emits `open_req(path)` which main.py handles to open the appropriate tool with that file pre-loaded.

---

## Tool Widgets — Common Structure

Every tool (view_tool, split_tool, excerpt_tool, pdf_to_csv_tool) follows the same structural contract:

```
QWidget (tool root)
├── Back button           (_make_back_button from utils)
├── Left panel            (settings / controls)
│   └── File drop zone or browse entry
├── Right panel / canvas  (PDF page rendering)
│   ├── PDFCanvas or _PreviewCanvas
│   └── Navigation bar
└── Bottom thumbnail strip (optional, horizontal scroll)
```

### Required interface (used by main.py)
| Attribute / Method | Purpose |
|---|---|
| `_modified: bool` | True if there are unsaved changes |
| `cleanup()` | Called before widget is destroyed; closes fitz docs |

Not all tools implement both — only ViewTool and ExcerptTool set `_modified`. SplitTool and PDFtoCSVTool write directly to disk and do not track unsaved state.

---

## PDF Rendering Pipeline

All tools render PDF pages using the same pipeline:

```
fitz.Document.load_page(n)
  └── fitz.Page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        └── utils._fitz_pix_to_qpixmap(pix)  →  QPixmap
              └── QLabel.setPixmap() or QPainter.drawPixmap()
```

### Zoom mechanics
- Zoom factor is a float multiplier (1.0 = 72 dpi, 2.0 = 144 dpi, etc.).
- ViewTool also supports two sentinel values: `FIT_PAGE = -1.0` and `FIT_WIDTH = -2.0` which compute the real zoom from widget dimensions at render time.
- All tools re-render on resize if using fit modes.

### Rotation
Rotation is expressed in degrees (0, 90, 180, 270) and passed as `rotate=` to `fitz.Page.get_pixmap()`.

---

## Annotation System (view_tool.py)

The annotation system lives entirely in `view_tool.py` and is built on top of PyMuPDF's annotation API.

```
User mouse event
  └── PDFCanvas.mousePressEvent / mouseMoveEvent / mouseReleaseEvent
        └── ViewTool._on_mouse_down / _on_mouse_move / _on_mouse_up
              └── fitz.Page.add_*_annot(rect_or_points, ...)
                    └── undo stack: copy of page annot state pushed to _undo_stack
                          └── ViewTool._undo() / _redo() restores state
```

### Undo/redo model
Undo captures a snapshot of the annotation list before each change. `MAX_UNDO = 30` steps are retained. The stack is per-document and is cleared when a different document is activated.

### Form fields
Detected via `fitz.Page.widgets()`. Qt widgets are overlaid at the correct PDF-coordinate positions using the page-to-widget coordinate transform. Changes are written back to the fitz widget on focus-out.

---

## Shared Infrastructure Details

### colors.py
Pure constant module. No classes or functions. All modules import directly:
```python
from colors import BLUE, G200, RED_HOVER, BRAND, ...
```

### icons.py
Renders Lucide SVG paths to QPixmap/QIcon at runtime. Caches by `(name, color, size)` tuple in a module-level dict. All icons use the same SVG template (stroke-only, `stroke-width="2"`, `fill="none"`).

```python
svg_pixmap("scissors", "#3B82F6", 22)  # → QPixmap
svg_icon("upload", "#FFFFFF", 15)      # → QIcon
```

### utils.py
Three exports:
- `_fitz_pix_to_qpixmap(pix)` — converts fitz.Pixmap to QPixmap
- `_make_back_button(text, callback, color)` — factory for the standard back nav button
- `_WheelToHScroll(QObject)` — event filter for thumbnail strips

---

## Data Flow Diagrams

### Opening a file from Quick-Start
```
QuickStartZone.file_selected(path)
  └── PDFreeApp._on_quick_start(path)
        └── library_page.LibraryState.track(path)
        └── _open_tool("view")
              └── ViewTool.__init__()
              └── ViewTool.load_file(path)
```

### Capturing an excerpt region
```
ExcerptCanvas.mouseReleaseEvent(pos)
  └── ExcerptTool._do_capture(crop_rect)
        ├── fitz.show_pdf_page(output_page, source_page, clip=crop_rect)
        ├── Snippet(source_path, page_index, crop_rect, thumbnail)
        └── left panel snippet list refreshed
              └── ExcerptTool._save_excerpt() [on button click]
                    └── output_doc.save(path)
```

### Splitting a PDF
```
SplitTool._split_pdf()
  └── _parse_ranges(range_string) → list[list[int]]
        └── for each range:
              pypdf.PdfWriter.add_page(reader.pages[n])
              PdfWriter.write(output_path % part_number)
```

### Extracting tables to CSV
```
PDFtoCSVTool._run_extraction()
  └── pdfplumber.open(pdf_path)
        └── for each page in range:
              page.find_tables(settings) → tables
              for each table:
                apply filters (min rows/cols)
                normalize cells (unicode, linebreaks, types)
                csv.DictWriter.writerows(rows)
```

---

## Threading Model

All PDF rendering and IO is currently done on the main Qt thread. Heavy operations (large PDFs, slow extraction) can block the UI. The existing pattern to be followed for any new async work:

- Use `QThread` or `QRunnable` for rendering or IO.
- Never update Qt widgets from a non-main thread — use signals/slots.
- Thumbnail generation in view_tool and split_tool uses `QTimer.singleShot(0, ...)` for deferred (but still main-thread) rendering to keep the UI responsive on first load.

---

## External Dependencies

| Library | Used by | Purpose |
|---|---|---|
| `PySide6` | all modules | GUI framework |
| `fitz` (PyMuPDF) | view_tool, split_tool, excerpt_tool, pdf_to_csv_tool, library_page (page count) | PDF rendering, annotation, text search |
| `pypdf` | split_tool | Page-accurate PDF splitting/writing |
| `pdfplumber` | pdf_to_csv_tool | Table detection and extraction |
| `json` | library_page | Library state persistence |
| `pathlib` | library_page, excerpt_tool | Cross-platform path handling |
| `csv` | pdf_to_csv_tool | CSV writing |
| `unicodedata` | pdf_to_csv_tool | Unicode normalization |
| `subprocess` | view_tool, library_page, pdf_to_csv_tool | System print dialog; open in Explorer |
| `tempfile` | view_tool | Signature PNG export |

---

## Key Design Decisions

**Single-file tools.** Each tool is one `.py` file that contains all its UI, logic, and state. This keeps related code co-located and avoids import tangles, at the cost of large files.

**No global state between tools.** Tools do not call each other. Communication goes through main.py signals or the shared `LibraryState`. This makes each tool independently testable.

**fitz as primary PDF engine.** PyMuPDF is used for all rendering, annotation, and text search. pypdf is used only in split_tool where its page-level write API gives more reliable output than fitz's incremental save for split workflows. pdfplumber wraps fitz for table detection.

**colors.py and icons.py as pure infrastructure.** Neither has side effects on import. All styling flows through these two modules — no inline hex literals in tool code except for locally scoped constants.
