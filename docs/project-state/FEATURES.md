# Feature Catalog

Every implemented feature in PDFree. Append new features at the bottom of their module section using the same format.

---

## main.py — App Shell & Home Dashboard

### Tool Browser Grid
Displays all available tools in a filtered grid. Tabs (All Tools, Convert, Edit, Protect) and a debounced search entry narrow the visible cards. Each card shows an icon, name, and description. Unimplemented tools render in a disabled "coming soon" state.
- **Module**: main.py — `PDFreeApp._render_tool_grid()`
- **Dependencies**: `CATEGORIES`, `TOOL_DESCRIPTIONS`, `IMPLEMENTED` constants; `ToolCard`; `colors.SOON_TXT`

### Dynamic Tool Loading
When a tool card is clicked, the corresponding module is imported at runtime, instantiated, and pushed onto a `QStackedWidget`. The previous tool is cleaned up via its `cleanup()` method before switching.
- **Module**: main.py — `PDFreeApp._open_tool()`
- **Dependencies**: `view_tool`, `split_tool`, `excerpt_tool`, `pdf_to_csv_tool` modules; `QStackedWidget`

### Unsaved Changes Guard
Before navigating away from an active tool, checks a `_modified` flag on the tool widget. If set, prompts the user to Save / Discard / Cancel.
- **Module**: main.py — `PDFreeApp._has_unsaved_changes()`, `_prompt_save()`
- **Dependencies**: Any tool widget that exposes `_modified`

### Quick-Start Drop Zone
On the home screen, a dashed drag-and-drop zone accepts PDF file drops and also opens a file browser. Emits `file_selected(str)` signal when a file is chosen.
- **Module**: main.py — `QuickStartZone`
- **Dependencies**: `PDFIconWidget`; `colors.QS_BG`, `BLUE`

### Recently Used Tools
A horizontal strip of compact cards showing the last N tools the user opened, persisted in memory during the session.
- **Module**: main.py — `PDFreeApp._update_recents()`, `RecentCard`
- **Dependencies**: `TOOL_DESCRIPTIONS`; `icons`

### Category Accent Colors
Each tool category is assigned an accent color used in the hero banner and category headers.
- **Module**: main.py — `CATEGORIES` constant
- **Dependencies**: `colors.BLUE_ACCENT`, `TEAL`, `BLUE`, `GREEN`, `CORAL`

---

## library_page.py — Document Library

### File Tracking
Automatically records every PDF opened via any tool. Stores name, path, last-opened timestamp, favorite flag, and trash flag. State is persisted as JSON at `~/.pdfree/library.json` (path configurable via `PDFREE_STATE_DIR` env var).
- **Module**: library_page.py — `LibraryState.track()`
- **Dependencies**: `json`, `pathlib`, `datetime`

### Favorites
Toggle a star on any tracked file. Favorites surface in a dedicated sidebar view.
- **Module**: library_page.py — `LibraryState.set_favorite()`
- **Dependencies**: `LibraryState`; `colors.AMBER`

### Trash / Restore / Permanent Delete
Soft-delete files (move to Trash view). Restore from trash or permanently remove from the library.
- **Module**: library_page.py — `LibraryState.trash()`, `restore()`, `delete_permanently()`
- **Dependencies**: `LibraryState`

### Folder Tracking
Track real filesystem folders. Each folder is assigned a color from a fixed palette and appears as a card showing file count and total size. Clicking opens a filtered file list for that folder.
- **Module**: library_page.py — `LibraryState.add_folder()`, `folder_stats()`, `in_folder()`; `FolderCard`, `_NewFolderCard`
- **Dependencies**: `FOLDER_COLORS`; `colors.BLUE_ACCENT`; `icons.folder`

### Library Search
A text entry filters all visible file and folder cards in real time by substring match against file names.
- **Module**: library_page.py — `LibraryState._match()`, `all_active()`, `recent()`, `favorites()`
- **Dependencies**: `LibraryState`

### Hero Banner
Shows the most recently opened PDF with file size, page count, and last-modified age. A "Continue Editing" button opens that file. Falls back to a welcome message when the library is empty.
- **Module**: library_page.py — `HeroBanner`
- **Dependencies**: `fitz` (page count); `colors.EMERALD`, `EMERALD_DARK`; Signals: `open_req(str)`

### Human-Readable File Metadata
Displays file age ("5m ago", "2h ago", "3d ago") and formatted file size ("1.2 MB") alongside each entry.
- **Module**: library_page.py — `_age_str()`, `_fmt_size()`
- **Dependencies**: `datetime`

---

## view_tool.py — PDF Viewer

### PDF Rendering
Opens a PDF and renders each page to a `QPixmap` via PyMuPDF at the current zoom level and rotation. Supports fit-page and fit-width zoom modes in addition to a continuous 0.1–5.0× scale range.
- **Module**: view_tool.py — `ViewTool._show()`, `PDFCanvas.paintEvent()`
- **Dependencies**: `fitz`; `utils._fitz_pix_to_qpixmap`; `FIT_PAGE = -1.0`, `FIT_WIDTH = -2.0`

### Zoom Controls
Zoom in/out buttons, fit-page, fit-width, and a direct scale entry. Mouse wheel also zooms. Zoom range: 0.1× to 5.0×.
- **Module**: view_tool.py — `ViewTool._zoom_in()`, `_zoom_out()`, `_zoom_fit_page()`, `_zoom_fit_width()`
- **Dependencies**: `fitz.Matrix`

### Page Navigation
Previous/next page buttons, a direct page number entry, and keyboard shortcuts (PgUp/PgDn, arrow keys).
- **Module**: view_tool.py — `ViewTool._prev_page()`, `_next_page()`, `_goto_page()`
- **Dependencies**: None beyond PySide6

### Rotation
Rotate the current view 90° clockwise or counter-clockwise. Rotation state is per-document.
- **Module**: view_tool.py — `ViewTool._rotate_cw()`, `_rotate_ccw()`
- **Dependencies**: `fitz.Matrix`

### Annotation Tools (13 tools)
Toolbar with 13 annotation types, each with a keyboard shortcut:

| Tool | Key | Description |
|---|---|---|
| View | V | Pan/scroll mode, no annotation |
| Select | S | Select/move existing annotations |
| Highlight | H | Yellow highlight over text |
| Underline | U | Underline text |
| Strikethrough | K | Strikethrough text |
| Freehand | X | Free-draw ink path |
| Text Box | N | Add a text annotation |
| Sticky Note | D | Add a sticky note icon |
| Rectangle | R | Draw a rectangle shape |
| Circle | O | Draw an ellipse/circle shape |
| Line | L | Draw a straight line |
| Arrow | A | Draw a line with arrowhead |
| Sign | E | Place a drawn signature |

- **Module**: view_tool.py — `Tool` enum; `ViewTool._set_tool()`, `_get_tool_def()`
- **Dependencies**: `fitz` annotation API; `Tool(Enum)`

### Annotation Color Picker
Color selector with 6 preset annotation colors (Yellow, Red, Blue, Green, Orange, Black) and a hex color entry for custom colors. Recent colors are shown as swatches with hover-delete.
- **Module**: view_tool.py — `_RecentSwatch`; `ViewTool._on_color_pick()`
- **Dependencies**: `ANNOT_COLORS`; `colors.BLUE_MED`

### Annotation Stroke Width
Slider control to adjust pen/line width for applicable annotation tools (Freehand, Line, Arrow, Rectangle, Circle).
- **Module**: view_tool.py — width slider in annotation toolbar
- **Dependencies**: `fitz` stroke width API

### Annotation Editing (Double-click)
Double-clicking an existing annotation opens an inline editor to change its content or delete it.
- **Module**: view_tool.py — `ViewTool._on_double_click()`
- **Dependencies**: `fitz` annotation hit-testing

### Undo / Redo
Per-session undo/redo stack (max 30 steps) for annotation actions. Tracks annotation state via `fitz.Page.set_annot_flags`.
- **Module**: view_tool.py — `ViewTool._undo()`, `_redo()`
- **Dependencies**: `fitz`; `MAX_UNDO = 30`

### Full-Text Search
Ctrl+F opens a search bar. Matches are highlighted on the page canvas. Next/Previous match navigation with wrapping.
- **Module**: view_tool.py — `ViewTool._on_search()`, `_search_next_match()`
- **Dependencies**: `fitz.Page.search_for()`; `SEL_BLUE_R/G/B` constants

### Thumbnail Sidebar
Left sidebar showing page thumbnails for quick navigation. Thumbnails are lazy-rendered via `QTimer`.
- **Module**: view_tool.py — thumbnail sidebar
- **Dependencies**: `fitz`; `QTimer`

### TOC / Properties Sidebar
Right sidebar with two tabs: Table of Contents (from PDF bookmarks) and document properties (metadata, page count, file size).
- **Module**: view_tool.py — right sidebar, TOC tab
- **Dependencies**: `fitz.Document.get_toc()`

### Form Field Overlay
Detects PDF form fields and overlays interactive Qt widgets (`QLineEdit`, `QCheckBox`, `QComboBox`) at the correct positions for each field type.
- **Module**: view_tool.py — `ViewTool._build_form_overlay()`
- **Dependencies**: `fitz.Page.widgets()`; PySide6 form widgets

### Signature Drawing
A modal dialog with a freehand canvas for drawing a signature with the mouse. The result is exported as a PNG and inserted as an image annotation at the cursor position.
- **Module**: view_tool.py — `SignatureDialog`, `_SigCanvas`
- **Dependencies**: `fitz` image annotation; `tempfile`

### PDF Save
Writes the annotated PDF back to disk (in-place or Save As). Sets `_modified = False` after save.
- **Module**: view_tool.py — `ViewTool._save_pdf()`
- **Dependencies**: `fitz.Document.save()`

### Multi-Document Tabs
Open multiple PDFs in tabs; each tab shows a filename (truncated to 20 chars), with `•` prefix when modified. Tab bar includes a `+` button for quick adding. Keyboard shortcuts: Ctrl+Tab (next), Ctrl+Shift+Tab (previous), Ctrl+W (close). Duplicate files are detected and reused. Each pane maintains independent zoom, rotation, page position, and annotation undo stack (30 steps max).
- **Module**: view_tool.py — `_RenderPane`, `ViewTool._tab_widget`, `ViewTool.open_file()`, `ViewTool._close_tab()`
- **Dependencies**: `QTabWidget`, `_RenderPane` per-document state container

### Split View
Side-by-side display of two independent panes within a `QSplitter`. Left pane is the active tab; right pane is independent and opens the same file at page 0. Split mode toggled via `toggle_split()` / `close_split()`. Splitter is collapsible and resizable.
- **Module**: view_tool.py — `ViewTool._split_left_pane`, `ViewTool._split_right_pane`, `ViewTool._splitter`, `ViewTool.toggle_split()`, `ViewTool.close_split()`
- **Dependencies**: `QSplitter`, `_RenderPane` instances

### Clickable Links
URI links (`LINK_URI`) open in the system browser via `QDesktopServices.openUrl()`. GOTO links (`LINK_GOTO`) navigate to the target page within the current pane. Hover over any link shows a PointingHandCursor. Click vs. drag discrimination uses a 4 px threshold to avoid accidental navigation.
- **Module**: view_tool.py — `PDFCanvas._update_link_cache()`, `PDFCanvas._fire_link()`, `PDFCanvas._link_at_pos()`
- **Dependencies**: `fitz` link API, `QDesktopServices`

### Reading Position Memory
Last-viewed page number is persisted in `library.json` via `LibraryState.get_last_page()` / `set_last_page()`. Restored automatically on file reopen with out-of-range clamping (e.g., if the PDF was reduced to fewer pages). Signal `page_changed` is emitted on each navigation; listeners write state to persistence.
- **Module**: view_tool.py — `_RenderPane.load()`, `_RenderPane.page_changed` signal; library_page.py — `LibraryState.get_last_page()`, `LibraryState.set_last_page()`
- **Dependencies**: `LibraryState` for persistence

### Unsaved-Changes Dialogs
Per-tab Save / Discard / Cancel dialog on tab close (via `_close_tab()`). Aggregate Save All / Discard All / Cancel dialog on app quit (via `ViewTool.closeEvent()`). Dirty state tracked per-pane via `is_modified` property.
- **Module**: view_tool.py — `ViewTool._close_tab()`, `ViewTool.closeEvent()`; main.py — `PDFreeApp.closeEvent()`
- **Dependencies**: `QMessageBox`

---

## split_tool.py — PDF Splitter

### PDF Loading
Opens a PDF via file dialog and shows a preview of the first page.
- **Module**: split_tool.py — `SplitTool._pick_pdf()`
- **Dependencies**: `fitz`; `QFileDialog`

### Page Preview
Renders a high-resolution preview of any page with the current cut line overlaid as a dashed red/grey horizontal line.
- **Module**: split_tool.py — `_PreviewCanvas`; `SplitTool._show()`
- **Dependencies**: `fitz`; `utils._fitz_pix_to_qpixmap`; `CUT_ACTIVE`, `CUT_INACTIVE`

### Cut Line Dragging
The horizontal cut line on the preview can be dragged vertically with the mouse. The cursor changes to a resize cursor near the line. Cut position is stored as a fractional Y offset on the page.
- **Module**: split_tool.py — `SplitTool._start_drag()`, `_do_drag()`, `_end_drag()`
- **Dependencies**: `_PreviewCanvas`; `QCursor`

### Split Modes
Three splitting modes selectable from a combo box:
1. **By Range** — User enters page ranges (e.g. "1-4, 7, 10-12"), each range becomes one PDF.
2. **Every N Pages** — Split into chunks of N pages.
3. **In Half** — Split the document at its midpoint.
- **Module**: split_tool.py — `SplitTool._split_pdf()`, `_parse_ranges()`
- **Dependencies**: `pypdf.PdfReader`, `PdfWriter`

### Range Quick-Add
From/To entry fields with a "+" button to append a range to the range string without typing.
- **Module**: split_tool.py — `SplitTool._quick_add_range()`, `_set_quick_to_current()`
- **Dependencies**: None beyond PySide6

### Output File Naming
A configurable output filename template where `%d` is replaced by the part number (e.g. "report_part_%d.pdf").
- **Module**: split_tool.py — `SplitTool._split_pdf()`
- **Dependencies**: `pypdf`

### Zoom Controls
Zoom in/out buttons and a fit-to-width button in the preview toolbar.
- **Module**: split_tool.py — zoom controls
- **Dependencies**: `fitz.Matrix`

### Page Navigation
Previous/next buttons and direct page entry. Navigating updates the preview and thumbnail strip selection.
- **Module**: split_tool.py — `SplitTool._next()`, `_prev()`, `_goto_page()`
- **Dependencies**: None beyond PySide6

### Thumbnail Strip
A horizontal scrollable strip of page thumbnails at the bottom. Wheel events are routed to horizontal scroll. Selected page is highlighted.
- **Module**: split_tool.py — thumbnail strip
- **Dependencies**: `utils._WheelToHScroll`; `THUMB_W = 64`

### Full-Text Search
Ctrl+F toggles a search bar. Matches are highlighted on the preview canvas. Next/Prev match navigation.
- **Module**: split_tool.py — `SplitTool._search_do()`, `_search_next_match()`
- **Dependencies**: `fitz.Page.search_for()`

### Progress Feedback
A progress bar and status label show extraction progress during splitting.
- **Module**: split_tool.py — `QProgressBar`, status label
- **Dependencies**: PySide6

---

## excerpt_tool.py — Excerpt / Region Capture

### Multi-PDF Loading
Load multiple PDFs simultaneously. Each appears in the left panel list. Switch the active document with one click.
- **Module**: excerpt_tool.py — `ExcerptTool._add_pdf()`, `_set_active_pdf()`
- **Dependencies**: `fitz`; `QFileDialog`

### Page Rendering
Renders the current page of the active PDF at the current zoom level with a soft drop-shadow effect.
- **Module**: excerpt_tool.py — `ExcerptCanvas.paintEvent()`; `ExcerptTool._render_page()`
- **Dependencies**: `fitz`; `utils._fitz_pix_to_qpixmap`

### Rubber-Band Region Selection
Click and drag on the page canvas to draw a rectangular selection. The selection is shown with a dashed blue border and corner handles. Releasing the mouse captures the region.
- **Module**: excerpt_tool.py — `ExcerptCanvas` mouse events; `ExcerptTool._do_capture()`
- **Dependencies**: `fitz.Rect`; `colors.SEL_BLUE`, `BLUE_DARK`

### Region Capture
Each dragged selection creates a `Snippet` (dataclass with source path, page index, crop rect, label, thumbnail) and appends the cropped region to the in-memory output PDF using `fitz.show_pdf_page` with a clip rect. Preserves native PDF text and links.
- **Module**: excerpt_tool.py — `ExcerptTool._do_capture()`; `Snippet` dataclass
- **Dependencies**: `fitz.show_pdf_page`; `Snippet`

### Capture Flash Feedback
A brief green flash animation plays on the canvas to confirm a capture has been recorded.
- **Module**: excerpt_tool.py — `ExcerptTool._flash_feedback()`
- **Dependencies**: `QTimer`; `colors.GREEN`

### Snippet List
The left panel shows a scrollable list of all captured snippets with thumbnails, labels, and page references. Snippets can be reordered and removed.
- **Module**: excerpt_tool.py — `ExcerptTool._build_snippet_panel()`
- **Dependencies**: `Snippet.thumbnail`

### Save Excerpt PDF
Saves the accumulated output PDF to a user-chosen path via file dialog.
- **Module**: excerpt_tool.py — `ExcerptTool._save_excerpt()`
- **Dependencies**: `fitz.Document.save()`

### Zoom Controls
Zoom in/out of the page preview. Current page re-renders at the new scale.
- **Module**: excerpt_tool.py — `ExcerptTool._zoom_in()`, `_zoom_out()`
- **Dependencies**: `fitz.Matrix`

### Page Navigation
Previous/next buttons and a direct page entry field for navigating within the active PDF.
- **Module**: excerpt_tool.py — `ExcerptTool._prev_page()`, `_next_page()`, `_goto_page()`
- **Dependencies**: None beyond PySide6

### Thumbnail Strip
A horizontal scrollable thumbnail strip at the bottom for quick page navigation. Wheel events route to horizontal scroll.
- **Module**: excerpt_tool.py — bottom thumbnail strip
- **Dependencies**: `utils._WheelToHScroll`; `THUMB_W = 80`

### Collapsible Sidebar
A toggle button hides/shows the left snippet panel to maximize the page canvas area.
- **Module**: excerpt_tool.py — `ExcerptTool._toggle_sidebar()`
- **Dependencies**: `LEFT_W = 320`

---

## pdf_to_csv_tool.py — PDF Table Extractor

### PDF Loading
Load a PDF via file dialog. Displays pages in a preview canvas with detected table outlines.
- **Module**: pdf_to_csv_tool.py — `PDFtoCSVTool._browse_file()`
- **Dependencies**: `fitz`; `pdfplumber`; `QFileDialog`

### Table Detection
Detect tables using pdfplumber with three selectable methods: Lattice (ruled lines), Stream (whitespace), Hybrid (combines both). Configurable row tolerance and column tolerance.
- **Module**: pdf_to_csv_tool.py — `PDFtoCSVTool._run_extraction()`
- **Dependencies**: `pdfplumber.open()` table detection settings

### Table Overlay Preview
Detected table bounding boxes are drawn as blue dashed rectangles over the page preview.
- **Module**: pdf_to_csv_tool.py — `_PreviewCanvas.paintEvent()`
- **Dependencies**: `fitz`; `QPen` dashed style

### Page Range Filter
Optional page range input (e.g. "1-3, 5") to limit extraction to specific pages.
- **Module**: pdf_to_csv_tool.py — `PDFtoCSVTool._run_extraction()`
- **Dependencies**: Range parsing logic

### Table Filters
Min-rows and min-columns thresholds to discard spurious small tables. Toggle to skip image-only pages.
- **Module**: pdf_to_csv_tool.py — `PDFtoCSVTool._run_extraction()`
- **Dependencies**: `pdfplumber`

### Extraction Settings
Fine-grained controls over output content:
- Strip leading/trailing whitespace
- Handle merged/spanning cells
- Custom or standard line-break handling within cells
- Unicode normalization (NFC, NFKC)
- Automatic type detection (numbers, dates)
- Header row handling
- **Module**: pdf_to_csv_tool.py — `PDFtoCSVTool._run_extraction()`
- **Dependencies**: `unicodedata`; `re`

### CSV Output Options
Full control over the output format:
- Delimiter: Comma, Semicolon, Tab, Pipe
- Encoding: UTF-8, UTF-8 with BOM, UTF-16, ASCII, Windows-1252, ISO-8859-1
- Line endings: System default, Unix (LF), Windows (CRLF)
- Multi-table handling: one CSV per table vs. all tables in one file
- Optional source metadata columns (source file, page number, table index)
- **Module**: pdf_to_csv_tool.py — `PDFtoCSVTool._run_extraction()`; `ENCODING_MAP`, `DELIMITER_MAP`, `LINE_ENDING_MAP`
- **Dependencies**: `csv.DictWriter`

### Output Folder Selection
Browse for an output directory. All CSV files are written there.
- **Module**: pdf_to_csv_tool.py — `PDFtoCSVTool._browse_folder()`
- **Dependencies**: `QFileDialog`

### Extraction Report
After extraction, a report view replaces the canvas, showing per-page and per-table status, row counts, and any errors.
- **Module**: pdf_to_csv_tool.py — `PDFtoCSVTool._build_report_widget()`
- **Dependencies**: `QStackedWidget`

### Page Navigation
Previous/next page navigation in the preview panel. Also drives the thumbnail strip selection.
- **Module**: pdf_to_csv_tool.py — `PDFtoCSVTool._prev_page()`, `_next_page()`
- **Dependencies**: `fitz`

### Thumbnail Strip
A horizontal scrollable thumbnail strip at the bottom. Wheel routes to horizontal scroll.
- **Module**: pdf_to_csv_tool.py — bottom thumbnail strip
- **Dependencies**: `utils._WheelToHScroll`; `THUMB_W = 80`

---

## Shared Infrastructure

### Color Palette (colors.py)
Single source of truth for all UI colors. Organized into neutral, grayscale, brand, blue family, action, amber, extended, and chrome groups.
- **Module**: colors.py
- **Dependencies**: None

### SVG Icon Library (icons.py)
Lucide Icons (ISC License) rendered on-demand to `QPixmap`/`QIcon` at any color and size. Cached by (name, color, size). 90+ icons organized by category.
- **Module**: icons.py — `svg_pixmap()`, `svg_icon()`, `is_svg_icon()`
- **Dependencies**: PySide6, QSvgRenderer

### Fitz-to-QPixmap Conversion (utils.py)
Converts a `fitz.Pixmap` (RGB) to a `QPixmap` for rendering PDF pages in Qt widgets. Handles both `samples_mv` and `samples` attribute variants.
- **Module**: utils.py — `_fitz_pix_to_qpixmap()`
- **Dependencies**: `fitz`; PySide6

### Back Button Factory (utils.py)
Returns a styled `QPushButton` with an arrow-left icon, transparent background, and hover state. Used by all tool screens to navigate back to the home dashboard.
- **Module**: utils.py — `_make_back_button()`
- **Dependencies**: `icons.svg_icon`; `colors.G100`, `G700`

### Wheel-to-Horizontal Scroll (utils.py)
Event filter installed on `QScrollArea.viewport()`. Routes vertical mouse wheel events to the horizontal scrollbar, enabling natural horizontal scrolling of thumbnail strips with a standard scroll wheel.
- **Module**: utils.py — `_WheelToHScroll`
- **Dependencies**: PySide6 event system

---

## bookmarks_tool.py — Bookmark Editor

### Bookmark Tree View
Right panel displays the PDF's full table of contents as a `QTreeWidget` with hierarchical indentation (levels 1–6). Each entry shows title and target page. Selecting an entry populates the left-panel editor.
- **Module**: bookmarks_tool.py — `BookmarksTool._refresh_tree()`, `_on_selection_changed()`
- **Dependencies**: `fitz.Document.get_toc()`; `QTreeWidget`

### Add / Remove / Rename Bookmarks
Left panel editor: title field, page spin, level spin, Apply Changes button. Add inserts a new level-1 entry after the current selection. Remove deletes the entry and all its children (subtree). `toc_remove()` and `toc_move_up/down()` are pure functions on the flat TOC list.
- **Module**: bookmarks_tool.py — `toc_remove()`, `toc_move_up()`, `toc_move_down()`; `BookmarksTool._add_bookmark()`, `_remove_bookmark()`, `_apply_edit()`
- **Dependencies**: stdlib only for pure helpers

### Reorder Bookmarks
Up/Down buttons move the selected entry (and its children) one sibling position within the same nesting level. Cross-level moves are not permitted.
- **Module**: bookmarks_tool.py — `BookmarksTool._move_up()`, `_move_down()`
- **Dependencies**: `toc_move_up()`, `toc_move_down()`

---

## page_labels_tool.py — Page Labels

### Custom Page Numbering Ranges
Define one or more label ranges, each specifying: first page (1-based), numbering style (Arabic, Roman lower/upper, Alpha lower/upper, or None), optional prefix, and start number. The right panel shows a live preview table mapping physical pages to their computed labels. Existing PDF label ranges are read on load via `fitz.Document.get_page_labels()`.
- **Module**: page_labels_tool.py — `PageLabelsTool`, `_RangeRow`, `compute_labels()`
- **Dependencies**: `fitz.Document.get_page_labels()`, `fitz.Document.set_page_labels()`

### Label Formats
Six styles supported: `D` (1, 2, 3…), `r` (i, ii, iii…), `R` (I, II, III…), `a` (a, b, c…), `A` (A, B, C…), empty string (no label). Optional text prefix prepended to each label (e.g. "A-" → "A-1", "A-2"…).
- **Module**: page_labels_tool.py — `_format_num()`, `_to_roman()`, `_to_alpha()`
- **Dependencies**: stdlib only

---

## theme.py — Dark / Light Theme

### Theme Toggle
A moon/sun button in the home screen header switches between light and dark themes. `theme.apply_theme(dark)` mutates all relevant constants in `colors.py` so every subsequently created widget picks up the new palette. Preference is persisted as `theme.json` in the log directory and applied at startup.
- **Module**: theme.py — `apply_theme()`, `is_dark()`; main.py — `PDFreeApp._toggle_theme()`
- **Dependencies**: `colors.py`; `logging_config._log_dir()`

---

## batch_tool.py — Batch Processor

### Multi-File Batch Operations
Apply one operation to multiple PDF files at once. Supported operations: Compress (lossless/lossy presets), Rotate Pages (90° CW, 90° CCW, 180°), Add Page Numbers (position, format, start), Add Password (AES 256/128, RC4 128), Remove Password. Files are processed sequentially in a background `_BatchWorker(QThread)`.
- **Module**: batch_tool.py — `BatchTool`, `_BatchWorker`, `_run_compress`, `_run_rotate`, `_run_add_page_numbers`, `_run_add_password`, `_run_remove_password`
- **Dependencies**: `fitz`; `pypdf`; `PySide6.QThread`

### File Queue with Status Tracking
Right panel shows all queued PDFs with filename, page count, and a per-file status badge (Pending / Processing... / Done / Error). Files can be added via Browse or drag-and-drop and removed individually or all at once.
- **Module**: batch_tool.py — `_FileRow`; `BatchTool._add_file()`, `_remove_file()`, `_clear_files()`
- **Dependencies**: `fitz` (page count)

### Configurable Output Folder
Output folder selector; defaults to the directory of the first input file when left blank. Each processed file is saved as `<stem>_batch.pdf` in the output folder.
- **Module**: batch_tool.py — `BatchTool._browse_out_dir()`, `_run_batch()`
- **Dependencies**: `pathlib`

---

## merge_tool.py — PDF Merger

### Multi-File Loading
Add multiple PDFs via a browse dialog or drag-and-drop onto the tool window. Duplicate paths are silently ignored. Each file is opened with fitz for preview and its page count stored.
- **Module**: merge_tool.py — `MergeTool._browse_files()`, `_add_file()`
- **Dependencies**: `fitz`; `QFileDialog`

### File List with Reorder and Remove
Each added file appears as a row in a scrollable list showing a first-page thumbnail, filename (elided), and page count. Up/down buttons reorder the merge order; a remove button drops the file. Button states are kept consistent (top item cannot move up, bottom cannot move down).
- **Module**: merge_tool.py — `_FileRow`; `MergeTool._rebuild_list()`, `_move_up()`, `_move_down()`, `_remove_file()`
- **Dependencies**: None beyond PySide6

### Page Preview
Clicking a file row selects it and renders its first page (at 1.4× scale) in the right-panel canvas. The canvas paints a drop-shadow around the page and falls back to a placeholder when no file is loaded.
- **Module**: merge_tool.py — `_PreviewCanvas`; `MergeTool._select()`, `_render_preview()`
- **Dependencies**: `fitz`; `utils._fitz_pix_to_qpixmap`

### Page Navigation
Prev/next buttons and a clickable thumbnail strip let the user browse all pages of the selected file before merging.
- **Module**: merge_tool.py — `MergeTool._prev_page()`, `_next_page()`, `_goto_page()`
- **Dependencies**: None beyond PySide6

### Thumbnail Strip
Horizontal scrollable strip of page thumbnails for the selected file. Wheel events route to horizontal scroll. Selected page is highlighted with a blue border.
- **Module**: merge_tool.py — `MergeTool._rebuild_thumbs()`, `_refresh_thumb_highlight()`
- **Dependencies**: `utils._WheelToHScroll`; `THUMB_W = 68`

### Merge with Progress Feedback
Writes all loaded PDFs in list order to a user-chosen output path using `pypdf.PdfWriter.append()`. A progress bar and status label update during the write. The merge button is disabled until at least two files are loaded.
- **Module**: merge_tool.py — `MergeTool._merge_pdfs()`
- **Dependencies**: `pypdf.PdfReader`, `pypdf.PdfWriter`; `QProgressBar`

---

## remove_tool.py — Remove Pages

### Page Grid View
The right panel renders all pages as a scrollable thumbnail grid (4 columns). Thumbnails are loaded lazily in batches of 8 via `QTimer` to keep the UI responsive on large documents.
- **Module**: remove_tool.py — `RemoveTool._build_grid()`, `_render_thumbs_deferred()`
- **Dependencies**: `fitz`; `utils._fitz_pix_to_qpixmap`; `THUMB_SCALE = 0.25`; `GRID_COLS = 4`

### Toggle Page Selection
Clicking any thumbnail marks or unmarks it for removal. Marked pages show a red overlay with a drawn X cross. The page number label turns red when marked.
- **Module**: remove_tool.py — `_PageCell`; `RemoveTool._toggle_page()`
- **Dependencies**: `QPainter`; `colors.RED`, `RED_DIM`

### Bulk Selection Controls
Select All, Deselect All, and Invert Selection buttons act on the full page set at once.
- **Module**: remove_tool.py — `RemoveTool._select_all()`, `_deselect_all()`, `_invert_selection()`
- **Dependencies**: None beyond PySide6

### Selection Summary
A label updates in real time showing how many pages are marked and how many will remain. Turns red and bold when pages are marked.
- **Module**: remove_tool.py — `RemoveTool._update_summary()`
- **Dependencies**: None beyond PySide6

### Save with Guard
Writes only the kept pages via `pypdf.PdfWriter.add_page()`. Prevents saving if all pages are marked (at least one must remain). Output filename defaults to `<stem>_removed.pdf`.
- **Module**: remove_tool.py — `RemoveTool._remove_pages()`
- **Dependencies**: `pypdf.PdfReader`, `pypdf.PdfWriter`; `QProgressBar`

---

## rotate_tool.py — Rotate Pages

### Page Grid View with Live Preview
All pages rendered as a 4-column thumbnail grid. After any rotation is applied, affected thumbnails are re-queued and re-rendered immediately at the new angle using `fitz.Matrix.prerotate()`.
- **Module**: rotate_tool.py — `RotateTool._build_grid()`, `_render_cell_thumb()`, `_render_thumbs_deferred()`
- **Dependencies**: `fitz`; `utils._fitz_pix_to_qpixmap`; `THUMB_SCALE = 0.25`

### Click-to-Select Pages
Clicking a thumbnail toggles selection (blue border). Selected pages are the target for the rotate-selected buttons. Selection state and count shown in left panel.
- **Module**: rotate_tool.py — `_PageCell`; `RotateTool._toggle_select()`
- **Dependencies**: `colors.BLUE_DIM`, `BLUE`

### Rotate Selected / Rotate All
Two button groups: one applies rotation to selected pages only; the other to all pages at once. Both support 90° CCW, 90° CW, and 180°. Rotations accumulate (e.g. two CW clicks = 180°).
- **Module**: rotate_tool.py — `RotateTool._rotate_selected()`, `_rotate_all()`, `_apply_rotation()`
- **Dependencies**: `fitz.Matrix.prerotate()`

### Rotation Badge
Each cell shows the cumulative extra rotation in degrees as a bold badge next to the page number. Cells with no rotation show no badge.
- **Module**: rotate_tool.py — `_PageCell.paintEvent()`
- **Dependencies**: None beyond PySide6

### Save
Writes all pages via `pypdf.PdfWriter`; only pages with non-zero rotation have `PageObject.rotate()` called. Save button stays disabled until at least one page has been rotated. Output defaults to `<stem>_rotated.pdf`.
- **Module**: rotate_tool.py — `RotateTool._save_pdf()`
- **Dependencies**: `pypdf.PdfReader`, `pypdf.PdfWriter`

---

## compress_tool.py — PDF Compressor

### Compression Presets
Four selectable preset cards in the left panel, each with a colored badge, label, and description. Only one preset can be active at a time.
- **Module**: compress_tool.py — `_PresetCard`; `CompressTool._select_preset()`; `PRESETS` constant
- **Dependencies**: None beyond PySide6

### Lossless Compression
Calls `fitz.Document.save()` with `garbage=4, deflate=True, deflate_images=True, deflate_fonts=True, clean=True, use_objstms=True`. Removes unused objects, consolidates duplicates, and deflates all streams. No quality loss.
- **Module**: compress_tool.py — `CompressTool._compress_lossless()`
- **Dependencies**: `fitz`

### Lossy Re-render Compression
For Print (150 DPI), eBook (96 DPI), and Screen (72 DPI) presets: renders each page to a pixmap at the target DPI, inserts the image into a new fitz document at the original page dimensions, then saves with deflate. Trades text searchability for smaller file size.
- **Module**: compress_tool.py — `CompressTool._compress_lossy()`
- **Dependencies**: `fitz.Matrix`, `fitz.Page.get_pixmap()`, `fitz.Page.insert_image()`

---

## add_password_tool.py — Add Password

### Encryption Level Selection
Three selectable cards: AES 256-bit (default), AES 128-bit, RC4 128-bit. Maps to `fitz.PDF_ENCRYPT_AES_256/128` and `PDF_ENCRYPT_RC4_128`.
- **Module**: add_password_tool.py — `_EncCard`; `AddPasswordTool._select_enc()`; `ENC_MAP`
- **Dependencies**: `fitz` encryption constants

### Password Fields with Validation
User password field, confirm field, and optional owner password field. Save button is disabled until the user password is non-empty and both password fields match. Inline mismatch error shown between fields.
- **Module**: add_password_tool.py — `AddPasswordTool._validate()`
- **Dependencies**: None beyond PySide6

### Permission Checkboxes
Seven checkboxes mapped to `fitz.PDF_PERM_*` flags: Print, Print HQ, Copy, Modify, Annotate, Forms, Assemble. All checked by default. Combined with bitwise OR into the `permissions` argument of `fitz.Document.save()`.
- **Module**: add_password_tool.py — `AddPasswordTool._save()`; `PERMISSIONS` constant
- **Dependencies**: `fitz.PDF_PERM_*`

### Already-Protected Guard
On file load, opens the document and checks `doc.needs_pass`. If already encrypted, shows a warning and rejects the file.
- **Module**: add_password_tool.py — `AddPasswordTool._load_file()`
- **Dependencies**: `fitz`

---

## remove_password_tool.py — Remove Password

### Encryption Status Badge
On file load, checks `doc.needs_pass` and shows a colored status badge: red "Password-protected" or green "Not encrypted". Non-encrypted files bypass the unlock step and enable Save directly.
- **Module**: remove_password_tool.py — `RemovePasswordTool._load_file()`
- **Dependencies**: `fitz`; `colors.RED_DIM`, `EMERALD`

### Inline Unlock Step
Password field + Unlock button. On click, opens the document and calls `doc.authenticate(pw)`. Shows inline success or error. Save button only activates after successful authentication.
- **Module**: remove_password_tool.py — `RemovePasswordTool._try_unlock()`
- **Dependencies**: `fitz.Document.authenticate()`

### Save Without Encryption
Saves via `fitz.Document.save(encryption=PDF_ENCRYPT_NONE, garbage=3, deflate=True)`. Re-authenticates at save time for safety.
- **Module**: remove_password_tool.py — `RemovePasswordTool._save()`
- **Dependencies**: `fitz.PDF_ENCRYPT_NONE`

---

### Before / After Result Card
The right panel shows the original file info on load. After compression completes, a result card is inserted showing compressed size, bytes saved, and percentage reduction, with a visual fill bar.
- **Module**: compress_tool.py — `CompressTool._show_file_info()`, `_show_result()`
- **Dependencies**: `colors.EMERALD`

---

## img_to_pdf_tool.py — Image to PDF

### Ordered Image List
Add JPEG, PNG, BMP, GIF, TIFF, and WebP files via browse dialog or drag-and-drop. Each entry shows a thumbnail, filename, and format badge. Up/down buttons reorder; a remove button drops the entry. Clicking a row previews the full image on the right.
- **Module**: img_to_pdf_tool.py — `_ImgRow`; `ImgToPDFTool._add_image()`, `_rebuild_list()`
- **Dependencies**: `QPixmap`; `SUPPORTED_EXT`

### Page Size and Margin Options
Page size combo (A4 Portrait/Landscape, Letter Portrait/Landscape, Fit to Image) and margin combo (None/Small/Medium/Large in points). "Fit to Image" computes page dimensions from the image pixel size assuming 96 DPI.
- **Module**: img_to_pdf_tool.py — `ImgToPDFTool._convert()`; `PAGE_SIZES`, `MARGINS` constants
- **Dependencies**: `QImageReader`; `fitz.Page.insert_image(keep_proportion=True)`

### Convert to PDF
Creates a new fitz document, adds one page per image at the configured size and margin, inserts each image with `keep_proportion=True`, and saves with deflate.
- **Module**: img_to_pdf_tool.py — `ImgToPDFTool._convert()`
- **Dependencies**: `fitz`

---

## pdf_to_img_tool.py — PDF to Image

### Page Selection Grid
All pages shown as a 4-column thumbnail grid, all selected by default (blue border). Click to deselect/reselect. Select All / None buttons. Thumbnails rendered lazily in batches of 8.
- **Module**: pdf_to_img_tool.py — `_PageCell`; `PDFToImgTool._build_grid()`, `_toggle_page()`
- **Dependencies**: `fitz`; `utils._fitz_pix_to_qpixmap`

### Export Settings
Format (PNG / JPEG), DPI (72/96/150/200/300), and JPEG quality slider (20–100, visible only for JPEG). Output folder defaults to the PDF's directory.
- **Module**: pdf_to_img_tool.py — `PDFToImgTool._export()`; `DPI_OPTIONS`, `FORMAT_OPTIONS`
- **Dependencies**: `fitz.Pixmap.save(jpg_quality=)`

### Batch Export
Exports each selected page as `<stem>_page<NNNN>.<ext>` in the output folder. Progress bar updates per page.
- **Module**: pdf_to_img_tool.py — `PDFToImgTool._export()`
- **Dependencies**: `fitz`; `QProgressBar`

---

## change_metadata_tool.py — Change Metadata

### Metadata Field Editor
Displays all 8 standard PDF metadata fields (Title, Author, Subject, Keywords, Creator, Producer, Creation Date, Modification Date) as editable inputs. Keywords uses a multi-line text area; all other fields use single-line entries. Fields are pre-populated with the current values when a file is loaded.
- **Module**: change_metadata_tool.py — `ChangeMetadataTool._load_file()`
- **Dependencies**: `fitz.Document.metadata`; `_FIELDS` constant

### Current Metadata Display
The right panel shows a card with all current metadata values read from the loaded PDF, updated on each file load.
- **Module**: change_metadata_tool.py — `ChangeMetadataTool._build_right_panel()`; `_meta_rows` dict
- **Dependencies**: `fitz`

### Save with New Metadata
Writes a new PDF with the edited metadata via `fitz.Document.set_metadata()`. Output filename defaults to `<stem>_metadata.pdf`. Leaves blank fields empty (clearing them from the PDF).
- **Module**: change_metadata_tool.py — `ChangeMetadataTool._save()`
- **Dependencies**: `fitz.Document.set_metadata()`, `fitz.Document.save(garbage=3, deflate=True)`

---

## add_page_numbers_tool.py — Add Page Numbers

### Live Preview
Right panel renders the current preview page with the number stamped at the configured position using an in-memory fitz copy. Preview refreshes 200 ms after any setting change (debounced via `QTimer`). Prev/next buttons navigate pages.
- **Module**: add_page_numbers_tool.py — `AddPageNumbersTool._refresh_preview()`, `_queue_preview()`
- **Dependencies**: `fitz.Document.insert_pdf()`; `fitz.Page.insert_textbox()`

### Numbering Options
Position (6 options), format (1 / Page 1 / 1/N / Page 1 of N / - 1 -), font size (6–36 pt), start number, and skip-first-N-pages. Format strings resolved by `_format_number()`.
- **Module**: add_page_numbers_tool.py — `_format_number()`; `POSITIONS`, `FORMATS` constants
- **Dependencies**: None beyond PySide6

### Save
Applies `fitz.Page.insert_textbox()` to every non-skipped page with the configured text and alignment, then saves with `garbage=3, deflate=True`.
- **Module**: add_page_numbers_tool.py — `AddPageNumbersTool._save()`
- **Dependencies**: `fitz`; `_number_rect()`

---

## pdfa_tool.py — PDF/A Export

### Version Selection
Three PDF/A version cards (PDF/A-1b, -2b, -3b) let the user choose the target archival standard. Selecting a card highlights it and sets `part` / `conformance` for the conversion. An amber "best-effort" notice references VeraPDF for certified validation.
- **Module**: pdfa_tool.py — `PDFATool._build_left_panel()`; `_VERSIONS` catalogue
- **Dependencies**: None beyond PySide6

### Sanitisation Options
Four checkboxes control what gets stripped before conversion: JavaScript, embedded/attached files, hidden text layers, and thumbnail images. Stripping is performed via `fitz.Document.scrub()`.
- **Module**: pdfa_tool.py — `PDFATool._build_left_panel()`; `convert_to_pdfa()` — `remove_js`, `remove_embedded`, `remove_hidden_text`, `remove_thumbnails` parameters
- **Dependencies**: `fitz.Document.scrub()`

### XMP Conformance Declaration
Injects an XMP metadata block with `pdfaid:part` and `pdfaid:conformance` identifiers (ISO 19005) into the output PDF via `fitz.Document.set_xml_metadata()`.
- **Module**: pdfa_tool.py — `convert_to_pdfa()`; `_PDFA_XMP_TEMPLATE`
- **Dependencies**: `fitz.Document.set_xml_metadata()`

### Background Conversion Worker
Conversion runs in `_PDFAWorker(QThread)` so the UI stays responsive. Emits `progress(int)`, `finished(str)`, and `failed(str)` signals. The UI shows a progress bar and a result card on completion.
- **Module**: pdfa_tool.py — `_PDFAWorker`; `PDFATool._start_conversion()`, `_on_done()`, `_on_failed()`
- **Dependencies**: `QThread`, `Signal`

---

## i18n.py — Internationalisation Scaffolding

### Translation Helper
`tr(text)` wraps `QCoreApplication.translate("PDFree", text)` for runtime string lookup. `QT_TRANSLATE_NOOP(context, text)` marks strings at module level without translating (no-op at runtime; recognised by `pyside6-lupdate`).
- **Module**: i18n.py — `tr()`, `QT_TRANSLATE_NOOP()`
- **Dependencies**: `PySide6.QtCore.QCoreApplication`

### Translatable Catalogue in main.py
All CATEGORIES titles and tool names, all TOOL_DESCRIPTIONS values, and all TAB_CATEGORIES keys are wrapped with `QT_TRANSLATE_NOOP`. `tr()` is called at widget-creation time in ToolCard, RecentCard, tab buttons, `_tool_display_name`, and key home-screen labels.
- **Module**: main.py — `CATEGORIES`, `TOOL_DESCRIPTIONS`, `TAB_CATEGORIES`; `ToolCard.__init__()`, `RecentCard.__init__()`, `_build_tool_grid()`, `_tool_display_name()`
- **Dependencies**: i18n.py

### Base Translation File
`translations/pdffree_en.ts` — Qt XML catalogue with 82 English source strings, generated by `pyside6-lupdate main.py i18n.py -ts translations/pdffree_en.ts`. To add a locale: copy to `translations/pdffree_<lang>.ts`, translate with Qt Linguist, compile with `pyside6-lrelease`, load via `QTranslator` at startup.
- **Module**: translations/pdffree_en.ts
- **Dependencies**: `pyside6-lupdate`, `pyside6-lrelease`

---

## sign_tool.py — Digital Signature

### Cryptographic PDF Signing
Sign a PDF with a PKCS#12 (.p12/.pfx) certificate. Adds a cryptographically valid digital signature field at a user-chosen position on any page. Supports optional reason, location, and contact info metadata. Signing runs in a background `_SignWorker(QThread)` so the UI stays responsive. Output saved as `<stem>_signed.pdf`.
- **Module**: sign_tool.py — `SignTool`, `_SignWorker`
- **Dependencies**: `pyhanko`; `fitz` (preview); `PySide6.QThread`

### Signature Placement Presets
Four one-click placement presets: Bottom Right, Bottom Left, Top Right, Top Left. Each computes a standard 240×70 pt signature box in PDF coordinates (bottom-left origin). The right-panel preview shows the exact placement as a dashed blue rectangle before signing.
- **Module**: sign_tool.py — `_POSITIONS`; `_pdf_box_to_canvas()`; `_PreviewCanvas`
- **Dependencies**: `fitz`

### TSA Timestamping
Optional RFC 3161 timestamp can be embedded in the signature by supplying a TSA URL in the left-panel "TIMESTAMP (OPTIONAL)" field. When non-empty, `HTTPTimeStamper` is constructed and passed to `signers.sign_pdf()`. Leave blank to sign without a timestamp.
- **Module**: sign_tool.py — `_SignWorker.run()`
- **Dependencies**: `pyhanko.sign.timestamps.HTTPTimeStamper`

---

## validate_signature_tool.py — Signature Validation

### PDF Digital Signature Validation
Validates all embedded digital signatures in a PDF. For each signature reports: field name, signer DN, trust status, document integrity (bottom_line), validation summary, signing time, and timestamp presence. Validation runs in `_ValidateWorker(QThread)`. Results shown as per-signature cards in a scrollable right panel with colored trust badge (emerald = trusted, red = not trusted).
- **Module**: validate_signature_tool.py — `ValidateSignatureTool`, `_ValidateWorker`, `validate_signatures()`
- **Dependencies**: `pyhanko.pdf_utils.reader.PdfFileReader`; `pyhanko.sign.validation.validate_pdf_signature`; `PySide6.QThread`


---

## redact_tool.py — Manual Redaction

### Drag-to-Draw Bounding Box Redaction
Draw black redaction boxes over any area of a page by clicking and dragging. Boxes are rendered in the canvas immediately. Double-clicking an existing box removes it. All rects are stored per-page in `_all_rects`. On save, each rect is applied via `page.add_redact_annot()` + `page.apply_redactions()` for permanent content-stream removal.
- **Module**: redact_tool.py — `_RedactCanvas`, `RedactTool._save()`
- **Dependencies**: `fitz`

### Text / Regex Auto-Redaction
Search for a plain-text string or regex pattern across all pages and automatically add bounding-box redactions for every match. Options: case-sensitive toggle, regex mode toggle. In plain-text mode uses `fitz.Page.search_for()`; in regex mode extracts page text, finds matches with `re`, then resolves bounding boxes via `search_for`. Results are merged into `_all_rects`; the current page canvas refreshes immediately.
- **Module**: redact_tool.py — `RedactTool._find_and_add_matches()`
- **Dependencies**: `fitz`; `re`
