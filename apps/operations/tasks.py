from celery import shared_task
from django.contrib.auth.models import User
from apps.operations.models import AccountOpeningRequest, CloudComputerUser
from apps.hosts.models import Host
from apps.tasks.models import AsyncTask
from apps.tasks.models import TaskProgress
import logging
import secrets
import string

logger = logging.getLogger(__name__)


def generate_secure_password(length=16):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+-=[]{}|;:,.<>?"
    while True:
        password = ''.join(secrets.choice(alphabet) for _ in range(length))
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password)
        if has_upper and has_lower and has_digit and has_special:
            return password


@shared_task(bind=True)
def process_opening_request(self, request_id, operator_id):
    task = AsyncTask.objects.create(
        task_id=self.request.id,
        name=f"处理开户请求 #{request_id}",
        created_by_id=operator_id,
        target_object_id=request_id,
        target_content_type='operations.AccountOpeningRequest',
        status='running'
    )
    
    try:
        request_obj = AccountOpeningRequest.objects.get(id=request_id)
        task.start_execution()
        
        task.progress = 10
        task.save()
        
        TaskProgress.objects.create(
            task=task,
            progress=10,
            message="开始处理开户请求"
        )
        
        available_host = Host.objects.filter(
            is_active=True,
            init_status='ready'
        ).first()
        
        if not available_host:
            raise Exception("没有可用的主机资源")
        
        task.progress = 30
        task.save()
        
        TaskProgress.objects.create(
            task=task,
            progress=30,
            message="找到可用主机"
        )
        
        from utils.winrm_client import WinrmClient
        
        username = request_obj.username
        password = generate_secure_password()
        
        task.progress = 50
        task.save()
        
        TaskProgress.objects.create(
            task=task,
            progress=50,
            message="执行PowerShell命令创建用户"
        )
        
        client = WinrmClient(
            hostname=available_host.hostname,
            port=available_host.port,
            username=available_host.username,
            password=available_host.password,
            use_ssl=available_host.use_ssl
        )
        
        result = client.create_user(
            username=username,
            password=password,
            description=getattr(request_obj, 'user_description', 'Cloud computer user')
        )
        
        if result.status_code != 0:
            error_msg = result.std_err if result.std_err else 'Unknown error'
            raise Exception(f"创建用户失败: {error_msg}")
        
        task.progress = 70
        task.save()
        
        TaskProgress.objects.create(
            task=task,
            progress=70,
            message="用户创建成功"
        )
        
        request_obj.host = available_host
        request_obj.windows_username = username
        request_obj.windows_password = password
        request_obj.status = 'approved'
        request_obj.save()
        
        cloud_user, created = CloudComputerUser.objects.get_or_create(
            account_opening_request=request_obj,
            defaults={
                'windows_username': username,
                'host': available_host,
                'status': 'active'
            }
        )
        if not created:
            cloud_user.windows_username = username
            cloud_user.host = available_host
            cloud_user.status = 'active'
            cloud_user.save()
        
        task.progress = 90
        task.save()
        
        TaskProgress.objects.create(
            task=task,
            progress=90,
            message="更新请求状态"
        )
        
        task.progress = 100
        task.complete_success({
            'host': available_host.hostname,
            'username': username,
            'success': True,
            'cloud_user_id': cloud_user.id
        })
        
        TaskProgress.objects.create(
            task=task,
            progress=100,
            message="开户请求处理完成"
        )
        
        return {
            'success': True,
            'host': available_host.hostname,
            'username': username,
            'cloud_user_id': cloud_user.id
        }
        
    except Exception as e:
        logger.error(f"处理开户请求失败: {str(e)}", exc_info=True)
        task.complete_failure(str(e))
        
        try:
            rollback_opening_request(request_id)
        except Exception as rollback_error:
            logger.error(f"回滚开户请求失败: {str(rollback_error)}", exc_info=True)
        
        return {
            'success': False,
            'error': str(e)
        }


def rollback_opening_request(request_id):
    try:
        request_obj = AccountOpeningRequest.objects.get(id=request_id)
        if request_obj.host and request_obj.windows_username:
            from utils.winrm_client import WinrmClient
            client = WinrmClient(
                hostname=request_obj.host.hostname,
                port=request_obj.host.port,
                username=request_obj.host.username,
                password=request_obj.host.password,
                use_ssl=request_obj.host.use_ssl
            )
            
            result = client.disabled_user(request_obj.windows_username)
            
            if result.status_code == 0:
                logger.info(f"已禁用用户 {request_obj.windows_username}")
            else:
                logger.warning(f"禁用用户失败: {result.std_err}")
        
        request_obj.status = 'pending'
        request_obj.save()
        
    except Exception as e:
        logger.error(f"回滚操作失败: {str(e)}")


@shared_task(bind=True)
def reset_user_password(self, user_id, operator_id):
    task = AsyncTask.objects.create(
        task_id=self.request.id,
        name=f"重置用户密码 - 用户 #{user_id}",
        created_by_id=operator_id,
        target_object_id=user_id,
        target_content_type='operations.CloudComputerUser',
        status='running'
    )
    
    try:
        user = CloudComputerUser.objects.get(id=user_id)
        task.start_execution()
        
        new_password = generate_secure_password()
        
        from utils.winrm_client import WinrmClient
        client = WinrmClient(
            hostname=user.host.hostname,
            port=user.host.port,
            username=user.host.username,
            password=user.host.password,
            use_ssl=user.host.use_ssl
        )
        
        result = client.reset_password(user.windows_username, new_password)
        
        if result.status_code != 0:
            error_msg = result.std_err if result.std_err else 'Unknown error'
            raise Exception(f"重置密码失败: {error_msg}")
        
        if hasattr(user, 'account_opening_request') and user.account_opening_request:
            user.account_opening_request.windows_password = new_password
            user.account_opening_request.save()
        
        task.progress = 100
        task.complete_success({
            'success': True,
            'message': '密码重置成功',
            'username': user.windows_username
        })
        
        return {
            'success': True,
            'message': '密码重置成功',
            'username': user.windows_username
        }
        
    except Exception as e:
        logger.error(f"重置密码失败: {str(e)}", exc_info=True)
        task.complete_failure(str(e))
        
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(bind=True)
def batch_process_opening_requests(self, request_ids, operator_id):
    task = AsyncTask.objects.create(
        task_id=self.request.id,
        name=f"批量处理开户请求 ({len(request_ids)}个)",
        created_by_id=operator_id,
        status='running'
    )
    
    try:
        task.start_execution()
        
        results = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'errors': []
        }
        
        total_requests = len(request_ids)
        
        for idx, request_id in enumerate(request_ids):
            try:
                progress = int((idx / total_requests) * 80) + 10
                task.progress = progress
                task.save()
                
                result = process_opening_request.delay(request_id, operator_id).get()
                
                results['processed'] += 1
                if result['success']:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'request_id': request_id,
                        'error': result.get('error', 'Unknown error')
                    })
                    
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'request_id': request_id,
                    'error': str(e)
                })
        
        task.progress = 100
        task.complete_success(results)
        
        return results
        
    except Exception as e:
        logger.error(f"批量处理开户请求失败: {str(e)}", exc_info=True)
        task.complete_failure(str(e))
        
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(bind=True)
def cleanup_inactive_users(self, days_inactive=30):
    task = AsyncTask.objects.create(
        task_id=self.request.id,
        name=f"清理非活跃用户 (超过{days_inactive}天未使用)",
        status='running'
    )
    
    try:
        task.start_execution()
        
        from django.utils import timezone
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days_inactive)
        
        inactive_users = CloudComputerUser.objects.filter(
            last_login__lt=cutoff_date,
            status='active'
        )
        
        cleaned_count = 0
        for user in inactive_users:
            from utils.winrm_client import WinrmClient
            client = WinrmClient(
                hostname=user.host.hostname,
                port=user.host.port,
                username=user.host.username,
                password=user.host.password,
                use_ssl=user.host.use_ssl
            )
            
            result = client.disabled_user(user.windows_username)
            
            if result.status_code == 0:
                user.status = 'disabled'
                user.save()
                cleaned_count += 1
            else:
                logger.warning(f"无法禁用用户 {user.windows_username}: {result.std_err}")
        
        task.progress = 100
        task.complete_success({
            'cleaned_users': cleaned_count,
            'total_inactive': inactive_users.count()
        })
        
        return {
            'success': True,
            'cleaned_users': cleaned_count,
            'total_inactive': inactive_users.count()
        }
        
    except Exception as e:
        logger.error(f"清理非活跃用户失败: {str(e)}", exc_info=True)
        task.complete_failure(str(e))
        
        return {
            'success': False,
            'error': str(e)
        }
