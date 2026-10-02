from .context import change_context
from .models import ChangeLog


class HistoryMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        source = _source_for_path(request.path)
        user = request.user if getattr(request, "user", None) else None
        with change_context(user=user, source=source):
            return self.get_response(request)


def _source_for_path(path):
    if path.startswith("/admin/"):
        return ChangeLog.Source.ADMIN
    if path.startswith("/accounts/"):
        return ChangeLog.Source.DASHBOARD
    return ChangeLog.Source.WEB
