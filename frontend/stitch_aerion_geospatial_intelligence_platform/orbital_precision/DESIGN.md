---
name: Orbital Precision
colors:
  surface: '#101319'
  surface-dim: '#101319'
  surface-bright: '#36393f'
  surface-container-lowest: '#0b0e13'
  surface-container-low: '#191c21'
  surface-container: '#1d2025'
  surface-container-high: '#272a30'
  surface-container-highest: '#32353b'
  on-surface: '#e1e2ea'
  on-surface-variant: '#bbc9ce'
  inverse-surface: '#e1e2ea'
  inverse-on-surface: '#2d3036'
  outline: '#869398'
  outline-variant: '#3c494d'
  surface-tint: '#38d7ff'
  primary: '#b3ebff'
  on-primary: '#003642'
  primary-container: '#38d7ff'
  on-primary-container: '#005a6e'
  inverse-primary: '#00677d'
  secondary: '#c8bfff'
  on-secondary: '#2e148c'
  secondary-container: '#4835a5'
  on-secondary-container: '#baaeff'
  tertiary: '#ffdeac'
  on-tertiary: '#432c00'
  tertiary-container: '#ffba38'
  on-tertiary-container: '#6f4c00'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#b3ebff'
  primary-fixed-dim: '#38d7ff'
  on-primary-fixed: '#001f27'
  on-primary-fixed-variant: '#004e5f'
  secondary-fixed: '#e5deff'
  secondary-fixed-dim: '#c8bfff'
  on-secondary-fixed: '#1a0064'
  on-secondary-fixed-variant: '#4633a2'
  tertiary-fixed: '#ffdeac'
  tertiary-fixed-dim: '#ffba38'
  on-tertiary-fixed: '#281900'
  on-tertiary-fixed-variant: '#604100'
  background: '#101319'
  on-background: '#e1e2ea'
  surface-variant: '#32353b'
typography:
  display-xl:
    fontFamily: Geist
    fontSize: 40px
    fontWeight: '500'
    lineHeight: 48px
    letterSpacing: -0.03em
  display-xl-mobile:
    fontFamily: Geist
    fontSize: 28px
    fontWeight: '500'
    lineHeight: 34px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-sm:
    fontFamily: Geist
    fontSize: 18px
    fontWeight: '500'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Geist
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: 0em
  body-sm:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: 0.005em
  data-mono-lg:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
    letterSpacing: 0.02em
  data-mono-sm:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 14px
    letterSpacing: 0.04em
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '600'
    lineHeight: 12px
    letterSpacing: 0.08em
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
  canvas-margin: 1.5rem
  panel-gutter: 0.75rem
  sidebar-width: 20rem
  inspector-width: 24rem
---

## Brand & Style

The design system projects absolute operational clarity, scientific rigor, and cinematic restraint for mission-critical geospatial intelligence. Built for planetary observers, intelligence analysts, and scientific directors, the aesthetic avoids speculative sci-fi tropes or decorative cyberpunk neon. Visual hierarchy prioritizes raw observational data over chrome: the canvas dominates, tools recede until summoned, and data streams present themselves with the calm authority of an aerospace telemetry console.

### Aesthetic Foundation
- **Visual Weight**: A 70/30 spatial hierarchy where the visual or telemetry canvas claims unconditional dominance, flanked by razor-sharp, low-profile tool arrays.
- **Atmospheric Palette**: Deep, abyssal dark-neutrals mimic deep-orbit instrumentation. Accents serve purely as selective optical pings rather than decorative illumination.
- **Editorial Density**: Information density is counterbalanced by deliberate negative margins, crisp dividing hairpins, and precise, proportional data micro-typography.

## Colors

The system relies on an ultra-disciplined dark neutral hierarchy, deploying color strictly for semantic state transmission, target classification, and precise vector cues.

### Color Rules & Application
- **Canvas Base (`#080B10`)**: The deepest floor. Exclusively reserved for spatial map rendering, point clouds, raster analysis planes, and outer canvas margins.
- **Instrument Surface (`#10151D`)**: The primary containment layer for floating telemetry HUDs, collapsed panels, dock toolbars, and global navigation.
- **Elevated Surface (`#151C25`)**: Context menus, active inspect drawers, popover metadata chips, and dragged layers.
- **Restrained Vector Accent (`#38D7FF`)**: Used sparingly for targeted focal points, vector crosshairs, active coordinate locks, and pinpoint telemetry pings. Never use outer drop-shadow glows or neon strokes.
- **Machine Intelligence (`#9C8CFF`)**: Reserved exclusively for algorithmic insights, synthetic aperture radar (SAR) inference paths, and automated predictive boundaries.
- **Status Indicators**:
  - `Critical (#FF5368)`: Immediate breach, anomaly detection, telemetry disconnect.
  - `Warning (#F4B74A)`: Sensor drift, occlusion, low-confidence alignment.
  - `Success (#3DDC97)`: Calibrated, lock acquired, nominal packet flow.

## Typography

Typography balances Scandinavian editorial neutrality with the strict tabular cadence of scientific instrumentation.

### Typographic Roles
- **Geist**: Carries all narrative layers, global navigation, filter parameters, and section titles. Rendered at medium to regular weights with slightly negative tracking to reinforce structural solidity.
- **JetBrains Mono**: Assigned to latitude/longitude matrices, azimuth angles, sensor timestamps, UTC clocks, spectral wavelengths, and categorical tags. Numeric tabular data (`font-variant-numeric: tabular-nums`) must be enabled globally for monospaced elements to prevent layout jitter during live telemetry feeds.
- **Casing**: Monospaced utility markers (`label-caps`) always render uppercase with wide letter spacing (+0.08em) to ensure immediate legibility under dim ambient lighting conditions.

## Layout & Spacing

Designed desktop-first (optimizing for 1920×1080 and ultrawide tactical command screens), the spatial structure prioritizes unbounded viewing area for geospatial layers.

### Layout Model
- **Viewport Canvas Grid**: A decoupled viewport model where the primary geospatial stage occupies 100vw × 100vh. Instrumentation, telemetry docks, and control panels float or dock with precise 12px (`space-md`) panel gutters.
- **Dock Paneling**: Primary control sidebars (`20rem` / 320px) anchor to the left; the contextual spatial inspector (`24rem` / 384px) glides onto the right edge. Panels preserve a minimum 70% unoccluded central viewport at 1920×1080 resolution.
- **Micro Spacing**: Strict 4px base increment (`0.25rem`). Internal component paddings rely primarily on `space-xs` and `space-sm` to maintain dense, expert-level utility without visual bloat.

### Breakpoint Matrix
- **Desktop Ultra (>=1920px)**: Persistent left command bar, 70%+ center interactive viewport, persistent multi-source right inspector.
- **Desktop Standard (1280px - 1919px)**: Inspector collapses into a floating, auto-hiding overlay ribbon.
- **Compact / Tablet (<1280px)**: Bottom horizontal timeline collapses into a swipeable telemetry drawer; all lateral panels convert to full-height slide-over surfaces.

## Elevation & Depth

Elevation is achieved without blurry physical drop shadows or heavy skeuomorphic effects. Instead, spatial depth uses calibrated tonal layering, subtle hairline perimeter borders, and subdued optical translucency.

### Depth Architecture
1. **Level 0 (Map & Canvas Bed)**: Pure `#080B10`. Ground level for visual telemetry, vectors, satellite tiles, and volumetric point fields.
2. **Level 1 (Docked Consoles & Nav Bars)**: `#10151D` with a subtle 1px border rendered in `rgba(245, 247, 250, 0.06)`. No box shadows.
3. **Level 2 (Floating Instrument HUDs & Inspector Cards)**: Backed by `rgba(16, 21, 29, 0.85)` with `backdrop-filter: blur(12px)`. Structural perimeter defined by a razor 1px border `rgba(245, 247, 250, 0.1)`. A low-opacity ambient rim (`box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45)`) creates clean edge separation from bright satellite imagery.
4. **Level 3 (Target Focus Modals & Critical Overlays)**: `#151C25` surface with border `rgba(56, 215, 255, 0.3)`. Elevated with `box-shadow: 0 16px 40px rgba(0, 0, 0, 0.6)`.

Glows, heavy colored outlines, and diffuse neon lights are strictly prohibited. Light manifests only through sharp, vector-grade precision.

## Shapes

The interface expresses technical instruments rather than consumer software, using a disciplined, low-radius shape system (`roundedness: 1`).

### Geometry Guidelines
- **Containers, Panels & Drawers**: 4px (`0.25rem`) corner radius. Maintains an architectural, calibrated profile that aligns cleanly with grid intersections.
- **Buttons, Inputs & Selectors**: 4px (`0.25rem`). Ensures crisp tactile containment without distracting curvature.
- **Badges, Status Nodes & Pings**: 2px (`0.125rem`) or sharp circular forms for status pings (e.g., target reticle nodes, satellite tracking dots).
- **Pill geometries**: Prohibited except for spatial status tags requiring immediate differentiation from rectangular data fields.

## Components

### Buttons & Trigger Controls
- **Primary**: High-contrast, clean action block. Background `#F5F7FA`, text `#080B10`, font Geist medium. Hover transitions to `rgba(245, 247, 250, 0.9)`. No borders or glow.
- **Secondary / Ghost**: Surface `#10151D`, 1px border `rgba(245, 247, 250, 0.1)`, text `#F5F7FA`. On hover: border shifts to `rgba(56, 215, 255, 0.4)`, text accents subtly to `#38D7FF`.
- **Destructive**: Low-profile dark background with 1px hairline `rgba(255, 83, 104, 0.4)`, text `#FF5368`.

### Chips & Coordinate Tags
- Compact container styled in JetBrains Mono (`data-mono-sm` or `label-caps`). Height 22px, padding 2px 6px.
- Subtle `rgba(245, 247, 250, 0.04)` fill, bordered by hairline `rgba(245, 247, 250, 0.08)`.
- Status variation relies on a single 4px solid square or circle indicator at the leading edge (e.g., `#3DDC97` for active orbital sensor lock).

### Input Fields & Parameter Steppers
- Input background `#080B10`, height 32px, text `#F5F7FA`, placeholder `#9AA6B2` at 50% opacity.
- Border is 1px `rgba(245, 247, 250, 0.1)`. Focus state changes border to clean `#38D7FF` with zero spread glow.
- Technical parameters (coordinates, optical zoom scales, UTC bounds) render strictly in `JetBrains Mono`.

### Inspection Cards & HUD Modules
- Layered floating card on Level 2 elevation (`rgba(16, 21, 29, 0.85)` + 12px blur).
- Card headers feature an uppercase `label-caps` category indicator in `#9AA6B2` with an adjacent 1px rule spanning the remaining width.
- Values use a dual-stack layout: large, high-legibility tabular number above, concise secondary unit label below.

### Geospatial Targeting Reticles & Crosshairs
- 1px hairline geometry utilizing `#38D7FF` at 60% default opacity, resolving to 100% on target acquisition.
- Corner crop markers: 6px line segments framing bounding boxes for inferred anomalies and tracked vessels.
- Coordinate reads float adjacent to the cursor with a 4px offset in JetBrains Mono 10px.