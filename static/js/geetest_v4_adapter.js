// geetest_v4_adapter.js
// Adapter for gt4.js to open verification when triggered (on button click)
// - Uses bind mode to attach verification to trigger elements
// - On success, fills hidden inputs: lot_number, captcha_output, pass_token, gen_time, captcha_id
// - Handles form submission with proper validation
// - Also handles email code button verification

(function () {
    function $(sel) { return document.querySelector(sel); }
    function $all(sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); }

    var defaultCaptchaId = window.GEETEST_CAPTCHA_ID || null;
    var captchaInstances = {}; // Store the captcha instances by element

    function initOnTrigger() {
        // find all trigger buttons
        var triggers = $all('[data-geetest-trigger]');
        triggers.forEach(function (btn) {
            var form = btn.closest('form');
            var captchaId = btn.getAttribute('data-captcha-id') || defaultCaptchaId;
            if (!captchaId) {
                console.error('captchaId not provided for Geetest v4');
                return;
            }

            // initialize geetest v4 in bind mode
            initGeetest4({ 
                captchaId: captchaId,
                product: "bind"  // Use bind mode for hidden button
            }, function (captcha) {
                // Store the captcha instance for this button
                captchaInstances[btn] = captcha;

                // Add event listener to the button to trigger the captcha
                btn.addEventListener('click', function(e) {
                    // Check if we already have captcha values filled
                    var passTokenInput = form ? form.querySelector('input[name="pass_token"]') : null;
                    var passTokenValue = passTokenInput ? passTokenInput.value : '';
                    
                    // If we already have captcha values, just submit the form
                    if (passTokenValue) {
                        return; // Let the form submit normally
                    }

                    e.preventDefault(); // Prevent default form submission
                    
                    // Call verify to trigger the verification process in bind mode
                    if (typeof captcha.verify === 'function') {
                        captcha.verify();
                    } else if (typeof captcha.showBox === 'function') {
                        // Fallback to showBox if verify is not available
                        captcha.showBox();
                    } else {
                        // Final fallback: try appendTo method
                        var container = document.getElementById('geetest-v4-popup-container');
                        if (!container) {
                            container = document.createElement('div');
                            container.id = 'geetest-v4-popup-container';
                            container.style.position = 'fixed';
                            container.style.left = '50%';
                            container.style.top = '50%';
                            container.style.transform = 'translate(-50%, -50%)';
                            container.style.zIndex = '2000';
                            container.style.background = 'white';
                            container.style.padding = '10px';
                            container.style.boxShadow = '0 2px 10px rgba(0,0,0,0.2)';
                            document.body.appendChild(container);
                        }

                        // clear container
                        container.innerHTML = '';
                        try {
                            captcha.appendTo('#' + container.id);
                        } catch (err) {
                            // some builds expect a DOM element, so we pass the element
                            captcha.appendTo(container);
                        }
                    }
                });

                // attach success handler
                if (typeof captcha.onSuccess === 'function') {
                    captcha.onSuccess(function () {
                        // v4 exposes getValidate or similar — try common names
                        var result = {};
                        try {
                            // these names depend on geetest version; attempt a few
                            if (typeof captcha.getValidate === 'function') {
                                result = captcha.getValidate();
                            } else if (typeof captcha.getCaptcha === 'function') {
                                result = captcha.getCaptcha();
                            } else if (typeof captcha.getResponse === 'function') {
                                result = captcha.getResponse();
                            } else {
                                // In case methods don't exist, try to get properties directly
                                result = {
                                    lot_number: captcha.lot_number || captcha.lotNumber || captcha.challenge || '',
                                    captcha_output: captcha.captcha_output || captcha.captchaOutput || captcha.validate || '',
                                    pass_token: captcha.pass_token || captcha.passToken || captcha.seccode || '',
                                    gen_time: captcha.gen_time || captcha.genTime || Date.now().toString()
                                };
                            }
                        } catch (e) {
                            console.warn('Cannot read captcha result via helper APIs', e);
                            // Fallback to direct property access
                            result = {
                                lot_number: captcha.lot_number || captcha.lotNumber || captcha.challenge || '',
                                captcha_output: captcha.captcha_output || captcha.captchaOutput || captcha.validate || '',
                                pass_token: captcha.pass_token || captcha.passToken || captcha.seccode || '',
                                gen_time: captcha.gen_time || captcha.genTime || Date.now().toString()
                            };
                        }

                        // Ensure we have the required fields
                        var lot_number = result.lot_number || result.lotNumber || result.lot || '';
                        var captcha_output = result.captcha_output || result.captchaOutput || result.captcha || '';
                        var pass_token = result.pass_token || result.passToken || result.pass || '';
                        var gen_time = result.gen_time || result.genTime || result.gen || '';

                        // If the captcha instance has direct properties
                        lot_number = lot_number || captcha.lot_number || captcha.lotNumber || captcha.challenge || '';
                        captcha_output = captcha_output || captcha.captcha_output || captcha.captchaOutput || captcha.validate || '';
                        pass_token = pass_token || captcha.pass_token || captcha.passToken || captcha.seccode || '';
                        gen_time = gen_time || captcha.gen_time || captcha.genTime || Date.now().toString();

                        // also get captcha_id if available
                        var captcha_id = captchaId; // Use the captchaId from the initialization

                        // Validate that we have essential values
                        if (!lot_number || !captcha_output || !pass_token) {
                            console.error('Missing required Geetest v4 parameters:', { 
                                lot_number: lot_number, 
                                captcha_output: captcha_output, 
                                pass_token: pass_token 
                            });
                            alert('验证码验证失败，请重试');
                            return;
                        }

                        // close popup if exists
                        var container = document.getElementById('geetest-v4-popup-container');
                        if (container) {
                            try { container.remove(); } catch (e) { container.style.display = 'none'; }
                        }

                        // fill hidden inputs if present in the form
                        if (form) {
                            var inLot = form.querySelector('input[name="lot_number"]');
                            var inOutput = form.querySelector('input[name="captcha_output"]');
                            var inPass = form.querySelector('input[name="pass_token"]');
                            var inGen = form.querySelector('input[name="gen_time"]');
                            var inCid = form.querySelector('input[name="captcha_id"]');

                            if (inLot) inLot.value = lot_number;
                            if (inOutput) inOutput.value = captcha_output;
                            if (inPass) inPass.value = pass_token;
                            if (inGen) inGen.value = gen_time;
                            if (inCid) inCid.value = captcha_id;
                        }
                        
                        // Submit the form after filling the captcha fields
                        if (form) form.submit();
                    });
                } else {
                    console.warn('captcha.onSuccess is not a function');
                }

                // Handle error events
                if (typeof captcha.onError === 'function') {
                    captcha.onError(function(error) {
                        console.error('Geetest v4 error:', error);
                        // close popup if exists
                        var container = document.getElementById('geetest-v4-popup-container');
                        if (container) {
                            try { container.remove(); } catch (e) { container.style.display = 'none'; }
                        }
                        alert('验证码加载失败，请稍后重试');
                    });
                }
            });
            
            // Add event listener to form to handle submission
            var form = btn.closest('form');
            if (form) {
                // Override the form submit to check for captcha completion
                form.addEventListener('submit', function(e) {
                    var passTokenInput = form.querySelector('input[name="pass_token"]');
                    var passTokenValue = passTokenInput ? passTokenInput.value : '';
                    
                    // Check if we already have captcha values filled
                    if (!passTokenValue && window.CAPTCHA_PROVIDER === 'geetest') {
                        e.preventDefault(); // Prevent form submission
                        
                        // Trigger the captcha verification by clicking the button
                        btn.click();
                    }
                    // If we have captcha values, let the form submit normally
                });
            }
        });
    }
    
    // Special handling for email code button on register page
    function initEmailCodeButton() {
        if (window.CAPTCHA_PROVIDER === 'geetest') {
            var emailCodeBtn = $('#get-email-code');
            if (emailCodeBtn) {
                // Remove any existing event listeners to avoid conflicts
                var newBtn = emailCodeBtn.cloneNode(true);
                emailCodeBtn.parentNode.replaceChild(newBtn, emailCodeBtn);
                emailCodeBtn = newBtn;

                // Get captchaId from multiple sources to ensure availability
                var captchaId = defaultCaptchaId || 
                               document.getElementById('captcha_id')?.value || 
                               document.querySelector('input[name="captcha_id"]')?.value;
                
                if (!captchaId) {
                    console.error('captchaId not provided for Geetest v4 on email code button');
                    return;
                }

                // initialize geetest v4 for email code button
                initGeetest4({ 
                    captchaId: captchaId,
                    product: "bind"  // Use bind mode for hidden button
                }, function (captcha) {
                    // Store the captcha instance for this button
                    captchaInstances[emailCodeBtn] = captcha;

                    // Add event listener to the email code button to trigger the captcha
                    emailCodeBtn.addEventListener('click', function(e) {
                        e.preventDefault(); // Prevent default action
                        
                        // Call verify to trigger the verification process in bind mode
                        if (typeof captcha.verify === 'function') {
                            captcha.verify();
                        } else if (typeof captcha.showBox === 'function') {
                            // Fallback to showBox if verify is not available
                            captcha.showBox();
                        } else {
                            // Final fallback: try appendTo method
                            var container = document.getElementById('geetest-v4-popup-container');
                            if (!container) {
                                container = document.createElement('div');
                                container.id = 'geetest-v4-popup-container';
                                container.style.position = 'fixed';
                                container.style.left = '50%';
                                container.style.top = '50%';
                                container.style.transform = 'translate(-50%, -50%)';
                                container.style.zIndex = '2000';
                                container.style.background = 'white';
                                container.style.padding = '10px';
                                container.style.boxShadow = '0 2px 10px rgba(0,0,0,0.2)';
                                document.body.appendChild(container);
                            }

                            // clear container
                            container.innerHTML = '';
                            try {
                                captcha.appendTo('#' + container.id);
                            } catch (err) {
                                // some builds expect a DOM element, so we pass the element
                                captcha.appendTo(container);
                            }
                        }
                    });

                    // attach success handler for email code verification
                    if (typeof captcha.onSuccess === 'function') {
                        captcha.onSuccess(function () {
                            // v4 exposes getValidate or similar — try common names
                            var result = {};
                            try {
                                // these names depend on geetest version; attempt a few
                                if (typeof captcha.getValidate === 'function') {
                                    result = captcha.getValidate();
                                } else if (typeof captcha.getCaptcha === 'function') {
                                    result = captcha.getCaptcha();
                                } else if (typeof captcha.getResponse === 'function') {
                                    result = captcha.getResponse();
                                } else {
                                    // In case methods don't exist, try to get properties directly
                                    result = {
                                        lot_number: captcha.lot_number || captcha.lotNumber || captcha.challenge || '',
                                        captcha_output: captcha.captcha_output || captcha.captchaOutput || captcha.validate || '',
                                        pass_token: captcha.pass_token || captcha.passToken || captcha.seccode || '',
                                        gen_time: captcha.gen_time || captcha.genTime || Date.now().toString()
                                    };
                                }
                            } catch (e) {
                                console.warn('Cannot read captcha result via helper APIs', e);
                                // Fallback to direct property access
                                result = {
                                    lot_number: captcha.lot_number || captcha.lotNumber || captcha.challenge || '',
                                    captcha_output: captcha.captcha_output || captcha.captchaOutput || captcha.validate || '',
                                    pass_token: captcha.pass_token || captcha.passToken || captcha.seccode || '',
                                    gen_time: captcha.gen_time || captcha.genTime || Date.now().toString()
                                };
                            }

                            // Ensure we have the required fields
                            var lot_number = result.lot_number || result.lotNumber || result.lot || '';
                            var captcha_output = result.captcha_output || result.captchaOutput || result.captcha || '';
                            var pass_token = result.pass_token || result.passToken || result.pass || '';
                            var gen_time = result.gen_time || result.genTime || result.gen || '';

                            // If the captcha instance has direct properties
                            lot_number = lot_number || captcha.lot_number || captcha.lotNumber || captcha.challenge || '';
                            captcha_output = captcha_output || captcha.captcha_output || captcha.captchaOutput || captcha.validate || '';
                            pass_token = pass_token || captcha.pass_token || captcha.passToken || captcha.seccode || '';
                            gen_time = gen_time || captcha.gen_time || captcha.genTime || Date.now().toString();

                            // also get captcha_id if available
                            var captcha_id = captchaId; // Use the captchaId from the initialization

                            // Validate that we have essential values
                            if (!lot_number || !captcha_output || !pass_token) {
                                console.error('Missing required Geetest v4 parameters for email code:', { 
                                    lot_number: lot_number, 
                                    captcha_output: captcha_output, 
                                    pass_token: pass_token 
                                });
                                alert('验证码验证失败，请重试');
                                return;
                            }

                            // close popup if exists
                            var container = document.getElementById('geetest-v4-popup-container');
                            if (container) {
                                try { container.remove(); } catch (e) { container.style.display = 'none'; }
                            }

                            // Get the email address
                            var emailInput = document.querySelector('input[name="email"]');
                            var email = emailInput ? emailInput.value : '';
                            
                            if (!email) {
                                alert('请先输入邮箱地址');
                                return;
                            }

                            // Make AJAX request to send email code
                            var xhr = new XMLHttpRequest();
                            var formData = new FormData();
                            formData.append('email', email);
                            formData.append('lot_number', lot_number);
                            formData.append('captcha_output', captcha_output);
                            formData.append('pass_token', pass_token);
                            formData.append('gen_time', gen_time);
                            formData.append('captcha_id', captcha_id);

                            xhr.open('POST', '/accounts/email/send-code/', true);
                            xhr.setRequestHeader('X-CSRFToken', window.getCsrfToken ? window.getCsrfToken() : (document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''));
                            
                            xhr.onreadystatechange = function() {
                                if (xhr.readyState === 4) {
                                    if (xhr.status === 200) {
                                        var response = JSON.parse(xhr.responseText);
                                        if (response.status === 'ok') {
                                            alert('验证码已发送，请查收邮件');
                                            // Disable the button temporarily with countdown - using consistent format
                                            emailCodeBtn.disabled = true;
                                            var originalText = emailCodeBtn.textContent.replace(/\s*\(\d+s\)$/, ''); // Remove any existing countdown text
                                            var countdown = 60;
                                            var timer = setInterval(function() {
                                                emailCodeBtn.textContent = originalText + ` (${countdown}s)`;
                                                countdown--;
                                                if (countdown < 0) {
                                                    clearInterval(timer);
                                                    emailCodeBtn.disabled = false;
                                                    emailCodeBtn.textContent = originalText;
                                                }
                                            }, 1000);
                                        } else {
                                            // Re-enable button on failure
                                            emailCodeBtn.disabled = false;
                                            var originalText = emailCodeBtn.textContent.replace(/\s*\(\d+s\)$/, ''); // Remove any existing countdown text
                                            emailCodeBtn.textContent = originalText;
                                            alert('发送失败: ' + (response.message || '未知错误'));
                                        }
                                    } else {
                                        // Re-enable button on failure
                                        emailCodeBtn.disabled = false;
                                        var originalText = emailCodeBtn.textContent.replace(/\s*\(\d+s\)$/, ''); // Remove any existing countdown text
                                        emailCodeBtn.textContent = originalText;
                                        alert('发送失败: 请稍后重试');
                                    }
                                }
                            };
                            
                            xhr.send(formData);
                        });
                    } else {
                        console.warn('captcha.onSuccess is not a function for email code button');
                    }

                    // Handle error events for email code button
                    if (typeof captcha.onError === 'function') {
                        captcha.onError(function(error) {
                            console.error('Geetest v4 error on email code button:', error);
                            // close popup if exists
                            var container = document.getElementById('geetest-v4-popup-container');
                            if (container) {
                                try { container.remove(); } catch (e) { container.style.display = 'none'; }
                            }
                            alert('验证码加载失败，请稍后重试');
                        });
                    }
                });
            }
        }
    }

    // Make functions globally accessible for manual initialization if needed
    window.initGeetestAdapter = {
        initOnTrigger: initOnTrigger,
        initEmailCodeButton: initEmailCodeButton
    };
    
    // auto init on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            initOnTrigger();
            initEmailCodeButton();
        });
    } else {
        initOnTrigger();
        initEmailCodeButton();
    }
})();