from .base import *  # noqa: F403

DEBUG = True

ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': env('DB_NAME', default='sycamore'),      # noqa: F405
        'USER': env('DB_USER', default='root'),            # noqa: F405
        'PASSWORD': env('DB_PASSWORD', default='Syca@2026..'),  # noqa: F405
        'HOST': env('DB_HOST', default='127.0.0.1'),       # noqa: F405
        'PORT': env('DB_PORT', default='3306'),             # noqa: F405
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    },
}
