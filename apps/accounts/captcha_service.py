import logging
from typing import Tuple, Optional
from django.http import HttpRequest
from . import geetest_utils, captcha_utils

logger = logging.getLogger(__name__)


class CaptchaValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class CaptchaService:

    @staticmethod
    def validate_captcha(
        request: HttpRequest,
        scene: str,
        raise_exception: bool = False
    ) -> Tuple[bool, Optional[str]]:
        from apps.dashboard.models import SystemConfig

        provider, _, _ = SystemConfig.get_config().get_captcha_config(scene=scene)

        try:
            if provider == 'geetest':
                return CaptchaService._validate_geetest(request)
            elif provider == 'turnstile':
                return CaptchaService._validate_turnstile(request)
            elif provider == 'local':
                return CaptchaService._validate_local_captcha(request)
            else:
                logger.debug(f"No captcha validation required for scene '{scene}', provider: {provider}")
                return True, None
        except CaptchaValidationError as e:
            if raise_exception:
                raise
            return False, e.message

    @staticmethod
    def _validate_geetest(request: HttpRequest) -> Tuple[bool, Optional[str]]:
        lot_number = request.POST.get('lot_number')
        captcha_output = request.POST.get('captcha_output')
        pass_token = request.POST.get('pass_token')
        gen_time = request.POST.get('gen_time')
        captcha_id = request.POST.get('captcha_id')

        if not all([lot_number, captcha_output, pass_token, gen_time]):
            logger.warning(f"Geetest validation failed: missing parameters - lot_number={lot_number}, captcha_output={captcha_output}, pass_token={pass_token}, gen_time={gen_time}")
            raise CaptchaValidationError('请完成验证码验证')

        ok, resp = geetest_utils.verify_geetest_v4(
            lot_number, captcha_output, pass_token, gen_time, captcha_id=captcha_id
        )

        if not ok:
            logger.warning(f"Geetest validation failed: {resp}")
            raise CaptchaValidationError('验证码校验失败')

        logger.info("Geetest validation succeeded")
        return True, None

    @staticmethod
    def _validate_turnstile(request: HttpRequest) -> Tuple[bool, Optional[str]]:
        tf_token = request.POST.get('cf-turnstile-response') or request.POST.get('turnstile_token')

        if not tf_token:
            logger.warning("Turnstile validation failed: missing token")
            raise CaptchaValidationError('请完成 Turnstile 验证')

        ok, resp = geetest_utils.verify_turnstile(
            tf_token, remoteip=request.META.get('REMOTE_ADDR')
        )

        if not ok:
            logger.warning(f"Turnstile validation failed: {resp}")
            raise CaptchaValidationError('Turnstile 验证失败')

        logger.info("Turnstile validation succeeded")
        return True, None

    @staticmethod
    def _validate_local_captcha(request: HttpRequest) -> Tuple[bool, Optional[str]]:
        lot_number = request.POST.get('lot_number')
        captcha_input = request.POST.get('captcha_output')

        if not all([lot_number, captcha_input]):
            logger.warning(f"Local captcha validation failed: missing parameters - lot_number={lot_number}, captcha_input={captcha_input}")
            raise CaptchaValidationError('请完成验证码验证')

        is_valid = captcha_utils.verify_captcha(
            lot_number, captcha_input, consume=True, check_attempts=True
        )

        if not is_valid:
            logger.warning(f"Local captcha validation failed: lot_number={lot_number}")
            raise CaptchaValidationError('本地验证码校验失败')

        logger.info(f"Local captcha validation succeeded: lot_number={lot_number}")
        return True, None


def validate_captcha(request: HttpRequest, scene: str) -> Tuple[bool, Optional[str]]:
    return CaptchaService.validate_captcha(request, scene, raise_exception=False)
