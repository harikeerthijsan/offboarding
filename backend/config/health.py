from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(['GET'])
@permission_classes([AllowAny])
def health(request):
    """Lightweight liveness/readiness probe. Verifies DB connectivity without
    exposing any infrastructure details."""
    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        db_ok = False

    payload = {'status': 'healthy' if db_ok else 'unhealthy'}
    if not db_ok:
        payload['database'] = 'unavailable'
    return Response(payload, status=200 if db_ok else 503)
