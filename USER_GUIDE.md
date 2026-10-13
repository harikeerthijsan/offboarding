# JSAN People360 — User Guide

A complete, role-by-role guide to the JSAN People360 platform: employee records,
the full offboarding workflow, company policies, and the Skills Hub (skill matrix
and six-month review cycles).

> This guide describes the implemented interface. A live site may differ until the
> latest frontend/backend are deployed. Which buttons you see depends on your
> **role** and the **current status** of the record — a visible page does not grant
> permission for every action on it.

---

## Contents

1. [Getting started — sign in & your account](#1-getting-started--sign-in--your-account)
2. [Roles & what each can do](#2-roles--what-each-can-do)
3. [Navigation & the dashboard](#3-navigation--the-dashboard)
4. [Your profile & self-service](#4-your-profile--self-service)
5. [Employees & organization (HR/Admin)](#5-employees--organization-hradmin)
6. [Offboarding — end-to-end walkthrough](#6-offboarding--end-to-end-walkthrough)
7. [Assets & departmental clearance](#7-assets--departmental-clearance)
8. [Exit documents](#8-exit-documents)
9. [Policies](#9-policies)
10. [Skills Hub](#10-skills-hub)
11. [Notifications & email](#11-notifications--email)
12. [Troubleshooting](#12-troubleshooting)
13. [Admin & operations](#13-admin--operations)

---

## 1. Getting started — sign in & your account

1. Open your organization's People360 URL in a browser.
2. On the login screen, enter your **email or Employee/JSAN ID** and your **password**, then select **Sign In**.
3. Tick **Keep me signed in** on trusted personal devices.
4. **First-time users / new accounts:** you'll be given a temporary password by HR (change it after your first sign-in — see §4).
5. **Forgot your password?** Select **Forgot Password?** — the screen shows instructions to contact your HR administrator. (There is no automated reset email yet.)
6. **Single sign-on (Microsoft/Google)** buttons are not active; use email + password.

Your **JSAN ID** is the part of your email before `@` (e.g. `vsatish` for `vsatish@jsanconsulting.com`).

To sign out, open the account menu in the top-right and select **Sign Out**.

---

## 2. Roles & what each can do

| Role | What they can do |
| --- | --- |
| **Employee** | View their profile & dashboard, update their own personal details, maintain and submit their skill matrix, submit their own resignation, complete assigned knowledge-transfer tasks, declare asset returns, complete an exit interview, view policies, download released exit documents. |
| **Manager** | Everything an employee can, plus review direct-report resignations, organize/review knowledge transfer, perform permitted manager clearance, and view the Skills team directory & catalogue. |
| **HR** | Maintain employee & organization records, approve resignations, manage notice periods, set up clearance, review settlement & interviews, approve final offboarding, manage policies and exit documents, manage Skills review cycles & exports. |
| **IT** | Maintain the asset catalogue & assignments, record/verify asset returns, perform IT clearance. |
| **Finance** | Prepare & submit full-and-final settlement, perform Finance clearance, generate the settlement document. |
| **Admin** | Full access across the platform, including role changes and administrative maintenance. |

The sidebar only shows items your role is allowed to open. Employees don't see the employee directory or HR Dashboard; IT/Finance reach their work through **Clearances** and notifications.

---

## 3. Navigation & the dashboard

The left **sidebar** is your main navigation. Items visible to you depend on your role. Common entries: **Dashboard, Employees, Organization, Resignation** (with **Knowledge Transfer**), **HR Dashboard, Clearances, Assets, My Skills / Skills Hub** (with **Catalogue, Team Skills, Review Cycles**), **Policies, Notifications**.

**Dashboards differ by role:**

- **Employees** get a **personal dashboard**: a profile hero card (avatar, name, designation, status), stat tiles (status, department, designation, tenure), their current offboarding status (if any), their details, and quick actions.
- **Managers / HR / IT / Finance / Admin** get the **workforce overview**: employee & department counts, an offboarding pipeline, department distribution, recent exits, upcoming tasks, and quick actions.

**HR Dashboard** (HR/Admin) is a separate page for searching offboarding records by name/ID/email and filtering by department, settlement, or final-review status. Use **Review** to open a record's final review.

> Visual motion on the dashboard/login is decorative only — it does not indicate progress. Reduced-motion device settings are respected.

---

## 4. Your profile & self-service

Open **My Profile** (top-right account menu, or from the dashboard **Edit Profile**).

**You can edit your own:**
- Personal details (phone, date of birth, gender, address),
- Emergency contact (name, phone),
- Statutory details (Aadhaar, PAN, UAN, ESI),
- Bank details (bank name, account holder, account number, IFSC).

Format is validated on save (e.g. PAN `ABCDE1234F`, IFSC `ABCD0123456`, Aadhaar 12 digits). PAN and IFSC are auto-uppercased.

**Managed by HR (read-only for you):** employee ID, name, email, role, department, designation, manager, joining date, employment status. Contact HR to change any of these.

**Change your password:** in the **Password** section, select **Change Password**, enter your current password, a new password (min 8 characters), and the confirmation, then save.

---

## 5. Employees & organization (HR/Admin)

### Employees
1. Open **Employees**, then search/filter by name, ID, department, type, or status.
2. Open a person's detail page to see department, designation, manager, and employment status. (For **exited** employees, only core Personal & Employment info is shown.)
3. HR/Admin can **Add Employee** and **Edit Employee**.
   - On create, a **login account is provisioned automatically** (choose a role; leave the password blank to auto-generate a temporary one, which is shown once — share it securely).
   - **Department and Designation are required** on create.
   - Personal/statutory/bank fields are optional at creation — the employee can fill them in later from their own profile.
4. **Export:** on the Employees list, **Export** downloads a CSV (honoring your current filters) including each employee's **Joining Date, Exit Date, Exit Interview, and clearance statuses** (KT, IT, Finance, HR, Admin, Manager, Overall).

Before testing or starting an offboarding, confirm the employee has a login, is **ACTIVE**, and has the correct **reporting manager**.

### Organization
Open **Organization** to view departments, designations, and the reporting hierarchy. HR/Admin can **Add Department** / **Add Designation**. Correct department & manager assignments ensure approvals route to the right people.

---

## 6. Offboarding — end-to-end walkthrough

The order below avoids the asset-declaration timing restriction (see step 6). Some stages overlap, but **final approval requires all prerequisites**.

### Step 1 — Employee submits resignation
1. Sign in as the departing employee → **Resignation** → **Submit Resignation**.
2. Choose a reason, add optional notes.
3. **Review & Submit** → check the preview → **Confirm & Submit**.

The resignation date is set to the submission day; the initial last working day is derived from the notice policy (**1 month** for tenure under 6 months, otherwise **2 months**). HR manages the actual notice dates separately. The request goes to the employee's **manager**.

### Step 2 — Manager reviews
1. Sign in as the employee's **direct manager** (or Admin) → open the request under **Resignation**.
2. Review reason/dates/notes → **Approve** or **Reject** with comments.

Approval advances the request to HR review.

### Step 3 — HR approves
1. HR/Admin opens the request after manager approval → performs the HR approval.
2. The request becomes **APPROVED**, unlocking the workflow sections.

### Step 4 — HR starts the notice period
1. Open the request's **Notice Period** page (HR/Admin).
2. Enter **Start Date**, **Notice Period Days**, **Expected Last Working Day**; add early-relieving date/comments if applicable.
3. **Start Notice Period** (use **Save Changes** for later edits).

Employees can request **early release** from their resignation details; HR reviews it. HR can **Record Extension** when needed. **Do not complete notice until the employee has submitted the asset declaration (step 6).**

### Step 5 — Knowledge transfer
1. Open **Knowledge Transfer**. Managers/HR/Admin create tasks with **New KT Task** (title, receiver, responsibility, priority, project, dates).
2. The departing employee: **Start KT** → add notes/document links → **Submit for Review**.
3. The **receiver**: **Accept** or **Request Changes**.
4. The **manager/Admin**: **Approve** (enter completion date) → **Confirm Approval**.
5. When all tasks are done, an authorized user selects **Mark KT Complete** for the phase — this also auto-creates the **Finance clearance** and prompts the employee for the asset declaration.

Completing one task and marking the whole phase complete are separate actions.

### Step 6 — Employee declares asset returns
1. Sign in as the employee → **Resignation → request → Clearance → Step 1 · Employee Asset Declaration**.
2. For **each asset type** (Laptop, Charger, Mouse, Keyboard, Monitor, Headset, Mobile, SIM, ID Card, Access Card, Other), choose **Yes** (returned), **No** (not returned), or **N/A**.
3. Tick the confirmation, add optional notes, **Submit Declaration**. This unlocks the **IT asset clearance**.

> **Timing restriction:** the declaration is only available while the request is **APPROVED** or **NOTICE_PERIOD**. Completing notice sets the request to **COMPLETED** and hides the form — so collect the declaration **before** completing notice.

### Step 7 — Staff complete clearance
See [§7 Assets & departmental clearance](#7-assets--departmental-clearance). HR/Admin marks overall clearance complete when asset + department work is done.

### Step 8 — HR completes notice
1. HR/Admin opens **Notice Period** → completion action → enter **Actual Last Working Day**.
2. Confirm only after the early-release review is resolved and the declaration is submitted.

This sets the resignation **COMPLETED** and the employee **EXITED** — but it does **not** complete final approval.

### Step 9 — Finance settlement; HR approves
1. Finance/Admin opens **Final Settlement** → **Create Settlement** → **Edit Values**.
2. Enter additions (pending salary, leave encashment, bonus, incentives) and deductions (notice recovery, loans/advances, other) → **Save** (totals recompute server-side).
3. **Submit for Review** → HR/Admin **Approve** (enter settlement date) → **Confirm Approval**.

HR cannot create/submit settlement; Finance/Admin does. Approval records the decision — it is not proof of bank payment.

### Step 10 — Exit interview
1. Employee opens **Exit Interview → Start Exit Interview** → fill reasons, ratings, feedback → **Save Draft** → **Submit for Review**.
2. HR/Admin adds **HR Review Notes** → **Mark Reviewed**.

### Step 11 — Final approval
1. Open **Final Review** (or **HR Dashboard → Review**).
2. Clear the **pending-items** list: notice completed, required KT complete, overall clearance complete, settlement approved, exit interview submitted/reviewed.
3. Enter **Final Review Date** → **Start Final Review** → **Approve Offboarding** → enter **Final Approval Date** → **Confirm Final Approval**.

Use **final-review approval** as the true completion check — an employee showing EXITED alone does not mean final approval is done.

---

## 7. Assets & departmental clearance

### Asset catalogue
Open **Assets**. Employees see their own assigned assets. IT/Admin can **New Asset** / **Edit** (asset ID, name, type, serial, condition, assignee, assignment date).

### Asset return verification
1. IT/HR/Admin opens the employee's **Clearance → Assets** (populated after the employee's declaration).
2. **Record Return** (date, condition, remarks).
3. Use the verification action to **clear** a returned asset, or record **reject/damaged/lost** as appropriate.
4. Resolve every outstanding asset.

### Department checklists
1. HR/Admin sets up the required departments on the Clearance page.
2. Department staff open **Clearances** → the employee → complete checklist items (or mark **N/A**).
3. **Clear** (date, comments) → **Confirm Clear**.
4. HR/Admin selects **Mark Clearance Complete** when all required departments and asset outcomes are acceptable.

| Clearance department | Roles allowed |
| --- | --- |
| IT | IT, Admin |
| Admin | Admin |
| Finance | Finance, HR, Admin |
| HR | HR, Admin |
| Manager | Manager, Admin (subject to record access) |

---

## 8. Exit documents

1. HR/Admin opens the request's **Documents → Generate Document**.
2. Choose **Relieving Letter, Experience Letter, Full & Final Settlement, Exit Clearance Certificate,** or **Other**; enter the date; **Generate**.
3. **Preview**, then **Submit → Approve → Release** per the document's status.
4. The employee opens **Documents** to **Download** released documents.

Finance can generate the Full & Final Settlement document; HR/Admin manages approval/release. Documents are only visible to the employee once **RELEASED**. HR/Admin can **Regenerate** a version or **Revoke** with a reason.

---

## 9. Policies

Company policy documents, available to **all employees** to view/download.

**All users:**
1. Open **Policies** from the sidebar.
2. Browse the policy cards (filter by **category** or **search** by title).
3. Select **View** to open a policy (PDF/DOC) in a new tab.

**HR/Admin (manage):**
1. Select **Upload Policy** → enter title, category (HR, IT, Finance, Security, Code of Conduct, Leave & Attendance, Other), optional description → choose a **PDF/DOC/DOCX** file (≤ 20 MB) → **Upload**. New policies are active immediately.
2. **Archive/Restore** hides or re-shows a policy from employees without deleting it.
3. **Delete** removes a policy permanently.

Employees only see **active** policies; HR/Admin see all (including archived).

---

## 10. Skills Hub

Employees keep a **skill matrix** and submit it each company-wide **six-month review cycle**. There is no approval gate — a submitted set is on record immediately and can be updated while its cycle is open. Staff (Manager/HR/Admin) view, export, and manage the catalogue and cycles.

### 10.1 My Skills (all employees)
1. Open **My Skills** (or **Skills Hub**).
2. The banner shows the **active cycle**, its state, and due/closure dates.
3. In the **Skill Matrix**, add a row per skill: **name** (auto-suggested from the catalogue, or type your own), category, status (**Current / Newly learned / In progress**), level, **years** (0.5 steps), company, role, customer/project, note. Use **Add skill** / the ✕ to manage rows.
4. Add an optional note.
5. **Save Draft** to keep working, or **Submit** to record it for the active cycle.
   - You must complete your **profile (department & designation)** before submitting.
   - At least one skill is required to submit.
6. The **Review Timeline** shows every cycle's status for you.

### 10.2 Skill Catalogue (staff)
Open **Catalogue** (under Skills Hub). **Add Skill** (name, typical tools, customers). **Hide/Show** removes a skill from pickers without losing history; **Delete** removes it.

### 10.3 Team Skills (staff)
Open **Team Skills** to see each employee's compliance for the **active cycle** (Submitted / Due / Overdue / etc.), with search and department filter, and a submitted/total summary. **Export Excel** downloads the full skill matrix.

### 10.4 Review Cycles (HR/Admin)
Open **Review Cycles** to manage the six-month calendar:
- **Add Cycle** / **Edit** / **Delete** — set Cycle ID (e.g. `2027-H1`), period start/end, employee due, manager due, closure target, notes.
- **Export Skill Matrix** — choose a **status** (all/submitted/draft/recorded/needs-update) and optional **cycle**, then **Download Excel** (a JSAN/QF/09-style workbook: an Employee Skill Matrix sheet + a per-skill details sheet).
- **Import Calendar** — upload a **CSV or Excel** with columns *Cycle ID, Period Start, Period End, Employee Update Due, Manager Validation Due, Closure Target* (Notes optional). Cycles are matched and updated by Cycle ID; unreadable rows are reported and skipped.

---

## 11. Notifications & email

- Open the header **bell** or **Notifications**. Use **All/Unread**, **Open** (jumps to the related record/task), **Mark read**, **Mark all read**.
- Every in-app notification is **also emailed** to the recipient (resignation, notice, KT, clearance, asset declaration, settlement, exit interview, final review, documents) — provided production email (SMTP) is configured. In-app notifications work regardless of email setup.

---

## 12. Troubleshooting

| Issue | What to check |
| --- | --- |
| Can't sign in / "not an active employee" | Confirm the account exists and the employee is **ACTIVE**. If you were just offboarded for testing, ask an admin to reset you. Log out/in to refresh a stale session. |
| No asset-declaration form | Right employee account; request is **APPROVED/NOTICE_PERIOD**; declaration not already submitted. If notice was completed first, the form is hidden (known restriction). |
| No "Create Settlement" button | Use **Finance/Admin**; HR reviews rather than prepares. |
| Can't approve a resignation | Manager stage precedes HR stage; confirm the assigned reporting manager and current status. |
| Can't complete notice | Resolve any pending early-release request; enter the required actual last working day. |
| Final approval disabled | Read the **pending-items** list and finish each phase; overall KT/clearance markers are separate from individual approvals. |
| Can't download a document | Documents must be **RELEASED**; check for revoked status with HR. |
| Can't submit skills | Complete your **profile (department & designation)** first; add at least one skill; a review cycle must be open. |
| Policy upload rejected | Use **PDF/DOC/DOCX**, ≤ 20 MB; you must be HR/Admin. |
| A new change isn't visible | The latest frontend/backend must be deployed; refresh (Ctrl+Shift+R). |
| Role change not taking effect | Log out and back in. |

---

## 13. Admin & operations

These are operator tasks run against the backend (locally, or on the live server via Railway SSH using the environment's Python, e.g. `/opt/venv/bin/python`).

- **Reset a test employee's offboarding** (deletes their offboarding history, restores ACTIVE, restores assigned assets). Preview first:
  ```bash
  python manage.py reset_offboarding JSAN010 --dry-run
  python manage.py reset_offboarding JSAN010
  ```
- **Change a user's role:**
  ```bash
  python manage.py set_role JSAN252 ADMIN
  ```
- **Add the post-seed GIS employees** (idempotent sync of active roster):
  ```bash
  python manage.py add_gis_employees
  ```
- **Set real emails on exited employees** (idempotent):
  ```bash
  python manage.py sync_exit_emails
  ```

New logins get a temporary password and should change it on first sign-in. Administrative resets affect **data**, not code, and run against whichever database the environment points to — verify you're targeting the intended environment (local vs live) before applying.

---

*Maintain this guide when workflow rules, button labels, permissions, or feature behavior change.*
