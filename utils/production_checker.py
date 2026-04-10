"""
生产环境安全配置检查器
确保部署前进行安全验证
"""
import os
import sys
from django.conf import settings


def check_production_readiness():
    """检查生产环境配置的安全性"""
    errors = []
    warnings = []

    # 1. 检查 SECRET_KEY
    if not os.environ.get('DJANGO_SECRET_KEY'):
        if not settings.DEBUG:
            errors.append("生产环境必须设置 DJANGO_SECRET_KEY 环境变量")
        else:
            warnings.append("未设置 DJANGO_SECRET_KEY，系统将生成临时密钥")

    if settings.DEBUG and not settings.DEBUG:
        errors.append("生产环境不得启用 DEBUG 模式")

    if not settings.DEBUG:
        allowed_hosts = settings.ALLOWED_HOSTS
        if not allowed_hosts or allowed_hosts == ['*'] or 'localhost' in allowed_hosts:
            errors.append("生产环境必须设置有效的 ALLOWED_HOSTS，不能使用 * 或 localhost")

    if not settings.DEBUG:
        if not getattr(settings, 'SECURE_SSL_REDIRECT', False):
            warnings.append("建议启用 SECURE_SSL_REDIRECT 强制 HTTPS 重定向")

        if not getattr(settings, 'SECURE_HSTS_SECONDS', 0):
            warnings.append("建议启用 HSTS (HTTP Strict Transport Security)")

        if not getattr(settings, 'CSRF_COOKIE_SECURE', False):
            errors.append("生产环境必须启用 CSRF_COOKIE_SECURE")

        if not getattr(settings, 'SESSION_COOKIE_SECURE', False):
            errors.append("生产环境必须启用 SESSION_COOKIE_SECURE")

    # 5. 检查 WinRM 安全配置
    if hasattr(settings, 'WINRM_CLIENT_CERT_VALIDATION') and \
       settings.WINRM_CLIENT_CERT_VALIDATION == 'validate':
        if not settings.WINRM_CLIENT_CERT_PATH:
            warnings.append("WinRM 证书验证已启用但未指定客户端证书路径")

    # 6. 检查日志配置
    if not os.path.exists(os.path.join(settings.BASE_DIR, 'logs')):
        warnings.append("日志目录不存在，将自动创建")

    # 7. 检查数据库配置
    db_engine = settings.DATABASES['default']['ENGINE']
    if 'sqlite3' in db_engine and not settings.DEBUG:
        warnings.append("生产环境建议使用 PostgreSQL 或 MySQL 而不是 SQLite")

    return errors, warnings


def print_production_status():
    """打印生产环境状态"""
    errors, warnings = check_production_readiness()

    print("\n" + "="*60)
    print("ZASCA 生产环境安全性检查报告")
    print("="*60)
    print(f"生产模式: {'是' if not settings.DEBUG else '否'}")
    print(f"DEBUG 模式: {'是' if settings.DEBUG else '否'}")
    print(f"秘密密钥: {'已设置' if os.environ.get('DJANGO_SECRET_KEY') else '未设置'}")

    if errors:
        print("\n❌ 必须修复的错误:")
        for error in errors:
            print(f"  - {error}")

    if warnings:
        print("\n⚠️  建议修复的警告:")
        for warning in warnings:
            print(f"  - {warning}")

    if not errors and not warnings:
        print("\n✅ 所有安全检查通过，系统已准备好部署到生产环境")

    print("\n="*60)

    # 如果有严重错误，退出程序
    if errors:
        sys.exit(1)


if __name__ == '__main__':
    print_production_status()