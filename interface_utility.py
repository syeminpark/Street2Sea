# interface_utility.py
from PyQt5.QtCore import QObject, QEvent

def make_autofill_on_tab(edit):
    def _fill():
        if not edit.text().strip():
            text = edit.placeholderText().lstrip("e.g. ")  # remove prefix if present
            edit.setText(text)

    edit.editingFinished.connect(_fill)          # covers Return key
    edit.installEventFilter(FocusOutFilter(edit, _fill))

class FocusOutFilter(QObject):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self._cb = callback
    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.FocusOut:
            self._cb()
        return False          # let the event continue
    

    