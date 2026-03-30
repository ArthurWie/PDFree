# PDFree — Tauri Rewrite Design Spec
> Date: 2026-03-30

## Context

PDFree is currently implemented in Python 3.11 + PySide6, with PyMuPDF (fitz), pypdf, and pdfplumber as PDF backends. The app ships 42+ tools across a native widget-tree GUI.

This spec covers the complete rewrite to a Tauri 2.0 + Rust + React architecture. The Python repo is frozen as a reference. All new work lives in a separate greenfield repository.

---

## Decisions

### Rendering approach
PDFium (via `pdfium-render`) rasterizes pages on the Rust side on a dedicated rendering thread. The resulting RGBA bitmap is sent to the frontend as a raw `ArrayBuffer` over Tauri's binary IPC — not base64. JS constructs an `ImageData` object and paints it to a `<canvas>`. A second transparent `<canvas>` layer handles all annotation drawing (freehand, shapes, highlights, text boxes). AcroForm fields are the only DOM overlay (HTML `<input>`/`<select>`/`<textarea>` absolutely positioned over the canvas at transformed coordinates).

**wgpu is dropped.** PDFium's software rasterizer is sufficient. wgpu would add a custom GPU compositing pipeline on top of a library that doesn't expose raw primitives for re-rendering, yielding no measurable user-visible benefit for a document viewer at standard zoom levels.

### Migration strategy
Greenfield repo. Python repo frozen — critical bug fixes only. Feature parity tracked against `docs/project-state/FEATURES.md`. Staged roadmap with the viewer as the centerpiece; the app is not released until Phases 0–2 are complete.

### Deferred / out of scope
Office → PDF, HTML → PDF, PDF → Word, and PDF → Excel are deferred to a future phase (Phase 9+). These have no clean Rust-native solution without shelling out to LibreOffice or a cloud API. They are cut from the v1 roadmap.

---

## Target Stack

### Desktop shell
- **Tauri 2.0** — native window, OS integration, keyboard shortcuts, file drag-and-drop

### Frontend
- **React** — component UI (toolbar, sidebar, panels, annotation overlays)
- **Tailwind CSS** — utility-first styling
- **shadcn/ui** — copy-paste component library (Radix UI primitives, Tailwind-native, accessible). Used for all buttons, inputs, dialogs, selects, tooltips, menus across 42+ tool panels.
- **Zustand** — global state: page position, zoom, selections, edit mode, per-tab undo/redo stacks
- **Vite** — dev server and production bundler
- **i18next + react-i18next** — internationalization (English locale initialized; translations added later)

### Rust — rendering & reading
- **pdfium-render** — PDFium binding: page tree, rendering, text extraction, annotation read/write, AcroForm, page add/remove
- **tantivy** — full-text search index across the document library
- **tesseract-rs** — OCR for scanned PDFs

### Rust — PDF editing
- **lopdf** — low-level content stream access: surgical edits, page manipulation, object-level mutations
- **pdf-writer** — high-level page generation and reconstruction
- **printpdf** — higher-level PDF generation for simpler workflows

### Rust — storage & security
- **sqlx + SQLite** — local database: annotations, bookmarks, recent files, library state, user settings, reading position
- **rasn + rasn-cms** — PDF digital signature creation and verification (PKCS#7 / CMS over X.509)
- **reqwest** — HTTP client for TSA timestamping during PDF signing

### Rust ↔ TypeScript bridge
- **Specta** — generates TypeScript types from Rust structs automatically

### Tauri plugins
- `tauri-plugin-single-instance` — single-instance detection (replaces QLocalServer)
- `tauri-plugin-updater` — auto-update via GitHub Releases (replaces updater.py)
- `tauri-plugin-dialog` — file open/save dialogs (replaces QFileDialog)
- `tauri-plugin-fs` — file system access
- `tauri-plugin-drag` — file drag-and-drop onto app window
- `tauri-plugin-log` — structured log file on disk

### Infrastructure (not in original stack, now explicit)
- **tracing + tracing-subscriber** — structured logging on Rust side
- Rust panic hook — writes backtrace to log file on crash
- JS error boundary — "copy crash report" dialog surfacing the log
- CSS custom properties + Tailwind `dark:` variants — theme system (dark/light, persisted in SQLite settings)
- `tauri-action` CI/CD — builds Windows x64, macOS universal, Linux AppImage; code signing via secrets
- Windows Authenticode cert — required to avoid SmartScreen warnings
- Apple Developer ID + notarization via `notarytool` — required for macOS distribution

### Testing
- **Vitest** — React unit and integration tests
- **cargo test** — Rust unit tests
- **Playwright via Tauri WebDriver** — end-to-end tests driving the full desktop app
- **axe-core via axe-playwright** — accessibility auditing in E2E runs

---

## Architecture

### Coordinate transform module
A dedicated, unit-tested module handles all coordinate transforms between PDF space and canvas space. This is not optional — every annotation, link, form field, and selection rect depends on it.

```
PDF space:    origin bottom-left, unit = points (1pt = 1/72 inch)
Canvas space: origin top-left, unit = pixels, zoom-scaled

pdf_to_canvas(x, y, page_height_pts, zoom, dpr):
    canvas_x = x * zoom * dpr
    canvas_y = (page_height_pts - y) * zoom * dpr

canvas_to_pdf(cx, cy, page_height_pts, zoom, dpr):
    x = cx / (zoom * dpr)
    y = page_height_pts - cy / (zoom * dpr)
```

All annotation coordinates stored in PDF space. Transform applied on render only.

### Multi-document state (Rust)
A `HashMap<TabId, OpenDocument>` held in Tauri managed state. `OpenDocument` holds the `PdfiumDocument` handle, current page, zoom, rotation, and a dirty flag. All PDFium calls are marshalled through a dedicated rendering thread (PDFium is not guaranteed Send across threads in all configurations — validate with pdfium-render's thread model before finalizing).

### Annotation layer
- Page canvas: renders PDFium bitmap
- Annotation canvas: transparent overlay, same dimensions, handles all drawing tool interactions
- Annotation state: stored in Zustand per tab, serialized to PDF on save via pdfium-render write-back
- Undo/redo: per-tab stack in Zustand, max 30 steps, each step is a full snapshot of that tab's annotation state

### Library state
Replaces `~/.pdfree/library.json` with SQLite via sqlx. Schema:

```sql
files    (id, path, name, last_opened, size, page_count, favorited, trashed,
          last_page INTEGER, scroll_offset REAL, zoom REAL)
folders  (id, path, color)
settings (key TEXT PRIMARY KEY, value TEXT)
```

Reading position (scroll offset, zoom, last page) stored directly in the `files` row. Replaces Python's in-memory-only position memory with cross-session persistence.

---

## Phased Migration Plan

### Phase 0 — Scaffold
New repo initialized. Cargo workspace, Vite + React + TypeScript, Tailwind, shadcn/ui, Zustand, Specta, all Tauri plugins, sqlx schema, tracing. CI/CD pipeline live from day one. Code signing stubbed.

**Gate:** blank window opens on Windows, macOS, Linux. CI is green.

### Phase 1 — Rendering Pipeline
PDFium integrated. Page rasterized to RGBA on a rendering thread. Bitmap sent as `ArrayBuffer` over binary IPC. JS paints to canvas. Zoom, rotation, page navigation, thumbnail strip, TOC sidebar, clickable links.

**Critical benchmark:** A4 PDF, 150 DPI, measure round-trip latency per page turn. If > 50ms, implement progressive rendering (viewport-first, prefetch adjacent pages) before proceeding.

**Gate:** open any PDF, scroll, zoom, navigate, click links. Page turn latency < 50ms on A4 at 150 DPI on a mid-range machine.

### Phase 2 — Annotation Engine
Canvas annotation layer. All 13 tool types: View, Select, Highlight, Underline, Strikethrough, Freehand, Text Box, Sticky Note, Rectangle, Circle, Line, Arrow, Sign. Color picker, stroke width. Undo/redo. Annotation persistence via pdfium-render write-back. AcroForm field display (read-only overlay — interactive fill, export, and unlock are Phase 6). Multi-document tabs. Split view. PDF save. Unsaved changes guard.

**Validation required:** prototype all 13 annotation types against pdfium-render's write API before committing. If any type is unsupported, decide: implement via lopdf, or cut.

**Gate:** full annotation round-trip — add all 13 types, save, reopen, all intact.

### Phase 3 — App Shell & Library
Home dashboard (hero banner, tool grid, search, drag-drop, recently used tools). SQLite-backed library (favorites, trash, folders). Dark/light theme. Auto-updater. i18next initialized. Crash reporter.

**Gate:** app shell navigable. Library tracks files from Phase 2.

### Phase 4 — Organize Tools
Merge, Split, Rotate, Remove pages, Reorder, Excerpt. All share the pattern: load pages → thumbnail grid → mutate → save.

**Gate:** each tool round-trips correctly with a corpus of test PDFs.

### Phase 5 — Edit Tools
Compress, Add/Remove password, Watermark, Add page numbers, Headers/footers, Crop, Scale pages, Change metadata, Bookmarks, Page labels, Redact, Flatten, Remove annotations, Add image, N-up, Batch operations.

Independent tools — can be shipped incrementally within the phase.

### Phase 6 — AcroForm & Signing
AcroForm fill/export/unlock (builds on Phase 2 read-only overlay). PDF signing (rasn-cms + reqwest for TSA). Signature validation. PDF/A conversion. Sanitize (removes embedded scripts, metadata, and other potentially sensitive content from PDF object graph).

### Phase 7 — Convert & Advanced Tools
OCR (tesseract-rs), Image ↔ PDF, SVG → PDF, PDF → CSV, PDF → Excel, Compare, Font info.

---

## Risk Register

| Risk | Phase | Mitigation |
|---|---|---|
| ArrayBuffer IPC throughput | 1 | Benchmark before proceeding; design progressive rendering in from the start |
| pdfium-render annotation write-back coverage gaps | 2 | Prototype all 13 types explicitly; lopdf fallback or cut for unsupported types |
| PDFium thread-safety with pdfium-render | 1 | Validate thread model; use dedicated rendering thread + channel if not Send |
| AcroForm coordinate precision at non-integer zoom | 2 & 6 | Dedicated test suite with real-world AcroForm PDFs |
| lopdf content stream editing brittleness | 5+ | Limit to specific well-defined operations; honest UI copy about limitations |
| Tesseract bundling on all three platforms | 7 | Validate Tauri bundling of native tessdata early; don't leave to last |
| macOS notarization pipeline | 0 | Stub config in Phase 0; add real certs before any public release |

---

## What is explicitly out of scope

- Office → PDF
- HTML → PDF
- PDF → Word
- PDF → Excel

These are deferred to Phase 9+ pending a decision on LibreOffice shell-out or cloud API. They are not referenced in Phases 0–7.
