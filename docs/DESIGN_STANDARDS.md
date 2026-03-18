# Design Standards

## Principles

- Clarity over decoration. Every visual element must serve a function.
- Consistency over novelty. Reuse existing tokens; do not invent new ones.
- No inline hardcoded colors, sizes, or icon paths — always reference the design system modules.

## Colors

All colors come from `colors.py`. Do not define color literals anywhere else.

### Semantic usage

| Token | Use |
|---|---|
| `BG` | App and panel backgrounds |
| `WHITE` / `CARD_BG` | Card and surface backgrounds |
| `SIDEBAR_BG` | Left-side navigation panels |
| `G200`–`G400` | Borders, dividers, disabled states |
| `G500`–`G700` | Secondary text, icons |
| `G800`–`G900` | Primary text |
| `BLUE` | Primary action buttons, links, selections |
| `BLUE_ACCENT` / `BLUE_HOVER` | Hover state for primary actions |
| `BLUE_DIM` / `BLUE_MED` | Highlighted or selected row backgrounds |
| `GREEN` | Confirm, success, safe action |
| `GREEN_HOVER` | Hover state for confirm actions |
| `RED` | Destructive or error states |
| `SOON_TXT` / `SOON_BG` | Disabled "coming soon" items |

### Adding colors

Only add a token to `colors.py` when the same value is used in three or more places. Otherwise use an existing token or derive from it with Qt's color API.

## Icons

All icons come from `icons.py` (Lucide set). Use `svg_icon()` for buttons and actions; use `svg_pixmap()` for labels and painted elements.

- Default icon size: 16 px in toolbars, 20 px elsewhere.
- Default icon color: `G700` (`#374151`) for neutral icons; `BLUE` for primary-action icons; `G400` for disabled icons.
- Never embed raw SVG strings outside `icons.py`. Add new icons to `_SVGS` in `icons.py`.

## Layout and Spacing

Use a 4 px base unit. Prefer multiples of 4 for all margins, paddings, and gaps.

| Level | Value |
|---|---|
| Tight (icon gap, inline) | 4–8 px |
| Component internal padding | 8–12 px |
| Section spacing | 16–24 px |
| Panel/page margins | 24–32 px |

- Use `QVBoxLayout` / `QHBoxLayout` with `setContentsMargins` and `setSpacing`; never use fixed pixel geometry unless rendering a PDF page.
- Minimum click target: 32 × 32 px.

## Typography

PySide6 inherits the system font. Do not set custom font families.

| Role | Size | Weight |
|---|---|---|
| Body / default | system default | regular |
| Label / caption | system default − 1 pt | regular |
| Heading / section title | system default + 2 pt | bold |
| Monospace (path display) | monospace family, default size | regular |

## Components

### Buttons

- Primary (blue fill): `BLUE` background, white text, `BLUE_HOVER` on hover.
- Secondary (outline): `G200` border, `G800` text, `G100` background on hover.
- Destructive: `RED` background or `RED` text on secondary style.
- No text-only buttons for primary actions — always pair with an icon or clear label.

### Cards and Panels

- Background: `CARD_BG` (`#FFFFFF`).
- Border: 1 px solid `G200`.
- Border-radius: 8 px.
- Drop shadow: only on modals and floating overlays, not on inline cards.

### Tool Cards (home screen)

- Use the `SOON_BG` / `SOON_TXT` pattern for unavailable tools — do not hide them.
- Icon size: 24 px, color `BLUE` for available, `G400` for unavailable.

### Scrollbars

- Style via QSS using `THUMB_BG` for the handle and `G100` for the track.

## Motion and Feedback

- No animations unless triggered by user action (drag, progress).
- Progress: use `QProgressBar` with `BLUE` fill, not custom-painted bars.
- Transient status messages: display in a status bar or inline label, not a modal.
- Error messages for user-recoverable errors: inline, in `RED`, near the offending control.

## QSS Rules

- Define QSS strings in the widget that owns the style, not in a global stylesheet unless the rule applies to every instance of that widget class.
- Never override the system palette for text colors — only set backgrounds and borders in QSS.
- Test QSS on both light-mode Windows 11 and macOS before merging.

## When Adding a New Screen or Tool

1. Reuse an existing layout from a similar tool as a starting point.
2. All colors and icons must resolve to tokens from `colors.py` and `icons.py`.
3. Include a screenshot in the PR body (required by `PR_STANDARDS.md`).
