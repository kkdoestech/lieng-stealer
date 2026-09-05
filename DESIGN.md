# DESIGN.MD: TACTICAL RADAR ANALYTICS TERMINAL SPECIFICATION

## 1. Design Persona & Visual Identity ("EPL SCOPE" Aesthetic)
**LIÊNG SCOPE** is engineered as a high-precision, tactical radar analytics terminal for game-theoretic analysis in Vietnamese Liêng. The aesthetic directly mirrors elite sports radar and military telemetry systems (modeled on the visual discipline of *EPL SCOPE*).

### Strict Prohibitions (Zero Consumer AI Tropes)
- **NO purple or violet gradients**: Eliminate all generic AI gradient blends.
- **NO robot, sparkle, or emoji decorations**: No `🤖`, `✨`, `⚡`, `🔮`, or friendly chat avatars.
- **NO conversational chat interfaces**: All outputs, including LLM analysis, must be formatted as raw mathematical telemetry, tactical intelligence drawers, and structured data tables.
- **NO rounded "bubble" cards**: All UI containers must feature crisp, rectangular or micro-radius geometries (maximum 2px–4px border radius).

---

## 2. Color Palette & CSS Variables

| Token | Hex / Value | Purpose |
| :--- | :--- | :--- |
| `--bg-canvas` | `#050705` | Pitch tactical black canvas background. |
| `--bg-grid` | `rgba(34, 197, 94, 0.03)` | 24px subtle radar grid lines overlaying canvas. |
| `--bg-surface` | `#101511` | Primary container surface (dark matte charcoal). |
| `--bg-surface-hover`| `#151C17` | Hover state for interactive rows, panels, and chips. |
| `--bg-surface-input`| `#0A0E0B` | Deep contrast inset background for data entry fields. |
| `--border-base` | `#1C261F` | Default panel and table borders (tactical green-gray). |
| `--border-highlight`| `#22C55E` | Active, focused, or positive threshold borders. |
| `--border-subtle` | `#141C16` | Internal dividers and secondary table gridlines. |
| `--accent-green` | `#22C55E` | Radar terminal green (brand highlight, live status, raise action). |
| `--accent-green-muted` | `#153820` | Low-key tactical fill for badges, chips, and table highlights. |
| `--accent-green-glow` | `rgba(34, 197, 94, 0.12)` | Subtle radar illumination for high-value targets and active inputs. |
| `--accent-red` | `#EF4444` | Negative EV indicator and fold signal. |
| `--accent-red-muted` | `#2A1215` | Low-key background for check/fold states. |
| `--text-white` | `#FFFFFF` | Primary headers, values, and top-tier metrics. |
| `--text-green` | `#22C55E` | Highlights, positive EV, and active indicators. |
| `--text-muted` | `#85998B` | Monospaced labels, descriptions, and telemetry metadata. |
| `--text-dim` | `#4B5E51` | Inactive markers, table headers, and footnote details. |

---

## 3. Typography & Micro-Interactions

### Monospaced Precision
- **Primary Font**: `'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace`.
- All labels, data readouts, table cells, metric values, preset tags, and action buttons must strictly render in monospace.
- Uppercase text transformations applied to all structural headers and telemetry labels (`text-transform: uppercase`, `letter-spacing: 0.06em`).

### Tactical Controls
- **Action Buttons**: Solid rectangular blocks (`[ EXECUTE SOLVER ]`) with high-contrast `#22C55E` background or crisp bordered outlines, with instant hover transitions and no bouncy animations.
- **Form Inputs**: Inset dark matte boxes (`#0A0E0B`) with subtle border `#1C261F`, transitioning on focus to solid `#22C55E` border and razor-thin glow (`0 0 0 1px #22C55E`).
- **Preset Chips**: Compact monospaced badges (`50k`, `100k`, `0.5x Pot`, `1.0x Pot`) for instant tactical parameter switching.

---

## 4. UI Architecture & Structural Hierarchy

### 4.1 Header & System Telemetry Status
- **Title Block**: Dual-tone typographic logo:
  - `LIÊNG` in bold crisp white (`#FFFFFF`).
  - `SCOPE` in bold radar green (`#22C55E`).
- **Telemetry Tag**: Right-aligned live solver status pill:
  - Pulsing radar dot (`#22C55E`) with text `● LIVE SOLVER // 455 CLASSES LOADED`.
- **System Subtitle**: `GTO SOLVER & COMBINATORIAL ENGINE`.

### 4.2 Left Panel: Control Telemetry
- Dedicated control deck organized into distinct technical modules:
  - `CURRENT POT (VND)` with preset chips (`50k`, `100k`, `200k`, `500k`).
  - `BET / RAISE SIZING` with multiplier chips (`0.5x Pot`, `1.0x Pot`, `2.0x Pot`).
  - `OPPONENT FOLD FREQUENCY` slider with real-time percentage readout and calibrated anchor points (`0% Calling Station`, `50% GTO Median`, `100% Extreme Fold`).
  - `PLAYER HAND (3 CARDS)` with quick-select canonical holding presets.
  - Action trigger: `[ EXECUTE SOLVER ]`.

### 4.3 Right Panel: Strategic HUD & Heatmap
- **Decision Verdict Banner**:
  - `ACTION: RAISE / ALL-IN` in radar green (`#22C55E`) or `ACTION: CHECK / FOLD` in tactical muted red.
  - Accompanied by player holding evaluation, exact canonical class, and net EV readout.
- **4-Card Metrics HUD**:
  1. `RANGE COVERAGE`: Percentage of 22,100 combinations profitable to raise.
  2. `SHOWDOWN EQUITY`: Mathematical win-rate vs. random holding distribution.
  3. `EXPECTED VALUE`: Net gain/loss in VND across calling and folding branches.
  4. `PURE BLUFF THRESHOLD`: Break-even fold equity required to profitably push air (0 points).
- **Range Breakdown Matrix**:
  - Structured matrix summarizing performance across the 4 core Liêng categories:
    - `SÁP` (Three of a Kind, 13 classes / 52 combinations)
    - `LIÊNG` (Straight / Sequence, 12 classes / 768 combinations)
    - `ĐĨ` (Three Face Cards, 6 classes / 288 combinations)
    - `ĐIỂM` (Point Totals Modulo 10, 424 classes / 20,992 combinations)
- **Top Canonical Holdings Table**:
  - High-density monospaced table displaying top playable holdings with equity, EV, and combo multiplicity.
- **Mathematical Telemetry Notes (Collapsible Drawer)**:
  - Replaces generic AI commentary with a tactical drawer titled `[ + MATHEMATICAL TELEMETRY NOTES ]`.
  - When expanded, displays technical game-theoretic evaluation without conversational fluff.

