from io import BytesIO
from pathlib import Path
from string import Template
import sys

import cv2
import numpy as np
from PySide6.QtCore import Qt, QProcess, QSize, QTimer
from PySide6.QtGui import QAction, QColor, QCursor, QIcon, QImage, QKeySequence, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QRadioButton, QSlider, QStyle, QStyleOptionButton, QVBoxLayout, QWidget,
)

from armath import SURFACE_SCALE, SURFACES, draw_augmentation, marker_dictionary, surface_rotation


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
QMenuBar::item { padding: 7px 12px; }
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
QWidget#cameraPanel, QWidget#transformPanel, QWidget#planePanel {
    background: $panel; border: 1px solid $line; border-radius: 10px;
}
QWidget#equationPanel { background: $background; border: 1px solid $line; border-radius: 8px; }
QLabel#cameraTitle, QLabel#panelTitle, QLabel#surfaceName { font-weight: 700; font-size: 16px; }
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
QPushButton#exitApp { background: transparent; color: $exit; border-color: $exit_border; }
QPushButton#exitApp:hover { background: $exit_hover; }
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


def photo_icon():
    image = QPixmap(36, 36)
    image.fill(Qt.GlobalColor.transparent)
    with QPainter(image) as painter:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(Qt.GlobalColor.white, 3))
        painter.drawRoundedRect(4, 10, 28, 20, 4, 4)
        painter.drawEllipse(13, 15, 10, 10)
        painter.drawLine(12, 7, 24, 7)
    image.setDevicePixelRatio(2)
    return QIcon(image)


def reset_icon():
    image = QPixmap(32, 32)
    image.fill(Qt.GlobalColor.transparent)
    with QPainter(image) as painter:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#8c9890"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawArc(5, 5, 22, 22, 135 * 16, 310 * 16)
        painter.drawLine(7, 8, 7, 15)
        painter.drawLine(7, 15, 14, 15)
    image.setDevicePixelRatio(2)
    return QIcon(image)


def panel_divider(vertical=False):
    divider = QWidget()
    divider.setObjectName("panelDivider")
    if vertical:
        divider.setFixedWidth(1)
    else:
        divider.setFixedHeight(1)
    return divider


def add_panel_title(layout, text):
    title = QLabel(text)
    title.setObjectName("panelTitle")
    layout.addWidget(title)
    layout.addWidget(panel_divider())


class ARMathWindow(QMainWindow):
    def __init__(self, camera_index):
        super().__init__()
        self.setWindowTitle("ARMath 2.0")
        self.theme = DARK_THEME
        self.setStyleSheet(THEME_STYLE.substitute(self.theme))
        self.frame = None
        self.camera_frame = None
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
        self.camera_status = QLabel("Conectando…")
        self.camera_status.setObjectName("cameraStatus")
        header_layout = QHBoxLayout(camera_header)
        header_layout.setContentsMargins(12, 6, 12, 6)
        header_layout.addWidget(camera_title)
        header_layout.addWidget(self.camera_status)
        header_layout.addStretch()
        light_mode = ToggleSwitch("Modo claro")
        light_mode.toggled.connect(self.set_light_mode)

        self.brand = QLabel("ARMath", self.menuBar())
        self.brand.setObjectName("brand")
        self.brand.setContentsMargins(10, 0, 10, 0)
        self.brand.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.menuBar().setCornerWidget(self.brand, Qt.Corner.TopRightCorner)
        self.surface_name = QLabel("Aponte a câmera para um marcador")
        self.surface_name.setObjectName("surfaceName")
        self.surface_name.setWordWrap(True)
        self.formula = QLabel()
        self.formula.setAlignment(Qt.AlignmentFlag.AlignCenter)
        equation_panel = QWidget()
        equation_panel.setObjectName("equationPanel")
        equation_panel.setMinimumHeight(78)
        equation_layout = QHBoxLayout(equation_panel)
        equation_layout.setContentsMargins(14, 6, 14, 6)
        equation_layout.addWidget(self.surface_name, 1)
        equation_layout.addWidget(panel_divider(vertical=True))
        equation_layout.addWidget(self.formula, 2)
        self.formula_images = {}

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
        self.menuBar().addAction("&Sobre", self.show_about)

        save_button = QPushButton(photo_icon(), "Salvar foto")
        save_button.setObjectName("savePhoto")
        save_button.setEnabled(False)
        self.save_action.changed.connect(lambda: save_button.setEnabled(self.save_action.isEnabled()))
        save_button.clicked.connect(self.save_action.trigger)
        axes_button = ToggleSwitch("Eixos 3D")
        axes_button.toggled.connect(self.axes_action.setChecked)
        self.axes_action.toggled.connect(axes_button.setChecked)
        restart_button = QPushButton("Reiniciar câmera")
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
        controls.addWidget(panel_divider(vertical=True))
        controls.addWidget(axes_button)
        controls.addWidget(light_mode)
        controls.addStretch()
        controls.addWidget(restart_button)
        controls.addWidget(exit_button)

        transform_panel = QWidget()
        transform_panel.setObjectName("transformPanel")
        transform_layout = QVBoxLayout(transform_panel)
        transform_layout.setContentsMargins(14, 10, 14, 10)
        transform_layout.setSpacing(10)
        add_panel_title(transform_layout, "Transformação")
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
        reset_transform.clicked.connect(self.reset_transform)
        transform_layout.addWidget(reset_transform)

        plane_panel = QWidget()
        plane_panel.setObjectName("planePanel")
        plane_layout = QVBoxLayout(plane_panel)
        plane_layout.setContentsMargins(14, 10, 14, 10)
        plane_layout.setSpacing(10)
        add_panel_title(plane_layout, "Plano de corte")
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
        plane_layout.addWidget(plane_controls)
        plane_controls.hide()
        self.plane_toggle.toggled.connect(plane_controls.setVisible)
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
        camera_column.setContentsMargins(9, 4, 9, 9)
        camera_column.setSpacing(8)
        camera_column.addWidget(camera_header)
        camera_column.addWidget(camera_slot, alignment=Qt.AlignmentFlag.AlignHCenter)
        camera_column.addWidget(equation_panel)
        columns.addWidget(camera_panel, 1, Qt.AlignmentFlag.AlignTop)
        sidebar = QWidget()
        sidebar.setFixedWidth(SIDEBAR_WIDTH)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(8)
        sidebar_layout.addStretch()
        sidebar_layout.addWidget(transform_panel)
        sidebar_layout.addWidget(plane_panel)
        sidebar_layout.addStretch()
        columns.addWidget(sidebar)
        layout.addLayout(columns)
        layout.addWidget(toolbar)
        self.setCentralWidget(root)

        QTimer.singleShot(0, self, self.start_camera)

    def set_light_mode(self, enabled):
        self.theme = LIGHT_THEME if enabled else DARK_THEME
        self.setStyleSheet(THEME_STYLE.substitute(self.theme))
        self.show_formula_image(self.active_marker)

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
        reset = QPushButton(reset_icon(), "")
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

    def set_camera_status(self, text, state):
        if self.camera_status.property("state") == state:
            return
        self.camera_status.setText(text)
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
            worker_args.insert(0, str(Path(__file__).with_name("armath.py").resolve()))
        self.camera_timeout.start(8000 if packaged else 4000)
        self.camera.start(sys.executable, worker_args)

    def camera_finished(self):
        self.camera_timeout.stop()
        if self.closing:
            return
        self.frame = None
        self.camera_frame = None
        self.save_action.setEnabled(False)
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
        self.render_frame()
        self.set_camera_status("● Ao vivo", "live")
        self.save_action.setEnabled(True)

    def render_frame(self):
        if self.camera_frame is None:
            return
        frame = self.camera_frame.copy()
        plane = None
        if self.plane_toggle.isChecked():
            axis = next(axis for axis, radio in zip((2, 1, 0), self.plane_radios) if radio.isChecked())
            plane = (axis, self.plane_slider.value() / 100)
        self.update_formula(draw_augmentation(
            frame, self.detector, self.axes_action.isChecked(),
            self.zoom_slider.value() / 100, self.rotation, plane,
        ))
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        height, width = rgb.shape[:2]
        image = QImage(rgb.data, width, height, rgb.strides[0], QImage.Format.Format_RGB888)
        self.frame = image.copy().scaled(
            self.preview_size, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview.setFixedSize(self.frame.size() + self.border_size)
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
        else:
            name = SURFACES[marker_id][0]
            self.surface_name.setText(name)
            self.show_formula_image(marker_id)

    def show_formula_image(self, marker_id):
        if marker_id is None:
            return
        key = (marker_id, self.theme["text"])
        expression = SURFACES[marker_id][1]
        if key not in self.formula_images:
            from matplotlib.figure import Figure

            figure = Figure()
            figure.text(
                0.5, 0.5, f"${expression}$", color=self.theme["text"], fontsize=22,
                math_fontfamily="stix", ha="center", va="center",
            )
            buffer = BytesIO()
            figure.savefig(
                buffer, dpi=144, format="png", transparent=True,
                bbox_inches="tight", pad_inches=0.12,
            )
            pixmap = QPixmap()
            pixmap.loadFromData(buffer.getvalue())
            pixmap.setDevicePixelRatio(2)
            formula_width = self.preview_size.width() * 2 // 3
            if pixmap.deviceIndependentSize().width() > formula_width:
                pixmap = pixmap.scaledToWidth(
                    formula_width * 2, Qt.TransformationMode.SmoothTransformation
                )
            self.formula_images[key] = pixmap
        self.formula.setPixmap(self.formula_images[key])

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
