"""Planar mesh panels and closed DXF / Rhino contours. All output in mm."""
import io
from collections import defaultdict
import numpy as np
import trimesh
import ezdxf
from ezdxf import path as dxf_path
import pyclipper
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon, LineString
from shapely.geometry.polygon import orient
from shapely.ops import unary_union, polygonize_full
from shapely.affinity import rotate, translate
from .models import Piece, Settings

MAX_FACES = 40_000
MAX_PIECES = 250
CLIP_SCALE = 100_000


class GeometryError(ValueError):
    pass


def checked(poly):
    if poly.is_empty or not poly.is_valid or poly.area < 1e-6:
        raise GeometryError('Se encontró un contorno vacío, degenerado o autointersectado. Corrige la geometría antes de cortar.')
    if not np.isfinite(poly.bounds).all() or max(abs(v) for v in poly.bounds) > 1e7:
        raise GeometryError('Coordenadas fuera de rango. Revisa las unidades y el origen del archivo.')
    return orient(poly, sign=1)


def nested_rings(rings):
    """Even/odd fill rule; preserve nested islands and holes independently of winding."""
    polygons = []
    seen = set()
    for ring in rings:
        p = checked(Polygon(ring))
        key = p.normalize().wkb
        if key not in seen:
            polygons.append(p)
            seen.add(key)
    if len(polygons) > 2000:
        raise GeometryError('Demasiados contornos: el límite de esta versión es 2000.')
    parents = []
    for i, p in enumerate(polygons):
        candidates = []
        for j, q in enumerate(polygons):
            if i == j:
                continue
            if p.boundary.intersects(q.boundary):
                raise GeometryError('Hay contornos que se cruzan o se tocan. Separa o une los polígonos en el archivo CAD.')
            if q.area > p.area and q.contains(p):
                candidates.append(j)
        parents.append(min(candidates, key=lambda j: polygons[j].area) if candidates else None)
    def depth(i):
        n = 0
        while parents[i] is not None:
            i = parents[i]
            n += 1
        return n
    return [checked(Polygon(p.exterior.coords, [q.exterior.coords for j, q in enumerate(polygons) if parents[j] == i]))
            for i, p in enumerate(polygons) if depth(i) % 2 == 0]


def mesh_panels(mesh, warnings):
    if not len(mesh.faces) or len(mesh.faces) > MAX_FACES:
        raise GeometryError(f'La malla debe tener entre 1 y {MAX_FACES:,} triángulos. Simplifica el modelo.')
    if not np.isfinite(mesh.vertices).all():
        raise GeometryError('La malla contiene coordenadas no finitas.')
    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.update_faces(mesh.unique_faces())
    mesh.remove_unreferenced_vertices()
    if not len(mesh.faces):
        raise GeometryError('La malla no contiene caras válidas.')
    if not mesh.is_watertight:
        warnings.append('Malla abierta o no manifold: se procesaron sus caras planas, pero no constituye un sólido cerrado.')
    if not mesh.is_winding_consistent:
        warnings.append('Hay normales inconsistentes. Comprueba la orientación de las caras en el modelo original.')
    edge_counts = np.bincount(mesh.edges_unique_inverse)
    if np.any(edge_counts > 2):
        raise GeometryError('Malla no manifold: existen aristas compartidas por más de dos caras. Repara el modelo.')
    parent = list(range(len(mesh.faces)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    normals = mesh.face_normals
    tolerance = max(float(np.max(mesh.extents)) * 1e-8, 1e-6)
    for a, b in mesh.face_adjacency:
        # Opposite windings on the same plane are allowed but reported above.
        if abs(float(np.dot(normals[a], normals[b]))) > 1 - 1e-10:
            delta = mesh.triangles[b] - mesh.triangles[a, 0]
            if np.max(np.abs(delta @ normals[a])) < tolerance:
                parent[find(int(b))] = find(int(a))
    groups = defaultdict(list)
    for i in range(len(mesh.faces)):
        groups[find(i)].append(i)
    if len(groups) > MAX_PIECES:
        raise GeometryError(f'El modelo produce {len(groups)} paneles; máximo {MAX_PIECES}. Las superficies curvas se facetan: simplifica o prepara paneles planos.')
    if sum(len(g) == 1 for g in groups.values()) > 8:
        warnings.append('Se detectaron numerosas caras triangulares aisladas: las superficies curvas se exportan como facetas, sin aplanado continuo.')
    output = []
    for faces in groups.values():
        triangle = mesh.triangles[faces[0]]
        normal = normals[faces[0]]
        u = triangle[1] - triangle[0]
        u /= np.linalg.norm(u)
        v = np.cross(normal, u)
        points = mesh.triangles[faces] - triangle[0]
        projected = np.stack((points @ u, points @ v), axis=-1)
        merged = unary_union([Polygon(t) for t in projected])
        candidates = [merged] if merged.geom_type == 'Polygon' else list(merged.geoms)
        output.extend(checked(p) for p in candidates if p.geom_type == 'Polygon')
    return output


def read_dxf(data, settings, warnings):
    # DXF files may use a legacy codepage; ezdxf detects it from the header.
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'input.dxf'
        path.write_bytes(data)
        doc = ezdxf.readfile(path)
    header_unit = doc.header.get('$INSUNITS', 0)
    names = {1: 'in', 4: 'mm', 5: 'cm', 6: 'm'}
    if header_unit in names and names[header_unit] != settings.units:
        warnings.append(f'DXF declara {names[header_unit]}; se aplicó tu selección explícita: {settings.units}.')
    paths = []
    ignored = set()
    total_points = 0
    for entity in doc.modelspace():
        if entity.dxf.layer.upper() == 'GRABADO':
            ignored.add('GRABADO original')
            continue
        try:
            p = dxf_path.make_path(entity)
        except (TypeError, ValueError, NotImplementedError):
            ignored.add(entity.dxftype())
            continue
        coords = np.array([tuple(v) for v in p.flattening(distance=0.03/settings.unit_factor)])
        if len(coords) < 2:
            continue
        total_points += len(coords)
        if total_points > 100_000:
            raise GeometryError('DXF demasiado complejo: reduce la cantidad de vértices o curvas.')
        if np.ptp(coords[:, 2]) * settings.unit_factor > 0.01:
            raise GeometryError('Los contornos DXF deben estar en un plano paralelo a XY. Proyecta el dibujo antes de importarlo.')
        xy = coords[:, :2] * settings.unit_factor
        if np.linalg.norm(xy[0]-xy[-1]) < 1e-6:
            checked(Polygon(xy))
        paths.append(LineString(xy))
    if ignored:
        warnings.append('Entidades omitidas en DXF: ' + ', '.join(sorted(ignored)) + '. El grabado exportado contiene identificadores nuevos.')
    if not paths:
        raise GeometryError('El DXF no contiene contornos de corte compatibles.')
    polys, cuts, dangles, invalid = polygonize_full(unary_union(paths))
    if not cuts.is_empty or not dangles.is_empty or not invalid.is_empty:
        raise GeometryError('Hay líneas abiertas o contornos inválidos en el DXF. Cierra los perfiles de corte; coloca anotaciones abiertas en GRABADO.')
    return nested_rings([p.exterior.coords for p in polys.geoms])


def read_3dm(data, settings, warnings):
    import rhino3dm as rh
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'input.3dm'
        path.write_bytes(data)
        doc = rh.File3dm.Read(str(path))
    if doc is None:
        raise GeometryError('El archivo 3DM no es válido.')
    meshes, rings = [], []
    skipped = set()
    def add_mesh(geo):
        vertices = np.array([[v.X, v.Y, v.Z] for v in geo.Vertices], dtype=float)
        faces = []
        for a, b, c, d in geo.Faces:
            faces.append([a, b, c])
            if c != d:
                faces.append([a, c, d])
        if faces:
            meshes.append(trimesh.Trimesh(vertices * settings.unit_factor, faces, process=False))
    for obj in doc.Objects:
        geo = obj.Geometry
        if isinstance(geo, rh.Mesh):
            add_mesh(geo)
        elif isinstance(geo, rh.PolylineCurve) and geo.IsClosed:
            points = np.array([[p.X, p.Y, p.Z] for p in geo.TryGetPolyline()]) * settings.unit_factor
            if np.ptp(points[:, 2]) > 0.01:
                raise GeometryError('Las polilíneas 3DM deben estar en un plano paralelo a XY.')
            rings.append(points[:, :2])
        elif isinstance(geo, rh.Brep):
            cached = [face.GetMesh(rh.MeshType.Render) for face in geo.Faces]
            if cached and all(m is not None for m in cached):
                for mesh in cached:
                    add_mesh(mesh)
            else:
                skipped.add('Brep sin malla renderizada')
        else:
            skipped.add(type(geo).__name__)
    if skipped:
        warnings.append('Objetos 3DM omitidos: ' + ', '.join(sorted(skipped)) + '. Convierte NURBS, extrusiones y bloques a Mesh en Rhino y guarda nuevamente.')
    warnings.append('3DM: las coordenadas se interpretan según la unidad elegida en el formulario.')
    if not meshes and not rings:
        raise GeometryError('3DM sin mallas ni polilíneas cerradas compatibles. En Rhino: Mesh → exportar Selected como .3dm o .stl. Los Brep necesitan mallas de render guardadas.')
    return meshes, nested_rings(rings)


def compensate(poly, kerf):
    if kerf == 0:
        return poly
    poly = orient(poly, sign=1)
    paths = [list(poly.exterior.coords)[:-1]] + [list(r.coords)[:-1] for r in poly.interiors]
    offset = pyclipper.PyclipperOffset(miter_limit=2)
    offset.AddPaths([pyclipper.scale_to_clipper(p, CLIP_SCALE) for p in paths], pyclipper.JT_MITER, pyclipper.ET_CLOSEDPOLYGON)
    solution = offset.Execute(kerf / 2 * CLIP_SCALE)
    if not solution:
        raise GeometryError('El kerf elimina una pieza. Reduce la compensación.')
    polygons = nested_rings([pyclipper.scale_from_clipper(p, CLIP_SCALE) for p in solution])
    if len(polygons) != 1 or len(polygons[0].interiors) != len(poly.interiors):
        raise GeometryError('El kerf cierra un agujero o altera la topología de una pieza. Reduce el kerf o agranda el detalle.')
    return polygons[0]


def load_geometry(data, extension, settings):
    warnings, polygons, meshes = [], [], []
    if extension == 'dxf':
        polygons = read_dxf(data, settings, warnings)
    elif extension == '3dm':
        meshes, polygons = read_3dm(data, settings, warnings)
    else:
        scene = trimesh.load_scene(io.BytesIO(data), file_type=extension, process=False, skip_materials=True)
        # to_mesh applies each instance transform; no external material resources required.
        mesh = scene.to_mesh()
        if not isinstance(mesh, trimesh.Trimesh):
            raise GeometryError('El archivo no contiene una malla triangular.')
        mesh.apply_scale(settings.unit_factor)
        meshes = [mesh]
    vector_polygons = list(polygons)
    if sum(len(m.faces) for m in meshes) > MAX_FACES:
        raise GeometryError(f'El conjunto supera el límite de {MAX_FACES:,} triángulos.')
    vertex_parts, face_parts, cursor = [], [], 0
    for mesh in meshes:
        polygons.extend(mesh_panels(mesh, warnings))
        vertex_parts.append(mesh.vertices)
        face_parts.append(mesh.faces + cursor)
        cursor += len(mesh.vertices)
    if not polygons or len(polygons) > MAX_PIECES:
        raise GeometryError(f'Se admiten entre 1 y {MAX_PIECES} piezas planas por trabajo.')
    # Build a 3D preview of vector-only files too, respecting holes.
    for poly in vector_polygons:
        for tri in constrained_delaunay_triangles(poly).geoms:
            xy = np.asarray(tri.exterior.coords)[:3]
            vertex_parts.append(np.column_stack((xy, np.zeros(3))))
            face_parts.append(np.array([[cursor, cursor+1, cursor+2]]))
            cursor += 3
    vertices = np.concatenate(vertex_parts) if vertex_parts else np.zeros((0, 3))
    faces = np.concatenate(face_parts) if face_parts else np.zeros((0, 3), dtype=int)
    if len(faces) > MAX_FACES:
        raise GeometryError(f'El conjunto supera el límite de {MAX_FACES:,} triángulos.')
    pieces = []
    for i, polygon in enumerate(polygons):
        polygon = checked(polygon)
        # Align the smallest enclosing rectangle before considering 0/90° nesting.
        # This removes arbitrary triangle-edge orientations introduced by projection.
        rect = np.asarray(polygon.minimum_rotated_rectangle.exterior.coords)
        edge = rect[1] - rect[0]
        angle = np.degrees(np.arctan2(edge[1], edge[0]))
        polygon = rotate(polygon, -angle, origin=(0, 0))
        x, y, _, _ = polygon.bounds
        polygon = translate(polygon, xoff=-x, yoff=-y)
        compensated = compensate(polygon, settings.kerf)
        x, y, _, _ = compensated.bounds
        pieces.append(Piece(f'P{i+1:03}', translate(compensated, -x, -y), polygon.area))
    warnings.append('Paneles independientes: el espesor se registra como material; no se generan encastres ni ajustes de unión automáticamente.')
    preview = {'vertices': np.round(vertices, 5).ravel().tolist(), 'faces': faces.astype(int).ravel().tolist(),
               'bounds': np.round(np.ptp(vertices, axis=0), 3).tolist() if len(vertices) else [0, 0, 0]}
    return pieces, preview, list(dict.fromkeys(warnings))
