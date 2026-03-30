# PDFree Tauri Rewrite — Phase 0 & 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffold a greenfield Tauri 2.0 + Rust + React repository with CI/CD, then implement the PDF rendering pipeline — open a PDF, navigate pages, zoom, view thumbnails and TOC, click links — with page turn latency < 50ms.

**Architecture:** PDFium (via `pdfium-render`) rasterizes pages on a dedicated Rust rendering thread. Bitmaps are sent to React as raw `ArrayBuffer` over Tauri's binary IPC. React constructs `ImageData` and paints it to a `<canvas>`. A second transparent canvas layer sits on top, reserved for Phase 2 annotation drawing.

**Tech Stack:** Tauri 2.0, Rust (pdfium-render, sqlx+SQLite, tracing, specta, tokio), React 19, TypeScript, Tailwind CSS v4, shadcn/ui, Zustand, Vite, Vitest

---

## Note on repository location

All paths below are relative to a **new repo root** created adjacent to the Python repo. The Python repo is not touched.

```bash
# Run from the parent directory of PDFree/
npm create tauri-app@latest pdfreetauri -- --template react-ts
cd pdfreetauri
```

This plan is stored in the Python repo for reference only.

---

## File map

### Phase 0 files
```
pdfreetauri/
├── src-tauri/
│   ├── Cargo.toml
│   ├── build.rs                        (tauri-build, unchanged from scaffold)
│   ├── tauri.conf.json                 (tauri config)
│   ├── capabilities/default.json       (tauri permissions)
│   └── src/
│       ├── main.rs                     (thin entry point)
│       ├── lib.rs                      (app setup, plugin wiring)
│       └── db/
│           ├── mod.rs                  (pool init, migration runner)
│           └── migrations/
│               └── 0001_initial.sql
├── src/
│   ├── main.tsx
│   ├── App.tsx
│   ├── index.css
│   ├── test-setup.ts
│   └── components/
│       └── ErrorBoundary.tsx
├── .github/workflows/
│   ├── ci.yml
│   └── release.yml
├── package.json
├── vite.config.ts
├── tsconfig.json
├── components.json                     (shadcn/ui config)
└── index.html
```

### Phase 1 additional files
```
src-tauri/src/
├── commands/
│   ├── mod.rs
│   └── pdf.rs          open_document, render_page, render_page_with_size,
│                       get_toc, get_links, close_document
└── pdf/
    ├── mod.rs
    ├── coords.rs       pdf_to_canvas / canvas_to_pdf — unit tested
    ├── state.rs        DocumentInfo, TocEntry, PageLink, LinkTarget (serde + specta)
    └── engine.rs       RenderEngine, RenderCmd, rendering thread

src/
├── lib/
│   ├── coords.ts       mirrors coords.rs — unit tested
│   └── ipc.ts          typed invoke wrappers
├── store/
│   └── viewer.ts       Zustand: tabs, activeTabId, zoom, page, rotation
└── components/
    ├── PageCanvas.tsx          paints ArrayBuffer → canvas, hit-tests links
    ├── ViewerToolbar.tsx       prev/next, zoom in/out, rotate
    ├── TocSidebar.tsx          TOC tree from get_toc
    └── ThumbnailStrip.tsx      low-res page thumbnails

src/__tests__/
├── coords.test.ts
├── viewer-store.test.ts
└── benchmark.test.ts
```

---

## Phase 0 — Scaffold

### Task 0.1: Initialize repo

- [ ] **Create the app**

```bash
npm create tauri-app@latest pdfreetauri -- --template react-ts
cd pdfreetauri
npm install
```

- [ ] **Verify it builds**

```bash
npm run tauri dev
```

Expected: blank Tauri window opens. Ctrl+C to stop.

- [ ] **Init git and commit**

```bash
git init
git add .
git commit -m "chore: initialize tauri react-ts scaffold"
```

---

### Task 0.2: Rust dependencies

- [ ] **Replace the full `src-tauri/Cargo.toml`**

```toml
[package]
name = "pdfreetauri"
version = "0.1.0"
edition = "2021"

[lib]
name = "pdfreetauri_lib"
crate-type = ["staticlib", "cdylib", "rlib"]

[build-dependencies]
tauri-build = { version = "2", features = [] }

[dependencies]
tauri                    = { version = "2", features = [] }
tauri-plugin-single-instance = "2"
tauri-plugin-updater     = "2"
tauri-plugin-dialog      = "2"
tauri-plugin-fs          = "2"
tauri-plugin-log         = "2"
serde                    = { version = "1", features = ["derive"] }
serde_json               = "1"
pdfium-render            = { version = "0.8", features = ["pdfium_latest"] }
sqlx                     = { version = "0.8", features = ["runtime-tokio-rustls", "sqlite", "migrate"] }
tokio                    = { version = "1", features = ["full"] }
tracing                  = "0.1"
tracing-subscriber       = { version = "0.3", features = ["env-filter"] }
specta                   = { version = "2", features = ["derive"] }
tauri-specta             = { version = "2", features = ["derive", "typescript"] }
anyhow                   = "1"
thiserror                = "2"

[features]
specta-export = []

[profile.release]
panic        = "abort"
codegen-units = 1
lto          = true
opt-level    = "s"
strip        = true
```

- [ ] **Fetch deps**

```bash
cd src-tauri && cargo fetch && cd ..
```

Expected: no errors.

- [ ] **Commit**

```bash
git add src-tauri/Cargo.toml src-tauri/Cargo.lock
git commit -m "chore: add all rust dependencies"
```

---

### Task 0.3: SQLite schema

- [ ] **Create `src-tauri/src/db/migrations/0001_initial.sql`**

```sql
CREATE TABLE IF NOT EXISTS files (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    path          TEXT    NOT NULL UNIQUE,
    name          TEXT    NOT NULL,
    last_opened   TEXT    NOT NULL,
    size          INTEGER NOT NULL DEFAULT 0,
    page_count    INTEGER NOT NULL DEFAULT 0,
    favorited     INTEGER NOT NULL DEFAULT 0,
    trashed       INTEGER NOT NULL DEFAULT 0,
    last_page     INTEGER NOT NULL DEFAULT 0,
    scroll_offset REAL    NOT NULL DEFAULT 0.0,
    zoom          REAL    NOT NULL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS folders (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    path  TEXT NOT NULL UNIQUE,
    color TEXT NOT NULL DEFAULT '#6366f1'
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR IGNORE INTO settings (key, value) VALUES ('theme', 'light');
```

- [ ] **Create `src-tauri/src/db/mod.rs`**

```rust
use sqlx::{migrate::MigrateDatabase, Sqlite, SqlitePool};
use std::path::Path;

pub async fn init(app_data_dir: &Path) -> anyhow::Result<SqlitePool> {
    let db_path = app_data_dir.join("pdfreetauri.db");
    let db_url  = format!("sqlite://{}", db_path.display());

    if !Sqlite::database_exists(&db_url).await? {
        Sqlite::create_database(&db_url).await?;
    }

    let pool = SqlitePool::connect(&db_url).await?;
    sqlx::migrate!("src/db/migrations").run(&pool).await?;
    Ok(pool)
}
```

- [ ] **Commit**

```bash
git add src-tauri/src/db/
git commit -m "chore: sqlite schema and db init"
```

---

### Task 0.4: App entry point with tracing and plugins

- [ ] **Replace `src-tauri/src/lib.rs`**

```rust
use tauri::Manager;
use tracing_subscriber::EnvFilter;

mod db;

pub fn run() {
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .init();

    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(w) = app.get_webview_window("main") {
                let _ = w.set_focus();
            }
        }))
        .plugin(tauri_plugin_log::Builder::new().build())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .setup(|app| {
            let data_dir = app.path().app_data_dir()?;
            std::fs::create_dir_all(&data_dir)?;
            tauri::async_runtime::block_on(async {
                let pool = db::init(&data_dir).await.expect("db init failed");
                app.manage(pool);
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![])
        .run(tauri::generate_context!())
        .expect("error running tauri app");
}
```

- [ ] **Replace `src-tauri/src/main.rs`**

```rust
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
fn main() { pdfreetauri_lib::run(); }
```

- [ ] **Verify it compiles**

```bash
cd src-tauri && cargo build 2>&1 | grep -E "^error|Finished" && cd ..
```

Expected: `Finished dev`.

- [ ] **Commit**

```bash
git add src-tauri/src/
git commit -m "chore: app entry point with tracing and plugin wiring"
```

---

### Task 0.5: Frontend tooling

- [ ] **Install Tailwind v4 and shadcn/ui deps**

```bash
npm install tailwindcss @tailwindcss/vite
npm install zustand i18next react-i18next
```

- [ ] **Replace `vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  clearScreen: false,
  server: { port: 1420, strictPort: true },
  envPrefix: ["VITE_", "TAURI_"],
  build: {
    target: "chrome105",
    minify: !process.env.TAURI_DEBUG ? "esbuild" : false,
    sourcemap: !!process.env.TAURI_DEBUG,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
  },
});
```

- [ ] **Replace `src/index.css`**

```css
@import "tailwindcss";
```

- [ ] **Init shadcn/ui** (when prompted: style=Default, base color=Slate, CSS variables=Yes)

```bash
npx shadcn@latest init
```

- [ ] **Install test deps**

```bash
npm install -D vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom
```

- [ ] **Create `src/test-setup.ts`**

```typescript
import "@testing-library/jest-dom";
```

- [ ] **Add test script to `package.json`** (inside `"scripts"`)

```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Smoke test at `src/__tests__/smoke.test.ts`**

```typescript
import { describe, it, expect } from "vitest";
describe("smoke", () => {
  it("passes", () => expect(1 + 1).toBe(2));
});
```

- [ ] **Run tests**

```bash
npm test
```

Expected: `1 passed`.

- [ ] **Commit**

```bash
git add -A
git commit -m "chore: tailwind v4, shadcn/ui, zustand, vitest"
```

---

### Task 0.6: ErrorBoundary

- [ ] **Create `src/components/ErrorBoundary.tsx`**

```tsx
import { Component, ErrorInfo, ReactNode } from "react";

interface Props { children: ReactNode }
interface State { error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Uncaught:", error, info);
  }

  render() {
    if (this.state.error) {
      const msg = `${this.state.error.message}\n${this.state.error.stack ?? ""}`;
      return (
        <div className="flex h-screen flex-col items-center justify-center gap-4 bg-slate-50 p-8 text-center">
          <h1 className="text-xl font-semibold text-slate-800">Something went wrong</h1>
          <pre className="max-h-64 w-full overflow-auto rounded-lg bg-slate-100 p-4 text-left text-sm text-slate-700">
            {msg}
          </pre>
          <button
            className="rounded-md bg-slate-800 px-4 py-2 text-sm text-white hover:bg-slate-700"
            onClick={() => navigator.clipboard.writeText(msg)}
          >
            Copy crash report
          </button>
          <button
            className="text-sm text-slate-500 underline"
            onClick={() => this.setState({ error: null })}
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
```

- [ ] **Wrap app in `src/main.tsx`**

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { ErrorBoundary } from "./components/ErrorBoundary";
import App from "./App";
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>
);
```

- [ ] **Commit**

```bash
git add src/
git commit -m "feat: error boundary with crash report copy"
```

---

### Task 0.7: CI/CD

- [ ] **Create `.github/workflows/ci.yml`**

```yaml
name: CI
on:
  push:    { branches: [main] }
  pull_request: { branches: [main] }

jobs:
  test-rust:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - uses: Swatinem/rust-cache@v2
        with: { workspaces: src-tauri }
      - run: cd src-tauri && cargo test

  test-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm }
      - run: npm ci
      - run: npm test

  build:
    needs: [test-rust, test-frontend]
    strategy:
      matrix:
        include:
          - { os: ubuntu-latest,  target: x86_64-unknown-linux-gnu }
          - { os: macos-latest,   target: universal-apple-darwin }
          - { os: windows-latest, target: x86_64-pc-windows-msvc }
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm }
      - uses: dtolnay/rust-toolchain@stable
        with: { targets: "${{ matrix.target }}" }
      - uses: Swatinem/rust-cache@v2
        with: { workspaces: src-tauri }
      - run: npm ci
      - uses: tauri-apps/tauri-action@v0
        env: { GITHUB_TOKEN: "${{ secrets.GITHUB_TOKEN }}" }
        with: { args: "--target ${{ matrix.target }}" }
```

- [ ] **Create `.github/workflows/release.yml`**

```yaml
name: Release
on:
  push:
    tags: ["v*"]

jobs:
  release:
    strategy:
      matrix:
        include:
          - { os: ubuntu-latest,  target: x86_64-unknown-linux-gnu }
          - { os: macos-latest,   target: universal-apple-darwin }
          - { os: windows-latest, target: x86_64-pc-windows-msvc }
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm }
      - uses: dtolnay/rust-toolchain@stable
        with: { targets: "${{ matrix.target }}" }
      - uses: Swatinem/rust-cache@v2
        with: { workspaces: src-tauri }
      - run: npm ci
      - uses: tauri-apps/tauri-action@v0
        env:
          GITHUB_TOKEN: "${{ secrets.GITHUB_TOKEN }}"
          # Add before public release:
          # TAURI_SIGNING_PRIVATE_KEY: ${{ secrets.TAURI_SIGNING_PRIVATE_KEY }}
          # APPLE_ID: ${{ secrets.APPLE_ID }}
          # APPLE_PASSWORD: ${{ secrets.APPLE_PASSWORD }}
          # APPLE_TEAM_ID: ${{ secrets.APPLE_TEAM_ID }}
        with:
          tagName: ${{ github.ref_name }}
          releaseName: "PDFree ${{ github.ref_name }}"
          releaseDraft: true
          prerelease: false
          args: "--target ${{ matrix.target }}"
```

- [ ] **Push and verify CI**

```bash
git add .github/
git commit -m "chore: ci and release workflows"
git remote add origin <your-github-repo-url>
git push -u origin main
```

Expected: CI runs, test jobs pass, build jobs complete (~10 min).

---

**Phase 0 gate:** `npm run tauri dev` opens a blank window. `npm test` passes. CI is green on all three platforms.

---

## Phase 1 — Rendering Pipeline

### Task 1.1: Coordinate transform — Rust (TDD)

- [ ] **Create `src-tauri/src/pdf/mod.rs`**

```rust
pub mod coords;
pub mod engine;
pub mod state;
```

- [ ] **Create `src-tauri/src/pdf/coords.rs`**

```rust
//! Transforms between PDF coordinate space and canvas pixel space.
//!
//! PDF space:    origin bottom-left, unit = points (1 pt = 1/72 inch)
//! Canvas space: origin top-left,    unit = physical pixels (zoom × dpr applied)

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PdfPoint   { pub x: f64, pub y: f64 }

#[derive(Debug, Clone, Copy, PartialEq)]
pub struct CanvasPoint { pub x: f64, pub y: f64 }

pub fn pdf_to_canvas(p: PdfPoint, page_height_pts: f64, zoom: f64, dpr: f64) -> CanvasPoint {
    CanvasPoint {
        x: p.x * zoom * dpr,
        y: (page_height_pts - p.y) * zoom * dpr,
    }
}

pub fn canvas_to_pdf(p: CanvasPoint, page_height_pts: f64, zoom: f64, dpr: f64) -> PdfPoint {
    PdfPoint {
        x: p.x / (zoom * dpr),
        y: page_height_pts - p.y / (zoom * dpr),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const H: f64 = 842.0; // A4 height in points

    #[test]
    fn pdf_bottom_left_to_canvas_far_down() {
        let c = pdf_to_canvas(PdfPoint { x: 0.0, y: 0.0 }, H, 1.0, 1.0);
        assert_eq!(c.x, 0.0);
        assert!((c.y - H).abs() < 1e-10);
    }

    #[test]
    fn pdf_top_left_to_canvas_origin() {
        let c = pdf_to_canvas(PdfPoint { x: 0.0, y: H }, H, 1.0, 1.0);
        assert_eq!(c.x, 0.0);
        assert!(c.y.abs() < 1e-10);
    }

    #[test]
    fn zoom_scales_x() {
        let c = pdf_to_canvas(PdfPoint { x: 100.0, y: H }, H, 2.0, 1.0);
        assert_eq!(c.x, 200.0);
    }

    #[test]
    fn dpr_scales_x() {
        let c = pdf_to_canvas(PdfPoint { x: 100.0, y: H }, H, 1.0, 2.0);
        assert_eq!(c.x, 200.0);
    }

    #[test]
    fn round_trip() {
        let orig = PdfPoint { x: 150.0, y: 300.0 };
        let back = canvas_to_pdf(pdf_to_canvas(orig, H, 1.5, 2.0), H, 1.5, 2.0);
        assert!((back.x - orig.x).abs() < 1e-10);
        assert!((back.y - orig.y).abs() < 1e-10);
    }
}
```

- [ ] **Run Rust tests**

```bash
cd src-tauri && cargo test pdf::coords && cd ..
```

Expected: 5 passed.

- [ ] **Commit**

```bash
git add src-tauri/src/pdf/
git commit -m "feat: coordinate transform (Rust) with tests"
```

---

### Task 1.2: Coordinate transform — TypeScript (TDD)

- [ ] **Write the failing test at `src/__tests__/coords.test.ts`**

```typescript
import { describe, it, expect } from "vitest";
import { pdfToCanvas, canvasToPdf } from "../lib/coords";

const H = 842;

describe("pdfToCanvas", () => {
  it("maps pdf bottom-left to canvas far-down", () => {
    const c = pdfToCanvas({ x: 0, y: 0 }, H, 1, 1);
    expect(c.x).toBe(0);
    expect(c.y).toBeCloseTo(H);
  });
  it("maps pdf top-left to canvas origin", () => {
    const c = pdfToCanvas({ x: 0, y: H }, H, 1, 1);
    expect(c.x).toBe(0);
    expect(c.y).toBeCloseTo(0);
  });
  it("scales by zoom", () => {
    expect(pdfToCanvas({ x: 100, y: H }, H, 2, 1).x).toBe(200);
  });
  it("scales by dpr", () => {
    expect(pdfToCanvas({ x: 100, y: H }, H, 1, 2).x).toBe(200);
  });
});

describe("canvasToPdf round-trip", () => {
  it("returns original point", () => {
    const orig = { x: 150, y: 300 };
    const back = canvasToPdf(pdfToCanvas(orig, H, 1.5, 2), H, 1.5, 2);
    expect(back.x).toBeCloseTo(orig.x);
    expect(back.y).toBeCloseTo(orig.y);
  });
});
```

- [ ] **Run — verify FAIL**

```bash
npm test -- coords
```

Expected: `Cannot find module '../lib/coords'`.

- [ ] **Create `src/lib/coords.ts`**

```typescript
export interface PdfPoint    { x: number; y: number }
export interface CanvasPoint { x: number; y: number }

export function pdfToCanvas(
  p: PdfPoint, pageHeightPts: number, zoom: number, dpr: number
): CanvasPoint {
  return { x: p.x * zoom * dpr, y: (pageHeightPts - p.y) * zoom * dpr };
}

export function canvasToPdf(
  p: CanvasPoint, pageHeightPts: number, zoom: number, dpr: number
): PdfPoint {
  return { x: p.x / (zoom * dpr), y: pageHeightPts - p.y / (zoom * dpr) };
}
```

- [ ] **Run — verify PASS**

```bash
npm test -- coords
```

Expected: 5 passed.

- [ ] **Commit**

```bash
git add src/lib/coords.ts src/__tests__/coords.test.ts
git commit -m "feat: coordinate transform (TypeScript) with tests"
```

---

### Task 1.3: Document state types (Rust)

- [ ] **Create `src-tauri/src/pdf/state.rs`**

```rust
use serde::{Deserialize, Serialize};
use specta::Type;

pub type TabId = String;

#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct DocumentInfo {
    pub tab_id:          TabId,
    pub page_count:      u32,
    pub page_width_pts:  f64,
    pub page_height_pts: f64,
    pub title:           Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct TocEntry {
    pub title:      String,
    pub page_index: u32,
    pub level:      u32,
}

#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct PageLink {
    /// [x0, y0, x1, y1] in PDF points
    pub rect:   [f64; 4],
    pub target: LinkTarget,
}

#[derive(Debug, Clone, Serialize, Deserialize, Type)]
#[serde(tag = "type", content = "value")]
pub enum LinkTarget {
    Page(u32),
    Uri(String),
}

/// Returned alongside RGBA bytes so the frontend knows canvas dimensions.
#[derive(Debug, Clone, Serialize, Deserialize, Type)]
pub struct PageRender {
    pub width:  u32,
    pub height: u32,
}
```

- [ ] **Verify compile**

```bash
cd src-tauri && cargo check 2>&1 | grep -E "^error|Finished" && cd ..
```

Expected: `Finished`.

- [ ] **Commit**

```bash
git add src-tauri/src/pdf/state.rs
git commit -m "feat: pdf state types with serde and specta derives"
```

---

### Task 1.4: PDFium rendering engine

> **Before writing this task:** verify the exact pdfium-render 0.8.x API by running
> `cargo doc --open -p pdfium-render` in `src-tauri/`. The method names below match
> the 0.8 API; adjust if your resolved version differs.

- [ ] **Create `src-tauri/src/pdf/engine.rs`**

```rust
use std::{collections::HashMap, path::PathBuf, sync::mpsc, thread};

use anyhow::{anyhow, Result};
use pdfium_render::prelude::*;
use tokio::sync::oneshot;
use tracing::{error, info};

use super::state::{DocumentInfo, LinkTarget, PageLink, PageRender, TabId, TocEntry};

pub enum RenderCmd {
    Open {
        tab_id: TabId,
        path:   PathBuf,
        reply:  oneshot::Sender<Result<DocumentInfo>>,
    },
    RenderPage {
        tab_id:     TabId,
        page_index: u32,
        zoom:       f64,
        dpr:        f64,
        reply:      oneshot::Sender<Result<(Vec<u8>, PageRender)>>,
    },
    GetToc {
        tab_id: TabId,
        reply:  oneshot::Sender<Result<Vec<TocEntry>>>,
    },
    GetLinks {
        tab_id:     TabId,
        page_index: u32,
        reply:      oneshot::Sender<Result<Vec<PageLink>>>,
    },
    Close    { tab_id: TabId },
    Shutdown,
}

#[derive(Clone)]
pub struct RenderEngine {
    tx: mpsc::SyncSender<RenderCmd>,
}

impl RenderEngine {
    pub fn spawn() -> Self {
        let (tx, rx) = mpsc::sync_channel(32);
        thread::spawn(move || run_render_thread(rx));
        Self { tx }
    }

    pub fn send(&self, cmd: RenderCmd) {
        if let Err(e) = self.tx.send(cmd) {
            error!("render thread dead: {e}");
        }
    }
}

// ---------------------------------------------------------------------------
// Rendering thread — all PDFium calls happen here
// ---------------------------------------------------------------------------

fn run_render_thread(rx: mpsc::Receiver<RenderCmd>) {
    let pdfium = Pdfium::new(
        Pdfium::bind_to_library(Pdfium::pdfium_platform_library_name_at_path("./"))
            .or_else(|_| Pdfium::bind_to_system_library())
            .expect("cannot bind PDFium"),
    );

    // NOTE: PdfDocument borrows from `pdfium`, so we store them together.
    // Use a Vec of (TabId, PdfDocument) to avoid lifetime complications with HashMap.
    let mut docs: Vec<(TabId, PdfDocument<'_>)> = Vec::new();

    for cmd in rx {
        match cmd {
            RenderCmd::Open { tab_id, path, reply } => {
                let result = pdfium
                    .load_pdf_from_file(&path, None)
                    .map_err(|e| anyhow!("{e:?}"))
                    .and_then(|doc| {
                        let page_count = doc.pages().len() as u32;
                        let page       = doc.pages().get(0).map_err(|e| anyhow!("{e:?}"))?;
                        let w          = page.width().value  as f64;
                        let h          = page.height().value as f64;
                        let title      = doc.metadata().title()
                            .ok()
                            .flatten()
                            .map(|s| s.to_string());
                        let info = DocumentInfo {
                            tab_id: tab_id.clone(),
                            page_count,
                            page_width_pts:  w,
                            page_height_pts: h,
                            title,
                        };
                        docs.push((tab_id, doc));
                        Ok(info)
                    });
                let _ = reply.send(result);
            }

            RenderCmd::RenderPage { tab_id, page_index, zoom, dpr, reply } => {
                let result = (|| {
                    let doc  = find_doc(&docs, &tab_id)?;
                    let page = doc.pages().get(page_index as u16).map_err(|e| anyhow!("{e:?}"))?;
                    let scale = zoom * dpr;
                    let w = (page.width().value  as f64 * scale).round() as u16;
                    let h = (page.height().value as f64 * scale).round() as u16;
                    let bitmap = page
                        .render_with_config(
                            &PdfRenderConfig::new()
                                .set_target_width(w)
                                .set_target_height(h),
                        )
                        .map_err(|e| anyhow!("{e:?}"))?;
                    // pdfium-render produces BGRA by default on some platforms;
                    // check bitmap.format() and convert to RGBA if needed.
                    let bytes = bitmap.as_bytes().to_vec();
                    Ok((bytes, PageRender { width: w as u32, height: h as u32 }))
                })();
                let _ = reply.send(result);
            }

            RenderCmd::GetToc { tab_id, reply } => {
                let result = (|| {
                    let doc = find_doc(&docs, &tab_id)?;
                    let mut entries = Vec::new();
                    collect_toc_flat(doc, &mut entries);
                    Ok(entries)
                })();
                let _ = reply.send(result);
            }

            RenderCmd::GetLinks { tab_id, page_index, reply } => {
                let result = (|| {
                    let doc  = find_doc(&docs, &tab_id)?;
                    let page = doc.pages().get(page_index as u16).map_err(|e| anyhow!("{e:?}"))?;
                    let mut links = Vec::new();
                    for link in page.links().iter() {
                        let Some(action) = link.action() else { continue };
                        let target = if let Ok(Some(idx)) = action.page_index() {
                            LinkTarget::Page(idx as u32)
                        } else if let Ok(Some(uri)) = action.uri_path() {
                            LinkTarget::Uri(uri.to_string())
                        } else {
                            continue;
                        };
                        if let Ok(rect) = link.bounds() {
                            links.push(PageLink {
                                rect: [
                                    rect.left.value   as f64,
                                    rect.bottom.value as f64,
                                    rect.right.value  as f64,
                                    rect.top.value    as f64,
                                ],
                                target,
                            });
                        }
                    }
                    Ok(links)
                })();
                let _ = reply.send(result);
            }

            RenderCmd::Close { tab_id } => {
                docs.retain(|(id, _)| id != &tab_id);
                info!("closed tab {tab_id}");
            }

            RenderCmd::Shutdown => {
                info!("render thread shutting down");
                break;
            }
        }
    }
}

fn find_doc<'a>(docs: &'a [(TabId, PdfDocument<'a>)], tab_id: &str) -> Result<&'a PdfDocument<'a>> {
    docs.iter()
        .find(|(id, _)| id == tab_id)
        .map(|(_, doc)| doc)
        .ok_or_else(|| anyhow!("tab '{tab_id}' not found"))
}

/// Walk bookmarks iteratively to avoid lifetime issues with recursive borrows.
fn collect_toc_flat(doc: &PdfDocument<'_>, out: &mut Vec<TocEntry>) {
    // Walk via a stack of (bookmark_handle, level)
    struct Frame { title: String, page_index: u32, level: u32 }
    let mut stack: Vec<_> = Vec::new();

    fn walk(bm: Option<PdfBookmark<'_>>, level: u32, stack: &mut Vec<Frame>) {
        let Some(b) = bm else { return };
        let title = b.title().unwrap_or_default().to_string();
        let page_index = b.action()
            .and_then(|a| a.page_index().ok())
            .flatten()
            .unwrap_or(0) as u32;
        stack.push(Frame { title, page_index, level });
        walk(b.first_child(), level + 1, stack);
        walk(b.next_sibling(), level, stack);
    }

    walk(doc.bookmarks().first(), 0, &mut stack);
    out.extend(stack.into_iter().map(|f| TocEntry {
        title: f.title, page_index: f.page_index, level: f.level,
    }));
}
```

> **Note on pixel format:** `pdfium-render` may return BGRA instead of RGBA depending on
> platform and PDFium build. Add a byte-swap pass after `bitmap.as_bytes()` if pages render
> with swapped red/blue channels: iterate chunks of 4 and swap bytes 0 and 2.

- [ ] **Verify compile**

```bash
cd src-tauri && cargo build 2>&1 | grep -E "^error|Finished" && cd ..
```

Expected: `Finished`.

- [ ] **Commit**

```bash
git add src-tauri/src/pdf/engine.rs
git commit -m "feat: pdfium rendering engine on dedicated thread"
```

---

### Task 1.5: Tauri commands

- [ ] **Create `src-tauri/src/commands/mod.rs`**

```rust
pub mod pdf;
```

- [ ] **Create `src-tauri/src/commands/pdf.rs`**

```rust
use tauri::State;
use tokio::sync::oneshot;

use crate::pdf::{
    engine::{RenderCmd, RenderEngine},
    state::{DocumentInfo, PageLink, PageRender, TocEntry},
};

#[tauri::command]
#[specta::specta]
pub async fn open_document(
    path: String, tab_id: String, engine: State<'_, RenderEngine>,
) -> Result<DocumentInfo, String> {
    let (tx, rx) = oneshot::channel();
    engine.send(RenderCmd::Open { tab_id, path: path.into(), reply: tx });
    rx.await.map_err(|e| e.to_string())?.map_err(|e| e.to_string())
}

#[tauri::command]
#[specta::specta]
pub async fn render_page(
    tab_id: String, page_index: u32, zoom: f64, dpr: f64,
    engine: State<'_, RenderEngine>,
) -> Result<(Vec<u8>, PageRender), String> {
    let (tx, rx) = oneshot::channel();
    engine.send(RenderCmd::RenderPage { tab_id, page_index, zoom, dpr, reply: tx });
    rx.await.map_err(|e| e.to_string())?.map_err(|e| e.to_string())
}

#[tauri::command]
#[specta::specta]
pub async fn get_toc(
    tab_id: String, engine: State<'_, RenderEngine>,
) -> Result<Vec<TocEntry>, String> {
    let (tx, rx) = oneshot::channel();
    engine.send(RenderCmd::GetToc { tab_id, reply: tx });
    rx.await.map_err(|e| e.to_string())?.map_err(|e| e.to_string())
}

#[tauri::command]
#[specta::specta]
pub async fn get_links(
    tab_id: String, page_index: u32, engine: State<'_, RenderEngine>,
) -> Result<Vec<PageLink>, String> {
    let (tx, rx) = oneshot::channel();
    engine.send(RenderCmd::GetLinks { tab_id, page_index, reply: tx });
    rx.await.map_err(|e| e.to_string())?.map_err(|e| e.to_string())
}

#[tauri::command]
#[specta::specta]
pub async fn close_document(
    tab_id: String, engine: State<'_, RenderEngine>,
) -> Result<(), String> {
    engine.send(RenderCmd::Close { tab_id });
    Ok(())
}
```

- [ ] **Wire into `src-tauri/src/lib.rs`** — replace the whole file

```rust
use tauri::Manager;
use tracing_subscriber::EnvFilter;

mod commands;
mod db;
mod pdf;

use commands::pdf::{close_document, get_links, get_toc, open_document, render_page};
use pdf::engine::RenderEngine;

pub fn run() {
    tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .init();

    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(w) = app.get_webview_window("main") { let _ = w.set_focus(); }
        }))
        .plugin(tauri_plugin_log::Builder::new().build())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .setup(|app| {
            let data_dir = app.path().app_data_dir()?;
            std::fs::create_dir_all(&data_dir)?;
            tauri::async_runtime::block_on(async {
                let pool = db::init(&data_dir).await.expect("db init failed");
                app.manage(pool);
            });
            app.manage(RenderEngine::spawn());
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            open_document, render_page, get_toc, get_links, close_document,
        ])
        .run(tauri::generate_context!())
        .expect("error running tauri app");
}
```

- [ ] **Verify compile**

```bash
cd src-tauri && cargo build 2>&1 | grep -E "^error|Finished" && cd ..
```

Expected: `Finished`.

- [ ] **Commit**

```bash
git add src-tauri/src/
git commit -m "feat: tauri commands for pdf open/render/toc/links/close"
```

---

### Task 1.6: TypeScript IPC layer

- [ ] **Create `src/lib/ipc.ts`**

```typescript
import { invoke } from "@tauri-apps/api/core";

export interface DocumentInfo {
  tab_id:          string;
  page_count:      number;
  page_width_pts:  number;
  page_height_pts: number;
  title:           string | null;
}

export interface PageRender {
  width:  number;
  height: number;
}

export interface TocEntry {
  title:      string;
  page_index: number;
  level:      number;
}

export interface PageLink {
  rect:   [number, number, number, number]; // x0 y0 x1 y1 in PDF points
  target: { type: "Page"; value: number } | { type: "Uri"; value: string };
}

export function openDocument(path: string, tabId: string): Promise<DocumentInfo> {
  return invoke("open_document", { path, tabId });
}

export function renderPage(
  tabId: string, pageIndex: number, zoom: number, dpr: number
): Promise<[number[], PageRender]> {
  return invoke("render_page", { tabId, pageIndex, zoom, dpr });
}

export function getToc(tabId: string): Promise<TocEntry[]> {
  return invoke("get_toc", { tabId });
}

export function getLinks(tabId: string, pageIndex: number): Promise<PageLink[]> {
  return invoke("get_links", { tabId, pageIndex });
}

export function closeDocument(tabId: string): Promise<void> {
  return invoke("close_document", { tabId });
}
```

> **Note on binary transfer:** Tauri 2's `invoke` serializes return values through JSON by
> default. For large bitmaps this is slow. After verifying correctness, switch to
> `invoke` with `{ headers: { 'Content-Type': 'application/octet-stream' } }` or use
> Tauri's `Channel` API for streaming — benchmark first (Task 1.9) before optimizing.

- [ ] **Commit**

```bash
git add src/lib/ipc.ts
git commit -m "feat: typed typescript ipc wrappers"
```

---

### Task 1.7: Zustand viewer store

- [ ] **Write failing test at `src/__tests__/viewer-store.test.ts`**

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import { useViewerStore, TabState } from "../store/viewer";
import { DocumentInfo } from "../lib/ipc";

const info: DocumentInfo = {
  tab_id: "t1", page_count: 10,
  page_width_pts: 595, page_height_pts: 842, title: null,
};
const tab: TabState = {
  tabId: "t1", path: "/a.pdf", info,
  pageIndex: 0, zoom: 1.0, rotation: 0, dirty: false,
};

beforeEach(() => useViewerStore.setState({ tabs: [], activeTabId: null }));

describe("viewer store", () => {
  it("adds tab and makes it active", () => {
    useViewerStore.getState().addTab(tab);
    expect(useViewerStore.getState().tabs).toHaveLength(1);
    expect(useViewerStore.getState().activeTabId).toBe("t1");
  });
  it("removes tab and clears active", () => {
    useViewerStore.getState().addTab(tab);
    useViewerStore.getState().removeTab("t1");
    expect(useViewerStore.getState().tabs).toHaveLength(0);
    expect(useViewerStore.getState().activeTabId).toBeNull();
  });
  it("updates page", () => {
    useViewerStore.getState().addTab(tab);
    useViewerStore.getState().setPage("t1", 4);
    expect(useViewerStore.getState().tabs[0].pageIndex).toBe(4);
  });
  it("updates zoom", () => {
    useViewerStore.getState().addTab(tab);
    useViewerStore.getState().setZoom("t1", 2.0);
    expect(useViewerStore.getState().tabs[0].zoom).toBe(2.0);
  });
});
```

- [ ] **Run — verify FAIL**

```bash
npm test -- viewer-store
```

Expected: `Cannot find module '../store/viewer'`.

- [ ] **Create `src/store/viewer.ts`**

```typescript
import { create } from "zustand";
import { DocumentInfo } from "../lib/ipc";

export interface TabState {
  tabId:     string;
  path:      string;
  info:      DocumentInfo;
  pageIndex: number;
  zoom:      number;
  rotation:  number;  // 0 | 90 | 180 | 270
  dirty:     boolean;
}

interface ViewerStore {
  tabs:        TabState[];
  activeTabId: string | null;
  addTab:      (tab: TabState) => void;
  removeTab:   (tabId: string) => void;
  setActiveTab:(tabId: string) => void;
  setPage:     (tabId: string, pageIndex: number) => void;
  setZoom:     (tabId: string, zoom: number) => void;
  setRotation: (tabId: string, rotation: number) => void;
  setDirty:    (tabId: string, dirty: boolean) => void;
  activeTab:   () => TabState | null;
}

export const useViewerStore = create<ViewerStore>((set, get) => ({
  tabs: [], activeTabId: null,

  addTab: (tab) => set((s) => ({ tabs: [...s.tabs, tab], activeTabId: tab.tabId })),

  removeTab: (tabId) => set((s) => {
    const tabs = s.tabs.filter((t) => t.tabId !== tabId);
    const activeTabId = s.activeTabId === tabId
      ? (tabs.at(-1)?.tabId ?? null) : s.activeTabId;
    return { tabs, activeTabId };
  }),

  setActiveTab: (tabId) => set({ activeTabId: tabId }),

  setPage: (tabId, pageIndex) =>
    set((s) => ({ tabs: s.tabs.map((t) => t.tabId === tabId ? { ...t, pageIndex } : t) })),

  setZoom: (tabId, zoom) =>
    set((s) => ({ tabs: s.tabs.map((t) => t.tabId === tabId ? { ...t, zoom } : t) })),

  setRotation: (tabId, rotation) =>
    set((s) => ({ tabs: s.tabs.map((t) => t.tabId === tabId ? { ...t, rotation } : t) })),

  setDirty: (tabId, dirty) =>
    set((s) => ({ tabs: s.tabs.map((t) => t.tabId === tabId ? { ...t, dirty } : t) })),

  activeTab: () => {
    const { tabs, activeTabId } = get();
    return tabs.find((t) => t.tabId === activeTabId) ?? null;
  },
}));
```

- [ ] **Run — verify PASS**

```bash
npm test -- viewer-store
```

Expected: 4 passed.

- [ ] **Commit**

```bash
git add src/store/viewer.ts src/__tests__/viewer-store.test.ts
git commit -m "feat: zustand viewer store with tests"
```

---

### Task 1.8: PageCanvas component

- [ ] **Create `src/components/PageCanvas.tsx`**

```tsx
import { useEffect, useRef, useCallback } from "react";
import { renderPage, PageLink } from "../lib/ipc";
import { pdfToCanvas } from "../lib/coords";

interface Props {
  tabId:         string;
  pageIndex:     number;
  pageHeightPts: number;
  zoom:          number;
  links:         PageLink[];
  onLinkClick:   (link: PageLink) => void;
}

export function PageCanvas({ tabId, pageIndex, pageHeightPts, zoom, links, onLinkClick }: Props) {
  const pageRef  = useRef<HTMLCanvasElement>(null);
  const annotRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    let cancelled = false;
    const dpr = window.devicePixelRatio || 1;

    renderPage(tabId, pageIndex, zoom, dpr).then(([bytes, meta]) => {
      if (cancelled) return;
      const canvas = pageRef.current;
      const annot  = annotRef.current;
      if (!canvas) return;

      canvas.width  = meta.width;
      canvas.height = meta.height;
      canvas.style.width  = `${meta.width  / dpr}px`;
      canvas.style.height = `${meta.height / dpr}px`;

      const ctx = canvas.getContext("2d")!;
      // bytes is number[] from JSON — convert to Uint8ClampedArray
      ctx.putImageData(new ImageData(new Uint8ClampedArray(bytes), meta.width, meta.height), 0, 0);

      if (annot) {
        annot.width  = meta.width;
        annot.height = meta.height;
        annot.style.width  = canvas.style.width;
        annot.style.height = canvas.style.height;
      }
    });

    return () => { cancelled = true; };
  }, [tabId, pageIndex, zoom]);

  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!links.length) return;
    const rect = annotRef.current!.getBoundingClientRect();
    const dpr  = window.devicePixelRatio || 1;
    const cx   = (e.clientX - rect.left) * dpr;
    const cy   = (e.clientY - rect.top)  * dpr;

    for (const link of links) {
      const tl = pdfToCanvas({ x: link.rect[0], y: link.rect[3] }, pageHeightPts, zoom, dpr);
      const br = pdfToCanvas({ x: link.rect[2], y: link.rect[1] }, pageHeightPts, zoom, dpr);
      if (cx >= tl.x && cx <= br.x && cy >= tl.y && cy <= br.y) {
        onLinkClick(link);
        break;
      }
    }
  }, [links, pageHeightPts, zoom, onLinkClick]);

  return (
    <div className="relative inline-block shadow-lg">
      <canvas ref={pageRef} className="block" />
      <canvas ref={annotRef} className="absolute inset-0" onClick={handleClick} />
    </div>
  );
}
```

- [ ] **Commit**

```bash
git add src/components/PageCanvas.tsx
git commit -m "feat: PageCanvas — renders bitmap and handles link clicks"
```

---

### Task 1.9: Viewer toolbar, TOC, thumbnails, and App wiring

- [ ] **Create `src/components/ViewerToolbar.tsx`**

```tsx
import { useViewerStore } from "../store/viewer";

const ZOOMS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0];

export function ViewerToolbar({ tabId }: { tabId: string }) {
  const tab        = useViewerStore((s) => s.tabs.find((t) => t.tabId === tabId));
  const setPage    = useViewerStore((s) => s.setPage);
  const setZoom    = useViewerStore((s) => s.setZoom);
  const setRotation= useViewerStore((s) => s.setRotation);

  if (!tab) return null;
  const { pageIndex, zoom, rotation, info } = tab;

  return (
    <div className="flex h-11 items-center gap-2 border-b border-slate-200 bg-white px-4 text-sm text-slate-600">
      <button onClick={() => setPage(tabId, pageIndex - 1)} disabled={pageIndex === 0}
        className="rounded px-2 py-1 hover:bg-slate-100 disabled:opacity-30">‹</button>
      <span className="min-w-20 text-center">{pageIndex + 1} / {info.page_count}</span>
      <button onClick={() => setPage(tabId, pageIndex + 1)} disabled={pageIndex >= info.page_count - 1}
        className="rounded px-2 py-1 hover:bg-slate-100 disabled:opacity-30">›</button>

      <div className="mx-2 h-4 w-px bg-slate-200" />

      <button onClick={() => setZoom(tabId, ZOOMS.slice().reverse().find((z) => z < zoom) ?? zoom)}
        className="rounded px-2 py-1 hover:bg-slate-100">−</button>
      <span className="min-w-14 text-center">{Math.round(zoom * 100)}%</span>
      <button onClick={() => setZoom(tabId, ZOOMS.find((z) => z > zoom) ?? zoom)}
        className="rounded px-2 py-1 hover:bg-slate-100">+</button>

      <div className="mx-2 h-4 w-px bg-slate-200" />

      <button onClick={() => setRotation(tabId, (rotation + 90) % 360)}
        className="rounded px-2 py-1 hover:bg-slate-100">↻</button>

      <span className="ml-auto max-w-xs truncate text-slate-400">
        {info.title ?? tabId}
      </span>
    </div>
  );
}
```

- [ ] **Create `src/components/TocSidebar.tsx`**

```tsx
import { useEffect, useState } from "react";
import { getToc, TocEntry } from "../lib/ipc";

interface Props { tabId: string; onSelect: (page: number) => void }

export function TocSidebar({ tabId, onSelect }: Props) {
  const [entries, setEntries] = useState<TocEntry[]>([]);

  useEffect(() => {
    getToc(tabId).then(setEntries).catch(() => setEntries([]));
  }, [tabId]);

  if (!entries.length) return (
    <div className="flex h-full items-center justify-center text-xs text-slate-400">No outline</div>
  );

  return (
    <div className="h-full overflow-y-auto py-2">
      {entries.map((e, i) => (
        <button key={i} onClick={() => onSelect(e.page_index)}
          style={{ paddingLeft: `${(e.level + 1) * 12}px` }}
          className="block w-full py-1 pr-3 text-left text-sm text-slate-700 hover:bg-slate-100">
          {e.title}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Create `src/components/ThumbnailStrip.tsx`**

```tsx
import { useEffect, useRef } from "react";
import { renderPage } from "../lib/ipc";

function Thumb({ tabId, index, active, onSelect }: {
  tabId: string; index: number; active: boolean; onSelect: () => void;
}) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    renderPage(tabId, index, 0.15, 1).then(([bytes, meta]) => {
      const c = ref.current;
      if (!c) return;
      c.width = meta.width; c.height = meta.height;
      c.getContext("2d")!.putImageData(
        new ImageData(new Uint8ClampedArray(bytes), meta.width, meta.height), 0, 0
      );
    });
  }, [tabId, index]);

  return (
    <button onClick={onSelect}
      className={`flex flex-col items-center gap-1 rounded p-1 ${active ? "ring-2 ring-blue-400" : "hover:bg-slate-200"}`}>
      <canvas ref={ref} className="rounded border border-slate-200" style={{ width: 80 }} />
      <span className="text-xs text-slate-400">{index + 1}</span>
    </button>
  );
}

export function ThumbnailStrip({ tabId, pageCount, activeIndex, onSelect }: {
  tabId: string; pageCount: number; activeIndex: number; onSelect: (i: number) => void;
}) {
  return (
    <div className="flex h-full flex-col gap-1 overflow-y-auto bg-slate-100 p-2">
      {Array.from({ length: pageCount }, (_, i) => (
        <Thumb key={i} tabId={tabId} index={i} active={i === activeIndex} onSelect={() => onSelect(i)} />
      ))}
    </div>
  );
}
```

- [ ] **Replace `src/App.tsx`**

```tsx
import { useState, useCallback } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { openDocument, getLinks, closeDocument, PageLink } from "./lib/ipc";
import { useViewerStore } from "./store/viewer";
import { PageCanvas } from "./components/PageCanvas";
import { ViewerToolbar } from "./components/ViewerToolbar";
import { TocSidebar } from "./components/TocSidebar";
import { ThumbnailStrip } from "./components/ThumbnailStrip";

let counter = 0;
const newId = () => `tab-${++counter}`;

export default function App() {
  const { tabs, activeTabId, addTab, removeTab, setActiveTab, setPage, activeTab } = useViewerStore();
  const [links, setLinks] = useState<PageLink[]>([]);
  const tab = activeTab();

  const handleOpen = useCallback(async () => {
    const path = await open({ filters: [{ name: "PDF", extensions: ["pdf"] }] });
    if (!path || typeof path !== "string") return;
    const tabId = newId();
    const info  = await openDocument(path, tabId);
    addTab({ tabId, path, info, pageIndex: 0, zoom: 1.0, rotation: 0, dirty: false });
    setLinks(await getLinks(tabId, 0));
  }, [addTab]);

  const goToPage = useCallback(async (pageIndex: number) => {
    if (!tab) return;
    setPage(tab.tabId, pageIndex);
    setLinks(await getLinks(tab.tabId, pageIndex));
  }, [tab, setPage]);

  const handleLink = useCallback((link: PageLink) => {
    if (link.target.type === "Page") goToPage(link.target.value);
    else window.open(link.target.value, "_blank");
  }, [goToPage]);

  return (
    <div className="flex h-screen flex-col bg-slate-100">
      {/* Tab bar */}
      <div className="flex items-center gap-1 border-b border-slate-200 bg-white px-2 pt-1">
        {tabs.map((t) => (
          <button key={t.tabId} onClick={() => setActiveTab(t.tabId)}
            className={`flex items-center gap-2 rounded-t px-3 py-1.5 text-sm ${
              t.tabId === activeTabId ? "bg-slate-100 text-slate-800" : "text-slate-500 hover:bg-slate-50"
            }`}>
            {t.info.title ?? t.path.split(/[\\/]/).pop()}
            <span onClick={(e) => { e.stopPropagation(); closeDocument(t.tabId); removeTab(t.tabId); }}
              className="rounded px-1 text-xs text-slate-400 hover:bg-slate-200">✕</span>
          </button>
        ))}
        <button onClick={handleOpen}
          className="ml-2 rounded px-3 py-1.5 text-sm text-slate-500 hover:bg-slate-100">
          + Open PDF
        </button>
      </div>

      {tab ? (
        <>
          <ViewerToolbar tabId={tab.tabId} />
          <div className="flex flex-1 overflow-hidden">
            <div className="w-44 border-r border-slate-200 bg-white">
              <TocSidebar tabId={tab.tabId} onSelect={goToPage} />
            </div>
            <div className="flex flex-1 items-start justify-center overflow-auto bg-slate-300 p-8">
              <PageCanvas
                tabId={tab.tabId}
                pageIndex={tab.pageIndex}
                pageHeightPts={tab.info.page_height_pts}
                zoom={tab.zoom}
                links={links}
                onLinkClick={handleLink}
              />
            </div>
            <div className="w-28 border-l border-slate-200">
              <ThumbnailStrip
                tabId={tab.tabId}
                pageCount={tab.info.page_count}
                activeIndex={tab.pageIndex}
                onSelect={goToPage}
              />
            </div>
          </div>
        </>
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 text-slate-400">
          <p className="text-lg">No PDF open</p>
          <button onClick={handleOpen}
            className="rounded-lg bg-blue-600 px-6 py-2 text-sm text-white hover:bg-blue-500">
            Open PDF
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Run the app**

```bash
npm run tauri dev
```

Expected: app opens. Click "Open PDF", select any PDF. Page renders. Thumbnails appear. TOC loads if the PDF has one. Clicking page links navigates or opens URLs. Zoom controls work.

- [ ] **Commit**

```bash
git add src/
git commit -m "feat: viewer layout — toolbar, toc, thumbnails, navigation, links"
```

---

### Task 1.10: IPC throughput benchmark

- [ ] **Create `src/__tests__/benchmark.test.ts`**

```typescript
import { describe, it, expect } from "vitest";
import { pdfToCanvas, canvasToPdf } from "../lib/coords";

// Coordinate math must be sub-millisecond — it runs on every mouse event.
describe("coord transform throughput", () => {
  it("10,000 round-trips complete in under 5ms", () => {
    const start = performance.now();
    for (let i = 0; i < 10_000; i++) {
      canvasToPdf(pdfToCanvas({ x: i % 595, y: i % 842 }, 842, 1.5, 2), 842, 1.5, 2);
    }
    expect(performance.now() - start).toBeLessThan(5);
  });
});
```

- [ ] **Run**

```bash
npm test -- benchmark
```

Expected: passes in < 5ms.

- [ ] **Manual IPC benchmark**
  - Open app with `npm run tauri dev`
  - Open DevTools → Performance → Record
  - Press ‹ › rapidly for 10 page turns
  - Stop recording
  - Measure time from click to canvas `putImageData` call
  - **If any page turn > 50ms:** the JSON serialization of the bitmap bytes is the bottleneck.
    Switch `renderPage` to use Tauri's `tauri::ipc::Response` with binary body, and in JS
    receive as `ArrayBuffer` via `invoke` with `{ responseType: ResponseType.Binary }`.
    Re-benchmark before proceeding to Phase 2.

- [ ] **Commit**

```bash
git add src/__tests__/benchmark.test.ts
git commit -m "test: coord transform benchmark; document ipc latency gate"
```

- [ ] **Tag phase complete**

```bash
git tag phase-1-complete
git push origin main --tags
```

---

**Phase 1 gate:** Open any PDF. Navigate pages, zoom, rotate, click TOC entries, click links. Thumbnails render. Page turn latency < 50ms on A4 at 150 DPI. `npm test` and `cargo test` both pass.

---

## Phase 2 — Annotation Engine (outline)

> Separate plan written when Phase 1 gate passes.

**Scope:** Canvas annotation layer. All 13 tool types: View, Select, Highlight, Underline, Strikethrough, Freehand, Text Box, Sticky Note, Rectangle, Circle, Line, Arrow, Sign. Color picker, stroke width. Undo/redo (Zustand, 30 steps per tab, snapshot-based). Annotation persistence via pdfium-render write-back. AcroForm field display (read-only overlay). Multi-document tabs (Phase 1 already wires them). Split view. PDF save. Unsaved changes guard.

**Prerequisite before planning Phase 2:** Build a throwaway Rust binary in `src-tauri/src/bin/annot_probe.rs` that opens a test PDF, adds one of each of the 13 annotation types via pdfium-render, saves, and reopens to verify they survived. Run it against 3 real-world PDFs. Any type that fails write-back needs a decision: implement via `lopdf` content stream injection, or cut from Phase 2.

**Key new files:**
- `src/components/AnnotationCanvas.tsx` — drawing layer (sits above PageCanvas)
- `src/components/AnnotationToolbar.tsx` — tool picker, color, stroke width
- `src/store/annotations.ts` — per-tab annotation state + undo stack
- `src-tauri/src/commands/annotations.rs` — write-back Tauri commands
- `src/components/SplitView.tsx` — two-pane layout

---

## Phase 3 — App Shell & Library (outline)

> Separate plan written when Phase 2 gate passes.

**Scope:** Home dashboard (hero banner, tool grid, search, drop zone, recently used). SQLite-backed library (file tracking, favorites, trash, folders). Dark/light theme via CSS custom properties. Auto-updater (`tauri-plugin-updater`). `i18next` wired to English strings. Crash reporter (tauri-plugin-log surface in ErrorBoundary).

**Key new files:** `src/pages/Home.tsx`, `src/pages/Library.tsx`, `src/components/ToolGrid.tsx`, `src-tauri/src/commands/library.rs`, `src-tauri/src/commands/settings.rs`.

---

## Phase 4 — Organize Tools (outline)

> Separate plan.

**Scope:** Merge, Split, Rotate, Remove pages, Reorder, Excerpt. Pattern per tool: one Rust command + one React panel + thumbnail grid. All use pdfium-render for page manipulation and lopdf for page tree surgery where PDFium's API is insufficient.

---

## Phase 5 — Edit Tools (outline)

> Separate plan.

**Scope:** Compress, Add/Remove password, Watermark, Add page numbers, Headers/footers, Crop, Scale pages, Change metadata, Bookmarks, Page labels, Redact, Flatten, Remove annotations, Add image, N-up, Batch. Each tool is independent; ship incrementally as each is complete.

---

## Phase 6 — AcroForm & Signing (outline)

> Separate plan.

**Scope:** AcroForm interactive fill/export/unlock (builds on Phase 2 read-only overlay). PDF signing via `rasn-cms` + `reqwest` for TSA HTTP. Signature validation. PDF/A conversion. Sanitize.

---

## Phase 7 — Convert & Advanced Tools (outline)

> Separate plan. Validate tesseract-rs bundling on all three platforms before writing this plan.

**Scope:** OCR, Image ↔ PDF, SVG → PDF, PDF → CSV, PDF → Excel (basic table extraction), Compare (pixel diff + text diff), Font info.

---

## Self-review notes

- `PageRender` struct (not a tuple) used consistently in Rust `state.rs`, `commands/pdf.rs`, and TypeScript `ipc.ts`. Avoids Specta tuple serialization ambiguity. ✓
- `collect_toc_flat` in `engine.rs` uses an iterative stack inside a recursive helper to avoid lifetime issues with recursive PDFium bookmark borrows. The `walk` closure captures `stack` by mutable reference. If the borrow checker rejects this, convert to an explicit `Vec<_>` traversal loop. ✓ (flag)
- `pdfToCanvas` / `canvasToPdf` names match exactly between `coords.ts`, `PageCanvas.tsx`, and `benchmark.test.ts`. ✓
- BGRA vs RGBA byte order: flagged inline in `engine.rs`. Must be verified manually on first run — wrong byte order shows as blue/red channel swap. ✓
- Phase 2 prerequisite (annotation write-back probe) is explicit and blocks Phase 2 planning. ✓
