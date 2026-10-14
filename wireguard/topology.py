"""Layout for the overview's network map: each server is a hub with its peers on a ring around it."""
import math

WIDTH = 520
HEIGHT = 340
CENTER_X = WIDTH // 2
CENTER_Y = HEIGHT // 2
RING_RADIUS = 118
LABEL_GAP = 16
MAX_PEERS = 16
MAX_LABELLED_PEERS = 10


def server_cluster(server):
    peers = list(server.peers.order_by('created_at'))
    shown = peers[:MAX_PEERS]
    label_peers = len(shown) <= MAX_LABELLED_PEERS
    nodes = []
    for index, peer in enumerate(shown):
        angle = -math.pi / 2 + 2 * math.pi * index / max(len(shown), 1)
        cos, sin = math.cos(angle), math.sin(angle)
        anchor = 'middle' if abs(cos) < 0.2 else ('start' if cos > 0 else 'end')
        nodes.append({
            'peer': peer,
            'x': round(CENTER_X + RING_RADIUS * cos, 1),
            'y': round(CENTER_Y + RING_RADIUS * sin, 1),
            'label_x': round(CENTER_X + (RING_RADIUS + LABEL_GAP) * cos, 1),
            'label_y': round(CENTER_Y + (RING_RADIUS + LABEL_GAP) * sin + 4 + (6 * sin if anchor == 'middle' else 0), 1),
            'anchor': anchor,
            'order': index,
        })
    return {
        'server': server,
        'nodes': nodes,
        'label_peers': label_peers,
        'hidden_count': len(peers) - len(shown),
        'enabled_count': sum(1 for p in peers if p.enabled),
        'peer_count': len(peers),
        'width': WIDTH,
        'height': HEIGHT,
        'cx': CENTER_X,
        'cy': CENTER_Y,
        'ring': RING_RADIUS,
    }
