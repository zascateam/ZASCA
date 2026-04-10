/**
 * 基础JavaScript功能
 */

// 全局配置
const Config = {
    apiBase: '/api/',
};

function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
           document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
           document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1] ||
           '';
}

Config.csrfToken = getCsrfToken();

// 工具函数
const Utils = {
    /**
     * 显示加载动画
     */
    showLoading() {
        const loading = document.createElement('div');
        loading.className = 'loading-overlay';
        loading.id = 'loading-overlay';
        loading.innerHTML = `
            <div class="spinner-border text-primary" role="status">
                <span class="sr-only">加载中...</span>
            </div>
        `;
        document.body.appendChild(loading);
    },

    /**
     * 隐藏加载动画
     */
    hideLoading() {
        const loading = document.getElementById('loading-overlay');
        if (loading) {
            loading.remove();
        }
    },

    /**
     * 显示提示信息
     */
    showAlert(message, type = 'info') {
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.innerHTML = `
            ${message}
            <button type="button" class="close" data-dismiss="alert" aria-label="Close">
                <span aria-hidden="true">&times;</span>
            </button>
        `;

        const container = document.querySelector('.container') || document.body;
        container.insertBefore(alert, container.firstChild);

        // 5秒后自动关闭
        setTimeout(() => {
            alert.classList.remove('show');
            setTimeout(() => alert.remove(), 150);
        }, 5000);
    },

    /**
     * 确认对话框
     */
    confirm(message) {
        return window.confirm(message);
    },

    /**
     * 格式化日期时间
     */
    formatDateTime(dateStr) {
        const date = new Date(dateStr);
        return date.toLocaleString('zh-CN');
    },

    /**
     * 格式化文件大小
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    },

    /**
     * 防抖函数
     */
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    /**
     * 节流函数
     */
    throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
};

// API请求封装
const API = {
    /**
     * 发送GET请求
     */
    async get(url, params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const fullUrl = queryString ? `${url}?${queryString}` : url;

        const response = await fetch(fullUrl, {
            method: 'GET',
            headers: {
                'X-CSRFToken': Config.csrfToken,
            },
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return response.json();
    },

    /**
     * 发送POST请求
     */
    async post(url, data = {}) {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': Config.csrfToken,
            },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return response.json();
    },

    /**
     * 发送PUT请求
     */
    async put(url, data = {}) {
        const response = await fetch(url, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': Config.csrfToken,
            },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return response.json();
    },

    /**
     * 发送DELETE请求
     */
    async delete(url) {
        const response = await fetch(url, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': Config.csrfToken,
            },
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return response.json();
    }
};

// 表单处理
const FormHandler = {
    /**
     * 初始化表单
     */
    init(formSelector, options = {}) {
        const form = document.querySelector(formSelector);
        if (!form) return;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();

            if (options.beforeSubmit) {
                const result = await options.beforeSubmit(form);
                if (result === false) return;
            }

            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());

            try {
                Utils.showLoading();

                const response = await API.post(form.action, data);

                if (options.onSuccess) {
                    options.onSuccess(response, form);
                }
            } catch (error) {
                console.error('Form submission error:', error);

                if (options.onError) {
                    options.onError(error, form);
                } else {
                    Utils.showAlert('提交失败，请稍后重试', 'danger');
                }
            } finally {
                Utils.hideLoading();
            }
        });
    }
};

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    // 初始化所有提示框的关闭按钮
    document.querySelectorAll('.alert[data-dismiss="alert"]').forEach(alert => {
        alert.querySelector('.close').addEventListener('click', () => {
            alert.classList.remove('show');
            setTimeout(() => alert.remove(), 150);
        });
    });

    // 初始化所有确认按钮
    document.querySelectorAll('[data-confirm]').forEach(button => {
        button.addEventListener('click', (e) => {
            if (!Utils.confirm(button.dataset.confirm)) {
                e.preventDefault();
            }
        });
    });
});

// 导出到全局
window.Config = Config;
window.Utils = Utils;
window.API = API;
window.FormHandler = FormHandler;
window.getCsrfToken = getCsrfToken;
