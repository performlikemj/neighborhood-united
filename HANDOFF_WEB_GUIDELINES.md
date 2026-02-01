# Web Interface Guidelines - Agent Handoff Document

## Context

This project (`sautai`) is undergoing a frontend accessibility and UX audit against the [Vercel Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines). The full plan lives at:

```
/Users/michaeljones/.claude/plans/harmonic-napping-tide.md
```

The frontend is React 18 + Vite. The main stylesheet is `frontend/src/styles.css` (~13,000 lines). Theming uses CSS variables with `[data-theme="dark"]` selector.

---

## COMPLETED WORK

### WS1A: Semantic Buttons (DONE)
Replaced `<div onClick>` / `<span onClick>` with `<button>` elements:
- `components/MealPlanWeekView.jsx` - Grid cells + accordion slots converted to `<button type="button">` with `aria-label`
- `components/ScaffoldPreview.jsx` - Editable name spans converted to conditional `<button>` rendering
- `components/ScaffoldPreview.css` - Added `.scaffold-item__name--editable` button reset styles
- `components/SousChefWidget.jsx` - Toast div got `role="alert"`, `tabIndex={0}`, `onKeyDown` for Enter key

### WS1B: Semantic Labels (PARTIAL)
- `pages/Login.jsx` - DONE: `<div className="label">` replaced with `<label htmlFor>`, matching `id` on inputs
- `pages/Register.jsx` - DONE: Same treatment
- `pages/Profile.jsx` - **NOT DONE**: ~19 instances of `<div className="label">` remain (lines 314-477)
- `pages/Account.jsx` - **NOT DONE**: ~6 instances of `<div className="label">` remain (lines 140-184)

### WS1C-D: ARIA Attributes (DONE)
- `components/MealPlanWeekView.jsx` - Added `aria-expanded` to accordion header buttons
- `components/ScaffoldPreview.jsx` - Added `aria-expanded` to toggle button

### WS1E-F: Focus Management + Live Regions (DONE)
- `components/ConfirmDialog.jsx` - Added focus management (auto-focus cancel button), Escape key handler, `aria-modal`, `aria-labelledby`
- `components/NavBar.jsx` - Added Escape key handler for account menu + chef picker dropdowns
- `components/SousChefWidget.jsx` - Added `role="alert"` to toast notification

### WS2: Reduced Motion (PARTIAL)
**In `styles.css`:**
- `transition: all` anti-pattern - DONE: All ~35 instances replaced with explicit property lists (e.g., `transition: background 0.2s ease, color 0.2s ease, border-color 0.2s ease`)
- Dark mode `--muted` contrast - DONE: Changed from `#a6b5ab` to `#c0ccc4` (improves ratio from ~3.8:1 to ~5.2:1)
- Existing `prefers-reduced-motion` guards at lines 446 and 1889
- **NOT DONE**: Global `@media (prefers-reduced-motion: reduce)` guard not yet added. Needs to be appended to end of `styles.css`:
  ```css
  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
    }
  }
  ```
- **NOT DONE**: Component inline `<style>` animations in `SousChefWidget.jsx`, `MealPlanWeekView.jsx`, `TodayDashboard.jsx`, `GhostInput.jsx` need reduced-motion guards

### WS3: Hardcoded Colors (PARTIAL)
**Completed in `styles.css`:**
- `.nav-unread-badge` background: `#e53935` -> `var(--danger, #dc2626)` (line ~399)
- `.btn-danger` background: `#d9534f` -> `var(--danger, #dc2626)` (line ~455)
- `.status-text--blue` color: `#4d74ff` -> `var(--info, #1d4ed8)` (line ~484)
- `.icon-btn` width/height: `28px` -> `44px` (line ~745)

**Completed in components:**
- `CartSidebar.jsx` - All `#c0392b` replaced with `var(--danger, #dc2626)`, `#666` with `var(--muted, #666)`
- `Login.jsx` - `#d9534f` replaced with `var(--danger, #d9534f)`
- `Register.jsx` - `#d9534f` replaced with `var(--danger, #d9534f)`

**NOT DONE in `styles.css`:**
| Line | Current Value | Replace With |
|------|--------------|--------------|
| 495 | `.toast` border-left: `#aaa` | `var(--muted, #aaa)` |
| 777 | `.field-hint` color: `#a94442` | `var(--danger, #dc2626)` |
| 1530 | `.metric-change.positive` color: `#168516` | `var(--success, #168516)` |
| 1533 | `.metric-change.negative` color: `#a11919` | `var(--danger, #dc2626)` |
| 2823 | `.chef-availability-badge.available` color: `#047857` | `var(--success, #047857)` |
| 2829 | `.chef-availability-badge.unavailable` color: `#b45309` | `var(--warning, #b45309)` |

**NOT DONE in page components (inline styles):**
| File | Lines | Current | Replace With |
|------|-------|---------|--------------|
| `Account.jsx` | 143, 156, 172 | `borderColor:'#d9534f'` | `borderColor:'var(--danger)'` |
| `Profile.jsx` | 600 | `borderColor:'#f5c6cb'` | `borderColor:'var(--danger-bg)'` |
| `Profile.jsx` | 601 | `color:'#a94442'` | `color:'var(--danger)'` |
| `Home.jsx` | 415 | `color: '#635bff'` | OK to keep (Stripe brand color) or add `--stripe-brand` var |
| `CustomerOrders.jsx` | 598 | `borderColor:'#d9534f'` | `borderColor:'var(--danger)'` |
| `ChefDashboard.jsx` | 2674, 2712 | `color: '#d9534f'` | `color: 'var(--danger)'` |
| `MealPlans.jsx` | 1089, 1108, 1127, 1298, 2204, 2354, 2399, 2523 | `#d9534f` in various styles | `var(--danger)` |

### WS4: Touch Targets (PARTIAL)
**Completed:**
- `.icon-btn`: 28px -> 44px (DONE)

**NOT DONE:**
| Selector | Line | Current | Target |
|----------|------|---------|--------|
| `.file-clear-btn` | 754-755 | 24x24px | 44x44px (or add padding to reach 44px touch area) |
| `.nav-icon-link` | 380-381 | 40x40px | 44x44px |
| `.gallery-modal-close` (`.page-chef-gallery .lightbox .close`) | Check ~line 2320 | 36x36px | 44x44px |
| `.slot-actions .btn` | ~line 723 | 36px height | 44px |

### WS5: Focus Styles (NOT DONE)
Replace `:focus` with `:focus-visible` in `styles.css`. These are the locations:

| Line | Selector | Current |
|------|----------|---------|
| 438 | `.btn:focus` | `:focus` |
| 505 | `.input:focus, .textarea:focus` | `:focus` |
| 529 | `.select.time-select:focus` | `:focus` |
| 544 | `.select:focus` | `:focus` |
| 554 | `.input[type="date"]:focus, .input[type="time"]:focus` | `:focus` |
| 770 | `.file-clear-btn:focus` | `:focus` |
| 819 | `.mode-option:focus` | `:focus` |
| 2190 | `.listbox-field:focus` | `:focus` |
| 2964 | `.chef-gallery-item:focus` | `:focus` |
| 3816 | `.gallery-grid-item:focus` | `:focus` |
| 4336 | `.orders-filter-select:focus` | `:focus` |
| 4722 | `.search-input:focus` | `:focus` |
| 5384 | `.country-select:focus` | `:focus` |
| 7525-26 | `.form-field input:focus, .form-field textarea:focus` | `:focus` |
| 12884 | `.service-areas-search .search-input:focus` | `:focus` |

Good existing example at line ~1546: `.clickable-order-card:focus-visible` - follow this pattern.

### WS6: Form Autocomplete (PARTIAL)
- `Login.jsx` - DONE: `autoComplete="username"`, `autoComplete="current-password"`
- `Register.jsx` - DONE: `autoComplete="username"`, `autoComplete="email"`, `autoComplete="new-password"`
- `Profile.jsx` - **NOT DONE**: Needs `autoComplete="given-name"`, `autoComplete="postal-code"`, `autoComplete="country"`, etc.
- `CartSidebar.jsx` - **NOT DONE**: Needs `autoComplete="street-address"`, `autoComplete="postal-code"`, etc.

### WS7-11: Other Improvements
**Completed:**
- `index.html` - Added `<link rel="preconnect">` for cdnjs.cloudflare.com and images.unsplash.com
- `App.jsx` - Wrapped `<Routes>` in `<main id="main-content">` for skip link target
- `NavBar.jsx` - Added skip-to-main-content link (`<a href="#main-content" className="sr-only">`)
- `ThemeContext.jsx` - Added `colorScheme` CSS property, dynamic `<meta name="theme-color">` update

**NOT DONE (lower priority):**
- WS7: Add `width`/`height` attributes and `loading="lazy"` to `<img>` tags across pages
- WS8: Replace `...` with `…` (ellipsis), add `font-variant-numeric: tabular-nums` to number columns, `text-wrap: balance` on headings
- WS9: URL state reflection for chef dashboard tabs, directory filters, meal plan week navigation
- WS11: Remove `!important` overrides (~13 instances, mostly in responsive nav rules lines ~277-327)

---

## REMAINING WORK SUMMARY (Priority Order)

### 1. `styles.css` - Sequential edits required (DO NOT use parallel agents on this file)

#### a) Add global reduced-motion guard (append to end of file)
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

#### b) Fix remaining hardcoded colors
- Line 495: `.toast` `border-left:4px solid #aaa` -> `border-left:4px solid var(--muted, #aaa)`
- Line 777: `.field-hint` `color:#a94442` -> `color:var(--danger, #dc2626)`
- Line 1530: `.metric-change.positive` `color: #168516` -> `color: var(--success, #168516)`
- Line 1533: `.metric-change.negative` `color: #a11919` -> `color: var(--danger, #dc2626)`
- Line 2823: `.chef-availability-badge.available` `color: #047857` -> `color: var(--success, #047857)`
- Line 2829: `.chef-availability-badge.unavailable` `color: #b45309` -> `color: var(--warning, #b45309)`

#### c) Fix remaining touch targets
- Line 754-755: `.file-clear-btn` width/height from `24px` to `44px`
- Line 380-381: `.nav-icon-link` width/height from `40px` to `44px`

#### d) Replace `:focus` with `:focus-visible` (15 locations listed above in WS5 section)

### 2. Page Components - Hardcoded colors to CSS variables
- `Account.jsx` (3 locations) - `#d9534f` -> `var(--danger)`
- `Profile.jsx` (2 locations) - `#f5c6cb` -> `var(--danger-bg)`, `#a94442` -> `var(--danger)`
- `CustomerOrders.jsx` (1 location) - `#d9534f` -> `var(--danger)`
- `ChefDashboard.jsx` (2 locations) - `#d9534f` -> `var(--danger)`
- `MealPlans.jsx` (8 locations) - `#d9534f` -> `var(--danger)`

### 3. Profile.jsx - Semantic labels
Replace ~19 instances of `<div className="label">` with `<label htmlFor>` and add `id` to inputs.

### 4. Account.jsx - Semantic labels
Replace ~6 instances of `<div className="label">` with `<label htmlFor>` and add `id` to inputs.

### 5. Profile.jsx + CartSidebar.jsx - Autocomplete attributes
Add `autoComplete` attributes to remaining form fields.

### 6. Component inline animations - Reduced motion guards
Add `prefers-reduced-motion` guards to inline `<style>` blocks in:
- `SousChefWidget.jsx`
- `MealPlanWeekView.jsx`
- `TodayDashboard.jsx`
- `GhostInput.jsx`

### 7. Lower Priority (WS7-11)
- Add `width`/`height` + `loading="lazy"` to images
- Typography fixes (ellipsis chars, tabular-nums, text-wrap: balance)
- URL state reflection for filters/tabs/pagination
- Remove `!important` overrides

---

## CRITICAL NOTES

1. **NEVER edit `styles.css` with parallel agents.** The file is ~13,000 lines and concurrent edits cause "file modified since read" conflicts. All `styles.css` edits must be sequential.

2. **Non-frontend files in git diff are unrelated.** The following modified files are from a different feature branch and should NOT be touched:
   - `chefs/api/serializers.py`
   - `chefs/tasks.py`
   - `custom_auth/models.py`
   - `custom_auth/serializers.py`
   - `shared/utils.py`

3. **CSS variable naming convention:** Use existing variables from `:root` block (lines 20-70 of styles.css):
   - `--danger: #dc2626`, `--danger-bg: rgba(220, 38, 38, 0.12)`
   - `--success: #168516`, `--success-bg: rgba(22, 133, 22, 0.12)`
   - `--warning: #b45309`, `--warning-bg: rgba(245, 158, 11, 0.12)`
   - `--info: #1d4ed8`, `--info-bg: rgba(29, 78, 216, 0.08)`
   - `--muted: #5c6b5d` (light), `#c0ccc4` (dark)

4. **Build verification:** After all changes, run `cd frontend && npm run build` to verify no regressions.

5. **The full plan file** with detailed rationale is at: `/Users/michaeljones/.claude/plans/harmonic-napping-tide.md`
