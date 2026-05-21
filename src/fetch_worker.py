import threading
import traceback
from PyQt5.QtCore import QObject, pyqtSignal
from .deepseek_api import fetch_snapshot, DeepSeekAPIError


class FetchWorker(QObject):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def fetch(self, user_token: str):
        def _run():
            try:
                snap = fetch_snapshot(user_token)
                self.finished.emit(snap.to_dict())
            except DeepSeekAPIError as e:
                self.error.emit(str(e))
            except Exception:
                self.error.emit(f"获取数据时出错:\n{traceback.format_exc()}")

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
