import sys
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from src.app import App

if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("DeepSeek Usage Monitor")
    app.setQuitOnLastWindowClosed(False)

    window = App()
    window.show()

    sys.exit(app.exec_())
