"""Skills Hub API — Phase 1 core endpoints.

Role mapping from the source app's 3 roles to ours:
  employee actions  -> any authenticated user
  staff actions     -> MANAGER / HR / ADMIN (view team, export, manage catalogue & cycles)
"""
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.employees.models import Employee

from .cycles import active_cycle, cycles_for, compliance_of
from .models import SkillDefinition, ReviewCycle, SkillSubmission
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
    """GET /api/skills/cycles/ — company calendar; staff also get per-cycle counts."""
    permission_classes = [IsAuthenticated]

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
