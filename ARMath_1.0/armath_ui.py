from io import BytesIO
from pathlib import Path
import sys

import cv2
import numpy as np
from PySide6.QtCore import Qt, QProcess, QSize, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QImage, QKeySequence, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
    QMessageBox, QPushButton, QStyle, QStyleOptionButton, QVBoxLayout, QWidget,
)

from armath import SURFACES, draw_augmentation, marker_dictionary


CAMERA_BORDER = 3
CAMERA_RADIUS = 14
SIDE_PADDING = 16


DARK_STYLE = """
QMainWindow, QWidget#content, QDialog { background: #242629; }
QWidget { color: #f4f5f6; font-family: "Segoe UI"; font-size: 14px; }
QMenuBar, QMenu { background: #2e3135; }
QMenuBar { border-bottom: 1px solid #41454a; padding: 2px 12px; }
QMenuBar::item { padding: 7px 12px; }
QMenuBar::item:selected, QMenu::item:selected { background: #41454a; }
QMenu { border: 1px solid #45494e; padding: 4px; }
QMenu::item { padding: 7px 30px 7px 12px; }
QMenu::item:disabled, QPushButton:disabled { color: #a2a7ad; }
QLabel#brand {
    color: #38d8eb;
    font-family: "Segoe Script", "Lucida Handwriting", cursive;
    font-size: 26px;
}
QLabel#cameraFrame {
    background: #2b2e32; border: %dpx solid #38d8eb; border-radius: %dpx; padding: 0;
}
QWidget#cameraHeader, QWidget#equationPanel { background: #2e3135; border-radius: 8px; }
QLabel#cameraTitle, QLabel#surfaceName { font-weight: 700; font-size: 16px; }
QLabel#cameraStatus { color: #c4c8cd; }
QLabel#cameraStatus[state="live"] { color: #38d8eb; font-weight: 600; }
QWidget#toolbar { border-top: 1px solid #41454a; }
QPushButton {
    background: #393d42; border: 1px solid #51565c; border-radius: 7px;
    padding: 8px 14px;
}
QPushButton:hover, QCheckBox:hover { background: #45494e; }
QPushButton#savePhoto, QPushButton#exitApp { font-weight: 700; }
QPushButton#savePhoto { background: #218b45; border-color: #218b45; color: white; }
QPushButton#savePhoto:hover:enabled { background: #1c783a; }
QPushButton#savePhoto:disabled { background: #35483c; color: #b6c2b9; border-color: #46594c; }
QPushButton#exitApp { background: transparent; color: #ff696f; border-color: #ff525a; }
QPushButton#exitApp:hover { background: #493035; }
QPushButton#savePhoto:focus, QPushButton#exitApp:focus, QPushButton:focus, QCheckBox:focus {
    border: 1px solid #38d8eb;
}
QCheckBox { spacing: 8px; padding: 7px; border: 1px solid transparent; border-radius: 6px; }
QCheckBox::indicator { width: 34px; height: 18px; background: transparent; }
""" % (CAMERA_BORDER, CAMERA_RADIUS)


class AxesSwitch(QCheckBox):
    def paintEvent(self, event):
        super().paintEvent(event)
        option = QStyleOptionButton()
        self.initStyleOption(option)
        track = self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, self)
        checked = self.isChecked()
        with QPainter(self) as painter:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#38d8eb" if checked else "#686d73"))
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


class ARMathWindow(QMainWindow):
    def __init__(self, camera_index):
        super().__init__()
        self.setWindowTitle("ARMath")
        self.setStyleSheet(DARK_STYLE)
        self.frame = None
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
        available = self.screen().availableGeometry()
        horizontal_space = available.width() - 2 * (SIDE_PADDING + CAMERA_BORDER) - 20
        width = min(600, horizontal_space, (available.height() - 235) * 5 // 4)
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
        header_layout.addStretch()
        header_layout.addWidget(self.camera_status)

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
        equation_layout.addWidget(self.formula, 2)
        self.formula_images = {}

        menu = self.menuBar().addMenu("&Arquivo")
        self.save_action = QAction("Salvar foto", self)
        self.save_action.setShortcut(QKeySequence("Ctrl+S"))
        self.save_action.triggered.connect(self.save_photo)
        self.save_action.setEnabled(False)
        self.axes_action = QAction("Eixos 3D", self, checkable=True)
        self.axes_action.setShortcut(QKeySequence("Ctrl+E"))
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
        axes_button = AxesSwitch("Eixos 3D")
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
        controls.addWidget(axes_button)
        controls.addStretch()
        controls.addWidget(restart_button)
        controls.addWidget(exit_button)
        root = QWidget()
        root.setObjectName("content")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(SIDE_PADDING, 10, SIDE_PADDING, 10)
        layout.setSpacing(8)
        layout.addWidget(camera_header)
        layout.addWidget(camera_slot, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(equation_panel)
        layout.addWidget(toolbar)
        self.setCentralWidget(root)

        QTimer.singleShot(0, self, self.start_camera)

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
        self.update_formula(draw_augmentation(frame, self.detector, self.axes_action.isChecked()))
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
        self.set_camera_status("● Ao vivo", "live")
        self.save_action.setEnabled(True)

    def update_formula(self, marker_id):
        if marker_id == self.active_marker:
            return
        self.active_marker = marker_id
        if marker_id is None:
            self.surface_name.setText("Aponte a câmera para um marcador")
            self.formula.clear()
        else:
            name, expression, _ = SURFACES[marker_id]
            self.surface_name.setText(name)
            if marker_id not in self.formula_images:
                from matplotlib.figure import Figure

                figure = Figure()
                figure.text(
                    0.5, 0.5, f"${expression}$", color="white", fontsize=22,
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
                self.formula_images[marker_id] = pixmap
            self.formula.setPixmap(self.formula_images[marker_id])

    def show_about(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Sobre o ARMath")
        dialog.setFixedWidth(420)
        dialog.setStyleSheet("""
            QDialog { background: #242629; }
            QLabel { color: #eef3fb; }
            QLabel#aboutTitle { color: #67e8f9; font-size: 24px; font-weight: 700; }
            QPushButton {
                background: #22d3ee; color: #071a27; border: 1px solid #38bdf8;
                font-weight: 700; min-width: 68px;
            }
            QPushButton:hover { background: #67e8f9; }
            QPushButton:focus { border-color: #f0fbff; }
        """)

        logo_path = Path(__file__).with_name("docs") / "imagens" / "armath-logo.png"
        logo_image = QPixmap(str(logo_path))
        logo = QLabel()
        logo.setAccessibleName("Logotipo do ARMath")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setPixmap(logo_image.scaled(
            320, 110, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

        title = QLabel("ARMath 1.0")
        title.setObjectName("aboutTitle")
        description = QLabel(
            "O ARMath usa realidade aumentada para explorar superfícies matemáticas em 3D. "
            "Aponte a câmera para um marcador para ver a superfície sobre o vídeo e sua equação "
            "logo abaixo. Gire o marcador para observar o gráfico de diferentes ângulos."
        )
        description.setWordWrap(True)
        credits = QLabel(
            'Criado por Izaias Neri<br><a style="color: #67e8f9;" '
            'href="mailto:izaiasneri@gmail.com">izaiasneri@gmail.com</a>'
        )
        credits.setOpenExternalLinks(True)
        ok = QPushButton("OK")
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
    return app.exec()
