"""
ZASCA URL Configuration
"""
from django.contrib import admin
from django.contrib.staticfiles.views import serve
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from config import views

urlpatterns = [
    path('admin/login/', views.extend_admin_login),
    path('admin/', admin.site.urls),
    path('api/', include('rest_framework.urls')),
    path('accounts/', include('apps.accounts.urls')),
    path('operations/', include('apps.operations.urls')),
    path('certificates/', include('apps.certificates.urls')),
    # path('bootstrap/', include('apps.bootstrap.urls')),  # 已隐藏主机引导系统
    path('audit/', include('apps.audit.urls')),
    path('', include('apps.dashboard.urls')),
    # 处理404页面
    path('404/', TemplateView.as_view(template_name='errors/404.html'), name='404'),
    path('favicon.ico', views.favicon_view),
    path('favicon.svg', views.favicon_svg_view),
]

# 开发环境下提供媒体文件服务
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# 自定义错误页面
handler404 = 'config.views.custom_404'
handler500 = 'config.views.custom_500'