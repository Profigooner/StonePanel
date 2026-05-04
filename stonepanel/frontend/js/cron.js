var CronMgr = {
    jobs: [],

    start: function() {
        var self = this;
        document.getElementById('cron-refresh-btn').addEventListener('click', function() { self.refresh(); });
        document.getElementById('cron-add-btn').addEventListener('click', function() { self.openModal(); });
        document.getElementById('cron-modal-close').addEventListener('click', function() { self.closeModal(); });
        document.getElementById('cron-modal-cancel').addEventListener('click', function() { self.closeModal(); });
        document.getElementById('cron-modal-save').addEventListener('click', function() { self.save(); });
        document.getElementById('cron-preset').addEventListener('change', function() { self.applyPreset(this.value); });

        // Live preview on schedule field changes
        var fields = ['cron-minute', 'cron-hour', 'cron-day', 'cron-month', 'cron-weekday'];
        for (var i = 0; i < fields.length; i++) {
            (function(id) {
                document.getElementById(id).addEventListener('input', function() { self.updatePreview(); });
            })(fields[i]);
        }
    },

    refresh: async function() {
        var r = await API.get('/api/cron/jobs');
        if (!r || !r.ok) return;
        var data = await r.json();
        this.jobs = data.jobs || [];
        this.render();
    },

    render: function() {
        var tbody = document.querySelector('#cron-table tbody');
        var empty = document.getElementById('cron-empty');
        tbody.innerHTML = '';

        if (this.jobs.length === 0) {
            empty.classList.remove('hidden');
            return;
        }
        empty.classList.add('hidden');

        for (var i = 0; i < this.jobs.length; i++) {
            var j = this.jobs[i];
            var tr = document.createElement('tr');
            tr.innerHTML =
                '<td><label class="toggle-switch"><input type="checkbox"' + (j.enabled ? ' checked' : '') +
                ' data-id="' + j.id + '"><span class="toggle-slider"></span></label></td>' +
                '<td><span class="text-muted">' + this.esc(j.schedule) + '</span><br>' + this.esc(j.human_schedule) + '</td>' +
                '<td><code>' + this.esc(j.command) + '</code></td>' +
                '<td>' + this.esc(j.description || '') + '</td>' +
                '<td class="col-act">' +
                '<button class="btn btn-xs cron-edit-btn" data-id="' + j.id + '">Edit</button> ' +
                '<button class="btn btn-xs btn-danger cron-del-btn" data-id="' + j.id + '">Del</button></td>';
            tbody.appendChild(tr);
        }

        var self = this;
        tbody.querySelectorAll('.toggle-switch input').forEach(function(cb) {
            cb.addEventListener('change', function() {
                self.toggle(this.dataset.id, this.checked);
            });
        });
        tbody.querySelectorAll('.cron-edit-btn').forEach(function(btn) {
            btn.addEventListener('click', function() { self.edit(this.dataset.id); });
        });
        tbody.querySelectorAll('.cron-del-btn').forEach(function(btn) {
            btn.addEventListener('click', function() { self.del(this.dataset.id); });
        });
    },

    openModal: function(job) {
        document.getElementById('cron-modal').classList.remove('hidden');
        document.getElementById('cron-edit-id').value = job ? job.id : '';
        document.getElementById('cron-modal-title').textContent = job ? 'Edit Cron Job' : 'Add Cron Job';
        document.getElementById('cron-preset').value = 'custom';

        if (job) {
            var parts = job.schedule.split(' ');
            document.getElementById('cron-minute').value = parts[0] || '*';
            document.getElementById('cron-hour').value = parts[1] || '*';
            document.getElementById('cron-day').value = parts[2] || '*';
            document.getElementById('cron-month').value = parts[3] || '*';
            document.getElementById('cron-weekday').value = parts[4] || '*';
            document.getElementById('cron-command').value = job.command;
            document.getElementById('cron-description').value = job.description || '';
        } else {
            document.getElementById('cron-minute').value = '*';
            document.getElementById('cron-hour').value = '*';
            document.getElementById('cron-day').value = '*';
            document.getElementById('cron-month').value = '*';
            document.getElementById('cron-weekday').value = '*';
            document.getElementById('cron-command').value = '';
            document.getElementById('cron-description').value = '';
        }
        this.updatePreview();
    },

    closeModal: function() {
        document.getElementById('cron-modal').classList.add('hidden');
    },

    applyPreset: function(preset) {
        var presets = {
            'everymin':  ['*', '*', '*', '*', '*'],
            'hourly':    ['0', '*', '*', '*', '*'],
            'daily':     ['0', '0', '*', '*', '*'],
            'weekly':    ['0', '0', '*', '*', '0'],
            'monthly':   ['0', '0', '1', '*', '*'],
        };
        var vals = presets[preset];
        if (!vals) return;
        document.getElementById('cron-minute').value = vals[0];
        document.getElementById('cron-hour').value = vals[1];
        document.getElementById('cron-day').value = vals[2];
        document.getElementById('cron-month').value = vals[3];
        document.getElementById('cron-weekday').value = vals[4];
        this.updatePreview();
    },

    updatePreview: async function() {
        var expr = [
            document.getElementById('cron-minute').value,
            document.getElementById('cron-hour').value,
            document.getElementById('cron-day').value,
            document.getElementById('cron-month').value,
            document.getElementById('cron-weekday').value,
        ].join(' ');
        var r = await API.post('/api/cron/validate', { expression: expr });
        var el = document.getElementById('cron-preview');
        if (r && r.ok) {
            var data = await r.json();
            el.textContent = data.valid ? data.message : data.message;
            el.style.color = data.valid ? 'var(--green)' : 'var(--red)';
        } else {
            el.textContent = expr;
            el.style.color = '';
        }
    },

    save: async function() {
        var id = document.getElementById('cron-edit-id').value;
        var body = {
            minute: document.getElementById('cron-minute').value.trim(),
            hour: document.getElementById('cron-hour').value.trim(),
            day: document.getElementById('cron-day').value.trim(),
            month: document.getElementById('cron-month').value.trim(),
            weekday: document.getElementById('cron-weekday').value.trim(),
            command: document.getElementById('cron-command').value.trim(),
            description: document.getElementById('cron-description').value.trim(),
        };

        if (!body.command) {
            API.toast('Command is required', 'error');
            return;
        }

        var r;
        if (id) {
            r = await API.put('/api/cron/jobs/' + id, body);
        } else {
            r = await API.post('/api/cron/jobs', body);
        }

        if (r && r.ok) {
            API.toast(id ? 'Job updated' : 'Job created', 'success');
            this.closeModal();
            this.refresh();
        } else {
            var err = r ? await r.json().catch(function() { return {}; }) : {};
            API.toast(err.detail || 'Failed to save job', 'error');
        }
    },

    edit: function(id) {
        for (var i = 0; i < this.jobs.length; i++) {
            if (this.jobs[i].id === id) {
                this.openModal(this.jobs[i]);
                return;
            }
        }
    },

    del: async function(id) {
        if (!confirm('Delete this cron job?')) return;
        var r = await API.delete('/api/cron/jobs/' + id);
        if (r && r.ok) {
            API.toast('Job deleted', 'success');
            this.refresh();
        } else {
            API.toast('Failed to delete job', 'error');
        }
    },

    toggle: async function(id, enabled) {
        var r = await API.post('/api/cron/jobs/' + id + '/toggle', { enabled: enabled });
        if (r && r.ok) {
            API.toast(enabled ? 'Job enabled' : 'Job disabled', 'success');
        } else {
            API.toast('Failed to toggle job', 'error');
            this.refresh();
        }
    },

    esc: function(s) {
        var d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }
};
