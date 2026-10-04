# Call & Flow Marketing Visual System

## Approach

Prefer **human-centric campaign storytelling** over gadget-only or illustration-only pages.

Story spine:

`REAL PERSON → REAL BUSINESS ENVIRONMENT → CUSTOMER CALL → AI VOICE AGENT → BUSINESS ACTION`

- **Primary**: Human business campaign scenes (`HumanBusinessVisual`)
- **Secondary**: React/CSS product frames (`CallFlowDiagram`, `VisualFrame`, glass overlays)
- **Depth**: Existing 22-asset 3D library (`Marketing3DVisual`) remains intact as supporting product intelligence
- **Delivery**: `next/image` for photography/3D; CSS/SVG for diagrams and glass UI

## Asset inventory

```text
public/images/
├── human/
│   ├── business/
│   │   ├── industries/       # 12 unique campaign scenes (HUMAN → AI → ACTION)
│   │   └── use-cases/        # 5 unique campaign scenes
│   └── core/                 # owner, receptionist, caller, handoff, sales, support
├── 3d/                       # kept intact (core + industries + use-cases)
├── hero/
├── product/
└── …
```

## Component map

| Component | Use |
|---|---|
| `HumanBusinessVisual` | Campaign visual: human + environment + AI + outcome UI |
| `HumanProductVisual` | Supporting human scene ± floating 3D chip |
| `Marketing3DVisual` | Optimized 3D still (library preserved) |
| `IndustryVisual` | Hero: campaign business visual + product flow |
| `UseCaseVisual` | Hero: campaign business visual + product flow |
| `SectionFlowVisual` | Story sections via `media` + optional `businessVisual` |
| `CallFlowDiagram` | Shared step/branch diagram |
| `VisualFrame` | Product chrome |

Config:

- `src/lib/marketing/human-business-visuals.ts` — campaign registry (industries + use cases)
- `src/lib/marketing/human-assets.ts` — supporting human registry + story media rhythm
- `src/lib/marketing/three-d-assets.ts` — 3D registry (kept intact)
- `src/lib/marketing/visuals.ts` — flow/step mockup data
- `src/lib/marketing/feature-sections.ts` — alternating story copy

## Campaign visual formula

Every major industry/use-case visual communicates:

1. Correct environment
2. Correct human role
3. Correct customer/business context
4. Correct AI workflow
5. Correct business action

Hierarchy:

- **HUMAN** = context
- **AI** = intelligence
- **UI** = outcome

Campaign photographs may include baked glass storytelling. The component also supports HTML/CSS overlays (`overlayMode: "html"`) for clean bases and responsive reduction of floating cards on mobile.

## Story visual rhythm

Each industry/use-case page maps **four media compositions**:

1. **human-product** — campaign `HumanBusinessVisual` (+ optional product chrome)
2. **three-d** — workflow 3D + `CallFlowDiagram`
3. **human-3d** — ops/booking human + CRM/calendar 3D
4. **human-handoff** — human receiving handoff + handoff 3D

Only assets for the current page are referenced.

## Priority by page type

| Page type | Priority order |
|---|---|
| Industry / use-case | Human campaign → Product UI → 3D |
| Core product pages | Product UI → 3D → Human |

## Image rules

- Meaningful visuals: descriptive `alt`
- Decorative bands inside labeled frames: `decorative`
- Below-fold images: lazy via `next/image`
- No fake logos, fake revenue, fake conversion stats, or fake testimonials
- Art direction: cinematic lighting, shallow DOF, natural professionals, restrained SaaS blue/teal accents
- Avoid cartoon, anime, cyberpunk neon, generic stock, or sci-fi robot aesthetics
