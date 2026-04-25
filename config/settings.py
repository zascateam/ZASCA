"""
Django settings for ZASCA project.
"""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-change-this-in-production')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True').lower() == 'true'

# 允许的主机列表
# 在DEBUG模式下，允许所有主机
if DEBUG:
    ALLOWED_HOSTS = ['*']
    # CSRF Trusted Origins - 添加内网穿透域名
    CSRF_TRUSTED_ORIGINS = [
        'http://localhost',
        'http://127.0.0.1',
        'https://localhost',
        'https://127.0.0.1',
        'https://demo.supercmd.dpdns.org',  # 内网穿透域名
        'https://zasca.supercmd.dpdns.org', 
    ]
else:
    ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', 'https://localhost,https://127.0.0.1').split(',')

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # 第三方应用
    'rest_framework',
    'corsheaders',
    'django_bootstrap5',

    # 本地应用
    'apps.accounts',
    'apps.hosts',
    'apps.operations',
    'apps.dashboard',
    'apps.certificates',
    'apps.bootstrap',  # 主机引导系统
    'apps.audit',
    'apps.tasks',
    'apps.themes',  # 主题系统
    'plugins',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'config.maintenance_middleware.MaintenanceModeMiddleware',  # 维护模式中间件
    'config.local_lock_middleware.LocalLockMiddleware',  # 本地访问限制中间件
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'apps.bootstrap.middleware.SessionValidationMiddleware',  # 主机引导系统的会话验证中间件
    'config.demo_middleware.DemoModeMiddleware',  # DEMO模式中间件
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.dashboard.context_processors.system_config',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'zh-hans'

TIME_ZONE = 'Asia/Shanghai'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# CORS settings
CORS_ALLOW_ALL_ORIGINS = os.environ.get(
    'CORS_ALLOW_ALL_ORIGINS', 'True' if DEBUG else 'False'
).lower() == 'true'


# Winrm settings
WINRM_TIMEOUT = int(os.environ.get('WINRM_TIMEOUT', '30'))  # Winrm连接超时时间（秒）
WINRM_MAX_RETRIES = int(os.environ.get('WINRM_RETRY_COUNT', '3'))  # Winrm连接最大重试次数

# Logging settings
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
LOG_FILE = os.environ.get('LOG_FILE', str(BASE_DIR / 'logs' / 'zasca.log'))

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_FILE,
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': LOG_LEVEL,
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': LOG_LEVEL,
            'propagate': False,
        },
        'zasca': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# 安全配置
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

USE_X_FORWARDED_FOR = os.environ.get(
    'USE_X_FORWARDED_FOR', 'False'
).lower() == 'true'

SESSION_COOKIE_SECURE = os.environ.get(
    'SESSION_COOKIE_SECURE', 'True' if not DEBUG else 'False'
).lower() == 'true'
CSRF_COOKIE_SECURE = os.environ.get(
    'CSRF_COOKIE_SECURE', 'True' if not DEBUG else 'False'
).lower() == 'true'
SESSION_COOKIE_HTTPONLY = True

# HTTPS相关安全配置 (仅在生产环境中启用)
if not DEBUG:
    SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True').lower() == 'true'
    SECURE_HSTS_SECONDS = 31536000  # 一年
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Redis 配置 (保留用于兼容性检查，实际不再使用)
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Celery 配置 (使用 SQLite 替代 Redis)
CELERY_BROKER_URL = os.environ.get(
    'CELERY_BROKER_URL',
    f'sqla+sqlite:///{BASE_DIR / "celery_broker.sqlite3"}'
)
CELERY_RESULT_BACKEND = os.environ.get(
    'CELERY_RESULT_BACKEND',
    f'db+sqlite:///{BASE_DIR / "celery_results.sqlite3"}'
)
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'polling_interval': 1,
}

# Gateway 控制面配置
GATEWAY_ENABLED = os.environ.get(
    'GATEWAY_ENABLED', 'False'
).lower() in ('true', '1', 'yes')
GATEWAY_CONTROL_SOCKET = os.environ.get(
    'GATEWAY_CONTROL_SOCKET', '/run/zasca/control.sock'
)

# RDP 域名配置
RDP_DOMAIN = os.environ.get('RDP_DOMAIN', 'zasca.com')

# Geetest (极验) 验证码配置
GEETEST_ID = os.environ.get('GEETEST_ID')
GEETEST_KEY = os.environ.get('GEETEST_KEY')
# 是否在极验服务不可用时回退到本地验证码（True/False）
GEETEST_FALLBACK_LOCAL = os.environ.get('GEETEST_FALLBACK_LOCAL', 'True').lower() == 'true'
# 缓存极验服务状态的秒数（用于短期内避免重复探测）
GEETEST_SERVER_STATUS_CACHE_SECONDS = int(os.environ.get('GEETEST_SERVER_STATUS_CACHE_SECONDS', '300'))

# Cloudflare Turnstile 配置
TURNSTILE_SITE_KEY = os.environ.get('TURNSTILE_SITE_KEY')
TURNSTILE_SECRET_KEY = os.environ.get('TURNSTILE_SECRET_KEY')

# 系统配置
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@localhost')
SYSTEM_NAME = os.environ.get('SYSTEM_NAME', 'ZASCA 管理系统')

# Email settings
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '25'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'False').lower() == 'true'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'webmaster@localhost')

# DEMO模式配置
if os.environ.get('ZASCA_DEMO', '').lower() == '1':
    # 使用DEMO数据库
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'DEMO.sqlite3',
        }
    }
    
    # DEMO模式保留最小长度验证，仅放宽复杂度要求
    AUTH_PASSWORD_VALIDATORS = [
        {
            'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
            'OPTIONS': {'min_length': 4},
        },
    ]
    
    # 允许所有主机
    ALLOWED_HOSTS = ['*']
    
    # DEBUG模式开启
    DEBUG = True
    
    # 生成随机SECRET_KEY（每次启动不同）
    import secrets as _secrets
    SECRET_KEY = _secrets.token_urlsafe(50)
    import logging as _logging
    _logging.getLogger('zasca').warning('DEMO模式: 使用随机生成的SECRET_KEY，重启后所有session将失效')

# DEMO模式启动消息
if os.environ.get('ZASCA_DEMO', '').lower() == '1':
    from config.demo_startup import show_demo_startup_message
    show_demo_startup_message()

# Create logs directory if it doesn't exist
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

# Bootstrap认证配置
BOOTSTRAP_SHARED_SALT = os.environ.get('BOOTSTRAP_SHARED_SALT', '')
