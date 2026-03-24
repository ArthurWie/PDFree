# Data Storage

PDFree is a desktop application with no SQL database and no ORM. The only persistent storage is a single JSON file managed by `LibraryState` in `library_page.py`.

---

## library.json

**Location:** `~/.pdfree/library.json`
**Configurable via:** `PDFREE_STATE_DIR` environment variable (see `docs/ENV.md`). If set, the file is at `$PDFREE_STATE_DIR/library.json`.
**Managed by:** `LibraryState` class in `library_page.py`
**Write strategy:** Debounced — changes are queued and written after a 1 s `QTimer` fires. Immediate writes available via `_save()`.

### Top-level schema

```json
{
  "files":   [ <FileEntry>, ... ],
  "folders": [ <FolderEntry>, ... ]
}
```

---

### FileEntry

Represents one tracked PDF file.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Filename only (no directory path), e.g. `"report.pdf"` |
| `path` | string | yes | Absolute resolved path to the file |
| `last_opened` | string | yes | ISO 8601 UTC timestamp, e.g. `"2026-03-15T10:00:00+00:00"` |
| `favorited` | boolean | yes | Whether the user has starred this file |
| `trashed` | boolean | yes | Whether the file is in the soft-delete trash |

**Constraints:**
- `path` is the primary key. `track()` is idempotent — calling it twice for the same resolved path updates `last_opened` rather than creating a duplicate.
- `path` is resolved via `Path(path).resolve()` before storage, ensuring no duplicates from relative vs absolute paths.
- Files are never hard-deleted from the JSON by default. `delete_permanently()` removes the entry entirely.

**Example:**
```json
{
  "name": "contract.pdf",
  "path": "/Users/alice/Documents/contract.pdf",
  "last_opened": "2026-03-15T09:45:12+00:00",
  "favorited": false,
  "trashed": false
}
```

---

### FolderEntry

Represents a tracked filesystem folder.

| Field | Type | Required | Description |
|---|---|---|---|
| `path` | string | yes | Absolute path to the folder |
| `color` | string | yes | Hex color string assigned to this folder card, e.g. `"#3B82F6"` |

**Constraints:**
- `path` is the primary key.
- Color is assigned from a fixed palette (`FOLDER_COLORS` in `library_page.py`) cycling by current folder count. User cannot currently change color after creation.
- Files inside a tracked folder are **not** stored in `folders` — they are scanned live from disk via `_scan_folder()` each time the folder is opened.

**Example:**
```json
{
  "path": "/Users/alice/Projects",
  "color": "#10B981"
}
```

---

## Relationships

```
FolderEntry (1) ──── (N) FileEntry
```

This relationship is **implicit, not stored**. There is no foreign key. When the user views a folder, `LibraryState.in_folder(folder_path)` scans the real filesystem for `.pdf` files in that directory and cross-references against `files` entries to get `last_opened`, `favorited`, and `trashed` status. Files that exist on disk but have never been opened via PDFree will not have a FileEntry.

---

## In-Memory State (non-persisted)

The following state exists during a session but is never written to disk:

| Location | State | Description |
|---|---|---|
| `ViewTool._undo_stack` | `list[list]` | Per-document annotation undo history (max 30 steps) |
| `ViewTool._docs` | `list[dict]` | Loaded fitz documents and per-doc state (zoom, rotation, page) |
| `ExcerptTool._snippets` | `list[Snippet]` | Captured regions; lost if app closes before saving |
| `ExcerptTool._out_doc` | `fitz.Document` | In-memory output PDF; lost if app closes before saving |
| `PDFreeApp._recents` | `list[str]` | Recently used tool IDs (session only) |

---

## Migration

There is no migration system. The JSON schema is implicitly versioned by the application version. If the schema changes in a future version:

1. Add a `"version"` integer field to the top-level object.
2. On load, check the version and run a migration function before passing data to the rest of the app.
3. Document the migration in `CHANGELOG.md`.

Current schema version: **1** (implicit, no version field present).
