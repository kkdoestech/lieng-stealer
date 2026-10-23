# DESIGN.MD: WEB UI SPECIFICATION

## 1. Look & Principles
The web UI of **LIÊNG SCOPE** is a plain tool page: inputs on the left, results on the right. It uses the **Ayu Dark** color palette (as in the VS Code "Ayu Dark Bordered" theme): one dark background, with regions split by 1px lines. There is no visual concept beyond that. It should look like something a person built for their own use.

### Prohibitions
- **No concept or theme language**: no "terminal", "radar", "HUD", "telemetry" or "engine" styling or copy.
- **No effects**: no glow, `text-shadow`, gradients, background grids, noise or blurred shapes.
- **No motion**: no pulsing dots, spinners, entrance animations or hover lifts. Hover changes background color only.
- **No decoration**: no emoji, robot or sparkle icons, no chat bubbles, no purple or violet.
- **No cards by default**: sections are separated by spacing and 1px `--line` borders. Only controls, the error message and the open notes panel get a box.
- **No pills**: radius is `3px` everywhere.
- **No empty labels**: no kicker tags, section IDs (`SEC-01`) or badges that carry no information. No fake status (e.g. a "LIVE" indicator that checks nothing).

---

## 2. Color Tokens (`frontend/src/index.css`)

| Token | Value | Use |
| :--- | :--- | :--- |
| `--bg` | `#0B0E14` | Page background. |
| `--bg-input` | `#0D1017` | Text and number inputs. |
| `--bg-hover` | `#141922` | Hover on buttons and table rows. |
| `--bg-active` | `#1F2530` | Selected preset / language. |
| `--line` | `#232834` | Section dividers, table rows. |
| `--line-control` | `#3D4452` | Borders of inputs and buttons. |
| `--text` | `#BFBDB6` | Body text. |
| `--text-strong` | `#E6E1CF` | Headings, values, input text. |
| `--muted` | `#8A9199` | Secondary text (6:1 contrast on `--bg`). |
| `--accent` | `#E6B450` | Focus ring, slider, "Run solver" button. Nothing else. |
| `--accent-hover` | `#D9A63F` | Hover state of the "Run solver" button. |
| `--good` | `#AAD94C` | Raise, +EV. |
| `--bad` | `#F07178` | Fold, −EV, errors. |
| `--zone-good` | `--good` at 45% (`color-mix`) | Profitable stretches of the profit map. |
| `--zone-bad` | `--bad` at 20% (`color-mix`) | The rest of the profit map's track. |

- Green and red appear only where they mean raise/fold or +/−EV.
- `App.css` uses tokens only: no hex or `rgba()` literals outside `index.css`.
- Selected presets use `--bg-active` with a `--muted` border, not the accent.
- Don't use Ayu's darker UI greys (e.g. `#565B66`) for text: they fail contrast.

---

## 3. Typography
- **One family**: the system UI stack (`system-ui, -apple-system, "Segoe UI", Roboto, Ubuntu, …`). No web fonts. Monospace only for real code.
- **Sizes**: base `15px / 1.5`. Labels `0.93rem`. Smallest text `0.87rem` (13px), never smaller.
- **Case**: sentence case, normal letter spacing. The product name `LIÊNG SCOPE` and game category names (`SÁP`, `LIÊNG`, `ĐĨ`, `ĐIỂM`) stay as written.
- **Numbers**: `font-variant-numeric: tabular-nums`.
- **Hierarchy**: section headings `1rem / 600`. The verdict and its EV are `1.25rem / 600`. Nothing bigger.

---

## 4. Controls
- **Sizes**: buttons and presets at least `32px` tall, inputs `36px`, the main button `40px`.
- **Focus**: `2px solid var(--accent)` outline, offset `1px`, on every control (`:focus-visible` in `index.css`). Never remove an outline without a replacement.
- **Labels**: every input has a `<label htmlFor>`.
- **Number inputs**: a `−` / `+` stepper (36px buttons) around the field. Browser spin arrows hidden. Step `10,000`, minimum `1,000`.
- **Slider**: native `<input type="range">` with `accent-color`.
- **Presets**: plain bordered buttons; the active one uses `--bg-active`.

---

## 5. Layout
- **Header**: `LIÊNG SCOPE` and the subtitle on the left, the EN / VI toggle on the right, 1px line below.
- **Columns**: inputs `340px` on the left with a 1px divider, results `1fr` on the right. Max width `1360px`, 24px side padding.
- **Results, in order**:
  1. Verdict: recommended action (green or red), hand, canonical class, EV in VND, the fold-frequency range where raising is +EV.
  2. Summary: four rows of label, value and note (range coverage, showdown equity, expected value, bluff break-even).
  3. Coverage by category table.
  4. Most profitable hands table.
  5. Analysis notes, collapsed by default.
- **Engine specs**: a small muted footnote under the "Run solver" button, not a box. It states what the data is (exact enumeration over 455 canonical classes); keep it true when the engine changes.
- **Responsive**:
  - `≤1024px`: one column, the divider moves below the inputs.
  - `≤640px`: the verdict and summary stack.
  - `≤480px`: 16px side padding.
  - Tables scroll sideways; the page itself must not scroll sideways at 390px.
- **Class names**: `terminal-*`, `tactical-*`, `hud-*` and `radar-slider` are leftovers from the earlier radar-terminal design and carry no meaning. Don't add new names in that vocabulary.

---

## 6. Copy
- Plain words that say what things do. Buttons start with a verb: "Run solver", "Show analysis notes".
- No `//`, `[ ]`, `●` or `>` decorations.
- Errors say what happened and what to do next.
- All UI strings live in `frontend/src/i18n.js` (English and Vietnamese, same keys), including preset labels and the currency. Change the Vietnamese wording only when asked.
- Each API error `code` has its own message (`invalidHand`, `invalidParams`, `serverError`, `solverOffline`, `badResponse`, `aiRateLimited`); the server's text is only the detail.
- Never claim what the code doesn't do: no "live" indicators, no "GTO" (the tool computes EV, not an equilibrium).

---

## 7. Checking a UI Change
- Run `npm run build`, `npm run lint` (any warning fails) and `npm test` in `frontend/`.
- Screenshot at 1360px and 390px wide and check them against this file.
- The numbers on screen (EV, equity, coverage, top hands) must not change from a styling change.
