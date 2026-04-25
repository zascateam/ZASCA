from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required, permission_required
from django.utils.decorators import method_decorator
from django.views import View
from .models import InitialToken, ActiveSession
from apps.hosts.models import Host
from apps.certificates.models import CertificateAuthority, ServerCertificate
from apps.tasks.models import AsyncTask
from apps.bootstrap.tasks import generate_bootstrap_config, initialize_host_bootstrap
from django.shortcuts import get_object_or_404
import json
import logging
from django.utils import timezone
import secrets
import uuid


logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
@permission_required('bootstrap.add_initialtoken', raise_exception=True)
def create_initial_token(request):
    """创建初始令牌API - 基于配对码的简化认证机制"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        host_id = data.get('host_id')
        operator_id = data.get('operator_id')
        expire_hours = data.get('expire_hours', 24)

        if not host_id:
            return JsonResponse({
                'success': False,
                'error': 'Host ID is required'
            }, status=400)

        if not operator_id:
            return JsonResponse({
                'success': False,
                'error': 'Operator ID is required'
            }, status=400)

        try:
            host = Host.objects.get(id=host_id)
        except Host.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Host not found'
            }, status=404)

        from datetime import timedelta
        from django.utils import timezone

        token = secrets.token_urlsafe(32)
        expires_at = timezone.now() + timedelta(hours=expire_hours)

        initial_token = InitialToken.objects.create(
            token=token,
            host=host,
            expires_at=expires_at,
            status='ISSUED'
        )

        pairing_code = initial_token.generate_pairing_code()

        import base64
        config_data = {
            'c_side_url': request.build_absolute_uri('/').rstrip('/'),
            'token': initial_token.token,
            'host_id': str(host.id),
            'expires_at': initial_token.expires_at.isoformat()
        }

        config_json = json.dumps(config_data)
        encoded_config = base64.b64encode(config_json.encode('utf-8')).decode('utf-8')

        return JsonResponse({
            'success': True,
            'data': {
                'token': initial_token.token,
                'expires_at': initial_token.expires_at.isoformat(),
                'host_id': host.id,
                'hostname': host.hostname,
                'pairing_code': pairing_code,
                'encoded_config': encoded_config
            }
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        logger.error(f"Error creating initial token: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Failed to create initial token'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def verify_pairing_code(request):
    """配对码验证接口 - 简化的认证机制"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        host_id = data.get('host_id')
        pairing_code = data.get('pairing_code')
        
        if not host_id or not pairing_code:
            return JsonResponse({
                'success': False,
                'error': 'Host ID and pairing code are required'
            }, status=400)
        
        # 查找对应的初始令牌
        try:
            initial_tokens = InitialToken.objects.filter(
                host_id=host_id,
                status='ISSUED',  # 只处理已签发但未配对的令牌
                expires_at__gt=timezone.now()
            )
            
            if not initial_tokens.exists():
                return JsonResponse({
                    'success': False,
                    'error': 'No valid initial token found for this host'
                }, status=404)
            
            # 尝试验证配对码
            verified = False
            for token_obj in initial_tokens:
                logger.info(f"验证配对码: token={token_obj.token[:10]}..., host_id={token_obj.host.id}")
                
                if token_obj.verify_pairing_code(pairing_code):
                    verified = True
                    logger.info(f"配对码验证成功: {pairing_code}")
                    break
                else:
                    logger.info(f"配对码验证失败: {pairing_code}")
            
            if verified:
                return JsonResponse({
                    'success': True,
                    'message': 'Pairing code verification successful'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid or expired pairing code'
                }, status=400)
                
        except Exception as e:
            logger.error(f"Error verifying pairing code: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Pairing code verification failed'
        }, status=500)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        logger.error(f"Error validating pairing code: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Pairing code validation failed'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def get_bootstrap_config(request):
    """获取主机引导配置API"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        hostname = data.get('hostname')
        ip_address = data.get('ip_address')
        auth_token = data.get('auth_token')  # 认证令牌
        
        if not hostname or not auth_token:
            return JsonResponse({
                'success': False,
                'error': 'Hostname and auth_token are required'
            }, status=400)
        
        # 验证初始令牌
        try:
            token_obj = InitialToken.objects.get(
                token=auth_token,
                status='PAIRED',  # 确保已经配对验证
                expires_at__gt=timezone.now()
            )
        except InitialToken.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid or unauthorized bootstrap token'
            }, status=401)
        
        # 验证主机是否匹配令牌
        if str(token_obj.host.id) != data.get('host_id', ''):
            return JsonResponse({
                'success': False,
                'error': 'Host ID does not match the token'
            }, status=400)
        
        # 标记令牌为已使用
        token_obj.status = 'CONSUMED'
        token_obj.save()
        
        # 生成活动会话
        session_token = str(uuid.uuid4())
        bound_ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        
        ActiveSession.objects.create(
            session_token=session_token,
            host=token_obj.host,
            bound_ip=bound_ip,
            expires_at=timezone.now() + timezone.timedelta(days=1)  # 24小时有效期
        )
        
        # 生成引导配置（异步任务）
        from apps.accounts.models import User
        admin_user = User.objects.filter(is_superuser=True).first()
        operator_id = admin_user.id if admin_user else None
        
        task_result = generate_bootstrap_config.delay(
            hostname=hostname,
            ip_address=ip_address or token_obj.host.ip_address,
            operator_id=operator_id
        )
        
        # 等待任务完成（最多等待30秒）
        config_result = task_result.get(timeout=30)
        
        if config_result['success']:
            return JsonResponse({
                'success': True,
                'data': config_result['config'],
                'session_token': session_token  # 返回新的会话令牌
            })
        else:
            return JsonResponse({
                'success': False,
                'error': config_result.get('error', 'Failed to generate bootstrap config')
            }, status=500)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        logger.error(f"Error getting bootstrap config: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Failed to get bootstrap config'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
@permission_required('bootstrap.change_initialtoken', raise_exception=True)
def trigger_host_bootstrap(request):
    """触发主机引导流程API"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        host_id = data.get('host_id')
        operator_id = data.get('operator_id')

        if not host_id:
            return JsonResponse({
                'success': False,
                'error': 'Host ID is required'
            }, status=400)

        if not operator_id:
            return JsonResponse({
                'success': False,
                'error': 'Operator ID is required'
            }, status=400)

        try:
            host = Host.objects.get(id=host_id)
        except Host.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Host not found'
            }, status=404)

        task_result = initialize_host_bootstrap.delay(
            host_id=host_id,
            operator_id=operator_id
        )

        return JsonResponse({
            'success': True,
            'data': {
                'task_id': task_result.id,
                'host_id': host_id,
                'hostname': host.hostname,
                'status': 'started'
            }
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        logger.error(f"Error triggering host bootstrap: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Failed to trigger host bootstrap'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def check_bootstrap_status(request):
    """检查引导状态API"""
    try:
        token = request.GET.get('token')
        host_id = request.GET.get('host_id')
        
        if not token and not host_id:
            return JsonResponse({
                'success': False,
                'error': 'Either token or host_id is required'
            }, status=400)
        
        if token:
            # 通过令牌查询
            try:
                initial_token = InitialToken.objects.get(token=token)
                host = initial_token.host
            except InitialToken.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid token'
                }, status=404)
        else:
            # 通过主机ID查询
            try:
                host = Host.objects.get(id=host_id)
            except Host.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'error': 'Host not found'
                }, status=404)
        
        return JsonResponse({
            'success': True,
            'data': {
                'host_id': host.id,
                'hostname': host.hostname,
                'init_status': host.init_status if hasattr(host, 'init_status') else 'unknown',
                'initialized_at': getattr(host, 'initialized_at', None),
                'certificate_thumbprint': getattr(host, 'certificate_thumbprint', None),
                'ip_address': host.ip_address,
                'port': host.port
            }
        })
        
    except Exception as e:
        logger.error(f"Error checking bootstrap status: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Failed to check bootstrap status'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def validate_bootstrap_token(request):
    """验证引导令牌有效性"""
    try:
        data = json.loads(request.body.decode('utf-8'))
        token = data.get('token')
        
        if not token:
            return JsonResponse({
                'success': False,
                'error': 'Token is required'
            }, status=400)
        
        try:
            token_obj = InitialToken.objects.get(
                token=token,
                status__in=['ISSUED', 'PAIRED'],  # 未消耗的令牌
                expires_at__gt=timezone.now()
            )
            
            return JsonResponse({
                'success': True,
                'data': {
                    'valid': True,
                    'host_id': token_obj.host.id,
                    'hostname': token_obj.host.hostname,
                    'expires_at': token_obj.expires_at.isoformat(),
                    'status': token_obj.status
                }
            })
        except InitialToken.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid or expired token'
            }, status=401)
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        logger.error(f"Error validating bootstrap token: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Token validation failed'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def get_session_token(request):
    """获取会话令牌接口 - H端初始化流程的第一步"""
    try:
        # 记录请求详细信息
        client_ip = get_client_ip(request)
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        logger.info(f"Get session token request received - IP: {client_ip}")
        
        if not auth_header.startswith('Bearer '):
            return JsonResponse({
                'success': False,
                'error': 'Authorization header missing or invalid'
            }, status=401)
        
        initial_token = auth_header.split(' ')[1]
        
        # 验证InitialToken
        try:
            token_obj = InitialToken.objects.get(
                token=initial_token,
                status__in=['ISSUED', 'PAIRED'],  # 允许已签发或已配对的令牌
                expires_at__gt=timezone.now()
            )
        except InitialToken.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid or expired initial token'
            }, status=401)
        
        # 获取真实客户端IP
        ip = client_ip
        
        # 原子操作：生成新的session_token，创建ActiveSession记录
        from django.db import transaction
        with transaction.atomic():
            # 生成新的session_token
            session_token = str(uuid.uuid4())
            
            # 在ActiveSession表中插入记录
            active_session = ActiveSession.objects.create(
                session_token=session_token,
                host=token_obj.host,
                bound_ip=ip,
                expires_at=timezone.now() + timezone.timedelta(hours=1)  # 1小时后过期
            )
            
            # 更新InitialToken状态为CONSUMED
            token_obj.status = 'CONSUMED'
            token_obj.save()
        
        return JsonResponse({
            'success': True,
            'session_token': session_token,
            'expires_in': 3600,  # 1小时（秒）
            'details': {
                'host_name': token_obj.host.name,
                'host_id': token_obj.host.id,
                'bound_ip': ip,
                'session_expires_at': active_session.expires_at.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error creating session token: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Failed to create session token'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def exchange_token(request):
    """令牌交换接口 - 根据规范"""
    try:
        # 记录请求详细信息
        client_ip = get_client_ip(request)
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header.startswith('Bearer '):
            return JsonResponse({
                'success': False,
                'error': 'Authorization header missing or invalid'
            }, status=401)
        
        session_token = auth_header.split(' ')[1]
        
        # 验证ActiveSession
        try:
            active_session = ActiveSession.objects.get(
                session_token=session_token,
                expires_at__gt=timezone.now()
            )
        except ActiveSession.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid or expired session token'
            }, status=401)
        
        # 验证IP绑定
        current_ip = client_ip
        if active_session.bound_ip != current_ip:
            return JsonResponse({
                'success': False,
                'error': 'IP address mismatch'
            }, status=403)
        
        # 延长会话有效期
        from django.db import transaction
        with transaction.atomic():
            active_session.expires_at = timezone.now() + timezone.timedelta(days=7)  # 延长到7天
            active_session.save()
        
        return JsonResponse({
            'success': True,
            'session_token': session_token,
            'expires_in': 604800,  # 7天（秒）
            'details': {
                'host_name': active_session.host.name,
                'host_id': active_session.host.id,
                'bound_ip': active_session.bound_ip,
                'session_expires_at': active_session.expires_at.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error exchanging token: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Token exchange failed'
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def check_pairing_status(request):
    """检查配对状态接口"""
    try:
        # 从Authorization头获取InitialToken
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return JsonResponse({
                'paired': False,
                'message': 'Invalid authorization header'
            }, status=401)
        
        initial_token = auth_header.split(' ')[1]
        
        # 查找对应的初始令牌
        try:
            token_obj = InitialToken.objects.get(
                token=initial_token,
                expires_at__gt=timezone.now()
            )
            
            if token_obj.status == 'PAIRED':
                return JsonResponse({
                    'paired': True,
                    'message': 'Pairing completed',
                    'host_id': token_obj.host.id,
                    'hostname': token_obj.host.hostname
                })
            elif token_obj.status == 'ISSUED':
                return JsonResponse({
                    'paired': False,
                    'message': 'Waiting for pairing code verification',
                    'host_id': token_obj.host.id
                })
            elif token_obj.status == 'CONSUMED':
                return JsonResponse({
                    'paired': True,
                    'message': 'Token already consumed',
                    'host_id': token_obj.host.id
                })
            else:
                return JsonResponse({
                    'paired': False,
                    'message': f'Token status: {token_obj.status}'
                })
                
        except InitialToken.DoesNotExist:
            return JsonResponse({
                'paired': False,
                'message': 'Invalid or expired token'
            }, status=404)
            
    except Exception as e:
        logger.error(f"Error checking pairing status: {str(e)}", exc_info=True)
        return JsonResponse({
            'paired': False,
            'message': 'Internal error'
        }, status=500)


@csrf_exempt
@require_http_methods(["DELETE"])
def revoke_session(request):
    """吊销会话接口 - 根据规范"""
    try:
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if not auth_header.startswith('Bearer '):
            return JsonResponse({
                'success': False,
                'error': 'Authorization header missing or invalid'
            }, status=401)
        
        session_token = auth_header.split(' ')[1]
        
        # 删除ActiveSession表中的对应记录
        try:
            session = ActiveSession.objects.get(session_token=session_token)
            session.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Session revoked successfully'
            })
        except ActiveSession.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Invalid session token'
            }, status=401)
        
    except Exception as e:
        logger.error(f"Error revoking session: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Failed to revoke session'
        }, status=500)


def get_client_ip(request):
    """获取客户端真实IP地址"""
    from django.conf import settings as django_settings
    if getattr(django_settings, 'USE_X_FORWARDED_FOR', False):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


class BootstrapManagementView(View):
    """引导管理视图 - 需要管理员权限"""
    
    @method_decorator(permission_required('bootstrap.view_initialtoken'))
    def get(self, request):
        """获取引导令牌列表"""
        try:
            page = int(request.GET.get('page', 1))
            page_size = min(int(request.GET.get('page_size', 20)), 100)  # 最大100条每页
            status_filter = request.GET.get('status')  # issued, paired, consumed, all
            
            queryset = InitialToken.objects.select_related('host').all()
            
            # 状态过滤
            if status_filter == 'issued':
                queryset = queryset.filter(status='ISSUED')
            elif status_filter == 'paired':
                queryset = queryset.filter(status='PAIRED')
            elif status_filter == 'consumed':
                queryset = queryset.filter(status='CONSUMED')
            elif status_filter == 'expired':
                queryset = queryset.filter(expires_at__lt=timezone.now())
            elif status_filter != 'all':
                # 默认显示未过期的
                queryset = queryset.filter(expires_at__gt=timezone.now())
            
            # 分页
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            tokens = queryset[start_idx:end_idx]
            
            total_count = queryset.count()
            
            result = {
                'success': True,
                'data': {
                    'tokens': [
                        {
                            'id': token.token,
                            'token': token.token,
                            'hostname': token.host.hostname,
                            'host_id': token.host.id,
                            'created_at': token.created_at.isoformat(),
                            'expires_at': token.expires_at.isoformat(),
                            'status': token.status,
                            'is_expired': token.expires_at < timezone.now()
                        }
                        for token in tokens
                    ],
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total_count': total_count,
                        'total_pages': (total_count + page_size - 1) // page_size
                    }
                }
            }
            
            return JsonResponse(result)
            
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid page or page_size parameter'
            }, status=400)
        except Exception as e:
            logger.error(f"Error getting bootstrap tokens: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Failed to retrieve bootstrap tokens'
            }, status=500)
    
    @method_decorator(permission_required('bootstrap.delete_initialtoken'))
    def delete(self, request):
        """删除引导令牌"""
        try:
            token_id = request.GET.get('id')
            
            if not token_id:
                return JsonResponse({
                    'success': False,
                    'error': 'Token ID is required'
                }, status=400)
            
            token = get_object_or_404(InitialToken, token=token_id)
            token.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Initial token deleted successfully'
            })
            
        except Exception as e:
            logger.error(f"Error deleting initial token: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'error': 'Failed to delete initial token'
            }, status=500)