# VoxPilot Brand Guidelines

**Product:** VoxPilot  
**Short name:** VoxPilot  
**Description:** AI Voice Platform for Service Businesses & Call Centers  

**Primary tagline:** Build AI Voice Agents for Any Business.  
**Secondary tagline:** Answer every call, automate conversations, and help your team focus on what matters.

**Personality:** Modern · Premium · Intelligent · Enterprise-ready · Trustworthy · Human · Minimal  

Avoid playful, cartoonish, or generic “AI startup” aesthetics.

---

## Logo

The mark combines a forward chevron (pilot trajectory / connection) with a center node and three voice arcs (conversation / sound). It is original to VoxPilot and must not be redrawn to resemble competitor marks.

### Variants

| File | Use |
|------|-----|
| `logo.svg` / `logo-light.svg` | Horizontal lockup on light backgrounds |
| `logo-dark.svg` | Horizontal lockup on dark backgrounds |
| `logo-stacked.svg` | Narrow layouts, mobile splash, social square |
| `icon.svg` | App icon, favicon source, compact UI |
| `icon-white.svg` | Icon on dark / brand-colored fields |
| `icon-mono.svg` | Single-color / print / watermark |
| `favicon.svg` / `.ico` | Browser tabs |
| `apple-touch-icon.png` | iOS home screen (180×180) |
| `pwa-192.png` / `pwa-512.png` | Progressive web app |
| `social-preview.png` | Open Graph / Twitter (1200×630) |

### Clear space

Keep empty margin around the mark equal to **at least half the icon height** on all sides. Do not crowd with other UI or text.

### Minimum sizes

| Context | Minimum |
|---------|---------|
| Icon only (digital) | 16×16 px |
| Favicon | 16×16 px |
| Horizontal logo | 88 px wide |
| Print | 12 mm wide (icon) |

### Do

- Use official SVG/PNG assets from `/branding`
- Prefer SVG on web for crisp high-DPI rendering
- Use white / light lockups on dark hero surfaces
- Use dark / color lockups on light surfaces
- Pair the wordmark with Inter at medium/semibold weight

### Don’t

- Stretch, skew, rotate, or add drop shadows to the mark
- Recolor arcs arbitrarily outside the palette
- Place the logo on busy photography without a solid scrim
- Add a microphone, speech bubble, robot, or chatbot glyph
- Outline or stroke the wordmark
- Use low-contrast combinations (e.g. teal on teal)

---

## Color palette

| Token | Hex | Role |
|-------|-----|------|
| Primary | `#0F766E` | Brand actions, key UI, logo arcs |
| Secondary | `#14B8A6` | Highlights, secondary actions |
| Accent | `#0EA5E9` | Focus, links accent, node in mark |
| Background | `#FAFAFA` | App / page background |
| Surface | `#FFFFFF` | Cards, panels, inputs |
| Dark background | `#0F172A` | Hero, sidebar, dark mode base |
| Border | `#E5E7EB` | Dividers, input borders |
| Success | `#16A34A` | Positive states |
| Warning | `#F59E0B` | Caution |
| Error | `#DC2626` | Errors, destructive |
| Text | `#111827` | Primary copy |
| Muted | `#6B7280` | Secondary copy |

### Contrast

All body text combinations (Text on Surface / Background, Text on Dark with white) should meet **WCAG AA**. Prefer Text (`#111827`) on Surface; white on Dark Background. Primary buttons: white text on Primary.

---

## Typography

| Role | Family | Notes |
|------|--------|-------|
| Headings | Inter | Semibold / medium; tight tracking on large display sizes |
| Body | Inter | Regular / medium; comfortable line-height |
| Mono | IBM Plex Mono | Code, IDs, technical labels |

Do not substitute Inter with generic system stacks for marketing surfaces when webfonts are available.

---

## Icon usage

- Prefer the VoxPilot mark for product identity; Lucide (or equivalent) for functional UI icons
- Functional icons: 1.5–2 px stroke, rounded caps, aligned to 24 px grid
- Never replace the brand mark with a generic mic or bot icon

---

## Voice & naming

- Product name is always **VoxPilot** (one word, capital V and P)
- Do not abbreviate to “VP” in customer-facing UI
- Package / code namespaces may remain historical (`callbot_platform`, repo folder names) — do not rename those without a migration plan

---

## Accessibility checklist

- [ ] Logo has meaningful `alt` text (“VoxPilot”)
- [ ] Icons that are decorative use `aria-hidden`
- [ ] Theme supports light and dark surfaces with appropriate lockups
- [ ] Favicons and PWA icons provided at multiple densities
- [ ] SVG paths stay simple and optimized

---

## Asset locations

- Source of truth: `/branding`
- Marketing site: `web/public/branding` (+ root favicons / `og.png`)
- Ops console: `ops/public/branding` (+ root favicons)
