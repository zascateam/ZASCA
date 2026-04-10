// email_code.js
// Handles "Get code" button on registration and forgot password pages.
// If CAPTCHA_PROVIDER == 'geetest', it will open geetest popup via initGeetest4 and then POST v4 params + email to /accounts/email/send-code/ or /accounts/email/send-forgot-password-code/
// Otherwise, it will POST only the email to the endpoint.

(function(){
    function qs(sel){ return document.querySelector(sel); }
    var btn = qs('#get-email-code');
    if(!btn) return;

    // 倒计时功能
    var countdownTimers = {};
    
    function startCountdown(button, initialText = null) {
        var buttonId = button.id || 'unknown-button';
        
        // 清除之前的倒计时
        if (countdownTimers[buttonId]) {
            clearInterval(countdownTimers[buttonId]);
        }
        
        let count = 60;
        const originalText = initialText || button.textContent || button.innerText;
        button.disabled = true;
        
        // 更新按钮文本显示倒计时
        button.textContent = `${originalText} (${count}s)`;
        
        countdownTimers[buttonId] = setInterval(() => {
            count--;
            button.textContent = `${originalText} (${count}s)`;
            
            if (count <= 0) {
                clearInterval(countdownTimers[buttonId]);
                delete countdownTimers[buttonId];
                button.disabled = false;
                button.textContent = originalText;
            }
        }, 1000);
    }

    btn.addEventListener('click', function(e){
        e.preventDefault();
        var emailInput = document.querySelector('input[name="email"]') || document.querySelector('input[type="email"]');
        var email = emailInput && emailInput.value && emailInput.value.trim();
        if(!email){ alert('请先输入邮箱'); return; }

        // Check if we're on the forgot password page
        var isForgotPassword = window.location.pathname.includes('forgot-password');
        var endpoint = isForgotPassword ? '/accounts/email/send-forgot-password-code/' : '/accounts/email/send-code/';

        // CAPTCHA_PROVIDER is injected in template context as CAPTCHA_PROVIDER
        var provider = window.CAPTCHA_PROVIDER || document.body.getAttribute('data-captcha-provider') || 'none';

        function postCode(payload, buttonRef){
            fetch(endpoint, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': window.getCsrfToken ? window.getCsrfToken() : (document.querySelector('[name=csrfmiddlewaretoken]')?.value || '')
                },
                body: payload
            }).then(function(resp){
                if(resp.ok) {
                    alert('验证码已发送，请注意查收');
                    // 开始倒计时
                    if(buttonRef) {
                        startCountdown(buttonRef, '获取验证码');
                    }
                } else {
                    // 请求失败时恢复按钮状态
                    if(buttonRef) {
                        buttonRef.disabled = false;
                        buttonRef.textContent = '获取验证码';
                    }
                    resp.json().then(function(j){ alert('发送失败：' + (j.message || JSON.stringify(j))); }).catch(function(){ alert('发送失败'); });
                }
            }).catch(function(err){ 
                console.error(err); 
                // 请求失败时恢复按钮状态
                if(buttonRef) {
                    buttonRef.disabled = false;
                    buttonRef.textContent = '获取验证码';
                }
                alert('网络错误'); 
            });
        }

        if(provider === 'geetest'){
            // show geetest popup, use adapter's mechanism: initGeetest4 and onSuccess
            initGeetest4({ captchaId: window.GEETEST_CAPTCHA_ID || window.GEETEST_CAPTCHA_ID || (document.getElementById('captcha_id') && document.getElementById('captcha_id').value) }, function(captcha){
                var container = document.getElementById('geetest-email-popup');
                if(!container){ container = document.createElement('div'); container.id='geetest-email-popup'; document.body.appendChild(container);}
                container.innerHTML = '';
                try{ captcha.appendTo(container); } catch(e){ captcha.appendTo('#' + container.id); }
                if(typeof captcha.onSuccess === 'function'){
                    captcha.onSuccess(function(){
                        var res = null;
                        try{ if(typeof captcha.getValidate === 'function') res = captcha.getValidate(); else if(typeof captcha.getResponse === 'function') res = captcha.getResponse(); }catch(e){}
                        var form = new FormData();
                        form.append('email', email);
                        if(res){
                            form.append('lot_number', res.lot_number || res.lotNumber || '');
                            form.append('captcha_output', res.captcha_output || res.captchaOutput || '');
                            form.append('pass_token', res.pass_token || res.passToken || '');
                            form.append('gen_time', res.gen_time || res.genTime || '');
                            form.append('captcha_id', document.getElementById('captcha_id') ? document.getElementById('captcha_id').value : '');
                        }
                        postCode(form, btn); // Pass button reference for countdown
                        try{ container.remove(); } catch(e){ container.style.display='none'; }
                    });
                } else {
                    alert('当前验证码组件不支持回调，请刷新页面');
                }
            });
        } else if(provider === 'local') {
            // 如果是本地验证码，不应该到达这里，因为local_captcha_adapter.js会处理
            // 但为了兼容性，我们也可以处理
            alert('本地验证码需要先完成验证');
        } else {
            if(provider === 'turnstile'){
                var sitekey = window.TURNSTILE_SITE_KEY || (document.getElementById('turnstile_site_key') && document.getElementById('turnstile_site_key').value);
                if(!sitekey){ alert('Turnstile site key 未配置'); return; }
                // execute turnstile
                if(typeof window.executeTurnstile === 'function'){
                    window.executeTurnstile(sitekey, function(err, token){
                        if(err){ alert('Turnstile 验证失败'); return; }
                        var fd = new FormData(); fd.append('email', email); fd.append('cf-turnstile-response', token);
                        postCode(fd, btn); // Pass button reference for countdown
                    });
                } else {
                    alert('Turnstile adapter 未加载');
                }
            } else {
                var fd = new FormData(); fd.append('email', email);
                postCode(fd, btn); // Pass button reference for countdown
            }
        }
    });
})();