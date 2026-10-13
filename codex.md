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
- Skills form UI: updated `frontend/src/pages/SkillsPage.tsx` and added `frontend/src/styles/skills-form.css` to present skill entries as labeled, responsive cards instead of a cramped horizontal table. Added accessible field names and clearer removal controls; preserved existing fields, datalists, validation, save/submit handlers, and cycle rules. Production build passed (with Vite's bundle-size advisory); browser verification not performed. Preserved existing backend skills edits. Redeploy frontend for live changes.
# Skills Hub visibility review — 2026-10-12

- Confirmed employee access in sidebar navigation and the authenticated SSO endpoint; employees map to the external hub's employee role.
- Moved the existing Skills Hub button in `frontend/src/components/Sidebar.tsx` directly below My Skills, instead of after the entire navigation list. Preserved SSO behavior and permissions.
- Validation: frontend build and diff whitespace check passed (existing bundle-size advisory). Live deployment, external SSO configuration, and employee browser view were not tested. Missing SSO configuration affects opening the hub, not whether its link renders. Redeploy frontend to apply the placement change.
# Internal Skills Hub navigation — 2026-10-12

- Corrected `frontend/src/components/Sidebar.tsx`: Skills Hub now uses the existing internal `/skills` NavLink for every supported role, replacing the duplicate external SSO button and its error alert/loading handler. Catalogue and Team Skills retain their existing role visibility.
- Renamed the former My Skills navigation entry to Skills Hub; the destination remains the existing My Skills page. No external service configuration is needed for this navigation. Left unrelated backend/service code and existing edits intact.
- Validation: frontend production build passed after removing unused imports; live employee browser flow not tested. Redeploy frontend to apply the correction.

## 2026-10-12 — Commit and push pending skills changes

- User requested committing and pushing all pending code. Included existing backend skills cycle/submission/export work alongside the responsive skills form, internal Skills Hub navigation, and change log.
- Validation: all 12 backend skills tests passed with DEBUG=False for the test process; frontend build previously passed; git diff --check passed.


# Full project testing — 2026-10-12

- All 455 Django tests passed in 482.322 seconds; Django checks, migration consistency, and frontend TypeScript/production build passed.
- Lint blocked by missing ESLint configuration. Local deployment check warns about SECRET_KEY strength; Vite reports a bundle-size advisory. Browser/live UI testing remains unperformed.
- Added `TEST_REPORT.md` with results and limits; normalized legacy encoding in this log to UTF-8. No application code changes.

## 2026-10-13 — Skills Hub Phase 3 frontend (cycle management + export)

- Added `frontend/src/pages/SkillsCyclesPage.tsx`: staff Review Cycles manager (list, create/edit/delete via modal) plus an Excel export panel (status + cycle filter) that fetches with the auth header and downloads a blob.
- Added an "Export Excel" button to `frontend/src/pages/SkillsTeamPage.tsx`.
- Extended `frontend/src/services/skillsService.ts` with createCycle/updateCycle/deleteCycle and exportUrl; added CyclePayload type.
- Added `id` to the cycles_for output (`backend/apps/skills/cycles.py`) and to the CycleRow type so the manager can edit/delete; routed `/skills/cycles` and added a Review Cycles sidebar sub-item (HR/ADMIN).
- Added backend tests for Phase 3 (cycle CRUD, export xlsx, staff submissions filters, permission gates).
- Validation: 18/18 skills tests pass; Django check clean; frontend tsc + vite build clean.

## 2026-10-13 — Skills Hub review-calendar import

- Added `backend/apps/skills/import_calendar.py` (ported from lib/import.ts detectCalendar): parses CSV/XLSX, fuzzy header detection, date parsing (01-Oct-2026 / ISO / Excel serial), upserts ReviewCycle by Cycle ID, reports skipped rows.
- Added `CalendarImportView` (POST /api/skills/cycles/import/, staff, multipart, 5MB cap) + URL.
- Frontend: "Import Calendar" button + modal on `SkillsCyclesPage.tsx`; `importCalendar` in skillsService.
- Added 4 backend tests (upsert + skip bad rows, idempotent re-import, employee 403, no-cycle-id 400).
- Validation: 22/22 skills tests pass; Django check clean; frontend tsc + vite build clean.
# Add three requested active employees — 2026-10-13

- Added `seed_requested_employees` management command and invoked it on backend startup after initial seeding. Creates JSAN022 (Kajal Prajwal Mendon), JSAN083 (Anjali Bhadouria), and JSAN400 (Puranapu Shiva Ramakrishna) using supplied emails and screenshot dates/departments/designations.
- Set new profiles ACTIVE and accounts to EMPLOYEE. Passwords are unusable until HR provisions them; no shared credentials added. Existing employee/account data is preserved on repeat runs.
- Linked JSAN083 to Kalpesh Mehta (JSAN005). Anjali Singh and Damodar manager records were not found, so JSAN022 and JSAN400 manager links remain pending clarification.
- Local and Railway dry-runs passed; applied the requested import locally and live. Added two automated tests for dry-run rollback and repeat-run preservation; both passed. Django check passed.
- The earlier draft `import_missing_employees.py` remains uncommitted and is not part of this change. The broader missing-employees sync was stopped and has not been applied.
# Correct JSAN083 details — 2026-10-13

- Corrected JSAN083 locally and live to Anjali Singh, joining date 2021-04-19, phone 9011099221, and designation Account Manager - IN. Used Recruitment-IN based on the corrected designation. Preserved email, password, account role, status, and Kalpesh reporting-manager link.
- Linked JSAN022 (Kajal) to JSAN083 as the previously supplied reporting manager. Updated deployment seed data and regression assertions to match; existing rows remain preserved during later deployments.
- Validation: targeted employee import tests passed; local/live correction completed. Updated code pushed to main under the continuing request to add these employees and push.
# Link Shiva's reporting manager — 2026-10-13

- Confirmed screenshot manager JSAN349 is Damoder Reddy Banala and linked local JSAN400 to that employee.
- Updated requested-employee seed and regression tests with the confirmed manager. Both targeted tests passed.
- No live database change, commit, or push performed, following the user's instruction to withhold pushes. Existing live records are preserved by the seed, so the live JSAN400 manager will require an explicit data update when authorized.
# Correct exited employee emails from workbook — 2026-10-13

- Added `correct_exit_emails` management command to match Exit-sheet emails by JSAN ID, validate uniqueness/ownership, and update employee plus login email atomically. Preview rolls back by default; passwords/usernames/statuses remain unchanged. Trimmed spaces and stray trailing periods.
- Corrected 61 exited employee emails locally using the supplied workbook. Three addresses conflict with active employees (JSAN215/JSAN278, JSAN016/JSAN291, JSAN159/JSAN303); JSAN294 has a blank sheet email. Those four remain unchanged pending clarification.
- Validation: preview and apply completed; repeated preview shows zero further updates for resolvable rows. No live-data changes or push performed.

## 2026-10-13 — Baked exit-email sync command (runnable on live)

- Added `backend/apps/employees/management/commands/sync_exit_emails.py`: idempotent command with 64 JSAN ID -> real email mappings baked in from the Exit sheet of "List of active & exit Employees (2).xlsx" (blank JSAN294 omitted). Updates Employee + linked User email/username together, only for EXITED employees; skips already-correct rows and reports ownership conflicts (JSAN215/JSAN016/JSAN159) without overwriting.
- Purpose: the existing file-based correct_exit_emails needs the workbook; this baked version can run on the live server via Railway SSH (like add_gis_employees).
- Local run: 0 updated / 61 skipped (already correct) / 3 conflicts — matches expectations. Django check clean.
- Remaining: run on live to replace the .local placeholders; 4 rows need manual clarification (JSAN294 blank; JSAN215/016/159 emails already held by active JSAN278/291/303).
