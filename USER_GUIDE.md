# JSAN People360 User Guide

Reviewed against the project source on 12 October 2026. This guide describes the implemented interface; a live deployment may differ until the latest frontend and backend are deployed. The instructions were checked against source code, not through an end-to-end live workflow test.

## Contents

1. [Sign in and account settings](#sign-in-and-account-settings)
2. [Roles and navigation](#roles-and-navigation)
3. [Dashboard](#dashboard)
4. [Employee and organization records](#employee-and-organization-records)
5. [Offboarding walkthrough](#offboarding-walkthrough)
6. [Assets and departmental clearance](#assets-and-departmental-clearance)
7. [Documents and notifications](#documents-and-notifications)
8. [Troubleshooting](#troubleshooting)
9. [Testing checklist](#testing-checklist)

## Sign in and account settings

1. Open your organization's People360 URL.
2. Enter your assigned email and password, then select **Sign In**. Google and Microsoft sign-in options have been removed.
3. Use **Keep me signed in** if appropriate for your device.
4. For a forgotten password, select **Forgot Password?** and contact HR. This currently displays contact instructions; it does not send a password-reset email.
5. Open the account menu in the top-right corner to access **My Profile** or **Sign Out**.

In **My Profile**, use **Edit My Details** to update the personal/contact fields offered by the form. Review sensitive identity and bank details carefully before saving. Use the password-change section to enter your current password, a new password, and its confirmation. Contact HR for changes to employment details outside the editable fields.

On phones, the login page shows only the login form. Within the application, available controls depend on your role and the record's current status.

## Roles and navigation

| Role | Main responsibilities |
| --- | --- |
| Employee | Submit their own resignation, complete assigned handover work, declare asset returns, complete an exit interview, download released documents. |
| Manager | Review direct-report resignations, organize/review knowledge transfer, perform permitted manager clearance. |
| HR | Maintain employee and organization records, approve resignations, manage notice periods, set up clearance, review settlement/interviews, approve final offboarding, manage exit documents. |
| IT | Maintain asset records and assignments, record/verify returns, perform IT clearance. |
| Finance | Prepare and submit settlement, perform permitted Finance clearance, generate the full and final settlement document. |
| Admin | Perform administrative actions across the workflow, including employee/organization maintenance, assets, settlement and final approval. |

The sidebar preserves role-specific access. Employees do not see the employee directory or HR Dashboard. Finance and IT do not have a Resignation sidebar entry; they can access relevant records through **Clearances**, authorized notifications, and existing dashboard links. A visible menu or page does not grant permission to every action on it.

## Dashboard

Employees see a personal profile dashboard with employment details, their latest resignation, and quick actions.

Other roles see the workforce overview: employee counts, department counts, an offboarding pipeline, department distribution, recent exits, upcoming tasks, trends, and quick actions. Counts and lists come from the application data. KPI monthly percentage comparisons have been removed.

**Dashboard** and **HR Dashboard** are separate pages. HR/Admin use **HR Dashboard** to search offboarding records by name/ID/email and filter by department, settlement, or final-review status. Use **Review** to open a record's final review; use **Previous/Next** for additional results.

Decorative motion does not indicate workflow progress. Reduced-motion preferences disable animations, and touch devices skip cursor tracking.

## Employee and organization records

### Employees

1. Open **Employees** and search/filter for the person.
2. Open their detail page to review their department, designation, manager, and employment status.
3. HR/Admin can create records and use **Edit Employee** to update permitted fields.
4. Before testing a resignation, verify that the employee has a login, is ACTIVE, and has the correct reporting manager.

### Organization

Open **Organization** to view departments, designations, and the reporting hierarchy. HR/Admin can use **Add Department** and **Add Designation**, enter the displayed fields, and **Save**. Assign the correct department and manager to employee records so approvals reach the correct people.

## Offboarding walkthrough

The following order avoids the current asset-declaration restriction. Some stages can run in parallel, but final approval requires all prerequisites.

### 1. Employee submits resignation

1. Log in as the employee being offboarded.
2. Open **Resignation**, or use **Submit Resignation/New Offboarding** where available.
3. Select a resignation reason and enter optional notes.
4. Select **Review & Submit**, check the preview, then **Confirm & Submit**.

The current implementation sets the resignation date to the submission day and calculates the initial last working day using its notice policy: one month for tenure under six months, otherwise two months. HR separately manages notice-period dates. Do not assume every date is manually entered.

The request goes to the manager. An active employee profile is required; IT/Finance cannot create resignations through this flow. The presence of an HR/Admin creation button does not mean they can submit a resignation for an arbitrary employee.

### 2. Reporting manager reviews

1. Log in as the employee's direct manager (or Admin).
2. Open the submitted request under **Resignation**.
3. Review the reason, dates, and notes; approve or reject using the offered action and comments.

Manager approval advances the request to HR review. Internally this status is named `MANAGER_REVIEW`; it means the manager stage has advanced, rather than final approval being complete.

### 3. HR approves

1. HR/Admin opens the request after manager approval.
2. Review the submission and perform the HR approval action.
3. The request becomes **APPROVED**, enabling the workflow sections.

If a request is rejected or cancelled, review its details rather than trying to continue its active stages. Use cancellation only when the action is offered for your role and request status.

### 4. HR starts notice period

1. Open the request's **Notice Period** page as HR/Admin.
2. Enter **Notice Period Start Date**, **Notice Period Days**, and **Expected Last Working Day**.
3. Enter any applicable early-relieving date/comments.
4. Select **Start Notice Period**. Use **Save Changes** for later permitted edits.

For early release, the employee requests it from their resignation details; HR reviews it through **Review Early Release**. HR can use **Record Extension** when an extension is needed. Resolve a pending early-release request before completing notice.

**Do not complete notice until the employee has submitted the asset declaration described below.**

### 5. Complete knowledge transfer

1. Open **Knowledge Transfer** from the request. Authorized staff can create tasks with **New KT Task**, specifying the title, receiver, responsibility, priority, project if applicable, and dates.
2. The departing employee opens an assigned task, selects **Start KT**, records completion notes and document links, then **Submit for Review**.
3. The assigned receiver reviews the handover and selects **Accept** or **Request Changes**.
4. The manager/Admin reviews the accepted task, selects **Approve**, enters the completion date, and **Confirm Approval**.
5. After required tasks are completed, an authorized user selects **Mark KT Complete** for the overall phase.

If changes are requested, update the handover and resume/resubmit it. Completing an individual task and marking the overall KT phase complete are separate actions. If no KT tasks exist, final review currently does not require a KT completion marker.

### 6. Employee declares asset returns

1. Log in as the departing employee and open **Resignation → request details → Clearance**.
2. Locate **Step 1 · Employee Asset Declaration**.
3. Mark each listed item **Yes** (returned), **No** (pending), or **N/A** (not applicable).
4. Once all assigned property is returned, tick the declaration confirmation, add optional notes, and select **Submit Declaration**.

Do not confirm that no property remains while items are still pending. The declaration is an employee statement; asset returns still require staff recording and verification.

**Current limitation:** the declaration is allowed only in **APPROVED** or **NOTICE_PERIOD**. Completing notice changes the request to **COMPLETED**, hiding and blocking an unsubmitted declaration. This is a known workflow restriction, not proof that clearance is complete. An already submitted declaration is displayed instead of the form.

### 7. Staff complete clearance

Follow [Assets and departmental clearance](#assets-and-departmental-clearance) below. HR/Admin must mark the overall clearance complete after the required asset and departmental work is finished.

### 8. HR completes notice

1. HR/Admin opens **Notice Period**.
2. Use the completion action and enter the **Actual Last Working Day**.
3. Confirm completion only after resolving pending early-release review and submitting the employee declaration.

**Current behavior:** this sets the resignation to **COMPLETED** and the employee to **EXITED**. It does not complete final offboarding approval. Completed notice records cannot be edited through the ordinary notice form.

### 9. Finance prepares settlement; HR approves

1. Finance/Admin opens **Final Settlement** for the employee's request.
2. Select **Create Settlement**, then **Edit Values**.
3. Enter pending salary, leave encashment, bonus, incentives and other additions; enter notice recovery, loan/advance deductions and other deductions as applicable.
4. Select **Save**. Totals are recomputed by the server.
5. Select **Submit for Review**. The settlement becomes **UNDER_REVIEW**.
6. HR/Admin opens the same settlement, selects **Approve**, enters **Settlement Date** and optional comments, then **Confirm Approval**.

HR cannot create or submit the settlement; Finance/Admin does that. HR/Admin can reject it for correction. The preparer cannot approve their own settlement unless they are Admin. Approval records the settlement decision; it is not evidence of a bank payment.

### 10. Employee completes exit interview; HR reviews

1. Employee opens **Exit Interview → Start Exit Interview**.
2. Fill in the reasons, experience ratings, feedback, suggestions, and other displayed answers.
3. **Save Draft**, then **Submit for Review**.
4. HR/Admin reads the answers, adds **HR Review Notes**, and selects **Mark Reviewed**.

HR/Admin can also start, edit, and submit an in-progress interview when conducting it with the employee. **Reopen** allows corrections where offered. Final review currently accepts a submitted **COMPLETED** interview or a **REVIEWED** one; HR review is still recommended.

### 11. HR/Admin approves final offboarding

1. Open **Final Review**, or use **HR Dashboard → Review**.
2. Check the pending-items list. Notice must be completed; required KT must be marked complete; overall clearance must be complete; settlement must be approved; exit interview must be submitted/reviewed.
3. Enter **Final Review Date** and select **Start Final Review**.
4. Select **Approve Offboarding**, enter **Final Approval Date** and optional comments, then **Confirm Final Approval**.

Use final-review approval status as the completion check. An employee showing EXITED or a resignation showing COMPLETED alone does not prove final approval is done. Final rejection requires correction before approval can proceed.

## Assets and departmental clearance

### Asset catalogue

Open **Assets**. Employees see their own assigned assets. Authorized staff can search/filter the catalogue. IT/Admin can use **New Asset** or **Edit**, recording asset ID, name, type, serial number, condition, assignee and assignment date.

### Asset return verification

1. IT/HR/Admin opens the employee's **Clearance → Assets**.
2. Add assigned assets to clearance where required. Employee declaration precedes IT asset-clearance work.
3. Use **Record Return** and enter the return date, condition and remarks.
4. Use the verification action to clear the returned asset or record the appropriate rejection/damage outcome.
5. Resolve every outstanding asset according to the displayed status. Do not mark an asset lost simply to bypass return work.

### Department checklists

1. HR/Admin sets up the required departments on the employee's Clearance page.
2. Department staff open **Clearances** and the appropriate employee record.
3. Complete checklist items or mark genuinely inapplicable items **N/A**.
4. Select **Clear**, enter **Clearance Date** and comments, then **Confirm Clear**.
5. HR/Admin selects **Mark Clearance Complete** when all required departments and asset outcomes are acceptable.

| Clearance department | Roles allowed by the department mapping |
| --- | --- |
| IT | IT, Admin |
| Admin | Admin |
| Finance | Finance, HR, Admin |
| HR | HR, Admin |
| Manager | Manager, Admin, subject to record access |

Assigned responsibility and record access can further restrict actions. **Reject/Reopen** handle corrections where available. Checklist **Reset** resets that checklist item; it does not reset an employee's offboarding.

## Documents and notifications

### Generate and release exit documents

1. HR/Admin opens the request's **Documents → Generate Document**.
2. Choose **Relieving Letter**, **Experience Letter**, **Full & Final Settlement**, **Exit Clearance Certificate**, or **Other**.
3. Enter the document date as required and select **Generate**. Follow prerequisite errors if generation is blocked.
4. **Preview**, then **Submit**, **Approve**, and **Release** using the actions available for the document's status.
5. Employee opens **Documents** to **Download** released documents.

Finance can generate the Full & Final Settlement document; HR/Admin manages approval/release. Generated or approved documents are not yet visible to the employee until released. HR/Admin can **Regenerate** a version or **Revoke** a document with a reason where permitted.

### Notifications

Open the header bell or **Notifications**. Use **All/Unread**, **Open**, **Mark read**, or **Mark all read**. Opening a notification can lead directly to the relevant request/task. In-app notifications work independently of whether production email delivery has been configured.

## Troubleshooting

| Issue | What to check |
| --- | --- |
| No asset declaration form | Correct employee account; request is APPROVED/NOTICE_PERIOD; declaration not already submitted. If notice was completed first, contact the administrator about the known restriction. |
| No Create Settlement button | Use Finance/Admin; HR reviews rather than prepares. |
| Cannot approve resignation | Manager stage precedes HR stage; confirm the assigned reporting manager and current status. |
| Cannot complete notice | Resolve an outstanding early-release request; enter the required actual last working day. |
| Final approval disabled | Read the pending-items list and complete each phase; overall KT/clearance markers are separate from individual approvals. |
| Cannot see/download documents | Employee documents must be RELEASED; check revoked status and file availability with HR. |
| Missing button or permission denied | Check role, assignment and record status. Another role may own the next action. |
| Design changes not visible | Latest frontend must be deployed; refresh the page. |
| Employee is EXITED but work remains | Notice completion sets EXITED; check final-review status separately. |

## Testing checklist

Use a designated test employee and record their ID/email. Complete: resignation → manager approval → HR approval → start notice → KT → employee declaration → asset/department clearance → complete notice → settlement → interview → final approval → release/download documents. Record any missing controls or errors at each stage.

Administrative reset is intended only for test data. It deletes all offboarding history for the selected employee, restores their ACTIVE status, and restores assets still assigned to them to ASSIGNED. It is not a notice-only undo, does not reset passwords, and cannot recover deleted history.

An operator can preview and then execute it in the live backend container:

```bash
/opt/venv/bin/python manage.py reset_offboarding --email test.employee@example.com --dry-run
/opt/venv/bin/python manage.py reset_offboarding --email test.employee@example.com
```

Replace the placeholder with the intended test employee; verify the dry-run identifies the correct person before execution. The `/opt/venv/bin/python` path is the environment path observed in this project's Railway backend. Run against the intended environment, since a local command normally changes local data instead of live data.

## Guide maintenance

Update this guide when workflow rules, button labels, permissions, or date behavior change. Source references used for this review include the frontend pages, Sidebar/Header, and backend resignation, notice, KT, clearance, settlement, final-review and document handlers. This guide takes current source behavior over older README statements or earlier chat instructions.
