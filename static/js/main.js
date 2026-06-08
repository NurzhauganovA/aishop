// SmartShop — main.js

document.addEventListener('DOMContentLoaded', function() {

    // ── Real-time notifications via WebSocket ──────────────────────
    var isLoggedIn = document.body.dataset.userAuthenticated === 'true' ||
                     !!document.getElementById('userDropdownBtn');

    if (isLoggedIn) {
        connectNotifications();
    }

    function connectNotifications() {
        var wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws/notifications/';
        var socket;
        try {
            socket = new WebSocket(wsUrl);
        } catch(e) { return; }

        socket.onmessage = function(e) {
            try {
                var data = JSON.parse(e.data);
                if (data.type === 'notification') showToast(data.notification);
                if (data.type === 'unread_count') updateNotificationBadge(data.count);
            } catch(err) {}
        };

        socket.onclose = function() {
            setTimeout(connectNotifications, 5000);
        };
    }

    function showToast(notification) {
        var container = document.getElementById('toastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toastContainer';
            container.style.cssText = 'position:fixed;bottom:24px;left:24px;z-index:9990;display:flex;flex-direction:column;gap:10px;max-width:340px';
            document.body.appendChild(container);
        }

        var toast = document.createElement('div');
        toast.style.cssText = 'background:#fff;border:1px solid var(--border);border-radius:12px;padding:14px 16px;box-shadow:0 10px 25px rgba(0,0,0,.12);display:flex;gap:12px;align-items:flex-start;animation:slideInLeft .3s ease';
        toast.innerHTML = '<span style="font-size:20px;flex-shrink:0">🔔</span>' +
            '<div style="flex:1;min-width:0">' +
                '<div style="font-size:13px;font-weight:600;color:var(--text);margin-bottom:3px">' + (notification.title || 'Уведомление') + '</div>' +
                '<div style="font-size:12px;color:var(--text-secondary)">' + (notification.message || '') + '</div>' +
                (notification.link ? '<a href="' + notification.link + '" style="font-size:12px;color:var(--primary);font-weight:600;margin-top:6px;display:inline-block">Перейти →</a>' : '') +
            '</div>' +
            '<button onclick="this.parentNode.remove()" style="background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:16px;padding:0;flex-shrink:0">×</button>';

        container.appendChild(toast);
        setTimeout(function() { if (toast.parentNode) toast.remove(); }, 6000);
    }

    function updateNotificationBadge(count) {
        // Update notification badge in navbar
        document.querySelectorAll('.notification-count').forEach(function(el) {
            if (count > 0) { el.textContent = count; el.style.display = 'flex'; }
            else { el.style.display = 'none'; }
        });
    }

    // ── Slideup animation for toasts ──────────────────────────────
    var style = document.createElement('style');
    style.textContent = '@keyframes slideInLeft{from{opacity:0;transform:translateX(-20px)}to{opacity:1;transform:translateX(0)}}';
    document.head.appendChild(style);

});
