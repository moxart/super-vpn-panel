from .models import Server


def sidebar(request):
    """Servers for the sidebar navigation, only for signed-in users."""
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {}
    return {'sidebar_servers': Server.objects.order_by('interface')}
