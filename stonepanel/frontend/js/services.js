var ServiceMgr = {
    units: [],
    currentService: null,

    start: function() {
        var self = this;
        document.getElementById('svc-refresh-btn').addEventListener('click', function() { self.refresh(); });
        document.getElementById('svc-state-filter').addEventListener('change', function() { self.refresh(); });
        document.getElementById('svc-search').addEventListener('input', function() { self.filterTable(); });
        document.getElementById('svc-modal-close').addEventListener('click', function() { self.closeModal(); });
        document.getElementById('svc-modal-done').addEventListener('click', function() { self.closeModal(); });

        document.querySelectorAll('.svc-action-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                self.doAction(self.currentService, this.dataset.action);
            });
        });
    },

    refresh: async function() {
        var state = document.getElementById('svc-state-filter').value;
        var url = '/api/services/units?type=service';
        if (state) url += '&state=' + state;

        var r = await API.get(url);
        if (!r || !r.ok) return;
        var data = await r.json();
        this.units = data.units || [];
        this.render();
    },

    render: function() {
        var tbody = document.querySelector('#svc-table tbody');
        var empty = document.getElementById('svc-empty');
        var search = (document.getElementById('svc-search').value || '').toLowerCase();
        tbody.innerHTML = '';

        var filtered = this.units;
        if (search) {
            filtered = this.units.filter(function(u) {
                return u.name.toLowerCase().indexOf(search) !== -1 ||
                       (u.description || '').toLowerCase().indexOf(search) !== -1;
            });
        }

        if (filtered.length === 0) {
            empty.classList.remove('hidden');
            return;
        }
        empty.classList.add('hidden');

        for (var i = 0; i < filtered.length; i++) {
            var u = filtered[i];
            var dotClass = 'status-dot';
            if (u.sub === 'running') dotClass += ' dot-green';
            else if (u.active === 'failed') dotClass += ' dot-red';
            else dotClass += ' dot-gray';

            var tr = document.createElement('tr');
            tr.innerHTML =
                '<td><span class="' + dotClass + '"></span></td>' +
                '<td><a href="#" class="svc-name-link" data-name="' + this.esc(u.name) + '">' + this.esc(u.name) + '</a></td>' +
                '<td>' + this.esc(u.description || '') + '</td>' +
                '<td>' + this.esc(u.sub || u.active) + '</td>' +
                '<td class="col-act">' +
                (u.sub === 'running'
                    ? '<button class="btn btn-xs btn-danger svc-quick-btn" data-name="' + this.esc(u.name) + '" data-action="restart">Restart</button>'
                    : '<button class="btn btn-xs btn-primary svc-quick-btn" data-name="' + this.esc(u.name) + '" data-action="start">Start</button>') +
                '</td>';
            tbody.appendChild(tr);
        }

        var self = this;
        tbody.querySelectorAll('.svc-name-link').forEach(function(a) {
            a.addEventListener('click', function(e) {
                e.preventDefault();
                self.openDetail(this.dataset.name);
            });
        });
        tbody.querySelectorAll('.svc-quick-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                self.doAction(this.dataset.name, this.dataset.action);
            });
        });
    },

    filterTable: function() {
        this.render();
    },

    openDetail: async function(name) {
        this.currentService = name;
        document.getElementById('svc-modal-title').textContent = name;
        document.getElementById('svc-modal').classList.remove('hidden');

        var infoEl = document.getElementById('svc-detail-info');
        infoEl.innerHTML = '<span class="text-muted">Loading...</span>';

        var r = await API.get('/api/services/units/' + encodeURIComponent(name));
        if (!r || !r.ok) {
            infoEl.innerHTML = '<span class="text-muted">Failed to load</span>';
            return;
        }
        var s = await r.json();

        var html = '<div class="info-grid">';
        html += '<div class="info-item"><span class="info-label">State</span><span class="info-value">' + this.esc(s.active_state) + ' (' + this.esc(s.sub_state) + ')</span></div>';
        html += '<div class="info-item"><span class="info-label">Enabled</span><span class="info-value">' + (s.enabled ? 'Yes' : 'No') + '</span></div>';
        if (s.main_pid) html += '<div class="info-item"><span class="info-label">PID</span><span class="info-value">' + s.main_pid + '</span></div>';
        if (s.memory) html += '<div class="info-item"><span class="info-label">Memory</span><span class="info-value">' + this.formatBytes(s.memory) + '</span></div>';
        if (s.started_at) html += '<div class="info-item"><span class="info-label">Started</span><span class="info-value">' + this.esc(s.started_at) + '</span></div>';
        if (s.description) html += '<div class="info-item"><span class="info-label">Description</span><span class="info-value">' + this.esc(s.description) + '</span></div>';
        html += '</div>';
        infoEl.innerHTML = html;

        this.loadLogs(name);
    },

    loadLogs: async function(name) {
        var viewer = document.getElementById('svc-log-viewer');
        var count = document.getElementById('svc-log-count');
        viewer.innerHTML = '<span class="text-muted">Loading logs...</span>';

        var r = await API.get('/api/services/units/' + encodeURIComponent(name) + '/logs?lines=50');
        if (!r || !r.ok) {
            viewer.innerHTML = '<span class="text-muted">Failed to load logs</span>';
            return;
        }
        var data = await r.json();
        var logs = data.logs || [];
        count.textContent = '(' + logs.length + ' lines)';

        if (logs.length === 0) {
            viewer.innerHTML = '<span class="text-muted">No log entries</span>';
            return;
        }

        var html = '';
        for (var i = 0; i < logs.length; i++) {
            var entry = logs[i];
            var cls = 'log-line';
            if (entry.priority <= 3) cls += ' log-error';
            else if (entry.priority <= 4) cls += ' log-warn';

            var ts = '';
            if (entry.timestamp) {
                var d = new Date(parseInt(entry.timestamp) / 1000);
                if (!isNaN(d.getTime())) {
                    ts = d.toLocaleTimeString();
                }
            }
            html += '<div class="' + cls + '">';
            if (ts) html += '<span class="log-ts">' + ts + '</span> ';
            html += this.esc(entry.message);
            html += '</div>';
        }
        viewer.innerHTML = html;
        viewer.scrollTop = viewer.scrollHeight;
    },

    closeModal: function() {
        document.getElementById('svc-modal').classList.add('hidden');
        this.currentService = null;
    },

    doAction: async function(name, action) {
        if (!name) return;
        var r = await API.post('/api/services/units/' + encodeURIComponent(name) + '/' + action, {});
        if (r && r.ok) {
            API.toast(action + ' successful', 'success');
            // Refresh detail if modal is open
            if (this.currentService === name) {
                setTimeout(function() { ServiceMgr.openDetail(name); }, 500);
            }
            this.refresh();
        } else {
            var err = r ? await r.json().catch(function() { return {}; }) : {};
            API.toast(err.detail || action + ' failed', 'error');
        }
    },

    formatBytes: function(bytes) {
        bytes = parseInt(bytes);
        if (isNaN(bytes) || bytes === 0) return '0 B';
        var units = ['B', 'KB', 'MB', 'GB'];
        var i = 0;
        while (bytes >= 1024 && i < units.length - 1) { bytes /= 1024; i++; }
        return bytes.toFixed(1) + ' ' + units[i];
    },

    esc: function(s) {
        var d = document.createElement('div');
        d.textContent = s || '';
        return d.innerHTML;
    }
};
