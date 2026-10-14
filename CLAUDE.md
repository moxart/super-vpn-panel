# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Super VPN Panel is a Django 5.2 web panel for managing WireGuard server interfaces and client (peer) configs. Keys (`cryptography` X25519) and QR codes (`segno`) are generated in-process, so no `wg`/`qrencode` binaries are needed and nothing shells out.

## Commands

```bash
python3 -m venv venv && source venv/bin/activate   # Python >= 3.10
pip install -r requirements.txt
export DJANGO_DEBUG=1                  # settings refuse to load without DJANGO_SECRET_KEY unless debug is on
python manage.py migrate
python manage.py createsuperuser       # needed to log in; there is no signup flow
python manage.py runserver             # / redirects to /svp/wireguard/home/, login at /svp/login/

python manage.py test                  # all tests
python manage.py test wireguard.tests.PeerViewTests.test_downloads   # a single test

docker compose up --build              # runs migrate + runserver on :8000
```

There is no linter or formatter configured. Settings come from env vars (`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_DB_PATH`, `WIREGUARD_SERVER_CONF`); see the docstring in `vpn/settings.py`.

## Architecture

- URLs are all under `/svp/`: `svp/wireguard/` → `wireguard.urls`, `svp/` → `accounts.urls` (Django's auth `LoginView`/`LogoutView`; logout is POST-only), `svp/admin/`.
- `wireguard/models.py`: `Server` (one interface, e.g. `wg0`, with its subnet in `address` like `10.0.0.1/24`) and `Peer` (FK to `Server`, CASCADE; nullable only for legacy orphans). Peers have no endpoint/port of their own: their config always uses the server's current values. `Server.next_free_address()` does IP allocation.
- **The database is the single source of truth.** Every config is rendered from it by `wireguard/configs.py`: `render_server_config` (Interface plus a `[Peer]` block with a `/32` or `/128` AllowedIPs for each *enabled* peer) and `render_peer_config`, plus the QR PNG and `.tar.gz` profile. Peer files are never stored on disk; `PeerDownloadView` serves them behind login.
- The only file written is `<WIREGUARD_SERVER_CONF>/<interface>.conf` (mode 0600). Anything that changes a server or its peers must call `sync_server_config` (in views) or `configs.write_server_config`, including the old server when a peer moves or an interface is renamed. The admin classes in `wireguard/admin.py` do this too.
- Forms live in `<app>/forms/<FormName>.py`, one class per module. `ServerForm`/`PeerForm` are ModelForms that hold all the input validation (`wireguard/validators.py`): key format, interface and peer name charset, single-line PostUp/PostDown, subnet overlap between servers, and peer address inside the subnet and unused. `ServerForm.save` derives the public key from the private key. Values end up verbatim in wg-quick config files, so new free-text fields need a single-line validator.
- `wireguard/backup.py`: JSON export/import (version 1). Import re-validates through the same forms and skips existing interfaces and peer names; it never overwrites.
- Templates: wireguard templates are referenced without an app prefix (`layouts/...`, `includes/...`); accounts templates are under `accounts/`. App pages extend `layouts/app.html`, the sidebar shell, and fill `page_head`, `page_actions` and `content`. The login page extends `base.html` directly. The sidebar's server list comes from the `wireguard.context_processors.sidebar` context processor. Shared pieces are `includes/field.html` (label, widget, help and errors), `includes/config-block.html` (highlighted `<pre>` plus a copy button) and `includes/peer-table.html`/`peer-rows.html`. The `peer_config` and `highlight_config` filters live in `wireguard/templatetags/wireguard_tags.py`. The overview's network map is laid out in `wireguard/topology.py` and drawn as inline SVG in `layouts/home.html`.
- Styling is a single hand-written `wireguard/static/css/styles.css` (design tokens on `:root`, no CSS framework) using the fonts vendored in `static/vendor/fonts/`. `static/js/scripts.js` is vanilla JS plus the vendored clipboard.js. Bulma and jQuery are still under `static/vendor/` but are no longer loaded. `includes/navbar.html`, `footer.html`, `status.html` and `peer-card.html` are leftovers from the old UI and are unused.
- Migration `0002_hardening` includes a data step that normalises rows written by the pre-rewrite version (trailing newlines on keys, NULL or duplicate peer names, NULL ports).
