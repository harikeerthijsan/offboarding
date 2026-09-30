"""Map hardware assets (laptops/desktops) from the GIS asset workbook onto
employees by JSANID.

Sheets used:
  - "GIS _Data"     : active employees' laptops  -> status ASSIGNED (RETURNED if the
                      employee is already EXITED)
  - "Exit Laptops " : exited employees' laptops  -> status RETURNED (working=GOOD)
  - "Desktops "     : unassigned desktop pool     -> assigned_to = None

asset_id is generated deterministically (idempotent). The raw Service Tag is kept
in serial_number. assigned_date is left blank (no assignment date in the source;
manual-date rule). Rows whose JSANID isn't in the DB are reported, not guessed.

Usage:
  python manage.py import_assets --file "C:/path/GIS system Laptops data (3).xlsx" [--commit]
"""
import re
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.employees.models import Employee
from apps.offboarding.models import Asset, AssetClearance, ResignationRequest

User = get_user_model()


def clean(v):
    return str(v).strip() if v is not None else ''


# raw substring -> display brand
_BRANDS = [('HP', 'HP'), ('DELL', 'Dell'), ('LENOVO', 'Lenovo'), ('ACER', 'Acer'),
           ('ASUS', 'Asus'), ('APPLE', 'Apple'), ('MAC', 'Apple'), ('MSI', 'MSI')]


def model_name(m, kind):
    raw = clean(m).upper()
    for key, disp in _BRANDS:
        if key in raw:
            return f"{disp} {kind}"
    return kind


class Command(BaseCommand):
    help = 'Import laptop/desktop assets and map them to employees by JSANID.'

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True)
        parser.add_argument('--commit', action='store_true')

    def handle(self, *args, **opts):
        try:
            import openpyxl
        except ImportError:
            raise CommandError('openpyxl required')
        wb = openpyxl.load_workbook(opts['file'], data_only=True)

        plan = []          # (asset_id, type, name, serial, config, jid, status, condition, remarks)
        unmatched = []     # (sheet, jid, name, serial)

        def emp_for(jid):
            return Employee.objects.filter(employee_id=jid).first() if jid else None

        # ── GIS _Data: active laptops ──
        seq = {}
        for row in wb['GIS _Data'].iter_rows(min_row=2, values_only=True):
            jid = clean(row[0]).upper()
            if not jid:
                continue
            serial = clean(row[5])
            config = clean(row[3])
            model = clean(row[6])
            seq[jid] = seq.get(jid, 0) + 1
            aid = f"LAP-{jid}-{seq[jid]}"
            emp = emp_for(jid)
            if not emp:
                unmatched.append(('GIS_Data', jid, clean(row[1]), serial))
                continue
            status = 'RETURNED' if emp.employment_status == 'EXITED' else 'ASSIGNED'
            plan.append(dict(asset_id=aid, atype='LAPTOP', name=model_name(model, 'Laptop'),
                             serial=serial, config=config, emp=emp, status=status,
                             condition='', remarks='Imported from GIS asset sheet.'))

        # ── Exit Laptops: exited employees' laptops (returned) ──
        xseq = {}
        for row in wb['Exit Laptops '].iter_rows(min_row=2, values_only=True):
            jid = clean(row[0]).upper()
            name = clean(row[1])
            if not jid:
                if name:
                    unmatched.append(('Exit Laptops', '(no EMP-ID)', name, clean(row[4])))
                continue
            serial = clean(row[4])
            config = clean(row[3])
            model = clean(row[5])
            working = 'work' in clean(row[7]).lower()
            xseq[jid] = xseq.get(jid, 0) + 1
            aid = f"LAP-{jid}-X{xseq[jid]}"
            emp = emp_for(jid)
            if not emp:
                unmatched.append(('Exit Laptops', jid, name, serial))
                continue
            plan.append(dict(asset_id=aid, atype='LAPTOP', name=model_name(model, 'Laptop'),
                             serial=serial, config=config, emp=emp, status='RETURNED',
                             condition='GOOD' if working else '',
                             remarks='Exited employee laptop (returned).'))

        # ── Desktops: unassigned pool ──
        for row in wb['Desktops '].iter_rows(min_row=2, values_only=True):
            aid = clean(row[1])
            if not aid:
                continue
            plan.append(dict(asset_id=aid, atype='DESKTOP', name=model_name(row[3], 'Desktop'),
                             serial=clean(row[2]), config=clean(row[0]), emp=None,
                             status='ASSIGNED', condition='', remarks='Unassigned desktop pool.'))

        self.stdout.write(f"Asset rows to import: {len(plan)}  (laptops+desktops)")
        self.stdout.write(f"  assigned to employees: {sum(1 for p in plan if p['emp'])}")
        self.stdout.write(f"  unassigned (desktops): {sum(1 for p in plan if not p['emp'])}")
        self.stdout.write(f"Unmatched rows (JSANID not in DB / no EMP-ID): {len(unmatched)}")
        for u in unmatched[:15]:
            self.stdout.write(f"    {u[0]}: {u[1]} {u[2]}  serial={u[3]}")

        if not opts['commit']:
            self.stdout.write(self.style.WARNING('DRY RUN — no DB changes. Re-run with --commit.'))
            for p in plan[:8]:
                who = p['emp'].employee_id if p['emp'] else 'UNASSIGNED'
                self.stdout.write(f"    {p['asset_id']:16s} {p['atype']:7s} {p['name']:14s} "
                                  f"serial={p['serial'][:18]:18s} -> {who} [{p['status']}]")
            return

        created, skipped, cleared = self._commit(plan)
        self.stdout.write(self.style.SUCCESS(
            f"Created {created} assets, skipped {skipped} existing, "
            f"created {cleared} asset-clearance records for exited employees."))

    @transaction.atomic
    def _commit(self, plan):
        created = skipped = 0
        for p in plan:
            if Asset.objects.filter(asset_id=p['asset_id']).exists():
                skipped += 1
                continue
            Asset.objects.create(
                asset_id=p['asset_id'], asset_type=p['atype'], asset_name=p['name'],
                serial_number=p['serial'][:120], description=p['config'],
                assigned_to=p['emp'], status=p['status'], condition=p['condition'],
                remarks=p['remarks'],
            )
            created += 1
        cleared = self._clear_exited_assets()
        return created, skipped, cleared

    def _clear_exited_assets(self):
        """For every asset held by an EXITED employee, record a CLEARED asset
        clearance against their offboarding and mark the asset CLEARED."""
        hr = User.objects.filter(role__in=['HR', 'ADMIN'], is_active=True).order_by('role').first()
        now = timezone.now()
        cleared = 0
        assets = Asset.objects.select_related('assigned_to').filter(
            assigned_to__employment_status='EXITED')
        for asset in assets:
            emp = asset.assigned_to
            res = ResignationRequest.objects.filter(employee=emp).order_by('-created_at').first()
            if not res:
                continue
            ac, made = AssetClearance.objects.get_or_create(
                offboarding_request=res, asset=asset,
                defaults=dict(
                    employee=emp, status='CLEARED',
                    return_date=res.last_working_date,   # = DOE (manual, stored)
                    condition_at_return=asset.condition or 'GOOD',
                    remarks='Historical import — returned & cleared on exit.',
                    verified_by=hr, verified_at=now,
                ),
            )
            if made:
                cleared += 1
            if asset.status != 'CLEARED':
                asset.status = 'CLEARED'
                asset.save(update_fields=['status', 'updated_at'])
        return cleared
