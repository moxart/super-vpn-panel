"""
Django settings for vpn project.

Deployment-specific values are read from environment variables:

    DJANGO_SECRET_KEY     required when DJANGO_DEBUG is off
    DJANGO_DEBUG          "1"/"true" to enable debug mode (default: off)
    DJANGO_ALLOWED_HOSTS  comma-separated host names (default: localhost,127.0.0.1)
    DJANGO_DB_PATH        SQLite database file (default: <project>/db.sqlite3)
    WIREGUARD_SERVER_CONF directory the generated <interface>.conf files are written to
"""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')


DEBUG = env_bool('DJANGO_DEBUG')

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Set DJANGO_SECRET_KEY, or DJANGO_DEBUG=1 for local development.')
    SECRET_KEY = 'insecure-development-only-key'

ALLOWED_HOSTS = [h.strip() for h in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]


# Application definition

INSTALLED_APPS = [
    'wireguard',
    'accounts',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'vpn.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'wireguard.context_processors.sidebar',
            ],
        },
    },
]

WSGI_APPLICATION = 'vpn.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ.get('DJANGO_DB_PATH', BASE_DIR / 'db.sqlite3'),
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

WIREGUARD_SERVER_CONF = os.environ.get(
    'WIREGUARD_SERVER_CONF', os.path.join(BASE_DIR, 'wireguard/wg-configs/server/conf/'))

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'wireguard:home'
LOGOUT_REDIRECT_URL = 'accounts:login'

if not DEBUG:
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
    X_FRAME_OPTIONS = 'DENY'
