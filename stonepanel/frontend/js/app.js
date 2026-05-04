const App = {
    currentPage: 'dashboard',

    async init() {
        if (API.token) {
            // Verify token
            var r = await API.get('/api/system/info');
            if (r && r.ok) { this.enterApp(); return; }
        }
        // Show login
        document.getElementById('login-page').classList.remove('hidden');
        document.getElementById('app').classList.add('hidden');
        Auth.init();
    },

    enterApp() {
        document.getElementById('login-page').classList.add('hidden');
        document.getElementById('app').classList.remove('hidden');

        // Nav
        document.querySelectorAll('.nav-item').forEach(function(item) {
            item.addEventListener('click', function() {
                App.navigate(this.dataset.page);
            });
        });

        document.getElementById('logout-btn').addEventListener('click', function() {
            API.logout();
        });

        // Resize
        window.addEventListener('resize', function() { TermMgr.handleResize(); });

        // Start default page
        Dashboard.start();
        TermMgr.start();
        FileMgr.start();
        ScreenMgr.start();
        CronMgr.start();
        ServiceMgr.start();
        ProxyMgr.start();
        WAFMgr.start();
        this.navigate('dashboard');
    },

    navigate(page) {
        // Update nav
        document.querySelectorAll('.nav-item').forEach(function(item) {
            item.classList.toggle('active', item.dataset.page === page);
        });

        // Toggle pages
        var pages = ['dashboard', 'terminal', 'files', 'screen', 'cron', 'services', 'proxy', 'waf'];
        for (var i = 0; i < pages.length; i++) {
            var el = document.getElementById('page-' + pages[i]);
            if (pages[i] === page) {
                el.classList.remove('hidden');
                if (pages[i] === 'terminal') el.classList.add('visible');
            } else {
                el.classList.add('hidden');
                if (pages[i] === 'terminal') el.classList.remove('visible');
            }
        }

        // Page lifecycle
        if (page === 'dashboard') { Dashboard.start(); }
        else { Dashboard.stop(); }

        if (page === 'terminal') {
            setTimeout(function() { TermMgr.handleResize(); }, 50);
        }
        if (page === 'files') {
            FileMgr.loadDir(FileMgr.cwd);
        }
        if (page === 'screen') {
            ScreenMgr.refresh();
        }
        if (page === 'cron') {
            CronMgr.refresh();
        }
        if (page === 'services') {
            ServiceMgr.refresh();
        }
        if (page === 'proxy') {
            ProxyMgr.refresh();
        }
        if (page === 'waf') {
            WAFMgr.refresh();
        }

        this.currentPage = page;
    },
};

document.addEventListener('DOMContentLoaded', function() { App.init(); });
