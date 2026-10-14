"""Skills Hub API — Phase 1 core endpoints.

Role mapping from the source app's 3 roles to ours:
  employee actions  -> any authenticated user
  staff actions     -> MANAGER / HR / ADMIN (view team, export, manage catalogue & cycles)
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.employees.models import Employee
from apps.notifications.models import Notification
from apps.notifications.emails import send_notification_email
from django.conf import settings

User = get_user_model()

from .cycles import active_cycle, cycles_for, compliance_of
from .export import build_workbook
from .import_calendar import import_calendar
from .models import SkillDefinition, ReviewCycle, SkillSubmission, SUBMISSION_STATUS
from .serializers import (
    SkillDefinitionSerializer, ReviewCycleSerializer, SkillSubmissionSerializer,
    clean_skills, _list_field,
)

STAFF_ROLES = ('MANAGER', 'HR', 'ADMIN')
DEFAULT_ROLES = ['Trainee GIS', 'GIS Analyst', 'Telecom Operator', 'Designer',
                 'QC Analyst', 'Team Lead', 'Project Lead', 'Project Manager']


class IsSkillsStaff(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in STAFF_ROLES


def _employee_of(user):
    return Employee.objects.filter(user=user).select_related('department', 'designation').first()


def _profile_complete(user):
    e = _employee_of(user)
    return bool(e and e.department_id and e.designation_id)


# ─── Approval routing ────────────────────────────────────────────────────────

def _manager_user_of(employee):
    """The reporting manager's login account, or None."""
    if not employee or not employee.manager_id:
        return None
    mgr = Employee.objects.filter(pk=employee.manager_id).select_related('user').first()
    return mgr.user if (mgr and mgr.user_id) else None


def _hr_admin_users():
    return list(User.objects.filter(role__in=('HR', 'ADMIN')))


def _approvers_for(employee):
    """Who reviews this employee's submission: the reporting manager if set,
    otherwise HR/Admin (the no-manager fallback)."""
    mgr = _manager_user_of(employee)
    return [mgr] if mgr else _hr_admin_users()


def _can_review(submission, user):
    """A reviewer is the submitter's reporting manager, or any HR/Admin."""
    if user.role in ('HR', 'ADMIN'):
        return True
    emp = _employee_of(submission.user)
    reviewer = _employee_of(user)
    return bool(emp and reviewer and emp.manager_id == reviewer.pk)


def _notify_skill(recipient, ntype, title, message, submission, path):
    if not recipient:
        return
    Notification.objects.create(
        recipient=recipient,
        notification_type=ntype,
        title=title,
        message=message,
        related_object_type='SkillSubmission',
        related_object_id=submission.pk,
    )
    link = f"{settings.FRONTEND_URL}{path}" if getattr(settings, 'FRONTEND_URL', '') else None
    send_notification_email(recipient, title, message, link=link)


# ─── My skills: cycles + submissions ─────────────────────────────────────────

class MySkillsView(APIView):
    """GET /api/skills/me/ — my review timeline + my submissions + profile status."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        subs = list(SkillSubmission.objects.filter(user=request.user).select_related('cycle', 'reviewed_by'))
        cycle_docs = list(ReviewCycle.objects.all())
        by_id = {s.cycle.cycle_id: s.status for s in subs}
        return Response({
            'profile_complete': _profile_complete(request.user),
            'cycles': cycles_for(cycle_docs, by_id),
            'submissions': SkillSubmissionSerializer(subs, many=True).data,
        })


class MySubmissionsView(APIView):
    """GET  /api/skills/submissions/  — my submissions.
       POST /api/skills/submissions/  — save draft / submit for the active cycle."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        subs = SkillSubmission.objects.filter(user=request.user).select_related('cycle', 'reviewed_by')
        return Response({'submissions': SkillSubmissionSerializer(subs, many=True).data})

    def post(self, request):
        if not _profile_complete(request.user):
            return Response(
                {'detail': 'Complete your profile (department and designation) first.'},
                status=status.HTTP_412_PRECONDITION_FAILED,
            )
        cycle = active_cycle(list(ReviewCycle.objects.all()))
        if not cycle:
            return Response({'detail': 'No review cycle is configured yet. Ask HR.'},
                            status=status.HTTP_412_PRECONDITION_FAILED)

        body = request.data
        req_cycle = body.get('cycle_id') or body.get('cycleId')
        if req_cycle and req_cycle != cycle.cycle_id:
            return Response({'detail': f'Only the {cycle.cycle_id} review is open for changes.'},
                            status=status.HTTP_400_BAD_REQUEST)

        skills = clean_skills(body.get('skills'))
        submit = bool(body.get('submit'))
        if submit and not skills:
            return Response({'detail': 'Add at least one skill before submitting.'},
                            status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            sub, _ = SkillSubmission.objects.select_for_update().get_or_create(
                user=request.user, cycle=cycle,
            )
            sub.skills = skills
            sub.employee_note = str(body.get('employee_note') or body.get('employeeNote') or '')[:1000]
            sub.due_date = cycle.employee_due
            sub.status = 'submitted' if submit else 'draft'
            sub.submitted_at = timezone.now() if submit else None
            sub.reviewed_by = None
            sub.reviewed_at = None
            sub.review_note = ''
            sub.source = 'portal'
            sub.save()

        if submit:
            emp = _employee_of(request.user)
            name = (f"{request.user.first_name} {request.user.last_name}".strip()
                    or request.user.username)
            title = 'Skills submitted for approval'
            msg = (f"{name} submitted their skill matrix for {cycle.cycle_id} "
                   f"and it is awaiting your approval.")
            for approver in _approvers_for(emp):
                if approver and approver.pk != request.user.pk:
                    _notify_skill(approver, 'SKILLS_SUBMITTED', title, msg, sub, '/skills/approvals')

        return Response({'submission': SkillSubmissionSerializer(sub).data})


# ─── Picker data (catalogue + known companies/roles) ─────────────────────────

class SkillsPickerView(APIView):
    """GET /api/skills/picker/ — active catalogue + known companies/roles for autocomplete."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        skills = SkillDefinition.objects.filter(active=True)
        used_companies = {str(c).strip() for s in SkillSubmission.objects.values_list('skills', flat=True)
                          for c in ([x.get('company') for x in (s or [])])}
        used_roles = {str(r).strip() for s in SkillSubmission.objects.values_list('skills', flat=True)
                      for r in ([x.get('role') for x in (s or [])])}
        designations = set(Employee.objects.exclude(designation=None)
                           .values_list('designation__name', flat=True))

        def clean(xs):
            m = {}
            for x in xs:
                x = str(x or '').strip()
                if x and not all(ch.isdigit() or ch in '. ' for ch in x):
                    m.setdefault(x.lower(), x)
            return sorted(m.values(), key=lambda v: v.lower())

        companies = clean(['JSAN', *used_companies])
        roles = clean([*DEFAULT_ROLES, *designations, *used_roles])
        return Response({
            'skills': SkillDefinitionSerializer(skills, many=True).data,
            'companies': companies,
            'roles': roles,
        })


# ─── Review calendar ─────────────────────────────────────────────────────────

class CyclesView(APIView):
    """GET  /api/skills/cycles/ — company calendar; staff also get per-cycle counts.
       POST /api/skills/cycles/ — create a review cycle (staff)."""
    def get_permissions(self):
        return [IsSkillsStaff()] if self.request.method == 'POST' else [IsAuthenticated()]

    def post(self, request):
        ser = ReviewCycleSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        cycle = ser.save()
        return Response(ReviewCycleSerializer(cycle).data, status=status.HTTP_201_CREATED)

    def get(self, request):
        docs = list(ReviewCycle.objects.all())
        rows = cycles_for(docs, {})
        is_staff = request.user.role in STAFF_ROLES
        if is_staff:
            headcount = Employee.objects.filter(employment_status='ACTIVE').count()
            subs = list(SkillSubmission.objects.values_list('cycle__cycle_id', 'status'))
            for r in rows:
                mine = [st for (cid, st) in subs if cid == r['cycle_id']]
                r['counts'] = {
                    'headcount': headcount,
                    'draft': mine.count('draft'),
                    'submitted': mine.count('submitted'),
                    'approved': mine.count('approved'),
                    'rejected': mine.count('rejected'),
                }
        return Response({'cycles': rows})


# ─── Catalogue management (staff) ────────────────────────────────────────────

class CatalogueView(APIView):
    """GET  /api/skills/catalogue/  — list (active-only for employees, all for staff).
       POST /api/skills/catalogue/  — add a catalogue skill (staff)."""
    def get_permissions(self):
        return [IsSkillsStaff()] if self.request.method == 'POST' else [IsAuthenticated()]

    def get(self, request):
        qs = SkillDefinition.objects.all()
        if request.user.role not in STAFF_ROLES:
            qs = qs.filter(active=True)
        return Response({'skills': SkillDefinitionSerializer(qs, many=True).data})

    def post(self, request):
        name = ' '.join(str(request.data.get('name') or '').split())[:80]
        if not name:
            return Response({'detail': 'Skill name is required.'}, status=status.HTTP_400_BAD_REQUEST)
        if SkillDefinition.objects.filter(name__iexact=name).exists():
            return Response({'detail': 'That skill already exists.'}, status=status.HTTP_409_CONFLICT)
        skill = SkillDefinition.objects.create(
            name=name,
            tools=_list_field(request.data.get('tools')),
            customers=_list_field(request.data.get('customers')),
        )
        return Response({'skill': SkillDefinitionSerializer(skill).data}, status=status.HTTP_201_CREATED)


class CatalogueDetailView(APIView):
    """PATCH/DELETE /api/skills/catalogue/{pk}/ — edit / remove (staff)."""
    permission_classes = [IsSkillsStaff]

    def patch(self, request, pk):
        try:
            skill = SkillDefinition.objects.get(pk=pk)
        except SkillDefinition.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if 'name' in request.data:
            skill.name = ' '.join(str(request.data['name']).split())[:80]
        if 'tools' in request.data:
            skill.tools = _list_field(request.data['tools'])
        if 'customers' in request.data:
            skill.customers = _list_field(request.data['customers'])
        if 'active' in request.data:
            skill.active = request.data['active'] in (True, 'true', 'True', 1, '1')
        skill.save()
        return Response({'skill': SkillDefinitionSerializer(skill).data})

    def delete(self, request, pk):
        SkillDefinition.objects.filter(pk=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─── Team directory (staff) ──────────────────────────────────────────────────

class TeamView(APIView):
    """GET /api/skills/team/ — staff directory with each person's active-cycle compliance."""
    permission_classes = [IsSkillsStaff]

    def get(self, request):
        cycle_docs = list(ReviewCycle.objects.all())
        subs = list(SkillSubmission.objects.values_list('user_id', 'cycle__cycle_id', 'status'))
        by_user = {}
        for uid, cid, st in subs:
            by_user.setdefault(uid, {})[cid] = st

        rows = []
        emps = Employee.objects.select_related('user', 'department', 'designation').all()
        for e in emps:
            if not e.user_id:
                continue
            compliance = compliance_of(cycle_docs, by_user.get(e.user_id, {}))
            rows.append({
                'employee_id': e.employee_id,
                'name': f"{e.first_name} {e.last_name}".strip(),
                'department': e.department.name if e.department else '',
                'designation': e.designation.name if e.designation else '',
                'employment_status': e.employment_status,
                'compliance': compliance,
                'user_id': e.user_id,
            })
        return Response({'team': rows})


class CycleDetailView(APIView):
    """PATCH/DELETE /api/skills/cycles/{pk}/ — edit / remove a review cycle (staff)."""
    permission_classes = [IsSkillsStaff]

    def patch(self, request, pk):
        try:
            cycle = ReviewCycle.objects.get(pk=pk)
        except ReviewCycle.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        ser = ReviewCycleSerializer(cycle, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)

    def delete(self, request, pk):
        ReviewCycle.objects.filter(pk=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CalendarImportView(APIView):
    """POST /api/skills/cycles/import/ — upload a review-calendar CSV/XLSX (staff).
    Upserts cycles by Cycle ID; returns {imported, skipped[]}."""
    permission_classes = [IsSkillsStaff]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        f = request.FILES.get('file')
        if not f:
            return Response({'detail': 'Please choose a file to upload.'}, status=status.HTTP_400_BAD_REQUEST)
        if f.size > 5 * 1024 * 1024:
            return Response({'detail': 'File is too large (max 5 MB).'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = import_calendar(f.name, f.read())
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:  # noqa: BLE001
            return Response({'detail': 'Could not read the file. Please check the format.'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response(result)


class StaffSubmissionsView(APIView):
    """GET /api/skills/submissions/all/ — staff submission list.
    Filters: ?status=submitted|approved|rejected|draft|all  &cycle=2027-H1"""
    permission_classes = [IsSkillsStaff]

    def get(self, request):
        raw = request.query_params.get('status', 'all')
        valid = {s for s, _ in SUBMISSION_STATUS}
        qs = SkillSubmission.objects.select_related('user', 'cycle', 'reviewed_by')
        if raw != 'all':
            if raw not in valid:
                return Response({'detail': 'Invalid status.'}, status=status.HTTP_400_BAD_REQUEST)
            qs = qs.filter(status=raw)
        cycle = request.query_params.get('cycle')
        if cycle:
            qs = qs.filter(cycle__cycle_id=cycle)
        qs = qs.order_by('-submitted_at', '-updated_at')
        return Response({'submissions': SkillSubmissionSerializer(qs, many=True).data})


class ApprovalsView(APIView):
    """GET /api/skills/approvals/ — submissions awaiting the current reviewer.
    Managers see their direct reports; HR/Admin also see employees with no
    reporting manager (the no-manager fallback)."""
    permission_classes = [IsSkillsStaff]

    def get(self, request):
        reviewer_emp = _employee_of(request.user)
        is_hr = request.user.role in ('HR', 'ADMIN')
        emp_by_user = {
            e.user_id: e for e in
            Employee.objects.exclude(user=None).select_related('department', 'designation')
        }
        subs = (SkillSubmission.objects.filter(status='submitted')
                .select_related('user', 'cycle', 'reviewed_by')
                .order_by('-submitted_at', '-updated_at'))
        rows = []
        for s in subs:
            emp = emp_by_user.get(s.user_id)
            is_my_report = bool(emp and reviewer_emp and emp.manager_id == reviewer_emp.pk)
            is_routed_to_hr = is_hr and (emp is None or not emp.manager_id)
            if not (is_my_report or is_routed_to_hr):
                continue
            data = SkillSubmissionSerializer(s).data
            data['employee_id'] = emp.employee_id if emp else ''
            data['department'] = emp.department.name if (emp and emp.department) else ''
            data['designation'] = emp.designation.name if (emp and emp.designation) else ''
            rows.append(data)
        return Response({'approvals': rows})


class SubmissionReviewView(APIView):
    """POST /api/skills/submissions/<pk>/review/ — approve or request an update.
    Body: {action: 'approve'|'reject', note?}. Reviewer = reporting manager or HR/Admin."""
    permission_classes = [IsSkillsStaff]

    def post(self, request, pk):
        try:
            sub = SkillSubmission.objects.select_related('user', 'cycle').get(pk=pk)
        except SkillSubmission.DoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        if not _can_review(sub, request.user):
            return Response({'detail': 'You are not the reviewer for this submission.'},
                            status=status.HTTP_403_FORBIDDEN)

        action = str(request.data.get('action') or '').lower()
        note = str(request.data.get('note') or '')[:1000]
        if action not in ('approve', 'reject'):
            return Response({'detail': 'action must be "approve" or "reject".'},
                            status=status.HTTP_400_BAD_REQUEST)
        if action == 'reject' and not note.strip():
            return Response({'detail': 'Please add a note explaining what to update.'},
                            status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            sub = SkillSubmission.objects.select_for_update().select_related('user', 'cycle').get(pk=pk)
            if sub.status != 'submitted':
                return Response({'detail': 'Only submitted skills can be reviewed.'},
                                status=status.HTTP_400_BAD_REQUEST)
            sub.status = 'approved' if action == 'approve' else 'rejected'
            sub.reviewed_by = request.user
            sub.reviewed_at = timezone.now()
            sub.review_note = note
            sub.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_note', 'updated_at'])

        reviewer = (f"{request.user.first_name} {request.user.last_name}".strip()
                    or request.user.username)
        if action == 'approve':
            _notify_skill(sub.user, 'SKILLS_APPROVED', 'Skills approved',
                          f"{reviewer} approved your {sub.cycle.cycle_id} skill matrix.",
                          sub, '/skills')
        else:
            _notify_skill(sub.user, 'SKILLS_CHANGES_REQUESTED', 'Skills need an update',
                          f"{reviewer} asked you to update your {sub.cycle.cycle_id} skills: {note}",
                          sub, '/skills')
        return Response({'submission': SkillSubmissionSerializer(sub).data})


class ExportView(APIView):
    """GET /api/skills/export/ — download the JSAN/QF/09 skill-matrix workbook (staff).
    ?status=all|submitted|... &cycle=2027-H1 . 'all' lists every employee (blanks
    show who hasn't submitted); a status filters to matching people only."""
    permission_classes = [IsSkillsStaff]

    def get(self, request):
        raw = request.query_params.get('status', 'all')
        valid = {s for s, _ in SUBMISSION_STATUS}
        sub_qs = SkillSubmission.objects.select_related('cycle')
        if raw != 'all':
            if raw not in valid:
                return Response({'detail': 'Invalid status.'}, status=status.HTTP_400_BAD_REQUEST)
            sub_qs = sub_qs.filter(status=raw)
        cycle = request.query_params.get('cycle')
        if cycle:
            sub_qs = sub_qs.filter(cycle__cycle_id=cycle)

        # Latest matching submission per user.
        latest = {}
        for s in sub_qs.order_by('updated_at'):
            latest[s.user_id] = {
                'cycle_id': s.cycle.cycle_id,
                'status': s.status,
                'skills': s.skills or [],
                'employee_note': s.employee_note,
                'submitted_at': (s.submitted_at.strftime('%Y-%m-%d %H:%M')
                                 if s.submitted_at else ''),
            }

        people = (Employee.objects
                  .select_related('department', 'designation')
                  .exclude(user__isnull=True)
                  .order_by('first_name', 'last_name'))
        data = build_workbook(people, latest, include_everyone=(raw == 'all'))

        stamp = date.today().isoformat()
        fname = f"JSAN_QF09_Employee_Skill_Matrix_{cycle or 'all-cycles'}_{raw}_{stamp}.xlsx"
        resp = HttpResponse(
            data,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        resp['Content-Disposition'] = f'attachment; filename="{fname}"'
        resp['Cache-Control'] = 'no-store'
        return resp
