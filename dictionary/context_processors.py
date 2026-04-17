from django.db import DatabaseError, OperationalError, ProgrammingError

from .models import SiteSettings


def site_settings(request):
    """Expose the singleton SiteSettings as `site` to every template.

    Returns an empty dict on DB errors (e.g. before migrations are applied)
    so that management commands and early boot paths don't crash.
    """
    try:
        return {'site': SiteSettings.load()}
    except (DatabaseError, OperationalError, ProgrammingError):
        return {}
