from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import logging
from pathlib import Path
from string import Template
import sys

import cv2
import numpy as np
from PySide6.QtCore import Qt, QProcess, QSize, QTimer, QUrl
from PySide6.QtGui import (
    QAction, QColor, QCursor, QDesktopServices, QIcon, QImage, QKeySequence,
    QPainter, QPainterPath, QPen, QPixmap,
)
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow,
    QMenuBar, QMessageBox, QPushButton, QRadioButton, QSlider, QStyle,
    QStyleOptionButton, QVBoxLayout, QWidget,
)

from armath import (
    CUSTOM_MARKER_ID, SURFACE_SCALE, SURFACES, custom_formula_latex, draw_augmentation, format_cut_coordinate,
    marker_dictionary, set_custom_expression, surface_rotation,
)


CAMERA_BORDER = 3
CAMERA_RADIUS = 14
SIDE_PADDING = 16
SIDEBAR_WIDTH = 332
COLUMN_SPACING = 12


THEME_STYLE = Template("""
QMainWindow, QWidget#content, QDialog { background: $background; }
QWidget { color: $text; font-family: "Segoe UI"; font-size: 14px; }
QMenuBar, QMenu { background: $panel; }
QMenuBar { border-bottom: 1px solid $line; padding: 2px 12px; }
QMenuBar::item { padding: 7px 12px 7px 33px; }
QMenuBar::item:selected, QMenu::item:selected { background: $line; }
QMenu { border: 1px solid $hover; padding: 4px; }
QMenu::item { padding: 7px 30px 7px 12px; }
QMenu::item:disabled, QPushButton:disabled { color: $muted; }
QLabel#brand {
    color: $accent_text;
    font-family: "Segoe Script", "Lucida Handwriting", cursive;
    font-size: 26px;
}
QLabel#cameraFrame {
    background: $preview; border: %dpx solid $accent; border-radius: %dpx; padding: 0;
}
QWidget#cameraPanel {
    background: $panel; border: 1px solid $line; border-radius: 10px;
}
QWidget#visualizationPanel, QWidget#transformPanel, QWidget#planePanel {
    background: $background; border: 1px solid $line; border-radius: 8px;
}
QWidget#sidebar { background: $background; }
QWidget#sidebar QPushButton { padding: 4px 9px; }
QWidget#sidebar QPushButton#resetTransform { padding: 8px 12px; }
QWidget#sidebar QPushButton#resetSlider { padding: 0; }
QWidget#sidebar QCheckBox { padding: 3px; }
QWidget#sidebar QLabel#sliderReading { padding: 1px 4px; }
QWidget#equationPanel { background: $background; border: 1px solid $line; border-radius: 8px; }
QLabel#cameraTitle, QLabel#panelTitle, QLabel#surfaceName { font-weight: 700; font-size: 16px; }
QLabel#cameraTitle, QLabel#panelTitle { color: $accent_text; }
QLabel#cutCoordinate { font-size: 16px; font-weight: 600; padding: 7px 10px; }
QLabel:disabled, QRadioButton:disabled { color: $muted; }
QSlider::handle:horizontal:disabled, QSlider::sub-page:horizontal:disabled,
QRadioButton::indicator:checked:disabled { background: $track; border-color: $track; }
QLineEdit { background: $background; border: 1px solid $line; border-radius: 5px; padding: 5px; }
QWidget#panelDivider { background: $line; }
QLabel#sliderReading {
    background: $background; border: 1px solid $button_border; border-radius: 5px;
    padding: 3px 4px;
}
QLabel#cameraStatus { color: $status; }
QLabel#cameraStatus[state="live"] { color: $accent_text; font-weight: 600; }
QWidget#toolbar { border-top: 1px solid $line; }
QPushButton {
    background: $button; border: 1px solid $button_border; border-radius: 7px;
    padding: 8px 14px;
}
QPushButton:hover, QCheckBox:hover { background: $hover; }
QPushButton#savePhoto, QPushButton#exitApp { font-weight: 700; }
QPushButton#savePhoto { background: #218b45; border-color: #218b45; color: white; }
QPushButton#savePhoto:hover:enabled { background: #1c783a; }
QPushButton#savePhoto:disabled { background: $save_disabled; color: $save_disabled_text; border-color: $save_disabled_border; }
QPushButton#freezeImage:enabled, QPushButton#plotFunction:enabled, QPushButton#resetTransform:enabled {
    color: $accent_text; border-color: $accent_text;
}
QPushButton#freezeImage:checked:enabled { background: #176b38; border-color: #176b38; color: white; }
QPushButton#restartCamera { background: #ffcc21; border-color: #ffcc21; color: #241b00; font-weight: 700; }
QPushButton#restartCamera:hover { background: #ffdb59; border-color: #ffdb59; }
QPushButton#restartCamera:focus { border-color: #7a5900; }
QPushButton#exitApp { background: #e11d31; color: white; border-color: #e11d31; }
QPushButton#exitApp:hover { background: #c91629; border-color: #c91629; }
QPushButton#savePhoto:focus, QPushButton#exitApp:focus, QPushButton:focus, QCheckBox:focus {
    border: 1px solid $accent;
}
QCheckBox { spacing: 8px; padding: 7px; border: 1px solid transparent; border-radius: 6px; }
QCheckBox::indicator { width: 34px; height: 18px; background: transparent; }
QSlider::groove:horizontal { background: $track; height: 4px; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $accent; border-radius: 2px; }
QSlider::handle:horizontal { background: $accent; width: 14px; margin: -5px 0; border-radius: 7px; }
QSlider::handle:horizontal:hover, QSlider::handle:horizontal:focus { background: $accent_hover; }
QPushButton#resetSlider { padding: 0; font-size: 19px; }
QRadioButton { spacing: 5px; padding: 3px; }
QRadioButton::indicator { width: 12px; height: 12px; border: 1px solid $track; border-radius: 7px; }
QRadioButton::indicator:checked { background: $accent; border-color: $accent; }
""" % (CAMERA_BORDER, CAMERA_RADIUS))
ABOUT_STYLE = Template("""
    QLabel#aboutTitle { color: $accent_text; font-size: 24px; font-weight: 700; }
    QPushButton#aboutOk { background: $accent; color: #142419; border-color: $accent; min-width: 68px; }
    QPushButton#aboutOk:hover { background: $accent_hover; }
    QPushButton#aboutOk:focus { border-color: $accent_text; }
""")

DARK_THEME = {
    "background": "#242629",
    "text": "#f4f5f6",
    "panel": "#2e3135",
    "line": "#41454a",
    "hover": "#45494e",
    "muted": "#a2a7ad",
    "accent": "#39ff61",
    "accent_hover": "#83ff9b",
    "preview": "#2b2e32",
    "status": "#c4c8cd",
    "button": "#393d42",
    "button_border": "#51565c",
    "save_disabled": "#35483c",
    "save_disabled_text": "#b6c2b9",
    "save_disabled_border": "#46594c",
    "exit": "#ff696f",
    "exit_border": "#ff525a",
    "exit_hover": "#493035",
    "track": "#555a61",
    "accent_text": "#55f171",
}

LIGHT_THEME = {
    "background": "#f3f5f3",
    "text": "#242a25",
    "panel": "#ffffff",
    "line": "#d2dbd3",
    "hover": "#e2eae2",
    "muted": "#626d64",
    "accent": "#21cc41",
    "accent_hover": "#66ed7d",
    "preview": "#e5ebe5",
    "status": "#465247",
    "button": "#edf2ed",
    "button_border": "#acb9ad",
    "save_disabled": "#d9e5dc",
    "save_disabled_text": "#526457",
    "save_disabled_border": "#aebbaf",
    "exit": "#ad2633",
    "exit_border": "#bf3340",
    "exit_hover": "#fbe1e4",
    "track": "#a6b3a7",
    "accent_text": "#176b29",
}


class ToggleSwitch(QCheckBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        track = self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, self)
        checked = self.isChecked()
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self.window().theme["accent"] if checked else "#686d73"))
            painter.drawRoundedRect(track, 9, 9)
            knob_size = track.height() - 6
            knob_x = track.right() - knob_size - 2 if checked else track.left() + 3
            painter.setBrush(QColor("#242629" if checked else "#f4f5f6"))
            painter.drawEllipse(knob_x, track.top() + 3, knob_size, knob_size)


def photo_icon(color="#ffffff"):
    image = QPixmap(36, 36)
    image.fill(Qt.GlobalColor.transparent)
    with QPainter(image) as painter:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(color), 3))
        painter.drawRoundedRect(4, 10, 28, 20, 4, 4)
        painter.drawEllipse(13, 15, 10, 10)
        painter.drawLine(12, 7, 24, 7)
    image.setDevicePixelRatio(2)
    return QIcon(image)


def reset_icon(color):
    image = QPixmap(32, 32)
    image.fill(Qt.GlobalColor.transparent)
    with QPainter(image) as painter:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(color), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(5, 5, 22, 22, 135 * 16, 310 * 16)
        painter.drawLine(7, 8, 7, 15)
        painter.drawLine(7, 15, 14, 15)
    image.setDevicePixelRatio(2)
    return QIcon(image)


def menu_icon(kind, color):
    image = QPixmap(32, 32)
    image.fill(Qt.GlobalColor.transparent)
    paths = {
        "file": (((8, 4), (18, 4), (24, 10), (24, 28), (8, 28), (8, 4)),
                 ((18, 4), (18, 10), (24, 10)), ((12, 16), (20, 16)), ((12, 21), (20, 21))),
        "folder": (((4, 24), (4, 9), (12, 9), (15, 12), (25, 12), (25, 15)),
                   ((4, 24), (8, 15), (29, 15), (25, 24), (4, 24))),
        "play": (((10, 6), (26, 16), (10, 26), (10, 6)),),
        "axes": (((15, 6), (15, 20), (26, 24)), ((15, 20), (5, 26))),
        "plot": (((5, 5), (5, 26), (28, 26)), ((9, 21), (15, 14), (19, 17), (27, 7))),
        "cut": (((4, 19), (13, 12), (28, 15), (19, 22), (4, 19)),
                ((16, 5), (16, 16)), ((16, 20), (16, 27))),
        "transform": (((10, 21), (6, 9), (20, 5), (24, 16)),
                      ((12, 25), (13, 29), (27, 25), (26, 22)),
                      ((23, 10), (29, 11), (29, 17))),
        "exit": (((16, 6), (5, 6), (5, 26), (16, 26)), ((12, 16), (28, 16)),
                 ((22, 10), (28, 16), (22, 22))),
    }
    with QPainter(image) as painter:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(color), 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        if kind in ("help", "info"):
            painter.drawEllipse(4, 4, 24, 24)
            font = painter.font()
            font.setPixelSize(19)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(image.rect(), Qt.AlignmentFlag.AlignCenter, "?" if kind == "help" else "i")
        elif kind == "github":
            circle = QPainterPath()
            circle.addEllipse(2, 2, 28, 28)
            cat = QPainterPath()
            cat.moveTo(12, 30)
            cat.lineTo(12, 26)
            cat.cubicTo(8, 27, 8, 23, 6, 23)
            cat.cubicTo(9, 20, 9, 26, 12, 24)
            cat.lineTo(13, 22)
            cat.cubicTo(7, 22, 6, 16, 9, 13)
            cat.cubicTo(8, 11, 9, 8, 9, 8)
            cat.cubicTo(11, 8, 13, 10, 14, 10)
            cat.cubicTo(15, 9, 17, 9, 19, 10)
            cat.cubicTo(21, 9, 22, 8, 24, 8)
            cat.cubicTo(25, 10, 24, 12, 24, 13)
            cat.cubicTo(28, 17, 24, 22, 20, 22)
            cat.cubicTo(21, 23, 21, 26, 21, 30)
            cat.closeSubpath()
            painter.fillPath(circle.subtracted(cat), QColor(color))
        elif kind == "broadcast":
            painter.drawEllipse(14, 9, 4, 4)
            painter.drawLine(16, 13, 16, 27)
            painter.drawLine(11, 27, 21, 27)
            painter.drawArc(9, 4, 14, 14, -45 * 16, 90 * 16)
            painter.drawArc(9, 4, 14, 14, 135 * 16, 90 * 16)
            painter.drawArc(4, 0, 24, 22, -45 * 16, 90 * 16)
            painter.drawArc(4, 0, 24, 22, 135 * 16, 90 * 16)
        elif kind == "webcam":
            painter.drawRoundedRect(4, 5, 24, 14, 4, 4)
            painter.drawEllipse(13, 9, 6, 6)
            painter.drawLine(16, 19, 16, 24)
            painter.drawLine(9, 24, 23, 24)
        elif kind == "eye":
            outline = QPainterPath()
            outline.moveTo(3, 16)
            outline.cubicTo(10, 6, 22, 6, 29, 16)
            outline.cubicTo(22, 26, 10, 26, 3, 16)
            painter.drawPath(outline)
            painter.drawEllipse(12, 12, 8, 8)
        else:
            for path in paths[kind]:
                for start, end in zip(path, path[1:]):
                    painter.drawLine(*start, *end)
            if kind == "transform":
                arrow = QPainterPath()
                arrow.moveTo(5, 17)
                arrow.cubicTo(-7, 32, 25, 25, 29, 11)
                painter.drawPath(arrow)
    image.setDevicePixelRatio(2)
    return QIcon(image)


class IconMenuBar(QMenuBar):
    def __init__(self, parent):
        super().__init__(parent)
        self.icons = {}
        self.setNativeMenuBar(False)

    def paintEvent(self, event):
        super().paintEvent(event)
        with QPainter(self) as painter:
            for action, icon in self.icons.items():
                rect = self.actionGeometry(action)
                icon.paint(painter, rect.left() + 11, rect.center().y() - 8, 16, 16)


def panel_divider(vertical=False):
    divider = QWidget()
    divider.setObjectName("panelDivider")
    if vertical:
        divider.setFixedWidth(1)
    else:
        divider.setFixedHeight(1)
    return divider


def render_formula_png(expression, color):
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure()
    FigureCanvasAgg(figure)
    figure.text(
        0.5, 0.5, f"${expression}$", color=color, fontsize=22,
        math_fontfamily="stix", ha="center", va="center",
    )
    buffer = BytesIO()
    figure.savefig(
        buffer, dpi=144, format="png", transparent=True,
        bbox_inches="tight", pad_inches=0.12,
    )
    return buffer.getvalue()


class ARMathWindow(QMainWindow):
    def __init__(self, camera_index):
        super().__init__()
        self.setWindowTitle("ARMath 2.0")
        self.setWindowIcon(QIcon(str(Path(__file__).with_name("docs") / "imagens" / "armath-marcador.ico")))
        self.theme = DARK_THEME
        self.setStyleSheet(THEME_STYLE.substitute(self.theme))
        self.frame = None
        self.camera_frame = None
        self.frozen_frame = None
        self.rotation = np.eye(3)
        self.active_marker = None
        self.detector = cv2.aruco.ArucoDetector(marker_dictionary())
        self.camera_index = camera_index
        self.camera_backends = (cv2.CAP_DSHOW, cv2.CAP_MSMF) if sys.platform == "win32" else (cv2.CAP_ANY,)
        self.backends = iter(self.camera_backends)
        self.camera = QProcess(self)
        self.camera.setStandardErrorFile(QProcess.nullDevice())
        self.camera.readyReadStandardOutput.connect(self.read_camera)
        self.camera.finished.connect(self.camera_finished)
        self.camera.errorOccurred.connect(self.camera_error)
        self.camera_timeout = QTimer(self, singleShot=True)
        self.camera_timeout.timeout.connect(self.camera.kill)
        self.camera_bytes = bytearray()
        self.closing = False

        self.preview = QLabel("Procurando câmera…")
        self.preview.setObjectName("cameraFrame")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.startup_screen = QApplication.screenAt(QCursor.pos()) or self.screen()
        available = self.startup_screen.availableGeometry()
        compact_sidebar = available.height() < 850
        panel_margins = (12, 6, 12, 6) if compact_sidebar else (16, 10, 16, 10)
        panel_spacing = 4 if compact_sidebar else 7
        horizontal_space = (
            available.width() - 2 * (SIDE_PADDING + CAMERA_BORDER)
            - SIDEBAR_WIDTH - COLUMN_SPACING - 38
        )
        width = max(230, min(600, horizontal_space, (available.height() - 235) * 5 // 4))
        self.preview_size = QSize(width, width * 4 // 5)
        self.border_size = QSize(2 * CAMERA_BORDER, 2 * CAMERA_BORDER)
        camera_slot = QWidget()
        camera_slot.setFixedSize(self.preview_size + self.border_size)
        camera_layout = QVBoxLayout(camera_slot)
        camera_layout.setContentsMargins(0, 0, 0, 0)
        camera_layout.addWidget(self.preview, alignment=Qt.AlignmentFlag.AlignCenter)
        self.preview.setFixedSize(camera_slot.size())
        camera_header = QWidget()
        camera_header.setObjectName("cameraHeader")
        camera_title = QLabel("Câmera")
        camera_title.setObjectName("cameraTitle")
        self.heading_icons = {}
        self.camera_status = QLabel("Conectando…")
        self.camera_status.setObjectName("cameraStatus")
        self.live_icon = QLabel()
        self.live_icon.setFixedSize(16, 16)
        self.live_icon.setPixmap(menu_icon("broadcast", self.theme["accent_text"]).pixmap(QSize(16, 16)))
        self.live_icon.hide()
        header_layout = QHBoxLayout(camera_header)
        header_layout.setContentsMargins(3, 3, 3, 3)
        self.add_heading(header_layout, camera_title, photo_icon)
        header_layout.addStretch()
        status_layout = QHBoxLayout()
        status_layout.setSpacing(5)
        status_layout.addWidget(self.live_icon)
        status_layout.addWidget(self.camera_status)
        header_layout.addLayout(status_layout)
        self.theme_toggle = ToggleSwitch("Modo claro")
        self.theme_toggle.toggled.connect(self.set_light_mode)

        self.setMenuBar(IconMenuBar(self))
        menu_corner = QWidget(self.menuBar())
        corner_layout = QHBoxLayout(menu_corner)
        corner_layout.setContentsMargins(0, 0, 0, 0)
        corner_layout.setSpacing(8)
        self.brand = QLabel("ARMath", menu_corner)
        self.brand.setObjectName("brand")
        self.brand.setContentsMargins(10, 0, 10, 0)
        self.brand.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        corner_layout.addWidget(self.theme_toggle)
        corner_layout.addWidget(self.brand)
        self.menuBar().setCornerWidget(menu_corner, Qt.Corner.TopRightCorner)
        self.surface_name = QLabel("Aponte a câmera para um marcador")
        self.surface_name.setObjectName("surfaceName")
        self.surface_name.setWordWrap(True)
        self.surface_name.setFixedWidth(min(145, self.preview_size.width() // 3))
        self.formula = QLabel()
        self.formula.setTextFormat(Qt.TextFormat.PlainText)
        self.formula.setWordWrap(True)
        self.formula.setAlignment(Qt.AlignmentFlag.AlignCenter)
        equation_panel = QWidget()
        equation_panel.setObjectName("equationPanel")
        equation_panel.setMinimumHeight(78)
        equation_layout = QHBoxLayout(equation_panel)
        equation_layout.setContentsMargins(14, 6, 14, 6)
        equation_layout.addWidget(self.surface_name)
        equation_layout.addWidget(panel_divider(vertical=True))
        equation_layout.addWidget(self.formula, 1)
        self.formula_images = {}
        self.formula_executor = ThreadPoolExecutor(max_workers=1)
        self.formula_job = None
        self.formula_timer = QTimer(self, interval=30)
        self.formula_timer.timeout.connect(self.collect_formula)
        self.marker_loss_timer = QTimer(self, interval=180, singleShot=True)
        self.marker_loss_timer.timeout.connect(lambda: self.update_formula(None))

        menu = self.menuBar().addMenu("&Arquivo")
        self.save_action = QAction("Salvar foto", self)
        self.save_action.setShortcut(QKeySequence("Ctrl+S"))
        self.save_action.triggered.connect(self.save_photo)
        self.save_action.setEnabled(False)
        self.axes_action = QAction("Eixos 3D", self, checkable=True)
        self.axes_action.setShortcut(QKeySequence("Ctrl+E"))
        self.axes_action.toggled.connect(self.render_frame)
        self.restart_action = QAction("Reiniciar câmera", self)
        self.restart_action.setVisible(False)
        self.restart_action.triggered.connect(self.restart_camera)
        exit_action = QAction("Sair", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        for action in (self.save_action, self.axes_action, self.restart_action, exit_action):
            menu.addAction(action)
        camera_action = QAction("Selecionar câmera…", self, triggered=self.select_camera)
        menu.insertAction(exit_action, camera_action)
        help_menu = self.menuBar().addMenu("&Ajuda")
        quick_start = help_menu.addAction("Como começar", self.show_quick_start)
        markers = help_menu.addAction("Abrir pasta de marcadores", self.open_markers)
        manual = help_menu.addAction("Manual do usuário", self.open_manual)
        github = help_menu.addAction("GitHub do projeto", self.open_github)
        help_menu.addSeparator()
        about = help_menu.addAction("Sobre o ARMath", self.show_about)
        self.menu_titles = {menu.menuAction(): "file", help_menu.menuAction(): "help"}
        self.menu_items = {
            self.save_action: "photo", self.axes_action: "axes", self.restart_action: "reset",
            exit_action: "exit", quick_start: "play", markers: "folder", manual: "file",
            github: "github", about: "info", camera_action: "webcam",
        }
        self.update_menu_icons()

        save_button = QPushButton(photo_icon(), "Salvar foto")
        save_button.setObjectName("savePhoto")
        save_button.setEnabled(False)
        self.save_action.changed.connect(lambda: save_button.setEnabled(self.save_action.isEnabled()))
        save_button.clicked.connect(self.save_action.trigger)
        axes_button = ToggleSwitch("Eixos")
        axes_button.toggled.connect(self.axes_action.setChecked)
        self.axes_action.toggled.connect(axes_button.setChecked)
        self.box_toggle = ToggleSwitch("Caixa")
        self.box_toggle.setToolTip("Mostrar a caixa que delimita a superfície")
        self.box_toggle.toggled.connect(self.render_frame)
        self.grid_toggle = ToggleSwitch("Grade")
        self.grid_toggle.setToolTip("Mostrar três planos de referência com escala numérica")
        self.grid_toggle.toggled.connect(self.render_frame)
        restart_button = QPushButton(reset_icon("#241b00"), "Reiniciar câmera")
        restart_button.setObjectName("restartCamera")
        restart_button.hide()
        self.restart_action.visibleChanged.connect(
            lambda: restart_button.setVisible(self.restart_action.isVisible())
        )
        restart_button.clicked.connect(self.restart_action.trigger)
        exit_button = QPushButton("Sair")
        exit_button.setObjectName("exitApp")
        exit_button.clicked.connect(self.close)

        toolbar = QWidget()
        toolbar.setObjectName("toolbar")
        controls = QHBoxLayout(toolbar)
        controls.setContentsMargins(0, 8, 0, 0)
        controls.setSpacing(12)
        controls.addWidget(save_button)
        self.freeze_button = QPushButton("Congelar imagem")
        self.freeze_button.setObjectName("freezeImage")
        self.freeze_button.setCheckable(True)
        self.freeze_button.setEnabled(False)
        self.freeze_button.clicked.connect(self.toggle_freeze)
        controls.addWidget(self.freeze_button)
        controls.addStretch()
        controls.addWidget(restart_button)
        controls.addWidget(exit_button)

        visualization_panel = QWidget()
        visualization_panel.setObjectName("visualizationPanel")
        visualization_layout = QVBoxLayout(visualization_panel)
        visualization_layout.setContentsMargins(*panel_margins)
        visualization_layout.setSpacing(panel_spacing)
        self.add_panel_title(visualization_layout, "Visualização", lambda color: menu_icon("eye", color))
        visualization_controls = QHBoxLayout()
        visualization_controls.addWidget(axes_button)
        visualization_controls.addWidget(self.box_toggle)
        visualization_controls.addWidget(self.grid_toggle)
        visualization_controls.addStretch()
        visualization_layout.addLayout(visualization_controls)

        transform_panel = QWidget()
        transform_panel.setObjectName("transformPanel")
        transform_layout = QVBoxLayout(transform_panel)
        transform_layout.setContentsMargins(*panel_margins)
        transform_layout.setSpacing(panel_spacing)
        self.add_panel_title(transform_layout, "Transformação", lambda color: menu_icon("transform", color))
        self.zoom_slider = self.add_slider(
            transform_layout, "Escala", 100, 300, round(SURFACE_SCALE * 100),
            lambda value: f"{value / 100:.2f}×".replace(".", ","),
        )
        self.rotation_sliders = [
            self.add_slider(
                transform_layout, f"Rotação {axis}",
                -180, 180, 0, lambda value: f"{value}°",
            )
            for axis in "XYZ"
        ]
        reset_transform = QPushButton("Redefinir")
        reset_transform.setObjectName("resetTransform")
        reset_transform.clicked.connect(self.reset_transform)
        transform_layout.addSpacing(6 if compact_sidebar else 10)
        transform_layout.addWidget(reset_transform)

        plane_panel = QWidget()
        plane_panel.setObjectName("planePanel")
        plane_layout = QVBoxLayout(plane_panel)
        plane_layout.setContentsMargins(*panel_margins)
        plane_layout.setSpacing(panel_spacing)
        self.add_panel_title(plane_layout, "Plano de corte", lambda color: menu_icon("cut", color))
        self.plane_toggle = ToggleSwitch()
        self.plane_toggle.setAccessibleName("Mostrar plano")
        plane_toggle_row = QHBoxLayout()
        plane_toggle_row.addWidget(QLabel("Mostrar plano"))
        plane_toggle_row.addStretch()
        plane_toggle_row.addWidget(self.plane_toggle)
        plane_layout.addLayout(plane_toggle_row)
        plane_controls = QWidget()
        plane_controls_layout = QVBoxLayout(plane_controls)
        plane_controls_layout.setContentsMargins(0, 0, 0, 0)
        plane_controls_layout.setSpacing(panel_spacing)
        plane_controls_layout.addWidget(panel_divider())
        plane_options = QHBoxLayout()
        self.plane_radios = [QRadioButton(name) for name in ("XY", "XZ", "YZ")]
        self.plane_radios[0].setChecked(True)
        for radio in self.plane_radios:
            plane_options.addWidget(radio, 1)
            radio.toggled.connect(self.plane_changed)
        plane_controls_layout.addLayout(plane_options)
        plane_controls_layout.addWidget(panel_divider())
        self.plane_slider = QSlider(Qt.Orientation.Horizontal)
        self.plane_slider.setAccessibleName("Deslocamento do plano")
        self.plane_slider.setRange(-100, 100)
        self.add_slider_row(
            plane_controls_layout, self.plane_slider, "Deslocamento",
            0, lambda value: f"{value}%",
        )
        self.plane_slider.valueChanged.connect(self.render_frame)
        self.cut_description = QLabel("Aponte para um marcador")
        self.cut_description.setObjectName("cutCoordinate")
        self.cut_description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cut_description.setTextFormat(Qt.TextFormat.PlainText)
        self.cut_description.setWordWrap(True)
        self.cut_description.setMinimumHeight(36)
        plane_controls_layout.addWidget(self.cut_description)
        plane_layout.addWidget(plane_controls)
        plane_controls.setEnabled(False)
        self.plane_toggle.toggled.connect(plane_controls.setEnabled)
        self.plane_toggle.toggled.connect(self.render_frame)
        root = QWidget()
        root.setObjectName("content")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(SIDE_PADDING, 10, SIDE_PADDING, 10)
        layout.setSpacing(8)
        columns = QHBoxLayout()
        columns.setSpacing(COLUMN_SPACING)
        camera_panel = QWidget()
        camera_panel.setObjectName("cameraPanel")
        camera_column = QVBoxLayout(camera_panel)
        camera_column.setContentsMargins(10, 10, 10, 10)
        camera_column.setSpacing(10)
        camera_column.addWidget(camera_header)
        camera_column.addWidget(camera_slot, alignment=Qt.AlignmentFlag.AlignHCenter)
        camera_column.addStretch()
        camera_column.addWidget(equation_panel)
        columns.addWidget(camera_panel, 1)
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(8 if compact_sidebar else 14)
        custom_panel = QWidget()
        custom_panel.setObjectName("planePanel")
        custom_layout = QVBoxLayout(custom_panel)
        custom_layout.setContentsMargins(*panel_margins)
        custom_layout.setSpacing(panel_spacing)
        self.add_panel_title(custom_layout, "Função personalizada", lambda color: menu_icon("axes", color))
        self.function_input = QLineEdit(SURFACES[CUSTOM_MARKER_ID][1][2:])
        self.function_input.setMaxLength(120)
        self.function_input.setPlaceholderText("Ex.: exp(x+y)")
        self.function_input.setAccessibleName("Função de x e y")
        self.function_input.setToolTip("Use x, y, pi, e, +, -, *, /, ^, sin, cos, tan, exp, sqrt, log e abs.")
        function_row = QHBoxLayout()
        function_label = QLabel("f(x,y) =")
        function_label.setBuddy(self.function_input)
        function_row.addWidget(function_label)
        function_row.addWidget(self.function_input, 1)
        self.plot_button = QPushButton(menu_icon("plot", self.theme["accent_text"]), "Plotar")
        self.plot_button.setObjectName("plotFunction")
        self.plot_button.setToolTip("Plotar a função no marcador 9")
        self.plot_button.clicked.connect(self.apply_custom_function)
        self.function_input.returnPressed.connect(self.apply_custom_function)
        function_row.addWidget(self.plot_button)
        custom_layout.addLayout(function_row)
        sidebar_layout.addWidget(custom_panel)
        sidebar_layout.addStretch()
        sidebar_layout.addWidget(visualization_panel)
        sidebar_layout.addStretch()
        sidebar_layout.addWidget(transform_panel)
        sidebar_layout.addStretch()
        sidebar_layout.addWidget(plane_panel)
        columns.addWidget(sidebar)
        layout.addLayout(columns)
        layout.addWidget(toolbar)
        self.setCentralWidget(root)

        QTimer.singleShot(0, self, self.start_camera)

    def set_light_mode(self, enabled):
        self.theme = LIGHT_THEME if enabled else DARK_THEME
        self.theme_toggle.setText("Modo escuro" if enabled else "Modo claro")
        self.live_icon.setPixmap(menu_icon("broadcast", self.theme["accent_text"]).pixmap(QSize(16, 16)))
        self.setStyleSheet(THEME_STYLE.substitute(self.theme))
        self.update_menu_icons()
        self.plot_button.setIcon(menu_icon("plot", self.theme["accent_text"]))
        for label, make_icon in self.heading_icons.items():
            label.setPixmap(make_icon(self.theme["text"]).pixmap(QSize(16, 16)))
        icon = reset_icon(self.theme["accent"])
        for button in self.findChildren(QPushButton, "resetSlider"):
            button.setIcon(icon)
        self.show_formula_image(self.active_marker)

    def add_heading(self, layout, title, make_icon):
        label = QLabel()
        label.setFixedSize(16, 16)
        label.setPixmap(make_icon(self.theme["text"]).pixmap(QSize(16, 16)))
        self.heading_icons[label] = make_icon
        layout.addWidget(label)
        layout.addWidget(title)

    def add_panel_title(self, layout, text, make_icon):
        title = QLabel(text)
        title.setObjectName("panelTitle")
        row = QHBoxLayout()
        row.setSpacing(7)
        self.add_heading(row, title, make_icon)
        row.addStretch()
        layout.addLayout(row)
        layout.addWidget(panel_divider())

    def update_menu_icons(self):
        green = self.theme["accent_text"]
        self.menuBar().icons = {action: menu_icon(kind, green) for action, kind in self.menu_titles.items()}
        for action, kind in self.menu_items.items():
            if kind == "photo":
                icon = photo_icon(green)
            elif kind == "reset":
                icon = reset_icon(green)
            else:
                icon = menu_icon(kind, self.theme["exit"] if kind == "exit" else green)
            action.setIcon(icon)
            action.setIconVisibleInMenu(True)
        self.menuBar().update()

    def add_slider(self, layout, name, minimum, maximum, initial, format_value):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setAccessibleName(name)
        slider.setRange(minimum, maximum)
        slider.setValue(initial)
        self.add_slider_row(layout, slider, name, initial, format_value)
        slider.valueChanged.connect(self.update_transform)
        return slider

    def add_slider_row(self, layout, slider, name, initial, format_value):
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel(name)
        label.setBuddy(slider)
        label.setFixedWidth(100)
        reading = QLabel(format_value(initial))
        reading.setObjectName("sliderReading")
        reading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        reading.setFixedWidth(58)
        row.addWidget(label)
        row.addWidget(slider, 1)
        row.addWidget(reading)
        row.addWidget(self.slider_reset(slider, name, initial, format_value(initial)))
        layout.addLayout(row)
        slider.valueChanged.connect(lambda value: reading.setText(format_value(value)))

    def slider_reset(self, slider, name, initial, reading):
        reset = QPushButton(reset_icon(self.theme["accent"]), "")
        reset.setObjectName("resetSlider")
        reset.setFixedSize(30, 28)
        reset.setAccessibleName(f"Redefinir {name}")
        reset.setToolTip(f"Restaurar {name} para {reading}")
        reset.clicked.connect(lambda: slider.setValue(initial))
        return reset

    def plane_changed(self, checked):
        if checked:
            self.render_frame()

    def update_transform(self):
        angles = [slider.value() for slider in self.rotation_sliders]
        self.rotation = surface_rotation(angles)
        self.render_frame()

    def reset_transform(self):
        self.zoom_slider.setValue(round(SURFACE_SCALE * 100))
        for slider in self.rotation_sliders:
            slider.setValue(0)

    def restart_camera(self):
        self.restart_action.setVisible(False)
        self.preview.setText("Procurando câmera…")
        self.backends = iter(self.camera_backends)
        self.start_camera()

    def select_camera(self):
        index, accepted = QInputDialog.getInt(
            self, "Selecionar câmera", "Índice da câmera (0 é a padrão):",
            self.camera_index, 0, max(99, self.camera_index),
        )
        if accepted and index != self.camera_index:
            self.camera_index = index
            self.restart_action.setVisible(False)
            self.backends = iter(self.camera_backends)
            if self.camera.state() == QProcess.ProcessState.NotRunning:
                self.camera_finished()
            else:
                self.camera.kill()

    def toggle_freeze(self):
        self.frozen_frame = self.camera_frame if self.frozen_frame is None else None
        self.freeze_button.setChecked(self.frozen_frame is not None)
        self.freeze_button.setText("Retomar vídeo" if self.frozen_frame is not None else "Congelar imagem")
        self.render_frame()

    def apply_custom_function(self):
        try:
            set_custom_expression(self.function_input.text().strip())
        except (ValueError, SyntaxError, FloatingPointError, OverflowError) as error:
            QMessageBox.warning(self, "Função personalizada", f"Expressão inválida.\n{error}")
            return
        self.formula_images = {
            key: image for key, image in self.formula_images.items() if key[0] != CUSTOM_MARKER_ID
        }
        if self.active_marker == CUSTOM_MARKER_ID:
            self.show_formula_image(CUSTOM_MARKER_ID)
        self.render_frame()

    def set_camera_status(self, text, state):
        if self.frozen_frame is not None:
            text, state = "Imagem congelada", "frozen"
        if self.camera_status.property("state") == state and self.camera_status.text() == text:
            return
        self.camera_status.setText(text)
        self.live_icon.setVisible(state == "live")
        self.camera_status.setProperty("state", state)
        style = self.camera_status.style()
        style.unpolish(self.camera_status)
        style.polish(self.camera_status)

    def start_camera(self):
        if self.closing:
            return
        backend = next(self.backends, None)
        if backend is None:
            self.set_camera_status("Indisponível", "offline")
            self.preview.setText(
                f"Sem imagem da câmera {self.camera_index}.\n"
                "Verifique a conexão e as permissões da câmera."
            )
            self.restart_action.setVisible(True)
            return
        self.set_camera_status("Conectando…", "connecting")
        self.camera_bytes.clear()
        worker_args = ["--camera-worker", str(self.camera_index), str(backend)]
        packaged = getattr(sys, "frozen", False)
        if not packaged:
            worker_args = [str(Path(__file__).with_name("armath_camera.py").resolve()), *worker_args[1:]]
        self.camera_timeout.start(8000)
        self.camera.start(sys.executable, worker_args)

    def camera_finished(self):
        self.camera_timeout.stop()
        if self.closing:
            return
        self.frozen_frame = None
        self.freeze_button.setChecked(False)
        self.freeze_button.setText("Congelar imagem")
        self.freeze_button.setEnabled(False)
        self.cut_description.setText("Aponte para um marcador")
        self.cut_description.setToolTip("")
        self.frame = None
        self.camera_frame = None
        self.save_action.setEnabled(False)
        self.marker_loss_timer.stop()
        self.update_formula(None)
        self.preview.setFixedSize(self.preview_size + self.border_size)
        self.preview.setText("Tentando outra conexão com a câmera…")
        self.set_camera_status("Conectando…", "connecting")
        QTimer.singleShot(0, self, self.start_camera)

    def camera_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.camera_finished()

    def read_camera(self):
        self.camera_bytes.extend(self.camera.readAllStandardOutput().data())
        jpeg = None
        while len(self.camera_bytes) >= 4:
            size = int.from_bytes(self.camera_bytes[:4], "big")
            if len(self.camera_bytes) < 4 + size:
                break
            jpeg = self.camera_bytes[4:4 + size]
            del self.camera_bytes[:4 + size]
        if jpeg and not self.closing:
            frame = cv2.imdecode(np.frombuffer(jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if frame is not None:
                self.camera_timeout.start(4000)
                self.update_frame(frame)

    def update_frame(self, frame):
        self.camera_frame = frame
        if self.frozen_frame is None:
            self.render_frame()
        self.freeze_button.setEnabled(True)
        self.save_action.setEnabled(True)

    def render_frame(self):
        if self.camera_frame is None:
            return
        source = self.frozen_frame if self.frozen_frame is not None else self.camera_frame
        frame = source.copy()
        plane = None
        if self.plane_toggle.isChecked():
            axis = next(axis for axis, radio in zip((2, 1, 0), self.plane_radios) if radio.isChecked())
            plane = (axis, self.plane_slider.value() / 100)
        marker_id = draw_augmentation(
            frame, self.detector, self.axes_action.isChecked(),
            self.zoom_slider.value() / 100, self.rotation, plane,
            show_box=self.box_toggle.isChecked(), show_grid=self.grid_toggle.isChecked(),
        )
        if marker_id is not None:
            self.marker_loss_timer.stop()
            self.update_formula(marker_id)
        elif self.active_marker is not None and not self.marker_loss_timer.isActive():
            self.marker_loss_timer.start()
        status = "Ao vivo · Marcador reconhecido" if self.active_marker is not None else "Ao vivo · Aguardando marcador"
        self.set_camera_status(status, "live")
        if marker_id is not None and plane is not None:
            self.cut_description.setText(format_cut_coordinate(marker_id, *plane))
        else:
            self.cut_description.setText("Ative o plano" if plane is None else "Aponte para um marcador")
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        image = QImage(rgb.data, width, height, rgb.strides[0], QImage.Format.Format_RGB888)
        self.frame = image.copy().scaled(
            self.preview_size, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        preview_size = self.frame.size() + self.border_size
        if self.preview.size() != preview_size:
            self.preview.setFixedSize(preview_size)
        rounded_frame = QPixmap(self.frame.size())
        rounded_frame.fill(Qt.GlobalColor.transparent)
        radius = CAMERA_RADIUS - CAMERA_BORDER
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, self.frame.width(), self.frame.height(), radius, radius)
        with QPainter(rounded_frame) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setClipPath(clip)
            painter.drawImage(0, 0, self.frame)
        self.preview.setPixmap(rounded_frame)

    def update_formula(self, marker_id):
        if marker_id == self.active_marker:
            return
        self.active_marker = marker_id
        if marker_id is None:
            self.surface_name.setText("Aponte a câmera para um marcador")
            self.formula.clear()
            self.formula.setToolTip("")
        else:
            name = SURFACES[marker_id][0]
            self.surface_name.setText(name)
            self.show_formula_image(marker_id)

    def show_formula_image(self, marker_id):
        if marker_id is None:
            return
        expression = SURFACES[marker_id][1]
        custom = marker_id == CUSTOM_MARKER_ID
        self.formula.setToolTip(expression if custom else "")
        key = (marker_id, self.theme["text"], expression)
        if key in self.formula_images:
            self.formula.setPixmap(self.formula_images[key])
            return
        self.formula.clear()
        if self.formula_job is None:
            latex = custom_formula_latex(expression[2:]) if custom else expression
            future = self.formula_executor.submit(render_formula_png, latex, key[1])
            self.formula_job = (key, future)
            self.formula_timer.start()

    def collect_formula(self):
        key, future = self.formula_job
        if not future.done():
            return
        self.formula_timer.stop()
        self.formula_job = None
        marker_id, color, expression = key
        if expression != SURFACES[marker_id][1]:
            self.show_formula_image(self.active_marker)
            return
        try:
            pixmap = QPixmap()
            if not pixmap.loadFromData(future.result()):
                raise ValueError("Invalid formula image")
            pixmap.setDevicePixelRatio(2)
            formula_width = max(60, self.preview_size.width() - self.surface_name.width() - 45)
            if pixmap.deviceIndependentSize().width() > formula_width:
                pixmap = pixmap.scaledToWidth(
                    formula_width * 2, Qt.TransformationMode.SmoothTransformation
                )
            self.formula_images[key] = pixmap
        except Exception:
            logging.exception("Could not render formula")
            if marker_id == self.active_marker and color == self.theme["text"]:
                self.formula.setText(expression)
                return
        self.show_formula_image(self.active_marker)

    def show_quick_start(self):
        QMessageBox.information(
            self, "Como começar",
            "1. Conecte a webcam e aguarde a imagem aparecer.\n\n"
            "2. Mostre um marcador ArUco inteiro à câmera, com a margem branca visível.\n\n"
            "3. Aguarde a superfície aparecer e mova o marcador devagar para explorá-la.",
        )

    def open_markers(self):
        self.open_help_resource(Path("marcadores"), "a pasta de marcadores")

    def open_manual(self):
        self.open_help_resource(Path("docs") / "Manual_ARMath.pdf", "o manual do usuário")

    def open_github(self):
        url = QUrl("https://github.com/izaiasneri/ARmath/tree/main/ARMAth_2.0")
        if not QDesktopServices.openUrl(url):
            QMessageBox.warning(self, "Ajuda", "Não foi possível abrir o GitHub do projeto.")

    def open_help_resource(self, relative_path, description):
        source_root = Path(__file__).resolve().parent
        roots = (source_root,)
        if getattr(sys, "frozen", False):
            roots = (Path(sys.executable).resolve().parent, source_root)
        path = next((root / relative_path for root in roots if (root / relative_path).exists()), None)
        if path is None or not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            QMessageBox.warning(self, "Ajuda", f"Não foi possível abrir {description}.")

    def show_about(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Sobre o ARMath")
        dialog.setFixedWidth(420)
        dialog.setStyleSheet(ABOUT_STYLE.substitute(self.theme))

        logo_path = Path(__file__).with_name("docs") / "imagens" / "armath-logo.png"
        logo_source = QImage(str(logo_path)).convertToFormat(QImage.Format.Format_RGBA8888)
        if not logo_source.isNull():
            pixels = np.frombuffer(logo_source.bits(), dtype=np.uint8).reshape(-1, 4)
            cyan = (pixels[:, 1] > 90) & (pixels[:, 2] > 90) & (pixels[:, 0] < 100)
            pixels[cyan, :3] = QColor(self.theme["accent_text"]).getRgb()[:3]
        logo_image = QPixmap.fromImage(logo_source)
        logo = QLabel()
        logo.setAccessibleName("Logotipo do ARMath")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setPixmap(logo_image.scaled(
            320, 110, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

        title = QLabel("ARMath 2.0")
        title.setObjectName("aboutTitle")
        description = QLabel(
            "O ARMath usa realidade aumentada para explorar superfícies matemáticas em 3D. "
            "Aponte a câmera para um marcador para ver a superfície sobre o vídeo e sua equação "
            "logo abaixo. Use os deslizadores para ajustar a escala e girar a figura nos eixos X, Y e Z."
        )
        description.setWordWrap(True)
        credits = QLabel(
            f'Criado por Izaias Neri<br><a style="color: {self.theme["accent_text"]};" '
            'href="mailto:izaiasneri@gmail.com">izaiasneri@gmail.com</a>'
        )
        credits.setOpenExternalLinks(True)
        ok = QPushButton("OK")
        ok.setObjectName("aboutOk")
        ok.setDefault(True)
        ok.clicked.connect(dialog.accept)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        if not logo_image.isNull():
            layout.addWidget(logo)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(credits)
        layout.addWidget(ok, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def save_photo(self):
        photo = self.frame
        if photo is None:
            return
        filename, _ = QFileDialog.getSaveFileName(self, "Salvar foto", "armath.png", "Imagem PNG (*.png)")
        if filename:
            path = Path(filename)
            if path.suffix.lower() != ".png":
                path = path.with_name(path.name + ".png")
            if not photo.save(str(path), "PNG"):
                QMessageBox.warning(self, "Salvar foto", "Não foi possível salvar a imagem.")

    def closeEvent(self, event):
        self.closing = True
        self.marker_loss_timer.stop()
        self.formula_timer.stop()
        self.formula_executor.shutdown(wait=False, cancel_futures=True)
        self.camera_timeout.stop()
        if self.camera.state() != QProcess.ProcessState.NotRunning:
            self.camera.kill()
            self.camera.waitForFinished(1000)
        super().closeEvent(event)


def run(camera_index):
    app = QApplication([])
    window = ARMathWindow(camera_index)
    window.show()
    geometry = window.frameGeometry()
    geometry.moveCenter(window.startup_screen.geometry().center())
    window.move(geometry.topLeft())
    return app.exec()
