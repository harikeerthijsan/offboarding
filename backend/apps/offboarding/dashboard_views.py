"""Aggregated dashboard overview — one efficient endpoint powering the whole
dashboard (stat tiles, pipeline, status donut, department overview, recent
activity, upcoming tasks, 6-month trends)."""
import datetime

from django.db.models import Q, Count
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.employees.models import Employee, Department
from apps.audit.models import AuditLog

from .models import ResignationRequest
from .final_review_views import _one2one, pending_items

_ACTIVE = ['APPROVED', 'NOTICE_PERIOD', 'COMPLETED']


def _month_starts(n):
    """Return list of (year, month, label) for the last n months incl. current."""
    today = timezone.now().date()
    out = []
    y, m = today.year, today.month
    for _ in range(n):
        out.append((y, m, datetime.date(y, m, 1).strftime('%b %Y')))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(out))


def _range(y, m):
    start = datetime.date(y, m, 1)
    end = datetime.date(y + 1, 1, 1) if m == 12 else datetime.date(y, m + 1, 1)
    return start, end


def _pct(cur, prev):
    if prev == 0:
        return 100 if cur else 0
    return round((cur - prev) / prev * 100)


def _count_in_month(qs, field, y, m):
    start, end = _range(y, m)
    return qs.filter(**{f'{field}__gte': start, f'{field}__lt': end}).count()


class DashboardOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        emp = Employee.objects.all()
        total = emp.count()
        active = emp.filter(employment_status='ACTIVE').count()
        offb = emp.filter(employment_status='OFFBOARDING').count()
        exited = emp.filter(employment_status='EXITED').count()
        dept_count = Department.objects.count()

        # trend vs last month (uses business dates, never invented)
        cur = _month_starts(2)[-1]
        prev = _month_starts(2)[0]
        hires_cur = _count_in_month(emp, 'joining_date', cur[0], cur[1])
        hires_prev = _count_in_month(emp, 'joining_date', prev[0], prev[1])
        exit_qs = ResignationRequest.objects.filter(status='COMPLETED')
        exit_cur = _count_in_month(exit_qs, 'last_working_date', cur[0], cur[1])
        exit_prev = _count_in_month(exit_qs, 'last_working_date', prev[0], prev[1])
        res_qs = ResignationRequest.objects.exclude(status__in=['DRAFT', 'REJECTED', 'CANCELLED'])
        res_cur = _count_in_month(res_qs, 'resignation_date', cur[0], cur[1])
        res_prev = _count_in_month(res_qs, 'resignation_date', prev[0], prev[1])

        stats = {
            'total_employees': {'value': total, 'trend': _pct(hires_cur, hires_prev)},
            'active': {'value': active, 'trend': _pct(hires_cur, hires_prev)},
            'offboarding': {'value': offb, 'trend': _pct(res_cur, res_prev)},
            'exited': {'value': exited, 'trend': _pct(exit_cur, exit_prev)},
            'departments': {'value': dept_count, 'trend': 0},
        }

        # ── pipeline ──
        RR = ResignationRequest.objects
        base = RR.exclude(status__in=['DRAFT', 'REJECTED', 'CANCELLED'])
        act = base.filter(status__in=_ACTIVE)
        pipeline = {
            'resignation': RR.filter(status__in=['SUBMITTED', 'MANAGER_REVIEW', 'HR_REVIEW']).count(),
            'notice': base.filter(status='NOTICE_PERIOD').count(),
            'kt': act.filter(kt_items__isnull=False, kt_completed_at__isnull=True).distinct().count(),
            'clearance': act.filter(kt_completed_at__isnull=False, clearance_completed_at__isnull=True).count(),
            'settlement': act.filter(clearance_completed_at__isnull=False).exclude(
                final_settlement__settlement_status='APPROVED').count(),
            'exit_interview': act.filter(
                clearance_completed_at__isnull=False,
                final_settlement__settlement_status='APPROVED',
            ).exclude(exit_interview__status__in=['COMPLETED', 'REVIEWED']).count(),
            'final_review': base.filter(final_review_status__in=['READY_FOR_REVIEW', 'UNDER_REVIEW']).count(),
            'completed': base.filter(final_review_status='APPROVED').count() or base.filter(status='COMPLETED').count(),
        }

        # ── status donut ──
        total_cases = base.count()
        completed = base.filter(Q(status='COMPLETED') | Q(final_review_status='APPROVED')).distinct().count()
        rejected = RR.filter(status='REJECTED').count()
        in_progress = base.filter(Q(status='NOTICE_PERIOD') | Q(final_review_status='UNDER_REVIEW')).exclude(
            status='COMPLETED').distinct().count()
        pending = max(total_cases - completed - in_progress, 0)

        def _p(v):
            return round(v / total_cases * 100, 1) if total_cases else 0
        status = {
            'total': total_cases,
            'completed': completed, 'completed_pct': _p(completed),
            'in_progress': in_progress, 'in_progress_pct': _p(in_progress),
            'pending': pending, 'pending_pct': _p(pending),
            'rejected': rejected, 'rejected_pct': _p(rejected),
        }

        # ── department overview (top by employee count) ──
        dept_rows = (Department.objects.annotate(n=Count('employees'))
                     .values('name', 'n').order_by('-n')[:8])
        departments = [{'name': d['name'], 'count': d['n']} for d in dept_rows]

        # ── recent activity (audit) ──
        cat_map = {
            'RESIGNATION': 'resignation', 'MANAGER': 'resignation', 'HR': 'resignation',
            'NOTICE': 'notice', 'KT': 'kt', 'ASSET': 'asset', 'CLEARANCE': 'clearance',
            'DEPARTMENT_CLEARANCE': 'clearance', 'SETTLEMENT': 'settlement',
            'EXIT_INTERVIEW': 'exit', 'FINAL': 'final', 'DOCUMENT': 'document',
        }

        def _cat(action):
            for k, v in cat_map.items():
                if action.startswith(k):
                    return v
            return 'other'
        recent = []
        for a in AuditLog.objects.select_related('actor')[:6]:
            recent.append({
                'action': a.action,
                'label': a.action.replace('_', ' ').title(),
                'target': a.target_repr,
                'when': a.timestamp,
                'category': _cat(a.action),
            })

        # ── recent exits (recently exited employees) ──
        recent_exits = []
        for r in (ResignationRequest.objects
                  .filter(status='COMPLETED', last_working_date__isnull=False)
                  .select_related('employee__department')
                  .order_by('-last_working_date')[:6]):
            e = r.employee
            recent_exits.append({
                'name': f"{e.first_name} {e.last_name}",
                'employee_id': e.employee_id,
                'department': e.department.name if e.department else '',
                'date': r.last_working_date,
            })

        # ── upcoming tasks (derived from actionable offboardings) ──
        tasks = []
        for r in act.select_related('employee').order_by('-created_at')[:20]:
            pend = pending_items(r)
            if not pend:
                continue
            first = pend[0]
            priority = 'HIGH' if first in ('Final Settlement', 'Department & Asset Clearance') else \
                'MEDIUM' if first in ('Notice Period', 'Knowledge Transfer') else 'LOW'
            np = _one2one(r, 'notice_period')
            due = np.expected_last_working_day if np else None
            tasks.append({
                'title': first,
                'subtitle': f"{r.employee.employee_id} · {r.employee.first_name} {r.employee.last_name}",
                'due': due,
                'priority': priority,
            })
            if len(tasks) >= 6:
                break

        # ── 6-month trends ──
        months = _month_starts(6)
        labels, new_c, comp_c, pend_c = [], [], [], []
        for (y, m, lbl) in months:
            labels.append(lbl)
            nc = _count_in_month(res_qs, 'resignation_date', y, m)
            cc = _count_in_month(exit_qs, 'last_working_date', y, m)
            new_c.append(nc)
            comp_c.append(cc)
            pend_c.append(max(nc - cc, 0))
        trends = {'labels': labels, 'new': new_c, 'completed': comp_c, 'pending': pend_c}

        return Response({
            'stats': stats, 'pipeline': pipeline, 'status': status,
            'departments': departments, 'recent_activity': recent,
            'recent_exits': recent_exits,
            'upcoming_tasks': tasks, 'trends': trends,
        })
