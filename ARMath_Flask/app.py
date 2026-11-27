from functools import lru_cache
from io import BytesIO
from math import isfinite
from pathlib import Path
from threading import Lock

import click
import cv2
import numpy as np
from flask import Flask, abort, jsonify, render_template, request, send_file
from matplotlib.mathtext import math_to_image
from PIL import Image

import engine

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 900_000
FORMULA_LOCK = Lock()
GITHUB = "https://github.com/izaiasneri/ARmath/tree/main/ARMAth_2.0"


@lru_cache(maxsize=32)
def custom_geometry(expression):
    return engine.build_custom_geometry(expression)


@lru_cache(maxsize=64)
def formula_image(latex, theme):
    image = BytesIO()
    with FORMULA_LOCK:
        math_to_image(f"${latex}$", image, dpi=165, format="png", color="black")
    # MathText uses an opaque white background by default.
    pixels = cv2.imdecode(np.frombuffer(image.getvalue(), np.uint8), cv2.IMREAD_GRAYSCALE)
    result = np.empty((*pixels.shape, 4), dtype=np.uint8)
    result[:, :, :3] = (66, 38, 21) if theme == "light" else (255, 246, 241)
    result[:, :, 3] = 255 - pixels
    return cv2.imencode(".png", result)[1].tobytes()


def validated_expression(expression):
    try:
        if not isinstance(expression, str):
            raise ValueError("Digite uma expressão.")
        expression = expression.strip()
        geometry = custom_geometry(expression)
    except (ValueError, SyntaxError, FloatingPointError, OverflowError, RecursionError) as error:
        if isinstance(error, ValueError) and not isinstance(error, SyntaxError):
            raise ValueError(str(error)) from error
        raise ValueError("Use uma expressão válida e finita no domínio da malha.") from error
    return expression, geometry


def number(key, default, low, high):
    value = float(request.form.get(key, default))
    if not isfinite(value) or not low <= value <= high:
        raise ValueError(f"Valor fora do intervalo para {key}.")
    return value


def enabled(key):
    return request.form.get(key) == "true"


@app.cli.command("gerar-marcadores")
@click.argument("directory", type=click.Path(path_type=Path))
def generate_markers(directory):
    """Gera os dez marcadores ArUco em DIRECTORY."""
    engine.generate_markers(directory)


@app.get("/")
def home():
    return render_template(
        "index.html", github=GITHUB, expression=engine.DEFAULT_EXPRESSION,
        surfaces=engine.SURFACES,
    )


@app.post("/api/function")
def validate_function():
    body = request.get_json(silent=True)
    try:
        expression, _ = validated_expression(body.get("expression") if isinstance(body, dict) else None)
    except ValueError as error:
        return jsonify(error=str(error)), 400
    return jsonify(expression=expression)


@app.get("/api/formula/<int:marker_id>.png")
def formula(marker_id):
    if marker_id not in engine.SURFACES:
        abort(404)
    latex = engine.SURFACES[marker_id][1]
    theme = "light" if request.args.get("theme") == "light" else "dark"
    if marker_id == engine.CUSTOM_MARKER_ID:
        try:
            expression, _ = validated_expression(request.args.get("expression", engine.DEFAULT_EXPRESSION))
            latex = engine.custom_formula_latex(expression)
        except ValueError:
            abort(400)
    return send_file(BytesIO(formula_image(latex, theme)), mimetype="image/png")


@app.post("/api/frame")
def augment_frame():
    upload = request.files.get("frame")
    if not upload:
        return jsonify(error="Envie um quadro JPEG da câmera."), 400
    try:
        with Image.open(upload.stream, formats=["JPEG"]) as image:
            if max(image.size) > 800:
                raise ValueError("Quadro maior que 800 pixels.")
        upload.stream.seek(0)
        frame = cv2.imdecode(np.frombuffer(upload.read(), np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Quadro JPEG inválido.")
        _, custom = validated_expression(request.form.get("expression", engine.DEFAULT_EXPRESSION))
        scale = number("scale", 1, 1, 3)
        angles = tuple(number(axis, 0, -180, 180) for axis in "xyz")
        plane_name = request.form.get("plane")
        plane = None
        if plane_name:
            axis = {"yz": 0, "xz": 1, "xy": 2}.get(plane_name)
            if axis is None:
                raise ValueError("Plano inválido.")
            plane = (axis, number("offset", 0, -1, 1))
        detector = cv2.aruco.ArucoDetector(engine.marker_dictionary())
        marker_id = engine.draw_augmentation(
            frame, detector, enabled("axes"), scale, engine.surface_rotation(angles), plane,
            show_box=enabled("box"), show_grid=enabled("grid"), custom=custom,
        )
    except (OSError, Image.DecompressionBombError):
        return jsonify(error="Quadro JPEG inválido."), 400
    except (ValueError, cv2.error) as error:
        return jsonify(error=str(error)), 400

    image = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])[1]
    response = send_file(BytesIO(image.tobytes()), mimetype="image/jpeg", max_age=0)
    if marker_id is not None:
        response.headers["X-Marker-Id"] = str(marker_id)
        if plane is not None:
            response.headers["X-Cut-Coordinate"] = engine.format_cut_coordinate(marker_id, *plane, custom)
    return response


if __name__ == "__main__":
    app.run()
