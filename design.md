# ARIA — Design System

A terminal-inspired, monospace design language for a personal AI assistant PWA.
Dark zinc surfaces, a single emerald accent, sharp corners, and no decorative
noise. This document describes the system **as implemented** in
`frontend/app/globals.css` and the component layer.

> **Source of truth:** all design tokens live in the `@theme {}` block of
> `frontend/app/globals.css` (Tailwind v4 CSS-first config). There is no
> `tailwind.config.ts` customization. Change a token there and it propagates
> app-wide.

---

## 1. Principles

- **Terminal aesthetic.** Monospace everywhere, prompt-style chat, blinking
  cursor while streaming, `···` for loading. The UI reads like a focused CLI.
- **One accent.** Emerald `#10B981` is the only brand color. It marks the
  recommended action, focus, confirmations, "done", and live/urgent state.
  Everything else is neutral zinc.
- **Sharp by default.** Border-radius caps at `2px`. The only exception is the
  fully-round avatar (`--radius-full`).
- **No decoration.** No gradients, no glows, no shadows-as-decoration, no
  emojis. Hierarchy comes from spacing, weight, and opacity — not ornament.
- **PWA-native.** Safe-area insets, `h-dvh` over `h-screen`, 16px input font on
  mobile to prevent iOS zoom, content that clears the bottom nav and home
  indicator.
- **Framer Motion only.** All motion goes through Framer Motion
  (`AnimatePresence`, `motion.div`). CSS keyframes are reserved for ambient
  primitives (shimmer, cursor blink, loading dots).

---

## 2. Color tokens

### Surfaces (zinc)

| Token | Value | Role |
|-------|-------|------|
| `--color-bg-root` | `#09090b` | App background, chat surface, input field |
| `--color-bg-surface` | `#18181b` | Sidebar, cards, user message blocks |
| `--color-bg-elevated` | `#27272a` | Hover fills, rails, dividers |
| `--color-bg-hover` | `#3f3f46` | Strongest neutral hover |

### Text (zinc)

| Token | Value | Role |
|-------|-------|------|
| `--color-text-primary` | `#f4f4f5` | Body, titles |
| `--color-text-secondary` | `#71717a` | Secondary copy, inactive labels |
| `--color-text-muted` | `#52525b` | Timestamps, counts, hints |

### Accent (emerald — the only brand color)

| Token | Value | Role |
|-------|-------|------|
| `--color-accent` | `#10b981` | Focus, recommended action, confirm, live/urgent |
| `--color-accent-hover` | `#059669` | Accent hover/pressed |
| `--color-accent-muted` | `rgba(16,185,129,0.15)` | Accent tint fills (avatar, selection) |

### Semantic feedback

| Token | Value | Role |
|-------|-------|------|
| `--color-success` | `#22c55e` | Success state |
| `--color-warning` | `#eab308` | Warning state |
| `--color-error` | `#ef4444` | Error / destructive |
| `--color-info` | `#3b82f6` | Informational |

### Status surfaces (banners)

Three muted surface triples — background `0.10` alpha, border `0.22` alpha, and a
light foreground. Used by the `.banner` system; never hardcode the raw Tailwind
palette in components.

| Variant | bg | border | fg |
|---------|----|--------|----|
| warning | `rgba(234,179,8,0.10)` | `rgba(234,179,8,0.22)` | `#fde68a` |
| info | `rgba(59,130,246,0.10)` | `rgba(59,130,246,0.22)` | `#bfdbfe` |
| error | `rgba(239,68,68,0.10)` | `rgba(239,68,68,0.22)` | `#fecaca` |

### Borders

| Token | Value | Role |
|-------|-------|------|
| `--color-border-subtle` | `#27272a` | Default 1px separators (= bg-elevated) |
| `--color-border-strong` | `#3f3f46` | Hover/emphasis borders |

> **Content colors exception.** Event-type badges (`blue/purple/rose-500/15`)
> are contextual *content* colors, not chrome. They are an intentional, narrow
> exception to the token rule and are commented as such in `EventList.tsx`.

---

## 3. Typography

A single monospace stack drives the whole UI — there is no separate sans family.

```css
--font-sans: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
--font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
```

`body` base is `13px`, antialiased, with `overscroll-behavior: none`.

### Scale

| Size | Use |
|------|-----|
| `28px` | Page headings |
| `15px` | Section / panel titles |
| `13px` | Body, message text, primary rows |
| `11px` | Labels, prompt prefix, secondary meta |
| `10px` | Timestamps, smallest meta |

On screens `≤ 640px`, `input/textarea/select` are forced to `16px` to stop iOS
from auto-zooming on focus.

---

## 4. Shape, radius & spacing

- **Radius:** `--radius-sm` … `--radius-2xl` are all `2px`. `--radius-full` is
  `9999px` (avatars only). Sharp corners are a core part of the look.
- **Separators:** 1px lines using `--color-border-subtle`. Never rounded.
- **Bottom nav height** is tokenized: `--bottom-nav-height: 3.5rem`. All
  clearance math derives from it.

---

## 5. Global utilities

Defined in `globals.css`, below the `@theme` block.

| Utility | Purpose |
|---------|---------|
| `.pb-nav` | Bottom padding = nav height + safe-area inset (content clears BottomNav) |
| `.bottom-above-nav` | Anchors floating elements (toasts) above the nav + safe area |
| `.pb-safe` / `.pt-safe` | Safe-area padding when `env()` is supported |
| `.focus-ring` | Single focus treatment: 2px emerald ring (`rgba(16,185,129,0.35)`) on `:focus-visible`, transparent otherwise |
| `.scrollbar-thin` | 4px scrollbar, `#27272a` thumb, transparent track, no radius |
| `.banner` + `.banner-{warning,info,error}` | Token-driven status bars (see §2) |

### Motion primitives (CSS keyframes)

| Class | Animation |
|-------|-----------|
| `.animate-shimmer` | Skeleton shimmer across elevated→hover→elevated |
| `.animate-fade-in-up` | 8px rise + fade, `0.3s ease-out` |
| `.animate-pulse-dot` | Opacity pulse, `2s` |
| `.loading-dots` | Three 4px emerald dots, staggered `dot-fade` (`···` loading state) |
| `.cursor-blink` | Emerald block cursor `█`, `1s step-end` (streaming indicator) |

Everything beyond these primitives is animated with Framer Motion at the
component level.

---

## 6. Components

### Sidebar (`components/sidebar/`)

- **Width:** fixed `220px`, flex column. Desktop only.
- **Section headings:** plain `11px` text labels — no leading icons.
- **Hover:** rows transition `opacity 0.7 → 1` over `100ms` (no background
  swap unless it's a selectable surface).
- **Profile footer:** pinned to the bottom — avatar (email initial on
  `accent-muted`), email (`text-muted`, truncated), and a `Settings` icon.
  Links to `/profile`.
- **ProjectList:** each row is a `w-1.5 h-1.5` color dot + name (`13px`) + task
  count (`11px text-muted`, `tabular-nums`). `+ New` is a minimal text button;
  the create modal uses `2px` radius and `w-9 h-9` color swatches.
- **EventList:** events grouped by day. A 1px vertical rail
  (`--color-bg-elevated`) runs down the left of each group. Times render in
  `accent` when the event is today, `text-muted` otherwise. Clicking a row
  opens a detail/edit/delete sheet (see §7).
- **ReminderList:** due date renders in `accent` when under 24h (urgent),
  `text-muted` otherwise. Edit/delete actions are always visible on mobile,
  hover-revealed on desktop (`opacity-100 md:opacity-0 md:group-hover:opacity-100`).

### Chat (`components/chat/`)

The chat is the heart of the terminal aesthetic.

- **Assistant messages:** no bubble. Plain text on the root background. The
  first message of an assistant turn is prefixed with `ARIA ›`
  (`11px`, `accent`). While the last assistant message is streaming, a blinking
  emerald `█` cursor (`.cursor-blink`) is appended.
- **User messages:** code-block style — `#18181b` background, `2px` left border
  in emerald (`border-left: 2px solid #10b981`), `2px` radius, `12px 16px`
  padding.
- **Loading:** `···` (`.loading-dots`) shows only *before* the first assistant
  token arrives (when the last message is not yet the assistant's). No spinners.
- **Container:** `px-4 py-6 md:px-8`. Empty state copy: "Type a message below to
  begin."
- **Header (`ChatView`):** `11px`. No "Online" dot. Offline state surfaces as
  warning-colored subtitle text; offline/syncing/error use the `.banner` system.
- **Input (`MessageInput`):** `bg-bg-root`, 1px `#27272a` border, **no**
  radius beyond `2px`. Focus toggles the border to emerald `#10b981`
  (via `onFocus`/`onBlur`) — no glow, no ring shadow. Placeholder:
  "Message ARIA...". Send button is the Unicode `↵`, `text-muted` → `accent`
  when the field has content, on an explicit 36px touch target.

### Navigation (`components/navigation/BottomNav.tsx`)

- Prefix-aware active state via `isTabActive(pathname, href)` so
  `/projects/abc/chat` keeps the Projects tab lit.
- Labels at `text-xs`, constant `strokeWidth`, active state communicated by
  color + a top-pinned `h-0.5 w-12` indicator. Mobile only.

### Notifications (`components/notifications/ReminderNotification.tsx`)

- `AnimatePresence` entry/exit (`opacity/y/scale`).
- Positioned with `.bottom-above-nav` on mobile (full-width, clears the nav),
  `md:bottom-4` on desktop. Card border is `--color-border-subtle` — no glow.

---

## 7. Patterns

### Modal / sheet

Used by event detail and the project create flow.

- `AnimatePresence` + backdrop + `motion.div`.
- Mobile: anchored with `.bottom-above-nav`. Desktop: anchored
  (`md:bottom-6 md:right-6 md:w-80`).
- `2px` radius, `--color-border-subtle` border.
- Multi-mode (detail → edit → confirm-delete) handled by local state, not
  separate routes.

### Destructive actions

- Use the error status tokens (`--color-status-error-*`) — never raw
  `red-500`. Sign-out and delete confirmations follow this.

### Focus & touch

- Every interactive element uses `.focus-ring` for keyboard focus.
- Touch targets are explicit (≥ 36px); hover-only affordances always have a
  mobile-visible fallback.

---

## 8. Hard rules (do / don't)

**Do**
- Pull every color from a token in `@theme {}`.
- Keep radius at `2px` (round only avatars).
- Use Framer Motion for component motion.
- Use the `.banner` system for offline/sync/error states.
- Respect safe areas with `.pb-nav` / `.bottom-above-nav`.

**Don't**
- No gradients, glows, or decorative shadows.
- No emojis anywhere in the UI.
- No spinners — use `···` / shimmer.
- No raw Tailwind palette literals for chrome (only the documented event-type
  content exception).
- No `h-screen` for full-height layouts — use `h-dvh`.

---

## 9. Quick reference

```
Background    #09090B   bg-root      app, chat, input
Surface       #18181B   bg-surface   sidebar, cards, user blocks
Border        #27272A   bg-elevated  separators, rails, hover
Hover         #3F3F46   bg-hover
Text primary  #F4F4F5
Text 2nd      #71717A
Text muted    #52525B
Accent        #10B981   emerald      focus, confirm, live, urgent
Accent hover  #059669
Font          ui-monospace stack  (13px body)
Radius        2px max  (full only for avatars)
Sizes         28 / 15 / 13 / 11 / 10 px
```
