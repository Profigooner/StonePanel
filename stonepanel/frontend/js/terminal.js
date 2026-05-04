const TermMgr = {
    sessions: {},   // id -> { term, ws, fitAddon, tabEl, containerEl }
    activeId: null,

    start() {
        document.getElementById('new-term-btn').addEventListener('click', function() {
            TermMgr.createSession();
        });
    },

    async createSession() {
        var r = await API.post('/api/terminal/sessions');
        if (!r) return;
        var d = await r.json();
        var sid = d.session_id;
        this.addTab(sid);
        this.switchTo(sid);
    },

    addTab(sid, label) {
        var tab = document.createElement('div');
        tab.className = 'term-tab';
        tab.dataset.sid = sid;
        var idx = Object.keys(this.sessions).length + 1;
        var tabLabel = label || ('Terminal ' + idx);
        tab.innerHTML = '<span class="tab-label">' + tabLabel + '</span><span class="tab-close">&times;</span>';
        tab.querySelector('.tab-label').addEventListener('click', function() {
            TermMgr.switchTo(sid);
        });
        tab.querySelector('.tab-close').addEventListener('click', function(e) {
            e.stopPropagation();
            TermMgr.killSession(sid);
        });
        document.getElementById('term-tabs').appendChild(tab);

        // Container
        var box = document.createElement('div');
        box.style.cssText = 'width:100%;height:100%;display:none;';
        document.getElementById('term-viewport').appendChild(box);

        // xterm
        var term = new Terminal({
            cursorBlink: true,
            fontSize: 14,
            fontFamily: '"SF Mono","Fira Code","Cascadia Code",Menlo,Consolas,monospace',
            theme: { background: '#0d1117', foreground: '#e6edf3', cursor: '#58a6ff' },
        });
        var fit = new FitAddon.FitAddon();
        term.loadAddon(fit);
        term.open(box);
        fit.fit();

        // WebSocket
        var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        var ws = new WebSocket(proto + '//' + location.host + '/api/terminal/ws/' + sid + '?token=' + API.token);
        ws.binaryType = 'arraybuffer';

        ws.addEventListener('message', function(e) {
            if (e.data instanceof ArrayBuffer) {
                term.write(new Uint8Array(e.data));
            } else {
                try {
                    var msg = JSON.parse(e.data);
                    if (msg.error) { toast(msg.error, 'err'); }
                } catch (_) {
                    term.write(e.data);
                }
            }
        });
        ws.addEventListener('close', function() {
            term.write('\r\n\x1b[90m[session ended]\x1b[0m\r\n');
        });

        term.onData(function(data) {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'input', data: data }));
            }
        });

        this.sessions[sid] = { term: term, ws: ws, fitAddon: fit, tabEl: tab, containerEl: box };
    },

    switchTo(sid) {
        // Hide all
        for (var id in this.sessions) {
            var s = this.sessions[id];
            s.containerEl.style.display = 'none';
            s.tabEl.classList.remove('active');
        }
        // Show target
        var sess = this.sessions[sid];
        if (!sess) return;
        sess.containerEl.style.display = 'block';
        sess.tabEl.classList.add('active');
        sess.fitAddon.fit();
        sess.term.focus();
        this.activeId = sid;

        // Send resize
        var dims = sess.fitAddon.proposeDimensions();
        if (dims && sess.ws.readyState === WebSocket.OPEN) {
            sess.ws.send(JSON.stringify({ type: 'resize', rows: dims.rows, cols: dims.cols }));
        }

        // Remove placeholder
        var ph = document.querySelector('#term-viewport .placeholder');
        if (ph) ph.remove();
    },

    async killSession(sid) {
        var sess = this.sessions[sid];
        if (!sess) return;
        if (sess.ws.readyState === WebSocket.OPEN) sess.ws.close();
        sess.term.dispose();
        sess.tabEl.remove();
        sess.containerEl.remove();
        delete this.sessions[sid];
        await API.del('/api/terminal/sessions/' + sid);

        // Switch to another tab or show placeholder
        var remaining = Object.keys(this.sessions);
        if (remaining.length > 0) {
            this.switchTo(remaining[remaining.length - 1]);
        } else {
            this.activeId = null;
            var vp = document.getElementById('term-viewport');
            var ph = document.createElement('div');
            ph.className = 'placeholder';
            ph.textContent = 'Create a terminal to get started';
            vp.appendChild(ph);
        }
    },

    handleResize() {
        if (this.activeId && this.sessions[this.activeId]) {
            var s = this.sessions[this.activeId];
            s.fitAddon.fit();
            var dims = s.fitAddon.proposeDimensions();
            if (dims && s.ws.readyState === WebSocket.OPEN) {
                s.ws.send(JSON.stringify({ type: 'resize', rows: dims.rows, cols: dims.cols }));
            }
        }
    },

    cleanup() {
        for (var id in this.sessions) {
            var s = this.sessions[id];
            if (s.ws.readyState === WebSocket.OPEN) s.ws.close();
            s.term.dispose();
        }
        this.sessions = {};
        this.activeId = null;
    },
};
