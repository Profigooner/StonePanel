const ProxyMgr = {
    _editId: null,

    start() {
        // Tab switching
        document.querySelectorAll('#page-proxy .page-tab').forEach(function(tab) {
            tab.addEventListener('click', function() {
                ProxyMgr.switchTab(this.dataset.tab);
            });
        });

        // Add rule
        document.getElementById('proxy-add-btn').addEventListener('click', function() {
            ProxyMgr.openModal();
        });

        // Modal controls
        document.getElementById('proxy-modal-close').addEventListener('click', function() { ProxyMgr.closeModal(); });
        document.getElementById('proxy-modal-cancel').addEventListener('click', function() { ProxyMgr.closeModal(); });
        document.getElementById('proxy-modal-save').addEventListener('click', function() { ProxyMgr.saveRule(); });
        document.getElementById('proxy-add-upstream').addEventListener('click', function() { ProxyMgr.addUpstreamRow(); });

        // Caddy controls
        document.getElementById('caddy-start-btn').addEventListener('click', function() { ProxyMgr.caddyAction('start'); });
        document.getElementById('caddy-stop-btn').addEventListener('click', function() { ProxyMgr.caddyAction('stop'); });
        document.getElementById('caddy-apply-btn').addEventListener('click', function() { ProxyMgr.applyConfig(); });
    },

    switchTab(tabId) {
        document.querySelectorAll('#page-proxy .page-tab').forEach(function(t) {
            t.classList.toggle('active', t.dataset.tab === tabId);
        });
        document.querySelectorAll('#page-proxy .tab-pane').forEach(function(p) {
            p.classList.toggle('hidden', p.id !== tabId);
        });
        if (tabId === 'proxy-caddy') this.fetchCaddyStatus();
    },

    async refresh() {
        await this.fetchRules();
    },

    // --- Rules ---

    async fetchRules() {
        var r = await API.get('/api/proxy/rules');
        if (!r) return;
        var d = await r.json();
        this.renderRules(d.rules);
    },

    renderRules(rules) {
        var tb = document.querySelector('#proxy-table tbody');
        var empty = document.getElementById('proxy-empty');

        if (rules.length === 0) {
            tb.innerHTML = '';
            empty.classList.remove('hidden');
            return;
        }
        empty.classList.add('hidden');

        var html = '';
        for (var i = 0; i < rules.length; i++) {
            var r = rules[i];
            var statusCls = r.enabled ? 'badge-green' : 'badge-muted';
            var statusTxt = r.enabled ? 'Active' : 'Disabled';
            var healthDot = '<span class="dot dot-muted"></span>';

            html += '<tr>'
                + '<td><strong>' + esc(r.name) + '</strong></td>'
                + '<td><code>' + esc(r.protocol.toUpperCase()) + '</code></td>'
                + '<td>:' + r.listen_port + '</td>'
                + '<td>' + (r.domain ? esc(r.domain) : '<span class="text-muted">--</span>') + '</td>'
                + '<td>' + r.upstreams.length + '</td>'
                + '<td>' + healthDot + '</td>'
                + '<td><span class="badge ' + statusCls + '">' + statusTxt + '</span></td>'
                + '<td class="row-actions">'
                +   '<button class="btn btn-xs" onclick="ProxyMgr.editRule(\'' + r.id + '\')">Edit</button>'
                +   '<button class="btn btn-xs" onclick="ProxyMgr.toggleRule(\'' + r.id + '\',' + r.enabled + ')">' + (r.enabled ? 'Disable' : 'Enable') + '</button>'
                +   '<button class="btn btn-xs btn-danger" onclick="ProxyMgr.deleteRule(\'' + r.id + '\')">Del</button>'
                + '</td></tr>';
        }
        tb.innerHTML = html;
    },

    // --- Modal ---

    openModal(rule) {
        this._editId = rule ? rule.id : null;
        document.getElementById('proxy-modal-title').textContent = rule ? 'Edit Proxy Rule' : 'Add Proxy Rule';
        document.getElementById('proxy-edit-id').value = rule ? rule.id : '';
        document.getElementById('proxy-name').value = rule ? rule.name : '';
        document.getElementById('proxy-protocol').value = rule ? rule.protocol : 'http';
        document.getElementById('proxy-port').value = rule ? rule.listen_port : 80;
        document.getElementById('proxy-domain').value = rule ? (rule.domain || '') : '';
        document.getElementById('proxy-path').value = rule ? rule.path_prefix : '/';
        document.getElementById('proxy-lb').value = rule ? rule.load_balance : 'round_robin';
        document.getElementById('proxy-waf').value = rule ? String(rule.waf_enabled) : 'true';

        // Upstreams
        var list = document.getElementById('proxy-upstreams-list');
        list.innerHTML = '';
        if (rule && rule.upstreams.length > 0) {
            for (var i = 0; i < rule.upstreams.length; i++) {
                this.addUpstreamRow(rule.upstreams[i].address, rule.upstreams[i].weight);
            }
        } else {
            this.addUpstreamRow();
        }

        document.getElementById('proxy-modal').classList.remove('hidden');
    },

    closeModal() {
        document.getElementById('proxy-modal').classList.add('hidden');
        this._editId = null;
    },

    addUpstreamRow(addr, weight) {
        var list = document.getElementById('proxy-upstreams-list');
        var row = document.createElement('div');
        row.className = 'upstream-row';
        row.innerHTML = '<input type="text" class="input-sm upstream-addr" placeholder="192.168.1.10:8080" value="' + (addr || '') + '">'
            + '<input type="number" class="input-xs upstream-weight" placeholder="1" value="' + (weight || 1) + '" min="1" title="Weight">'
            + '<button class="btn btn-xs btn-danger upstream-remove" type="button">&times;</button>';
        row.querySelector('.upstream-remove').addEventListener('click', function() {
            row.remove();
        });
        list.appendChild(row);
    },

    async saveRule() {
        var upstreams = [];
        document.querySelectorAll('#proxy-upstreams-list .upstream-row').forEach(function(row) {
            var addr = row.querySelector('.upstream-addr').value.trim();
            var w = parseInt(row.querySelector('.upstream-weight').value) || 1;
            if (addr) upstreams.push({ address: addr, weight: w });
        });

        if (!document.getElementById('proxy-name').value.trim()) {
            toast('Name is required', 'err'); return;
        }
        if (upstreams.length === 0) {
            toast('At least one upstream is required', 'err'); return;
        }

        var data = {
            name: document.getElementById('proxy-name').value.trim(),
            protocol: document.getElementById('proxy-protocol').value,
            listen_port: parseInt(document.getElementById('proxy-port').value),
            domain: document.getElementById('proxy-domain').value.trim() || null,
            path_prefix: document.getElementById('proxy-path').value.trim() || '/',
            upstreams: upstreams,
            load_balance: document.getElementById('proxy-lb').value,
            waf_enabled: document.getElementById('proxy-waf').value === 'true',
        };

        var r;
        if (this._editId) {
            r = await API.put('/api/proxy/rules/' + this._editId, data);
        } else {
            r = await API.post('/api/proxy/rules', data);
        }
        if (r && r.ok) {
            toast(this._editId ? 'Rule updated' : 'Rule created', 'ok');
            this.closeModal();
            this.fetchRules();
        } else {
            toast('Failed to save rule', 'err');
        }
    },

    async editRule(id) {
        var r = await API.get('/api/proxy/rules/' + id);
        if (!r || !r.ok) { toast('Failed to load rule', 'err'); return; }
        var rule = await r.json();
        this.openModal(rule);
    },

    async toggleRule(id, currentlyEnabled) {
        var action = currentlyEnabled ? 'disable' : 'enable';
        var r = await API.post('/api/proxy/rules/' + id + '/' + action);
        if (r && r.ok) {
            toast('Rule ' + action + 'd', 'ok');
            this.fetchRules();
        } else {
            toast('Failed', 'err');
        }
    },

    async deleteRule(id) {
        if (!confirm('Delete this proxy rule?')) return;
        var r = await API.del('/api/proxy/rules/' + id);
        if (r && r.ok) {
            toast('Rule deleted', 'ok');
            this.fetchRules();
        } else {
            toast('Failed', 'err');
        }
    },

    // --- Caddy ---

    async fetchCaddyStatus() {
        var r = await API.get('/api/proxy/caddy/status');
        if (!r || !r.ok) return;
        var d = await r.json();
        document.getElementById('caddy-installed').textContent = d.installed ? 'Yes' : 'No';
        document.getElementById('caddy-installed').className = 'stat-value ' + (d.installed ? 'text-green' : 'text-red');
        document.getElementById('caddy-running').textContent = d.running ? 'Yes' : 'No';
        document.getElementById('caddy-running').className = 'stat-value ' + (d.running ? 'text-green' : 'text-red');
        document.getElementById('caddy-version').textContent = d.version || '--';
    },

    async caddyAction(action) {
        var r = await API.post('/api/proxy/caddy/' + action);
        if (r && r.ok) {
            toast('Caddy ' + action + (action.endsWith('e') ? 'd' : 'ed'), 'ok');
            this.fetchCaddyStatus();
        } else {
            var d = r ? await r.json() : {};
            toast(d.detail || 'Failed', 'err');
        }
    },

    async applyConfig() {
        var r = await API.post('/api/proxy/apply');
        if (r && r.ok) {
            toast('Config applied to Caddy', 'ok');
        } else {
            var d = r ? await r.json() : {};
            toast(d.detail || 'Failed to apply config', 'err');
        }
    },
};
