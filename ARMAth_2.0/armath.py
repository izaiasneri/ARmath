import argparse
import ast
import operator
import sys
from functools import partial
from itertools import product
from pathlib import Path

import cv2
import numpy as np


MARKER_SIZE = 0.08
SURFACE_SCALE = 1.0
SURFACE_OPACITY = 0.94
HALF = MARKER_SIZE / 2
EXPLICIT_Z_SCALE = 0.65
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
    return np.stack((x * HALF, y * HALF, z * HALF * EXPLICIT_Z_SCALE), axis=-1)


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


CUSTOM_MARKER_ID = 9
DEFAULT_EXPRESSION = "x+y"
CUSTOM_DOMAIN_LIMIT = 5
OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
             ast.Div: np.divide, ast.Pow: np.power, ast.UAdd: operator.pos, ast.USub: operator.neg}
FUNCTIONS = {name: getattr(np, name) for name in ("sin", "cos", "tan", "exp", "sqrt", "log", "abs")}


def evaluate_expression(node, variables):
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return np.float64(node.value)
    if isinstance(node, ast.Name) and node.id in variables:
        return variables[node.id]
    if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
        return OPERATORS[type(node.op)](evaluate_expression(node.left, variables),
                                        evaluate_expression(node.right, variables))
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
        return OPERATORS[type(node.op)](evaluate_expression(node.operand, variables))
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in FUNCTIONS and len(node.args) == 1 and not node.keywords):
        return FUNCTIONS[node.func.id](evaluate_expression(node.args[0], variables))
    raise ValueError("Use x, y e as operações permitidas.")


def build_custom_geometry(expression):
    if not expression or len(expression) > 120:
        raise ValueError("Digite uma expressão de até 120 caracteres.")
    tree = ast.parse(expression.replace("^", "**"), mode="eval")

    coordinates = np.linspace(-CUSTOM_DOMAIN_LIMIT, CUSTOM_DOMAIN_LIMIT, 25)
    x, y = np.meshgrid(coordinates, coordinates)
    with np.errstate(divide="raise", invalid="raise", over="raise"):
        z = np.broadcast_to(evaluate_expression(tree.body, {"x": x, "y": y, "pi": np.pi, "e": np.e}), x.shape)
    if not np.isfinite(z).all():
        raise ValueError("A função deve ter valores reais e finitos na malha.")
    horizontal_unit = HALF / CUSTOM_DOMAIN_LIMIT
    vertical_unit = HALF * EXPLICIT_Z_SCALE / max(CUSTOM_DOMAIN_LIMIT, np.abs(z).max())
    units = np.array((horizontal_unit, horizontal_unit, vertical_unit))
    return np.stack((x, y, z), axis=-1) * units, units


def build_custom_mesh(expression):
    return build_custom_geometry(expression)[0]


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
    7: (
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


MESHES = {marker_id: build_mesh() for marker_id, (_, _, build_mesh) in SURFACES.items()}
SURFACES[CUSTOM_MARKER_ID] = (
    "Função personalizada", f"z={DEFAULT_EXPRESSION}", partial(build_custom_mesh, DEFAULT_EXPRESSION),
)
MESHES[CUSTOM_MARKER_ID], custom_units = build_custom_geometry(DEFAULT_EXPRESSION)


def set_custom_expression(expression):
    global custom_units
    mesh, units = build_custom_geometry(expression)
    SURFACES[CUSTOM_MARKER_ID] = ("Função personalizada", f"z={expression}",
                                  partial(build_custom_mesh, expression))
    MESHES[CUSTOM_MARKER_ID] = mesh
    custom_units = units


def custom_formula_latex(expression):
    def render(node, group=False):
        if isinstance(node, ast.Constant):
            mantissa, separator, exponent = str(node.value).partition("e")
            return rf"{mantissa}\times 10^{{{exponent}}}" if separator else mantissa
        if isinstance(node, ast.Name):
            return r"\pi" if node.id == "pi" else node.id
        if isinstance(node, ast.UnaryOp):
            sign = "-" if isinstance(node.op, ast.USub) else "+"
            return sign + render(node.operand, group=True)
        if isinstance(node, ast.Call):
            argument = render(node.args[0])
            name = node.func.id
            if name == "sqrt":
                return rf"\sqrt{{{argument}}}"
            if name == "abs":
                return rf"\left|{argument}\right|"
            if name == "exp":
                return rf"e^{{{argument}}}"
            return rf"\{name}\left({argument}\right)"
        if isinstance(node.op, ast.Div):
            return rf"\frac{{{render(node.left)}}}{{{render(node.right)}}}"
        if isinstance(node.op, ast.Pow):
            base = render(node.left, group=True)
            if (isinstance(node.left, (ast.UnaryOp, ast.Call))
                    or isinstance(node.left, ast.BinOp) and isinstance(node.left.op, ast.Pow)):
                base = rf"\left({base}\right)"
            return rf"{{{base}}}^{{{render(node.right)}}}"
        symbol = {ast.Add: "+", ast.Sub: "-", ast.Mult: r"\cdot "}[type(node.op)]
        result = render(node.left, group=True) + symbol + render(node.right, group=True)
        return rf"\left({result}\right)" if group else result

    tree = ast.parse(expression.replace("^", "**"), mode="eval")
    return f"f(x,y)={render(tree.body)}"


def coordinate_units(marker_id, scale):
    if marker_id == CUSTOM_MARKER_ID:
        return custom_units * scale
    builder = SURFACES[marker_id][2].func
    z_scale = EXPLICIT_Z_SCALE if builder is surface_mesh else 1.0
    return HALF * scale * np.array((1, 1, z_scale))


def format_cut_coordinate(marker_id, axis, position):
    units = coordinate_units(marker_id, 1)
    value = plane_position(MESHES[marker_id], axis, position) / units[axis]
    number = f"{value:.4g}".replace(".", ",")
    coordinate = "xyz"[axis]
    return f"{coordinate} = {number}"


def surface_rotation(angles):
    x, y, z = np.deg2rad(angles)
    rotation_x = cv2.Rodrigues(np.array([x, 0, 0]))[0]
    rotation_y = cv2.Rodrigues(np.array([0, y, 0]))[0]
    rotation_z = cv2.Rodrigues(np.array([0, 0, z]))[0]
    return rotation_z @ rotation_y @ rotation_x


def plane_section(mesh, axis, offset):
    a, b = mesh[:-1, :-1], mesh[:-1, 1:]
    c, d = mesh[1:, :-1], mesh[1:, 1:]
    triangles = np.concatenate((
        np.stack((a, b, d), axis=-2).reshape(-1, 3, 3),
        np.stack((a, d, c), axis=-2).reshape(-1, 3, 3),
    ))
    distance = triangles[:, :, axis] - offset
    distance[np.abs(distance) < 1e-9] = 0
    ends = np.roll(triangles, -1, axis=1)
    end_distance = np.roll(distance, -1, axis=1)
    crossing = (distance > 0) != (end_distance > 0)
    cuts = crossing.sum(axis=1) == 2
    selected = crossing & cuts[:, None]
    fraction = distance[selected] / (distance[selected] - end_distance[selected])
    hits = triangles[selected] + (ends[selected] - triangles[selected]) * fraction[:, None]
    segments = hits.reshape(-1, 2, 3)

    # Include mesh edges on the plane, but skip the interiors of coplanar triangles.
    on_plane = (distance == 0) & (end_distance == 0) & (distance != 0).any(axis=1)[:, None]
    edges = np.stack((triangles[on_plane], ends[on_plane]), axis=1)
    segments = np.concatenate((segments, edges))
    return segments[np.linalg.norm(segments[:, 1] - segments[:, 0], axis=1) > 1e-9]


def plane_position(mesh, axis, position):
    levels = mesh[:, :, axis]
    limit = levels.min() if position < 0 else levels.max()
    return abs(position) * limit


def cutting_plane_mesh(mesh, axis, offset):
    tangents = [coordinate for coordinate in range(3) if coordinate != axis]
    extent = max(1.2 * HALF, np.abs(mesh[:, :, tangents]).max() * 1.12)
    ticks = np.linspace(-extent, extent, 21)
    grid = np.full((ticks.size, ticks.size, 3), offset, dtype=float)
    grid[:, :, tangents[0]], grid[:, :, tangents[1]] = np.meshgrid(ticks, ticks)
    return grid


def mesh_cells(mesh, rotation, translation, camera, marker_rotation, is_plane=False):
    points = mesh.reshape(-1, 3)
    depth = ((points @ marker_rotation.T)[:, 2] + translation[2, 0]).reshape(mesh.shape[:2])
    if np.any(depth <= 0) and not is_plane:
        return None
    projected = cv2.projectPoints(points, rotation, translation, camera, None)[0]
    pixels = np.clip(projected, -32768, 32767).round().astype(np.int32).reshape(*mesh.shape[:2], 2)
    return [
        (depth[row:row + 2, col:col + 2].mean(), is_plane,
         pixels[[row, row, row + 1, row + 1], [col, col + 1, col + 1, col]],
         mesh[row:row + 2, col:col + 2, 2].mean() / HALF)
        for row in range(mesh.shape[0] - 1)
        for col in range(mesh.shape[1] - 1)
        if np.all(depth[row:row + 2, col:col + 2] > 1e-6)
    ]


def draw_white_segments(frame, segments, camera, rotation, translation, marker_rotation, thickness):
    depth = (segments @ marker_rotation.T)[:, :, 2] + translation[2, 0]
    visible = segments[(depth > 1e-6).all(axis=1)]
    if visible.size:
        image_points = cv2.projectPoints(visible.reshape(-1, 3), rotation, translation, camera, None)[0]
        pixels = np.clip(image_points, -32768, 32767).round().astype(np.int32)
        cv2.polylines(frame, pixels.reshape(-1, 2, 2), False, (255, 255, 255), thickness, cv2.LINE_AA)


def draw_labeled_axes(frame, camera, orientation, translation):
    points = np.vstack((np.zeros(3), np.eye(3) * (HALF * 1.4)))
    depth = (points @ orientation.T)[:, 2] + translation[2, 0]
    if depth[0] <= 1e-6:
        return
    rotation = cv2.Rodrigues(orientation)[0]
    projected = cv2.projectPoints(points, rotation, translation, camera, None)[0].reshape(-1, 2)
    pixels = np.clip(projected, -32768, 32767).round().astype(np.int32)
    height, width = frame.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    for index, (label, color) in enumerate(
        (("X", (0, 0, 255)), ("Y", (0, 255, 0)), ("Z", (255, 0, 0))), start=1
    ):
        if depth[index] <= 1e-6:
            continue
        x, y = pixels[index]
        cv2.line(frame, tuple(pixels[0]), (x, y), color, 2, cv2.LINE_AA)
        if 0 <= x < width and 0 <= y < height:
            (label_width, label_height), baseline = cv2.getTextSize(label, font, 0.55, 2)
            position = (min(x + 5, width - label_width - 2), max(label_height + 2, y - baseline))
            cv2.putText(frame, label, position, font, 0.55, (0, 0, 0), 4, cv2.LINE_AA)
            cv2.putText(frame, label, position, font, 0.55, (255, 255, 255), 2, cv2.LINE_AA)


def reference_ticks(values):
    low, high = values.min(), values.max()
    if low == high:
        low, high = low - 0.05, high + 0.05
    target_step = max(high - low, 0.1) / 4
    magnitude = 10 ** np.floor(np.log10(target_step))
    step = next(factor * magnitude for factor in (1, 2, 2.5, 5, 10)
                if factor * magnitude >= target_step)
    return np.arange(np.floor(low / step), np.ceil(high / step) + 1) * step


def draw_dashed_grid_line(frame, start, end):
    height, width = frame.shape[:2]
    visible, start, end = cv2.clipLine((0, 0, width, height), tuple(start), tuple(end))
    if not visible:
        return
    start = np.asarray(start, dtype=float)
    direction = np.asarray(end, dtype=float) - start
    length = np.linalg.norm(direction)
    if length < 2:
        return
    direction /= length
    for offset in range(0, int(length), 8):
        dash_start = (start + offset * direction).round().astype(int)
        dash_end = (start + min(offset + 4, length) * direction).round().astype(int)
        cv2.line(frame, tuple(dash_start), tuple(dash_end), (255, 255, 255), 1, cv2.LINE_AA)


def draw_reference_grid(frame, mesh, units, camera, orientation, translation):
    coordinates = mesh / units
    ticks = [reference_ticks(coordinates[:, :, axis]) for axis in range(3)]
    lower_corner = np.array([values[0] for values in ticks])
    upper_corner = np.array([values[-1] for values in ticks])
    segments = []
    annotations = []
    for axis in range(3):
        next_axis = (axis + 1) % 3
        other_axis = (axis + 2) % 3
        for value in ticks[axis]:
            start = lower_corner.copy()
            start[axis] = value
            for across in (next_axis, other_axis):
                end = start.copy()
                end[across] = upper_corner[across]
                segments.append((start, end))
            label_point = start.copy()
            label_point[next_axis] = upper_corner[next_axis]
            number = f"{value:.3g}".replace(".", ",")
            annotations.append((label_point, number))

    label_points, numbers = zip(*annotations)
    faces = []
    for axis in range(3):
        first, second = (coordinate for coordinate in range(3) if coordinate != axis)
        face = np.tile(lower_corner, (4, 1))
        face[[1, 2], first] = upper_corner[first]
        face[[2, 3], second] = upper_corner[second]
        faces.append(face)
    points = np.concatenate(
        (np.array(segments).reshape(-1, 3), label_points, np.array(faces).reshape(-1, 3),
         [(lower_corner + upper_corner) / 2])
    ) * units
    depth = (points @ orientation.T)[:, 2] + translation[2, 0]
    rotation = cv2.Rodrigues(orientation)[0]
    projected = cv2.projectPoints(points, rotation, translation, camera, None)[0].reshape(-1, 2)
    pixels = np.clip(projected, -32768, 32767).round().astype(np.int32)
    split = 2 * len(segments)
    face_start = split + len(numbers)
    fill = frame.copy()
    # Faces are generated normal to X (YZ), Y (XZ), then Z (XY).
    face_colors = ((65, 65, 215), (220, 135, 55), (50, 205, 245))
    for face, face_depth, color in zip(
        pixels[face_start:-1].reshape(-1, 4, 2), depth[face_start:-1].reshape(-1, 4), face_colors,
    ):
        if np.all(face_depth > 1e-6):
            cv2.fillConvexPoly(fill, face, color, cv2.LINE_AA)
    cv2.addWeighted(fill, 0.45, frame, 0.55, 0, dst=frame)
    for line, line_depth in zip(pixels[:split].reshape(-1, 2, 2), depth[:split].reshape(-1, 2)):
        if np.all(line_depth > 1e-6):
            draw_dashed_grid_line(frame, line[0], line[1])
    return [(point, number, pixels[-1]) for point, number, z in
            zip(pixels[split:face_start], numbers, depth[split:face_start])
            if z > 1e-6]


def draw_grid_numbers(frame, annotations):
    height, width = frame.shape[:2]
    font = cv2.FONT_HERSHEY_SIMPLEX
    labels = []
    for (x, y), number, (center_x, center_y) in annotations:
        if 0 <= x < width and 0 <= y < height:
            (text_width, text_height), baseline = cv2.getTextSize(number, font, 0.4, 1)
            left = x + 4 if x >= center_x else x - text_width - 4
            bottom = y + text_height + 4 if y >= center_y else y - 4
            origin = (int(np.clip(left, 2, max(2, width - text_width - 2))),
                      int(np.clip(bottom, text_height + 2, max(text_height + 2, height - baseline - 2))))
            left, bottom = origin
            right, top = left + text_width, bottom - text_height
            bottom += baseline
            if any(left <= r and right >= l and top <= b and bottom >= t for l, t, r, b in labels):
                continue
            labels.append((left, top, right, bottom))
            cv2.putText(frame, number, origin, font, 0.4, (20, 20, 20), 3, cv2.LINE_AA)
            cv2.putText(frame, number, origin, font, 0.4, (255, 255, 255), 1, cv2.LINE_AA)


def draw_surface(frame, corners, marker_id, show_axes, scale, local_rotation,
                 plane=None, show_box=False, show_grid=False):
    height, width = frame.shape[:2]
    focal = max(width, height)
    camera = np.array([[focal, 0, width / 2], [0, focal, height / 2], [0, 0, 1]], dtype=float)
    found, rotation, translation = cv2.solvePnP(
        MARKER_CORNERS, corners.reshape(4, 2), camera, None, flags=cv2.SOLVEPNP_IPPE_SQUARE
    )
    if not found or not np.isfinite(rotation).all() or not np.isfinite(translation).all():
        return False

    scaled_mesh = MESHES[marker_id] * scale
    mesh = scaled_mesh @ local_rotation.T
    marker_rotation = cv2.Rodrigues(rotation)[0]
    cells = mesh_cells(mesh, rotation, translation, camera, marker_rotation)
    if cells is None:
        return False
    if plane is not None:
        axis, position = plane
        offset = plane_position(scaled_mesh, axis, position)
        grid = cutting_plane_mesh(scaled_mesh, axis, offset) @ local_rotation.T
        cells.extend(mesh_cells(grid, rotation, translation, camera, marker_rotation, is_plane=True))
    if show_grid:
        # Explicit z=f(x,y) surfaces compress the vertical coordinate for display.
        units = coordinate_units(marker_id, scale)
        annotations = draw_reference_grid(
            frame, scaled_mesh, units, camera, marker_rotation @ local_rotation, translation,
        )
    overlay = frame.copy()
    wire_mask = np.zeros((height, width), dtype=np.uint8)
    for _, is_plane, quad, elevation in sorted(cells, key=lambda cell: cell[0], reverse=True):
        if is_plane:
            fill, wire = (28, 33, 196), (28, 235, 255)
        else:
            green = int(np.clip(39 + elevation * 20, 22, 66))
            fill, wire = (green // 2, green, 10), (95, 255, 52)
        cv2.fillConvexPoly(overlay, quad, fill, cv2.LINE_AA)
        cv2.polylines(overlay, [quad], True, wire, 1, cv2.LINE_AA)
        # Clear hidden edges before drawing the glow mask for each nearer cell.
        cv2.fillConvexPoly(wire_mask, quad, 0, cv2.LINE_AA)
        if not is_plane:
            cv2.polylines(wire_mask, [quad], True, 255, 1, cv2.LINE_AA)
    cv2.addWeighted(overlay, SURFACE_OPACITY, frame, 1 - SURFACE_OPACITY, 0, dst=frame)
    glow = cv2.GaussianBlur(wire_mask, (7, 7), 1.5)
    cv2.add(
        frame,
        cv2.merge((cv2.convertScaleAbs(glow, alpha=0.12),
                   cv2.convertScaleAbs(glow, alpha=0.34), np.zeros_like(glow))),
        dst=frame,
    )
    if plane is not None:
        section = plane_section(scaled_mesh, axis, offset) @ local_rotation.T
        draw_white_segments(frame, section, camera, rotation, translation, marker_rotation, 3)
    if show_box:
        bounds = np.array((scaled_mesh.min(axis=(0, 1)), scaled_mesh.max(axis=(0, 1))))
        vertices = np.array(list(product(*bounds.T))) @ local_rotation.T
        edges = [(index, index | bit) for index in range(8) for bit in (1, 2, 4) if not index & bit]
        draw_white_segments(frame, vertices[edges, :], camera, rotation, translation, marker_rotation, 1)
    if show_grid:
        draw_grid_numbers(frame, annotations)
    if show_axes:
        draw_labeled_axes(frame, camera, marker_rotation @ local_rotation, translation)
    return True


def draw_augmentation(frame, detector, show_axes, scale, local_rotation,
                      plane=None, show_box=False, show_grid=False):
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
        if draw_surface(frame, quad, marker_id, show_axes, scale, local_rotation, plane, show_box, show_grid):
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
