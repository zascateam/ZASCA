from functools import wraps
from .models import AuditLog, SensitiveOperation, SecurityEvent
from django.contrib.auth.models import User
from apps.hosts.models import Host
from utils.helpers import get_client_ip
import json
import logging
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


def audit_log(action, host_param=None, details_extractor=None, related_object_param=None):
    """
    审计日志装饰器
    :param action: 操作类型
    :param host_param: 从参数中提取主机对象的参数名
    :param details_extractor: 从参数中提取详细信息的函数
    :param related_object_param: 从参数中提取关联对象的参数名（用于通用外键）
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            response = None
            success = True
            error_msg = None
            
            try:
                response = view_func(request, *args, **kwargs)
            except Exception as e:
                success = False
                error_msg = str(e)
                raise
            finally:
                # 记录审计日志
                try:
                    user = request.user if request.user.is_authenticated else None
                    
                    # 获取主机对象
                    host = None
                    if host_param and kwargs.get(host_param):
                        host_id = kwargs[host_param]
                        if isinstance(host_id, Host):
                            host = host_id
                        elif isinstance(host_id, int):
                            host = Host.objects.filter(id=host_id).first()
                    
                    # 获取关联对象（用于通用外键）
                    content_object = None
                    if related_object_param and kwargs.get(related_object_param):
                        obj_id = kwargs[related_object_param]
                        obj_type = None
                        if isinstance(obj_id, str) and '.' in obj_id:
                            app_label, model = obj_id.split('.')
                            from django.apps import apps
                            obj_type = apps.get_model(app_label, model)
                        # 这里可以根据实际需要扩展对象类型识别逻辑
                    
                    # 提取操作详情
                    details = {}
                    if details_extractor:
                        details = details_extractor(request, *args, **kwargs)
                    else:
                        # 默认提取一些基本信息
                        details = {
                            'method': request.method,
                            'path': request.path,
                            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                        }
                    
                    AuditLog.objects.create(
                        user=user,
                        host=host,
                        action=action,
                        ip_address=get_client_ip(request),
                        success=success,
                        details=details,
                        result=error_msg,
                        content_object=content_object
                    )
                except Exception as log_error:
                    # 审计日志记录失败不应该影响主业务
                    logger.error(f"Audit logging failed: {log_error}", exc_info=True)
            
            return response
        return wrapper
    return decorator


def log_sensitive_operation(operation_type, justification_required=True, response_on_missing_justification=None):
    """
    敏感操作日志装饰器
    :param operation_type: 操作类型
    :param justification_required: 是否需要提供操作理由
    :param response_on_missing_justification: 缺少理由时的响应
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if justification_required:
                justification = (
                    request.POST.get('justification') or 
                    request.GET.get('justification') or 
                    request.META.get('HTTP_X_JUSTIFICATION') or
                    getattr(request, 'data', {}).get('justification')  # 对于DRF
                )
                if not justification:
                    if response_on_missing_justification:
                        return response_on_missing_justification
                    else:
                        raise PermissionDenied("此操作需要提供操作理由")
            
            response = None
            error_occurred = False
            try:
                response = view_func(request, *args, **kwargs)
            except Exception as e:
                error_occurred = True
                raise
            finally:
                try:
                    # 记录敏感操作
                    SensitiveOperation.objects.create(
                        operation_type=operation_type,
                        user=request.user if request.user.is_authenticated else None,
                        target=str(args) + str(kwargs),
                        ip_address=get_client_ip(request),
                        justification=justification or "N/A",
                        result=str(response) if response and hasattr(response, '__str__') else "Completed" if not error_occurred else "Failed"
                    )
                except Exception as log_error:
                    logger.error(f"Sensitive operation logging failed: {log_error}", exc_info=True)
            
            return response
        return wrapper
    return decorator


def security_event_logger(event_type, severity='medium', auto_resolve_threshold=5):
    """
    安全事件记录装饰器
    :param event_type: 事件类型
    :param severity: 严重程度
    :param auto_resolve_threshold: 自动解决阈值（相同IP同类型事件数量）
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            ip_address = get_client_ip(request)
            
            # 检查是否有未解决的同类事件
            recent_events = SecurityEvent.objects.filter(
                event_type=event_type,
                ip_address=ip_address,
                resolved=False
            ).order_by('-timestamp')
            
            # 如果超过阈值，自动标记为已解决
            if recent_events.count() >= auto_resolve_threshold:
                recent_events.update(resolved=True, resolved_at=timezone.now())
            
            try:
                response = view_func(request, *args, **kwargs)
            except Exception as e:
                # 记录安全事件
                SecurityEvent.objects.create(
                    event_type=event_type,
                    severity=severity,
                    user=request.user if request.user.is_authenticated else None,
                    ip_address=ip_address,
                    description=str(e) if str(e) != '' else f"Security event occurred during {view_func.__name__}",
                )
                raise
            
            # 对于某些类型的事件，即使成功也要记录
            if event_type in ['failed_login']:  # 这种情况不太可能，但我们保留这个逻辑
                pass  # 不记录成功的登录为安全事件
            
            return response
        return wrapper
    return decorator


def log_user_session_activity(view_func):
    """
    记录用户会话活动的装饰器
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from .models import SessionActivity
        from django.contrib.sessions.models import Session
        
        session_key = request.session.session_key
        user = request.user if request.user.is_authenticated else None
        
        if user and session_key:
            # 检查是否已有对应的会话活动记录
            session_activity, created = SessionActivity.objects.get_or_create(
                session_key=session_key,
                user=user,
                is_active=True,
                defaults={
                    'ip_address': get_client_ip(request),
                    'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],  # 限制长度
                }
            )
        
        response = view_func(request, *args, **kwargs)
        return response
    return wrapper


# 辅助函数：批量记录审计日志
def bulk_audit_log(entries):
    """
    批量记录审计日志
    :param entries: 日志条目列表，每个条目是一个字典
    """
    audit_logs = []
    for entry in entries:
        audit_logs.append(AuditLog(
            user=entry.get('user'),
            host=entry.get('host'),
            action=entry['action'],
            ip_address=entry.get('ip_address'),
            success=entry.get('success', True),
            details=entry.get('details', {}),
            result=entry.get('result')
        ))
    
    AuditLog.objects.bulk_create(audit_logs)


# Django信号处理器辅助函数
def log_model_change(sender, instance, created, **kwargs):
    """
    通用模型变更日志记录函数
    可以作为Django信号的处理器使用
    """
    from django.contrib.contenttypes.models import ContentType
    
    user = getattr(instance, '_audit_user', None)  # 从实例获取操作用户（需要在视图中设置）
    action = 'create' if created else 'update'
    ip_address = getattr(instance, '_audit_ip', None)  # 从实例获取IP地址
    
    AuditLog.objects.create(
        user=user,
        action=action,
        ip_address=ip_address,
        details={
            'model': sender._meta.label,
            'pk': instance.pk,
            'fields_changed': getattr(instance, '_fields_changed', [])
        },
        content_type=ContentType.objects.get_for_model(sender),
        object_id=instance.pk
    )


def log_model_deletion(sender, instance, **kwargs):
    """
    通用模型删除日志记录函数
    可以作为Django信号的处理器使用
    """
    from django.contrib.contenttypes.models import ContentType
    
    user = getattr(instance, '_audit_user', None)  # 从实例获取操作用户
    ip_address = getattr(instance, '_audit_ip', None)  # 从实例获取IP地址
    
    AuditLog.objects.create(
        user=user,
        action='delete',
        ip_address=ip_address,
        details={
            'model': sender._meta.label,
            'pk': instance.pk,
        },
        content_type=ContentType.objects.get_for_model(sender),
        object_id=instance.pk
    )