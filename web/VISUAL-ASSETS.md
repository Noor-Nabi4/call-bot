# Call & Flow Marketing Visual System

## Approach

Prefer product UI mockups and workflow diagrams over lifestyle photography.

- **Primary visuals**: React/SVG product frames (`HeroVisual`, `ProductVisual`, `IndustryVisual`, `UseCaseVisual`, `CallFlowDiagram`)
- **Secondary photos**: curated desk/ops imagery already in `public/images/` (no smiling stock-people heroes)
- **Delivery**: `next/image` for photos (auto WebP/AVIF when supported); CSS/SVG for diagrams (zero extra bytes)

## Asset inventory

```text
public/images/
├── hero/
│   └── ai-voice-ops.jpg                 # waveform laptop + phone desk
├── product/
│   └── voice-ops-dashboard.jpg          # dual-monitor ops / CRM desk
├── industries/
│   └── industry-hub.jpg                 # multi-industry brochure desk
├── use-cases/
│   └── appointment-calendar.jpg         # calendar workspace
├── blog/                                # reserved for future article photos
├── ui/                                  # reserved for UI export frames
├── hero-voice-ops.jpg                   # legacy source (kept)
├── section-*.jpg                        # legacy sources (kept; not all used)
```

Unused on purpose (people-forward stock):

- `section-answer.jpg`
- `section-handoff.jpg`

## Component map

| Component | Use |
|---|---|
| `HeroVisual` | Homepage hero product preview + call flow |
| `ProductVisual` | `/ai-receptionist`, `/ai-voice-agents` |
| `IndustryVisual` | `/industries/[slug]` unique scenario mockups |
| `UseCaseVisual` | `/use-cases/[slug]` workflow mockups |
| `PricingVisual` | Subtle capacity meters on `/pricing` |
| `BlogCover` | Featured covers for `/blog` |
| `MarketingImage` | Optimized photo wrapper |
| `CallFlowDiagram` | Shared step/branch diagram |

Config lives in `src/lib/marketing/visuals.ts`.

## Where visuals appear

| Page | Visual |
|---|---|
| `/` | `HeroVisual` (LCP-critical product mock) |
| `/ai-receptionist` | Receptionist flow diagram |
| `/ai-voice-agents` | Platform branch diagram + ops photo |
| `/industries` | Industry hub photo |
| `/industries/*` | Unique industry scenario mockups |
| `/use-cases/*` | Unique workflow mockups (+ booking photo on appointment page) |
| `/pricing` | Minimal capacity visual |
| `/blog`, `/blog/*` | Featured covers (photo or generated product cover) |
| FAQ / CTA | No large images |

## Image rules

- Meaningful visuals: descriptive `aria-label` / `alt`
- Decorative chrome: `aria-hidden`
- Hero product mock is CSS (no heavy LCP photo on homepage)
- Below-fold photos use `loading="lazy"` via `next/image`
- Filenames describe content; no `image1.png`

## Future assets (optional)

If commissioning custom renders later:

| Filename | Page | Concept | Size | Priority |
|---|---|---|---|---|
| `product/ai-receptionist-3d.webp` | `/ai-receptionist` | Abstract phone + agent node | 1600×1066 | P2 |
| `product/ai-voice-agent-graph.webp` | `/ai-voice-agents` | Node graph of tools | 1600×1066 | P2 |
| `industries/hvac-dispatch.webp` | `/industries/hvac` | HVAC dispatch board UI | 1600×900 | P3 |
| `blog/ai-receptionist-cover.webp` | blog article | Phone UI abstract | 1600×900 | P2 |

Keep one cohesive dark UI chrome, teal accents, and soft depth — matching the existing brand tokens.
