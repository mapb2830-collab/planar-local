"""Deterministic MaxRects with 0/90 degree rotations and bounding-box spacing.

Conservative: holes are not reused and irregular shapes do not interlock.
"""
from shapely.affinity import rotate, translate
from shapely.geometry import box
from .models import Placement
from .geometry import GeometryError

EPS = 1e-7


def normalize(poly):
    x, y, _, _ = poly.bounds
    return translate(poly, -x, -y)


def split_free(free, used):
    ux, uy, uw, uh = used
    result = []
    for x, y, w, h in free:
        if ux >= x+w-EPS or ux+uw <= x+EPS or uy >= y+h-EPS or uy+uh <= y+EPS:
            result.append((x, y, w, h))
            continue
        if ux > x+EPS:
            result.append((x, y, ux-x, h))
        if ux+uw < x+w-EPS:
            result.append((ux+uw, y, x+w-ux-uw, h))
        if uy > y+EPS:
            result.append((x, y, w, uy-y))
        if uy+uh < y+h-EPS:
            result.append((x, uy+uh, w, y+h-uy-uh))
    result = list(dict.fromkeys(result))
    return [r for i, r in enumerate(result) if not any(
        i != j and r[0] >= q[0]-EPS and r[1] >= q[1]-EPS
        and r[0]+r[2] <= q[0]+q[2]+EPS and r[1]+r[3] <= q[1]+q[3]+EPS
        for j, q in enumerate(result))]


def nest(pieces, settings):
    available_w = settings.width - 2*settings.margin
    available_h = settings.height - 2*settings.margin
    sheets, free_lists = [], []
    ordered = sorted(pieces, key=lambda p: (-max(p.polygon.bounds[2:]), -p.polygon.area, p.id))
    for piece in ordered:
        options = [(0, normalize(piece.polygon))]
        if settings.rotate:
            options.append((90, normalize(rotate(piece.polygon, 90, origin=(0, 0)))))
        fits_empty = any(p.bounds[2] <= available_w+EPS and p.bounds[3] <= available_h+EPS for _, p in options)
        if not fits_empty:
            w, h = piece.polygon.bounds[2:]
            raise GeometryError(f'{piece.id} ({w:.1f} × {h:.1f} mm) no cabe en la lámina con los márgenes actuales. Amplía la lámina o revisa las unidades.')
        best = None
        # Evaluate an empty new sheet only if all existing sheets cannot fit.
        for sheet_idx in range(len(sheets)+1):
            if sheet_idx == len(sheets):
                if best is not None:
                    break
                sheets.append([])
                free_lists.append([(settings.margin, settings.margin, available_w+settings.gap, available_h+settings.gap)])
            for x, y, fw, fh in free_lists[sheet_idx]:
                for angle, poly in options:
                    w, h = poly.bounds[2]+settings.gap, poly.bounds[3]+settings.gap
                    if w <= fw+EPS and h <= fh+EPS:
                        score = (min(fw-w, fh-h), max(fw-w, fh-h), sheet_idx, y, x, angle)
                        if best is None or score < best[0]:
                            best = (score, sheet_idx, x, y, w, h, angle, poly)
        _, idx, x, y, w, h, angle, poly = best
        placed = translate(poly, x, y)
        sheets[idx].append(Placement(piece, placed, angle))
        free_lists[idx] = split_free(free_lists[idx], (x, y, w, h))
    # Verify geometry independently of MaxRects before allowing fabrication output.
    inside = box(settings.margin, settings.margin, settings.width-settings.margin, settings.height-settings.margin)
    for sheet in sheets:
        for i, placement in enumerate(sheet):
            if not inside.buffer(EPS).covers(placement.polygon):
                raise GeometryError('Una pieza excede los límites de la lámina.')
            for other in sheet[:i]:
                if placement.polygon.distance(other.polygon) < settings.gap-EPS:
                    raise GeometryError('No se pudo mantener la separación entre piezas.')
    return sheets
