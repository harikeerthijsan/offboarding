"""Set each employee's reporting manager from the HR reference workbook.

Mapping baked from "List of active & exit Employees" (Active sheet, RM column).
Idempotent and argument-free so it runs cleanly over `railway ssh`:

  python manage.py map_reporting_managers
  python manage.py map_reporting_managers --dry-run

Not mapped (left unchanged):
  * JSAN007, JSAN202, JSAN246 — report to "Navin", who has no employee record.
  * Employees absent from the Active sheet (no RM in the reference).
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.employees.models import Employee

# employee_id -> reporting-manager employee_id
MAPPING = {
    'JSAN002': 'JSAN274', 'JSAN005': 'JSAN274', 'JSAN010': 'JSAN015', 'JSAN015': 'JSAN005',
    'JSAN022': 'JSAN083', 'JSAN026': 'JSAN274', 'JSAN031': 'JSAN002', 'JSAN049': 'JSAN026',
    'JSAN051': 'JSAN083', 'JSAN063': 'JSAN083', 'JSAN079': 'JSAN005', 'JSAN083': 'JSAN005',
    'JSAN098': 'JSAN026', 'JSAN107': 'JSAN005', 'JSAN124': 'JSAN015', 'JSAN167': 'JSAN178',
    'JSAN178': 'JSAN005', 'JSAN188': 'JSAN079', 'JSAN194': 'JSAN002', 'JSAN203': 'JSAN026',
    'JSAN204': 'JSAN015', 'JSAN205': 'JSAN002', 'JSAN210': 'JSAN005', 'JSAN220': 'JSAN293',
    'JSAN224': 'JSAN026', 'JSAN230': 'JSAN259', 'JSAN231': 'JSAN015', 'JSAN232': 'JSAN015',
    'JSAN234': 'JSAN293', 'JSAN235': 'JSAN350', 'JSAN237': 'JSAN026', 'JSAN238': 'JSAN252',
    'JSAN241': 'JSAN079', 'JSAN242': 'JSAN026', 'JSAN243': 'JSAN350', 'JSAN245': 'JSAN005',
    'JSAN249': 'JSAN252', 'JSAN250': 'JSAN369', 'JSAN251': 'JSAN252', 'JSAN252': 'JSAN274',
    'JSAN253': 'JSAN079', 'JSAN254': 'JSAN252', 'JSAN255': 'JSAN293', 'JSAN256': 'JSAN026',
    'JSAN257': 'JSAN178', 'JSAN259': 'JSAN252', 'JSAN261': 'JSAN252', 'JSAN262': 'JSAN178',
    'JSAN265': 'JSAN348', 'JSAN266': 'JSAN238', 'JSAN267': 'JSAN348', 'JSAN268': 'JSAN349',
    'JSAN269': 'JSAN255', 'JSAN271': 'JSAN026', 'JSAN272': 'JSAN245', 'JSAN274': 'JSAN026',
    'JSAN277': 'JSAN350', 'JSAN278': 'JSAN026', 'JSAN280': 'JSAN238', 'JSAN286': 'JSAN202',
    'JSAN287': 'JSAN317', 'JSAN290': 'JSAN332', 'JSAN291': 'JSAN252', 'JSAN293': 'JSAN252',
    'JSAN295': 'JSAN252', 'JSAN296': 'JSAN252', 'JSAN298': 'JSAN348', 'JSAN299': 'JSAN252',
    'JSAN300': 'JSAN252', 'JSAN301': 'JSAN252', 'JSAN302': 'JSAN178', 'JSAN303': 'JSAN026',
    'JSAN305': 'JSAN026', 'JSAN306': 'JSAN378', 'JSAN307': 'JSAN378', 'JSAN308': 'JSAN378',
    'JSAN309': 'JSAN378', 'JSAN310': 'JSAN378', 'JSAN311': 'JSAN378', 'JSAN312': 'JSAN378',
    'JSAN313': 'JSAN378', 'JSAN314': 'JSAN378', 'JSAN315': 'JSAN378', 'JSAN316': 'JSAN255',
    'JSAN317': 'JSAN252', 'JSAN318': 'JSAN252', 'JSAN319': 'JSAN202', 'JSAN321': 'JSAN274',
    'JSAN322': 'JSAN296', 'JSAN324': 'JSAN252', 'JSAN326': 'JSAN350', 'JSAN329': 'JSAN259',
    'JSAN332': 'JSAN252', 'JSAN333': 'JSAN079', 'JSAN334': 'JSAN252', 'JSAN335': 'JSAN350',
    'JSAN336': 'JSAN350', 'JSAN337': 'JSAN317', 'JSAN338': 'JSAN349', 'JSAN339': 'JSAN252',
    'JSAN340': 'JSAN350', 'JSAN341': 'JSAN350', 'JSAN342': 'JSAN291', 'JSAN343': 'JSAN349',
    'JSAN344': 'JSAN293', 'JSAN345': 'JSAN317', 'JSAN346': 'JSAN291', 'JSAN347': 'JSAN348',
    'JSAN348': 'JSAN252', 'JSAN349': 'JSAN348', 'JSAN350': 'JSAN252', 'JSAN351': 'JSAN348',
    'JSAN352': 'JSAN348', 'JSAN353': 'JSAN178', 'JSAN354': 'JSAN369', 'JSAN355': 'JSAN255',
    'JSAN356': 'JSAN015', 'JSAN357': 'JSAN349', 'JSAN358': 'JSAN224', 'JSAN359': 'JSAN252',
    'JSAN360': 'JSAN252', 'JSAN361': 'JSAN005', 'JSAN362': 'JSAN349', 'JSAN363': 'JSAN079',
    'JSAN364': 'JSAN252', 'JSAN365': 'JSAN252', 'JSAN366': 'JSAN291', 'JSAN367': 'JSAN349',
    'JSAN368': 'JSAN245', 'JSAN369': 'JSAN274', 'JSAN370': 'JSAN349', 'JSAN371': 'JSAN349',
    'JSAN372': 'JSAN348', 'JSAN373': 'JSAN369', 'JSAN374': 'JSAN005', 'JSAN375': 'JSAN361',
    'JSAN376': 'JSAN349', 'JSAN377': 'JSAN252', 'JSAN378': 'JSAN349', 'JSAN379': 'JSAN349',
    'JSAN380': 'JSAN291', 'JSAN381': 'JSAN259', 'JSAN382': 'JSAN349', 'JSAN383': 'JSAN349',
    'JSAN384': 'JSAN349', 'JSAN385': 'JSAN349', 'JSAN386': 'JSAN349', 'JSAN387': 'JSAN349',
    'JSAN388': 'JSAN349', 'JSAN389': 'JSAN349', 'JSAN390': 'JSAN349', 'JSAN391': 'JSAN349',
    'JSAN392': 'JSAN349', 'JSAN393': 'JSAN349', 'JSAN394': 'JSAN349', 'JSAN395': 'JSAN349',
    'JSAN396': 'JSAN349', 'JSAN397': 'JSAN349', 'JSAN398': 'JSAN349', 'JSAN399': 'JSAN349',
    'JSAN400': 'JSAN349', 'JSAN401': 'JSAN349', 'JSAN402': 'JSAN349', 'JSAN403': 'JSAN349',
    'JSAN404': 'JSAN349', 'JSAN405': 'JSAN349', 'JSAN406': 'JSAN349',
}


class Command(BaseCommand):
    help = "Assign reporting managers from the HR reference workbook (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report without writing.')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        by_id = {e.employee_id.upper(): e for e in Employee.objects.select_related('manager').all()}
        changed = unchanged = self_ref = 0
        missing_emp, missing_mgr, changes = [], [], []

        with transaction.atomic():
            for emp_id, mgr_id in MAPPING.items():
                emp, mgr = by_id.get(emp_id), by_id.get(mgr_id)
                if not emp:
                    missing_emp.append(emp_id); continue
                if not mgr:
                    missing_mgr.append((emp_id, mgr_id)); continue
                if emp.pk == mgr.pk:
                    self_ref += 1; continue
                if emp.manager_id == mgr.pk:
                    unchanged += 1; continue
                old = emp.manager.employee_id if emp.manager else '(none)'
                changes.append(f'{emp_id}: {old} -> {mgr_id}')
                if not dry:
                    emp.manager = mgr
                    emp.save(update_fields=['manager', 'updated_at'])
                changed += 1
            if dry:
                transaction.set_rollback(True)

        for c in changes:
            self.stdout.write(c)
        if missing_emp:
            self.stdout.write(self.style.WARNING(f'Employees not found: {", ".join(missing_emp)}'))
        if missing_mgr:
            self.stdout.write(self.style.WARNING(
                'Managers not found: ' + ', '.join(f'{e}->{m}' for e, m in missing_mgr)))
        verb = 'Would change' if dry else 'Changed'
        self.stdout.write(self.style.SUCCESS(
            f'{verb} {changed}; already-correct {unchanged}; self-ref skipped {self_ref}. '
            f'(JSAN007/202/246 report to "Navin" — not in the system — and stay unset.)'))
