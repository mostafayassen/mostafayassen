"""Light/dark theme handling.

Follows the Windows system theme automatically via Qt's colorScheme() API
(Qt 6.5+) and re-applies whenever the user flips their OS theme while the
app is running. On platforms/Qt versions where that signal isn't available,
falls back to whatever palette Qt itself detected at startup and simply
never switches -- the app still looks fine, it just won't live-update.

The stylesheet replaces per-OS native widget chrome with a single flat,
modern look (rounded cards, consistent spacing, an accent color for primary
actions) built on top of Qt's "Fusion" style, which is the one style that
renders identically regardless of OS theme engine quirks.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

LIGHT_COLORS = {
    "bg": "#f5f6f8",
    "surface": "#ffffff",
    "surface_alt": "#eef0f4",
    "border": "#dde1e8",
    "text": "#1c1e21",
    "text_muted": "#6b7280",
    "primary": "#3763f4",
    "primary_hover": "#2c52d6",
    "primary_text": "#ffffff",
    "danger": "#e5484d",
    "nav_selected": "#e8edff",
}

DARK_COLORS = {
    "bg": "#1e2024",
    "surface": "#26282d",
    "surface_alt": "#2e3136",
    "border": "#3a3d43",
    "text": "#e7e9ec",
    "text_muted": "#9aa0a8",
    "primary": "#5b7cfa",
    "primary_hover": "#7089fb",
    "primary_text": "#ffffff",
    "danger": "#f47174",
    "nav_selected": "#31344a",
}

# {token} placeholders are substituted from LIGHT_COLORS/DARK_COLORS below.
STYLESHEET_TEMPLATE = """
QWidget {
    background: {bg};
    color: {text};
    font-family: "Segoe UI", sans-serif;
    font-size: 10pt;
}
QMainWindow, QDialog { background: {bg}; }

QListWidget#navList {
    background: {surface};
    border: none;
    border-right: 1px solid {border};
    padding: 8px 6px;
    outline: none;
}
QListWidget#navList::item {
    padding: 10px 12px;
    border-radius: 8px;
    margin: 2px 2px;
}
QListWidget#navList::item:selected {
    background: {nav_selected};
    color: {primary};
    font-weight: 600;
}
QListWidget#navList::item:hover:!selected { background: {surface_alt}; }

QGroupBox {
    background: {surface};
    border: 1px solid {border};
    border-radius: 10px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {text_muted};
}

QFrame#card {
    background: {surface};
    border: 1px solid {border};
    border-radius: 10px;
}

QListWidget, QTableWidget {
    background: {surface};
    border: 1px solid {border};
    border-radius: 8px;
    outline: none;
}
QListWidget::item, QTableWidget::item { padding: 4px 2px; }
QListWidget::item:selected, QTableWidget::item:selected {
    background: {nav_selected};
    color: {text};
}

QToolBar {
    background: {surface};
    border: none;
    border-bottom: 1px solid {border};
    padding: 6px;
    spacing: 6px;
}
QToolBar QToolButton {
    background: {surface_alt};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 6px 12px;
}
QToolBar QToolButton:hover { background: {nav_selected}; border-color: {primary}; }

QPushButton {
    background: {surface_alt};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton:hover { background: {nav_selected}; border-color: {primary}; }
QPushButton:pressed { background: {nav_selected}; }

QPushButton#primaryButton {
    background: {primary};
    color: {primary_text};
    border: none;
    font-weight: 600;
}
QPushButton#primaryButton:hover { background: {primary_hover}; }

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QDateTimeEdit, QSpinBox {
    background: {surface};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: {primary};
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QDateTimeEdit:focus {
    border: 1px solid {primary};
}
QLineEdit#quickAddInput {
    font-size: 11pt;
    padding: 10px 12px;
}

QHeaderView::section {
    background: {surface_alt};
    border: none;
    border-bottom: 1px solid {border};
    padding: 6px;
    font-weight: 600;
}

QStatusBar { background: {surface}; border-top: 1px solid {border}; }

QLabel#pageHeading { font-size: 16pt; font-weight: 700; }
QLabel#pageSubheading { color: {text_muted}; }

QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: {border};
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: {text_muted}; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def is_dark_mode() -> bool:
    """Best-effort detection of the current OS/Qt color scheme."""
    try:
        from PySide6.QtCore import Qt as _Qt

        scheme = QGuiApplication.styleHints().colorScheme()
        return scheme == _Qt.ColorScheme.Dark
    except Exception:
        return False


def build_stylesheet(dark: bool) -> str:
    colors = DARK_COLORS if dark else LIGHT_COLORS
    css = STYLESHEET_TEMPLATE
    for key, value in colors.items():
        css = css.replace("{" + key + "}", value)
    return css


class ThemeManager(QObject):
    """Applies the light/dark stylesheet and keeps it in sync with the OS."""

    theme_changed = Signal(bool)  # emits is_dark

    def __init__(self, app: QApplication):
        super().__init__()
        self._app = app
        self._dark = is_dark_mode()
        self._app.setStyle("Fusion")
        self.apply()
        try:
            QGuiApplication.styleHints().colorSchemeChanged.connect(self._on_scheme_changed)
        except Exception:
            # Older Qt/PySide6 without colorSchemeChanged: theme just won't
            # live-update if the user flips Windows' setting mid-session.
            pass

    def _on_scheme_changed(self, *_args) -> None:
        dark = is_dark_mode()
        if dark != self._dark:
            self._dark = dark
            self.apply()
            self.theme_changed.emit(dark)

    def apply(self) -> None:
        self._app.setStyleSheet(build_stylesheet(self._dark))

    @property
    def is_dark(self) -> bool:
        return self._dark
