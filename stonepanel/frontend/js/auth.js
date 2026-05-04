/* global API helper + auth logic */

const API = {
    token: localStorage.getItem('sp_token'),

    async request(method, path, body) {
        const opts = { method, headers: {} };
        if (this.token) opts.headers['Authorization'] = 'Bearer ' + this.token;
        if (body !== undefined && !(body instanceof FormData)) {
            opts.headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(body);
        } else if (body instanceof FormData) {
            opts.body = body;
        }
        const resp = await fetch(path, opts);
        if (resp.status === 401) { this.logout(); return null; }
        return resp;
    },
    get(p)    { return this.request('GET', p); },
    post(p,b) { return this.request('POST', p, b); },
    put(p,b)  { return this.request('PUT', p, b); },
    del(p)    { return this.request('DELETE', p); },

    setToken(t) { this.token = t; localStorage.setItem('sp_token', t); },
    logout()    { this.token = null; localStorage.removeItem('sp_token'); location.reload(); },
};

function toast(msg, type) {
    type = type || 'info';
    const el = document.createElement('div');
    el.className = 'toast toast-' + type;
    el.textContent = msg;
    document.getElementById('toasts').appendChild(el);
    setTimeout(function() { el.remove(); }, 3500);
}

/* Auth form */
const Auth = {
    async init() {
        const resp = await fetch('/api/auth/status');
        const data = await resp.json();
        const btn = document.getElementById('login-btn');
        const sub = document.getElementById('login-subtitle');
        if (!data.setup_complete) {
            btn.textContent = 'Set Password';
            sub.textContent = 'First-time setup: choose a password';
            this.mode = 'setup';
        } else {
            btn.textContent = 'Login';
            sub.textContent = 'Server Management Panel';
            this.mode = 'login';
        }
        document.getElementById('login-form').addEventListener('submit', function(e) {
            e.preventDefault();
            Auth.submit();
        });
    },

    async submit() {
        const pw = document.getElementById('password-input').value;
        const errEl = document.getElementById('login-error');
        errEl.classList.add('hidden');

        const endpoint = this.mode === 'setup' ? '/api/auth/setup' : '/api/auth/login';
        try {
            const resp = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password: pw }),
            });
            if (!resp.ok) {
                const d = await resp.json();
                errEl.textContent = d.detail || 'Error';
                errEl.classList.remove('hidden');
                return;
            }
            const data = await resp.json();
            API.setToken(data.access_token);
            App.enterApp();
        } catch (_) {
            errEl.textContent = 'Connection failed';
            errEl.classList.remove('hidden');
        }
    },
};
