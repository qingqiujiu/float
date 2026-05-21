from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import pyqtSignal, QObject


class TrayManager(QObject):
    show_requested = pyqtSignal()
    hide_requested = pyqtSignal()
    refresh_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._visible = True
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(self._make_icon())
        self._tray.setToolTip("DeepSeek Usage Monitor")

        menu = QMenu()
        menu.setStyleSheet(
            "QMenu { background-color: #1e1e2e; color: #ccc; border: 1px solid #333; }"
            "QMenu::item:selected { background-color: #334; }"
        )

        self._show_action = QAction("隐藏", self)
        self._show_action.triggered.connect(self._toggle_visibility)
        menu.addAction(self._show_action)

        refresh_action = QAction("立即刷新", self)
        refresh_action.triggered.connect(self.refresh_requested.emit)
        menu.addAction(refresh_action)

        settings_action = QAction("设置...", self)
        settings_action.triggered.connect(self.settings_requested.emit)
        menu.addAction(settings_action)

        menu.addSeparator()

        exit_action = QAction("退出", self)
        exit_action.triggered.connect(self.exit_requested.emit)
        menu.addAction(exit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)
        self._tray.show()

    def _make_icon(self) -> QIcon:
        from PyQt5.QtGui import QPixmap, QPainter, QColor
        from PyQt5.QtCore import QSize, Qt

        pixmap = QPixmap(QSize(32, 32))
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor("#4488cc"))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(4, 4, 24, 24, 6, 6)
        painter.setBrush(QColor("#ffffff"))
        painter.drawRect(9, 14, 6, 8)
        painter.drawRect(17, 10, 6, 12)
        painter.end()

        return QIcon(pixmap)

    def _toggle_visibility(self):
        if self._visible:
            self.hide_requested.emit()
            self._show_action.setText("显示")
        else:
            self.show_requested.emit()
            self._show_action.setText("隐藏")
        self._visible = not self._visible

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._toggle_visibility()

    def update_tooltip(self, text: str):
        self._tray.setToolTip(f"DeepSeek Usage\n{text}")
