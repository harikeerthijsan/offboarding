# Codex change log

This file tracks changes made by Codex from 2026-10-12 onward. Future file-changing tasks will append entries with affected files, validation, and remaining work. Repository instructions in `AGENTS.md` require maintaining this log.

## 2026-10-12 — Remove alternate login options

- Removed Google and Microsoft sign-in buttons and the "or continue with" divider from `frontend/src/pages/LoginPage.tsx`.
- Removed the unused provider icons and single-sign-on placeholder handler.
- Preserved pre-existing login-page edits. Existing edits to `frontend/src/styles/login.css` were not made as part of this task.
- Validation: `npm run build` passed from `frontend` after running outside the filesystem sandbox, which initially blocked Vite configuration access.
- Remaining work: redeploy the frontend for the live app to display the change.

## 2026-10-12 — Establish ongoing change tracking

- Created `codex.md` as the running change log.
- Created `AGENTS.md` with instructions to update this log for future file changes, preserve history, and exclude secrets and pre-existing user edits.
- Validation: documentation-only additions; no application tests needed.

## 2026-10-12 — Refine login feature cards

- Updated `frontend/src/styles/login.css` to make the five feature cards more compact with smaller padding, 12px labels, 28px icon backgrounds, subtle borders and shadows, and muted blue icons.
- Removed continuous floating animation from the feature cards and softened hover styling. Preserved the existing positions and responsive layout.
- Updated `frontend/src/pages/LoginPage.tsx` to reduce feature icons from 18px to 15px.
- Validation: frontend `npm run build` and `git diff --check` passed. Visual browser verification was not performed.
- Remaining work: redeploy the frontend to apply the design to the live app.

## 2026-10-12 — Show only the login form on mobile

- Updated `frontend/src/styles/login.css` at widths of 620px and below to hide the promotional brand section and decorative background.
- Centered the login form with mobile padding and dynamic viewport height; allowed the page to grow for short screens and form messages.
- Validation: frontend `npm run build` and `git diff --check` passed. Visual browser verification was not performed.
- Remaining work: redeploy the frontend for the mobile layout to appear in the live app.

## 2026-10-12 — Dashboard visual and motion enhancement

- Inspected the React/Vite entry point, protected `/dashboard` route, main layout, role-specific dashboard views, API data sources, existing navigation handlers, and working tree before editing. Preserved all prior login and documentation changes.
- Added `frontend/src/components/DashboardMotion.tsx`, a presentation-only wrapper with decorative layers and requestAnimationFrame-based pointer tracking. It updates CSS properties without React state, skips touch/reduced-motion tracking, and cleans up listeners and animation frames.
- Added `frontend/src/styles/dashboard-motion.css` with scoped light blue/violet backgrounds, translucent cards, subtle borders/shadows, staggered entrances, floating accents, pointer glow, hover polish, and visible focus outlines. Decorations cannot intercept pointer events. Touch and reduced-motion overrides are included.
- Updated `frontend/src/pages/DashboardPage.tsx` only to wrap both existing dashboard views and add normalized SVG path animation attributes to the existing live trend chart. Department bars animate visually without changing their widths or values.
- Kept all existing data fetching, role selection, buttons, handlers, labels, routes, dates, and layouts. No mock KPIs, new dependencies, backend, API-client, authentication, routing, or workflow changes. The separate HR offboarding dashboard and sidebar were left intact.
- Validation: TypeScript compilation and Vite production build passed via `npm run build`; `git diff --check` passed. Reviewed the dashboard diff to confirm only presentation changes.
- `npm run lint` could not run: the repository has ESLint 9 installed but no `eslint.config.js/mjs/cjs`. Did not expand scope to alter tooling.
- Limitations: no browser automation tool was available; visual comparison, mobile rendering, console inspection, keyboard interaction, and authenticated workflow testing were not performed. Existing KPI tiles have no sparklines, so none were fabricated. Reference imagery was interpreted through CSS rather than inserted as a static dashboard image.
- Remaining work: inspect the dashboard in a browser and redeploy the frontend for the live app.

## 2026-10-12 — Make dashboard styling more visible

- The user's screenshot showed the initial motion styles applied, but the effect was too subtle relative to the reference.
- Added decorative SVG blue/violet ribbons in `frontend/src/components/DashboardMotion.tsx` with slow drift and existing pointer parallax. The SVG remains inside the noninteractive, aria-hidden decorative layer.
- Updated `frontend/src/styles/dashboard-motion.css` with a distinct greeting panel, translucent blurred cards, colored KPI top borders, section heading accents, and a blue/violet primary-button gradient. Preserved all controls, layout hierarchy, and data.
- Mobile ribbon animation is disabled; reduced-motion rules continue to disable animations.
- Validation: production build (including TypeScript) and `git diff --check` passed. Browser visual/workflow checks remain unperformed; lint remains blocked by the missing repository ESLint config.
- Remaining work: refresh the local frontend or redeploy the live frontend and visually review the result.

## 2026-10-12 — Match the supplied dashboard reference more closely

- Added `frontend/public/dashboard-office.png`, generated with the imagegen skill and visually inspected: a panoramic office/sunset skyline with blue-violet ribbons and a light text area.
- Updated `frontend/src/styles/dashboard-motion.css` with dashboard-scoped sidebar styling, gradient active navigation, compact spacing and KPI cards, and a photographic greeting banner. Existing navigation hierarchy remains intact; mobile uses a simple background.
- Added a live-data Offboarding Pipeline to `frontend/src/pages/DashboardPage.tsx`, using the existing overview response and all eight real stages. The View All action links to the existing HR offboarding route. No fabricated counts, dates, trends, photos of employees, or tasks were introduced.
- Kept existing dashboard sections and controls. Reference features without existing data/behavior (such as a new global search and KPI history sparklines) were not fabricated.
- Validation: TypeScript and Vite build passed; `git diff --check` passed. Generated banner visually inspected. Full browser rendering and authenticated workflow testing remain unperformed; repository lint configuration remains missing.
- Remaining work: redeploy the frontend and review the dashboard in desktop/mobile browsers.

## 2026-10-12 — Remove KPI monthly comparisons

- Removed percentage trends, trend arrows, "No change", and "vs last month" from all five KPI cards in `frontend/src/pages/DashboardPage.tsx`.
- Preserved the live counts, labels, icons, and API response format.
- Validation: frontend production build passed. Remaining work: redeploy the frontend for the live app.

## 2026-10-12 — Write the application user guide

- Reviewed navigation, dashboard data sources, employee/profile/organization screens, resignation and notice rules, KT actions, asset/department clearance, settlement, interviews, final-review prerequisites, documents, and notifications against frontend/backend source.
- Created `USER_GUIDE.md` with role responsibilities, an end-to-end walkthrough, specific button instructions, troubleshooting, and test-reset guidance without storing credentials.
- Documented current behavior that differs from earlier advice/README: initial resignation dates are automatic; completing notice sets the employee EXITED before final approval; asset declaration is blocked after notice completion; final review accepts submitted or reviewed interviews.
- Validation: `git diff --check` passed; reviewed headings and source-backed workflow steps. Documentation-only task; no application build/tests required. No live workflow testing was performed.
