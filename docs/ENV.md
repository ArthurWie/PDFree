# Environment Variables and Local Setup

---

## Environment Variables

### `PDFREE_STATE_DIR`
| | |
|---|---|
| **Purpose** | Directory where `library.json` (the document library state) is stored |
| **Required** | No |
| **Default** | `~/.pdfree/` (user home directory) |
| **Example** | `PDFREE_STATE_DIR=/tmp/pdfree-test` |
| **Used in** | `library_page.py` — `_STATE_PATH` |
| **Notes** | The directory must already exist or be creatable. The file is always named `library.json` inside this directory. Useful for tests (isolation) and for non-standard installs (e.g. network drives, portable setups). |

**Code reference:**
```python
# library_page.py
_STATE_PATH = (
    Path(os.environ.get("PDFREE_STATE_DIR", Path.home() / ".pdfree"))
    / "library.json"
)
```

---

### `sys._MEIPASS` (PyInstaller runtime — not a real env var)
| | |
|---|---|
| **Purpose** | Base path for bundled resources when running as a PyInstaller `.exe` or `.app` |
| **Required** | No (only set by PyInstaller at runtime) |
| **Default** | Falls back to `os.path.dirname(os.path.abspath(__file__))` in development |
| **Used in** | `main.py` — `resource_path()` |
| **Notes** | Not set by users. Controls where `LOGO.svg` and other data files are resolved. |

**Code reference:**
```python
# main.py
def resource_path(relative_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)
```

---

## No `.env` File

PDFree does not use a `.env` file. There are no secrets, API keys, or credentials. The only runtime-configurable variable is `PDFREE_STATE_DIR`, which can be set in the shell before launching the app.

---

## Local Development Setup

### Prerequisites

| Tool | Minimum Version | Notes |
|---|---|---|
| Python | 3.11 | 3.10 may work but is not tested; 3.12+ is fine |
| pip | any | Comes with Python |
| Git | any | For cloning |
| (Windows) Visual C++ Build Tools | latest | May be needed by some pip packages |
| (macOS) Xcode Command Line Tools | latest | `xcode-select --install` |

### 1. Clone the repository

```bash
git clone https://github.com/ArthurWie/PDFree.git
cd PDFree
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:
```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Windows (Command Prompt)
.venv\Scripts\activate.bat

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

`requirements.txt` installs:
```
PySide6>=6.7
pymupdf>=1.24
pypdf>=4.0
Pillow>=10.0
pdfplumber>=0.11.0
pytest>=8.0
```

### 4. Run the application

```bash
python main.py
```

### 5. Run the tests

```bash
pytest tests/
```

---

## macOS Quick Setup (alternative)

```bash
# Install Homebrew if not present
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.11+
brew install python@3.11

# Then follow steps 1–5 above using python3.11 instead of python
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3.11 main.py
```

---

## Building a Release Binary

### Windows — `.exe` installer

Requires PyInstaller (not in `requirements.txt` — install separately):
```bash
pip install pyinstaller
pyinstaller PDFree.spec
```
Output: `dist/PDFree/` folder containing `PDFree.exe` + `_internal/`.

To create the installer `.exe`, open `PDFree.iss` in Inno Setup 6 and click Build, or run:
```bash
iscc PDFree.iss
```
Output: `dist/PDFree_Setup.exe`.

### macOS — `.app` bundle

```bash
pip install pyinstaller
bash build-mac.sh
```
Output: `dist/PDFree.app` (and optionally `dist/PDFree.dmg` if `hdiutil` is available).

Alternatively, build manually:
```bash
pyinstaller PDFree-mac.spec
```

---

## Troubleshooting Setup

See `docs/TROUBLESHOOTING.md` for known issues.

Common quick fixes:
- **`ModuleNotFoundError: No module named 'fitz'`** — run `pip install pymupdf` (not `fitz` directly).
- **`ModuleNotFoundError: No module named 'PySide6'`** — your venv may not be activated.
- **pytest not found** — run `pip install pytest` or reinstall from requirements.
- **macOS: app won't open (Gatekeeper)** — right-click → Open, or run `xattr -cr PDFree.app` in Terminal.
- **Windows: SmartScreen warning** — click "More info" → "Run anyway", or code-sign the `.exe`.
