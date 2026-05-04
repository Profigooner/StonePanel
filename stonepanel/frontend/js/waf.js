const WAFMgr = {
    _editRuleId: null,

    start() {
        // Tab switching
        document.querySelectorAll('#page-waf .page-tab').forEach(function(tab) {
            tab.addEventListener('click', function() {
                WAFMgr.switchTab(this.dataset.tab);
            });
        });

        // WAF toggle
        document.getElementById('waf-toggle-btn').addEventListener('click', function() { WAFMgr.toggleWAF(); });

        // Add buttons
        document.getElementById('waf-add-rule-btn').addEventListener('click', function() { WAFMgr.openRuleModal(); });
        document.getElementById('waf-add-whitelist-btn').addEventListener('click', function() { WAFMgr.addIP('whitelist'); });
        document.getElementById('waf-add-blacklist-btn').addEventListener('click', function() { WAFMgr.addIP('blacklist'); });
        document.getElementById('waf-add-ratelimit-btn').addEventListener('click', function() { WAFMgr.addRateLimit(); });
        document.getElementById('waf-add-geo-btn').addEventListener('click', function() { WAFMgr.addGeoRule(); });

        // Rule modal
        document.getElementById('waf-rule-modal-close').addEventListener('click', function() { WAFMgr.closeRuleModal(); });
        document.getElementById('waf-rule-modal-cancel').addEventListener('click', function() { WAFMgr.closeRuleModal(); });
        document.getElementById('waf-rule-modal-save').addEventListener('click', function() { WAFMgr.saveRule(); });
        document.getElementById('waf-add-condition').addEventListener('click', function() { WAFMgr.addConditionRow(); });

        // Log filters
        document.getElementById('waf-log-refresh').addEventListener('click', function() { WAFMgr.fetchLogs(); });
    },

    switchTab(tabId) {
        document.querySelectorAll('#page-waf .page-tab').forEach(function(t) {
            t.classList.toggle('active', t.dataset.tab === tabId);
        });
        document.querySelectorAll('#page-waf .tab-pane').forEach(function(p) {
            p.classList.toggle('hidden', p.id !== tabId);
        });
        if (tabId === 'waf-rules') { this.fetchOWASP(); this.fetchRules(); }
        if (tabId === 'waf-iplists') this.fetchIPLists();
        if (tabId === 'waf-ratelimit') this.fetchRateLimits();
        if (tabId === 'waf-geo') this.fetchGeoRules();
        if (tabId === 'waf-logs') this.fetchLogs();
    },

    async refresh() {
        await this.fetchDashboard();
    },

    // --- Dashboard ---

    async fetchDashboard() {
        var r = await API.get('/api/waf/dashboard');
        if (!r || !r.ok) return;
        var d = await r.json();

        // Config state
        var badge = document.getElementById('waf-mode-badge');
        var btn = document.getElementById('waf-toggle-btn');
        if (d.config.enabled) {
            badge.textContent = d.config.mode === 'active' ? 'ACTIVE' : 'MONITOR';
            badge.className = 'badge ' + (d.config.mode === 'active' ? 'badge-green' : 'badge-yellow');
            btn.textContent = 'Disable';
        } else {
            badge.textContent = 'DISABLED';
            badge.className = 'badge badge-muted';
            btn.textContent = 'Enable';
        }

        // Stats
        var blocked = 0;
        if (d.stats.actions && d.stats.actions.block) blocked = d.stats.actions.block;
        document.getElementById('waf-blocked-count').textContent = blocked;
        document.getElementById('waf-rules-count').textContent = d.custom_rules_count + d.owasp_rules_enabled;
        document.getElementById('waf-blacklist-count').textContent = d.blacklist_count;
        document.getElementById('waf-owasp-count').textContent = d.owasp_rules_enabled + '/' + d.owasp_rules_total;

        // Top IPs
        var ipTb = document.querySelector('#waf-top-ips tbody');
        if (d.stats.top_ips && d.stats.top_ips.length > 0) {
            var html = '';
            for (var i = 0; i < d.stats.top_ips.length; i++) {
                html += '<tr><td><code>' + esc(d.stats.top_ips[i].ip) + '</code></td><td>' + d.stats.top_ips[i].count + '</td></tr>';
            }
            ipTb.innerHTML = html;
        } else {
            ipTb.innerHTML = '<tr><td colspan="2" class="text-muted" style="text-align:center">No data</td></tr>';
        }

        // Recent attacks
        await this.fetchRecentAttacks();
    },

    async fetchRecentAttacks() {
        var r = await API.get('/api/waf/logs?limit=10');
        if (!r || !r.ok) return;
        var d = await r.json();
        var tb = document.querySelector('#waf-recent-attacks tbody');
        if (d.logs.length === 0) {
            tb.innerHTML = '<tr><td colspan="5" class="text-muted" style="text-align:center">No recent attacks</td></tr>';
            return;
        }
        var html = '';
        for (var i = 0; i < d.logs.length; i++) {
            var e = d.logs[i];
            var actionCls = e.action === 'block' ? 'badge-red' : 'badge-yellow';
            html += '<tr>'
                + '<td class="text-muted">' + fmtDate(e.timestamp) + '</td>'
                + '<td><code>' + esc(e.source_ip) + '</code></td>'
                + '<td class="text-muted" title="' + esc(e.url) + '">' + esc(truncate(e.url, 40)) + '</td>'
                + '<td>' + esc(e.rule_name) + '</td>'
                + '<td><span class="badge ' + actionCls + '">' + esc(e.action) + '</span></td>'
                + '</tr>';
        }
        tb.innerHTML = html;
    },

    async toggleWAF() {
        var r = await API.get('/api/waf/config');
        if (!r || !r.ok) return;
        var config = await r.json();
        config.enabled = !config.enabled;
        var r2 = await API.put('/api/waf/config', config);
        if (r2 && r2.ok) {
            toast('WAF ' + (config.enabled ? 'enabled' : 'disabled'), 'ok');
            this.fetchDashboard();
        }
    },

    // --- OWASP Rules ---

    async fetchOWASP() {
        var r = await API.get('/api/waf/owasp/rules');
        if (!r || !r.ok) return;
        var d = await r.json();
        var tb = document.querySelector('#waf-owasp-table tbody');
        var html = '';
        for (var i = 0; i < d.rules.length; i++) {
            var rule = d.rules[i];
            var statusCls = rule.enabled ? 'badge-green' : 'badge-muted';
            html += '<tr>'
                + '<td>' + esc(rule.name) + '<br><span class="text-muted" style="font-size:12px">' + esc(rule.description) + '</span></td>'
                + '<td><span class="badge">' + esc(rule.category) + '</span></td>'
                + '<td><span class="badge">' + esc(rule.action) + '</span></td>'
                + '<td><span class="badge ' + statusCls + '" style="cursor:pointer" '
                +   'onclick="WAFMgr.toggleOWASP(\'' + rule.id + '\',' + rule.enabled + ')">'
                +   (rule.enabled ? 'Enabled' : 'Disabled') + '</span></td>'
                + '</tr>';
        }
        tb.innerHTML = html;
    },

    async toggleOWASP(ruleId, currentEnabled) {
        var r = await API.put('/api/waf/owasp/rules/' + ruleId + '?enabled=' + !currentEnabled);
        if (r && r.ok) {
            toast('OWASP rule ' + (!currentEnabled ? 'enabled' : 'disabled'), 'ok');
            this.fetchOWASP();
        }
    },

    // --- Custom Rules ---

    async fetchRules() {
        var r = await API.get('/api/waf/rules');
        if (!r || !r.ok) return;
        var d = await r.json();
        var tb = document.querySelector('#waf-custom-table tbody');
        var empty = document.getElementById('waf-custom-empty');

        if (d.rules.length === 0) {
            tb.innerHTML = '';
            empty.classList.remove('hidden');
            return;
        }
        empty.classList.add('hidden');

        var html = '';
        for (var i = 0; i < d.rules.length; i++) {
            var rule = d.rules[i];
            var condText = rule.conditions.map(function(c) {
                return c.target + ' ' + c.operator + ' "' + c.value.substring(0, 30) + '"';
            }).join(', ');
            html += '<tr>'
                + '<td>' + esc(rule.name) + '</td>'
                + '<td>' + rule.priority + '</td>'
                + '<td class="text-muted" style="font-size:12px">' + esc(truncate(condText, 50)) + '</td>'
                + '<td><span class="badge">' + esc(rule.action) + '</span></td>'
                + '<td class="row-actions">'
                +   '<button class="btn btn-xs" onclick="WAFMgr.editRule(\'' + rule.id + '\')">Edit</button>'
                +   '<button class="btn btn-xs btn-danger" onclick="WAFMgr.deleteRule(\'' + rule.id + '\')">Del</button>'
                + '</td></tr>';
        }
        tb.innerHTML = html;
    },

    // --- Rule Modal ---

    openRuleModal(rule) {
        this._editRuleId = rule ? rule.id : null;
        document.getElementById('waf-rule-modal-title').textContent = rule ? 'Edit WAF Rule' : 'Add WAF Rule';
        document.getElementById('waf-rule-edit-id').value = rule ? rule.id : '';
        document.getElementById('waf-rule-name').value = rule ? rule.name : '';
        document.getElementById('waf-rule-priority').value = rule ? rule.priority : 100;
        document.getElementById('waf-rule-action').value = rule ? rule.action : 'block';

        var list = document.getElementById('waf-conditions-list');
        list.innerHTML = '';
        if (rule && rule.conditions.length > 0) {
            for (var i = 0; i < rule.conditions.length; i++) {
                var c = rule.conditions[i];
                this.addConditionRow(c.target, c.operator, c.value, c.negate);
            }
        } else {
            this.addConditionRow();
        }
        document.getElementById('waf-rule-modal').classList.remove('hidden');
    },

    closeRuleModal() {
        document.getElementById('waf-rule-modal').classList.add('hidden');
        this._editRuleId = null;
    },

    addConditionRow(target, operator, value, negate) {
        var list = document.getElementById('waf-conditions-list');
        var row = document.createElement('div');
        row.className = 'condition-row';
        row.innerHTML = '<select class="input-sm cond-target">'
            + '<option value="url"' + (target === 'url' ? ' selected' : '') + '>URL</option>'
            + '<option value="query"' + (target === 'query' ? ' selected' : '') + '>Query</option>'
            + '<option value="body"' + (target === 'body' ? ' selected' : '') + '>Body</option>'
            + '<option value="headers"' + (target === 'headers' ? ' selected' : '') + '>Headers</option>'
            + '<option value="user_agent"' + (target === 'user_agent' ? ' selected' : '') + '>User Agent</option>'
            + '<option value="ip"' + (target === 'ip' ? ' selected' : '') + '>IP</option>'
            + '<option value="method"' + (target === 'method' ? ' selected' : '') + '>Method</option>'
            + '</select>'
            + '<select class="input-sm cond-op">'
            + '<option value="contains"' + (operator === 'contains' ? ' selected' : '') + '>Contains</option>'
            + '<option value="regex"' + (operator === 'regex' ? ' selected' : '') + '>Regex</option>'
            + '<option value="equals"' + (operator === 'equals' ? ' selected' : '') + '>Equals</option>'
            + '<option value="starts_with"' + (operator === 'starts_with' ? ' selected' : '') + '>Starts With</option>'
            + '<option value="ends_with"' + (operator === 'ends_with' ? ' selected' : '') + '>Ends With</option>'
            + '</select>'
            + '<input type="text" class="input-sm cond-value" placeholder="pattern" value="' + esc(value || '') + '">'
            + '<label class="cond-negate"><input type="checkbox" class="cond-negate-cb"' + (negate ? ' checked' : '') + '> NOT</label>'
            + '<button class="btn btn-xs btn-danger cond-remove" type="button">&times;</button>';
        row.querySelector('.cond-remove').addEventListener('click', function() { row.remove(); });
        list.appendChild(row);
    },

    async saveRule() {
        var conditions = [];
        document.querySelectorAll('#waf-conditions-list .condition-row').forEach(function(row) {
            var val = row.querySelector('.cond-value').value.trim();
            if (val) {
                conditions.push({
                    target: row.querySelector('.cond-target').value,
                    operator: row.querySelector('.cond-op').value,
                    value: val,
                    negate: row.querySelector('.cond-negate-cb').checked,
                });
            }
        });

        if (!document.getElementById('waf-rule-name').value.trim()) {
            toast('Name is required', 'err'); return;
        }
        if (conditions.length === 0) {
            toast('At least one condition is required', 'err'); return;
        }

        var data = {
            name: document.getElementById('waf-rule-name').value.trim(),
            priority: parseInt(document.getElementById('waf-rule-priority').value) || 100,
            action: document.getElementById('waf-rule-action').value,
            conditions: conditions,
        };

        var r;
        if (this._editRuleId) {
            r = await API.put('/api/waf/rules/' + this._editRuleId, data);
        } else {
            r = await API.post('/api/waf/rules', data);
        }
        if (r && r.ok) {
            toast(this._editRuleId ? 'Rule updated' : 'Rule created', 'ok');
            this.closeRuleModal();
            this.fetchRules();
        } else {
            toast('Failed to save rule', 'err');
        }
    },

    async editRule(id) {
        var r = await API.get('/api/waf/rules');
        if (!r || !r.ok) return;
        var d = await r.json();
        var rule = d.rules.find(function(x) { return x.id === id; });
        if (rule) this.openRuleModal(rule);
    },

    async deleteRule(id) {
        if (!confirm('Delete this WAF rule?')) return;
        var r = await API.del('/api/waf/rules/' + id);
        if (r && r.ok) { toast('Rule deleted', 'ok'); this.fetchRules(); }
        else { toast('Failed', 'err'); }
    },

    // --- IP Lists ---

    async fetchIPLists() {
        var r = await API.get('/api/waf/ip-lists');
        if (!r || !r.ok) return;
        var d = await r.json();
        this.renderIPTable('waf-whitelist-table', d.whitelist, 'whitelist');
        this.renderIPTable('waf-blacklist-table', d.blacklist, 'blacklist');
    },

    renderIPTable(tableId, entries, listType) {
        var tb = document.querySelector('#' + tableId + ' tbody');
        if (entries.length === 0) {
            tb.innerHTML = '<tr><td colspan="3" class="text-muted" style="text-align:center">Empty</td></tr>';
            return;
        }
        var html = '';
        for (var i = 0; i < entries.length; i++) {
            var e = entries[i];
            html += '<tr>'
                + '<td><code>' + esc(e.address) + '</code></td>'
                + '<td class="text-muted">' + esc(e.note || '--') + '</td>'
                + '<td><button class="btn btn-xs btn-danger" '
                +   'onclick="WAFMgr.removeIP(\'' + listType + '\',\'' + esc(e.address) + '\')">&times;</button></td>'
                + '</tr>';
        }
        tb.innerHTML = html;
    },

    async addIP(listType) {
        var addr = prompt('Enter IP address or CIDR (e.g. 192.168.1.100 or 10.0.0.0/24):');
        if (!addr) return;
        var note = prompt('Note (optional):') || '';
        var r = await API.post('/api/waf/ip-lists/' + listType, { address: addr, note: note });
        if (r && r.ok) { toast('Added to ' + listType, 'ok'); this.fetchIPLists(); }
        else { toast('Failed', 'err'); }
    },

    async removeIP(listType, address) {
        var r = await API.del('/api/waf/ip-lists/' + listType + '/' + address);
        if (r && r.ok) { toast('Removed', 'ok'); this.fetchIPLists(); }
        else { toast('Failed', 'err'); }
    },

    // --- Rate Limits ---

    async fetchRateLimits() {
        var r = await API.get('/api/waf/rate-limits');
        if (!r || !r.ok) return;
        var d = await r.json();
        var tb = document.querySelector('#waf-ratelimit-table tbody');
        var empty = document.getElementById('waf-ratelimit-empty');

        if (d.rules.length === 0) {
            tb.innerHTML = '';
            empty.classList.remove('hidden');
            return;
        }
        empty.classList.add('hidden');

        var html = '';
        for (var i = 0; i < d.rules.length; i++) {
            var rule = d.rules[i];
            html += '<tr>'
                + '<td>' + esc(rule.name) + '</td>'
                + '<td><span class="badge">' + esc(rule.scope) + '</span></td>'
                + '<td>' + rule.requests + ' req</td>'
                + '<td>' + rule.window + 's</td>'
                + '<td>' + rule.block_duration + 's</td>'
                + '<td><button class="btn btn-xs btn-danger" '
                +   'onclick="WAFMgr.deleteRateLimit(\'' + rule.id + '\')">Del</button></td>'
                + '</tr>';
        }
        tb.innerHTML = html;
    },

    async addRateLimit() {
        var name = prompt('Rule name:');
        if (!name) return;
        var requests = parseInt(prompt('Max requests:', '100'));
        var window = parseInt(prompt('Time window (seconds):', '60'));
        var blockDuration = parseInt(prompt('Block duration (seconds):', '300'));
        if (!requests || !window) { toast('Invalid values', 'err'); return; }

        var r = await API.post('/api/waf/rate-limits', {
            name: name,
            requests: requests,
            window: window,
            block_duration: blockDuration || 300,
        });
        if (r && r.ok) { toast('Rate limit created', 'ok'); this.fetchRateLimits(); }
        else { toast('Failed', 'err'); }
    },

    async deleteRateLimit(id) {
        if (!confirm('Delete this rate limit rule?')) return;
        var r = await API.del('/api/waf/rate-limits/' + id);
        if (r && r.ok) { toast('Deleted', 'ok'); this.fetchRateLimits(); }
        else { toast('Failed', 'err'); }
    },

    // --- Geo Rules ---

    async fetchGeoRules() {
        var r = await API.get('/api/waf/geo-rules');
        if (!r || !r.ok) return;
        var d = await r.json();
        var tb = document.querySelector('#waf-geo-table tbody');
        var empty = document.getElementById('waf-geo-empty');

        if (d.rules.length === 0) {
            tb.innerHTML = '';
            empty.classList.remove('hidden');
            return;
        }
        empty.classList.add('hidden');

        var html = '';
        for (var i = 0; i < d.rules.length; i++) {
            var rule = d.rules[i];
            html += '<tr>'
                + '<td>' + esc(rule.countries.join(', ')) + '</td>'
                + '<td><span class="badge">' + esc(rule.mode) + '</span></td>'
                + '<td><span class="badge">' + esc(rule.action) + '</span></td>'
                + '<td><button class="btn btn-xs btn-danger" '
                +   'onclick="WAFMgr.deleteGeoRule(\'' + rule.id + '\')">Del</button></td>'
                + '</tr>';
        }
        tb.innerHTML = html;
    },

    async addGeoRule() {
        var countries = prompt('Country codes (comma-separated, e.g. CN,RU,KP):');
        if (!countries) return;
        var mode = prompt('Mode (blacklist or whitelist):', 'blacklist');
        if (mode !== 'blacklist' && mode !== 'whitelist') { toast('Invalid mode', 'err'); return; }

        var r = await API.post('/api/waf/geo-rules', {
            countries: countries.split(',').map(function(c) { return c.trim().toUpperCase(); }),
            mode: mode,
        });
        if (r && r.ok) { toast('Geo rule created', 'ok'); this.fetchGeoRules(); }
        else { toast('Failed', 'err'); }
    },

    async deleteGeoRule(id) {
        if (!confirm('Delete this geo rule?')) return;
        var r = await API.del('/api/waf/geo-rules/' + id);
        if (r && r.ok) { toast('Deleted', 'ok'); this.fetchGeoRules(); }
        else { toast('Failed', 'err'); }
    },

    // --- Logs ---

    async fetchLogs() {
        var ip = document.getElementById('waf-log-ip').value.trim();
        var cat = document.getElementById('waf-log-category').value;
        var params = '?limit=50';
        if (ip) params += '&source_ip=' + encodeURIComponent(ip);
        if (cat) params += '&category=' + encodeURIComponent(cat);

        var r = await API.get('/api/waf/logs' + params);
        if (!r || !r.ok) return;
        var d = await r.json();
        var tb = document.querySelector('#waf-log-table tbody');
        var empty = document.getElementById('waf-log-empty');

        if (d.logs.length === 0) {
            tb.innerHTML = '';
            empty.classList.remove('hidden');
            return;
        }
        empty.classList.add('hidden');

        var html = '';
        for (var i = 0; i < d.logs.length; i++) {
            var e = d.logs[i];
            var actionCls = e.action === 'block' ? 'badge-red' : 'badge-yellow';
            html += '<tr>'
                + '<td class="text-muted">' + fmtDate(e.timestamp) + '</td>'
                + '<td><code>' + esc(e.source_ip) + '</code></td>'
                + '<td>' + esc(e.method) + '</td>'
                + '<td class="text-muted" title="' + esc(e.url) + '">' + esc(truncate(e.url, 40)) + '</td>'
                + '<td>' + esc(e.rule_name) + '</td>'
                + '<td><span class="badge">' + esc(e.category) + '</span></td>'
                + '<td><span class="badge ' + actionCls + '">' + esc(e.action) + '</span></td>'
                + '</tr>';
        }
        tb.innerHTML = html;
    },
};

function truncate(s, n) {
    if (!s) return '';
    return s.length > n ? s.substring(0, n) + '...' : s;
}
