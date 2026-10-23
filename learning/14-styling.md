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

The styling is two plain CSS files: 59 lines of tokens and base rules, 596 of layout and components.
No framework, no preprocessor, no CSS modules: every class is global. `DESIGN.md` is an 88-line spec
of what the page may look like. This lesson reads all three, measures the result in a real browser,
and shows where code and rulebook still disagree.

---

## Reading order

| # | Location | What to look for |
|---|----------|------------------|
| 1 | [DESIGN.md:3-13](../DESIGN.md#L3-L13) | The principle ("a plain tool page") and seven prohibitions. |
| 2 | [index.css:1-26](../frontend/src/index.css#L1-L26) | Twelve colour tokens, one radius, the font. |
| 3 | [index.css:28-59](../frontend/src/index.css#L28-L59) | Resets and the `:focus-visible` ring. |
| 4 | [App.css:63-108](../frontend/src/App.css#L63-L108) | The two-column grid and the 1024 / 480 breakpoints. |
| 5 | [App.css:156-188](../frontend/src/App.css#L156-L188) | The stepper: how the browser's spin arrows are hidden. |
| 6 | [App.css:426-466](../frontend/src/App.css#L426-L466) | Summary rows as a three-column grid, and the 640 breakpoint. |
| 7 | [App.css:468-537](../frontend/src/App.css#L468-L537) | Tables: 1px lines, sideways scrolling, green and red text. |
| 8 | [DESIGN.md:85-88](../DESIGN.md#L85-L88) | How to check a UI change. |

---

## Walkthrough

### 1. How the page got this look, and why the class names say "terminal"

Until 2026-10-23 the page was a dark neon "tactical radar terminal": radar green `#22C55E`,
JetBrains Mono everywhere, uppercase labels with wide letter spacing, `text-shadow` glow, a pulsing
"LIVE" dot (`@keyframes pulse-beacon`) and a `[ EXECUTE SOLVER ]` button. Commit `661abfc`
("revamped the ui") replaced it with the plain look you see now: the Ayu Dark palette, the system
font, sentence case, 1px lines instead of cards, `−`/`+` steppers, labels tied to their inputs, focus
rings and no motion. `App.css` shrank from 905 to 596 lines, and `DESIGN.md` was rewritten.

The **class names** were deliberately kept, so that the old tutorial in `learning/` still matched
the code. They are now just legacy names:

| Legacy class | What it styles today |
|--------------|---------------------|
| `terminal-container`, `-header`, `-grid` | page wrapper, header, two-column layout |
| `radar-slider`, `tactical-btn`, `tactical-table` | the fold slider, "Run solver", both tables |
| `terminal-alert`, `preset-chip` | the red error box; every preset button (radius 3px, not a pill) |
| `hud-metrics-grid`, `hud-card`, `hud-value` | the four summary rows |
| `telemetry-body`, `mono-num`, `mono-canonical` | notes text; tabular numbers in the system font, not monospace |

Worse, **18 class names that `App.jsx` sets have no rule at all**. The restyle deleted the CSS for
17 of them, and for the dynamic `cat-SAP`, `cat-LIENG`, … classes; `verdict-col-left` never had one:

```
action-badge amber-metric brand-green brand-group brand-white cat-pill chip-partial dim-metric
green-glow highlight-val holding-class hud-label spec-label status-chip table-panel terminal-card
verdict-col-left white-metric
```

Some name effects DESIGN.md now forbids (`green-glow`, `cat-pill`, `status-chip`). They do nothing
on screen, but they mislead anyone reading `App.jsx` (weak spots 1 and 2).

### 2. The tokens

📍 [`frontend/src/index.css:1-26`](../frontend/src/index.css#L1-L26)
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

  --accent: #E6B450;   /* focus, main action only */
  --good: #AAD94C;     /* raise / +EV */
  --bad: #F07178;      /* fold / -EV / errors */

  --radius: 3px;

  font-family: system-ui, -apple-system, "Segoe UI", Roboto, Ubuntu, "Helvetica Neue", Arial, sans-serif;
  font-size: 15px;
  line-height: 1.5;
  font-weight: 400;
  color-scheme: dark;
}
```

Every colour on the page comes from these twelve names (with three exceptions, section 8). This is
what each one is for, according to [DESIGN.md §2](../DESIGN.md#L17-L36), and how often the CSS uses it:

| Token | Use (DESIGN.md) | `var()` uses |
|-------|-----------------|--------------|
| `--bg` | page background (also the text colour on the yellow button) | 2 |
| `--bg-input` | text and number inputs | 1 |
| `--bg-hover` | hover on buttons and table rows | 4 |
| `--bg-active` | the selected preset or language | 2 |
| `--line` | section dividers, table rows | 9 |
| `--line-control` | borders of inputs and buttons | 6 |
| `--text` | body text | 3 |
| `--text-strong` | headings, values, input text | 12 |
| `--muted` | secondary text (6:1 contrast on `--bg`) | 16 |
| `--accent` | focus ring, slider, "Run solver". **Nothing else.** | 5 |
| `--good` | raise, +EV | 4 |
| `--bad` | fold, −EV, errors | 4 |
| `--radius` | every corner, 3px | 8 |

Three things in this block are easy to miss:

- **`font-size: 15px` on `:root` makes `1rem` = 15px**, not the usual 16px: `0.87rem` is 13.05px and
  `1.25rem` is 18.75px (measured in Chromium: body 15px, verdict title 18.75px).
- **The system UI font stack.** Nothing to download, and it looks native on each OS. The monospace
  stack for `code`/`pre` ([index.css:56-59](../frontend/src/index.css#L56-L59)) is unused.
- **`color-scheme: dark`** makes the browser draw its own parts (scrollbars, slider track) dark too.

### 3. Base styles and the focus ring

Above the focus rule, [index.css:28-49](../frontend/src/index.css#L28-L49) resets every margin,
makes `width` include padding and border (`box-sizing: border-box`, so a `width: 100%` input never
overflows), gives `body` the page colours, and makes buttons and inputs inherit the page font, which
they do not do by default. Then:

📍 [`frontend/src/index.css:51-54`](../frontend/src/index.css#L51-L54)
```css
:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
```

**`:focus-visible`** draws a 2px accent outline, 1px away, on any control, but only when focus
should be visible (keyboard use, not mouse clicks). Measured: the first Tab lands on the language
toggle with `2px solid rgb(230, 180, 80)`. Text fields also get a yellow border on any focus
([App.css:152-154](../frontend/src/App.css#L152-L154)). DESIGN.md §4 ([:51](../DESIGN.md#L51)) adds the
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
Measured in headless Chromium:

| Viewport | Grid columns | Divider | Side padding | Summary row columns | EV aligned |
|----------|--------------|---------|--------------|---------------------|------------|
| 1360px | 340px 972px | right of inputs | 24px | 200px 110px 606px | right |
| 1025px | 340px 637px | right of inputs | 24px | 200px 110px 271px | right |
| 1024px | 976px | below inputs | 24px | 200px 110px 634px | right |
| 640px | 592px | below inputs | 24px | 523.875px 52.125px | left |
| 390px | 358px | below inputs | 16px | 289.875px 52.125px | left |

At 390px the two tables scroll sideways (by 103px and 131px) and the page does not, as
[DESIGN.md:73](../DESIGN.md#L73) asks. `.results-container > * + *`
([App.css:84-86](../frontend/src/App.css#L84-L86)) puts 24px above every result section but the first.

### 5. The stepper: hiding the browser's spin arrows

DESIGN.md §4 wants a `−` / `+` button pair around each number field instead of the tiny native
arrows. The JSX is in lesson 13. The CSS:

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
`--bg-active` with a `--muted` border, **not** the accent ([DESIGN.md:35](../DESIGN.md#L35)). The
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
  background: #D9A63F;
}
```

Yellow background, dark text (`--bg`), and a darker yellow on hover that is a raw hex value, not a
token (weak spot 4). The profit map ([App.css:262-295](../frontend/src/App.css#L262-L295)) is a 10px
`position: relative` bar: a faint red track, absolutely positioned green zones (their `left` and
`width` are inline styles, lesson 13) and a 2px marker. Its red and green are `rgba()` copies of
`--bad` and `--good`.

### 7. Summary rows and tables

The four summary figures used to be glowing "HUD cards". The container
([App.css:429-431](../frontend/src/App.css#L429-L431)) draws a line on top, and each figure is a row
with a 1px line underneath:

📍 [`frontend/src/App.css:433-447`](../frontend/src/App.css#L433-L447)
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
Only `green-metric` has a rule, so only a positive EV turns green. The other value classes are dead.

The tables ([App.css:475-498](../frontend/src/App.css#L475-L498)) have muted headers over a
`--line-control` rule, `--line` between rows and `--bg-hover` on hover. Colour means something
([App.css:524-537](../frontend/src/App.css#L524-L537)): +EV and "Raise" are green, −EV and "Fold all"
red, a "Fold" action only muted. That is DESIGN.md:34: *green and red only for raise/fold or ±EV*.

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
control sizes and focus (§4), the layout and breakpoints (§5), copy rules (§6) and how to verify a
change:

📍 [`DESIGN.md:85-88`](../DESIGN.md#L85-L88)
```markdown
## 7. Checking a UI Change
- Run `npm run build`, `npm run lint` and `npm test` in `frontend/`.
- Screenshot at 1360px and 390px wide and check them against this file.
- The numbers on screen (EV, equity, coverage, top hands) must not change from a styling change.
```

The last line is the one to respect most: a styling change must never change the numbers.

**Where code and rulebook still disagree.** A small script (exercise 7) that checks font sizes,
radii and raw colours against the spec finds seven problems in today's CSS:

| Line | Problem | Rule |
|------|---------|------|
| [App.css:23](../frontend/src/App.css#L23) | title `1.35rem` (20.25px measured) | §3: nothing bigger than `1.25rem` |
| [App.css:563](../frontend/src/App.css#L563) | drawer arrow `0.75rem` (11.25px measured) | §3: smallest `0.87rem` |
| [App.css:50](../frontend/src/App.css#L50), [:278](../frontend/src/App.css#L278) | `border-radius: 2px` | §1: radius is `3px` everywhere |
| [App.css:277](../frontend/src/App.css#L277), [:285](../frontend/src/App.css#L285), [:310](../frontend/src/App.css#L310) | raw `rgba()` / `#D9A63F` | §2: colours come from the tokens |

The accent rule itself holds. `grep 'var(--accent)'` finds exactly five uses: the focus ring, the
focused input border, the slider's `accent-color`, and the main button's background and border.

---

## 💡 Concept: CSS custom properties (tokens)

```css
:root { --accent: #E6B450; }                  /* define once, on the root element */
.tactical-btn { background: var(--accent); }  /* use anywhere below it */
```

A custom property is a named value that every element inherits. Change `--accent` once and every
`var(--accent)` follows. Unlike a Python constant it is resolved by the browser at run time, so you
can override it live in DevTools. A value typed directly (`#D9A63F`) does **not** follow (exercise 2).

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
  Only controls, the error and the open notes panel get a border (DESIGN.md:11).
- **The system font, no motion, no effects.** Nothing to download, animate or tune.
- **Keeping the old class names.** The restyle stayed a CSS-and-copy change and the old tutorial
  stayed accurate. The cost: vocabulary that contradicts DESIGN.md §1, plus dead classes.
- **A written spec.** DESIGN.md turns taste into checkable rules, so future changes, by you or by an
  AI assistant, can be reviewed against it.

---

## ⚠️ Weak spots

1. **Legacy names contradict the rulebook.** `terminal-*`, `tactical-*`, `hud-*`, `radar-slider` and
   `telemetry-*` ([App.css](../frontend/src/App.css)) use the vocabulary [DESIGN.md:7](../DESIGN.md#L7)
   bans, and so do JSX comments such as "Tactical Header & Telemetry Status"
   ([App.jsx:135](../frontend/src/App.jsx#L135)). `mono-*` is not monospace. *Fix:* rename (exercise 5).
2. **Dead class names.** 18 classes set in `App.jsx` have no rule, for example `green-glow`
   ([App.jsx:439](../frontend/src/App.jsx#L439)) and `cat-pill`
   ([App.jsx:501](../frontend/src/App.jsx#L501)). *Fix:* delete them (exercise 6).
3. **Sizes and radii outside the spec.** The title ([App.css:23](../frontend/src/App.css#L23)) is too
   big, the drawer arrow ([:563](../frontend/src/App.css#L563)) too small, and two corners use `2px`
   ([:50](../frontend/src/App.css#L50), [:278](../frontend/src/App.css#L278)). *Fix:* exercise 4.
4. **Colours that bypass the tokens.** `#D9A63F` ([App.css:310](../frontend/src/App.css#L310)) and two
   `rgba()` copies of `--bad` and `--good` ([App.css:277](../frontend/src/App.css#L277),
   [:285](../frontend/src/App.css#L285)). Change a token and these stay behind. *Fix:* exercise 8.
5. **Nothing enforces DESIGN.md.** §7 ([DESIGN.md:85-88](../DESIGN.md#L85-L88)) relies on manual
   screenshots, so every problem above went unnoticed. *Fix:* a check script in CI (exercise 7).
6. **The rulebook has drifted too.** DESIGN.md §6 says all UI strings live in `i18n.js`, but some
   don't (lesson 13, weak spot 9). Its own §5 calls the footnote "Engine specs" in a file that bans
   "engine" styling, and that footnote says "Monte Carlo" although the data is exact (lesson 04).

---

## 🧪 Try it

Run from `frontend/`.

Every use of the accent:

```bash
grep -n 'var(--accent)' src/index.css src/App.css
```

```
src/index.css:52:  outline: 2px solid var(--accent);
src/App.css:153:  border-color: var(--accent);
src/App.css:232:  accent-color: var(--accent);
src/App.css:302:  background: var(--accent);
src/App.css:304:  border: 1px solid var(--accent);
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
console.log([...names].filter((n) => !css.includes("." + n)).sort().join(" "));
'
```

```
action-badge amber-metric brand-green brand-group brand-white cat-pill chip-partial dim-metric green-glow highlight-val holding-class hud-label spec-label status-chip table-panel terminal-card verdict-col-left white-metric
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
Try it without editing files: in DevTools, add `--accent: #59C2FF` to `:root`.

<details><summary>Solution</summary>

The "Run solver" button, the slider, the focus ring and a focused input's border turn blue: the
five `var(--accent)` uses. **Hovering** the button still shows yellow, `rgb(217, 166, 63)`, because
[App.css:310](../frontend/src/App.css#L310) hard-codes `#D9A63F`. That is weak spot 4.
</details>

**🟢 3. Predict.** How many pixels are `0.87rem` and `1.35rem` on this page? Check under
DevTools, Computed.

<details><summary>Solution</summary>

`:root` sets `font-size: 15px`, so `0.87rem` = 13.05px and `1.35rem` = 20.25px (the title).
DESIGN.md's "0.87rem (13px)" assumes this root. With the default 16px it would be 13.92px.
</details>

**🟡 4. Follow the rulebook.** Fix the four size and radius breaks: the title to `1.25rem`
([App.css:23](../frontend/src/App.css#L23)), the drawer arrow to `0.87rem`
([:563](../frontend/src/App.css#L563)), and both `2px` radii to `var(--radius)`
([:50](../frontend/src/App.css#L50), [:278](../frontend/src/App.css#L278)). Check: DESIGN.md §7 (build,
lint, test, screenshots at 1360px and 390px) and the numbers on screen unchanged.

<details><summary>Solution</summary>

Four one-line edits. The build succeeds, the title is 18.75px like the verdict, and the script from
exercise 7 drops from seven problems to three (the colours). Undo with `git checkout -- frontend/src/App.css`.
</details>

**🟡 5. Rename a legacy class.** Rename `tactical-btn` to `solve-btn` in
[App.jsx:374](../frontend/src/App.jsx#L374) and in the three rules at
[App.css:298-316](../frontend/src/App.css#L298-L316). Check: `grep -rn tactical-btn src` prints
nothing, the build succeeds and the button still looks the same. Then run
`python3 learning/verify_course.py` from the repository root.

<details><summary>Solution</summary>

`sed -i 's/tactical-btn/solve-btn/g' src/App.jsx src/App.css` changes 4 occurrences and nothing
moves on screen. But the checker now reports `excerpt differs from ../frontend/src/App.css:298-311`
for this lesson: the price the restyle avoided by keeping old names. A real rename updates the
course in the same commit. Undo with `git checkout -- frontend/src/App.jsx frontend/src/App.css`.
</details>

**🟡 6. Delete dead classes.** Remove `green-glow`, `white-metric`, `amber-metric` and `dim-metric`
from the summary rows ([App.jsx:439-471](../frontend/src/App.jsx#L439-L471)). Check: the 🧪 scan no
longer lists them, and the summary looks exactly the same.

<details><summary>Solution</summary>

Keep `hud-value` everywhere and the `green-metric` branch on the EV row. None of the four removed
names had a rule, so nothing changes visually, which proves they were dead. Undo with
`git checkout -- frontend/src/App.jsx`.
</details>

**🔴 7. Make the rulebook executable.** Write `frontend/check-design.mjs` that reads both CSS files
and reports, with `file:line`, every `font-size` in `rem` outside 0.87–1.25, every `border-radius`
that is not `var(--radius)`, and every hex or `rgba()` colour outside a `--token:` line. It should
exit 1 if it finds anything. Check: `node check-design.mjs`.

<details><summary>Solution</summary>

```js
import fs from "node:fs";
let problems = 0;
const report = (at, msg) => { console.log(`${at}  ${msg}`); problems++; };
for (const file of ["src/index.css", "src/App.css"]) {
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

On today's CSS it prints seven lines (App.css 23, 50, 277, 278, 285, 310, 563), then
`7 problem(s)`, and exits 1. After exercises 4 and 8 it prints `0 problem(s)` and exits 0. Delete
the file to undo.
</details>

**🔴 8. Tokens only.** Add `--accent-hover`, `--good-zone` and `--bad-track` to `:root` in
`index.css`, and use them at [App.css:277](../frontend/src/App.css#L277),
[:285](../frontend/src/App.css#L285) and [:310](../frontend/src/App.css#L310). Check:
`grep -n -E '#[0-9A-Fa-f]{6}\b|rgba?\(' src/App.css` (today: lines 277, 285, 310) prints nothing.
Does the button's hover now follow a change of `--accent`?

<details><summary>Solution</summary>

```css
  --accent-hover: #D9A63F;
  --good-zone: rgba(170, 217, 76, 0.45);
  --bad-track: rgba(240, 113, 120, 0.2);
```

The grep prints nothing, and together with exercise 4 the script reports `0 problem(s)`. The hover
still does not follow `--accent`: it is its own token. Changing the accent now means two tokens, but
both sit in one place. Undo with `git checkout -- frontend/src/index.css frontend/src/App.css`.
</details>

---

## ❓ Quiz

1. Why does `0.87rem` mean 13.05px on this page?
2. What does `min-width: 0` on the grid's children prevent?
3. Why does the code hide the spin arrows with two different mechanisms?
4. DESIGN.md allows `--accent` in three places. Which five CSS lines use it, and do they keep the rule?
5. Why were names like `tactical-btn` and `hud-card` kept after the restyle, and what does it cost?

<details><summary>Answers</summary>

1. `:root` sets `font-size: 15px` ([index.css:22](../frontend/src/index.css#L22)), and `rem` is relative
   to the root element's font size: 0.87 × 15 = 13.05.
2. A grid item cannot normally be narrower than its content, so the wide tables would make the page
   scroll sideways on a phone. With it, the column shrinks and the tables scroll in their wrapper.
3. Browsers draw them differently: Firefox honours `appearance: textfield`, while Chrome and Safari
   need the `::-webkit-…-spin-button` pseudo-elements set to `-webkit-appearance: none`.
4. Focus ring (index.css:52), focused input border (App.css:153), slider (App.css:232), main button
   background and border (App.css:302, 304). Yes: the input border is part of focus.
5. So that the old tutorial, which quoted the CSS and JSX, stayed accurate. The cost: vocabulary that
   DESIGN.md bans, `mono-*` classes that are not monospace, and 18 dead names nothing checks.
</details>

---

## Recap

- `index.css` holds twelve colour tokens, the 3px radius, the 15px system font (`1rem` = 15px) and the
  `:focus-visible` ring. `App.css` uses them through `var(--…)`.
- The layout is a `340px 1fr` grid whose divider is a border. Breakpoints at 1024px (one column),
  640px (verdict and summary stack) and 480px (16px padding). Tables scroll, the page does not.
- The stepper hides native spin arrows with `appearance: textfield` and the WebKit pseudo-elements.
- Summary rows are small grids with fixed column widths. Tables use 1px lines, and colour only
  carries meaning (raise/fold, ±EV, errors).
- `terminal-*`, `tactical-*` and `hud-*` are legacy names kept on purpose; 18 names in `App.jsx` have no rule.
- DESIGN.md is the rulebook. Today's CSS breaks it in seven places, which a short script can find.

**Next:** [15 — Tests and performance](15-tests-and-performance.md)
