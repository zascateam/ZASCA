"""
自定义错误处理视图
"""
from django.shortcuts import render, redirect
from django.urls import reverse
from django.http import QueryDict
from django.views.static import serve
from django.conf import settings
import os


def custom_404(request, exception):
    """
    自定义404错误页面

    Args:
        request: HTTP请求对象
        exception: 异常对象

    Returns:
        HttpResponse: 404错误页面
    """
    return render(request, 'errors/404.html', status=404)


def custom_500(request):
    """
    自定义500错误页面

    Args:
        request: HTTP请求对象

    Returns:
        HttpResponse: 500错误页面
    """
    return render(request, 'errors/500.html', status=500)


def extend_admin_login(request):
    """
    重定向Django Admin登录页面到accounts登录页面，并保留查询参数
    """
    # 构建带查询参数的目标URL
    next_url = request.GET.get('next', '')  # 获取next参数
    target_url = reverse('accounts:login')
    
    # 如果有next参数，则添加到目标URL
    if next_url:
        target_url += f'?next={next_url}'
    
    return redirect(target_url)


def favicon_view(request):
    """
    提供 favicon 文件
    """
    favicon_path = os.path.join(settings.STATIC_ROOT or settings.STATICFILES_DIRS[0], 'img', 'favicon.ico')
    if not os.path.exists(favicon_path):
        favicon_path = os.path.join(settings.STATICFILES_DIRS[0], 'img', 'favicon.ico')
    
    return serve(request, os.path.basename(favicon_path), document_root=os.path.dirname(favicon_path))


def favicon_svg_view(request):
    """
    提供 favicon.svg 文件
    """
    favicon_path = os.path.join(settings.STATIC_ROOT or settings.STATICFILES_DIRS[0], 'img', 'favicon.svg')
    if not os.path.exists(favicon_path):
        favicon_path = os.path.join(settings.STATICFILES_DIRS[0], 'img', 'favicon.svg')
    
    return serve(request, os.path.basename(favicon_path), document_root=os.path.dirname(favicon_path))