from .base import *  # noqa: F403

DEBUG = True

ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': env('DB_NAME', default='sycamore'),      # noqa: F405
        'USER': env('DB_USER', default='root'),            # noqa: F405
        'PASSWORD': env('DB_PASSWORD', default='change-this-password'),  # noqa: F405  真实密码放 backend/.env
        'HOST': env('DB_HOST', default='127.0.0.1'),       # noqa: F405
        'PORT': env('DB_PORT', default='3306'),             # noqa: F405
        # 历史数据 start_time 等均为 naive 本地时间（CSV 导入），
        # 指定数据库时区为 Asia/Shanghai，避免 Django 误按 UTC 解释导致 +8h 偏移
        'TIME_ZONE': 'Asia/Shanghai',
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES', time_zone='+08:00'",
        },
    },
}
