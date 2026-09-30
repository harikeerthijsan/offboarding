"""Import employee accounts from the account roster (Name, Email), enriching each
with details (DOJ, designation, department, reporting manager) from the
active/exit workbook.

Matching uses the email local-part as the anchor (initial + full-name token),
with a fallback to exact normalised name equality. Only confident matches are
imported; uncertain/unmatched rows are written to a review CSV instead of
guessing — this protects data integrity (wrong dept/manager/DOJ).

Dev/admin utility. Idempotent: existing emails / employee IDs are skipped.
Business dates come only from the workbook (DOJ) — nothing is auto-generated.

Usage:
  python manage.py import_employees \
      --roster "C:/path/Employee List 1.xlsx" \
      --details "C:/path/List of active & exit Employees.xlsx" \
      --password "Welcome@123" [--commit]
"""
import csv
import os
import re
import difflib

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.employees.models import Department, Designation, Employee


def tokens(s):
    if not s:
        return []
    s = str(s).lower()
    s = re.sub(r'[^a-z ]', ' ', s)
    return [t for t in s.split() if len(t) > 1]


def name_key(s):
    return ' '.join(sorted(tokens(s)))


def is_team_mailbox(name, email):
    blob = f"{name or ''} {email or ''}".lower()
    return bool(re.search(r'\bteam\b|contracts@|hrjsan@|^hr@|info@|admin@|support@', blob))


class Command(BaseCommand):
    help = 'Import employee accounts from the roster + details workbooks.'

    def add_arguments(self, parser):
        parser.add_argument('--roster', required=True, help='Path to the Name/Email xlsx')
        parser.add_argument('--details', required=True, help='Path to the active/exit xlsx')
        parser.add_argument('--password', required=True, help='Shared initial password for created logins')
        parser.add_argument('--commit', action='store_true',
                            help='Actually write to the DB. Without this it is a dry run.')
        parser.add_argument('--review-out', default='import_review.csv',
                            help='Where to write the uncertain/unmatched rows')
        parser.add_argument('--overrides', default=None,
                            help='CSV (email,jsanid) forcing exact, human-confirmed matches')

    def handle(self, *args, **opts):
        try:
            import openpyxl
        except ImportError:
            raise CommandError('openpyxl is required. pip install openpyxl')

        roster_path, details_path = opts['roster'], opts['details']
        for p in (roster_path, details_path):
            if not os.path.exists(p):
                raise CommandError(f'File not found: {p}')

        # ── load roster (Name, Email) ──
        wb1 = openpyxl.load_workbook(roster_path, data_only=True)
        ws1 = wb1[wb1.sheetnames[0]]
        roster = []
        for row in ws1.iter_rows(min_row=2, values_only=True):
            if row and row[0] and len(row) > 1 and row[1]:
                roster.append((str(row[0]).strip(), str(row[1]).strip().lower()))

        # ── load details (Active sheet is the source for existing employees) ──
        wb2 = openpyxl.load_workbook(details_path, data_only=True)
        active, exit_keys = [], set()
        for row in wb2['Active'].iter_rows(min_row=2, values_only=True):
            if row and row[1]:
                active.append(dict(jid=str(row[1]).strip(), name=str(row[2]).strip(),
                                   doj=row[3], desig=(row[4] or '').strip(),
                                   dept=(row[5] or '').strip(), rm=(row[6] or '').strip()))
        if 'Exit' in wb2.sheetnames:
            for row in wb2['Exit'].iter_rows(min_row=2, values_only=True):
                if row and row[2]:
                    exit_keys.add(name_key(row[2]))

        active_by_jid = {a['jid']: a for a in active}

        # ── human-confirmed overrides (email -> jsanid), exact match, no guessing ──
        overrides = {}
        if opts['overrides']:
            if not os.path.exists(opts['overrides']):
                raise CommandError(f"Overrides file not found: {opts['overrides']}")
            with open(opts['overrides'], newline='', encoding='utf-8') as fh:
                for r in csv.reader(fh):
                    if len(r) >= 2 and '@' in r[0]:
                        overrides[r[0].strip().lower()] = r[1].strip()

        # ── match roster → active ──
        matched, review = [], []
        seen_jids = set()
        for name, email in roster:
            if is_team_mailbox(name, email):
                review.append((name, email, '', 'SKIPPED_TEAM_MAILBOX'))
                continue
            if email in overrides:
                chosen = active_by_jid.get(overrides[email])
                if chosen and chosen.get('doj') and chosen['jid'] not in seen_jids:
                    seen_jids.add(chosen['jid'])
                    matched.append((name, email, chosen))
                else:
                    review.append((name, email, overrides[email], 'OVERRIDE_INVALID'))
                continue
            best, score = self._match(name, email, active)
            exact = self._exact_unique(name, active)
            chosen = None
            if exact:
                chosen = exact
            elif score >= 0.9:
                chosen = best
            if chosen and chosen['jid'] not in seen_jids and chosen.get('doj'):
                seen_jids.add(chosen['jid'])
                matched.append((name, email, chosen))
            else:
                reason = 'DUPLICATE_JID' if (chosen and chosen['jid'] in seen_jids) else (
                    'IN_EXIT_SHEET' if name_key(name) in exit_keys else
                    ('NO_DOJ' if chosen else 'NO_CONFIDENT_MATCH'))
                guess = best['name'] if best else ''
                review.append((name, email, f"{guess} (score {round(score, 2)})", reason))

        # ── reporting-manager set (for MANAGER role) ──
        rm_keys = {name_key(a['rm']) for a in active if a['rm']}

        self.stdout.write(f"Roster rows: {len(roster)}")
        self.stdout.write(f"Confident matches: {len(matched)}")
        self.stdout.write(f"Review/skip rows: {len(review)}")

        # write review csv
        review_path = opts['review_out']
        with open(review_path, 'w', newline='', encoding='utf-8') as fh:
            w = csv.writer(fh)
            w.writerow(['roster_name', 'email', 'best_guess', 'reason'])
            w.writerows(review)
        self.stdout.write(f"Review file written: {os.path.abspath(review_path)}")

        if not opts['commit']:
            self.stdout.write(self.style.WARNING('DRY RUN — no DB changes. Re-run with --commit to apply.'))
            self._preview(matched[:10])
            return

        created, skipped = self._import(matched, rm_keys, opts['password'], active)
        self.stdout.write(self.style.SUCCESS(f"Created {created} accounts, skipped {skipped} existing."))

    # ── matching helpers ──
    def _match(self, name, email, active):
        local = re.sub(r'[^a-z]', '', email.split('@')[0].lower())
        if not local:
            return None, 0
        initial, rest = local[0], local[1:]
        rname = set(tokens(name))
        best, bs = None, 0.0
        for d in active:
            dt = tokens(d['name'])
            tokmatch = max([difflib.SequenceMatcher(None, rest, t).ratio() for t in dt] + [0])
            initmatch = any(t[0] == initial for t in dt)
            overlap = len(rname & set(dt))
            if tokmatch >= 0.9 and initmatch:
                score = 0.95 + 0.01 * overlap
            elif tokmatch >= 0.85:
                score = 0.8
            elif overlap >= 2:
                score = 0.75
            else:
                score = 0.3 * overlap
            if score > bs:
                bs, best = score, d
        return best, bs

    def _exact_unique(self, name, active):
        k = name_key(name)
        hits = [d for d in active if name_key(d['name']) == k and d.get('doj')]
        return hits[0] if len(hits) == 1 else None

    def _preview(self, rows):
        for name, email, d in rows:
            self.stdout.write(f"  {email:35s} -> {d['jid']:8s} {d['name'][:30]:30s} {d['dept']}")

    # ── import ──
    @transaction.atomic
    def _import(self, matched, rm_keys, password, active):
        created = skipped = 0
        dept_cache, desig_cache = {}, {}

        def get_dept(nm):
            if not nm:
                return None
            if nm in dept_cache:
                return dept_cache[nm]
            existing = Department.objects.filter(name=nm).first()
            if existing:
                dept_cache[nm] = existing
                return existing
            base = re.sub(r'[^A-Z0-9]', '', nm.upper())[:16] or 'DEPT'
            code, i = base, 1
            while Department.objects.filter(code=code).exists():
                i += 1
                code = f"{base}{i}"[:20]
            dept_cache[nm] = Department.objects.create(name=nm, code=code)
            return dept_cache[nm]

        def get_desig(nm, dept):
            if not nm:
                return None
            key = (nm, dept.id if dept else None)
            if key not in desig_cache:
                desig_cache[key], _ = Designation.objects.get_or_create(name=nm, department=dept)
            return desig_cache[key]

        first_pass = []  # (emp, rm) for every matched row (created or pre-existing)
        for name, email, d in matched:
            emp = (Employee.objects.filter(employee_id=d['jid']).first()
                   or Employee.objects.filter(email=email).first())
            if emp:
                skipped += 1
                first_pass.append((emp, d['rm']))
                continue
            parts = name.split()
            first = parts[0]
            last = ' '.join(parts[1:]) if len(parts) > 1 else ''
            dept = get_dept(d['dept'])
            desig = get_desig(d['desig'], dept)

            user = User.objects.create_user(
                email=email, username=email, password=password,
                first_name=first, last_name=last, role='EMPLOYEE',
            )
            emp = Employee.objects.create(
                employee_id=d['jid'], user=user, first_name=first, last_name=last,
                email=email, department=dept, designation=desig,
                joining_date=d['doj'].date() if hasattr(d['doj'], 'date') else d['doj'],
                employment_status='ACTIVE',
            )
            first_pass.append((emp, d['rm']))
            created += 1

        # ── second pass: link managers by RM name (subset match, closest wins) ──
        all_emps = list(Employee.objects.select_related('user').all())
        for emp, rm in first_pass:
            if not rm:
                continue
            rset = set(tokens(rm))
            if not rset:
                continue
            # candidate = employee whose name tokens are a superset of the RM tokens
            candidates = [e for e in all_emps
                          if e.pk != emp.pk and rset <= set(tokens(f"{e.first_name} {e.last_name}"))]
            if not candidates:  # relax to any-overlap
                candidates = [e for e in all_emps
                              if e.pk != emp.pk and rset & set(tokens(f"{e.first_name} {e.last_name}"))]
            if candidates:
                best = min(candidates, key=lambda e: len(tokens(f"{e.first_name} {e.last_name}")))
                emp.manager = best
                emp.save(update_fields=['manager'])

        # ── third pass: role follows linkage — anyone who manages someone is MANAGER ──
        manager_ids = set(Employee.objects.exclude(manager=None).values_list('manager_id', flat=True))
        for emp, _ in first_pass:
            desired = 'MANAGER' if emp.pk in manager_ids else 'EMPLOYEE'
            if emp.user and emp.user.role != desired and emp.user.role in ('EMPLOYEE', 'MANAGER'):
                emp.user.role = desired
                emp.user.save(update_fields=['role'])
        return created, skipped
