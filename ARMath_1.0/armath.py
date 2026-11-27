import argparse
import sys
from functools import partial
from pathlib import Path

import cv2
import numpy as np


MARKER_SIZE = 0.08
SURFACE_SCALE = 1.30
SURFACE_OPACITY = 0.94
HALF = MARKER_SIZE / 2
MARKER_CORNERS = np.array(
    [[-HALF, HALF, 0], [HALF, HALF, 0], [HALF, -HALF, 0], [-HALF, -HALF, 0]],
    dtype=np.float64,
)


def marker_dictionary():
    return cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)


def generate_markers(directory):
    directory.mkdir(parents=True, exist_ok=True)
    dictionary = marker_dictionary()
    for marker_id, (name, _, _) in SURFACES.items():
        marker = cv2.aruco.generateImageMarker(dictionary, marker_id, 600)
        marker = cv2.copyMakeBorder(marker, 100, 100, 100, 100, cv2.BORDER_CONSTANT, value=255)
        path = directory / f"marcador_{marker_id}.png"
        path.write_bytes(cv2.imencode(".png", marker)[1].tobytes())
        print(f"{path} — {name}")


def surface_mesh(function):
    coordinates = np.linspace(-1, 1, 17)
    x, y = np.meshgrid(coordinates, coordinates)
    z = function(x, y)
    return np.stack((x * HALF, y * HALF, z * HALF * 0.65), axis=-1)


def angular_mesh(function, start, stop):
    angle = np.linspace(0, 2 * np.pi, 29)
    parameter = np.linspace(start, stop, 19)
    u, v = np.meshgrid(angle, parameter)
    return np.stack(function(u, v), axis=-1) * HALF


def ellipsoid(u, v):
    return 0.9 * np.cos(u) * np.sin(v), 0.7 * np.sin(u) * np.sin(v), 0.5 * np.cos(v)


def torus(u, v):
    radius = 0.65 + 0.25 * np.cos(v)
    return radius * np.cos(u), radius * np.sin(u), 0.25 * np.sin(v)


def hyperboloid(u, z):
    radius = np.hypot(0.45, z)
    return radius * np.cos(u), radius * np.sin(u), z


def double_cone(u, z):
    radius = np.abs(z)
    return radius * np.cos(u), radius * np.sin(u), z


SURFACES = {
    0: ("Paraboloide elíptico", r"z=2x^2+2y^2", partial(surface_mesh, lambda x, y: 2*x**2 + 2*y**2)),
    1: ("Paraboloide hiperbólico (sela)", r"z=2x^2-2y^2", partial(surface_mesh, lambda x, y: 2*x**2 - 2*y**2)),
    2: ("Ondas senoidais", r"z=\sin(2x)\cos(2y)", partial(surface_mesh, lambda x, y: np.sin(2*x) * np.cos(2*y))),
    3: (
        "Elipsoide",
        r"\frac{x^2}{0{,}9^2}+\frac{y^2}{0{,}7^2}+\frac{z^2}{0{,}5^2}=1",
        partial(angular_mesh, ellipsoid, 0, np.pi),
    ),
    4: (
        "Toro",
        r"(\sqrt{x^2+y^2}-0{,}65)^2+z^2=0{,}25^2",
        partial(angular_mesh, torus, 0, 2 * np.pi),
    ),
    5: (
        "Hiperboloide de uma folha",
        r"x^2+y^2-z^2=0{,}45^2",
        partial(angular_mesh, hyperboloid, -0.75, 0.75),
    ),
    6: (
        "Cone duplo",
        r"x^2+y^2=z^2",
        partial(angular_mesh, double_cone, -0.85, 0.85),
    ),
    9: (
        "Superfície gaussiana",
        r"z=e^{-3(x^2+y^2)}",
        partial(surface_mesh, lambda x, y: np.exp(-3 * (x**2 + y**2))),
    ),
    8: (
        "Ondulações concêntricas",
        r"z=\cos(6\sqrt{x^2+y^2})",
        partial(surface_mesh, lambda x, y: np.cos(6 * np.hypot(x, y))),
    ),
}


MESHES = {marker_id: build_mesh() * SURFACE_SCALE for marker_id, (_, _, build_mesh) in SURFACES.items()}


def draw_surface(frame, corners, marker_id, show_axes):
    height, width = frame.shape[:2]
    focal = max(width, height)
    camera = np.array([[focal, 0, width / 2], [0, focal, height / 2], [0, 0, 1]], dtype=float)
    found, rotation, translation = cv2.solvePnP(
        MARKER_CORNERS, corners.reshape(4, 2), camera, None, flags=cv2.SOLVEPNP_IPPE_SQUARE
    )
    if not found or not np.isfinite(rotation).all() or not np.isfinite(translation).all():
        return False

    mesh = MESHES[marker_id]
    points = mesh.reshape(-1, 3)
    depths = (points @ cv2.Rodrigues(rotation)[0].T)[:, 2] + translation[2, 0]
    if np.any(depths <= 0):
        return False
    projected = cv2.projectPoints(points, rotation, translation, camera, None)[0]
    pixels = np.clip(projected, -32768, 32767).round().astype(np.int32).reshape(*mesh.shape[:2], 2)
    depth = depths.reshape(mesh.shape[:2])
    cells = [
        (depth[row:row + 2, col:col + 2].mean(), row, col)
        for row in range(mesh.shape[0] - 1)
        for col in range(mesh.shape[1] - 1)
    ]
    overlay = frame.copy()
    wire_mask = np.zeros((height, width), dtype=np.uint8)
    for _, row, col in sorted(cells, reverse=True):
        quad = pixels[[row, row, row + 1, row + 1], [col, col + 1, col + 1, col]]
        elevation = mesh[row:row + 2, col:col + 2, 2].mean() / HALF
        teal = int(np.clip(39 + elevation * 20, 22, 66))
        cv2.fillConvexPoly(overlay, quad, (teal + 14, teal, 10), cv2.LINE_AA)
        cv2.polylines(overlay, [quad], True, (235, 216, 56), 1, cv2.LINE_AA)
        # Clear hidden edges before drawing the glow mask for each nearer cell.
        cv2.fillConvexPoly(wire_mask, quad, 0, cv2.LINE_AA)
        cv2.polylines(wire_mask, [quad], True, 255, 1, cv2.LINE_AA)
    cv2.addWeighted(overlay, SURFACE_OPACITY, frame, 1 - SURFACE_OPACITY, 0, dst=frame)
    glow = cv2.GaussianBlur(wire_mask, (7, 7), 1.5)
    cv2.add(
        frame,
        cv2.merge((cv2.convertScaleAbs(glow, alpha=0.34),
                   cv2.convertScaleAbs(glow, alpha=0.29), np.zeros_like(glow))),
        dst=frame,
    )
    if show_axes:
        cv2.drawFrameAxes(frame, camera, None, rotation, translation, HALF * 1.4, 2)
    return True


def draw_augmentation(frame, detector, show_axes):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    corners, ids, _ = detector.detectMarkers(gray)
    if ids is None:
        return None
    matches = [
        (cv2.contourArea(quad.reshape(4, 2)), marker_id, quad)
        for marker_id, quad in zip(ids.ravel(), corners)
        if marker_id in SURFACES
    ]
    # The formula panel follows the most prominent supported marker.
    for _, marker_id, quad in sorted(matches, key=lambda match: match[0], reverse=True):
        if draw_surface(frame, quad, marker_id, show_axes):
            return marker_id
    return None


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "--camera-worker":
        from armath_camera import stream

        return stream(int(sys.argv[2]), int(sys.argv[3]))

    parser = argparse.ArgumentParser(description="ARMath — realidade aumentada para matemática")
    parser.add_argument("--gerar-marcadores", type=Path, metavar="PASTA")
    parser.add_argument("--camera", type=int, default=0, metavar="ÍNDICE")
    args = parser.parse_args()
    if args.gerar_marcadores is not None:
        generate_markers(args.gerar_marcadores)
        return 0

    from armath_ui import run

    return run(args.camera)


if __name__ == "__main__":
    sys.exit(main())
