# Lesson 14 — Styling and DESIGN.md

> **Goal:** understand how the page gets its look (the colour tokens, the base styles and focus
> ring, the layout grid and its breakpoints, the stepper, the summary rows and tables) and how to
> use `DESIGN.md` as the rulebook for any future UI change.
> **Files:** [`frontend/src/index.css`](../frontend/src/index.css), [`frontend/src/App.css`](../frontend/src/App.css),
> [`DESIGN.md`](../DESIGN.md).
> **Time:** ~40 min. **Before this:** [13 — The React app](13-frontend-app.md).

---

## Where this fits

```
 DESIGN.md   the rulebook: what the page may and may not look like
     │ decides
     ▼
 index.css   tokens (--bg, --accent, --good, …), resets, focus ring       imported by main.jsx
     │ var(--…)
     ▼
 App.css     layout grid, 3 breakpoints, controls, summary rows, tables   imported by App.jsx
     │ class names
     ▼
 App.jsx     className="…" on every element (lesson 13)
```

The styling is two plain CSS files: 63 lines of tokens and base rules, 596 of layout and components.
No framework, no preprocessor, no CSS modules: every class is global. `DESIGN.md` is a 95-line spec
of what the page may look like. This lesson reads all three, measures the result in a real browser,
and shows which rules are now kept and which ones nothing checks.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [DESIGN.md:3-13](../DESIGN.md#L3-L13) | The principle ("a plain tool page") and seven prohibitions. |
| 2 | [index.css:1-30](../frontend/src/index.css#L1-L30) | Fifteen colour tokens (two of them mixed from others), one radius, the font. |
| 3 | [index.css:32-63](../frontend/src/index.css#L32-L63) | Resets and the `:focus-visible` ring. |
| 4 | [App.css:63-108](../frontend/src/App.css#L63-L108) | The two-column grid and the 1024 / 480 breakpoints. |
| 5 | [App.css:156-188](../frontend/src/App.css#L156-L188) | The stepper: how the browser's spin arrows are hidden. |
| 6 | [App.css:426-466](../frontend/src/App.css#L426-L466) | Summary rows as a three-column grid, and the 640 breakpoint. |
| 7 | [App.css:468-537](../frontend/src/App.css#L468-L537) | Tables: 1px lines, sideways scrolling, green and red text. |
| 8 | [DESIGN.md:92-95](../DESIGN.md#L92-L95) | How to check a UI change. |

---

## Walkthrough

### 1. How the page got this look, and why the class names say "terminal"

Until 2026-10-23 the page was a dark neon "tactical radar terminal": radar green `#22C55E`,
JetBrains Mono everywhere, uppercase labels with wide letter spacing, `text-shadow` glow, a pulsing
"LIVE" dot (`@keyframes pulse-beacon`) and a `[ EXECUTE SOLVER ]` button. Commit `661abfc`
("revamped the ui") replaced it with the plain look you see now: the Ayu Dark palette, the system
font, sentence case, 1px lines instead of cards, `−`/`+` steppers, labels tied to their inputs, focus
rings and no motion. `App.css` shrank from 905 to 596 lines, and `DESIGN.md` was rewritten. A day
later, commit `5dddad0` closed the gaps that restyle left: it fixed the sizes, radii and colours that
broke DESIGN.md (section 8), and deleted 18 class names from `App.jsx` that no CSS rule styled any
more (`green-glow`, `cat-pill`, `status-chip`, …).

The **class names that do have rules** were deliberately kept, so that the old tutorial in
`learning/` still matched the code. DESIGN.md now says so explicitly
([DESIGN.md:78](../DESIGN.md#L78)): they "are leftovers from the earlier radar-terminal design and
carry no meaning. Don't add new names in that vocabulary." What they style today:

| Legacy class | What it styles today |
|--------------|---------------------|
| `terminal-container`, `-header`, `-grid` | page wrapper, header, two-column layout |
| `radar-slider`, `tactical-btn`, `tactical-table` | the fold slider, "Run solver", both tables |
| `terminal-alert`, `preset-chip` | the red error box; every preset button (radius 3px, not a pill) |
| `hud-metrics-grid`, `hud-card`, `hud-value` | the four summary rows |
| `telemetry-body`, `mono-num`, `mono-canonical` | notes text; tabular numbers in the system font, not monospace |

### 2. The tokens

📍 [`frontend/src/index.css:1-31`](../frontend/src/index.css#L1-L31)
```css
:root {
  /* Ayu Dark (bordered): one background, regions split by 1px lines */
  --bg: #0B0E14;
  --bg-input: #0D1017;
  --bg-hover: #141922;
  --bg-active: #1F2530;

  --line: #232834;
  --line-control: #3D4452;

  --text: #BFBDB6;
  --text-strong: #E6E1CF;
  --muted: #8A9199;

  --accent: #E6B450;   /* focus, main action, thin-value hands */
  --accent-hover: #D9A63F;
  --good: #AAD94C;     /* value hands / +EV */
  --bad: #F07178;      /* -EV / errors */
  --bluff: #D2A6FF;    /* bluff hands: a bluff is a real play, not a warning */
  /* Soft fills for the profit map: the same two colours, mostly transparent */
  --zone-good: color-mix(in srgb, var(--good) 45%, transparent);
  --zone-bad: color-mix(in srgb, var(--bad) 20%, transparent);

  --radius: 3px;

  font-family: system-ui, -apple-system, "Segoe UI", Roboto, Ubuntu, "Helvetica Neue", Arial, sans-serif;
  font-size: 15px;
  line-height: 1.5;
  font-weight: 400;
  color-scheme: dark;
}
```

The `--bluff` token is the 3.0.0 addition, and it is a design statement: a bluff gets its own
colour instead of borrowing the warning red, because it is a real play rather than a mistake.

Every colour on the page comes from these sixteen names: `App.css` contains no hex or `rgba()`
value at all ([DESIGN.md:38](../DESIGN.md#L38) makes that a rule). This is what each one is for,
according to [DESIGN.md §2](../DESIGN.md#L17-L40), and how often the two CSS files use it
(`grep -o 'var(--THE_TOKEN)' frontend/src/*.css | wc -l` for each row):

| Token | Use (DESIGN.md) | `var()` uses |
|-------|-----------------|--------------|
| `--bg` | page background (also the text colour on the yellow button) | 2 |
| `--bg-input` | text and number inputs | 1 |
| `--bg-hover` | hover on buttons and table rows | 5 |
| `--bg-active` | the selected preset or language | 2 |
| `--line` | section dividers, table rows | 11 |
| `--line-control` | borders of inputs and buttons | 8 |
| `--text` | body text | 5 |
| `--text-strong` | headings, values, input text | 13 |
| `--muted` | secondary text (6:1 contrast on `--bg`) | 22 |
| `--accent` | focus ring, slider, "Run solver", thin-value hands | 6 |
| `--accent-hover` | hover state of "Run solver" | 1 |
| `--good` | value hands, +EV (one of the uses is inside `--zone-good`) | 5 |
| `--bad` | −EV, errors (one of the uses is inside `--zone-bad`) | 4 |
| `--bluff` | bluff hands, in the verdict card | 1 |
| `--zone-good` | profitable stretches of the profit map | 1 |
| `--zone-bad` | the rest of the profit map's track | 1 |
| `--radius` | every corner, 3px | 13 |

Four things in this block are easy to miss:

- **`font-size: 15px` on `:root` makes `1rem` = 15px**, not the usual 16px: `0.87rem` is 13.05px and
  `1.25rem` is 18.75px (measured in Chromium: body 15px, title and verdict 18.75px).
- **`color-mix()` derives a token from another.** `--zone-good` is `--good` at 45% opacity, so the
  profit map follows any change of `--good` (exercise 2). Before, the zones were `rgba()` copies of
  the two colours, which a change of `--good` left behind.
- **The system UI font stack.** Nothing to download, and it looks native on each OS. The monospace
  stack for `code`/`pre` ([index.css:60-63](../frontend/src/index.css#L60-L63)) is unused.
- **`color-scheme: dark`** makes the browser draw its own parts (scrollbars, slider track) dark too.

### 3. Base styles and the focus ring

Above the focus rule, [index.css:32-53](../frontend/src/index.css#L32-L53) resets every margin,
makes `width` include padding and border (`box-sizing: border-box`, so a `width: 100%` input never
overflows), gives `body` the page colours, and makes buttons and inputs inherit the page font, which
they do not do by default. Then:

📍 [`frontend/src/index.css:56-59`](../frontend/src/index.css#L56-L59)
```css
:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
```

**`:focus-visible`** draws a 2px accent outline, 1px away, on any control, but only when focus
should be visible (keyboard use, not mouse clicks). Measured: the first Tab lands on the language
toggle with `2px solid rgb(230, 180, 80)`. Text fields also get a yellow border on any focus
([App.css:152-154](../frontend/src/App.css#L152-L154)). DESIGN.md §4 ([:55](../DESIGN.md#L55)) adds the
rule that matters most when you restyle: *never remove an outline without a replacement*.

### 4. The layout: one grid, three breakpoints

📍 [`frontend/src/App.css:63-76`](../frontend/src/App.css#L63-L76)
```css
.terminal-grid {
  display: grid;
  grid-template-columns: 340px 1fr;
}

/* Let grid items shrink below their tables' min-content width (tables scroll instead) */
.terminal-grid > * {
  min-width: 0;
}

.control-panel {
  padding: 20px 24px 24px 0;
  border-right: 1px solid var(--line);
}
```

`grid-template-columns: 340px 1fr` makes a fixed 340px input column and gives the rest to the
results. The divider is not a separate element: it is the control panel's `border-right`. The
`min-width: 0` rule is the subtle one. A grid item normally refuses to become narrower than its
widest content, so a wide table would push the page past the screen. With `min-width: 0` the column
can shrink, and the table scrolls inside its own `.table-wrapper` (`overflow-x: auto`,
[App.css:471-473](../frontend/src/App.css#L471-L473)).

📍 [`frontend/src/App.css:88-102`](../frontend/src/App.css#L88-L102)
```css
@media (max-width: 1024px) {
  .terminal-grid {
    grid-template-columns: 1fr;
  }

  .control-panel {
    padding-right: 0;
    border-right: none;
    border-bottom: 1px solid var(--line);
  }

  .results-container {
    padding-left: 0;
  }
}
```

At 1024px and below the grid becomes one column and the divider turns into a `border-bottom`. At
480px and below the side padding drops from 24px to 16px ([App.css:104-108](../frontend/src/App.css#L104-L108)).
The third breakpoint, 640px, lives next to the parts it changes: the verdict's EV moves to the left ([App.css:397-401](../frontend/src/App.css#L397-L401))
and the summary rows fold into two columns ([App.css:458-466](../frontend/src/App.css#L458-L466)).
Measured in headless Chromium (scrollbars hidden, so the full width is available):

| Viewport | Grid columns | Divider | Side padding | Summary row columns | EV aligned |
|----------|--------------|---------|--------------|---------------------|------------|
| 1360px | 340px 972px | right of inputs | 24px | 200px 110px 606px | right |
| 1025px | 340px 637px | right of inputs | 24px | 200px 110px 271px | right |
| 1024px | 976px | below inputs | 24px | 200px 110px 634px | right |
| 640px | 592px | below inputs | 24px | 523.875px 52.125px | left |
| 390px | 358px | below inputs | 16px | 289.875px 52.125px | left |

At 390px the two tables scroll sideways (by 103px and 131px) and the page does not, as
[DESIGN.md:77](../DESIGN.md#L77) asks. `.results-container > * + *`
([App.css:84-86](../frontend/src/App.css#L84-L86)) puts 24px above every result section but the first.

### 5. The stepper: hiding the browser's spin arrows

DESIGN.md §4 wants a `−` / `+` button pair around each number field instead of the tiny native
arrows. The JSX is the `Stepper` component in lesson 13. The CSS:

📍 [`frontend/src/App.css:156-174`](../frontend/src/App.css#L156-L174)
```css
/* Number field with − / + buttons instead of the browser's spin arrows */
.stepper {
  display: flex;
  gap: 4px;
}

.stepper .input-field {
  flex: 1;
  min-width: 0;
  font-variant-numeric: tabular-nums;
  -moz-appearance: textfield;
  appearance: textfield;
}

.stepper .input-field::-webkit-inner-spin-button,
.stepper .input-field::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
```

- `.stepper` is a flex row: button, field, button, with 4px gaps. The field takes the remaining
  width (`flex: 1`), and `.stepper-btn` ([App.css:176-188](../frontend/src/App.css#L176-L188)) stays
  36px wide (`flex: none`).
- Hiding the arrows takes two mechanisms, because browsers differ. Firefox honours `appearance:
  textfield`. Chrome and Safari draw the arrows as `::-webkit-inner-spin-button` and
  `::-webkit-outer-spin-button` pseudo-elements, which `-webkit-appearance: none` removes.
- `tabular-nums` gives every digit the same width, so the number does not jitter as you click `+`.
- Measured heights: inputs and stepper buttons 36.5px, presets 32px, the main button 40.5px. That
  meets DESIGN.md's 36 / 32 / 40 (the extra half pixel comes from the 1.5 line height on 15px text).

### 6. Presets, the main button and the profit map

A preset ([App.css:197-205](../frontend/src/App.css#L197-L205)) is a plain bordered button:

📍 [`frontend/src/App.css:207-215`](../frontend/src/App.css#L207-L215)
```css
.preset-chip:hover {
  background: var(--bg-hover);
}

.preset-chip.active {
  background: var(--bg-active);
  border-color: var(--muted);
  color: var(--text-strong);
}
```

Hover changes only the background (no motion, DESIGN.md §1), and the active preset gets
`--bg-active` with a `--muted` border, **not** the accent ([DESIGN.md:39](../DESIGN.md#L39)). The
accent is saved for the one button that does something:

📍 [`frontend/src/App.css:298-311`](../frontend/src/App.css#L298-L311)
```css
.tactical-btn {
  width: 100%;
  min-height: 40px;
  padding: 8px 12px;
  background: var(--accent);
  color: var(--bg);
  border: 1px solid var(--accent);
  border-radius: var(--radius);
  font-weight: 600;
}

.tactical-btn:hover:not(:disabled) {
  background: var(--accent-hover);
}
```

Yellow background, dark text (`--bg`), and a darker yellow on hover. The hover colour used to be the
raw value `#D9A63F` typed into this rule; now it is the `--accent-hover` token with the same value,
listed in DESIGN.md's table ([DESIGN.md:31](../DESIGN.md#L31)). The profit map
([App.css:262-295](../frontend/src/App.css#L262-L295)) is a 10px `position: relative` bar: a faint red
track (`--zone-bad`), absolutely positioned green zones (`--zone-good`; their `left` and `width` are
inline styles, lesson 13) and a 2px marker.

### 7. Summary rows and tables

The four summary figures used to be glowing "HUD cards". The container
([App.css:429-431](../frontend/src/App.css#L429-L431)) draws a line on top, and each figure is a row
with a 1px line underneath:

📍 [`frontend/src/App.css:557-571`](../frontend/src/App.css#L557-L571)
```css
.hud-card {
  display: grid;
  grid-template-columns: 200px 110px 1fr;
  gap: 4px 16px;
  align-items: baseline;
  padding: 8px 0;
  border-bottom: 1px solid var(--line);
}

.hud-value {
  font-weight: 600;
  color: var(--text-strong);
  font-variant-numeric: tabular-nums;
  text-align: right;
}
```

Each `.hud-card` is a small grid: a 200px label, a 110px right-aligned value and a note. Every row
uses the same widths, so the values line up without a table. Below 640px the row becomes
`1fr auto` and the note wraps to its own line ([App.css:458-466](../frontend/src/App.css#L458-L466)).
Only the EV value gets an extra class, `green-metric`, and only when it is positive
([App.jsx:464](../frontend/src/App.jsx#L464)).

The tables ([App.css:475-498](../frontend/src/App.css#L475-L498)) have muted headers over a
`--line-control` rule, `--line` between rows and `--bg-hover` on hover. Colour means something
([App.css:524-537](../frontend/src/App.css#L524-L537)): +EV and "Raise" are green, −EV and "Fold all"
red, a "Fold" action only muted. That is [DESIGN.md:37](../DESIGN.md#L37): *green and red appear only
where they mean raise/fold or +/−EV*.

### 8. DESIGN.md as the rulebook

`DESIGN.md` is the file to read **before** you change anything visual. Its prohibitions:

📍 [`DESIGN.md:6-13`](../DESIGN.md#L6-L13)
```markdown
### Prohibitions
- **No concept or theme language**: no "terminal", "radar", "HUD", "telemetry" or "engine" styling or copy.
- **No effects**: no glow, `text-shadow`, gradients, background grids, noise or blurred shapes.
- **No motion**: no pulsing dots, spinners, entrance animations or hover lifts. Hover changes background color only.
- **No decoration**: no emoji, robot or sparkle icons, no chat bubbles, no purple or violet.
- **No cards by default**: sections are separated by spacing and 1px `--line` borders. Only controls, the error message and the open notes panel get a box.
- **No pills**: radius is `3px` everywhere.
- **No empty labels**: no kicker tags, section IDs (`SEC-01`) or badges that carry no information. No fake status (e.g. a "LIVE" indicator that checks nothing).
```

The rest is a spec you can check: the token table (§2), typography (§3: one family, base
`15px / 1.5`, labels `0.93rem`, nothing smaller than `0.87rem`, nothing bigger than `1.25rem`),
control sizes and focus (§4), the layout, breakpoints and the legacy class names (§5), copy rules
(§6: all strings in `i18n.js`, one message per API error code, no "live" or "GTO" claims) and how to
verify a change:

📍 [`DESIGN.md:93-96`](../DESIGN.md#L93-L96)
```markdown
## 7. Checking a UI Change
- Run `npm run build`, `npm run lint` (any warning fails) and `npm test` in `frontend/`.
- Screenshot at 1360px and 390px wide and check them against this file.
- The numbers on screen (EV, equity, coverage, top hands) must not change from a styling change.
```

The last line is the one to respect most: a styling change must never change the numbers.

**What the last fix changed.** A small script (exercise 7) that checks font sizes, radii and raw
colours against the spec found seven problems in the CSS before commit `5dddad0`, and finds none
now:

| Line | Before | Now | Rule |
|------|--------|-----|------|
| [App.css:23](../frontend/src/App.css#L23) | title `1.35rem` (20.25px) | `1.25rem` (18.75px measured) | §3: nothing bigger than `1.25rem` |
| [App.css:563](../frontend/src/App.css#L563) | drawer arrow `0.75rem` (11.25px) | `0.87rem` (13.05px measured) | §3: smallest `0.87rem` |
| [App.css:50](../frontend/src/App.css#L50), [:278](../frontend/src/App.css#L278) | `border-radius: 2px` | `var(--radius)` (3px measured) | §1: radius is `3px` everywhere |
| [App.css:277](../frontend/src/App.css#L277), [:285](../frontend/src/App.css#L285), [:310](../frontend/src/App.css#L310) | raw `rgba()` / `#D9A63F` | `var(--zone-bad)`, `var(--zone-good)`, `var(--accent-hover)` | §2: colours come from the tokens |

The accent rule holds too. `grep 'var(--accent)'` finds exactly five uses: the focus ring, the
focused input border, the slider's `accent-color`, and the main button's background and border.

None of this is checked automatically. `npm run build`, `npm run lint` and `npm test` never look at
CSS values, so any of these fixes could come back unnoticed (exercise 4, weak spot 2).

---

## 💡 Concept: CSS custom properties (tokens)

```css
:root { --accent: #E6B450; }                  /* define once, on the root element */
.tactical-btn { background: var(--accent); }  /* use anywhere below it */
:root { --zone-good: color-mix(in srgb, var(--good) 45%, transparent); }  /* a token built from a token */
```

A custom property is a named value that every element inherits. Change `--accent` once and every
`var(--accent)` follows. Unlike a Python constant it is resolved by the browser at run time, so you
can override it live in DevTools. A value typed directly (`#D9A63F`) does **not** follow; neither
does a separate token such as `--accent-hover`, which is why changing the accent means changing two
lines of `index.css` (exercise 2).

## 💡 Concept: grid, `fr` and media queries

```css
.terminal-grid { display: grid; grid-template-columns: 340px 1fr; }  /* fixed + "the rest" */
@media (max-width: 1024px) { .terminal-grid { grid-template-columns: 1fr; } }
```

`1fr` means one share of the free space. A media query applies its rules only while the condition
holds, and later rules win over earlier ones with the same selector, so the narrow-screen override
must come after the default. That is why each `@media` block sits below the rules it changes.

---

## Design decisions

- **Plain global CSS with tokens.** Two files and no styling tool. The cost: every class is global,
  and nothing warns you about dead ones.
- **Spacing and 1px lines instead of cards.** Fewer boxes and a page that reads like a document.
  Only controls, the error and the open notes panel get a border ([DESIGN.md:11](../DESIGN.md#L11)).
- **The system font, no motion, no effects.** Nothing to download, animate or tune.
- **Derived tokens with `color-mix()`.** The profit map's fills can't drift from `--good` and
  `--bad`. The cost: `color-mix()` needs a 2023-or-later browser (Chrome 111, Firefox 113, Safari
  16.2). In an older one the declaration is invalid when it is used, the background falls back to
  transparent, and the profit map loses its colours.
- **Keeping the old class names.** The restyle stayed a CSS-and-copy change and the old tutorial
  stayed accurate. The cost: vocabulary that contradicts DESIGN.md §1, which DESIGN.md §5 now
  excuses as "leftovers".
- **A written spec.** DESIGN.md turns taste into checkable rules, so future changes, by you or by an
  AI assistant, can be reviewed against it.

---

## ⚠️ Weak spots

Fixed since the first version of this course:

- ✅ **Fixed: dead class names.** 18 classes set in `App.jsx` (`green-glow`, `cat-pill`,
  `status-chip`, …) had no rule. They were deleted; the 🧪 scan below now prints nothing.
- ✅ **Fixed: sizes and radii outside the spec.** The title ([App.css:23](../frontend/src/App.css#L23)),
  the drawer arrow ([:563](../frontend/src/App.css#L563)) and two corners
  ([:50](../frontend/src/App.css#L50), [:278](../frontend/src/App.css#L278)) now follow DESIGN.md §1
  and §3 (section 8).
- ✅ **Fixed: colours that bypassed the tokens.** `--accent-hover`, `--zone-good` and `--zone-bad`
  ([index.css:16-21](../frontend/src/index.css#L16-L21)) replaced the raw values at
  [App.css:277](../frontend/src/App.css#L277), [:285](../frontend/src/App.css#L285) and
  [:310](../frontend/src/App.css#L310), and DESIGN.md lists them.
- ✅ **Fixed: a footnote that said "Monte Carlo".** It now says "Exact enumeration, 455 canonical
  classes", and [DESIGN.md:72](../DESIGN.md#L72) asks to keep it true.
- ✅ **Fixed: "GTO Insight" in the offline analysis.** The rule-based notes' third heading broke §6's
  "no GTO" rule; it is now "Nhận định chiến thuật" ([app.py:588](../backend/app.py#L588), lesson 13).

None of these fixes is pinned by a test (weak spot 2).

Still open:

1. **Legacy names contradict the rulebook.** `terminal-*`, `tactical-*`, `hud-*`, `radar-slider` and
   `telemetry-*` ([App.css](../frontend/src/App.css)) use the vocabulary [DESIGN.md:7](../DESIGN.md#L7)
   bans, and `mono-*` is not monospace. [DESIGN.md:78](../DESIGN.md#L78) now documents them as
   meaningless leftovers, which stops the list growing but doesn't shrink it. *Fix:* rename in one
   commit, together with the course excerpts that quote them (exercise 5).
2. **Nothing enforces DESIGN.md.** §7 ([DESIGN.md:92-95](../DESIGN.md#L92-L95)) relies on build,
   lint, tests and manual screenshots, and none of those reads a CSS value or a class name. The
   seven CSS problems of section 8 went unnoticed for the same reason. *Fix:* a check script in CI
   (exercises 7 and 8).
3. **The rulebook and the copy still disagree in places.** DESIGN.md §5 calls the footnote "Engine
   specs" in a file whose §1 bans "engine" copy. The Vietnamese notes title "Tư vấn lý thuyết trò
   chơi" ("game-theory advice", [i18n.js:185](../frontend/src/i18n.js#L185)) still breaks §6's "no
   GTO" rule ([DESIGN.md:88](../DESIGN.md#L88)), although the offline heading below it no longer
   does. A few `k` suffixes still live outside `i18n.js` (lesson 13, weak spot 4).

---

## 🧪 Try it

Run from `frontend/`.

Every use of the accent and of the new tokens:

```bash
grep -n 'var(--accent)\|var(--accent-hover)\|var(--zone-' src/index.css src/App.css
```

```
src/App.css:153:  border-color: var(--accent);
src/App.css:232:  accent-color: var(--accent);
src/App.css:277:  background: var(--zone-bad);
src/App.css:285:  background: var(--zone-good);
src/App.css:302:  background: var(--accent);
src/App.css:304:  border: 1px solid var(--accent);
src/App.css:310:  background: var(--accent-hover);
src/index.css:56:  outline: 2px solid var(--accent);
```

No raw colours left in `App.css` (the command prints nothing):

```bash
grep -n -E '#[0-9A-Fa-f]{6}\b|rgba?\(' src/App.css
```

Class names that `App.jsx` sets but no CSS rule styles:

```bash
node -e '
const fs = require("fs");
const jsx = fs.readFileSync("src/App.jsx", "utf8");
const css = fs.readFileSync("src/index.css", "utf8") + fs.readFileSync("src/App.css", "utf8");
const names = new Set();
for (const [, plain, tpl] of jsx.matchAll(/className=(?:"([^"]+)"|\{`([^`]+)`\})/g)) {
  (plain ?? tpl).match(plain ? /\S+/g : /\b[a-z]+(?:-[a-z]+)+\b/g).forEach((n) => names.add(n));
}
console.log(names.size, JSON.stringify([...names].filter((n) => !css.includes("." + n)).sort().join(" ")));
'
```

```
74 ""
```

74 names, none without a rule. Run the same script on the code from before the fix to see what was
removed:

```bash
mkdir -p /tmp/before/src
for f in App.jsx App.css index.css; do git show 5dddad0^:frontend/src/$f > /tmp/before/src/$f; done
(cd /tmp/before && node -e '…the same script…')
```

```
96 "action-badge amber-metric brand-green brand-group brand-white cat-pill chip-partial dim-metric green-glow highlight-val holding-class hud-label spec-label status-chip table-panel terminal-card verdict-col-left white-metric"
```

In the browser, drag the DevTools device-toolbar width across 1024, 640 and 480px to watch the
three breakpoints, and press Tab to see the focus ring.

---

## 🏋️ Exercises

Exercises marked 🟡 or 🔴 change code. Undo them afterwards with `git checkout -- <file>`.

**🟢 1. Predict.** The window is 1000px wide. How many columns are there, and where is the line
between inputs and results? Check with the DevTools device toolbar.

<details><summary>Solution</summary>

One column: 1000 ≤ 1024, so [App.css:88-102](../frontend/src/App.css#L88-L102) applies, and the
panel's `border-right` becomes a `border-bottom` under the inputs. Padding stays 24px until 480px.
</details>

**🟢 2. Predict.** You change `--accent` to Ayu's blue, `#59C2FF`. What turns blue, and what does not?
Then change `--good` to the same blue: what happens to the profit map? Try it without editing files:
in DevTools, add the property to `:root` (or run
`document.documentElement.style.setProperty('--accent', '#59C2FF')` in the console).

<details><summary>Solution</summary>

The "Run solver" button, the slider, the focus ring and a focused input's border turn blue: the
five `var(--accent)` uses. **Hovering** the button still shows yellow, `rgb(217, 166, 63)`, because
hover uses its own token, `--accent-hover` ([App.css:310](../frontend/src/App.css#L310)). Changing
the accent means changing both tokens, but both sit in `index.css`. With `--good` blue, the green
zones of the profit map turn a translucent blue (`color(srgb 0.34902 0.760784 1 / 0.45)` in
Chromium), because `--zone-good` is mixed from `var(--good)`. Before the fix they would have stayed
green.
</details>

**🟢 3. Predict.** How many pixels are `0.87rem` and `1.25rem` on this page, and what was the title
before the fix? Check under DevTools, Computed.

<details><summary>Solution</summary>

`:root` sets `font-size: 15px`, so `0.87rem` = 13.05px (the smallest text, now including the drawer
arrow) and `1.25rem` = 18.75px (the title and the verdict). The title used to be `1.35rem` =
20.25px. DESIGN.md's "0.87rem (13px)" assumes this root. With the default 16px it would be 13.92px.
</details>

**🟡 4. Undo a fix and see what notices.** Set the title back to `font-size: 1.35rem`
([App.css:23](../frontend/src/App.css#L23)) and run the three checks DESIGN.md §7 names:
`npm run build`, `npm run lint`, `npm test`. Which one fails?

<details><summary>Solution</summary>

None. The build compiles any valid CSS, oxlint only reads JavaScript, and the tests check text and
behaviour, not computed styles. Only the screenshot step (or DevTools: 20.25px) would catch it, which
is weak spot 2. Exercise 7 writes a check that does fail. Undo with
`git checkout -- frontend/src/App.css`.
</details>

**🟡 5. Rename a legacy class.** Rename `tactical-btn` to `solve-btn` in
[App.jsx:375](../frontend/src/App.jsx#L375) and in the three rules at
[App.css:298-316](../frontend/src/App.css#L298-L316). Check: `grep -rn tactical-btn src` prints
nothing, the build succeeds and the button still looks the same. Then run
`python3 learning/verify_course.py` from the repository root.

<details><summary>Solution</summary>

`sed -i 's/tactical-btn/solve-btn/g' src/App.jsx src/App.css` changes 4 occurrences and nothing
moves on screen. But the checker now reports `excerpt differs from ../frontend/src/App.css:298-311`
for this lesson: the price the restyle avoided by keeping old names. A real rename updates the
course and DESIGN.md §5 in the same commit. Undo with
`git checkout -- frontend/src/App.jsx frontend/src/App.css`.
</details>

**🟡 6. Find the scan's blind spot.** In `App.css`, rename `.act-fold` (the muted "Fold" cell,
[App.css:535](../frontend/src/App.css#L535)) to `.act-folded` and run the 🧪 scan. It still prints
nothing, although "Fold" cells have lost their style. Find the two reasons, and fix the scan.

<details><summary>Solution</summary>

1. `act-fold` is set in a plain expression, `className={item.is_profitable ? "act-raise" : "act-fold"}`
   ([App.jsx:549](../frontend/src/App.jsx#L549)), which the regex doesn't read: it only knows
   `className="…"` and template strings.
2. `css.includes(".act-fold")` is still true, because `.act-folded` contains it.

```js
for (const [, plain, tpl, expr] of jsx.matchAll(/className=(?:"([^"]+)"|\{`([^`]+)`\}|\{([^{}`]+)\})/g)) {
  if (plain) plain.split(/\s+/).forEach((n) => names.add(n));
  else if (tpl) tpl.match(/\b[a-z]+(?:-[a-z]+)+\b/g).forEach((n) => names.add(n));
  else for (const [, n] of expr.matchAll(/"([a-z]+(?:-[a-z]+)*)"/g)) names.add(n);
}
const hasRule = (n) => new RegExp(`\\.${n}(?![\\w-])`).test(css);
console.log(names.size, [...names].filter((n) => !hasRule(n)).sort().join(" "));
```

It now sees 78 names and prints `78 act-fold`. On the unmodified CSS it prints `78 ` (nothing
missing). Undo with `git checkout -- frontend/src/App.css`.
</details>

**🔴 7. Make the rulebook executable.** Write `frontend/check-design.mjs` that reads the CSS files
given on the command line (default: both of `src/`) and reports, with `file:line`, every
`font-size` in `rem` outside 0.87–1.25, every `border-radius` that is not `var(--radius)`, and every
hex or `rgba()` colour outside a `--token:` line. It should exit 1 if it finds anything. Check:
`node check-design.mjs` on today's CSS, and on the CSS from before the fix.

<details><summary>Solution</summary>

```js
import fs from "node:fs";
let problems = 0;
const report = (at, msg) => { console.log(`${at}  ${msg}`); problems++; };
const files = process.argv.length > 2 ? process.argv.slice(2) : ["src/index.css", "src/App.css"];
for (const file of files) {
  fs.readFileSync(file, "utf8").split("\n").forEach((line, i) => {
    const at = `${file}:${i + 1}`;
    const size = line.match(/font-size:\s*([\d.]+)rem/);
    if (size && (size[1] < 0.87 || size[1] > 1.25)) report(at, `font-size ${size[1]}rem is outside 0.87–1.25rem`);
    if (/border-radius:/.test(line) && !line.includes("var(--radius)")) report(at, `radius is not var(--radius): ${line.trim()}`);
    if (/#[0-9A-Fa-f]{6}\b|rgba?\(/.test(line) && !line.trim().startsWith("--")) report(at, `colour outside the tokens: ${line.trim()}`);
  });
}
console.log(`${problems} problem(s)`);
process.exitCode = problems ? 1 : 0;
```

Today it prints `0 problem(s)` and exits 0. On the old files
(`node check-design.mjs /tmp/before/src/index.css /tmp/before/src/App.css`, from 🧪) it prints:

```
/tmp/before/src/App.css:23  font-size 1.35rem is outside 0.87–1.25rem
/tmp/before/src/App.css:50  radius is not var(--radius): border-radius: 2px;
/tmp/before/src/App.css:277  colour outside the tokens: background: rgba(240, 113, 120, 0.2);
/tmp/before/src/App.css:278  radius is not var(--radius): border-radius: 2px;
/tmp/before/src/App.css:285  colour outside the tokens: background: rgba(170, 217, 76, 0.45);
/tmp/before/src/App.css:310  colour outside the tokens: background: #D9A63F;
/tmp/before/src/App.css:563  font-size 0.75rem is outside 0.87–1.25rem
7 problem(s)
```

and exits 1. It misses 3-digit hex colours and named colours (`white`); add them if you need to.
Delete the file to undo.
</details>

**🔴 8. Put the checks in CI.** Turn exercises 6 and 7 into `npm run check:design`, and run it in the
frontend job of [.github/workflows/ci.yml](../.github/workflows/ci.yml#L40-L43). Check: the script
exits 0 today and 1 after exercise 4's change, and DESIGN.md §7 mentions it.

<details><summary>Solution</summary>

Move both scripts into `frontend/scripts/` (`check-design.mjs`, and the class scan as
`check-classes.mjs` ending with `process.exitCode = missing.length ? 1 : 0`). In `package.json`
add `"check:design": "node scripts/check-design.mjs && node scripts/check-classes.mjs"`. In
`ci.yml`, after `- run: npm run lint`, add `- run: npm run check:design`. Add the command to the
first bullet of DESIGN.md §7. Now the fixes in section 8 are pinned: undoing any of them fails CI.
Undo with `git checkout -- frontend/package.json .github/workflows/ci.yml DESIGN.md` and delete
`frontend/scripts/`.
</details>

---

## ❓ Quiz

1. Why does `0.87rem` mean 13.05px on this page?
2. What does `min-width: 0` on the grid's children prevent?
3. Why does the code hide the spin arrows with two different mechanisms?
4. DESIGN.md allows `--accent` in three places. Which five CSS lines use it, do they keep the rule,
   and why doesn't the button's hover count?
5. Why were names like `tactical-btn` and `hud-card` kept after the restyle, and what does
   DESIGN.md now say about them?

<details><summary>Answers</summary>

1. `:root` sets `font-size: 15px` ([index.css:26](../frontend/src/index.css#L26)), and `rem` is relative
   to the root element's font size: 0.87 × 15 = 13.05.
2. A grid item cannot normally be narrower than its content, so the wide tables would make the page
   scroll sideways on a phone. With it, the column shrinks and the tables scroll in their wrapper.
3. Browsers draw them differently: Firefox honours `appearance: textfield`, while Chrome and Safari
   need the `::-webkit-…-spin-button` pseudo-elements set to `-webkit-appearance: none`.
4. Focus ring (index.css:56), focused input border (App.css:153), slider (App.css:232), main button
   background and border (App.css:302, 304). Yes: the input border is part of focus. The hover uses
   a separate token, `--accent-hover` (App.css:310), which DESIGN.md lists for exactly that use.
5. So that the old tutorial, which quoted the CSS and JSX, stayed accurate. DESIGN.md §5
   ([:78](../DESIGN.md#L78)) now calls them leftovers that carry no meaning and forbids new names in
   that vocabulary. The cost remains: words DESIGN.md §1 bans, and `mono-*` classes that are not
   monospace.
</details>

---

## Recap

- `index.css` holds fifteen colour tokens (two mixed from `--good` and `--bad` with `color-mix()`),
  the 3px radius, the 15px system font (`1rem` = 15px) and the `:focus-visible` ring. `App.css` uses
  them through `var(--…)` and contains no raw colours.
- The layout is a `340px 1fr` grid whose divider is a border. Breakpoints at 1024px (one column),
  640px (verdict and summary stack) and 480px (16px padding). Tables scroll, the page does not.
- The stepper hides native spin arrows with `appearance: textfield` and the WebKit pseudo-elements.
- Summary rows are small grids with fixed column widths. Tables use 1px lines, and colour only
  carries meaning (raise/fold, ±EV, errors).
- `terminal-*`, `tactical-*` and `hud-*` are legacy names, now documented as such; every class
  `App.jsx` sets has a rule.
- DESIGN.md is the rulebook. Today's CSS keeps its size, radius and colour rules, but nothing checks
  that automatically; a short script and one CI step would.

**Next:** [15 — Tests and performance](15-tests-and-performance.md)
