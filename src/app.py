import traceback

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

from .floating_widget import FloatingWidget
from .tray_manager import TrayManager
from .settings_dialog import SettingsDialog
from .config_manager import ConfigManager
from .cache_manager import CacheManager
from .usage_snapshot import UsageSnapshot
from .fetch_worker import FetchWorker


class App(FloatingWidget):
    def __init__(self):
        super().__init__()

        self._config = ConfigManager.instance()
        self._config.load()
        self._cache = CacheManager()
        self._fetch_worker = None
        self._settings_dialog = None

        # tray
        self._tray = TrayManager(self)
        self._tray.show_requested.connect(self.show)
        self._tray.hide_requested.connect(self.hide)
        self._tray.refresh_requested.connect(self._do_fetch)
        self._tray.settings_requested.connect(self._open_settings)
        self._tray.exit_requested.connect(self._on_exit)

        # widget signals
        self.refresh_requested.connect(self._do_fetch)
        self.settings_requested.connect(self._open_settings)

        # main refresh timer
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._on_refresh_tick)
        self._refresh_timer.start(1000)

        self._fetch_interval = self._config.get_general()["refresh_interval_seconds"]
        self._seconds_until_fetch = 2

        # restore position and size
        x = self._config.get_general().get("window_x")
        y = self._config.get_general().get("window_y")
        w = self._config.get_window_w()
        h = self._config.get_window_h()
        if x is not None and y is not None:
            self.move(x, y)
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            self.move(screen.right() - self.width() - 20, screen.top() + 80)
        if w is not None and h is not None:
            self.resize(w, h)

        # restore opacity
        self.set_opacity(self._config.get_general().get("window_opacity", 0.85))

        # load cache
        cached = self._cache.get_last()
        if cached is not None:
            self.display_snapshot(cached, "cached")
        else:
            token = self._config.get_user_token()
            if token:
                self.display_empty("等待首次刷新...")
            else:
                self.display_empty("请右键 → 设置 配置 User Token")

    # ── refresh logic ─────────────────────────────────────────────

    def _on_refresh_tick(self):
        if self._seconds_until_fetch > 0:
            self._seconds_until_fetch -= 1
            if self._seconds_until_fetch == 0:
                self._do_fetch()

    def _do_fetch(self):
        token = ConfigManager.instance().get_user_token()
        if not token:
            self.display_empty("请右键 → 设置 配置 User Token")
            self._seconds_until_fetch = self._fetch_interval
            return

        if self._fetch_worker is not None:
            try:
                self._fetch_worker.finished.disconnect()
                self._fetch_worker.error.disconnect()
            except Exception:
                pass

        self._fetch_worker = FetchWorker()
        self._fetch_worker.finished.connect(self._on_fetch_success)
        self._fetch_worker.error.connect(self._on_fetch_error)
        self._show_spinner(True)
        self._fetch_worker.fetch(token)

    def _show_spinner(self, show: bool):
        d = "inline-block" if show else "none"
        self._webview.page().runJavaScript(
            f"var s=document.getElementById('fetch-spinner');if(s)s.style.display='{d}'")

    def _on_fetch_success(self, data: dict):
        self._show_spinner(False)
        try:
            snapshot = UsageSnapshot.from_dict(data)
            self._cache.save(snapshot)
            self.display_snapshot(snapshot, "ok")
            self._tray.update_tooltip(
                f"余额: ¥{snapshot.total_balance:.2f} | "
                f"Tokens: {snapshot.total_tokens:,}"
            )
        except Exception:
            print(traceback.format_exc())
        finally:
            self._reset_countdown()

    def _on_fetch_error(self, error_msg: str):
        self._show_spinner(False)
        try:
            cached = self._cache.get_last()
            if cached is not None:
                self.display_snapshot(cached, "error")
            else:
                self.display_empty(f"错误: {error_msg}")
            self._tray.update_tooltip(f"错误: {error_msg}")
        except Exception:
            print(traceback.format_exc())
        finally:
            self._reset_countdown()

    def _reset_countdown(self):
        self._fetch_interval = self._config.get_general()["refresh_interval_seconds"]
        self._seconds_until_fetch = self._fetch_interval

    # ── settings ──────────────────────────────────────────────────

    def _open_settings(self):
        if self._settings_dialog is not None:
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            return
        dlg = SettingsDialog(self)
        self._settings_dialog = dlg
        dlg.finished.connect(self._on_settings_closed)
        dlg.show()

    def _on_settings_closed(self):
        self._settings_dialog = None
        self._config.load()
        self.set_opacity(self._config.get_general().get("window_opacity", 0.85))
        self.set_always_on_top(self._config.get_general().get("always_on_top", True))
        self._fetch_interval = self._config.get_general()["refresh_interval_seconds"]
        self._seconds_until_fetch = 1

    # ── exit ──────────────────────────────────────────────────────

    def _on_exit(self):
        self._config.set_general("window_x", self.x())
        self._config.set_general("window_y", self.y())
        self._config.save()
        QApplication.quit()

    def closeEvent(self, event):
        self._on_exit()
        super().closeEvent(event)
