/**
 * 用户账户JavaScript功能
 */

// 认证管理器
const Auth = {
    /**
     * 初始化认证功能
     */
    init() {
        this.bindEvents();
        this.initForms();
    },

    /**
     * 绑定事件
     */
    bindEvents() {
        // 登录表单
        const loginForm = document.getElementById('login-form');
        if (loginForm) {
            loginForm.addEventListener('submit', (e) => {
                this.handleLogin(e);
            });
        }

        // 注册表单
        const registerForm = document.getElementById('register-form');
        if (registerForm) {
            registerForm.addEventListener('submit', (e) => {
                this.handleRegister(e);
            });
        }

        // 忘记密码表单
        const forgotPasswordForm = document.getElementById('forgot-password-form');
        if (forgotPasswordForm) {
            forgotPasswordForm.addEventListener('submit', (e) => {
                this.handleForgotPassword(e);
            });
        }

        // 重置密码表单
        const resetPasswordForm = document.getElementById('reset-password-form');
        if (resetPasswordForm) {
            resetPasswordForm.addEventListener('submit', (e) => {
                this.handleResetPassword(e);
            });
        }

        // 退出登录按钮
        const logoutBtn = document.getElementById('logout-btn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', (e) => {
                e.preventDefault();
                this.handleLogout();
            });
        }
    },

    /**
     * 初始化表单
     */
    initForms() {
        // 初始化表单验证
        this.initFormValidation();
    },

    /**
     * 初始化表单验证
     */
    initFormValidation() {
        const forms = document.querySelectorAll('.needs-validation');
        forms.forEach(form => {
            form.addEventListener('submit', event => {
                if (!form.checkValidity()) {
                    event.preventDefault();
                    event.stopPropagation();
                }
                form.classList.add('was-validated');
            }, false);
        });
    },

    /**
     * 处理登录
     */
    async handleLogin(event) {
        event.preventDefault();

        const form = event.target;
        if (!form.checkValidity()) {
            return;
        }

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        try {
            Utils.showLoading();

            const response = await fetch(form.action, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': Config.csrfToken,
                },
                body: formData,
            });

            if (response.ok) {
                // 登录成功，重定向到指定页面或首页
                const redirectUrl = new URLSearchParams(window.location.search).get('next') || '/';
                window.location.href = redirectUrl;
            } else {
                const errorData = await response.json();
                Utils.showAlert(errorData.message || '登录失败，请检查用户名和密码', 'danger');
            }
        } catch (error) {
            console.error('Login error:', error);
            Utils.showAlert('登录失败，请稍后重试', 'danger');
        } finally {
            Utils.hideLoading();
        }
    },

    /**
     * 处理注册
     */
    async handleRegister(event) {
        event.preventDefault();

        const form = event.target;
        if (!form.checkValidity()) {
            return;
        }

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        // 验证密码
        if (data.password1 !== data.password2) {
            Utils.showAlert('两次输入的密码不一致', 'danger');
            return;
        }

        try {
            Utils.showLoading();

            const response = await API.post('/accounts/api/register/', data);

            if (response.status === 'success') {
                Utils.showAlert('注册成功，请登录', 'success');
                setTimeout(() => {
                    window.location.href = '/accounts/login/';
                }, 1500);
            } else {
                Utils.showAlert(response.message || '注册失败，请稍后重试', 'danger');
            }
        } catch (error) {
            console.error('Register error:', error);
            Utils.showAlert('注册失败，请稍后重试', 'danger');
        } finally {
            Utils.hideLoading();
        }
    },

    /**
     * 处理忘记密码
     */
    async handleForgotPassword(event) {
        event.preventDefault();

        const form = event.target;
        if (!form.checkValidity()) {
            return;
        }

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        try {
            Utils.showLoading();

            const response = await API.post('/accounts/api/forgot-password/', data);

            if (response.status === 'success') {
                Utils.showAlert('重置密码链接已发送到您的邮箱', 'success');
                form.reset();
            } else {
                Utils.showAlert(response.message || '发送失败，请稍后重试', 'danger');
            }
        } catch (error) {
            console.error('Forgot password error:', error);
            Utils.showAlert('发送失败，请稍后重试', 'danger');
        } finally {
            Utils.hideLoading();
        }
    },

    /**
     * 处理重置密码
     */
    async handleResetPassword(event) {
        event.preventDefault();

        const form = event.target;
        if (!form.checkValidity()) {
            return;
        }

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        // 验证密码
        if (data.password !== data.confirm_password) {
            Utils.showAlert('两次输入的密码不一致', 'danger');
            return;
        }

        try {
            Utils.showLoading();

            const response = await API.post('/accounts/api/reset-password/', data);

            if (response.status === 'success') {
                Utils.showAlert('密码重置成功，请使用新密码登录', 'success');
                setTimeout(() => {
                    window.location.href = '/accounts/login/';
                }, 1500);
            } else {
                Utils.showAlert(response.message || '重置失败，请稍后重试', 'danger');
            }
        } catch (error) {
            console.error('Reset password error:', error);
            Utils.showAlert('重置失败，请稍后重试', 'danger');
        } finally {
            Utils.hideLoading();
        }
    },

    /**
     * 处理退出登录
     */
    async handleLogout() {
        if (!Utils.confirm('确定要退出登录吗？')) {
            return;
        }

        try {
            Utils.showLoading();

            await fetch('/accounts/logout/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': Config.csrfToken,
                },
            });

            window.location.href = '/accounts/login/';
        } catch (error) {
            console.error('Logout error:', error);
            Utils.showAlert('退出失败，请稍后重试', 'danger');
            Utils.hideLoading();
        }
    }
};

// 用户资料管理器
const Profile = {
    /**
     * 初始化用户资料
     */
    init() {
        this.bindEvents();
        this.initAvatarUpload();
    },

    /**
     * 绑定事件
     */
    bindEvents() {
        // 资料表单
        const profileForm = document.getElementById('profile-form');
        if (profileForm) {
            profileForm.addEventListener('submit', (e) => {
                this.handleProfileUpdate(e);
            });
        }

        // 密码修改表单
        const passwordForm = document.getElementById('password-form');
        if (passwordForm) {
            passwordForm.addEventListener('submit', (e) => {
                this.handlePasswordChange(e);
            });
        }

        // 头像上传按钮
        const avatarUploadBtn = document.getElementById('avatar-upload-btn');
        if (avatarUploadBtn) {
            avatarUploadBtn.addEventListener('click', () => {
                document.getElementById('avatar-input').click();
            });
        }
    },

    /**
     * 初始化头像上传
     */
    initAvatarUpload() {
        const avatarInput = document.getElementById('avatar-input');
        if (avatarInput) {
            avatarInput.addEventListener('change', (e) => {
                this.handleAvatarUpload(e);
            });
        }
    },

    /**
     * 处理资料更新
     */
    async handleProfileUpdate(event) {
        event.preventDefault();

        const form = event.target;
        if (!form.checkValidity()) {
            return;
        }

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        try {
            Utils.showLoading();

            const response = await API.post('/accounts/api/profile/update/', data);

            if (response.status === 'success') {
                Utils.showAlert('资料更新成功', 'success');
            } else {
                Utils.showAlert(response.message || '更新失败，请稍后重试', 'danger');
            }
        } catch (error) {
            console.error('Profile update error:', error);
            Utils.showAlert('更新失败，请稍后重试', 'danger');
        } finally {
            Utils.hideLoading();
        }
    },

    /**
     * 处理密码修改
     */
    async handlePasswordChange(event) {
        event.preventDefault();

        const form = event.target;
        if (!form.checkValidity()) {
            return;
        }

        const formData = new FormData(form);
        const data = Object.fromEntries(formData.entries());

        // 验证新密码
        if (data.new_password !== data.confirm_password) {
            Utils.showAlert('两次输入的新密码不一致', 'danger');
            return;
        }

        try {
            Utils.showLoading();

            const response = await API.post('/accounts/api/password/change/', data);

            if (response.status === 'success') {
                Utils.showAlert('密码修改成功，请重新登录', 'success');
                form.reset();
                setTimeout(() => {
                    window.location.href = '/accounts/login/';
                }, 1500);
            } else {
                Utils.showAlert(response.message || '修改失败，请稍后重试', 'danger');
            }
        } catch (error) {
            console.error('Password change error:', error);
            Utils.showAlert('修改失败，请稍后重试', 'danger');
        } finally {
            Utils.hideLoading();
        }
    },

    /**
     * 处理通知设置更新
     */
    async handleNotificationUpdate(event) {
        event.preventDefault();

        const form = event.target;
        const formData = new FormData(form);

        try {
            Utils.showLoading();

            const response = await fetch(window.location.href, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                },
                body: formData
            });

            if (response.ok) {
                Utils.showAlert('通知设置更新成功', 'success');
            } else {
                Utils.showAlert('设置更新失败，请稍后重试', 'danger');
            }
        } catch (error) {
            console.error('Notification update error:', error);
            Utils.showAlert('设置更新失败，请稍后重试', 'danger');
        } finally {
            Utils.hideLoading();
        }
    },

    /**
     * 处理头像上传
     */
    async handleAvatarUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        // 验证文件类型
        const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif'];
        if (!allowedTypes.includes(file.type.toLowerCase())) {
            Utils.showAlert('请选择JPG、PNG或GIF格式的图片文件', 'danger');
            return;
        }

        // 验证文件大小（限制为5MB，与后端保持一致）
        if (file.size > 5 * 1024 * 1024) {
            Utils.showAlert('图片大小不能超过5MB', 'danger');
            return;
        }

        // 验证文件扩展名
        const fileName = file.name.toLowerCase();
        const allowedExtensions = ['.jpg', '.jpeg', '.png', '.gif'];
        const hasValidExtension = allowedExtensions.some(ext => fileName.endsWith(ext));
        
        if (!hasValidExtension) {
            Utils.showAlert('请选择JPG、PNG或GIF格式的图片文件', 'danger');
            return;
        }

        const formData = new FormData();
        formData.append('avatar', file);

        try {
            Utils.showLoading();

            const response = await fetch('/accounts/api/avatar/upload/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': Config.csrfToken,
                },
                body: formData,
            });

            if (response.ok) {
                const data = await response.json();
                if (data.status === 'success') {
                    // 更新头像显示
                    const avatarImg = document.getElementById('profile-avatar');
                    if (avatarImg) {
                        // 添加时间戳防止缓存
                        avatarImg.src = data.avatar_url + '?t=' + new Date().getTime();
                    }
                    Utils.showAlert('头像上传成功', 'success');
                } else {
                    Utils.showAlert(data.message || '上传失败', 'danger');
                }
            } else {
                Utils.showAlert('上传失败，请稍后重试', 'danger');
            }
        } catch (error) {
            console.error('Avatar upload error:', error);
            Utils.showAlert('上传失败，请稍后重试', 'danger');
        } finally {
            Utils.hideLoading();
        }
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    const isAuthPage = document.querySelector('.auth-page');
    const isProfilePage = document.querySelector('.profile-page');

    if (isAuthPage) {
        Auth.init();
    }

    if (isProfilePage) {
        Profile.init();
    }
});

// 导出到全局
window.Auth = Auth;
window.Profile = Profile;