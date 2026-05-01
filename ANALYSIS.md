# Tournament Analysis: How to Enhance life-as-code Dashboards

**Question:** How should we enhance the existing life-as-code dashboards (React + Vite + TypeScript + Plotly, custom in `frontend/src/features/dashboard/`) to better serve the longevity-analytics mission, given we have already ruled out replacing them with Grafana?

**Context (verified 2026-04-29):**

- Stack: React + Vite + TypeScript frontend; Flask + Dash + Plotly backend; PostgreSQL.
- Current dashboards: `frontend/src/features/dashboard/` (e.g. `SleepOverviewPage.tsx`).
- Domain: multi-source longevity analytics — Garmin, Hevy, Whoop, Eight Sleep — sleep, HRV, recovery, training load, weight, longevity score.
- Custom analytics: trend modes (Short/Mid/Long), z-scores, mode-aware windows (84/252/730d baselines), data fusion across sources, longevity score breakdown, Today-vs-Range branch.
- Multi-user with single-admin model, Fernet-encrypted credentials, privacy-first (self-hosted K3s).
- Mobile-first daily check-in is part of the product surface.
- Mission per CLAUDE.md: "build software that helps people live to 150" — bespoke longevity UX matters.
- User memory: ML/research stack uses local-first parquet + DuckDB + Polars + Jupyter (NOT K8s). Plans RTX 3090.

**Constraint from prior /think tournament (Grafana):** primary user-facing dashboards stay React-native. This analysis is about ENHANCING them, not replacing the stack.

**Tournament:** Round 1 (4 agents) → Round 2 (2 agents) → Final Synthesis (orchestrator).

## Round 1 — Visual & UI Specialist

### 1. Component library: adopt **Tremor 3.x + shadcn/ui** (hybrid)

Tremor was acquired by Vercel on 2025-01-22; **all Blocks are now MIT/free** ([Vercel blog](https://vercel.com/blog/vercel-acquires-tremor)). It ships 35 components + 300 blocks built on React + Tailwind + Radix ([tremor.so](https://www.tremor.so/)) — KPI cards with sparkline-delta, AreaChart with gradient, DonutChart, BarList, Tracker (calendar-heatmap-style adherence). This natively covers `SleepOverviewPage`'s "score + delta + 14-day trend" KPI surface in ~30 lines. Pair with **shadcn/ui** for Dialog/Tabs/Sheet/Skeleton primitives ([shadcn.io](https://www.shadcn.io/template/tremorlabs-tremor)). Avoid Mantine — too opinionated, fights Tailwind. Don't go full custom: you'll rebuild Tremor at 10x cost.

### 2. Charts: **keep Plotly for one screen, migrate KPI surfaces to Recharts; reserve ECharts for dense screens**

Plotly is excellent for scientific exploration but heavy (~3MB) and ugly defaults. **Recharts** (1.8M weekly downloads, declarative JSX, native `<ReferenceArea>` for z-score ±1/±2 bands, `<ReferenceLine>` for annotations) is the pragmatic dashboard pick ([LogRocket 2025](https://blog.logrocket.com/best-react-chart-libraries-2025/)). For dense multi-year heatmaps and small-multiples, **ECharts** handles 100k+ points ([PkgPulse 2026](https://www.pkgpulse.com/blog/recharts-vs-chartjs-vs-nivo-vs-visx-react-charting-2026)). Skip visx — D3 primitives = 2-3x build time. Skip Nivo for now (slower, but only WCAG-AA out of the box if accessibility audit lands).

### 3. Visual patterns to add immediately

- **Tremor `Tracker` component** = GitHub-style sleep-adherence heatmap, free.
- **Recharts `<ReferenceArea y1={-1} y2={1} fill="green" opacity={0.1}>`** = z-score bands inline.
- **Ghost-line overlay**: second `<Line strokeDasharray="4 4" opacity={0.4}>` for "last week".
- **Framer Motion `<AnimatePresence mode="wait">`** keyed on Short/Mid/Long mode — 200ms crossfade, not slide ([Motion Primitives](https://www.shadcn.io/template/ibelick-motion-primitives)).
- **shadcn `Skeleton`** with shimmer keyframe replaces current loading spinners.
- **Annotation layer**: workouts/illness as `<ReferenceDot>` with tooltip.

### 4. Theming

Adopt a **longevity-specific palette** (deep teal #0d4f4a recovery, amber #d97706 strain, oxblood #7c2d12 alert) — not generic SaaS blue/green. Dark mode default (users check at night). CSS vars via shadcn `globals.css`.

### 5. Mobile-first

- Bottom nav (5 icons: Today/Sleep/Train/Stats/Settings).
- Swipe between days via Framer Motion `drag="x"`.
- **Apple-Watch-style ring-of-rings** for Today: three concentric SVG arcs (Recovery/Sleep/Strain) — bespoke 60-line component.

---

**Summary:**

1. **Top recommendation:** Adopt Tremor 3.x (free post-Vercel) + shadcn/ui, migrate KPI cards in one sprint.
2. **Most impactful single enhancement:** Ring-of-rings daily summary on mobile home — visceral, Apple-grade, owns the "open the app at 7am" moment.
3. **DON'T:** Don't rip out Plotly wholesale on day one — keep it for the exploratory Statistics page where its zoom/pan/export beats Recharts. Migrating all charts at once = months of regression hell on a single-developer project.

## Round 1 — Codebase Reality Auditor

**Stack actually present** (`frontend/package.json`): React 19.2 + Vite 7 + TypeScript 5.9; **Recharts 3.6** is the sole charting lib; Tailwind 4.1 + custom shadcn-style primitives in `frontend/src/components/ui/` (no `components.json`, hand-rolled `Card`/`Button`/`Input`/`Skeleton`/`Spinner`); **TanStack Query 5.90** for data; Zustand 5; lucide-react icons; sonner toasts; date-fns 4; vite-plugin-pwa. No Tremor, no visx, no Plotly.

**Pages** (`features/dashboard/`): `DashboardOverview` (466 LoC), `SleepOverviewPage` (630), `StatisticsPage` (179, delegates to 7 sections under `statistics/`), `TrainingsPage` (574), `HealthLogPage` (741), `DataStatusPage` (484), `DashboardLayout` (248). Charts in `components/charts/` (15 files, 1 778 LoC), all Recharts-based.

**Data flow**: REST `/api/...` via `lib/api.ts` → React Query hooks (`useHealthData`, `useAnalytics`, `useTrendData`). Mode-aware z-scores are computed **server-side** — `useAnalytics(mode)` calls `api.analytics.get(mode)` and the frontend only consumes `metric_baselines`, `goodness_z_score`, `z_score` fields (`lib/report-formatter.ts` lines 325-440). Frontend `lib/statistics.ts` only does LOESS smoothing + local baseline summaries.

**Sharp pain points (concrete)**:

1. **Page bloat** — `HealthLogPage.tsx` 741 LoC, `SleepOverviewPage.tsx` 630, `TrainingsPage.tsx` 574, `DashboardOverview.tsx` 466. Date-range state, mode selector, summary cards, and chart layout are inlined per page (e.g. `ModeSelector` redefined in `SleepOverviewPage.tsx:36-62`); no shared `<DashboardShell>` / `<RangeSelector>` / `<MetricCard>` extraction (`MetricCard` lives privately inside `DashboardOverview.tsx:54-87`).
2. **Custom HTML date inputs**, no calendar component (`DashboardOverview.tsx:92-118` uses raw `<Input type=date>`); no shadcn `<DateRangePicker>`/popover/select.
3. **Chart duplication** — every `*Chart.tsx` re-imports recharts primitives, re-passes `bandwidthShort`/`bandwidthLong`/`dateRange`; no annotations layer (no markers for medication starts, anomalies, training peaks despite `interventions` API existing); `yDomain` hardcoded as strings; `SleepChart.tsx` is 333 LoC of bespoke Recharts config.
4. **No mobile breakpoints** in `DashboardOverview.tsx` (zero `sm:`/`md:` modifiers found in mode-selector/range row); no skeleton-driven loading per chart (page-level `LoadingState` only).

**Non-obvious surprise**: zero `TODO`/`FIXME`/`XXX`/`HACK` comments anywhere in `src/`. Eight Sleep is already wired into `MultiProviderLineChart` (`eightSleepLabel`, `eightSleepValue`) but **no UI surfaces an Eight-Sleep-only view** — capability is built but unused. Also: `BIOMARKER_PRESETS` in `HealthLogPage.tsx:47-`(ApoB, Lp(a), hsCRP, etc.) shows the longevity panel is data-ready but has no chart visualization at all.

**Theoretical enhancements that DON'T fit**:

- Swapping to **visx** — would require rewriting 1 778 LoC of Recharts; team has invested in shared `MultiProviderLineChart`/`TrendLines`/`chart-config`. Recharts is fine for ≤10 k points (we have ≤2 yr daily ≈ 730 rows).
- **Tremor** — built on Recharts but conflicts with the existing Tailwind 4 + custom shadcn primitives; would duplicate `Card`/`Button`.
- **Client-side z-score recomputation** — already centralized server-side; pulling it forward breaks the documented Data-Fusion-Quality contract in CLAUDE.md (mode-window 84/252/730 d).
- **Plotly / heavy WebGL libs** — overkill for ≤730 daily points and would blow PWA bundle budget.

**Sources**:

- [Recharts vs Chart.js big data — Oreate AI](https://www.oreateai.com/blog/recharts-vs-chartjs-navigating-the-performance-maze-for-big-data-visualizations/cf527fb7ad5dcb1d746994de18bdea30)
- [Recharts vs Nivo vs visx 2026 — PkgPulse](https://www.pkgpulse.com/blog/recharts-vs-chartjs-vs-nivo-vs-visx-react-charting-2026)
- [Tremor on shadcn — All Shadcn](https://allshadcn.com/components/tremor/)

## Round 1 — Data Layer & Interactivity

**Audit of current stack** (`frontend/package.json`): TanStack Query v5.90, Zustand 5, react-router 7, Recharts 3 (NOT Plotly — correct the brief), vite-plugin-pwa already present, React 19. So choices below skip what's installed.

### 1. Client cache/state

TanStack Query v5 already in. Don't add SWR/Apollo — Apollo is overkill (no GraphQL), SWR overlaps. Action: adopt `useSuspenseQuery` + React 19 `startTransition` so mode toggles (Short/Mid/Long) don't flash skeletons — TanStack docs explicitly recommend wrapping queryKey changes in `startTransition` to suppress the Suspense fallback ([TanStack v5 Suspense](https://tanstack.com/query/latest/docs/framework/react/guides/suspense)). Keep Zustand only for ephemeral UI state (selected metric, modal open); derived analytics belong in `select:` of useQuery, not Zustand.

### 2. Client-side analytics with DuckDB-WASM

**Highest-leverage upgrade.** Ship daily snapshot as Parquet (~100KB/year of HRV+sleep) to the browser; run mode-aware z-scores in-process. DuckDB-Wasm beats Arquero/SQLite-WASM by 10–100× on TPC-H ([VLDB paper, Kohn 2022](https://www.vldb.org/pvldb/vol15/p3574-kohn.pdf)); reasonable perf reported on 4.4M rows / 30 cols ([Sparkgeo](https://sparkgeo.com/blog/a-duckdb-wasm-web-mapping-experiment-with-parquet/)). Mode switch (84d→252d→730d window) becomes a SQL `WHERE` on the same in-memory Arrow table — no Flask round-trip. WASM bundle ~5MB; load lazily after first paint via dynamic `import('@duckdb/duckdb-wasm')`.

### 3. Real-time

SSE only for sync-progress toasts. Polling-on-focus (`refetchOnWindowFocus`, default in TQ) is sufficient for daily-check-in. WebSocket = wasted complexity.

### 4. URL-as-state

Add **nuqs** — type-safe `useQueryState` with React Router adapter, used by Sentry/Supabase/Vercel ([nuqs.dev](https://nuqs.dev/)). Encode `?mode=long&metric=hrv&from=...` so deep links survive refresh and are shareable.

### 5. Drill-down

Recharts `<Brush>` for zoom; click-day → modal route (`/day/:date`); week-hover small-multiple via `ReferenceArea`.

### 6. Perf

`React.lazy` per page (already supported by Vite), `react-window` only if WorkoutSet history > 500 rows. `useDeferredValue` on mode toggle.

### 7. PWA

vite-plugin-pwa installed — wire `workbox` cache-first for `/api/health/*`, enable Web Push for HRV anomalies (server emits via existing bot pipeline).

### 8. Testing

Playwright for mode-switch flow only. Skip Storybook/Chromatic — single-user product, no design-system payoff.

### 9. Type-safe API

Skip tRPC (Flask backend). Generate types from Flask via **openapi-typescript** + **zod** runtime validation at the fetch boundary — guards against schema drift in `data_sync` writes.

## Round 1 — Longevity Domain UX

**Reference patterns (verified Apr 2026):**

- **Whoop 5.0 (May 2025)**: three circular dials (Recovery / Strain / Sleep) on home, plus a new **Health tab** unifying cardiovascular fitness with long-term **Healthspan** metrics, lock-screen widgets ([Whoop 2025 launches](https://www.whoop.com/us/en/thelocker/everything-whoop-launched-in-2025/)).
- **Bryan Johnson Blueprint**: a single **Speed of Aging / DunedinPACE** number (his = 0.48, "world's slowest"), 100+ biomarkers tested 2x/yr, multi-month rolling averages, AI companion ([Speed of Aging](https://blueprint.bryanjohnson.com/products/speed-of-aging), [Biomarkers](https://blueprint.bryanjohnson.com/pages/biomarkers)).
- **Function Health**: per-biomarker **"in-range / out-of-range / optimal"** bands with a biological-age summary ([Function biological age](https://www.functionhealth.com/biomarker-categories/biological-age)).
- **Garmin / Cooper Institute**: VO2max → **Fitness Age** capped at -20y, with age×sex percentile bands ([Garmin VO2max ratings](https://www8.garmin.com/manuals/webhelp/GUID-C001C335-A8EC-4A41-AB0E-BAC434259F92/EN-US/GUID-1FBCCD9E-19E1-4E4C-BD60-1793B5B97EB3.html), [VO2max percentiles](https://www.shoulditrain.com/blog/garmin-vo2-max-by-age)).
- **Apple/Whoop/Levels** all share: ring/dial primary metric, then sparkline secondary, then annotation timeline (food, workouts, alcohol).

**Concrete missing widgets for life-as-code:**

1. **Pace-of-Aging hero card** — single DunedinPACE-style number from VO2max + HRV + RHR + RR + body comp (Levine PhenoAge surrogate); the *one* thing a longevity user wants to see first.
2. **Fitness-Age vs Chronological-Age delta** — "you train like a 34-year-old" with age-band peer percentile bar (the strongest survival signal Attia cites).
3. **Adherence calendar heatmap** — sleep ≥7h, zone-2 ≥150min/wk, protein ≥1.6g/kg, steps ≥8k — green/amber/red cells, weekly streak count.
4. **Lifestyle event timeline** — illness / travel / alcohol / fasting / sauna markers overlaid on HRV+RHR+sleep so causality is visible.
5. **"What's broken today" anomaly feed** — z<-2 metrics surfaced top, ranked by longevity-impact weight (HRV>sleep>RHR>steps).
6. **Percentile-band overlay** on every trend chart — your value vs published age×sex bands (Garmin/Cooper VO2max, Elite-HRV).
7. **Doctor-share single-page PDF** — labs + 90d trends + meds, one URL, signed.
8. **Weekly recap** — auto-rendered screenshot/email Sunday night, the Whoop "Monthly Performance Assessment" pattern.

**What life-as-code currently lacks vs the field**: trend lines + stat cards exist, but there is no *single longevity verdict number*, no peer comparison, no adherence accountability surface, no event-annotated causal view, and no anomaly feed — exactly what differentiates Whoop/Blueprint/Function from "yet another quantified-self chart wall."

**3-line summary:**

1. Most impactful: **Pace-of-Aging hero card** (VO2max + HRV + RHR composite, Fitness-Age delta + DunedinPACE-style number) — the single longevity verdict every user opens the app to see.
2. Overrated/wrong-fit: **three-ring "Move/Exercise/Stand"** Apple-style dials — designed for sedentary nudging, not longevity; an HRV/VO2max user already exceeds them daily and they convey no biological-age signal.
3. Non-obvious differentiation: **lifestyle-event annotated timeline + multi-source data-quality badges** — because life-as-code fuses Garmin+Whoop+Eight Sleep+Hevy, it can show "alcohol Tue → HRV -18% Wed, confirmed by 2 sources" — causal storytelling no single-vendor app can produce.

## Round 2 — Defender of Refactor-First Plan

**Thesis:** Refactor → Longevity widgets → Mobile polish. Ship value on top of the existing 1 778 LoC Recharts investment; do not migrate libraries.

**1. Refactor beats library swap.** The Auditor verified Recharts 3.6 is the *sole* charting lib, Tailwind 4 + custom shadcn-style primitives are hand-rolled, and zero `TODO`/`FIXME` exist. This is healthy code, just bloated (466–741 LoC pages). Tremor would duplicate `Card`/`Button` and fight Tailwind 4. The cheapest win is extracting `<DashboardShell>`/`<RangeSelector>`/`<MetricCard>`/`<DateRangePicker>`, cutting pages ~40 % and unblocking every later widget. Mobile breakpoints (`sm:`/`md:`) and a calendar-popover date picker land in the same sprint.

**2. Annotations layer is the highest-leverage Phase 2 item.** Recharts ships `<ReferenceArea>` (rectangular highlight via `x1/x2/y1/y2`), `<ReferenceDot>` (point marker), and `<ReferenceLine>` natively — all consume Label context and require no library swap ([Recharts ReferenceArea](https://recharts.github.io/en-US/api/ReferenceArea/), [ReferenceDot](https://recharts.github.io/en-US/api/ReferenceDot/)). The `interventions` API already exists; wiring it into one shared `<AnnotatedChart>` wrapper unlocks the Longevity agent's "alcohol Tue → HRV −18 % Wed, confirmed by 2 sources" causal moat — the single feature no single-vendor app (Whoop/Oura/Eight) can produce. Z-score bands `<ReferenceArea y1={-1} y2={1}>` come free in the same component.

**3. Pace-of-Aging hero card > ring-of-rings.** DunedinPACE is the validated "speedometer of aging" (years biological per calendar year; responds to interventions in 4–8 weeks; stronger cognitive-decline signal than Horvath/GrimAge ([Moffitt & Caspi, Duke](https://moffittcaspi.trinity.duke.edu/dunedinpace), [eLife 2022](https://elifesciences.org/articles/73420))). A surrogate from VO2max+HRV+RHR+RR+body-comp delivers the *one verdict number* a longevity user opens the app for. Apple-style rings encode adherence, not biology — keep them, but secondary on mobile.

**4. Sequencing rationale.** Refactor first because every Phase 2 widget renders inside the new shell. Annotations before hero card because the hero card *embeds* the annotations layer for the underlying biomarkers. Mobile last because bottom-nav + swipe ride on the already-extracted shell — building them first means redoing them.

**5. What this does NOT solve (acceptable):** no DuckDB-WASM client analytics (violates server-side z-score contract, bundle cost +5 MB); no Tremor migration (rebuild tax); no per-biomarker Function-Health "optimal band" UI (lands inside biomarker chart in Phase 2). Doctor-share PDF and weekly recap deferred — backend work, not dashboard.

**6. Counter-arguments.** *Visual ("Tremor!"):* conflicts with Tailwind 4 + custom primitives — Auditor verified. *Data ("DuckDB-WASM!"):* breaks Data-Fusion contract. *Longevity ("rings wrong-fit"):* agreed — verdict number primary, rings secondary on Today only. Mode-toggle crossfade uses Framer Motion `<AnimatePresence mode="wait">` with complementary `easeIn`/`easeOut` for the premium feel ([Motion docs](https://motion.dev/tutorials/react-animate-presence-modes)).

## Round 2 — Attacker of Refactor-First Plan

**Thesis:** The 3-phase plan is engineering-brain procrastination wearing longevity cosplay. Cut to ONE change: mobile breakpoints + bottom nav, shipped in 2 days.

**1. Refactor-first delays user value 1–2 weeks for zero user-visible delta.** Extracting `<MetricCard>`/`<RangeSelector>` is hygiene, not enhancement. Pages at 466–741 LoC are *fine* on a solo project with zero `TODO`s. Drop widgets directly into existing pages; refactor opportunistically when the third paste hurts. The Defender's "every Phase 2 widget renders inside the new shell" is circular — widgets render fine inside the *current* shell.

**2. Pace-of-Aging hero card is statistically dishonest.** DunedinPACE, PhenoAge and GrimAge **disagree on the same person**: DunedinPACE↔Horvath r=0.13, ↔PhenoAge r=0.36, ↔GrimAge r=0.58 ([npj Aging 2025 "Do we actually need aging clocks?"](https://www.nature.com/articles/s41514-025-00312-2)). CALERIE caloric-restriction trial moved DunedinPACE+PhenoAge but **not** GrimAge/Horvath/Hannum, and biological-vs-technical-replicate inconsistency is even stronger in 2025 pre-prints ([Frontiers in Aging 2024 critical review](https://public-pages-files-2025.frontiersin.org/journals/aging/articles/10.3389/fragi.2024.1487260/pdf)). A *surrogate* from VO2max+HRV+RHR+body-comp is not a clock — it's a vibes composite. Surfacing it as the headline number betrays "live to 150" with theater. Reject.

**3. Annotations layer is half-built theater.** Verified: `interventions` CRUD exists in `HealthLogPage.tsx:291` and `api.ts:224-259`, so data flow is real — but the layer's value is causal storytelling, which requires *dense* user input the Defender never plans for (no quick-add UI, no auto-import from calendar/Hevy). Without bulk-entry, the chart overlay is empty for months.

**4. Tremor dismissal is overstated.** Tremor ships native Tailwind v4 + React 19 support and uses copy-paste like shadcn ([allshadcn.com/components/tremor](https://allshadcn.com/components/tremor/), [shadcn/ui Tailwind v4 changelog Feb 2025](https://ui.shadcn.com/docs/changelog/2025-02-tailwind-v4)). "Conflicts with custom primitives" is solvable by replacing primitives incrementally — not a blocker.

**5. Ring-of-rings: drop entirely.** Longevity agent already showed Move/Exercise/Stand encodes nudging, not biology. Replace with Whoop-style Recovery+Strain dial (two values) and stop.

**6. Eight Sleep view + biomarker charts are missing-feature work, not enhancement.** Don't mix.

**Better plan:** (a) mobile breakpoints + bottom nav (2 days; thumb-zone wins retention — [AppMySite 2025](https://blog.appmysite.com/bottom-navigation-bar-in-mobile-apps-heres-all-you-need-to-know/)); (b) one differentiating widget: causal-overlay tooltip from multi-source fusion, the actual moat (1 week); (c) iterate from real use. Reject phases.

## Final Synthesis

### TL;DR

The Attacker is right on three big things, the Defender on one. **Drop the Pace-of-Aging hero card. Drop the Tremor migration. Drop the formal Phase-1 refactor sprint.** Keep Recharts. Ship enhancement *as features*, refactor *as second-use earns it*. Three concrete bets, in order: **mobile breakpoints + bottom nav** → **annotations layer + intervention quick-add** → **fill latent capabilities (Eight Sleep + biomarker charts)**.

### Recommendation (concrete, sequenced)

**Bet 1 — Mobile-first daily check-in (week 1).**

- Add `sm:`/`md:` breakpoints to `DashboardOverview`, `SleepOverviewPage`, `TrainingsPage`, `HealthLogPage`, `DataStatusPage`.
- Bottom nav (Today/Sleep/Train/Stats/Settings) on mobile via existing PWA shell.
- Replace raw `<input type=date>` (`DashboardOverview.tsx:92-118`) with one shadcn-style `<DateRangePicker>` calendar popover. This is the only Phase-1 component extraction that earns its keep up front because it's used everywhere.
- Defer all other shared-component extraction. When `<MetricCard>` lands in a third page, *then* extract.

**Bet 2 — Annotations + intervention quick-add (week 2-3).**

- Build `<AnnotatedChart>` wrapper using Recharts' native `<ReferenceArea>` / `<ReferenceDot>` / `<ReferenceLine>` over the existing `interventions` API.
- BUT — Attacker is right that without dense data the overlay is empty theater. So ship a **quick-add** intervention UI: a one-tap "tag today" button (alcohol / illness / travel / fasting / sauna / medication change) on the home page. Data first, layer second.
- Inline z-score reference bands `<ReferenceArea y1={-1} y2={1}>` on every metric trend (free with Recharts, no new lib).
- Causal-overlay tooltip ("alcohol Tue → HRV −18% Wed, confirmed by 2 sources") — the actual multi-source moat the Longevity agent named. This is the differentiation unmatched by Whoop/Oura/Eight alone.

**Bet 3 — Surface latent capabilities (week 4+).**

- Eight Sleep dedicated view (already plumbed in `MultiProviderLineChart`).
- Biomarker charts for `BIOMARKER_PRESETS` (ApoB, Lp(a), hsCRP) — show component values vs published reference bands. **Do NOT compose them into a single Pace-of-Aging score.** Show the truth (each marker, each trend, each band); let the user think.

**Polish along the way (no dedicated phase):** Framer Motion `<AnimatePresence mode="wait">` 200ms crossfade on Short/Mid/Long toggle; shadcn `Skeleton` for per-chart loading; longevity-specific palette (deep teal recovery / amber strain / oxblood alert) in CSS vars.

### Key Tradeoffs

- **Refactor opportunistically, not upfront.** Defender's clean-shell argument is real but premature on a solo project with zero `TODO`s. Pages of 600+ LoC are tolerable for now; the cost of a wrong shell is higher than the cost of a long page.
- **Truthful component metrics > a synthetic "biological age" number.** The user's audience is a longevity researcher (per memory: senior engineer, longevity research, plans RTX 3090). A vibes composite betrays that audience. The peer-reviewed literature (npj Aging 2025, Frontiers in Aging 2024) shows aging clocks disagree with each other — surfacing one as a verdict is a category error.
- **Multi-source causal overlay is the moat.** No single-vendor app can render "alcohol Tue → HRV −18% Wed across Garmin and Eight Sleep." This is the only widget that justifies "live to 150" framing.

### Strongest Counter-Argument (Defender, R2)

"Refactor first or every later widget gets cluttered." **Why I don't fully buy it:** the Auditor verified the codebase has zero TODOs, sole charting lib (Recharts), and consistent patterns. The same components getting redefined in 3-4 places is a real cost, but extracting them in advance commits to abstractions that may not fit the next widget. Defer until a third use shows the seams. The DateRangePicker is the single exception because it's needed in every page Bet 1 touches.

### Honest Gaps in This Analysis

- No agent measured actual mobile usability (no Lighthouse audit on a real phone). Bet 1 might surface bigger issues than just breakpoints.
- The `interventions` API was verified to exist as CRUD but no agent looked at *what schemas/categories it supports* — the quick-add UI design depends on this.
- No agent prototyped the causal-overlay tooltip — the multi-source-fusion data path that produces "alcohol Tue → HRV −18% Wed" is non-trivial and might require backend analytics work the Defender's plan didn't budget.
- Bryan Johnson Blueprint, Function Health, Levels — referenced but not deeply studied. A direct-comparison product audit might surface widgets none of the agents named.

### Sources (consolidated)

- Round 1 Auditor: codebase facts (Recharts 3.6, Tailwind 4, TanStack Query, Zustand, no Plotly).
- Round 1 Visual: Vercel-Tremor MIT, Recharts 1.8M weekly downloads, ECharts 100k point ceilings.
- Round 1 Longevity: Blueprint dashboard, Whoop 5.0, Function Health 2025, Garmin VO2max bands, DunedinPACE.
- Round 1 Data: DuckDB-WASM benchmarks, TanStack Query v5, nuqs URL-state.
- Round 2 Defender: Recharts ReferenceArea/Dot API, Moffitt/Caspi DunedinPACE, Motion AnimatePresence.
- Round 2 Attacker: npj Aging 2025 ("Do we actually need aging clocks?" — clocks disagree on same person), Frontiers in Aging 2024 critical review of biological-age clocks, shadcn/ui Tailwind v4 changelog Feb 2025, AppMySite bottom-nav 2025.

## Round 1 — Diagnostic Investigator

Goal: identify the code path holding the leaked advisory lock when the holder's `state=idle` and last query is `ROLLBACK`/`COMMIT`.

### 1. Map leaked-lock pid → application/client (pg_locks ⨝ pg_stat_activity)

```bash
kubectl exec -n shared-database shared-postgres-2 -- psql -U postgres -d lifeascode_production -c "
SELECT l.pid, l.classid, l.objid, l.granted, a.application_name, a.client_addr, a.client_port,
       a.usename, a.state, a.backend_start, a.xact_start, a.query_start,
       now()-a.state_change AS idle_for, a.query
FROM pg_locks l JOIN pg_stat_activity a USING(pid)
WHERE l.locktype='advisory' ORDER BY a.backend_start;"
```

`application_name` is the SQLAlchemy connect-arg; `client_addr`+`client_port` is the **pgbouncer-side** socket ([PG wiki Lock_Monitoring](https://wiki.postgresql.org/wiki/Lock_Monitoring), [pg_locks docs](https://www.postgresql.org/docs/current/view-pg-locks.html)).

### 2. pg_stat_statements — find the acquiring SQL

```bash
kubectl exec -n shared-database shared-postgres-2 -- psql -U postgres -d lifeascode_production -c "
SELECT queryid, calls, query FROM pg_stat_statements
WHERE query ILIKE '%pg_advisory_lock%' OR query ILIKE '%pg_try_advisory_lock%'
ORDER BY calls DESC LIMIT 20;"
```

Utility calls are normalized into one entry per shape ([pg_stat_statements docs](https://www.postgresql.org/docs/current/pgstatstatements.html)). If extension absent: `CREATE EXTENSION pg_stat_statements;` + restart.

### 3. Real-time capture (one sync window)

```bash
kubectl exec -n shared-database shared-postgres-2 -- psql -U postgres -c \
  "ALTER SYSTEM SET log_statement='all'; SELECT pg_reload_conf();"
kubectl rollout restart deploy/life-as-code-production-scheduler -n life-as-code-production
# wait one sync, then:
kubectl exec -n shared-database shared-postgres-2 -- psql -U postgres -c \
  "ALTER SYSTEM RESET log_statement; SELECT pg_reload_conf();"
kubectl logs -n shared-database shared-postgres-2 --since=15m | grep -iE 'advisory_lock|advisory_unlock'
```

Risk: log volume 50–200×, disk pressure on shared cluster — bound to a single sync, alert on PVC usage.

### 4. pgbouncer pid mapping

```bash
kubectl exec -n life-as-code-production deploy/.../pgbouncer -- psql -h 127.0.0.1 -p 6432 pgbouncer -c "SHOW SERVERS;"
kubectl exec -n life-as-code-production deploy/.../pgbouncer -- psql -h 127.0.0.1 -p 6432 pgbouncer -c "SHOW CLIENTS;"
```

Join `SHOW SERVERS.remote_pid` (= PG backend pid) with `SHOW SERVERS.link` ↔ `SHOW CLIENTS.ptr` to get original client `addr:port` ([pgbouncer usage](https://www.pgbouncer.org/usage.html)).

### 5. Instrument `src/sync_manager.py`

Wrap each sync with `connection.info['sync_id']=uuid4()`; set `SET application_name='sync:<provider>:<user>:<sync_id>'` per checkout; log `pid = conn.execute("SELECT pg_backend_pid()").scalar()` before lock + after release; emit on SQLAlchemy `engine.events` `checkout`/`checkin`/`reset` so leaked sessions surface in pod logs with the originating sync_id.

## Round 1 — PgBouncer Expert

**Verdict on the user's diagnosis: largely correct in shape, wrong on one detail.** A session-level `pg_advisory_lock` *can* persist on a backend in `state='idle'` after commit 2f8eff8. But the carrier is **SQLAlchemy's pool**, not pgbouncer — and the diff confirms it.

**Mechanism (concrete, line by line on the deleted code):**

1. Old `extract_and_parse` opened `lock_db = get_db_session_context()`, ran `pg_try_advisory_lock(:id)` (session-scope, NOT `_xact`), then `lock_db.commit()`. SQLAlchemy's `Session.commit()` issues SQL `COMMIT` on the underlying DBAPI connection but **does NOT return that connection to the pool** — the connection stays checked out for the lifetime of the `Session`/context ([SQLAlchemy 2.0 pooling docs](https://docs.sqlalchemy.org/en/20/core/pooling.html)). Backend goes `idle` (no open xact) but the **session-scoped advisory lock survives `COMMIT`** — only the holding *session* (PG backend) can release it ([Practical Advisory Locks — Medium](https://medium.com/inspiredbrilliance/a-practical-guide-to-using-advisory-locks-in-your-application-7f0e7908d7e9)).

2. If `api_call_func(...)` raised before `finally`, OR if the worker process was killed between `commit()` and the `finally pg_advisory_unlock`, the `with get_db_session_context()` block's `__exit__` runs `pool_reset_on_return="rollback"` (`src/database.py:24`) — which in stock SQLAlchemy is **just `ROLLBACK`, NOT `DISCARD ALL`**. ROLLBACK does not release session-level advisory locks. The connection returns to SQLAlchemy's pool with the lock still held, in `idle` state. Next checkout reuses it; `pg_try_advisory_lock` for the same key from the same backend re-acquires (locks are reentrant per session) — but a *different* worker process gets a fresh backend and is blocked forever on the per-pool lookup of the IN_PROGRESS row.

3. **pgbouncer is a red herring here unless transaction-pooling is actually configured.** In transaction mode, pgbouncer hands a different server to each xact — so `pg_advisory_lock` in xact A would be released by `server_reset_query` (default `DISCARD ALL` in PG ≥8.3.6 releases advisory locks — [pgBouncer & server_reset_query](https://jakub.fedyczak.net/post/pgbouncer-and-server-reset-query/)) **only if** `server_reset_query_always=1` (off by default — reset only runs in session pooling mode per [pgbouncer config](https://www.pgbouncer.org/config.html)). In transaction pooling with default settings, the lock would simply be unreachable from any later xact (orphaned on a server still pinned… until pgbouncer reaped it). [pgbouncer issue #102](https://github.com/pgbouncer/pgbouncer/issues/102) documents this exact gap.

4. **Pool pinning:** pgbouncer pins a server to a client only on PREPARE without protocol-level prepared statements, LISTEN, WITH HOLD cursors, or unfinished xact — **not** on `pg_advisory_lock`. So pgbouncer will happily release the server back to the pool with the lock still held. There is no per-client affinity to "the holder" — any later client can land on that server and observe (or fail to acquire) the lock. ([PgBouncer features](https://www.pgbouncer.org/features.html), [JP Camara: PgBouncer is fraught](https://jpcamara.com/2023/04/12/pgbouncer-is-useful.html)).

5. `pool_pre_ping=True` runs `SELECT 1` only — does not clear advisory locks. No SQLAlchemy default acquires session-level locks. AUTOCOMMIT on `read_engine` is irrelevant.

**Fix (to evict an already-leaked lock from the live pool):**

```sql
-- run as superuser against each backend in `idle` for this DB:
SELECT pid, pg_advisory_unlock_all() FROM pg_stat_activity
 WHERE datname='lifeascode_production' AND state='idle';
-- nuclear option:
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
 WHERE datname='lifeascode_production' AND state='idle'
   AND pid IN (SELECT pid FROM pg_locks WHERE locktype='advisory');
```

`pg_advisory_unlock_all()` only releases locks held by *the calling session* — you must execute it inside each leaking backend, or terminate them. `DISCARD ALL` from a privileged session won't help; it also acts only on the current session.

**Permanent hardening (independent of 2f8eff8):**

- Set `pool_reset_on_return=lambda dbapi, rec: dbapi.cursor().execute("DISCARD ALL")` (or use `events.PoolEvents.reset`) so future leaks self-heal on checkout. [SQLAlchemy pool reset](https://docs.sqlalchemy.org/en/20/core/pooling.html).
- If pgbouncer is in the path: `server_reset_query = DISCARD ALL` + `server_reset_query_always = 1` (only safe in session pooling mode — in transaction mode, prefer `pg_advisory_xact_lock` which auto-releases on COMMIT/ROLLBACK).
- Restart the backend pod once: kills SQLAlchemy's pool, drops every leaked backend connection, lock disappears. Cheapest immediate cure.

**Sources:**

- [pgbouncer issue #102 — reset_query needed for pg_advisory_lock](https://github.com/pgbouncer/pgbouncer/issues/102)
- [SQLAlchemy 2.0 Connection Pooling docs](https://docs.sqlalchemy.org/en/20/core/pooling.html)
- [pgbouncer config — server_reset_query / _always](https://www.pgbouncer.org/config.html)
- [pgBouncer & server_reset_query — Fedyczak](https://jakub.fedyczak.net/post/pgbouncer-and-server-reset-query/)
- [Advisory locks in practice — Medium](https://medium.com/inspiredbrilliance/a-practical-guide-to-using-advisory-locks-in-your-application-7f0e7908d7e9)
- [JP Camara: PgBouncer is useful, important, and fraught with peril](https://jpcamara.com/2023/04/12/pgbouncer-is-useful.html)

## Round 1 — Locking Strategist

Why current row-UPSERT (commit 2f8eff8) leaks: the row IS the lock. Any crash/OOMKill/SIGKILL during scheduler rollout leaves `status=in_progress`; only the staleness TTL releases it. Too long → blocks retries; too short → double-runs. No liveness heartbeat (pgbouncer pool isn't sticky), no fencing token (zombie can overwrite fresh sync).

**Candidates:**

1. **Current row-UPSERT** — Orphan `in_progress` after crash; clock-skew on stale check; no fencing. Blast: silent stale data. Low complexity; **already broken**.

2. **`SELECT FOR UPDATE NOWAIT` on sentinel row** — Row lock is *transaction-scoped*, released when pgbouncer returns conn ([PgBouncer features](https://www.pgbouncer.org/features.html)). Holding across a 5-min Garmin sync requires wrapping the entire sync in one transaction → kills pooling, pins backend, breaks on sub-commits. Reject.

3. **Redis/Valkey `SET NX PX` + unique token + Lua release** — Canonical ([Redis docs](https://redis.io/docs/latest/develop/clients/patterns/distributed-locks/)). TTL + heartbeat-extend solves leak; token prevents wrong-owner release. Single Valkey is "good enough" — skip Redlock ([Leapcell](https://leapcell.io/blog/implementing-distributed-locks-with-redis-delving-into-setnx-redlock-and-their-controversies)). **2-3 hrs** via `redis-py` `Lock`. Good if Valkey deployed; else +1 dep.

4. **Filesystem `flock` on PVC** — `life-as-code-production-garminconnect` is RWO single-mount. Crash-safe (kernel releases on PID death). **1 hr**. Couples to pod identity; scheduler scale >1 needs RWX. Fragile to remount races.

5. **Direct pg bypass pgbouncer + session `pg_advisory_lock`** — Connect to `shared-postgres-rw.shared-database.svc:5432` directly from sync subsystem only. Crash → backend dies → Postgres releases lock ([Heroku](https://help.heroku.com/UYH8N2WW/why-do-i-receive-activerecord-concurrentmigrationerror-when-running-rails-migrations-using-pgbouncer), [GoodJob #52](https://github.com/bensheldon/good_job/issues/52), [IBM #4051](https://github.com/IBM/mcp-context-forge/issues/4051)). Cost: +1 long-lived backend per pod. **1 hr**, zero deps. **Strongest fit.**

6. **K8s `coordination.k8s.io/Lease`** — Native, kubelet-aware. Python client lacks first-class Lease election ([k8s-client-python #1877](https://github.com/kubernetes-client/python/issues/1877)) — hand-roll via raw API. TTL+heartbeat survives crashes. Overkill if single-replica.

**Recommendation:** Option 5 (smallest blast radius, kernel-guaranteed release). Option 3 if Valkey already in cluster.

## Round 1 — Code Archaeologist

**Scope:** every code path that may issue `pg_advisory_lock`, `pg_try_advisory_lock`, `SELECT FOR UPDATE`, or other session-state-mutating SQL.

**1. Commit `2f8eff8` (May 1 2026, "Replace pg_advisory_lock with atomic UPSERT claim").** Diff touches `src/sync_manager.py` only. Removes the `with get_db_session_context() as lock_db: pg_try_advisory_lock(:id) … finally pg_advisory_unlock(:id)` block (~50 LoC) and replaces with `_try_claim_sync_slot()` (lines ~462-507): single `INSERT … ON CONFLICT DO UPDATE WHERE status!='in_progress' OR last_sync_timestamp<now()-30min`. One short tx, no session state, pgbouncer-safe.

**2. Residual references in app code.** `git grep -n "advisory|pg_advisory|pg_try|FOR UPDATE|with_for_update"` over `src/`, `migrations/`: **zero hits in `src/scheduler.py`, `src/database.py`, `src/api.py`, `src/pull_garmin_data.py`, `src/pull_hevy_data.py`, `src/pull_whoop_data.py`, `src/pull_eight_sleep_data.py`, all alembic migrations.** Sole orphan: `src/sync_manager.py:259` `_sync_lock_id()` (sha256→int63 helper) is dead code — defined, no caller. Should be deleted.

**3. Pod versions.** All 5 deployments (`backend`, `bot`, `frontend`, `ml`, `scheduler`) run `ghcr.io/nikolay-e/life-as-code/*:main-2f8eff8`, age ~7 min, RESTARTS=0. Migration job `life-as-code-production-migration-1-gc64v` completed on the new image. **No pre-fix replica is alive** — but pgbouncer in `shared-database` namespace outlives backend rollouts (per QA.md:303-309), so any locks leaked by a pre-`2f8eff8` backend connection still sit on idle pgbouncer-held physical connections.

**4. Library scan.** `grep -rn advisory` across `.venv/lib/python3.13/site-packages/{sqlalchemy,alembic,garminconnect}/`: **zero matches in all three.** SQLAlchemy core never issues advisory locks. **Alembic 1.x does NOT use advisory locks** for migrations (unlike Rails ActiveRecord and Django, which do — see [IBM mcp-context-forge #4051](https://github.com/IBM/mcp-context-forge/issues/4051), [Heroku Help — Rails+PgBouncer ConcurrentMigrationError](https://help.heroku.com/UYH8N2WW/why-do-i-receive-activerecord-concurrentmigrationerror-when-running-rails-migrations-using-pgbouncer)). `garminconnect` 0.3.2 is a pure HTTP wrapper — no DB code.

**5. Pgbouncer leak mechanics confirmed by independent sources.** Session-scoped advisory locks survive the `COMMIT`/`ROLLBACK` boundary pgbouncer transaction-mode uses to recycle backends; recommended fix is `server_reset_query` or `NullPool` ([pgbouncer/pgbouncer #102](https://github.com/pgbouncer/pgbouncer/issues/102), [pablomarti.dev SQLAlchemy+PgBouncer](https://pablomarti.dev/sqlalchemy-pgbouncer/)).

**Conclusion:** code is clean post-`2f8eff8`. No remaining call site issues advisory locks or `SELECT FOR UPDATE` anywhere in `src/` or `migrations/`. No third-party dep (sqlalchemy, alembic, garminconnect) does either. Any lingering "Sync already in progress" symptom is (a) leaked locks held by pgbouncer backends from pre-fix sessions — clear via `pg_terminate_backend` on `pg_locks WHERE locktype='advisory'`; or (b) `data_sync` rows left at `status='in_progress'` from before the fix — auto-recovered after the new 30-min stale-cutoff.

## Round 2 — Defender of UPSERT-claim fix

**Verdict: `2f8eff8` is correct and sufficient. The leaked `pg_locks` entries are pre-fix tombstones, not regressions.**

**1. Empirical proof the new claim mechanism works.** The post-`2f8eff8` sync run completed end-to-end: `body_battery_change` populated 86 records, `awake_count` 86, `spo2_avg/min` 34, `respiratory_rate` 233/237. If the UPSERT claim were wedged by stale advisory locks on the same backends, *zero* of these writes would have landed — the claim row would never flip to `in_progress` and the providers would short-circuit. They didn't. The data-plane is unblocked; only the orphaned `pg_locks` rows remain, and those touch *no* code path the new sync executes.

**2. Code is provably advisory-lock-free.** Round 1 Code Archaeologist: zero `pg_advisory_lock`/`pg_try_advisory_lock`/`FOR UPDATE` hits across `src/`, `migrations/`, and the relevant `.venv` deps (sqlalchemy, alembic, garminconnect). All five deployments run `:main-2f8eff8`, RESTARTS=0. There is no live writer of new advisory locks. The claim is a single short transaction with no session state — pgbouncer-safe by construction, exactly the idempotent `IN_PROGRESS/COMPLETED` three-state pattern recommended for DB-backed claim stores ([dzone — phantom-write idempotency](https://dzone.com/articles/phantom-write-idempotency-data-loss), [PG wiki UPSERT](https://wiki.postgresql.org/wiki/UPSERT)).

**3. Leaked locks are self-draining.** `server_idle_timeout` defaults to 3600s and closes idle server connections; `server_lifetime` recycles unused backends ([pgbouncer config](https://www.pgbouncer.org/config.html), [DeepWiki — connection lifecycle](https://deepwiki.com/pgbouncer/pgbouncer/5.2-connection-lifecycle-and-health-checks)). When pgbouncer closes a backend, Postgres releases every session-scoped advisory lock that backend held. No code action required; the tombstones evaporate within one `server_idle_timeout` window. Lower the knob to 300s if impatient — pure ops dial, not a code defect.

**4. Counter to Locking Strategist ("no liveness signal").** The 30-min `last_sync_timestamp < now()-30min` cutoff *is* the liveness signal. A Garmin sync is bounded ~5 min; 30 min gives 6× headroom before any retry can claim. Crash/OOMKill recovery time = 30 min worst case, vs. the *unbounded* leak the old advisory-lock path produced. This is strictly better, not worse.

**5. Counter to PgBouncer Expert (`DISCARD ALL` mandatory).** `DISCARD ALL` only matters if code re-introduces session-state-mutating SQL. The new path issues none — no `LISTEN`, no `SET`, no advisory locks, no temp tables. Hardening pgbouncer for hazards the codebase no longer creates is defensive overkill outside this fix's scope. Worth doing as separate hygiene; not a blocker on `2f8eff8`.

## Round 2 — Attacker of UPSERT-claim fix

**Claim under attack:** `2f8eff8` (UPSERT with 30-min stale cutoff) is sufficient. **It is not.**

**1. Liveness via TTL is unacceptable for a real-time health dashboard.** OOMKill, node eviction, SIGKILL during scheduler rollout, network partition mid-Garmin-call → row stuck `in_progress`. Every subsequent sync attempt for that user is dropped for **up to 30 minutes**. Garmin sleep/HRV is the user's *first* morning view — a 30-min hole during the AM cron window means stale recovery score for the day. TTL-without-heartbeat is the textbook anti-pattern Kleppmann calls out: "algorithms should make no assumptions about timing" ([How to do distributed locking — Kleppmann](https://martin.kleppmann.com/2016/02/08/how-to-do-distributed-locking.html)).

**2. No fencing token → zombie write corruption.** Pod A is paused (GC, kubelet throttle, network blackhole) past 30 min. Pod B's `_try_claim_sync_slot()` succeeds because `last_sync_timestamp<now()-30min`. Pod A's HTTP call to Garmin returns; Pod A then runs `INSERT INTO sleep ON CONFLICT DO UPDATE` for the same dates Pod B is now writing. **No token check** → last writer wins, mixing two sync generations into one user's day. Kleppmann: "The storage server must take an active role in checking tokens and rejecting any writes on which the token has gone backwards" ([Surfing Complexity — Locks, leases, fencing tokens](https://surfingcomplexity.blog/2025/03/03/locks-leases-fencing-tokens-fizzbee/)). The UPSERT path has no token column on `sleep`/`hrv`/`weight` writes.

**3. Pre-fix tombstones never self-heal.** `2f8eff8` did not touch `pool_reset_on_return='rollback'` (`src/database.py:24`) and shared-cluster pgbouncer was not restarted. Any pgbouncer server-side connection that cached a pre-fix backend with a leaked session-scope advisory lock keeps that lock until the *backend pid* dies — pgbouncer reuse keeps it alive across rollouts ([pgbouncer #102](https://github.com/pgbouncer/pgbouncer/issues/102)). New code never calls `pg_advisory_lock`, so the tombstone is invisible to the app but still occupies `pg_locks`.

**4. Race-to-claim:** two pods both see stale row at T+30:00.001, both run UPSERT. ON CONFLICT serializes correctly, but the *loser's* outer caller has already fetched API data — wasted Garmin API quota (rate-limited, account-ban risk).

**5. `is_sync_recently_active` (api.py:814) semantic drift:** that pre-check uses a *different* timestamp predicate than the UPSERT WHERE clause. A 31-min stale row passes the pre-check, the API enqueues, the UPSERT then claims — but the "freshness" the API promised the user is a lie.

**Single highest-priority fix:** Replace TTL-only with **heartbeat lease + monotonic fencing token**. Add `lease_expires_at` (renewed every 30s by sync worker via `UPDATE … RETURNING`) and `claim_generation BIGSERIAL`; every health-data UPSERT carries `WHERE existing_generation IS NULL OR existing_generation <= :token`. Crash → lease lapses in 60s, not 30min. Zombie → its writes get rejected by generation check.

## Final Synthesis — Lock Leak Investigation

**TL;DR:** Commit `2f8eff8` correctly removed all `pg_advisory_lock` calls and replaced them with an atomic UPSERT-based claim against `data_sync`. The fix works empirically — sleep sync completed and populated 86 records (body_battery_change, awake_count) + 34 records (spo2_avg/min) + 233 records (respiratory_rate). The "leaked lock" observed in `pg_locks` after deploy was a **pre-fix tombstone** sitting on a pgbouncer-cached idle backend — it does NOT block the new sync because the new code does not attempt `pg_try_advisory_lock` at all.

**Mechanism of pre-fix leak (settled):** SQLAlchemy `Session.commit()` returns the connection to the pool. `pool_reset_on_return='rollback'` (`src/database.py:24`) issues `ROLLBACK` only, which does NOT release session-scoped advisory locks. PgBouncer in transaction-pooling mode then routes the next transaction to a fresh physical conn that doesn't have the lock — the original lock-holder sits idle in the pool with the lock still attached, until pgbouncer's `server_idle_timeout` (default 3600s) closes it.

**Recommendation — three-tier:**

1. **Immediate (zero work):** the fix already shipped. Wait for old tombstones to drain via pgbouncer `server_idle_timeout` (1 hr). Or actively kill: `kubectl exec ... pg_terminate_backend(pid) FROM pg_locks WHERE locktype='advisory';`
2. **Short-term defensive (30 LOC):** change `pool_reset_on_return` to use `DISCARD ALL` in `src/database.py`. Eliminates the entire class of session-state leaks for any future code that accidentally uses `SET`, `LISTEN`, `PREPARE`, or `pg_advisory_lock`.
3. **Long-term (only if zombie-write becomes a real incident):** Defender's cutoff is 6× sync bound — fine. Attacker's fencing-token concern is theoretical: Garmin sync is per-user single-source, and "clobbering" means overwriting same user's same-day data with same source. No data corruption, just wasted API call.

**Strongest counter-argument (Attacker):** 30-min TTL means a crashed sync blocks all subsequent ones for 30 min — bad UX during morning HRV check. Mitigation: shorten cutoff to 5 min (still 1× the sync bound) and add heartbeat update from the sync worker every 60 s so a healthy long-running sync isn't reaped. ~20 LOC change.

**Sources:**

- pgbouncer #102 (advisory locks survive transaction-mode recycle)
- pablomarti.dev SQLAlchemy+PgBouncer
- Kleppmann distributed-locking essay (fencing tokens)
- Surfing Complexity fencing-token writeup
