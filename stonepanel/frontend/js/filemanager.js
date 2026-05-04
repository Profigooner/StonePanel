const FileMgr = {
    cwd: '/',
    _editPath: null,

    start() {
        document.getElementById('upload-btn').addEventListener('click', function() {
            document.getElementById('file-input').click();
        });
        document.getElementById('file-input').addEventListener('change', function() {
            FileMgr.uploadFiles(this.files);
            this.value = '';
        });
        document.getElementById('mkdir-btn').addEventListener('click', function() {
            var name = prompt('Folder name:');
            if (name) FileMgr.mkdir(name);
        });
        document.getElementById('mkfile-btn').addEventListener('click', function() {
            var name = prompt('File name:');
            if (name) FileMgr.createFile(name);
        });

        // Editor modal
        document.getElementById('editor-close').addEventListener('click', function() { FileMgr.closeEditor(); });
        document.getElementById('editor-cancel').addEventListener('click', function() { FileMgr.closeEditor(); });
        document.getElementById('editor-save').addEventListener('click', function() { FileMgr.saveEditor(); });

        // Drag-and-drop
        var panel = document.getElementById('files-panel');
        var overlay = document.getElementById('drop-overlay');
        var dragCount = 0;
        panel.addEventListener('dragenter', function(e) {
            e.preventDefault();
            dragCount++;
            overlay.classList.remove('hidden');
        });
        panel.addEventListener('dragover', function(e) { e.preventDefault(); });
        panel.addEventListener('dragleave', function() {
            dragCount--;
            if (dragCount <= 0) { dragCount = 0; overlay.classList.add('hidden'); }
        });
        panel.addEventListener('drop', function(e) {
            e.preventDefault();
            dragCount = 0;
            overlay.classList.add('hidden');
            if (e.dataTransfer.files.length > 0) FileMgr.uploadFiles(e.dataTransfer.files);
        });

        // Close context menu on scroll / outside click
        document.addEventListener('click', function() { FileMgr.closeCtx(); });
        document.querySelector('#page-files .file-table-wrap').addEventListener('scroll', function() {
            FileMgr.closeCtx();
        });

        this.loadDir('/');
    },

    /* ---- Directory loading ---- */

    async loadDir(path) {
        this.cwd = path;
        var r = await API.get('/api/files/list?path=' + encodeURIComponent(path));
        if (!r) return;
        if (!r.ok) { toast('Failed to list directory', 'err'); return; }
        var d = await r.json();
        this.renderBreadcrumb(path);
        this.renderTable(d.items);
    },

    /* ---- Breadcrumb ---- */

    renderBreadcrumb(path) {
        var el = document.getElementById('breadcrumb');
        var parts = path.split('/').filter(Boolean);
        var html = '<span class="bc-seg" data-path="/">/</span>';
        var built = '';
        for (var i = 0; i < parts.length; i++) {
            built += '/' + parts[i];
            html += '<span class="bc-sep">/</span><span class="bc-seg" data-path="' + esc(built) + '">' + esc(parts[i]) + '</span>';
        }
        el.innerHTML = html;
        el.querySelectorAll('.bc-seg').forEach(function(seg) {
            seg.addEventListener('click', function() { FileMgr.loadDir(this.dataset.path); });
        });
    },

    /* ---- Table rendering ---- */

    renderTable(items) {
        var tb = document.querySelector('#file-table tbody');
        var emptyEl = document.getElementById('file-empty');
        var tableWrap = document.querySelector('#page-files .file-table-wrap');

        if (items.length === 0) {
            tb.innerHTML = '';
            tableWrap.classList.add('hidden');
            emptyEl.classList.remove('hidden');
            return;
        }
        tableWrap.classList.remove('hidden');
        emptyEl.classList.add('hidden');

        var html = '';
        for (var i = 0; i < items.length; i++) {
            var f = items[i];
            var nameClass = f.is_dir ? 'fname fname-dir' : 'fname fname-file';
            html += '<tr>'
                + '<td><span class="' + nameClass + '" data-path="' + esc(f.path) + '" data-dir="' + f.is_dir + '">' + esc(f.name) + '</span></td>'
                + '<td class="text-muted">' + (f.is_dir ? '--' : fmtBytes(f.size)) + '</td>'
                + '<td class="text-muted">' + fmtDate(f.modified) + '</td>'
                + '<td><code class="text-muted">' + esc(f.permissions) + '</code></td>'
                + '<td style="text-align:center"><button class="row-menu-btn" data-path="' + esc(f.path) + '" data-dir="' + f.is_dir + '">&middot;&middot;&middot;</button></td>'
                + '</tr>';
        }
        tb.innerHTML = html;

        // Name click -> navigate dir or edit file
        tb.querySelectorAll('.fname').forEach(function(el) {
            el.addEventListener('click', function() {
                if (this.dataset.dir === 'true') FileMgr.loadDir(this.dataset.path);
                else FileMgr.editFile(this.dataset.path);
            });
        });

        // Row menu buttons
        tb.querySelectorAll('.row-menu-btn').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                e.stopPropagation();
                FileMgr.openCtx(e, this.dataset.path, this.dataset.dir === 'true');
            });
        });
    },

    /* ---- Context menu ---- */

    openCtx(e, path, isDir) {
        this.closeCtx();
        var menu = document.createElement('div');
        menu.className = 'ctx-menu';
        menu.id = 'ctx-menu-active';

        var items = [];
        if (!isDir) {
            items.push({ icon: 'E', label: 'Edit',     action: 'edit' });
            items.push({ icon: 'D', label: 'Download', action: 'download' });
            items.push('sep');
        }
        items.push({ icon: 'R', label: 'Rename', action: 'rename' });
        items.push('sep');
        items.push({ icon: 'X', label: 'Delete', action: 'delete', danger: true });

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
            row.dataset.path = path;
            row.innerHTML = '<span class="ctx-icon">' + it.icon + '</span>' + esc(it.label);
            menu.appendChild(row);
        }

        document.body.appendChild(menu);

        // Position next to the button, flipping if near edge
        var btn = e.currentTarget.getBoundingClientRect();
        var mw = menu.offsetWidth, mh = menu.offsetHeight;
        var top = btn.bottom + 4;
        var left = btn.right - mw;
        if (top + mh > window.innerHeight - 8) top = btn.top - mh - 4;
        if (left < 8) left = 8;
        menu.style.top = top + 'px';
        menu.style.left = left + 'px';

        menu.addEventListener('click', function(ev) {
            var target = ev.target.closest('.ctx-item');
            if (!target) return;
            ev.stopPropagation();
            var action = target.dataset.action;
            var p = target.dataset.path;
            FileMgr.closeCtx();
            if (action === 'edit')     FileMgr.editFile(p);
            if (action === 'download') FileMgr.download(p);
            if (action === 'rename')   FileMgr.rename(p);
            if (action === 'delete')   FileMgr.remove(p);
        });
    },

    closeCtx() {
        var m = document.getElementById('ctx-menu-active');
        if (m) m.remove();
    },

    /* ---- File operations ---- */

    async editFile(path) {
        var r = await API.get('/api/files/read?path=' + encodeURIComponent(path));
        if (!r || !r.ok) { toast('Cannot read file', 'err'); return; }
        var d = await r.json();
        document.getElementById('editor-title').textContent = path;
        document.getElementById('editor-area').value = d.content;
        document.getElementById('editor-overlay').classList.remove('hidden');
        this._editPath = path;
    },

    async saveEditor() {
        var content = document.getElementById('editor-area').value;
        var r = await API.put('/api/files/write', { path: this._editPath, content: content });
        if (r && r.ok) { toast('Saved', 'ok'); this.closeEditor(); this.loadDir(this.cwd); }
        else { toast('Save failed', 'err'); }
    },

    closeEditor() {
        document.getElementById('editor-overlay').classList.add('hidden');
    },

    download(path) {
        API.get('/api/files/download?path=' + encodeURIComponent(path)).then(function(r) {
            if (!r) return;
            return r.blob();
        }).then(function(blob) {
            if (!blob) return;
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = path.split('/').pop();
            a.click();
            URL.revokeObjectURL(url);
        });
    },

    async rename(path) {
        var name = prompt('New name:', path.split('/').pop());
        if (!name) return;
        var dir = path.substring(0, path.lastIndexOf('/')) || '/';
        var newPath = dir + '/' + name;
        var r = await API.post('/api/files/rename', { old_path: path, new_path: newPath });
        if (r && r.ok) { toast('Renamed', 'ok'); this.loadDir(this.cwd); }
        else { toast('Rename failed', 'err'); }
    },

    async remove(path) {
        if (!confirm('Delete ' + path + '?')) return;
        var r = await API.del('/api/files/delete?path=' + encodeURIComponent(path));
        if (r && r.ok) { toast('Deleted', 'ok'); this.loadDir(this.cwd); }
        else { toast('Delete failed', 'err'); }
    },

    async mkdir(name) {
        var path = this.cwd === '/' ? '/' + name : this.cwd + '/' + name;
        var r = await API.post('/api/files/mkdir', { path: path });
        if (r && r.ok) { toast('Created', 'ok'); this.loadDir(this.cwd); }
        else { toast('Failed', 'err'); }
    },

    async createFile(name) {
        var path = this.cwd === '/' ? '/' + name : this.cwd + '/' + name;
        var r = await API.put('/api/files/write', { path: path, content: '' });
        if (r && r.ok) { toast('Created', 'ok'); this.loadDir(this.cwd); }
        else { toast('Failed', 'err'); }
    },

    async uploadFiles(fileList) {
        for (var i = 0; i < fileList.length; i++) {
            var file = fileList[i];
            var path = this.cwd === '/' ? '/' + file.name : this.cwd + '/' + file.name;
            var fd = new FormData();
            fd.append('file', file);
            var r = await API.post('/api/files/upload?path=' + encodeURIComponent(path), fd);
            if (r && r.ok) toast('Uploaded ' + file.name, 'ok');
            else toast('Upload failed: ' + file.name, 'err');
        }
        this.loadDir(this.cwd);
    },
};

function fmtDate(ts) {
    var d = new Date(ts * 1000);
    var Y = d.getFullYear(), M = pad(d.getMonth()+1), D = pad(d.getDate());
    var h = pad(d.getHours()), m = pad(d.getMinutes());
    return Y + '-' + M + '-' + D + ' ' + h + ':' + m;
}
function pad(n) { return n < 10 ? '0' + n : '' + n; }
