---
name: y2k-design
description: Design and build websites and web apps in the Retro Y2K / early-internet aesthetic — OS-style windows, pixel fonts, grid backgrounds, hard box-shadows, pastel palettes, and delightful micro-animations. Use this skill whenever the user asks to design or build anything in a "Y2K style", "retro internet", "early 2000s UI", "windows XP vibe", "vaporwave UI", "pixel aesthetic", "nostalgia web", or says things like "make it look retro", "I want that old-school computer look", "Y2K design", or "bubblegum tech aesthetic". Always use this skill — do NOT attempt Y2K design from memory alone. Even if the user only says "retro" or "nostalgic", consider triggering this skill and confirming with them.
---

# Y2K Design Skill

Build interfaces that look like they escaped from a 2001 desktop — pixel fonts, OS window chrome, hard shadows, and pastel chaos. No gradients on buttons. No blur. No rounded pills. No emoji. Real icons only.

---

## Step 1 — Ask Clarifying Questions

Before writing a single line of code, ask these questions. If the user says "just pick" or "use the default", use the defaults listed below.

```
Hey! Before I build this, a few quick questions to nail the Y2K vibe:

1. **Color palette** — which direction fits best?
   - 🌸 Bubblegum: hot pink + yellow windows + cream — warm & girly
   - 🌀 Vaporwave: pink-to-purple gradient bg + lavender windows + blue accents
   - 🩵 Y2K Blue: sky blue background + white windows + pastel pink/mint accents
   - 🌿 Pastel Pixel: mint-to-pink gradient + light blue window borders + lime title bars
   - Custom: describe your colors

2. **Pixel font intensity** — how heavy is the retro feel?
   - Full pixel: Press Start 2P everywhere (very retro, harder to read)
   - Hybrid (default): pixel font for headers/UI chrome, rounded sans for body text
   - Subtle: pixel font for accents only

3. **Window style** — should the layout use OS-style draggable windows, or apply Y2K styling to a normal web layout?
   - OS windows (default for landing pages / apps)
   - Normal layout with Y2K styling applied

4. **Background** — grid paper (default), solid color, or gradient?
```

**If no answer, use:** Bubblegum palette · Hybrid font · OS windows · Grid background.

---

## Step 2 — Design System

### Color Palettes

```css
/* BUBBLEGUM (default) */
--bg:           #FF85C2;
--bg-grid:      #FF6FAF;
--window-body:  #FFF5DC;
--title-bar:    #FFD84D;
--border:       #1A0A2E;
--text-primary: #1A0A2E;
--text-muted:   #6B4C6B;
--btn-primary:  #FFD84D;
--btn-danger:   #FF3D6B;
--accent:       #C8A0FF;
--sparkle:      #FF3D9A;

/* VAPORWAVE */
--bg:           linear-gradient(135deg, #FF6EB4 0%, #8050D0 100%);
--window-body:  #C8A8FF;
--title-bar:    #9060E0;
--border:       #1A0028;
--btn-primary:  #4898FF;
--accent:       #FF3D9A;

/* Y2K BLUE */
--bg:           #7DD3F7;
--bg-grid:      #6BC5EF;
--window-body:  #FFFFFF;
--title-bar:    #FFB8D4;
--border:       #1A2A4A;
--btn-primary:  #FFE040;
--accent:       #B8F5D8;

/* PASTEL PIXEL */
--bg:           linear-gradient(135deg, #C0EAC0 0%, #FFD0E8 100%);
--window-body:  #FFFFFF;
--title-bar:    #B8E840;
--border:       #4080C0;
--btn-primary:  #FFE040;
--accent:       #FFB8D4;
```

### Typography

```css
/* Load from Google Fonts */
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=VT323:wght@400&family=Nunito:wght@400;600;700;800&display=swap');

--font-pixel:   'Press Start 2P', monospace;   /* headlines, window titles, UI chrome */
--font-pixel-lg:'VT323', monospace;             /* large display text, dialog bodies */
--font-body:    'Nunito', sans-serif;           /* body copy, labels */

/* Scale */
h1: Press Start 2P, 18–24px, line-height 1.6
h2–h3: Press Start 2P, 12–16px, line-height 1.8
Window title: Press Start 2P, 9–10px
Body text: Nunito 700, 14–16px
Captions/labels: Nunito 600, 12px, uppercase
```

### Core CSS Primitives

```css
/* ── THE WINDOW ── */
.y2k-window {
  background: var(--window-body);
  border: 2px solid var(--border);
  box-shadow: 4px 4px 0 var(--border);
  border-radius: 0;
  overflow: hidden;
}
.y2k-title-bar {
  background: var(--title-bar);
  border-bottom: 2px solid var(--border);
  padding: 6px 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-family: var(--font-pixel);
  font-size: 9px;
  color: var(--text-primary);
  user-select: none;
}
.y2k-controls { display: flex; gap: 4px; }
.y2k-controls span {
  width: 12px; height: 12px;
  border: 1px solid var(--border);
  display: flex; align-items: center; justify-content: center;
  font-size: 8px; cursor: pointer;
  font-family: var(--font-pixel);
  background: var(--window-body);
}
.y2k-controls .close  { background: #FF5B5B; }
.y2k-controls .min    { background: #FFD84D; }
.y2k-controls .max    { background: #59D98F; }

/* ── BUTTONS ── */
.y2k-btn {
  font-family: var(--font-pixel);
  font-size: 9px;
  padding: 8px 16px;
  background: var(--btn-primary);
  border: 2px solid var(--border);
  box-shadow: 3px 3px 0 var(--border);
  cursor: pointer;
  border-radius: 0;
  color: var(--text-primary);
  transition: transform 80ms, box-shadow 80ms;
}
.y2k-btn:active {
  transform: translate(3px, 3px);
  box-shadow: 0 0 0 var(--border);
}
.y2k-btn:hover { filter: brightness(1.08); }

/* ── INPUT ── */
.y2k-input {
  font-family: var(--font-body);
  font-size: 13px;
  font-weight: 700;
  border: 2px solid var(--border);
  box-shadow: 2px 2px 0 var(--border);
  padding: 6px 10px;
  background: #fff;
  outline: none;
  border-radius: 0;
}
.y2k-input:focus { box-shadow: 2px 2px 0 var(--sparkle); }

/* ── GRID BACKGROUND ── */
.y2k-bg {
  background-color: var(--bg);
  background-image:
    linear-gradient(rgba(255,255,255,0.12) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.12) 1px, transparent 1px);
  background-size: 32px 32px;
  min-height: 100vh;
}

/* ── PROGRESS BAR ── */
.y2k-progress-track {
  border: 2px solid var(--border);
  background: #fff;
  height: 18px;
  box-shadow: 2px 2px 0 var(--border);
}
.y2k-progress-fill {
  height: 100%;
  background: repeating-linear-gradient(
    45deg,
    var(--btn-primary) 0px, var(--btn-primary) 8px,
    var(--border) 8px, var(--border) 10px
  );
  animation: progress-march 0.6s linear infinite;
}
@keyframes progress-march {
  from { background-position: 0 0; }
  to   { background-position: 14px 0; }
}

/* ── DIALOG BOX ── */
.y2k-dialog {
  background: var(--window-body);
  border: 2px solid var(--border);
  box-shadow: 6px 6px 0 var(--border);
  padding: 0;
  max-width: 280px;
}
.y2k-dialog-body {
  padding: 16px;
  font-family: var(--font-pixel-lg);
  font-size: 18px;
  line-height: 1.4;
  color: var(--text-primary);
}
.y2k-dialog-actions {
  border-top: 2px solid var(--border);
  padding: 10px 16px;
  display: flex; gap: 8px; justify-content: flex-end;
}

/* ── SPARKLE DECORATION ── */
.sparkle {
  display: inline-block;
  animation: sparkle-spin 3s linear infinite;
}
@keyframes sparkle-spin {
  0%, 100% { transform: scale(1) rotate(0deg); opacity: 1; }
  50%       { transform: scale(1.3) rotate(180deg); opacity: 0.7; }
}
```

### Layout Pattern

```
FULL OS-STYLE LAYOUT:
┌─────────────────────────────────────────────────┐
│  GRID BG                                        │
│  ┌──[window title]──[- □ X]┐  ┌──[title]──┐   │
│  │  content area            │  │ dialog    │   │
│  └──────────────────────────┘  └───────────┘   │
│                                                 │
│  ┌──[title]────────────────────────────────┐   │
│  │  main content window (wider)            │   │
│  └─────────────────────────────────────────┘   │
│─────────────── TASKBAR ──────────────────────── │
└─────────────────────────────────────────────────┘

NORMAL LAYOUT WITH Y2K STYLING:
- Section headers → window title bars
- Cards → y2k-windows
- CTAs → y2k-btn
- Grid bg on hero sections
```

---

## Step 3 — Micro-Animations

Apply all of these. They are non-negotiable for a quality Y2K result.

```css
/* 1. Window spawn on load */
@keyframes window-spawn {
  from { transform: scale(0.92); opacity: 0; }
  to   { transform: scale(1);    opacity: 1; }
}
.y2k-window { animation: window-spawn 200ms cubic-bezier(0.34,1.56,0.64,1) both; }

/* 2. Stagger windows */
.y2k-window:nth-child(1) { animation-delay: 0ms; }
.y2k-window:nth-child(2) { animation-delay: 80ms; }
.y2k-window:nth-child(3) { animation-delay: 160ms; }

/* 3. Icon pixel-jump on hover */
.y2k-icon:hover { transform: translateY(-3px); transition: transform 120ms steps(1); }

/* 4. Title bar hover scanline shimmer */
.y2k-title-bar::after {
  content: '';
  position: absolute; inset: 0;
  background: repeating-linear-gradient(
    transparent 0px, transparent 2px,
    rgba(255,255,255,0.06) 2px, rgba(255,255,255,0.06) 4px
  );
  pointer-events: none;
}

/* 5. Button press (defined above in .y2k-btn:active) */

/* 6. Sparkle pulse (defined above in .sparkle) */

/* 7. Screen-on flicker — apply once to root on page load */
@keyframes screen-flicker {
  0%   { opacity: 0; }
  10%  { opacity: 1; }
  12%  { opacity: 0; }
  14%  { opacity: 1; }
  100% { opacity: 1; }
}
body { animation: screen-flicker 0.4s ease-out both; }

/* 8. Scrollbar */
::-webkit-scrollbar { width: 12px; }
::-webkit-scrollbar-track { background: var(--window-body); border-left: 2px solid var(--border); }
::-webkit-scrollbar-thumb { background: var(--title-bar); border: 2px solid var(--border); border-radius: 0; }
::-webkit-scrollbar-thumb:hover { background: var(--accent); }
```

---

## Step 4 — Icons

**Always use Lucide icons** (available in React via `lucide-react`) for functional icons. Render them at 16–20px, stroke 1.5–2px, colored with `var(--border)` or `var(--text-primary)`.

Do **not** use emoji as icons. Do not use Font Awesome. Pixel-art SVG decorations are acceptable as *decorative elements only* (sparkle stars, pixel hearts, pixel clouds) — these should be hand-coded SVGs, not image embeds.

**Decorative pixel SVG shapes to include:**
- 4-pointed sparkle star: two rotated rectangles crossing at center
- Pixel cloud: series of overlapping squares
- Small pixel heart: classic 5×4 pixel heart shape
- Checkerboard tile: for image placeholder areas

---

## Step 5 — Anti-Patterns (Never Do These)

- ❌ `border-radius > 4px` on windows, buttons, or inputs
- ❌ `backdrop-filter: blur(...)` — no frosted glass
- ❌ `box-shadow` with blur radius (always `0` blur, offset only)
- ❌ Gradient buttons — flat fill only
- ❌ Google Fonts: Inter, Roboto, Poppins, DM Sans, or any "clean" sans-serif as primary
- ❌ CSS `emoji` or unicode emoji characters as icons
- ❌ Soft, airy whitespace — this is a dense UI, not a minimal SaaS
- ❌ Smooth `border-radius` pill shapes on buttons
- ❌ Dark mode defaults — Y2K is light, loud, and colorful
- ❌ Generic card components that look like Tailwind defaults
- ❌ `transition: all` — be specific with transition properties

---

## Step 6 — Output Checklist

Before presenting code, verify:
- [ ] Grid background applied to page root
- [ ] At least one OS-style window with title bar + control buttons
- [ ] Press Start 2P or VT323 used for headings/chrome
- [ ] All buttons have hard box-shadow + press animation
- [ ] Window spawn animation on load
- [ ] Screen flicker on body load
- [ ] Sparkle decorations present (at least 2)
- [ ] Scrollbars styled
- [ ] Lucide icons used for any functional iconography
- [ ] No blur, no pill shapes, no Inter font
