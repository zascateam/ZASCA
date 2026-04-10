from celery import shared_task
from django.contrib.auth.models import User
from apps.hosts.models import Host
from apps.tasks.models import AsyncTask
from apps.certificates.models import ServerCertificate, ClientCertificate
import logging
import re

logger = logging.getLogger(__name__)

CERT_THUMBPRINT_PATTERN = re.compile(r'^[A-Fa-f0-9]{40}$')
CERT_FILENAME_PATTERN = re.compile(r'^[a-zA-Z0-9_\-\.]{1,255}\.pem$')


def validate_cert_thumbprint(thumbprint: str) -> str:
    if not thumbprint:
        raise ValueError("证书指纹不能为空")
    thumbprint = thumbprint.strip().upper()
    if not CERT_THUMBPRINT_PATTERN.match(thumbprint):
        raise ValueError("证书指纹格式无效，必须是40位十六进制字符")
    return thumbprint


def validate_cert_filename(filename: str) -> str:
    if not filename:
        raise ValueError("证书文件名不能为空")
    if not CERT_FILENAME_PATTERN.match(filename):
        raise ValueError("证书文件名格式无效，只允许字母、数字、下划线、连字符和点，且必须以.pem结尾")
    return filename


def validate_cert_content(content: str) -> str:
    if not content:
        raise ValueError("证书内容不能为空")
    if '@"' in content or '"@' in content:
        raise ValueError("证书内容包含非法字符")
    if len(content) > 100000:
        raise ValueError("证书内容过长")
    return content


@shared_task(bind=True)
def configure_winrm_on_host(self, host_id, cert_thumbprint=None, operator_id=None):
    task = AsyncTask.objects.create(
        task_id=self.request.id,
        name=f"配置WinRM - 主机 #{host_id}",
        created_by_id=operator_id,
        target_object_id=host_id,
        target_content_type='hosts.Host',
        status='running'
    )
    
    try:
        host = Host.objects.get(id=host_id)
        task.start_execution()
        
        task.progress = 10
        task.save()
        
        try:
            from utils.winrm_client import WinrmClient
            
            client = WinrmClient(
                hostname=host.hostname or host.ip_address,
                port=host.port,
                username=host.username,
                password=host.password,
                use_ssl=host.use_ssl
            )
            
            actual_thumbprint = cert_thumbprint or host.certificate_thumbprint
            if actual_thumbprint:
                actual_thumbprint = validate_cert_thumbprint(actual_thumbprint)
            
            ps_script = '''
            Enable-PSRemoting -Force
            Set-Service -Name WinRM -StartupType Automatic
            '''
            
            if actual_thumbprint:
                ps_script += f'''
                $selectorset = @{{Transport="HTTPS"}}
                $resourceset = @{{Port="5986"; CertificateThumbprint="{actual_thumbprint}"}}
                Get-WSManInstance -ResourceURI winrm/config/listener -SelectorSet $selectorset -ErrorAction SilentlyContinue | Remove-WSManInstance -ErrorAction SilentlyContinue
                New-WSManInstance -ResourceURI winrm/config/listener -SelectorSet $selectorset -ValueSet $resourceset
                if (-not (Get-NetFirewallRule -Name "WinRM-HTTPS-In-TCP-Public" -ErrorAction SilentlyContinue)) {{
                    New-NetFirewallRule -Name "WinRM-HTTPS-In-TCP-Public" -DisplayName "WinRM HTTPS Inbound" -Enabled True -Direction Inbound -Protocol TCP -LocalPort 5986 -Action Allow -Profile Public,Private,Domain
                }}
                '''
            
            ps_script += '''
            Set-Item -Path "WSMan:\\localhost\\Service\\AllowUnencrypted" -Value $false
            Set-Item -Path "WSMan:\\localhost\\Service\\Auth\\Basic" -Value $true
            Restart-Service WinRM
            '''
            
            task.progress = 30
            task.save()
            
            result = client.execute_powershell(ps_script)
            
            if result.status_code == 0:
                task.progress = 80
                task.save()
                
                from django.utils import timezone
                host.init_status = 'ready'
                host.initialized_at = timezone.now()
                if cert_thumbprint:
                    host.certificate_thumbprint = cert_thumbprint
                host.save()
                
                task.progress = 100
                task.complete_success({
                    'status_code': result.status_code,
                    'stdout': result.std_out,
                    'success': True
                })
                
                return {
                    'success': True,
                    'status_code': result.status_code,
                    'host_id': host_id
                }
            else:
                error_msg = result.std_err if result.std_err else 'Unknown error'
                task.complete_failure(f"PowerShell script failed: {error_msg}")
                
                return {
                    'success': False,
                    'status_code': result.status_code,
                    'error': error_msg
                }
                
        except Exception as conn_error:
            logger.error(f"连接主机失败: {str(conn_error)}", exc_info=True)
            task.complete_failure(f"无法连接到主机: {str(conn_error)}")
            
            return {
                'success': False,
                'error': str(conn_error)
            }
        
    except Exception as e:
        logger.error(f"配置WinRM失败: {str(e)}", exc_info=True)
        task.complete_failure(str(e))
        
        return {
            'success': False,
            'error': str(e)
        }


@shared_task(bind=True)
def test_winrm_connection(self, host_id, use_certificate_auth=False):
    task = AsyncTask.objects.create(
        task_id=self.request.id,
        name=f"测试WinRM连接 - 主机 #{host_id}",
        status='running'
    )
    
    try:
        host = Host.objects.get(id=host_id)
        task.start_execution()
        
        if use_certificate_auth and host.certificate_thumbprint:
            import tempfile
            import os
            
            client_cert = ClientCertificate.objects.filter(is_active=True).first()
            if not client_cert:
                from apps.certificates.models import CertificateAuthority
                ca = host.get_ca() if hasattr(host, 'get_ca') else None
                if not ca:
                    ca, _ = CertificateAuthority.objects.get_or_create(
                        name='default-ca',
                        defaults={'name': 'default-ca', 'description': 'Default Certificate Authority'}
                    )
                    if not ca.certificate:
                        ca.generate_self_signed_cert()
                        ca.save()
                
                client_cert = ClientCertificate(
                    name=f'client-{host.hostname}',
                    ca=ca
                )
                client_cert.generate_client_cert(f'client-{host.hostname}')
                client_cert.save()
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pem') as cert_file:
                cert_file.write(client_cert.certificate)
                cert_file_path = cert_file.name
            
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pem') as key_file:
                key_file.write(client_cert.private_key)
                key_file_path = key_file.name
            
            try:
                from utils.winrm_client import WinrmClient
                client = WinrmClient(
                    hostname=host.hostname or host.ip_address,
                    port=5986,
                    username='',
                    password='',
                    use_ssl=True,
                    server_cert_validation='validate',
                    client_cert_pem=cert_file_path,
                    client_cert_key=key_file_path
                )
                
                result = client.execute_command('echo', ['Connection Test'])
                success = result.status_code == 0
                
            finally:
                os.unlink(cert_file_path)
                os.unlink(key_file_path)
        else:
            from utils.winrm_client import WinrmClient
            client = WinrmClient(
                hostname=host.hostname or host.ip_address,
                port=host.port,
                username=host.username,
                password=host.password,
                use_ssl=host.use_ssl
            )
            
            result = client.execute_command('echo', ['Connection Test'])
            success = result.status_code == 0
        
        if success:
            task.progress = 100
            task.complete_success({
                'connected': True,
                'protocol': 'HTTPS with Certificate' if use_certificate_auth else 'HTTP with Basic Auth',
                'message': 'Connection successful'
            })
            
            return {
                'success': True,
                'connected': True,
                'protocol': 'HTTPS with Certificate' if use_certificate_auth else 'HTTP with Basic Auth'
            }
        else:
            task.complete_failure("Connection test failed")
            return {
                'success': False,
                'connected': False,
                'error': 'Connection test returned non-zero exit code'
            }
        
    except Exception as e:
        logger.error(f"测试WinRM连接失败: {str(e)}", exc_info=True)
        task.complete_failure(str(e))
        
        return {
            'success': False,
            'connected': False,
            'error': str(e)
        }


@shared_task(bind=True)
def install_certificates_on_host(self, host_id, cert_pem, cert_filename, operator_id=None):
    task = AsyncTask.objects.create(
        task_id=self.request.id,
        name=f"安装证书 - 主机 #{host_id}",
        created_by_id=operator_id,
        target_object_id=host_id,
        target_content_type='hosts.Host',
        status='running'
    )
    
    try:
        host = Host.objects.get(id=host_id)
        task.start_execution()
        
        cert_filename = validate_cert_filename(cert_filename)
        cert_pem = validate_cert_content(cert_pem)
        
        from utils.winrm_client import WinrmClient, _escape_for_here_string
        
        client = WinrmClient(
            hostname=host.hostname or host.ip_address,
            port=host.port,
            username=host.username,
            password=host.password,
            use_ssl=host.use_ssl
        )
        
        safe_cert_content = _escape_for_here_string(cert_pem)
        safe_filename = cert_filename.replace('"', '').replace("'", '').replace(';', '')
        
        ps_script = f'''
        $tempDir = "$env:TEMP\\ZASCA_Certs"
        if (!(Test-Path $tempDir)) {{
            New-Item -ItemType Directory -Path $tempDir -Force
        }}
        
        $certContent = @"
{safe_cert_content}
"@
        
        $certPath = Join-Path $tempDir "{safe_filename}"
        $certContent | Out-File -FilePath $certPath -Encoding UTF8
        
        Import-Certificate -FilePath $certPath -CertStoreLocation Cert:\\LocalMachine\\Root
        Import-Certificate -FilePath $certPath -CertStoreLocation Cert:\\LocalMachine\\My
        
        Write-Output "Certificate installed successfully"
        
        Remove-Item $tempDir -Recurse -Force
        '''
        
        result = client.execute_powershell(ps_script)
        
        if result.status_code == 0:
            task.progress = 100
            task.complete_success({
                'installed': True,
                'cert_filename': cert_filename,
                'output': result.std_out
            })
            
            return {
                'success': True,
                'installed': True
            }
        else:
            error_msg = result.std_err if result.std_err else 'Unknown error'
            task.complete_failure(f"Certificate installation failed: {error_msg}")
            
            return {
                'success': False,
                'installed': False,
                'error': error_msg
            }
        
    except Exception as e:
        logger.error(f"安装证书失败: {str(e)}", exc_info=True)
        task.complete_failure(str(e))
        
        return {
            'success': False,
            'error': str(e)
        }
