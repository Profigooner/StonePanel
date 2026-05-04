const Dashboard = {
    interval: null,
    sortBy: 'cpu',
    prevNet: null,
    prevNetTime: null,

    start() {
        this.fetchInfo();
        this.fetchStats();
        this.fetchProcs();
        this.interval = setInterval(function() {
            Dashboard.fetchStats();
            Dashboard.fetchProcs();
        }, 3000);

        document.getElementById('sort-cpu').addEventListener('click', function() {
            Dashboard.sortBy = 'cpu';
            this.classList.add('active');
            document.getElementById('sort-mem').classList.remove('active');
            Dashboard.fetchProcs();
        });
        document.getElementById('sort-mem').addEventListener('click', function() {
            Dashboard.sortBy = 'memory';
            this.classList.add('active');
            document.getElementById('sort-cpu').classList.remove('active');
            Dashboard.fetchProcs();
        });
    },

    stop() {
        if (this.interval) { clearInterval(this.interval); this.interval = null; }
    },

    async fetchInfo() {
        const r = await API.get('/api/system/info');
        if (!r) return;
        const d = await r.json();
        document.getElementById('header-hostname').textContent = d.hostname;
        document.getElementById('header-uptime').textContent = 'up ' + fmtUptime(d.uptime);
        var html = '';
        var items = [
            ['Hostname', d.hostname], ['OS', d.os], ['Arch', d.arch],
            ['CPUs', d.cpu_count], ['Memory', fmtBytes(d.total_memory)], ['Python', d.python],
        ];
        for (var i = 0; i < items.length; i++) {
            html += '<div class="info-item"><div class="label">' + items[i][0] + '</div><div class="val">' + items[i][1] + '</div></div>';
        }
        document.getElementById('sys-info').innerHTML = html;
    },

    async fetchStats() {
        const r = await API.get('/api/system/stats');
        if (!r) return;
        const d = await r.json();
        setGauge('cpu', d.cpu_percent);
        setGauge('mem', d.memory.percent);
        setGauge('disk', d.disk.percent);

        document.getElementById('mem-value').textContent = d.memory.percent.toFixed(1) + '% (' + fmtBytes(d.memory.used) + ')';
        document.getElementById('disk-value').textContent = d.disk.percent.toFixed(1) + '% (' + fmtBytes(d.disk.used) + ')';

        var now = Date.now();
        if (this.prevNet && this.prevNetTime) {
            var dt = (now - this.prevNetTime) / 1000;
            var up = (d.network.bytes_sent - this.prevNet.bytes_sent) / dt;
            var dn = (d.network.bytes_recv - this.prevNet.bytes_recv) / dt;
            document.getElementById('net-up').textContent = fmtBytes(up) + '/s up';
            document.getElementById('net-down').textContent = fmtBytes(dn) + '/s down';
        } else {
            document.getElementById('net-up').textContent = fmtBytes(d.network.bytes_sent) + ' sent';
            document.getElementById('net-down').textContent = fmtBytes(d.network.bytes_recv) + ' recv';
        }
        this.prevNet = d.network;
        this.prevNetTime = now;
    },

    async fetchProcs() {
        const r = await API.get('/api/system/processes?sort_by=' + this.sortBy);
        if (!r) return;
        const d = await r.json();
        var tb = document.querySelector('#proc-table tbody');
        var html = '';
        for (var i = 0; i < d.processes.length; i++) {
            var p = d.processes[i];
            html += '<tr><td>' + (p.pid || '') + '</td><td>' + esc(p.name || '') + '</td>'
                + '<td>' + (p.cpu_percent != null ? p.cpu_percent.toFixed(1) : '-') + '</td>'
                + '<td>' + (p.memory_percent != null ? p.memory_percent.toFixed(1) : '-') + '</td>'
                + '<td>' + esc(p.username || '-') + '</td>'
                + '<td>' + esc(p.status || '-') + '</td></tr>';
        }
        tb.innerHTML = html;
    },
};

function setGauge(id, pct) {
    var valEl = document.getElementById(id + '-value');
    var fill  = document.getElementById(id + '-gauge');
    if (id === 'cpu') valEl.textContent = pct.toFixed(1) + '%';
    fill.style.width = Math.min(pct, 100) + '%';
    fill.className = 'gauge-fill' + (pct >= 80 ? ' crit' : pct >= 60 ? ' warn' : '');
}

function fmtBytes(b) {
    if (b == null || b === 0) return '0 B';
    var k = 1024, s = ['B','KB','MB','GB','TB'];
    var i = Math.floor(Math.log(Math.abs(b)) / Math.log(k));
    if (i >= s.length) i = s.length - 1;
    return (b / Math.pow(k, i)).toFixed(1) + ' ' + s[i];
}

function fmtUptime(sec) {
    var d = Math.floor(sec / 86400);
    var h = Math.floor((sec % 86400) / 3600);
    var m = Math.floor((sec % 3600) / 60);
    return d + 'd ' + h + 'h ' + m + 'm';
}

function esc(s) {
    var el = document.createElement('span');
    el.textContent = s;
    return el.innerHTML;
}
