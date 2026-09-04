---
name: Precision Intelligence
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#464554'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#777586'
  outline-variant: '#c7c4d7'
  surface-tint: '#5148d7'
  primary: '#2a14b4'
  on-primary: '#ffffff'
  primary-container: '#4338ca'
  on-primary-container: '#c1beff'
  inverse-primary: '#c3c0ff'
  secondary: '#565e74'
  on-secondary: '#ffffff'
  secondary-container: '#dae2fd'
  on-secondary-container: '#5c647a'
  tertiary: '#7b0020'
  on-tertiary: '#ffffff'
  tertiary-container: '#a6002f'
  on-tertiary-container: '#ffb0b4'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e3dfff'
  primary-fixed-dim: '#c3c0ff'
  on-primary-fixed: '#100069'
  on-primary-fixed-variant: '#372abf'
  secondary-fixed: '#dae2fd'
  secondary-fixed-dim: '#bec6e0'
  on-secondary-fixed: '#131b2e'
  on-secondary-fixed-variant: '#3f465c'
  tertiary-fixed: '#ffdada'
  tertiary-fixed-dim: '#ffb3b6'
  on-tertiary-fixed: '#40000c'
  on-tertiary-fixed-variant: '#920028'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  display-hero:
    fontFamily: Plus Jakarta Sans
    fontSize: 44px
    fontWeight: '600'
    lineHeight: 52px
    letterSpacing: -0.03em
  display-hero-mobile:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.025em
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: -0.005em
  body-sm:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0em
  label-mono-md:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-caps-sm:
    fontFamily: Geist
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.06em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  space-2xs: 0.125rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-base: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
  space-2xl: 3rem
  space-3xl: 4rem
  gutter-desktop: 1.5rem
  margin-desktop: 3rem
  gutter-mobile: 0.75rem
  margin-mobile: 1rem
---

## Brand & Style

This design system embodies the calculated precision of high-velocity engineering tools paired with the understated reductionism of premium consumer hardware. Built for financial intelligence and automated synthesis, it discards legacy terminal clutter in favor of absolute signal fidelity, cognitive ease, and high-density legibility without visual exhaustion.

The aesthetic fuses **Modern Swiss Minimalism** with an **Instrumental Tech Ethos**:
- **Radical Reduction:** Layouts eliminate superfluous cards, drop shadows, and ornamental widgets. Data and typography act as the primary interface architecture.
- **Calm, Deliberate Focus:** A warm off-white foundational canvas provides an editorial calm, ensuring that high-stakes alerts command focus without inducing alarm fatigue.
- **Micro-Precision Engineering:** Tactile feedback, hair-thin 1px dividers, monospaced tabular alignments, and micro-badges deliver an exacting, authoritative feel.

## Colors

The palette establishes an intentional hierarchy: the canvas steps back into quiet warmth, deep carbon and obsidian ink establish clear optical weight, and vivid functional accents convey immediate systemic meaning.

### Canvas & Neutral Architecture
- **Canvas Base:** `#FAF9F6` — A warm, luminous alabaster neutral that eliminates glare while maintaining clean contrast.
- **Subtle Surface:** `#F1F3F5` — Recessed inputs, active states, and table headers.
- **Hairline Dividers & Ghost Borders:** `#E2E8F0` with alpha variants (`rgba(15, 23, 42, 0.06)`) for borderless row separators.
- **Muted Label Ink:** `#64748b` — Structural metadata, secondary keys, and timestamps.
- **Dominant Ink:** `#0F172A` — Primary metrics, titles, and decisive analytical readouts.

### Functional Accents
- **Primary Electric Cobalt (`#4338ca` / hover `#3730a3`):** Reserved for direct user intent, interactive focus vectors, active filter states, and system-level actions.
- **Critical Severity Coral (`#e11d48` / soft wash `#ffe4e6`):** High-urgency anomalies, downward volatility breaks, and severe systemic risks.
- **Transition Amber (`#d97706` / soft wash `#fef3c7`):** Volatility shifts, pending updates, and secondary watchpoints.
- **Alpha Emerald (`#059669` / soft wash `#d1fae5`):** Positive delta, confirmed execution, and upward signal momentum.

## Typography

The typographic hierarchy pairs **Plus Jakarta Sans** for structural headers with **Geist** for high-density analysis, body content, and numeric data sets.

### Principles
- **Tabular Numerics:** All currency, delta metrics, percentage markers, and timeline values must enforce `font-feature-settings: "tnum" on, "cv02" on, "cv03" on` to prevent layout reflow during live streaming updates.
- **Negative Tracking on Display:** Large headings use tight negative tracking (`-0.02em` to `-0.03em`) to mimic optical kerning found in Swiss modernism.
- **Precision Metadata:** Micro-labels and table headings (`label-caps-sm`) run in uppercase with expanded tracking (`+0.06em`) to ensure legibility at 11px.

## Layout & Spacing

The layout is built on a 4px baseline grid operating within an adaptive fluid framework, organized through continuous vertical flow rather than disconnected modules.

### Structural Philosophy
- **Anti-Container Architecture:** Avoid enclosing metrics and analysis within multiple nested bordered cards. Group data with whitespace gutters and subtle single-pixel baseline rules.
- **Grid Mechanics:**
  - **Desktop (≥1280px):** 12-column adaptive system with max-width `1440px`, 24px gutters, and 48px lateral safe margins. Data views can toggle into full-width "dense mode" utilizing a 16-column grid with 16px gutters.
  - **Tablet (768px – 1279px):** 8-column layout, 16px gutters, 24px lateral padding. Secondary collateral collapses beneath the primary signal feed.
  - **Mobile (<768px):** Single-column stacked stream, 12px gutters, 16px margins. Complex tabular grids reflow to atomic summary lines.

## Elevation & Depth

Visual hierarchy is maintained without heavy dropshadows or skeuomorphic bevels. Instead, depth is communicated through **tonal surfaces** and **whisper-thin hairline boundaries**.

- **Level 0 (Canvas Base):** Plain `#FAF9F6`. Ground floor for full feeds and primary reading viewports.
- **Level 1 (Subtle Inset / Grouped Surface):** Tinted `#F1F3F5` with zero borders, used for search inputs, segment selectors, and table headers.
- **Level 2 (Active Focus & Sticky Navigation):** Canvas background with a 1px border (`rgba(15, 23, 42, 0.08)`) and an ultra-diffused atmospheric shadow: `0 1px 2px rgba(15, 23, 42, 0.03), 0 4px 12px rgba(15, 23, 42, 0.02)`.
- **Level 3 (Command Menus & Modals):** Pure white background (`#FFFFFF`) with a 1px border (`rgba(15, 23, 42, 0.09)`) elevated by `0 12px 32px -4px rgba(15, 23, 42, 0.06), 0 4px 8px -2px rgba(15, 23, 42, 0.03)`.

## Shapes

The design system maintains a **Soft (Level 1)** geometric silhouette. Curvature is subtle and intentional, preventing UI elements from feeling toy-like while softening hard analytical edges:

- **Micro Components (Tags, Badges, Input Keys):** `4px` (`0.25rem`).
- **Standard Controls (Buttons, Inputs, Row Selectors):** `6px` (`0.375rem`).
- **Flyouts & Command Drawers:** `8px` (`0.5rem`).
- **Pills / Status Dots:** Fully rounded (`9999px`) reserved strictly for live connection pings, status indicators, and state dots.

## Components

### Buttons
- **Primary:** Deep slate (`#0F172A`) or Cobalt (`#4338ca`) solid fill, white text, 6px radius, height 36px (compact) or 40px (default). Smooth opacity shift (`0.92`) on hover. No harsh shadows.
- **Secondary / Ghost:** Transparent base with 1px border (`rgba(15, 23, 42, 0.1)`), deep slate text. Transitions to `#F1F3F5` on hover.
- **Micro Action:** Borderless 28px height icon or text trigger, muted slate color, turning deep slate on hover.

### Inputs & Command Bars
- **Surface:** `#FFFFFF` or recessed `#F1F3F5`, 1px border (`rgba(15, 23, 42, 0.1)`), 6px radius.
- **Focus State:** Hairline transition to Cobalt (`#4338ca`) accompanied by a subtle 2px ring at 15% opacity (`rgba(67, 56, 202, 0.15)`).
- **Keyboard Affordance:** Inline monospace shortcut tags (`⌘K`) in muted slate with a subtle `#E2E8F0` fill and 3px radius.

### Signal Badges & Chips
- Unbordered, soft tinted fills paired with high-contrast text:
  - **Severe Alert:** Background `rgba(225, 29, 72, 0.08)`, text `#BE123C`.
  - **Shift Alert:** Background `rgba(217, 119, 6, 0.08)`, text `#B45309`.
  - **Positive Momentum:** Background `rgba(5, 150, 105, 0.08)`, text `#047857`.
  - **Neutral Signal:** Background `rgba(15, 23, 42, 0.05)`, text `#334155`.
- Layout: 4px radius, 2px horizontal padding, 6px vertical padding, 11px Geist medium typography.

### Data Lists & Signal Rows (Replaces Standard Cards)
- Individual insights are presented as edge-to-edge list rows separated by 1px bottom dividers (`rgba(15, 23, 42, 0.06)`).
- Rows maintain a 12px to 16px vertical padding envelope with 8px horizontal clearance.
- Interactive rows transition to an ultra-soft `#F8F9FA` background wash on hover with smooth 120ms ease-out timing.

### Checkboxes & Segmented Controls
- **Checkboxes:** 16px square, 3.5px corner radius. Unchecked state is bordered with `rgba(15, 23, 42, 0.2)`. Checked state is solid Cobalt `#4338ca` with a crisp 1.5px white checkmark icon.
- **Segmented Filter Switcher:** Recessed `#EFEFED` track, 4px inner padding. Active tab sits on an elevated `#FFFFFF` pill with a 4px corner radius and a faint 1px ambient border.