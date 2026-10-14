from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from wireguard import configs

register = template.Library()


@register.filter
def peer_config(peer):
    if peer.server_id is None:
        return ''
    return configs.render_peer_config(peer)


@register.filter
def highlight_config(text):
    """Mark up wg-quick config text: section headers, keys and comments get their own spans."""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            lines.append('<span class="cf-section">{}</span>'.format(escape(line)))
        elif stripped.startswith('#'):
            lines.append('<span class="cf-comment">{}</span>'.format(escape(line)))
        elif '=' in line:
            key, value = line.split('=', 1)
            lines.append('<span class="cf-key">{}</span>=<span class="cf-value">{}</span>'.format(
                escape(key), escape(value)))
        else:
            lines.append(escape(line))
    return mark_safe('\n'.join(lines))
