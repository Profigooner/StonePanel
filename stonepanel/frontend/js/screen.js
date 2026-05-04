const ScreenMgr = {
    available: { screen: false, tmux: false },

    start() {
        document.getElementById('screen-new-btn').addEventListener('click', function() {
            ScreenMgr.openCreateModal();
        });
        document.getElementById('screen-refresh-btn').addEventListener('click', function() {
            ScreenMgr.refresh();
        });

        // Create modal
        document.getElementById('screen-create-cancel').addEventListener('click', function() {
            ScreenMgr.closeCreateModal();
        });
        document.getElementById('screen-create-close').addEventListener('click', function() {
            ScreenMgr.closeCreateModal();
        });
        document.getElementById('screen-create-form').addEventListener('submit', function(e) {
            e.preventDefault();
            ScreenMgr.submitCreate();
        });

        // Type toggle
        document.querySelectorAll('#screen-type-group .btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                document.querySelectorAll('#screen-type-group .btn').forEach(function(b) {
                    b.classList.remove('active');
                });
                this.classList.add('active');
            });
        });

        // Context menu close
        document.addEventListener('click', function() { ScreenMgr.closeCtx(); });

        this.checkAvailable();
    },

    async checkAvailable() {
        var r = await API.get('/api/screen/available');
        if (r && r.ok) this.available = await r.json();
        this.renderToolIndicator();
    },

    renderToolIndicator() {
        var el = document.getElementById('screen-tools-status');
        var parts = [];
        if (this.available.screen) parts.push('<span class="tool-ok">screen</span>');
        else parts.push('<span class="tool-na">screen</span>');
        if (this.available.tmux) parts.push('<span class="tool-ok">tmux</span>');
        else parts.push('<span class="tool-na">tmux</span>');
        el.innerHTML = parts.join(' ');
    },

    async refresh() {
        var r = await API.get('/api/screen/sessions');
        if (!r || !r.ok) return;
        var d = await r.json();
        this.renderTable(d.sessions);
    },

    renderTable(sessions) {
        var tb = document.querySelector('#screen-table tbody');
        var emptyEl = document.getElementById('screen-empty');
        var tableEl = document.getElementById('screen-table');

        if (sessions.length === 0) {
            tableEl.classList.add('hidden');
            emptyEl.classList.remove('hidden');
            return;
        }
        tableEl.classList.remove('hidden');
        emptyEl.classList.add('hidden');

        var html = '';
        for (var i = 0; i < sessions.length; i++) {
            var s = sessions[i];
            var statusClass = s.status === 'Attached' ? 'text-green' : 'text-muted';
            var created = s.created ? ScreenMgr.fmtCreated(s.created) : '--';
            html += '<tr>'
                + '<td><span class="session-name">' + esc(s.name) + '</span></td>'
                + '<td><span class="badge badge-' + s.type + '">' + s.type + '</span></td>'
                + '<td><span class="' + statusClass + '">' + esc(s.status) + '</span></td>'
                + '<td>' + (s.windows != null ? s.windows : '--') + '</td>'
                + '<td class="text-muted">' + created + '</td>'
                + '<td style="text-align:center">'
                + '<button class="row-menu-btn screen-menu-btn" '
                + 'data-type="' + esc(s.type) + '" '
                + 'data-id="' + esc(s.id) + '" '
                + 'data-name="' + esc(s.name) + '" '
                + 'data-status="' + esc(s.status) + '"'
                + '>&middot;&middot;&middot;</button>'
                + '</td></tr>';
        }
        tb.innerHTML = html;

        tb.querySelectorAll('.screen-menu-btn').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                ScreenMgr.openCtx(e, this.dataset);
            });
        });
    },

    /* ---- Context menu ---- */

    openCtx(e, data) {
        this.closeCtx();
        var menu = document.createElement('div');
        menu.className = 'ctx-menu';
        menu.id = 'screen-ctx-active';

        var items = [];
        if (data.status === 'Detached') {
            items.push({ icon: '>', label: 'Attach', action: 'attach' });
            items.push('sep');
        }
        items.push({ icon: 'X', label: 'Kill', action: 'kill', danger: true });

        for (var i = 0; i < items.length; i++) {
            var it = items[i];
            if (it === 'sep') {
                var sep = document.createElement('div');
                sep.className = 'ctx-sep';
                menu.appendChild(sep);
                continue;
            }
            var row = document.createElement('div');
            row.className = 'ctx-item' + (it.danger ? ' ctx-danger' : '');
            row.dataset.action = it.action;
            row.dataset.type = data.type;
            row.dataset.id = data.id;
            row.dataset.name = data.name;
            row.innerHTML = '<span class="ctx-icon">' + it.icon + '</span>' + esc(it.label);
            menu.appendChild(row);
        }

        document.body.appendChild(menu);
        var btn = e.currentTarget.getBoundingClientRect();
        var top = btn.bottom + 4;
        var left = btn.right - menu.offsetWidth;
        if (top + menu.offsetHeight > window.innerHeight - 8) top = btn.top - menu.offsetHeight - 4;
        if (left < 8) left = 8;
        menu.style.top = top + 'px';
        menu.style.left = left + 'px';

        menu.addEventListener('click', function(ev) {
            var target = ev.target.closest('.ctx-item');
            if (!target) return;
            ev.stopPropagation();
            ScreenMgr.closeCtx();
            if (target.dataset.action === 'attach')
                ScreenMgr.attachSession(target.dataset.type, target.dataset.id, target.dataset.name);
            if (target.dataset.action === 'kill')
                ScreenMgr.killSession(target.dataset.type, target.dataset.id);
        });
    },

    closeCtx() {
        var m = document.getElementById('screen-ctx-active');
        if (m) m.remove();
    },

    /* ---- Actions ---- */

    async attachSession(type, id, name) {
        // Create a PTY terminal session
        var r = await API.post('/api/terminal/sessions');
        if (!r || !r.ok) { toast('Failed to create terminal', 'err'); return; }
        var d = await r.json();
        var sid = d.session_id;

        // Build reattach command
        var cmd = type === 'screen'
            ? 'screen -r ' + id + '\n'
            : 'tmux attach -t ' + name + '\n';

        // Create terminal tab with session name as label
        var label = type + ': ' + name;
        TermMgr.addTab(sid, label);

        // Navigate to terminal page and activate
        App.navigate('terminal');
        TermMgr.switchTo(sid);

        // Send the attach command once WebSocket is ready
        var sess = TermMgr.sessions[sid];
        if (!sess) return;
        var send = function() {
            setTimeout(function() {
                if (sess.ws.readyState === WebSocket.OPEN) {
                    sess.ws.send(JSON.stringify({ type: 'input', data: cmd }));
                }
            }, 300);
        };
        if (sess.ws.readyState === WebSocket.OPEN) send();
        else sess.ws.addEventListener('open', send);
    },

    async killSession(type, id) {
        if (!confirm('Kill ' + type + ' session "' + id + '"?')) return;
        var r = await API.del('/api/screen/sessions/' + encodeURIComponent(type) + '/' + encodeURIComponent(id));
        if (r && r.ok) { toast('Session killed', 'ok'); this.refresh(); }
        else { toast('Failed to kill session', 'err'); }
    },

    /* ---- Create modal ---- */

    openCreateModal() {
        document.getElementById('screen-create-overlay').classList.remove('hidden');
        document.getElementById('screen-name-input').value = '';
        document.getElementById('screen-cmd-input').value = '';
        document.getElementById('screen-name-input').focus();
    },

    closeCreateModal() {
        document.getElementById('screen-create-overlay').classList.add('hidden');
    },

    async submitCreate() {
        var activeType = document.querySelector('#screen-type-group .btn.active');
        var type = activeType ? activeType.dataset.type : 'screen';
        var name = document.getElementById('screen-name-input').value.trim();
        var command = document.getElementById('screen-cmd-input').value.trim();

        if (!name) { toast('Name is required', 'err'); return; }

        var r = await API.post('/api/screen/sessions', { type: type, name: name, command: command });
        if (r && r.ok) {
            toast('Session created', 'ok');
            this.closeCreateModal();
            this.refresh();
        } else {
            var d = r ? await r.json() : {};
            toast(d.detail || 'Failed', 'err');
        }
    },

    /* ---- Helpers ---- */

    fmtCreated(ts) {
        // tmux returns unix timestamp
        var n = parseInt(ts, 10);
        if (isNaN(n)) return ts;
        var d = new Date(n * 1000);
        var now = Date.now();
        var diff = Math.floor((now - d.getTime()) / 1000);
        if (diff < 60) return diff + 's ago';
        if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
        if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
        return Math.floor(diff / 86400) + 'd ago';
    },
};
