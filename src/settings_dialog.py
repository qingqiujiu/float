from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox,
    QPushButton, QDialogButtonBox, QComboBox,
)
from PyQt5.QtCore import Qt
from .config_manager import ConfigManager
from .deepseek_api import test_connection
from .html_template import THEMES, DEFAULT_THEME


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setFixedSize(400, 380)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._config = ConfigManager.instance()
        self._config.load()

        root = QVBoxLayout(self)

        tabs = QTabWidget()

        # tab: general
        tab_general = QWidget()
        gen_layout = QVBoxLayout(tab_general)
        gen_layout.setSpacing(12)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("刷新间隔 (秒):"))
        self._refresh_spin = QSpinBox()
        self._refresh_spin.setRange(10, 3600)
        self._refresh_spin.setKeyboardTracking(False)
        self._refresh_spin.setValue(
            self._config.get_general().get("refresh_interval_seconds", 300)
        )
        row1.addWidget(self._refresh_spin)
        row1.addStretch()
        gen_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("窗口透明度:"))
        self._opacity_spin = QDoubleSpinBox()
        self._opacity_spin.setRange(0.2, 1.0)
        self._opacity_spin.setSingleStep(0.05)
        self._opacity_spin.setKeyboardTracking(False)
        self._opacity_spin.setValue(
            self._config.get_general().get("window_opacity", 0.85)
        )
        row2.addWidget(self._opacity_spin)
        row2.addStretch()
        gen_layout.addLayout(row2)

        self._ontop_check = QCheckBox("始终置顶")
        self._ontop_check.setChecked(
            self._config.get_general().get("always_on_top", True)
        )
        gen_layout.addWidget(self._ontop_check)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("配色方案:"))
        self._theme_combo = QComboBox()
        current_theme = self._config.get_general().get("color_theme", DEFAULT_THEME)
        for key, t in THEMES.items():
            self._theme_combo.addItem(t["name"], key)
            if key == current_theme:
                self._theme_combo.setCurrentIndex(self._theme_combo.count() - 1)
        row3.addWidget(self._theme_combo)
        row3.addStretch()
        gen_layout.addLayout(row3)

        gen_layout.addStretch()
        tabs.addTab(tab_general, "通用")

        # tab: token
        tab_token = QWidget()
        token_layout = QVBoxLayout(tab_token)
        token_layout.setSpacing(12)

        hint = QLabel(
            "从浏览器中获取 User Token：\n"
            "1. 打开 https://platform.deepseek.com 并登录\n"
            "2. 按 F12 → Console，运行：\n"
            "   JSON.parse(localStorage.getItem('userToken')).value\n"
            "3. 复制输出的 token"
        )
        hint.setStyleSheet("color: #888; font-size: 10px;")
        hint.setWordWrap(True)
        token_layout.addWidget(hint)

        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("User Token:"))
        self._token_input = QLineEdit()
        self._token_input.setEchoMode(QLineEdit.Password)
        self._token_input.setPlaceholderText("粘贴 userToken...")
        self._token_input.setText(self._config.get_user_token())
        key_row.addWidget(self._token_input)
        token_layout.addLayout(key_row)

        test_row = QHBoxLayout()
        self._test_btn = QPushButton("测试连接")
        self._test_btn.clicked.connect(self._on_test_connection)
        test_row.addWidget(self._test_btn)
        self._test_result = QLabel("")
        test_row.addWidget(self._test_result)
        test_row.addStretch()
        token_layout.addLayout(test_row)

        token_layout.addStretch()
        tabs.addTab(tab_token, "Token")

        root.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self._on_apply)
        root.addWidget(buttons)

    def _save_settings(self):
        self._refresh_spin.interpretText()
        self._opacity_spin.interpretText()
        self._config.set_general("refresh_interval_seconds", self._refresh_spin.value())
        self._config.set_general("window_opacity", self._opacity_spin.value())
        self._config.set_general("always_on_top", self._ontop_check.isChecked())
        self._config.set_general("color_theme", self._theme_combo.currentData())
        self._config.set_user_token(self._token_input.text().strip())

    def _on_apply(self):
        self._save_settings()

    def _on_ok(self):
        self._save_settings()
        self.accept()

    def get_refresh_interval(self) -> int:
        return self._refresh_spin.value()

    def get_opacity(self) -> float:
        return self._opacity_spin.value()

    def get_always_on_top(self) -> bool:
        return self._ontop_check.isChecked()

    def _on_test_connection(self):
        token = self._token_input.text().strip()
        if not token:
            self._test_result.setText("请先输入 User Token")
            self._test_result.setStyleSheet("color: #ddaa33;")
            return
        self._test_btn.setEnabled(False)
        self._test_result.setText("测试中...")
        self._test_result.setStyleSheet("color: #aaa;")
        ok, msg = test_connection(token)
        self._test_btn.setEnabled(True)
        if ok:
            self._test_result.setText(msg)
            self._test_result.setStyleSheet("color: #44cc66;")
        else:
            self._test_result.setText(msg)
            self._test_result.setStyleSheet("color: #ff5555;")
