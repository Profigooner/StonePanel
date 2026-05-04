# StonePanel

A lightweight, self-hosted server management panel built with FastAPI. Install it on any Linux server and manage everything from your browser.

## Features

- **Dashboard** -- Real-time CPU, memory, disk, and network monitoring with top process listing
- **Web Terminal** -- Full PTY terminal in your browser (powered by xterm.js), with multi-tab support
- **File Manager** -- Browse, upload, download, edit, rename, and delete files through a visual interface
- **Authentication** -- JWT-based auth with bcrypt password hashing; first-visit setup flow
- **Reverse Proxy** -- HTTP/HTTPS/TCP/UDP proxy rule management with Caddy integration, load balancing, health checks, and auto-TLS
- **WAF** -- Web Application Firewall with OWASP CRS rules, custom regex rules, IP whitelist/blacklist, rate limiting, and geo-blocking
- **Dark Theme** -- Clean, modern UI designed for server admins
- **Single Binary** -- Pure Python, no Node.js build step; frontend served as static files

## Quick Start

### Requirements

- Python 3.10+
- Linux server (macOS supported for development)

### Install

```bash
git clone https://github.com/Profigooner/StonePanel.git
cd StonePanel
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run

```bash
python run.py
```

Open `http://your-server-ip:6767` in your browser. On first visit, you'll be prompted to set a password.

### Development Mode

```bash
python run.py --dev
```

Enables auto-reload and CORS for local frontend development.

### Configuration

All settings can be overridden via environment variables with the `STONEPANEL_` prefix:

| Variable | Default | Description |
|---|---|---|
| `STONEPANEL_PORT` | `6767` | Server port |
| `STONEPANEL_HOST` | `0.0.0.0` | Bind address |
| `STONEPANEL_SECRET_KEY` | (random) | JWT signing key (set this in production) |
| `STONEPANEL_DATA_DIR` | `~/.stonepanel` | Data directory (stores auth credentials) |
| `STONEPANEL_FILE_ROOT` | `/` | Root path for the file manager |
| `STONEPANEL_DEV_MODE` | `false` | Enable dev mode |

## Architecture

```
stonepanel/
├── main.py              # App factory, static file serving
├── config.py            # Settings (pydantic-settings)
├── deps.py              # Auth dependency injection
├── auth/                # JWT auth + bcrypt passwords
├── terminal/            # PTY session manager + WebSocket
├── filemanager/         # File CRUD with path sandboxing
├── system/              # System stats via psutil
└── frontend/            # Static HTML/CSS/JS (no build step)
    ├── index.html
    ├── css/style.css
    └── js/
        ├── app.js       # SPA router
        ├── auth.js      # Login/token management
        ├── dashboard.js # System monitoring
        ├── terminal.js  # xterm.js + WebSocket terminals
        └── filemanager.js
```

## API

All endpoints are under `/api/` and require a Bearer token (except `/api/auth/status`, `/api/auth/setup`, `/api/auth/login`).

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/auth/status` | Check if setup is complete |
| POST | `/api/auth/setup` | Set initial password |
| POST | `/api/auth/login` | Login, returns JWT |
| GET | `/api/system/info` | Hostname, OS, CPU count, memory |
| GET | `/api/system/stats` | Live CPU/memory/disk/network stats |
| GET | `/api/system/processes` | Top processes (sort_by=cpu\|memory) |
| POST | `/api/terminal/sessions` | Create a terminal session |
| GET | `/api/terminal/sessions` | List active sessions |
| DELETE | `/api/terminal/sessions/{id}` | Kill a session |
| WS | `/api/terminal/ws/{id}?token=` | WebSocket terminal I/O |
| GET | `/api/files/list?path=` | List directory |
| GET | `/api/files/read?path=` | Read file content |
| PUT | `/api/files/write` | Write/create a file |
| POST | `/api/files/upload?path=` | Upload a file |
| GET | `/api/files/download?path=` | Download a file |
| DELETE | `/api/files/delete?path=` | Delete file or directory |
| POST | `/api/files/mkdir` | Create directory |
| POST | `/api/files/rename` | Rename/move |
| GET | `/api/files/info?path=` | File metadata |

## Testing

```bash
pip install -r requirements.txt
pytest tests/ -v
```

## Security Notes

- Always set `STONEPANEL_SECRET_KEY` to a fixed value in production (otherwise tokens invalidate on restart)
- Use a reverse proxy (nginx/caddy) with HTTPS in production
- The file manager is sandboxed to `STONEPANEL_FILE_ROOT` to prevent path traversal
- Consider binding to `127.0.0.1` and using SSH tunneling if the server is not behind a firewall

## Roadmap

- [ ] Docker container management
- [ ] Screen/tmux session management
- [ ] Firewall management (iptables/ufw)
- [ ] Python web project deployment wizard
- [ ] System service management (systemd)
- [ ] Multi-user support
- [ ] Cron job management -- View, create, edit, and delete cron jobs from the UI
- [ ] Database management -- MySQL/PostgreSQL/Redis instance management, user creation, backup/restore
- [ ] Log viewer -- Browse and search system logs (journalctl, syslog) and application logs in real time
- [ ] Backup & scheduled tasks -- Scheduled backup of files/databases to local or remote storage (S3, SFTP)
- [ ] Notification & alerting -- Email/Webhook/Telegram alerts when CPU/memory/disk exceeds thresholds or services go down
- [ ] Two-factor authentication (TOTP) -- Google Authenticator / Authy support for login security
- [ ] SSH key management -- Add, remove, and manage authorized_keys from the UI
- [ ] System package management -- View installed packages, check for updates, install/remove via apt/yum
- [ ] Audit log -- Record all user actions (login, file changes, service restarts) with timestamps
- [ ] SSL certificate management -- Let's Encrypt certificate issuance, renewal tracking, and expiration alerts
- [ ] Runtime environment management -- Install/switch Python versions (pyenv), Java (SDKMAN), Node.js (nvm), Go, etc. with UI-managed version switching
- [ ] Application marketplace -- One-click deploy common self-hosted apps (Nginx, MySQL, Redis, WordPress, Gitea, Nextcloud, etc.) with pre-built templates
- [ ] Network diagnostics toolkit -- Built-in ping, traceroute, DNS lookup, port scan, speed test, and connection tracking from the UI
- [ ] Resource usage history & charts -- Persistent CPU/memory/disk/bandwidth history with time-series charts (hourly/daily/weekly trends)
- [ ] Webhook & API integration -- Expose webhooks for CI/CD pipelines (GitHub/GitLab push-to-deploy), custom automation triggers
- [ ] Multi-server management -- Manage multiple remote servers from a single StonePanel instance via agent mode
- [ ] File editor enhancements -- Syntax highlighting (CodeMirror/Monaco), diff view, git status indicators, and in-browser image preview
- [ ] AI ops assistant -- LLM-powered log analysis, natural language server commands ("restart nginx", "show me failed logins"), anomaly detection and root cause suggestions
- [ ] Server health score -- Composite score (security, performance, configuration) with actionable optimization recommendations
- [ ] Collaborative terminal -- Share a live terminal session with teammates (like tmate/pair programming), with view-only and full-control modes
- [ ] Command snippet library -- Save, tag, and one-click execute frequently used commands; share snippets across team
- [ ] Process guardian -- Supervisor-like process manager: keep services alive, auto-restart on crash, resource limits, log tailing per process
- [ ] Security hardening wizard -- Guided SSH hardening, fail2ban setup, unused port closure, kernel parameter tuning, with a before/after security score
- [ ] Terminal session recording & playback -- Record all terminal sessions as asciinema-style recordings, searchable and replayable for audit and training
- [ ] Visual network topology -- Auto-discover and render a live map of services, ports, and connections between your servers
- [ ] Custom dashboard builder -- Drag-and-drop widgets (CPU gauge, log stream, service status, custom shell output) to build personalized monitoring dashboards
- [ ] Git deployment manager -- View deployed repos, pull/switch branches, view diff since last deploy, one-click rollback to previous commit
- [ ] Mobile PWA -- Progressive Web App with responsive UI, push notifications, and quick actions optimized for phone screens
- [ ] Hosts & local DNS management -- Edit /etc/hosts, manage local DNS entries (dnsmasq/CoreDNS) from the UI
- [ ] Scheduled power management -- Schedule server reboot, shutdown, wake-on-LAN, and maintenance windows with pre/post scripts

## License

MIT
