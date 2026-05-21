from PyQt5.QtWidgets import (QWidget, QVBoxLayout)
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtCore import Qt, QTimer, pyqtSignal

from .usage_snapshot import UsageSnapshot
from .html_template import render_html, DEFAULT_THEME, make_update_json
from .config_manager import ConfigManager

WIDTH = 520


class _DragPage(QWebEnginePage):
    """Custom page that forwards JS console drag/resize messages to the widget."""
    def __init__(self, widget: "FloatingWidget"):
        super().__init__(widget)
        self._widget = widget

    def _fit_height(self, content_h: int) -> int:
        """Calculate window height from content scrollHeight."""
        from PyQt5.QtWidgets import QApplication
        screen_h = QApplication.primaryScreen().availableGeometry().height()
        return max(80, min(content_h + 8, int(screen_h * 0.6)))

    def _set_height(self, target_h: int):
        self._widget.resize(self._widget.width(), target_h)
        self._sync_geo_to_js()

    def javaScriptConsoleMessage(self, level, msg, line, source):
        if msg.startswith("__DRAG__:"):
            parts = msg[9:].split(",")
            dx, dy = int(parts[0]), int(parts[1])
            self._widget.move(self._widget.x() + dx, self._widget.y() + dy)
        elif msg == "__DRAG_END__":
            ConfigManager.instance().set_general("window_x", self._widget.x())
            ConfigManager.instance().set_general("window_y", self._widget.y())
            self._sync_geo_to_js()
        elif msg.startswith("__RESIZE__:"):
            parts = msg[11:].split(",")
            nx, ny, nw, nh = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
            nw = max(360, nw)
            nh = max(200, nh)
            self._widget.setGeometry(nx, ny, nw, nh)
        elif msg == "__RESIZE_END__":
            ConfigManager.instance().set_general("window_x", self._widget.x())
            ConfigManager.instance().set_general("window_y", self._widget.y())
            ConfigManager.instance().set_window_w(self._widget.width())
            ConfigManager.instance().set_window_h(self._widget.height())
            self._sync_geo_to_js()
        elif msg == "__THEME_TOGGLE__":
            current = ConfigManager.instance().get_color_theme()
            new_theme = "light" if current == "dark" else "dark"
            ConfigManager.instance().set_color_theme(new_theme)
            self._widget._html_loaded = False
            self._widget._current_theme = None
            from .cache_manager import CacheManager
            cached = CacheManager().get_last()
            if cached:
                self._widget.display_snapshot(cached, "cached")
        elif msg == "__SETTINGS__":
            self._widget.settings_requested.emit()
        elif msg == "__OPEN_SETTINGS__":
            self._send_config_to_js()
        elif msg.startswith("__TEST_TOKEN__:"):
            self._test_token(msg[15:])
        elif msg.startswith("__CFG__:"):
            self._apply_config(msg[8:])
        elif msg == "__FOLD__":
            self._set_height(108)
        elif msg == "__UNFOLD__":
            self._widget._webview.page().runJavaScript(
                "var ft=document.querySelector('.ft');var w=document.querySelector('.wrap');if(ft&&w){var b=ft.getBoundingClientRect().bottom;var t=w.getBoundingClientRect().top;console.log('__AUTO_H__:'+Math.ceil(b-t+16))}")
        elif msg.startswith("__AUTO_H__:"):
            h = int(msg[11:])
            self._set_height(self._fit_height(h))

    def _sync_geo_to_js(self):
        sync = f"window.__widgetX={self._widget.x()};window.__widgetY={self._widget.y()};"
        sync += f"window.__widgetW={self._widget.width()};window.__widgetH={self._widget.height()};"
        self._widget._webview.page().runJavaScript(sync)

    def _send_config_to_js(self):
        import json as _json
        cfg = ConfigManager.instance()
        cfg.load()
        data = {
            "refresh_interval_seconds": cfg.get_general().get("refresh_interval_seconds", 300),
            "window_opacity": cfg.get_general().get("window_opacity", 0.85),
            "always_on_top": cfg.get_general().get("always_on_top", True),
            "color_theme": cfg.get_general().get("color_theme", "dark"),
            "user_token": cfg.get_user_token(),
        }
        js = f"setConfig({_json.dumps(data, ensure_ascii=False)});"
        self._widget._webview.page().runJavaScript(js)

    def _apply_config(self, pair: str):
        key, val = pair.split("=", 1)
        cfg = ConfigManager.instance()
        if key == "refresh_interval_seconds":
            cfg.set_general(key, int(val))
        elif key == "window_opacity":
            cfg.set_general(key, float(val))
            self._widget._webview.page().runJavaScript(
                f"document.body.style.opacity='{val}'")
        elif key == "always_on_top":
            on = val == "1"
            cfg.set_general(key, on)
            self._widget.set_always_on_top(on)
        elif key == "color_theme":
            cfg.set_color_theme(val)
            self._widget._current_theme = val
            self._widget._html_loaded = False
            self._widget._should_open_settings = True
            from .cache_manager import CacheManager
            cached = CacheManager().get_last()
            if cached:
                self._widget.display_snapshot(cached, "cached")
        elif key == "user_token":
            cfg.set_user_token(val)

    def _test_token(self, token: str):
        from .deepseek_api import test_connection
        import json as _json
        ok, msg = test_connection(token)
        js = f"setTestResult({'true' if ok else 'false'}, {_json.dumps(msg, ensure_ascii=False)});"
        self._widget._webview.page().runJavaScript(js)

# JS injected after page load for drag + 8-direction resize support
EDGE_JS = """
(function() {
var EDGE = 8, MIN_W = 360, MIN_H = 80;
var action = null;
var sx = 0, sy = 0, origX = 0, origY = 0, origW = 0, origH = 0;
window.__locked = false;

function getAction(e) {
    if (document.body.classList.contains('folded')) return null;
    var l = e.clientX < EDGE;
    var r = e.clientX > window.innerWidth - EDGE;
    if (l) return 'w'; if (r) return 'e';
    return null;
}

var cursors = {e:'ew-resize',w:'ew-resize'};

document.body.style.cursor = 'default';

document.addEventListener('mousemove', function(e) {
    if (action === 'drag') {
        var dx = e.screenX - sx, dy = e.screenY - sy;
        if (dx || dy) console.log('__DRAG__:' + dx + ',' + dy);
        sx = e.screenX; sy = e.screenY;
        return;
    }
    if (action === 'e') {
        var nw = Math.max(MIN_W, origW + e.screenX - sx);
        console.log('__RESIZE__:' + origX + ',' + origY + ',' + nw + ',' + origH);
        return;
    }
    if (action === 'w') {
        var nw2 = Math.max(MIN_W, origW - e.screenX + sx);
        var nx2 = origX + origW - nw2;
        console.log('__RESIZE__:' + nx2 + ',' + origY + ',' + nw2 + ',' + origH);
        return;
    }
    var a = getAction(e);
    document.body.style.cursor = cursors[a] || 'default';
});

document.addEventListener('mousedown', function(e) {
    if (window.__locked) return;
    var a = getAction(e);
    if (a) {
        action = a;
        sx = e.screenX; sy = e.screenY;
        origX = window.__widgetX; origY = window.__widgetY;
        origW = window.__widgetW; origH = window.__widgetH;
        e.preventDefault(); e.stopPropagation();
        return;
    }
    if (e.target.closest && e.target.closest('.model-card,button,a,input')) return;
    action = 'drag';
    sx = e.screenX; sy = e.screenY;
    e.preventDefault();
});

document.addEventListener('mouseup', function() {
    if (action === 'drag') console.log('__DRAG_END__');
    if (action && action !== 'drag') console.log('__RESIZE_END__');
    action = null;
});

// auto-resize on card expand/collapse — use element positions, not scrollHeight
function reportHeight() {
    var ft = document.querySelector('.ft');
    var wrap = document.querySelector('.wrap');
    if (!ft || !wrap) return;
    var bottom = ft.getBoundingClientRect().bottom;
    var top = wrap.getBoundingClientRect().top;
    var h = Math.ceil(bottom - top + 16);
    console.log('__AUTO_H__:' + h);
}
document.addEventListener('click', function(e) {
    var card = e.target.closest && e.target.closest('.mc[onclick]');
    if (!card) return;
    requestAnimationFrame(function() { requestAnimationFrame(reportHeight); });
});
})();
"""


class FloatingWidget(QWidget):
    refresh_requested = pyqtSignal()
    settings_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setObjectName("FloatingWidget")
        self.setWindowTitle("DeepSeek Usage")
        self.resize(WIDTH, 520)

        self._setup_window_flags()
        self._setup_ui()

        self._webview.loadFinished.connect(self._on_load_finished)
        self._html_loaded = False
        self._current_theme = None  # track theme for change detection

    # ── window flags ──────────────────────────────────────────────

    def _setup_window_flags(self):
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

    # ── ui layout ─────────────────────────────────────────────────

    def _setup_ui(self):
        self._webview = QWebEngineView(self)
        page = _DragPage(self)
        self._webview.setPage(page)
        self._webview.setStyleSheet("background:transparent;")
        page.setBackgroundColor(Qt.transparent)
        self._webview.setMinimumHeight(60)
        self._webview.setContextMenuPolicy(Qt.NoContextMenu)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._webview)

    # ── load finished ─────────────────────────────────────────────

    def _on_load_finished(self, ok):
        if ok:
            geo_js = f"window.__widgetX={self.x()};window.__widgetY={self.y()};"
            geo_js += f"window.__widgetW={self.width()};window.__widgetH={self.height()};"
            self._webview.page().runJavaScript(geo_js)
            self._webview.page().runJavaScript(EDGE_JS)
            self._webview.page().runJavaScript(
                "var ft=document.querySelector('.ft');var w=document.querySelector('.wrap');if(ft&&w){var b=ft.getBoundingClientRect().bottom;var t=w.getBoundingClientRect().top;console.log('__AUTO_H__:'+Math.ceil(b-t+16))}")
            # re-open settings page after theme change
            if getattr(self, '_should_open_settings', False):
                self._should_open_settings = False
                self._webview.page().runJavaScript("openSettings()")

    # ── public methods ─────────────────────────────────────────────

    def _get_theme(self) -> str:
        try:
            return ConfigManager.instance().get_general().get("color_theme", DEFAULT_THEME)
        except Exception:
            return DEFAULT_THEME

    def display_snapshot(self, snap: UsageSnapshot, status: str = "ok"):
        theme = self._get_theme()
        theme_changed = self._current_theme != theme
        self._current_theme = theme

        if self._html_loaded and not theme_changed:
            # in-place update via JS — no page reload, no flash
            payload = make_update_json(snap, status)
            js = f"_updateData({payload});"
            self._webview.page().runJavaScript(js)
        else:
            # first load or theme changed: full HTML, height set by JS after load
            html = render_html(snap, status, theme)
            self._webview.setHtml(html)
            self._html_loaded = True

    def display_empty(self, message: str = "请先配置 User Token"):
        self._html_loaded = False
        html = f"""<!DOCTYPE html>
<html lang="zh">
<head><meta charset="utf-8">
<style>
  body {{
    font-family: -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
    background:#0f0f1a; color:#8888aa; display:flex; align-items:center;
    justify-content:center; height:100vh; margin:0; font-size:13px;
  }}
</style></head>
<body>{message}</body></html>"""
        self._webview.setHtml(html)

    def set_opacity(self, opacity: float):
        self.setWindowOpacity(opacity)

    def set_always_on_top(self, on: bool):
        flags = self.windowFlags()
        if on:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    # ── context menu ───────────────────────────────────────────────

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.refresh_requested.emit()
