# PLANAR — Código completo

Los archivos siguientes también están separados en el proyecto. Los locks y archivos de ejemplo están incluidos en el ZIP.

## .gitignore

```text
.venv/
node_modules/
dist/
__pycache__/
.pytest_cache/
*.pyc
.env
*.tsbuildinfo

```

## INICIAR_WINDOWS.cmd

```batch
@echo off
setlocal
cd /d "%~dp0"
echo.
echo PLANAR - Instalacion y arranque local
echo Carpeta: %CD%
echo.
where node >nul 2>&1
if errorlevel 1 (
  echo Falta Node.js. Instala Node.js 24 LTS desde https://nodejs.org
  echo Despues cierra esta ventana y abre este archivo otra vez.
  pause
  exit /b 1
)
node -e "const [a,b]=process.versions.node.split('.').map(Number); if(a<22 || (a===22 && b<12)) process.exit(1)"
if errorlevel 1 (
  echo Se necesita Node.js 22.12 o superior. Se recomienda Node.js 24.
  pause
  exit /b 1
)
py -3.12 --version >nul 2>&1
if errorlevel 1 (
  echo Falta Python 3.12 con el lanzador py.
  echo Instala Python 3.12 desde https://www.python.org/downloads/windows/
  echo Incluye el Python Launcher durante la instalacion.
  pause
  exit /b 1
)
if not exist "backend\.venv\Scripts\python.exe" (
  py -3.12 -m venv "backend\.venv"
  if errorlevel 1 goto failed
)
echo [1/3] Instalando dependencias de Python...
"backend\.venv\Scripts\python.exe" -m pip install -r "backend\requirements.txt"
if errorlevel 1 goto failed
echo [2/3] Instalando dependencias de la interfaz...
pushd frontend
call npm ci
if errorlevel 1 (
  popd
  goto failed
)
popd
echo [3/3] Abriendo los servidores...
start "PLANAR - Backend" cmd /k call "%~dp0scripts\backend.cmd"
start "PLANAR - Frontend" cmd /k call "%~dp0scripts\frontend.cmd"
powershell -NoProfile -Command "$ErrorActionPreference='Stop'; Write-Host 'Esperando ambos servidores...'; for ($attempt=0; $attempt -lt 60; $attempt++) { try { $api=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8000/api/health' -TimeoutSec 2; $web=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:5173' -TimeoutSec 2; $health=$api.Content | ConvertFrom-Json; if ($health.status -eq 'ok' -and $web.StatusCode -eq 200 -and $web.Content -match 'PLANAR') { Start-Process 'http://127.0.0.1:5173'; exit 0 } } catch {}; Start-Sleep -Seconds 1 }; Write-Host 'Revisa los errores en las ventanas Backend y Frontend.'; exit 1"
if errorlevel 1 goto failed
echo.
echo PLANAR iniciado. Conserva abiertas las ventanas Backend y Frontend.
echo Para cerrar la aplicacion, pulsa Ctrl+C en cada una.
pause
exit /b 0
:failed
echo.
echo No se pudo completar el arranque. Copia el error que aparece arriba.
pause
exit /b 1

```

## backend/app/__init__.py

```python

```

## backend/app/exporters.py

```python
import io
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED
import ezdxf
from shapely.geometry import box
from ezdxf.enums import TextEntityAlignment
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm


def rings(poly):
    return [list(poly.exterior.coords)] + [list(r.coords) for r in poly.interiors]


def label_size(placement):
    x0, y0, x1, y1 = placement.polygon.bounds
    size = min(3, (x1-x0)/7, (y1-y0)/3)
    point = placement.polygon.representative_point()
    while size > 0.001:
        label_box = box(point.x-1.5*size, point.y-.7*size, point.x+1.5*size, point.y+.7*size)
        if placement.polygon.covers(label_box):
            break
        size *= .8
    return size


def export_dxf(job, sheet):
    doc = ezdxf.new('R2010')
    doc.units = ezdxf.units.MM
    doc.header['$MEASUREMENT'] = 1
    doc.layers.new('CORTE', dxfattribs={'color': 1, 'lineweight': 0})
    doc.layers.new('GRABADO', dxfattribs={'color': 5})
    model = doc.modelspace()
    for p in sheet:
        for ring in rings(p.polygon):
            model.add_lwpolyline(ring[:-1], close=True, dxfattribs={'layer': 'CORTE'})
        point = p.polygon.representative_point()
        text = model.add_text(p.piece.id, dxfattribs={'layer': 'GRABADO', 'height': label_size(p)})
        text.set_placement((point.x, point.y), align=TextEntityAlignment.MIDDLE_CENTER)
    stream = io.StringIO()
    doc.write(stream)
    return stream.getvalue().encode('utf-8')


def export_svg(job, sheet):
    w, h = job.settings.width, job.settings.height
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}mm" height="{h}mm" viewBox="0 0 {w} {h}">',
             '<title>PLANAR — trayectorias compensadas, milímetros</title>',
             '<g id="CORTE" fill="none" stroke="#ff0000" stroke-width="0.01">']
    for p in sheet:
        for ring in rings(p.polygon):
            path = 'M ' + ' L '.join(f'{x:.6f},{h-y:.6f}' for x, y in ring[:-1]) + ' Z'
            lines.append(f'<path d="{path}"/>')
    lines.append('</g><g id="GRABADO" fill="#0000ff" font-family="sans-serif" text-anchor="middle" dominant-baseline="central">')
    for p in sheet:
        point = p.polygon.representative_point()
        lines.append(f'<text x="{point.x:.6f}" y="{h-point.y:.6f}" font-size="{label_size(p):.6f}">{escape(p.piece.id)}</text>')
    lines.append('</g></svg>')
    return '\n'.join(lines).encode()


def export_pdf(job):
    stream = io.BytesIO()
    w, h = job.settings.width*mm, job.settings.height*mm
    pdf = canvas.Canvas(stream, pagesize=(w, h), pageCompression=1)
    pdf.setTitle(f'PLANAR — {job.filename} — escala 1:1')
    pdf.setSubject(f'Milímetros; kerf {job.settings.kerf}; espesor {job.settings.thickness}. Imprimir a tamaño real sin ajustar.')
    for sheet in job.sheets:
        pdf.setStrokeColorRGB(1, 0, 0)
        pdf.setLineWidth(0.01*mm)
        for p in sheet:
            for ring in rings(p.polygon):
                path = pdf.beginPath()
                path.moveTo(ring[0][0]*mm, ring[0][1]*mm)
                for x, y in ring[1:-1]:
                    path.lineTo(x*mm, y*mm)
                path.close()
                pdf.drawPath(path, stroke=1, fill=0)
        pdf.setFillColorRGB(0, 0, 1)
        for p in sheet:
            point = p.polygon.representative_point()
            size = label_size(p)*mm
            pdf.setFont('Helvetica', size)
            pdf.drawCentredString(point.x*mm, point.y*mm-size*0.35, p.piece.id)
        pdf.showPage()
    pdf.save()
    return stream.getvalue()


def export_job(job, format):
    if format == 'pdf':
        return export_pdf(job), 'application/pdf', 'planar-laminas.pdf'
    render = export_dxf if format == 'dxf' else export_svg
    if len(job.sheets) == 1:
        mime = 'application/dxf' if format == 'dxf' else 'image/svg+xml'
        return render(job, job.sheets[0]), mime, f'planar-lamina-01.{format}'
    stream = io.BytesIO()
    with ZipFile(stream, 'w', ZIP_DEFLATED) as archive:
        for i, sheet in enumerate(job.sheets, 1):
            archive.writestr(f'planar-lamina-{i:02}.{format}', render(job, sheet))
    return stream.getvalue(), 'application/zip', f'planar-{format}-laminas.zip'

```

## backend/app/geometry.py

```python
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

```

## backend/app/models.py

```python
from dataclasses import dataclass, field
from typing import Literal
import math
from pydantic import BaseModel, Field, model_validator
from shapely.geometry import Polygon


class Settings(BaseModel):
    width: float = Field(default=600, ge=20, le=3000)
    height: float = Field(default=400, ge=20, le=3000)
    thickness: float = Field(default=3, ge=0.1, le=50)
    kerf: float = Field(default=0.15, ge=0, le=3)
    gap: float = Field(default=3, ge=0.1, le=50)
    margin: float = Field(default=5, ge=0, le=100)
    units: Literal['mm', 'cm', 'm', 'in'] = 'mm'
    rotate: bool = True

    @model_validator(mode='after')
    def validate_sheet(self):
        if not all(math.isfinite(v) for v in [self.width, self.height, self.thickness, self.kerf, self.gap, self.margin]):
            raise ValueError('Los parámetros deben ser números finitos.')
        if self.margin * 2 >= min(self.width, self.height):
            raise ValueError('El margen consume toda la lámina.')
        return self

    @property
    def unit_factor(self):
        return {'mm': 1, 'cm': 10, 'm': 1000, 'in': 25.4}[self.units]


@dataclass
class Piece:
    id: str
    polygon: Polygon
    nominal_area: float


@dataclass
class Placement:
    piece: Piece
    polygon: Polygon
    angle: int


@dataclass
class Job:
    id: str
    filename: str
    settings: Settings
    sheets: list[list[Placement]]
    preview: dict
    warnings: list[str] = field(default_factory=list)

```

## backend/app/nesting.py

```python
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

```

## backend/main.py

```python
"""Local API. Run: python -m uvicorn main:app --reload --host 127.0.0.1."""
import logging
import time
from collections import OrderedDict
from pathlib import Path
from threading import Lock, BoundedSemaphore
from typing import Annotated, Literal
from uuid import uuid4
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from app.models import Job, Settings
from app.geometry import load_geometry, GeometryError
from app.nesting import nest
from app.exporters import export_job, rings

app = FastAPI(title='PLANAR Studio — API local', version='0.1.0')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
                   allow_methods=['GET', 'POST'], allow_headers=['Content-Type'], expose_headers=['Content-Disposition'])
MAX_BYTES = 20 * 1024 * 1024
jobs: OrderedDict[str, tuple[float, Job]] = OrderedDict()
lock = Lock()
processing_slot = BoundedSemaphore(1)
log = logging.getLogger('planar')


def clean_jobs():
    now = time.monotonic()
    for key, (created, _) in list(jobs.items()):
        if now-created > 3600:
            del jobs[key]
    while len(jobs) > 20:
        jobs.popitem(last=False)


def serialize(job):
    sheets = []
    nominal_area = 0
    for i, sheet in enumerate(job.sheets):
        parts = []
        area = 0
        for p in sheet:
            point = p.polygon.representative_point()
            area += p.piece.nominal_area
            parts.append({'id': p.piece.id, 'rings': rings(p.polygon), 'angle': p.angle,
                          'area': round(p.piece.nominal_area, 3), 'label': [point.x, point.y]})
        nominal_area += area
        sheets.append({'index': i, 'pieces': parts, 'utilization': round(100*area/(job.settings.width*job.settings.height), 2)})
    utilization = 100*nominal_area/(len(sheets)*job.settings.width*job.settings.height)
    return {'id': job.id, 'filename': job.filename, 'settings': job.settings.model_dump(),
            'sheets': sheets, 'preview': job.preview, 'warnings': job.warnings,
            'piece_count': sum(len(s) for s in job.sheets), 'utilization': round(utilization, 2),
            'area_mm2': round(nominal_area, 3), 'expires_in_seconds': 3600}


def process(data, filename, settings):
    extension = Path(filename).suffix.lower().lstrip('.')
    try:
        pieces, preview, warnings = load_geometry(data, extension, settings)
        sheets = nest(pieces, settings)
    except GeometryError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        log.exception('Failed parsing model')
        raise HTTPException(422, 'No se pudo interpretar el archivo. Comprueba que su contenido coincida con la extensión y que contenga geometría válida.') from exc
    job = Job(uuid4().hex, filename, settings, sheets, preview, warnings)
    with lock:
        jobs[job.id] = (time.monotonic(), job)
        clean_jobs()
    return serialize(job)


@app.get('/api/health')
def health():
    return {'status': 'ok', 'version': '0.1.0', 'mode': 'local'}


@app.post('/api/process')
async def process_file(file: Annotated[UploadFile, File()], settings: Annotated[str, Form()] = '{}'):
    filename = Path((file.filename or 'model').replace('\\', '/')).name
    if Path(filename).suffix.lower() not in {'.stl', '.obj', '.dxf', '.3dm', '.ply', '.off'}:
        await file.close()
        raise HTTPException(415, 'Formato no compatible. Usa STL, OBJ, DXF, 3DM, PLY u OFF.')
    try:
        options = Settings.model_validate_json(settings)
    except (ValidationError, ValueError) as exc:
        await file.close()
        raise HTTPException(422, 'Parámetros inválidos: revisa dimensiones, margen, grosor, kerf y unidades.') from exc
    data = bytearray()
    try:
        while chunk := await file.read(1024*1024):
            data.extend(chunk)
            if len(data) > MAX_BYTES:
                raise HTTPException(413, 'El archivo supera el límite de 20 MB.')
    finally:
        await file.close()
    if not data:
        raise HTTPException(422, 'El archivo está vacío.')
    if not processing_slot.acquire(blocking=False):
        raise HTTPException(429, 'Ya hay un modelo en proceso. Espera unos segundos e intenta de nuevo.')
    try:
        return await run_in_threadpool(process, bytes(data), filename, options)
    finally:
        processing_slot.release()


@app.get('/api/jobs/{job_id}/export/{format}')
def export(job_id: str, format: Literal['dxf', 'svg', 'pdf']):
    with lock:
        clean_jobs()
        record = jobs.get(job_id)
    if record is None:
        raise HTTPException(404, 'El trabajo expiró o el servidor se reinició. Procesa el archivo otra vez.')
    content, mime, filename = export_job(record[1], format)
    return Response(content, media_type=mime,
                    headers={'Content-Disposition': f'attachment; filename="{filename}"', 'Cache-Control': 'no-store'})

```

## backend/make_examples.py

```python
"""Rebuild small, inspectable source files for all six input formats."""
from pathlib import Path
import numpy as np
import trimesh
import ezdxf
import rhino3dm as rh

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'examples'
OUT.mkdir(exist_ok=True)
# Five separate planar panels, intentionally slightly spaced at joints.
quads = [
    [(0,0,0),(180,0,0),(180,140,0),(0,140,0)],
    [(0,0,101),(180,0,101),(180,140,101),(0,140,101)],
    [(1,139,1),(179,139,1),(179,139,100),(1,139,100)],
    [(1,1,1),(1,138,1),(1,138,100),(1,1,100)],
    [(179,1,1),(179,138,1),(179,138,100),(179,1,100)],
]
vertices = np.array(quads).reshape(-1,3)
faces = np.array([[4*i,4*i+1,4*i+2] for i in range(len(quads))] + [[4*i,4*i+2,4*i+3] for i in range(len(quads))])
mesh = trimesh.Trimesh(vertices,faces,process=False)
for ext in ('obj','stl','ply','off'):
    mesh.export(OUT/f'pabellon.{ext}')
(ROOT/'frontend/public/demo-pabellon.obj').write_bytes((OUT/'pabellon.obj').read_bytes())
doc=ezdxf.new('R2010');doc.units=4
model=doc.modelspace()
model.add_lwpolyline([(0,0),(180,0),(180,100),(0,100)],close=True)
model.add_lwpolyline([(20,20),(60,20),(60,80),(20,80)],close=True)
model.add_lwpolyline([(100,20),(160,20),(160,80),(100,80)],close=True)
model.add_lwpolyline([(200,0),(340,0),(340,100),(200,100)],close=True)
model.add_circle((270,50),radius=25)
doc.saveas(OUT/'fachadas-con-huecos.dxf')
rhino=rh.File3dm();rhino.Settings.ModelUnitSystem=rh.UnitSystem.Millimeters
for quad in quads:
    panel=rh.Mesh()
    for x,y,z in quad:panel.Vertices.Add(x,y,z)
    panel.Faces.AddFace(0,1,2,3)
    rhino.Objects.AddMesh(panel)
rhino.Write(str(OUT/'pabellon.3dm'),8)
print('Examples generated in',OUT)

```

## backend/requirements-dev.txt

```text
-r requirements.txt
pytest>=8,<10
httpx>=0.28,<1
pypdf>=5,<7

```

## backend/requirements.txt

```text
fastapi==0.162.2
uvicorn>=0.34,<1
python-multipart>=0.0.20,<1
trimesh==5.2.0
ezdxf==1.4.5
shapely==2.2.0
pyclipper==1.4.0
numpy>=2.2,<3
rhino3dm>=8.17,<9
reportlab>=4.4,<5

```

## backend/tests/test_pipeline.py

```python
import io
import json
from pathlib import Path
from zipfile import ZipFile
import numpy as np
import pytest
import trimesh
import ezdxf
import rhino3dm as rh
from fastapi.testclient import TestClient
from shapely.geometry import Polygon, box
from pypdf import PdfReader
from main import app
from app.geometry import compensate, GeometryError, load_geometry
from app.models import Settings, Piece
from app.nesting import nest

client = TestClient(app)


def submit(data, name, **settings):
    return client.post('/api/process', files={'file': (name, data)}, data={'settings': json.dumps(settings)})


def dxf_bytes(doc):
    stream = io.StringIO(); doc.write(stream)
    return stream.getvalue().encode()


@pytest.mark.parametrize('ext', ['stl','obj','ply','off'])
def test_mesh_formats_and_coplanar_faces(ext):
    mesh = trimesh.creation.box([120,80,60])
    r = submit(mesh.export(file_type=ext), f'cube.{ext}')
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['piece_count'] == 6  # Merge the 12 triangles into six panels.
    assert sorted(data['preview']['bounds']) == [60,80,120]
    assert data['area_mm2'] == pytest.approx(43200)
    assert data['utilization'] == pytest.approx(18)


def test_dxf_holes_and_kerf():
    doc = ezdxf.new(); m = doc.modelspace()
    m.add_lwpolyline([(0,0),(100,0),(100,100),(0,100)], close=True)
    m.add_lwpolyline([(30,30),(70,30),(70,70),(30,70)], close=True)
    result = submit(dxf_bytes(doc), 'hole.dxf', kerf=0.2).json()
    assert result['piece_count'] == 1
    part = result['sheets'][0]['pieces'][0]
    p = Polygon(part['rings'][0], part['rings'][1:])
    assert len(p.interiors) == 1
    assert p.area == pytest.approx(100.2**2-39.8**2, abs=.001)
    assert part['area'] == 8400
    assert len(result['preview']['faces']) > 0


def test_closed_dxf_circle_and_line_loop():
    doc = ezdxf.new(); m=doc.modelspace()
    m.add_circle((0,0), radius=25)
    for a,b in zip([(70,0),(100,0),(100,30),(70,30)],[(100,0),(100,30),(70,30),(70,0)]):
        m.add_line(a,b)
    r=submit(dxf_bytes(doc),'profiles.dxf')
    assert r.status_code==200,r.text
    assert r.json()['piece_count']==2


def test_kerf_rejects_disappearing_hole():
    polygon=Polygon([(0,0),(10,0),(10,10),(0,10)], [[(4.9,4.9),(5.1,4.9),(5.1,5.1),(4.9,5.1)]])
    with pytest.raises(GeometryError,match='agujero'):
        compensate(polygon, 0.5)


def test_multiple_sheets_rotation_and_collision_free():
    parts=[Piece(f'P{i}',box(0,0,70,40),2800) for i in range(12)]
    settings=Settings(width=100,height=100,kerf=0,gap=3,margin=5)
    sheets=nest(parts,settings)
    assert len(sheets)==6
    assert sum(map(len,sheets))==12
    for sheet in sheets:
        for i,p in enumerate(sheet):
            assert box(5,5,95,95).covers(p.polygon)
            for q in sheet[:i]:
                assert p.polygon.distance(q.polygon)>=3-1e-7
    rotated=nest([Piece('P',box(0,0,80,30),2400)],Settings(width=50,height=100))
    assert rotated[0][0].angle==90
    with pytest.raises(GeometryError,match='no cabe'):
        nest([Piece('P',box(0,0,80,30),2400)],Settings(width=50,height=100,rotate=False))


def test_three_exports_and_pdf_real_size():
    r=submit(trimesh.creation.box([20,20,20]).export(file_type='stl'),'cube.stl',width=100,height=80)
    assert r.status_code==200,r.text
    job=r.json()
    r=client.get(f"/api/jobs/{job['id']}/export/dxf")
    assert r.status_code==200
    doc=ezdxf.read(io.StringIO(r.text))
    assert doc.units==4
    assert doc.layers.get('CORTE').dxf.color==1
    assert doc.layers.get('GRABADO').dxf.color==5
    assert len(doc.modelspace().query('LWPOLYLINE'))==6
    assert len(doc.modelspace().query('TEXT'))==6
    assert not doc.audit().has_errors
    svg=client.get(f"/api/jobs/{job['id']}/export/svg")
    import xml.etree.ElementTree as ET
    root=ET.fromstring(svg.content)
    assert root.attrib['width']=='100.0mm'
    assert root.attrib['height']=='80.0mm'
    assert len(root.findall('.//{http://www.w3.org/2000/svg}path'))==6
    pdf=client.get(f"/api/jobs/{job['id']}/export/pdf")
    reader=PdfReader(io.BytesIO(pdf.content))
    assert len(reader.pages)==1
    assert float(reader.pages[0].mediabox.width)==pytest.approx(100*72/25.4,abs=.001)
    assert float(reader.pages[0].mediabox.height)==pytest.approx(80*72/25.4,abs=.001)
    assert 'P001' in reader.pages[0].extract_text()
    assert len(reader.pages[0].images) == 0


def test_multisheet_download_archive():
    r=submit(trimesh.creation.box([70,70,70]).export(file_type='stl'),'box.stl',width=90,height=90)
    assert r.status_code==200,r.text
    job=r.json(); assert len(job['sheets'])==6
    for ext in ('svg','dxf'):
        response=client.get(f"/api/jobs/{job['id']}/export/{ext}")
        assert response.headers['content-type']=='application/zip'
        with ZipFile(io.BytesIO(response.content)) as archive:
            assert len(archive.namelist())==6
            assert all(n.endswith('.'+ext) for n in archive.namelist())
    response=client.get(f"/api/jobs/{job['id']}/export/pdf")
    assert len(PdfReader(io.BytesIO(response.content)).pages)==6


def test_units_and_open_mesh_warning():
    mesh=trimesh.Trimesh([[0,0,0],[10,0,0],[10,5,0],[0,5,0]],[[0,1,2],[0,2,3]],process=False)
    r=submit(mesh.export(file_type='obj'),'plane.obj',units='cm',kerf=0)
    assert r.status_code==200,r.text
    result=r.json()
    assert result['area_mm2']==5000
    assert result['piece_count']==1
    assert any('abierta' in w for w in result['warnings'])


def test_3dm_mesh_and_polyline(tmp_path):
    doc=rh.File3dm(); mesh=rh.Mesh()
    for x,y in [(0,0),(40,0),(40,30),(0,30)]: mesh.Vertices.Add(x,y,0)
    mesh.Faces.AddFace(0,1,2,3);doc.Objects.AddMesh(mesh)
    doc.Objects.AddCurve(rh.PolylineCurve([rh.Point3d(100,0,0),rh.Point3d(120,0,0),rh.Point3d(120,20,0),rh.Point3d(100,0,0)]))
    file=tmp_path/'example.3dm';doc.Write(str(file),8)
    r=submit(file.read_bytes(),'example.3dm')
    assert r.status_code==200,r.text
    assert r.json()['piece_count']==2


def test_bad_files_and_invalid_settings():
    assert submit(b'junk','bad.stl').status_code==422
    assert submit(b'','empty.obj').status_code==422
    assert submit(b'junk','bad.txt').status_code==415
    assert submit(b'junk','bad.obj',width=20,margin=11).status_code==422
    assert submit(b'junk','bad.obj',kerf=-1).status_code==422
    assert client.get('/api/jobs/missing/export/svg').status_code==404
    assert client.get('/api/jobs/missing/export/exe').status_code==422
    doc=ezdxf.new();doc.modelspace().add_line((0,0),(20,20))
    assert submit(dxf_bytes(doc),'open.dxf').status_code==422
    doc=ezdxf.new();doc.modelspace().add_lwpolyline([(0,0),(20,20),(0,20),(20,0)],close=True)
    assert submit(dxf_bytes(doc),'self-intersection.dxf').status_code==422


def test_oversized_piece():
    r=submit(trimesh.creation.box([1000,1000,1000]).export(file_type='stl'),'large.stl')
    assert r.status_code==422
    assert 'no cabe' in r.json()['detail']


def test_scene_instance_transforms():
    scene=trimesh.Scene()
    scene.add_geometry(trimesh.creation.box([10,10,10]),node_name='first')
    scene.add_geometry(trimesh.creation.box([10,10,10]),node_name='second',transform=trimesh.transformations.translation_matrix([40,0,0]))
    # OBJ serializes transformed scene objects into independent face groups.
    r=submit(scene.export(file_type='obj'),'instances.obj')
    assert r.status_code==200,r.text
    assert r.json()['piece_count']==12
    assert r.json()['preview']['bounds']==[50,10,10]


def test_cross_origin_download_exposes_filename():
    r=submit(trimesh.creation.box([10,10,10]).export(file_type='stl'),'box.stl')
    assert r.status_code==200
    response=client.get(f"/api/jobs/{r.json()['id']}/export/dxf",headers={'Origin':'http://localhost:5173'})
    assert response.headers['access-control-allow-origin']=='http://localhost:5173'
    assert 'Content-Disposition' in response.headers['access-control-expose-headers']

```

## frontend/.env.example

```text
# Optional. Keep empty to use the Vite /api proxy to http://127.0.0.1:8000.
VITE_API_URL=

```

## frontend/index.html

```html
<!doctype html><html lang="es"><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width, initial-scale=1.0"/><meta name="theme-color" content="#111414"/><meta name="description" content="PLANAR: del modelo a la materia. Despiece arquitectónico y preparación local de corte láser."/><title>PLANAR — Estudio de fabricación</title><link rel="icon" type="image/svg+xml" href="/favicon.svg"/></head><body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body></html>

```

## frontend/package.json

```json
{
  "name": "planar-studio",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "tsc -b && vite build",
    "preview": "vite preview --host 127.0.0.1",
    "test": "vitest run"
  },
  "dependencies": {
    "@react-three/drei": "^10.7.0",
    "@react-three/fiber": "9.8.2",
    "lucide-react": "^0.577.0",
    "react": "^19.2.0",
    "react-dom": "^19.2.0",
    "three": "0.187.0"
  },
  "devDependencies": {
    "@tailwindcss/vite": "^4.2.0",
    "@testing-library/jest-dom": "^6.9.1",
    "@testing-library/react": "^16.3.3",
    "@testing-library/user-event": "^14.6.8",
    "@types/react": "^19.2.0",
    "@types/react-dom": "^19.2.0",
    "@types/three": "^0.183.0",
    "@vitejs/plugin-react": "^5.1.0",
    "jsdom": "^26.1.0",
    "tailwindcss": "^4.2.0",
    "typescript": "~5.9.3",
    "vite": "^7.3.0",
    "vitest": "^3.2.7"
  }
}

```

## frontend/public/favicon.svg

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48"><rect width="48" height="48" rx="12" fill="#d9fa75"/><path d="M12 35V13h15l9 11-9 11z" fill="none" stroke="#17201c" stroke-width="3"/><path d="M12 24h24M27 13v22" stroke="#17201c" stroke-width="2"/></svg>

```

## frontend/src/App.tsx

```tsx
import {Suspense,lazy,useEffect,useRef,useState} from 'react'
import {ArrowUpRight, ArrowRight, Download, LogOut, CircleHelp, X, AlertTriangle, Layers3, Package, Leaf, Check, ChevronDown, Command, Box, Loader2, FileCode2} from 'lucide-react'
import {Brand} from './components/Brand'
import {Login} from './components/Login'
import {Uploader} from './components/Uploader'
import {MaterialPanel} from './components/MaterialPanel'
const ModelViewer = lazy(() => import('./components/ModelViewer').then(module => ({default:module.ModelViewer})))
import {SheetViewer} from './components/SheetViewer'
import {defaults} from './types'
import type {Job,Settings,User} from './types'
import {processModel,downloadJob} from './api'
function getUser():User|null {try {const u=JSON.parse(sessionStorage.getItem('planar-demo-user')??'null');return u&&typeof u.name==='string'&&typeof u.email==='string'?u:null}catch{return null}}
export default function App() {
  const [user,setUser]=useState<User|null>(getUser),[file,setFile]=useState<File|null>(null),[settings,setSettings]=useState<Settings>(defaults)
  const [job,setJob]=useState<Job|null>(null),[busy,setBusy]=useState(false),[downloading,setDownloading]=useState(false),[error,setError]=useState(''),[format,setFormat]=useState('dxf'),[selected,setSelected]=useState<string|null>(null),[help,setHelp]=useState(false)
  const dialog=useRef<HTMLDialogElement>(null)
  useEffect(()=>{if(help)dialog.current?.showModal();else dialog.current?.close()},[help])
  const stale=!!job&&JSON.stringify(job.settings)!==JSON.stringify(settings)
  const selectedPiece=job?.sheets.flatMap(s=>s.pieces).find(p=>p.id===selected)
  function login(u:User){setUser(u);try{sessionStorage.setItem('planar-demo-user',JSON.stringify(u))}catch{/* The demo also works without storage. */}}
  function logout(){try{sessionStorage.removeItem('planar-demo-user')}catch{}setUser(null)}
  function updateFile(f:File|null){setFile(f);setJob(null);setError('');setSelected(null)}
  function valid(s:Settings){return [s.width,s.height,s.thickness,s.kerf,s.gap,s.margin].every(Number.isFinite)&&s.width>=20&&s.width<=3000&&s.height>=20&&s.height<=3000&&s.thickness>=.1&&s.thickness<=50&&s.kerf>=0&&s.kerf<=3&&s.gap>=.1&&s.gap<=50&&s.margin>=0&&s.margin<=100&&s.margin*2<Math.min(s.width,s.height)}
  async function process(f=file,s=settings){if(!f)return; if(!valid(s)){setError('Revisa las medidas: los valores deben estar dentro de los rangos y el margen no puede consumir la lámina.');return}setBusy(true);setError('');try{setJob(await processModel(f,s));setSelected(null)}catch(e){setError(e instanceof Error?e.message:'No se pudo procesar el archivo.')}finally{setBusy(false)}}
  async function demo(){setError('');setBusy(true);try{const r=await fetch('/demo-pabellon.obj');if(!r.ok)throw new Error('No se pudo cargar el ejemplo.');const f=new File([await r.blob()],'pabellon-estudio.obj');updateFile(f);setSettings({...defaults});await process(f,{...defaults})}catch(e){setError(e instanceof Error?e.message:'No se pudo cargar el ejemplo.')}finally{setBusy(false)}}
  async function download(){if(!job||stale)return;setDownloading(true);setError('');try{await downloadJob(job,format)}catch(e){setError(e instanceof Error?e.message:'No se pudo descargar.')}finally{setDownloading(false)}}
  if(!user)return <Login onLogin={login}/>
  return <div className="app-shell"><header className="topbar"><Brand small/><div className="topbar-divider"/><span className="workspace-name">Mi espacio de trabajo<ChevronDown size={12}/></span><div className="topbar-end"><span className="local-chip"><span className="status-dot"/>ENTORNO LOCAL</span><button className="icon-button help-button" title="Guía rápida" aria-label="Guía rápida" onClick={()=>setHelp(true)}><CircleHelp size={19}/></button><span className="avatar" title={user.email}>{user.name.slice(0,2).toUpperCase()}</span><button className="icon-button" title="Cerrar sesión" aria-label="Cerrar sesión" disabled={busy} onClick={logout}><LogOut size={17}/></button></div></header>
    <div className="app-body"><aside className="sidebar"><div className="sidebar-title"><span className="sidebar-square"><Command size={17}/></span><div><strong>Estudio de corte</strong><span>PREPARACIÓN DE ARCHIVOS</span></div><span className="version">BETA</span></div><div className="sidebar-content"><Uploader file={file} disabled={busy} onFile={updateFile} onDemo={demo} onError={setError}/><div className="sidebar-separator"/><MaterialPanel value={settings} onChange={setSettings} disabled={busy}/><div className="material-note"><Leaf size={15}/><span>Un buen acomodo también<br/>es una decisión de diseño.</span></div></div><div className="sidebar-bottom"><button className="primary generate" disabled={!file||busy} onClick={()=>process()}>{busy?<><Loader2 size={17} className="spin"/>Procesando…</>:<>Generar despiece<ArrowRight size={17}/></>}</button><span>Procesamiento local · Tus archivos se quedan aquí</span></div></aside>
      <main className="workspace"><div className="workspace-heading"><div><div className="breadcrumb">PROYECTOS <span>/</span> ESTUDIO DE FABRICACIÓN</div><h1>Del modelo a la materia<span>.</span></h1><p>Piensa en tres dimensiones. Fabrica plano a plano.</p></div><button className="quiet-button" onClick={()=>setHelp(true)}>Cómo funciona<ArrowUpRight size={15}/></button></div>
      <div className="project-bar"><div className="project-name"><span className="project-icon"><Box size={17}/></span><div><strong title={file?.name}>{file?.name.replace(/\.[^.]+$/,'')??'Proyecto sin título'}</strong><span>{job?`${job.piece_count} piezas detectadas · ${job.settings.thickness} mm de espesor`:'Carga un modelo para empezar a explorar'}</span></div></div><div className="step-indicators"><span className={file?'done':'current'}>{file?<Check size={11}/>:'1'}<b>Modelo</b></span><i/><span className={job?'done':file?'current':''}>{job?<Check size={11}/>:'2'}<b>Despiece</b></span><i/><span className={job&&!stale?'current':''}>3<b>Fabricación</b></span></div></div>
      {error&&<div className="alert error" role="alert"><AlertTriangle size={18}/><span>{error}</span><button className="icon-button" aria-label="Cerrar error" onClick={()=>setError('')}><X size={16}/></button></div>}
      {stale&&<div className="alert warning" role="status"><AlertTriangle size={17}/><span>Los parámetros cambiaron. Genera el despiece de nuevo para actualizar las láminas y exportar.</span></div>}
      <div className="viewers"><Suspense fallback={<div className="viewer-panel empty-state">Cargando visor 3D…</div>}><ModelViewer job={job} busy={busy}/></Suspense><SheetViewer job={job} selected={selected} onSelect={setSelected}/></div>
      <div className="results-row"><div className="metric"><span className="metric-icon"><Package size={18}/></span><div><span>Piezas listas</span><strong>{job?String(job.piece_count).padStart(2,'0'):'—'}<small>paneles</small></strong></div></div><div className="metric"><span className="metric-icon"><Layers3 size={18}/></span><div><span>Láminas necesarias</span><strong>{job?String(job.sheets.length).padStart(2,'0'):'—'}<small>{job?`${job.settings.width} × ${job.settings.height} mm`:'formato seleccionado'}</small></strong></div></div><div className="metric utilization-metric"><span className="metric-icon lime"><Leaf size={18}/></span><div><span>Aprovechamiento</span><strong className="lime-text">{job?`${job.utilization.toFixed(1)}%`:'—'}<small>área nominal / material</small></strong></div><svg viewBox="0 0 42 42" className="progress-ring" aria-hidden="true"><circle cx="21" cy="21" r="16"/><circle cx="21" cy="21" r="16" pathLength="100" strokeDasharray={`${job?.utilization??0} 100`}/></svg></div></div>
      {selectedPiece&&<div className="selection-info"><span className="status-dot"/><strong>{selectedPiece.id}</strong><span>{(selectedPiece.area/100).toFixed(2)} cm²</span><span>Rotación {selectedPiece.angle}°</span><button className="icon-button" aria-label="Deseleccionar pieza" onClick={()=>setSelected(null)}><X size={14}/></button></div>}
      <div className="export-bar"><div className="export-label"><span className="export-icon"><FileCode2 size={22}/></span><div><h2>El siguiente paso está en tus manos.</h2><p>{job&&job.sheets.length>1?'DXF y SVG: ZIP con una lámina por archivo. PDF: una página por lámina.':'Archivos a escala 1:1 · Corte en rojo · Grabado en azul'}</p></div></div><div className="export-actions"><label className="sr-only" htmlFor="export-format">Formato de salida</label><div className="select-wrap"><select id="export-format" value={format} onChange={e=>setFormat(e.target.value)}><option value="dxf">DXF · CAD</option><option value="svg">SVG · Vectorial</option><option value="pdf">PDF · Escala 1:1</option></select><ChevronDown size={14}/></div><button className="primary" disabled={!job||busy||stale||downloading} onClick={download}>{downloading?<Loader2 size={16} className="spin"/>:<Download size={16}/>}Descargar</button></div></div>
      {job&&<details className="processing-notes"><summary><AlertTriangle size={14}/>Notas de fabricación <span>{job.warnings.length}</span><ChevronDown size={14}/></summary><ul>{job.warnings.map(w=><li key={w}>{w}</li>)}<li>Acomodo heurístico por cajas envolventes: no garantiza el óptimo ni coloca piezas dentro de agujeros.</li><li>El kerf ya está compensado. Desactiva una segunda compensación en el software del láser y revisa el grabado antes de cortar.</li></ul></details>}
      <footer className="workspace-footer"><span><span className="status-dot muted"/>PLANAR STUDIO <b>/</b> HECHO PARA MATERIALIZAR IDEAS</span><span>V 0.1 <b>·</b> MM <b>·</b> LOCAL</span></footer>
      </main></div>
      <dialog ref={dialog} className="help-dialog" onCancel={()=>setHelp(false)} onClick={e=>{if(e.target===e.currentTarget)setHelp(false)}}><div className="dialog-head"><Brand small/><button className="icon-button" aria-label="Cerrar guía" onClick={()=>setHelp(false)}><X size={20}/></button></div><div className="eyebrow">GUÍA RÁPIDA</div><h2>Prepara tu primera lámina.</h2><ol><li><strong>Importa.</strong> Sube un modelo o prueba el pabellón. STL, OBJ, PLY y OFF admiten mallas; DXF requiere perfiles cerrados en XY. Para 3DM, usa mallas o polilíneas cerradas; los Brep requieren mallas de render guardadas.</li><li><strong>Configura.</strong> Elige las unidades del archivo, dimensiones de lámina, grosor y kerf. Los archivos sin unidades se interpretan según tu selección.</li><li><strong>Genera.</strong> Las caras coplanares conectadas forman paneles. Las curvas de una malla se separan en facetas, sin desplegado continuo. El grosor no crea encastres.</li><li><strong>Revisa y exporta.</strong> Inspecciona medidas, todas las láminas y advertencias. DXF y SVG tienen CORTE y GRABADO. El PDF es vectorial: imprime al 100%, sin ajustar a página.</li></ol><p className="help-note">Demo de acceso, sin autenticación real. Los resultados viven en memoria durante una hora (máximo 20 trabajos) y se pierden al reiniciar el backend. Solo para ejecución local.</p><button className="primary" onClick={()=>setHelp(false)}>Vamos a crear<ArrowRight size={16}/></button></dialog>
  </div>
}

```

## frontend/src/api.ts

```typescript
import type {Job, Settings} from './types'
const BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')
async function check(response:Response) {
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(typeof data.detail === 'string' ? data.detail : `Error del servidor (${response.status}).`)
  }
  return response
}
export async function processModel(file:File, settings:Settings):Promise<Job> {
  const form = new FormData(); form.append('file', file); form.append('settings', JSON.stringify(settings))
  try { return await check(await fetch(`${BASE}/api/process`, {method:'POST',body:form})).then(r=>r.json()) }
  catch (e) { if (e instanceof TypeError) throw new Error('No se pudo conectar al backend. Inicia FastAPI en el puerto 8000.'); throw e }
}
export async function downloadJob(job:Job, format:string) {
  const response = await check(await fetch(`${BASE}/api/jobs/${job.id}/export/${format}`))
  const blob = await response.blob(); const url = URL.createObjectURL(blob)
  const filename = response.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1] ?? `planar.${format}`
  const a = document.createElement('a'); a.href=url; a.download=filename; document.body.appendChild(a); a.click(); a.remove()
  setTimeout(()=>URL.revokeObjectURL(url), 30000)
}

```

## frontend/src/components/Brand.tsx

```tsx
export function Brand({small=false}:{small?:boolean}) {
  return <div className={`brand ${small?'small':''}`}><svg viewBox="0 0 40 40" aria-hidden="true"><path d="M8 31V9h15l9 11-9 11Z"/><path d="M8 20h24M23 9v22"/></svg><span>PLANAR<span className="brand-dot">.</span></span></div>
}

```

## frontend/src/components/Login.tsx

```tsx
import {useState} from 'react'
import {ArrowUpRight, ArrowRight, Layers3, ScanLine, Box, Eye, EyeOff} from 'lucide-react'
import {Brand} from './Brand'
import type {User} from '../types'
export function Login({onLogin}:{onLogin:(user:User)=>void}) {
  const [register,setRegister]=useState(false), [show,setShow]=useState(false)
  const [email,setEmail]=useState(''), [name,setName]=useState(''), [password,setPassword]=useState('')
  function enter(e:React.FormEvent) {e.preventDefault(); onLogin({name:register?name:email.split('@')[0],email})}
  return <div className="login-page"><section className="login-form-side"><Brand/>
    <div className="login-form-wrap"><div className="eyebrow"><span className="status-dot"/> TU ESTUDIO DE FABRICACIÓN</div>
      <h1>Las buenas ideas<br/>toman <em>forma.</em></h1><p className="login-subtitle">Del modelo digital a tu próxima maqueta.<br/>Un espacio para diseñar, desplegar y fabricar.</p>
      <div className="auth-tabs"><button className={!register?'active':''} onClick={()=>setRegister(false)}>Iniciar sesión</button><button className={register?'active':''} onClick={()=>setRegister(true)}>Crear cuenta</button></div>
      <form onSubmit={enter}>{register&&<label>Nombre<input required autoComplete="name" placeholder="Tu nombre" value={name} onChange={e=>setName(e.target.value)}/></label>}
      <label>Correo electrónico<input type="email" required autoComplete="email" placeholder="nombre@universidad.edu" value={email} onChange={e=>setEmail(e.target.value)}/></label>
      <label>Contraseña<div className="password-field"><input required minLength={6} type={show?'text':'password'} autoComplete={register?'new-password':'current-password'} placeholder="Al menos 6 caracteres" value={password} onChange={e=>setPassword(e.target.value)}/><button type="button" className="icon-button" aria-label={show?'Ocultar contraseña':'Mostrar contraseña'} onClick={()=>setShow(!show)}>{show?<EyeOff size={17}/>:<Eye size={17}/>}</button></div></label>
      <button className="primary auth-submit" type="submit">{register?'Crear mi espacio':'Entrar al estudio'}<ArrowRight size={18}/></button></form>
      <div className="or"><span/>o explora primero<span/></div><button className="demo-login" onClick={()=>onLogin({name:'Estudiante',email:'demo@planar.local'})}>Acceder a la demo<ArrowUpRight size={16}/></button>
      <p className="auth-note">Acceso de demostración. No se crea una cuenta real<br/>ni se guarda tu contraseña.</p>
    </div><footer>DISEÑADO PARA PENSAR CON LAS MANOS.<span>V 0.1 / LOCAL</span></footer>
    </section><section className="login-art"><div className="art-top"><span>EXPLORACIÓN N.º 001</span><span>ESTUDIO DE PLANOS / 2026</span></div>
      <div className="art-title">Una idea.<br/>Infinitas <span>posibilidades.</span></div>
      <svg className="architecture-drawing" viewBox="0 0 680 520" role="img" aria-label="Dibujo axonométrico de una maqueta arquitectónica desmontada"><defs><pattern id="grid" width="38" height="22" patternUnits="userSpaceOnUse" patternTransform="skewY(-30)"><path d="M38 0H0V22" fill="none" stroke="#353e32" strokeWidth="0.6"/></pattern><linearGradient id="face" x1="0" y1="0" x2="1" y2="1"><stop stopColor="#ccdbad"/><stop offset="1" stopColor="#778668"/></linearGradient></defs>
      <path d="M30 340 330 166 650 350 348 522Z" fill="url(#grid)"/>
      <g fill="none" stroke="#647651" strokeDasharray="4 6"><path d="m145 135 0 213m205-331v215m180-119v235M145 348 350 230 530 334 325 452Z"/></g>
      <path d="M145 348 350 230 530 334 325 452Z" fill="#4b5943" stroke="#b1c697"/><path d="m145 348 0 12 180 104 205-118v-12L325 452Z" fill="#738366" stroke="#a2b98b"/>
      <path d="m145 145 205-118v183L145 328Z" fill="url(#face)" stroke="#e0eec8"/><path d="m160 150 175-101v144L160 294Z" fill="#58694b" stroke="#bad29b"/>
      <path d="m160 199 175-101m-135 29v144m44-169v144m44-170v144" stroke="#cbdcaf" strokeWidth="5"/>
      <path d="m370 50 160 93v180l-160-93Z" fill="#83946d" stroke="#d4e3b7"/><path d="m391 87 51 30v104l-51-29Z" fill="#253321" stroke="#bfd29f"/><path d="m459 127 50 30v104l-50-29Z" fill="#253321" stroke="#bfd29f"/>
      <path d="m198 124 152-87 163 94-152 88Z" fill="#caddad" fillOpacity=".1" stroke="#d9fa75"/>
      <path d="m210 309 94-54 94 54-94 54Z" fill="#a4b78c" stroke="#d4e3b7"/><path d="m210 309 0 30 94 54v-30Z" fill="#6d7e5b"/><path d="m304 363 94-54v30l-94 54Z" fill="#415038"/>
      <g stroke="#d9fa75" fill="none"><path d="m105 375 180 104m-186-109 12 10m168 94 12 10M550 354l-205 119m199-124 12 10m-217 109 12 10"/><path d="M570 149v173m-5-173h10m-10 173h10"/></g>
      <g fontFamily="monospace" fontSize="11" fill="#d9fa75"><text x="166" y="449" transform="rotate(30 166 449)">180.00</text><text x="440" y="423" transform="rotate(-30 440 423)">240.00</text><text x="583" y="240" transform="rotate(-90 583 240)">120.00</text><text x="183" y="85">P01</text><text x="503" y="103">P02</text><text x="482" y="386">P03</text></g></svg>
      <div className="art-feature-row"><div><Box size={19}/><span>Importa tu modelo</span></div><i/><div><Layers3 size={19}/><span>Optimiza cada plano</span></div><i/><div><ScanLine size={19}/><span>Llévalo al láser</span></div></div>
      <div className="art-bottom"><span>MENOS DESPERDICIO. MÁS ARQUITECTURA.</span><span>01 — 03</span></div>
    </section></div>
}

```

## frontend/src/components/MaterialPanel.tsx

```tsx
import {ChevronDown,SlidersHorizontal} from 'lucide-react'
import {useState} from 'react'
import type {Settings} from '../types'
export function MaterialPanel({value,onChange,disabled}:{value:Settings;onChange:(s:Settings)=>void;disabled:boolean}) {
  const [advanced,setAdvanced]=useState(false), [preset,setPreset]=useState('600x400')
  function change(key:keyof Settings,next:number|string|boolean){onChange({...value,[key]:next})}
  const numberField=(key:'width'|'height'|'thickness'|'kerf'|'gap'|'margin', label:string, min:number,max:number,step:number)=> <label>{label}<div className="unit-input"><input aria-label={label} type="number" min={min} max={max} step={step} required value={Number.isNaN(value[key])?'':value[key]} onChange={e=>change(key,e.target.valueAsNumber)}/><span>mm</span></div></label>
  return <fieldset disabled={disabled} className="material-fields"><div className="section-label"><span>02 / MATERIAL Y CORTE</span><SlidersHorizontal size={13}/></div>
    <label>Formato de lámina<div className="select-wrap"><select value={preset} onChange={e=>{setPreset(e.target.value);if(e.target.value!=='custom'){const [width,height]=e.target.value.split('x').map(Number);onChange({...value,width,height})}}}><option value="600x400">60 × 40 cm · Estándar</option><option value="900x600">90 × 60 cm · Mediana</option><option value="1200x900">120 × 90 cm · Grande</option><option value="custom">Medidas personalizadas</option></select><ChevronDown size={14}/></div></label>
    {preset==='custom'&&<div className="field-row">{numberField('width','Ancho',20,3000,1)}{numberField('height','Alto',20,3000,1)}</div>}
    <div className="field-row">{numberField('thickness','Espesor',0.1,50,0.1)}{numberField('kerf','Kerf',0,3,0.01)}</div><p className="field-help">Compensación de trayectoria: kerf ÷ 2.</p>
    <label>Unidades del archivo<div className="select-wrap"><select value={value.units} onChange={e=>change('units',e.target.value)}><option value="mm">Milímetros (mm)</option><option value="cm">Centímetros (cm)</option><option value="m">Metros (m)</option><option value="in">Pulgadas (in)</option></select><ChevronDown size={14}/></div></label>
    <button type="button" className="advanced-toggle" aria-expanded={advanced} onClick={()=>setAdvanced(!advanced)}>Ajustes de acomodo<ChevronDown size={14} className={advanced?'rotated':''}/></button>
    {advanced&&<div className="advanced-fields"><div className="field-row">{numberField('gap','Separación',0.1,50,0.1)}{numberField('margin','Margen',0,100,0.5)}</div><label className="checkbox-label"><input type="checkbox" checked={value.rotate} onChange={e=>change('rotate',e.target.checked)}/>Permitir giros de 90°</label></div>}
  </fieldset>
}

```

## frontend/src/components/ModelViewer.tsx

```tsx
import {Component, Suspense, useEffect,useMemo,useState} from 'react'
import type {ReactNode} from 'react'
import {Canvas} from '@react-three/fiber'
import {Bounds, Edges, Grid, OrbitControls, GizmoHelper, GizmoViewport, Center, ContactShadows} from '@react-three/drei'
import * as THREE from 'three'
import {Box, RotateCcw, Scan, AlertTriangle} from 'lucide-react'
import type {Job} from '../types'
class ViewerBoundary extends Component<{children:ReactNode},{failed:boolean}> {
  state={failed:false}
  static getDerivedStateFromError(){return {failed:true}}
  render(){return this.state.failed?<div className="empty-state"><AlertTriangle/><h3>Vista 3D no disponible</h3><p>Activa WebGL o prueba otro navegador.<br/>El despiece y las descargas siguen disponibles.</p></div>:this.props.children}
}
function LoadedMesh({preview,wire}:{preview:Job['preview'];wire:boolean}) {
  const geometry=useMemo(()=>{const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(preview.vertices,3));g.setIndex(preview.faces);g.computeVertexNormals();return g},[preview])
  useEffect(()=>()=>geometry.dispose(),[geometry])
  return <group rotation={[-Math.PI/2,0,0]}><mesh geometry={geometry} castShadow receiveShadow><meshStandardMaterial color="#cbd4bc" metalness={0.1} roughness={0.7} side={THREE.DoubleSide} wireframe={wire}/>{!wire&&<Edges threshold={12} color="#3c4a34"/>}</mesh></group>
}
function Sample({wire}:{wire:boolean}) {
  return <group><mesh position={[0,.08,0]} receiveShadow castShadow><boxGeometry args={[3.5,.16,2.8]}/><meshStandardMaterial color="#7a876b" wireframe={wire}/><Edges color="#b4c49c"/></mesh>{[-1.2,0,1.2].map(x=><mesh key={x} position={[x,1,0]} castShadow receiveShadow><boxGeometry args={[.08,1.8,2.2]}/><meshStandardMaterial color="#ccd7b7" wireframe={wire}/><Edges color="#5b684d"/></mesh>)}<mesh position={[0,1.95,0]} castShadow><boxGeometry args={[3.2,.08,2.4]}/><meshStandardMaterial color="#bbcba0" transparent opacity={.8} wireframe={wire}/><Edges color="#5b684d"/></mesh></group>
}
export function ModelViewer({job,busy}:{job:Job|null;busy:boolean}) {
  const [wire,setWire]=useState(false), [reset,setReset]=useState(0)
  const extent=job?Math.max(...job.preview.bounds,1):4
  return <section className="viewer-panel model-panel"><div className="panel-heading"><div><Box size={16}/><h2>Modelo 3D</h2><span className="badge">{job?'ORIGINAL':'EJEMPLO'}</span></div><div className="panel-actions"><button title="Alternar malla" aria-label="Alternar malla" aria-pressed={wire} className={`icon-button ${wire?'active':''}`} onClick={()=>setWire(!wire)}><Scan size={16}/></button><button title="Restablecer cámara" aria-label="Restablecer cámara" className="icon-button" onClick={()=>setReset(reset+1)}><RotateCcw size={15}/></button></div></div>
    <div className="model-canvas"><span className="viewport-label">PERSPECTIVA <span> / </span> {wire?'WIREFRAME':'SOMBREADO'}</span><ViewerBoundary><Suspense fallback={<div className="empty-state">Preparando visor…</div>}><Canvas key={`${job?.id??'sample'}-${reset}`} shadows camera={{position:[extent,extent*.8,extent], fov:40, near:.01,far:100000}} dpr={[1,1.7]} gl={{antialias:true}} fallback={<div className="empty-state">Tu navegador no admite WebGL.</div>}><color attach="background" args={['#1b201e']}/><ambientLight intensity={1.4}/><directionalLight position={[extent,extent*2,extent]} intensity={2.8} castShadow shadow-mapSize={[1024,1024]} shadow-camera-left={-extent} shadow-camera-right={extent} shadow-camera-top={extent} shadow-camera-bottom={-extent} shadow-camera-far={extent*5}/><Bounds fit clip observe margin={1.35}><Center top>{job?<LoadedMesh preview={job.preview} wire={wire}/>:<Sample wire={wire}/>}</Center></Bounds><Grid position={[0,-.01,0]} args={[extent*6,extent*6]} cellSize={extent/12} sectionSize={extent/3} cellColor="#303a32" sectionColor="#455142" fadeDistance={extent*5} infiniteGrid/><ContactShadows position={[0,-.02,0]} opacity={.3} scale={extent*3} blur={2.5} far={extent*2} resolution={256} frames={1}/><OrbitControls makeDefault minDistance={extent*.05} maxDistance={extent*8}/><GizmoHelper alignment="bottom-right" margin={[50,50]}><GizmoViewport axisColors={['#b77671','#9cb87e','#7796b8']} labelColor="white" hideNegativeAxes/></GizmoHelper></Canvas></Suspense></ViewerBoundary>{busy&&<div className="canvas-busy"><span className="spinner"/>Procesando geometría…</div>}<div className="viewport-hint">Arrastrar para orbitar <b>·</b> Rueda para zoom <b>·</b> Clic derecho para mover</div></div>
    <div className="panel-footer"><span><span className="status-dot muted"/>{job?job.filename:'Pabellón conceptual · vista de ejemplo'}</span><span>{job?`${job.preview.bounds.map(n=>n.toFixed(1)).join(' × ')} mm`:'Z ↑'}</span></div>
  </section>
}

```

## frontend/src/components/SheetViewer.tsx

```tsx
import {useEffect,useRef,useState} from 'react'
import {Layers3, Plus, Minus, Maximize, ChevronLeft,ChevronRight,MousePointer2,Hand} from 'lucide-react'
import type {Job,Piece} from '../types'
const colors=['#b5c397','#a5bda9','#c5c1a1','#9cbab5','#b3adbe','#c5b298']
export function SheetViewer({job,selected,onSelect}:{job:Job|null;selected:string|null;onSelect:(id:string|null)=>void}) {
  const [index,setIndex]=useState(0), [zoom,setZoom]=useState(1), [offset,setOffset]=useState([0,0]), [pan,setPan]=useState(false)
  const drag=useRef<{x:number;y:number;ox:number;oy:number}|null>(null),svg=useRef<SVGSVGElement>(null)
  useEffect(()=>{setIndex(0);setZoom(1);setOffset([0,0])},[job?.id])
  const w=job?.settings.width??600,h=job?.settings.height??400,sheet=job?.sheets[index]
  const vbw=(w+36)/zoom, vbh=(h+36)/zoom
  const path=(p:Piece)=>p.rings.map(r=>r.map(([x,y],i)=>`${i?'L':'M'} ${x} ${h-y}`).join(' ')+' Z').join(' ')
  function reset(){setZoom(1);setOffset([0,0])}
  return <section className="viewer-panel sheet-panel"><div className="panel-heading"><div><Layers3 size={16}/><h2>Lámina de corte</h2><span className="badge">2D</span></div><div className="panel-actions"><button className={`icon-button ${pan?'active':''}`} title={pan?'Seleccionar piezas':'Mover lámina'} aria-label={pan?'Seleccionar piezas':'Mover lámina'} onClick={()=>setPan(!pan)}>{pan?<Hand size={16}/>:<MousePointer2 size={16}/>}</button><button className="icon-button" aria-label="Acercar lámina" onClick={()=>setZoom(z=>Math.min(z*1.3,8))}><Plus size={16}/></button><button className="icon-button" aria-label="Alejar lámina" onClick={()=>setZoom(z=>Math.max(z/1.3,.5))}><Minus size={16}/></button><button className="icon-button" aria-label="Ajustar lámina" onClick={reset}><Maximize size={15}/></button></div></div>
    <div className={`sheet-canvas ${pan?'pan-mode':''}`}><div className="sheet-ruler top-ruler">0 <span>{(w/4).toFixed(0)}</span><span>{(w/2).toFixed(0)}</span><span>{(w*3/4).toFixed(0)}</span><span>{w} mm</span></div>
    {sheet?<svg ref={svg} aria-label={`Lámina ${index+1} con ${sheet.pieces.length} piezas`} viewBox={`${w/2-vbw/2+offset[0]} ${h/2-vbh/2+offset[1]} ${vbw} ${vbh}`} onPointerDown={e=>{if(!pan)return;e.currentTarget.setPointerCapture(e.pointerId);drag.current={x:e.clientX,y:e.clientY,ox:offset[0],oy:offset[1]}}} onPointerMove={e=>{if(!drag.current||!svg.current)return;const rect=svg.current.getBoundingClientRect();const scale=Math.min(rect.width/vbw,rect.height/vbh);setOffset([drag.current.ox-(e.clientX-drag.current.x)/scale,drag.current.oy-(e.clientY-drag.current.y)/scale])}} onPointerUp={()=>drag.current=null} onPointerCancel={()=>drag.current=null}>
      <defs><pattern id="sheet-grid" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M10 0H0V10" fill="none" stroke="#424638" strokeWidth=".25"/></pattern></defs><rect x="0" y="0" width={w} height={h} fill="#30362b" stroke="#677654" strokeWidth=".7"/><rect width={w} height={h} fill="url(#sheet-grid)"/><rect x={job!.settings.margin} y={job!.settings.margin} width={w-2*job!.settings.margin} height={h-2*job!.settings.margin} fill="none" stroke="#8c986a" strokeWidth=".35" strokeDasharray="3 3"/>
      {sheet.pieces.map((p,i)=><g key={p.id} role="button" tabIndex={pan?-1:0} aria-label={`Seleccionar pieza ${p.id}`} className="sheet-piece" onClick={()=>{if(!pan)onSelect(selected===p.id?null:p.id)}} onKeyDown={e=>{if(!pan&&(e.key==='Enter'||e.key===' ')){e.preventDefault();onSelect(p.id)}}}><path d={path(p)} fill={colors[i%colors.length]} fillOpacity={selected === p.id ? .9 : .5} fillRule="evenodd" stroke={selected===p.id?'#e2ff8e':'#c2d197'} strokeWidth={selected===p.id?1.4:.55}/><text x={p.label[0]} y={h-p.label[1]} textAnchor="middle" dominantBaseline="central" fontSize={Math.max(1,Math.min(5,Math.sqrt(p.area)/9))} fill="#ecf4da" pointerEvents="none">{p.id}</text></g>)}
    </svg>:<div className="empty-sheet"><div className="empty-sheet-drawing"><span/><span/><span/><span/></div><h3>Cada pieza, en su lugar.</h3><p>Carga tu modelo y genera el despiece<br/>para preparar tu primera lámina.</p><div className="empty-dim">600 × 400 MM</div></div>}
    <div className="sheet-legend"><span><i className="cut"/>Contorno de corte</span><span><i className="engrave"/>Identificador</span><span>{Math.round(zoom*100)}%</span></div></div>
    <div className="panel-footer"><div className="sheet-pagination"><button disabled={!sheet||index===0} aria-label="Lámina anterior" className="icon-button" onClick={()=>{setIndex(index-1);reset();onSelect(null)}}><ChevronLeft size={14}/></button><span>Lámina {sheet?String(index+1).padStart(2,'0'):'—'} <b>/ {job?String(job.sheets.length).padStart(2,'0'):'—'}</b></span><button disabled={!job||index>=job.sheets.length-1} aria-label="Lámina siguiente" className="icon-button" onClick={()=>{setIndex(index+1);reset();onSelect(null)}}><ChevronRight size={14}/></button></div><span>{sheet?`${sheet.utilization.toFixed(1)}% aprovechado`:'A escala · milímetros'}</span></div>
  </section>
}

```

## frontend/src/components/Uploader.tsx

```tsx
import {useRef,useState} from 'react'
import {UploadCloud, FileBox, X, FlaskConical} from 'lucide-react'
const allowed = /\.(stl|obj|dxf|3dm|ply|off)$/i
export function Uploader({file,disabled,onFile,onDemo,onError}:{file:File|null;disabled:boolean;onFile:(file:File|null)=>void;onDemo:()=>void;onError:(error:string)=>void}) {
  const input=useRef<HTMLInputElement>(null), [drag,setDrag]=useState(false)
  function choose(file?:File) {if(!file)return; if(!allowed.test(file.name))return onError('Usa un archivo STL, OBJ, DXF, 3DM, PLY u OFF.'); if(file.size>20*1024*1024)return onError('El archivo debe pesar menos de 20 MB.');if(!file.size)return onError('El archivo está vacío.');onFile(file)}
  return <div><div className="section-label"><span>01 / MODELO DE ORIGEN</span><span>20 MB MÁX.</span></div>
    <input ref={input} type="file" accept=".stl,.obj,.dxf,.3dm,.ply,.off" hidden disabled={disabled} onChange={e=>{choose(e.target.files?.[0]);e.target.value=''}}/>
    {file?<div className="selected-file"><div className="file-icon"><FileBox size={22}/></div><div><strong title={file.name}>{file.name}</strong><small>{(file.size/1024).toFixed(1)} KB · LISTO PARA PROCESAR</small></div><button disabled={disabled} className="icon-button" aria-label="Quitar archivo" onClick={()=>onFile(null)}><X size={16}/></button></div>:<button disabled={disabled} className={`dropzone ${drag?'dragging':''}`} onClick={()=>input.current?.click()} onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);if(!disabled)choose(e.dataTransfer.files[0])}}><span className="upload-icon"><UploadCloud size={23}/></span><strong>Tu próximo proyecto,<br/>empieza aquí.</strong><span>Arrastra un archivo o <u>explora</u></span><small>STL · OBJ · DXF · 3DM · PLY · OFF</small></button>}
    <button className="example-button" disabled={disabled} onClick={onDemo}><FlaskConical size={14}/>Probar con un pabellón de ejemplo<span>↗</span></button>
  </div>
}

```

## frontend/src/main.tsx

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles.css'
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)

```

## frontend/src/styles.css

```css
@import "tailwindcss";
@theme { --font-sans: 'Inter','Segoe UI',system-ui,sans-serif; }
:root{font-family:'Inter','Segoe UI',system-ui,sans-serif;color:#e4e9e2;background:#111414;font-synthesis:none;color-scheme:dark;--lime:#d6f58a;--muted:#8a948e;--line:#2c3330;--panel:#191e1b;font-size:13px}*{box-sizing:border-box}body{margin:0}button,input,select{font:inherit}button{cursor:pointer;transition:background .18s,color .18s,opacity .18s;white-space:nowrap}button:disabled{opacity:.4;cursor:not-allowed}button:focus-visible,input:focus-visible,select:focus-visible,[tabindex]:focus-visible{outline:2px solid var(--lime);outline-offset:4px}button{border:0;background:none;color:inherit}input,select{width:100%;border:1px solid #353e37;background:#222923;border-radius:6px;min-height:41px;padding:10px 12px;color:#e4e9e2;outline:none}input:focus,select:focus{border-color:#a9c477}input::placeholder{color:#657168}label{display:block;color:#b7c0b7;font-size:12px;font-weight:500}label>input,label>.select-wrap,label>.unit-input,label>.password-field{margin-top:8px}select{appearance:none;padding-right:30px}.select-wrap{position:relative}.select-wrap>svg{position:absolute;right:12px;top:50%;transform:translateY(-50%);pointer-events:none;color:#97a28e}.primary{display:flex;align-items:center;justify-content:center;gap:10px;background:var(--lime);color:#222b18;border:1px solid var(--lime);border-radius:6px;padding:12px 18px;font-weight:650;min-height:42px}.primary:hover:not(:disabled){background:#e2ffa0}.icon-button{display:inline-flex;align-items:center;justify-content:center;border-radius:5px;width:29px;height:29px;color:#9ba69b;flex-shrink:0}.icon-button:hover:not(:disabled),.icon-button.active{background:#333d32;color:var(--lime)}.brand{display:flex;align-items:center;gap:12px;font-size:27px;font-weight:750;letter-spacing:2.5px;color:#f1f4e9}.brand svg{width:37px;height:37px;fill:none;stroke:var(--lime);stroke-width:1.6}.brand-dot{color:var(--lime)}.brand.small{font-size:21px;gap:9px;letter-spacing:1.7px}.brand.small svg{width:29px;height:29px}.eyebrow{font-size:10px;letter-spacing:1.8px;color:#bbcc9f;display:flex;align-items:center;gap:8px}.status-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--lime);flex-shrink:0}.status-dot.muted{background:#74836e}.spin,.spinner{animation:spin 1s linear infinite}.spinner{width:18px;height:18px;display:inline-block;border:2px solid #6f7c62;border-top-color:var(--lime);border-radius:50%}@keyframes spin{to{transform:rotate(360deg)}}
/* Entry / architecture plate */
.login-page{min-height:100vh;display:grid;grid-template-columns:47% 53%;background:#151916}.login-form-side{padding:36px 48px 25px;display:flex;flex-direction:column;min-height:100vh}.login-form-wrap{max-width:358px;width:100%;margin:auto;padding:54px 0 35px}.login-form-wrap h1{font-size:44px;line-height:1.14;letter-spacing:-2px;font-weight:500;margin:22px 0 18px}.login-form-wrap h1 em{font-style:normal;color:var(--lime)}.login-subtitle{color:#919d91;line-height:1.8;font-size:13px;margin-bottom:29px}.auth-tabs{display:flex;border-bottom:1px solid #333d32;margin-bottom:23px}.auth-tabs button{flex:1;padding:12px 0;color:#7c897d;font-size:12px;border-bottom:2px solid transparent}.auth-tabs button.active{color:#e1e9d6;border-color:var(--lime)}.login-form-wrap form{display:flex;flex-direction:column;gap:18px}.password-field{position:relative}.password-field input{padding-right:42px}.password-field button{position:absolute;right:7px;top:6px}.auth-submit{margin-top:4px;justify-content:space-between;padding-left:17px}.or{display:flex;align-items:center;gap:14px;color:#6e7b6e;font-size:10px;margin:22px 0}.or span{height:1px;background:#30392f;flex:1}.demo-login{border:1px solid #3c4739;display:flex;align-items:center;justify-content:center;gap:12px;border-radius:5px;width:100%;padding:11px;color:#bcc6b6}.demo-login:hover{background:#252e22}.auth-note{font-size:10px;line-height:1.7;color:#73806f;text-align:center;margin-top:20px}.login-form-side footer{font-size:8px;letter-spacing:1.1px;color:#75806f;display:flex;justify-content:space-between;gap:12px}.login-art{padding:34px 38px 24px;background:radial-gradient(ellipse at 50% 55%,#35432b 0,#283323 47%,#253020 100%);display:flex;flex-direction:column;min-height:100vh;overflow:hidden;position:relative;border-left:1px solid #455139}.login-art:before{content:'';position:absolute;inset:0;background-image:linear-gradient(#8aab5b09 1px,transparent 1px),linear-gradient(90deg,#8aab5b09 1px,transparent 1px);background-size:48px 48px;pointer-events:none}.art-top,.art-bottom{display:flex;justify-content:space-between;gap:16px;color:#9aaa89;font-family:monospace;font-size:9px;letter-spacing:1.3px;position:relative}.art-title{font-size:39px;line-height:1.2;letter-spacing:-1.6px;margin-top:66px;font-weight:350;position:relative}.art-title span{color:#bcd491}.architecture-drawing{width:115%;max-height:510px;align-self:center;margin:20px 0 12px;flex:1;position:relative;min-height:260px}.art-feature-row{display:flex;justify-content:space-between;gap:12px;align-items:center;position:relative;margin:12px 0 51px}.art-feature-row>div{display:flex;flex-direction:column;gap:12px;color:#c4d2b1;font-size:10px}.art-feature-row svg{color:#c5e89a}.art-feature-row i{height:1px;background:#596c47;flex:1;max-width:35px}.art-bottom{border-top:1px solid #4a593d;padding-top:21px;font-size:8px}
/* Studio */
.topbar{height:68px;border-bottom:1px solid var(--line);display:flex;align-items:center;padding:0 25px;gap:23px;background:#171b18}.topbar-divider{height:24px;width:1px;background:#384134}.workspace-name{display:flex;align-items:center;gap:18px;color:#9ba595;font-size:11px}.topbar-end{margin-left:auto;display:flex;align-items:center;gap:18px}.local-chip{border:1px solid #35432d;background:#263020;color:#afbf99;display:flex;align-items:center;gap:7px;border-radius:5px;font-size:8px;letter-spacing:1px;padding:7px 10px}.local-chip .status-dot{width:5px;height:5px}.avatar{display:flex;align-items:center;justify-content:center;width:30px;height:30px;background:#3e4934;border:1px solid #647254;color:#d7e5c5;border-radius:50%;font-size:10px}.app-body{display:grid;grid-template-columns:278px minmax(0,1fr);min-height:calc(100vh - 68px)}.sidebar{border-right:1px solid var(--line);background:#191e1a;display:flex;flex-direction:column}.sidebar-title{display:flex;align-items:center;gap:10px;padding:25px 20px 22px}.sidebar-square{background:#303b28;border:1px solid #465239;width:34px;height:34px;border-radius:8px;display:grid;place-items:center;color:#c7dda4}.sidebar-title strong{font-size:12px;font-weight:600;display:block}.sidebar-title div>span{font-size:7px;letter-spacing:1px;color:#8f9b86;display:block;margin-top:5px}.version{font-size:7px;letter-spacing:1px;border:1px solid #3c4635;color:#93a37c;padding:3px 5px;border-radius:3px;margin-left:auto}.sidebar-content{padding:0 20px}.section-label{display:flex;align-items:center;justify-content:space-between;font-size:8px;color:#9ba68e;letter-spacing:1px;font-weight:600;margin-bottom:13px}.section-label>span+span{color:#5f6d5c;font-size:7px;letter-spacing:.5px}.dropzone{display:flex;flex-direction:column;align-items:center;text-align:center;width:100%;border:1px dashed #4c5b3e;background:#222a1e;border-radius:7px;min-height:198px;padding:19px 8px;color:#c2ccb8}.dropzone:hover,.dropzone.dragging{border-color:var(--lime);background:#2e3926}.upload-icon{display:grid;place-items:center;width:41px;height:41px;border:1px solid #47583a;background:#2d3925;border-radius:10px;margin-bottom:13px;color:#b8d08d}.dropzone strong{font-weight:500;font-size:12px;line-height:1.5}.dropzone>span:not(.upload-icon){font-size:9px;color:#7f9074;margin-top:9px}.dropzone u{color:#bed990;text-underline-offset:3px}.dropzone small{font-size:7px;letter-spacing:.5px;color:#66795b;margin-top:17px}.example-button{display:flex;align-items:center;gap:6px;font-size:8.5px;color:#9cae86;width:100%;padding:11px 0}.example-button>span{margin-left:auto}.example-button:hover{color:var(--lime)}.selected-file{border:1px solid #435238;border-radius:6px;padding:12px 8px;display:flex;align-items:center;gap:8px;background:#242e20}.selected-file>div:nth-child(2){min-width:0;flex:1}.selected-file strong{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:10px}.selected-file small{display:block;color:#849677;font-size:6.5px;margin-top:7px;letter-spacing:.3px}.file-icon{color:#b7ce91}.sidebar-separator{height:1px;background:#30392e;margin:13px 0 22px}.material-fields{padding:0;border:0;margin:0;min-width:0}.material-fields>label,.material-fields>.field-row{margin-bottom:16px}.material-fields label{font-size:10px;color:#a6b299}.material-fields input,.material-fields select{font-size:10px;background:#22291f;min-height:37px;padding:9px 10px;border-color:#35412f}.field-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}.unit-input{position:relative}.unit-input input{padding-right:29px}.unit-input span{position:absolute;right:10px;top:50%;transform:translateY(-50%);font-size:9px;color:#718268;pointer-events:none}.field-help{font-size:8px;color:#798a6e;margin:-6px 0 20px}.advanced-toggle{display:flex;align-items:center;justify-content:space-between;width:100%;padding:0 0 13px;color:#a8b593;font-size:10px}.rotated{transform:rotate(180deg)}.advanced-fields{border-top:1px solid #35422f;padding-top:15px}.checkbox-label{display:flex;align-items:center;gap:8px;margin-top:14px}.checkbox-label input{width:13px;min-height:13px;height:13px;accent-color:var(--lime);margin:0}.material-note{display:flex;align-items:center;gap:9px;background:#242d20;border:1px solid #313d2a;border-radius:5px;padding:12px;margin:18px 0;color:#8eaa73}.material-note span{font-size:8px;line-height:1.6}.material-note svg{flex-shrink:0}.sidebar-bottom{margin-top:auto;padding:18px 20px 20px;border-top:1px solid #303b29}.generate{width:100%;justify-content:space-between;font-size:11px;padding:12px}.sidebar-bottom>span{display:block;text-align:center;font-size:7px;color:#718365;margin-top:12px}.workspace{min-width:0;padding:30px 30px 16px;max-width:2000px;width:100%;margin:0 auto}.workspace-heading{display:flex;align-items:center;justify-content:space-between;gap:15px;margin-bottom:27px}.breadcrumb{font-size:7px;letter-spacing:1.5px;color:#818e7a;margin-bottom:13px}.breadcrumb span{padding:0 9px;color:#4e5b46}.workspace-heading h1{font-size:27px;line-height:1.2;letter-spacing:-.9px;font-weight:500;margin:0 0 8px}.workspace-heading h1>span{color:var(--lime)}.workspace-heading p{font-size:10px;color:#83917b;margin:0}.quiet-button{display:flex;align-items:center;gap:9px;border:1px solid #35422e;border-radius:5px;padding:8px 11px;font-size:9px;color:#aab99b}.quiet-button:hover{background:#25301f}.project-bar{display:flex;align-items:center;justify-content:space-between;padding:14px 0 17px;border-top:1px solid #293324;gap:16px}.project-name{display:flex;align-items:center;gap:11px;min-width:0}.project-icon{display:grid;place-items:center;width:34px;height:34px;border:1px solid #38472d;border-radius:5px;background:#222d1c;color:#a7bc8d;flex-shrink:0}.project-name>div{min-width:0}.project-name strong{font-size:11px;display:block;font-weight:500;max-width:260px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.project-name div>span{display:block;font-size:8px;color:#7e8e72;margin-top:5px}.step-indicators{display:flex;align-items:center;gap:9px;color:#57684b;font-size:8px}.step-indicators>span{display:flex;align-items:center;gap:6px}.step-indicators b{font-size:8px;font-weight:400}.step-indicators i{width:21px;height:1px;background:#344329}.step-indicators .done{color:#a8c37e}.step-indicators .current{color:#d2edac}.viewers{display:grid;grid-template-columns:1fr 1fr;gap:15px}.viewer-panel{border:1px solid #343d31;border-radius:8px;background:#1a2119;overflow:hidden;min-width:0}.panel-heading{height:46px;display:flex;align-items:center;justify-content:space-between;padding:0 13px;border-bottom:1px solid #313d2b;background:#1c241a;gap:5px}.panel-heading>div:first-child{display:flex;align-items:center;gap:8px;color:#97aa86;min-width:0}.panel-heading h2{font-size:10px;font-weight:500;color:#d4ddcc;white-space:nowrap}.badge{font-size:6px;letter-spacing:.6px;color:#809573;border:1px solid #3b4b31;padding:3px 5px;border-radius:3px;margin-left:4px}.panel-actions{display:flex;gap:1px}.panel-actions .icon-button{width:25px;height:26px}.model-canvas,.sheet-canvas{height:370px;position:relative;overflow:hidden;background:#1b201e}.model-canvas>div:not(.canvas-busy):not(.viewport-hint){height:100%}.viewport-label{position:absolute;z-index:1;top:14px;left:14px;font-size:6px;letter-spacing:1.1px;color:#8b9b82;pointer-events:none}.viewport-label span{padding:0 6px;color:#53654a}.viewport-hint{position:absolute;bottom:12px;left:13px;right:13px;font-size:6px;color:#829678;pointer-events:none}.viewport-hint b{font-weight:400;margin:0 5px}.canvas-busy{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;gap:12px;background:#171e15b0;backdrop-filter:blur(3px);font-size:12px;z-index:3}.panel-footer{display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:36px;border-top:1px solid #313d2b;padding:3px 11px;font-family:monospace;font-size:7px;color:#8a9b7e;background:#1c241a}.panel-footer>span:first-child{display:flex;align-items:center;gap:7px;max-width:53%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.panel-footer>span:last-child{text-align:right}.panel-footer .status-dot{width:4px;height:4px}.sheet-canvas{background:#171d17;padding:32px 16px 33px;display:flex;align-items:center;justify-content:center}.sheet-canvas>svg{width:100%;height:100%;touch-action:none;user-select:none;overflow:hidden}.sheet-ruler{position:absolute;display:flex;align-items:center;justify-content:space-between;top:0;left:0;right:0;height:23px;background:#1c251a;border-bottom:1px solid #2e3b27;color:#617454;font-size:6px;font-family:monospace;padding:0 17px}.sheet-legend{position:absolute;bottom:13px;left:16px;right:16px;display:flex;align-items:center;gap:14px;font-size:6px;color:#859d75}.sheet-legend>span{display:flex;align-items:center;gap:5px}.sheet-legend>span:last-child{margin-left:auto;color:#b1c39f}.sheet-legend i{width:9px;height:2px;display:inline-block}.cut{background:#becd99}.engrave{background:#eaf3db}.sheet-piece{cursor:pointer;outline:none}.sheet-piece:hover>path,.sheet-piece:focus>path{stroke:#e3ff9a;stroke-width:1.4}.pan-mode .sheet-piece,.pan-mode{cursor:grab}.pan-mode:active{cursor:grabbing}.sheet-pagination{display:flex;align-items:center;gap:3px;white-space:nowrap}.sheet-pagination b{font-weight:400;color:#647956}.sheet-pagination button{width:18px;height:22px}.empty-sheet{text-align:center;border:1px solid #415136;background:linear-gradient(145deg,#283422,#202b1b);width:100%;max-width:390px;aspect-ratio:1.5;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:15px;position:relative}.empty-sheet h3{font-size:13px;font-weight:450;color:#a9bd96;margin:13px 0 7px}.empty-sheet p{font-size:9px;line-height:1.7;color:#738866;margin:0}.empty-dim{font-family:monospace;font-size:7px;letter-spacing:2px;color:#617754;position:absolute;bottom:13px}.empty-sheet-drawing{display:grid;grid-template-columns:24px 34px;grid-template-rows:20px 14px;gap:4px;transform:rotate(-8deg);opacity:.6}.empty-sheet-drawing span{border:1px solid #91a977;background:#52694122}.empty-sheet-drawing span:nth-child(2){border-radius:0 12px 0 0}.empty-sheet-drawing span:last-child{clip-path:polygon(0 0,100% 0,70% 100%,0 100%)}.empty-state{width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;padding:25px;text-align:center;color:#96aa89}.empty-state h3{font-size:14px}.empty-state p{font-size:10px;line-height:1.8}.results-row{display:grid;grid-template-columns:1fr 1fr 1.2fr;margin:17px 0;border:1px solid #303d29;background:#192117;border-radius:7px}.metric{display:flex;align-items:center;gap:12px;padding:17px 18px}.metric+.metric{border-left:1px solid #303d29}.metric-icon{width:36px;height:36px;border-radius:7px;background:#273320;display:grid;place-items:center;color:#8ca976;flex-shrink:0}.metric-icon.lime{background:#303f21;color:#c6e69b}.metric>div>span{font-size:8px;color:#899c79;display:block;margin-bottom:6px}.metric strong{font-size:22px;line-height:1;font-weight:500;letter-spacing:-.5px;white-space:nowrap}.metric small{font-size:7px;font-weight:400;margin-left:9px;color:#6d845b;letter-spacing:0}.lime-text{color:#cfe99b}.progress-ring{width:38px;height:38px;margin-left:auto;flex-shrink:0;transform:rotate(-90deg)}.progress-ring circle{fill:none;stroke:#33472a;stroke-width:3}.progress-ring circle+circle{stroke:#bedc8f;stroke-linecap:round}.export-bar{border:1px solid #3f5032;border-radius:7px;background:linear-gradient(100deg,#222e1c,#192315);padding:19px;display:flex;align-items:center;justify-content:space-between;gap:12px}.export-label{display:flex;gap:12px;align-items:center}.export-icon{width:37px;height:40px;display:grid;place-items:center;border:1px solid #526740;border-radius:5px;color:#c6dda5;background:#2c3d20;flex-shrink:0}.export-label h2{font-weight:500;font-size:12px;margin:0 0 7px}.export-label p{color:#8ca378;font-size:8px;line-height:1.5;margin:0}.export-actions{display:flex;align-items:center;gap:9px}.export-actions select{font-size:10px;min-width:126px;background:#222e1b;border-color:#4a5e38;height:39px;min-height:39px}.export-actions .primary{font-size:10px;padding:10px 14px;min-height:39px}.workspace-footer{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:25px 1px 0;color:#596e4b;letter-spacing:.8px;font-size:6px}.workspace-footer>span:first-child{display:flex;align-items:center;gap:7px}.workspace-footer b{font-weight:400;padding:0 4px}.alert{display:flex;align-items:center;gap:10px;padding:12px 14px;margin-bottom:15px;border-radius:6px;font-size:11px;line-height:1.5}.alert>svg{flex-shrink:0}.alert>span{flex:1}.alert.error{background:#3e2925;border:1px solid #715044;color:#ebc0ad}.alert.warning{background:#383322;border:1px solid #655b37;color:#d4c593}.selection-info{display:flex;align-items:center;gap:15px;margin:-4px 0 12px;padding:8px 12px;border:1px solid #3b4e2c;border-radius:5px;color:#a3bc8b;font-size:9px}.selection-info button{margin-left:auto}.processing-notes{border:1px solid #36442d;border-radius:5px;background:#1b2417;margin-top:13px;color:#93a97e}.processing-notes summary{display:flex;align-items:center;gap:8px;font-size:9px;cursor:pointer;padding:10px 13px;list-style:none}.processing-notes summary>svg:last-child{margin-left:auto}.processing-notes summary>span{padding:2px 5px;background:#344529;border-radius:3px;font-size:8px}.processing-notes ul{margin:0;padding:0 28px 13px;font-size:9px;line-height:1.8;list-style:disc}.processing-notes li+li{margin-top:5px}.help-dialog{border:1px solid #4b5c3d;border-radius:12px;background:#1c2518;color:#c5d4b7;padding:28px;max-width:580px;width:calc(100% - 36px);max-height:85vh;margin:auto;box-shadow:0 30px 100px #0008}.help-dialog::backdrop{background:#071006b8;backdrop-filter:blur(5px)}.dialog-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:30px}.help-dialog h2{font-size:26px;font-weight:450;letter-spacing:-1px;margin:13px 0 20px}.help-dialog ol{list-style:decimal;padding-left:20px;font-size:12px;line-height:1.8;color:#a0b68d}.help-dialog li+li{margin-top:13px}.help-dialog strong{color:#d3e6ba}.help-note{padding:13px;background:#2a3721;border:1px solid #405331;border-radius:5px;font-size:10px;line-height:1.8;margin:20px 0;color:#9eb788}.help-dialog>.primary{width:100%;justify-content:space-between}
@media(min-width:1600px){.model-canvas,.sheet-canvas{height:460px}.workspace{padding:38px 38px 20px}.app-body{grid-template-columns:294px minmax(0,1fr)}.panel-heading h2{font-size:12px}.panel-footer{font-size:8px}.workspace-heading h1{font-size:32px}.metric small{font-size:9px}.export-label h2{font-size:14px}.export-label p{font-size:10px}.export-actions .primary,.export-actions select{font-size:12px}.sidebar-content{padding:0 24px}}
@media(max-width:1180px){.workspace{padding:25px 20px 16px}.app-body{grid-template-columns:255px minmax(0,1fr)}.sidebar-content{padding:0 16px}.sidebar-title{padding:24px 16px}.sidebar-bottom{padding:18px 16px}.metric{padding:14px 12px;gap:8px}.metric small{display:block;margin:5px 0 0;font-size:6px}.metric strong{font-size:20px}.metric-icon{width:29px;height:29px}.progress-ring{width:31px;height:31px}.model-canvas,.sheet-canvas{height:315px}.panel-heading{padding:0 8px}.panel-heading .badge{display:none}.panel-footer{font-size:6px}.export-bar{padding:14px}.export-icon{display:none}.export-label h2{font-size:10px}.export-label p{font-size:7px;max-width:200px}.export-actions{gap:5px}.export-actions select{min-width:114px}.step-indicators{gap:6px}.step-indicators i{width:10px}.workspace-heading h1{font-size:24px}.login-form-side{padding:30px}.art-title{font-size:32px}.login-art{padding:30px}.login-form-wrap h1{font-size:40px}.art-top{font-size:7px}}
@media(max-width:980px){.viewers{grid-template-columns:1fr}.model-canvas,.sheet-canvas{height:310px}.panel-heading h2{font-size:11px}.panel-heading .badge{display:inline}.panel-footer{font-size:8px}.export-bar{align-items:flex-start;flex-direction:column;gap:15px}.export-actions{width:100%}.export-actions .select-wrap{flex:1}.export-actions .primary{flex:1}.export-label p{max-width:none}.export-label h2{font-size:13px}.export-label p{font-size:9px}.step-indicators b{display:none}.quiet-button{font-size:0;gap:0;padding:8px}.project-name strong{max-width:210px}.results-row{grid-template-columns:1fr 1fr 1fr}.metric{flex-direction:column;align-items:flex-start;padding:13px}.metric small{font-size:7px}.metric>div>span{font-size:7px}.progress-ring{display:none}.login-form-side{padding:27px}.login-form-wrap{max-width:310px}.login-form-wrap h1{font-size:35px}.login-art{padding:27px}.art-feature-row{gap:6px}.art-feature-row>div{font-size:8px}.art-feature-row i{max-width:18px}.art-title{font-size:29px}.art-top>span:last-child{display:none}.art-bottom{font-size:6px}}
@media(max-width:680px){.login-page{grid-template-columns:1fr}.login-art{display:none}.login-form-side{padding:26px;min-height:100dvh}.login-form-wrap{padding:40px 0;max-width:370px}.login-form-wrap h1{font-size:41px}.topbar{padding:0 15px;gap:12px;height:60px}.topbar-divider,.workspace-name,.local-chip,.help-button{display:none}.topbar-end{gap:12px}.app-body{display:flex;flex-direction:column}.sidebar{border-right:0;border-bottom:1px solid var(--line)}.sidebar-title{padding:18px 18px 15px}.sidebar-content{display:grid;grid-template-columns:1fr 1fr;gap:18px;padding:0 18px}.sidebar-separator,.material-note{display:none}.sidebar-bottom{padding:14px 18px;display:flex;align-items:center;gap:16px;margin-top:15px}.sidebar-bottom .primary{max-width:220px}.sidebar-bottom>span{text-align:left;font-size:8px;line-height:1.7;margin-top:0}.dropzone{min-height:200px}.example-button{font-size:7px;white-space:normal;text-align:left}.section-label{font-size:7px;letter-spacing:.5px}.section-label>span+span{display:none}.material-fields label{font-size:9px}.material-fields input,.material-fields select{font-size:9px;padding:8px}.material-fields>label,.material-fields>.field-row{margin-bottom:12px}.field-row{gap:6px}.unit-input span{font-size:7px;right:7px}.unit-input input{padding-right:23px}.field-help{font-size:7px}.field-help{margin-bottom:13px}.advanced-toggle{font-size:9px}.checkbox-label{font-size:8px!important}.workspace{padding:23px 16px 18px}.workspace-heading{margin-bottom:23px}.workspace-heading h1{font-size:26px}.workspace-heading p{font-size:9px}.breadcrumb{font-size:6px}.model-canvas,.sheet-canvas{height:320px}.viewers{gap:15px}.results-row{margin:15px 0}.metric>div>span{font-size:7px;line-height:1.5}.metric small{font-size:6px}.metric strong{font-size:23px}.metric{padding:12px 9px}.metric-icon{width:28px;height:28px}.workspace-footer{font-size:5px;letter-spacing:.3px}.workspace-footer>span:first-child{gap:4px}.project-bar{gap:7px}.project-name strong{max-width:210px}.processing-notes ul{font-size:9px}.topbar .brand{font-size:20px}.selected-file{flex-wrap:wrap}.selected-file>div:nth-child(2){min-width:75px}.selected-file .icon-button{margin-left:auto}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}.spin,.spinner{animation-duration:2s}}

```

## frontend/src/tests/App.test.tsx

```tsx
import {describe,it,expect,vi,beforeEach} from 'vitest'
import {render,screen,waitFor,fireEvent} from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../App'
import {defaults} from '../types'
import type {Job} from '../types'
const {processModel,downloadJob}=vi.hoisted(()=>({processModel:vi.fn(),downloadJob:vi.fn()}))
vi.mock('../api',()=>({processModel,downloadJob}))
vi.mock('../components/ModelViewer',()=>({ModelViewer:()=> <div>Visor 3D de prueba</div>}))
const job:Job={id:'test',filename:'panel.obj',settings:{...defaults},sheets:[{index:0,utilization:10,pieces:[{id:'P001',rings:[[[5,5],[105,5],[105,105],[5,105],[5,5]]],label:[55,55],area:10000,angle:0}]}],preview:{vertices:[0,0,0,1,0,0,0,1,0],faces:[0,1,2],bounds:[1,1,0]},warnings:['Panel plano de prueba'],piece_count:1,utilization:10,area_mm2:10000}
beforeEach(()=>{vi.clearAllMocks();processModel.mockResolvedValue(job);downloadJob.mockResolvedValue(undefined)})
async function enter(){const user=userEvent.setup();render(<App/>);await user.click(screen.getByRole('button',{name:/Acceder a la demo/}));return user}
async function uploadAndProcess(user:ReturnType<typeof userEvent.setup>){const input=document.querySelector('input[type=file]') as HTMLInputElement;await user.upload(input,new File(['v 0 0 0'],'panel.obj'));await user.click(screen.getByRole('button',{name:/Generar despiece/}));await waitFor(()=>expect(screen.getByRole('button',{name:'Descargar'})).toBeEnabled())}
describe('flujo local del estudio',()=>{
  it('permite acceso demo y salida sin almacenar contraseña',async()=>{const user=await enter();expect(screen.getByText('Del modelo a la materia',{exact:false})).toBeInTheDocument();expect(sessionStorage.getItem('planar-demo-user')).not.toContain('password');await user.click(screen.getByRole('button',{name:'Cerrar sesión'}));expect(screen.getByRole('button',{name:'Iniciar sesión'})).toBeInTheDocument();expect(sessionStorage.getItem('planar-demo-user')).toBeNull()})
  it('simula registro con nombre y correo',async()=>{const user=userEvent.setup();render(<App/>);await user.click(screen.getByRole('button',{name:'Crear cuenta'}));await user.type(screen.getByLabelText('Nombre'),'Ana');await user.type(screen.getByLabelText('Correo electrónico'),'ana@uni.edu');await user.type(screen.getByLabelText('Contraseña'),'demo123');await user.click(screen.getByRole('button',{name:'Crear mi espacio'}));expect(JSON.parse(sessionStorage.getItem('planar-demo-user')!)).toEqual({name:'Ana',email:'ana@uni.edu'})})
  it('procesa, selecciona, exporta y bloquea resultados obsoletos',async()=>{const user=await enter();expect(screen.getByRole('button',{name:'Descargar'})).toBeDisabled();await uploadAndProcess(user);expect(processModel).toHaveBeenCalledWith(expect.any(File),defaults);await user.click(screen.getByRole('button',{name:'Seleccionar pieza P001'}));expect(screen.getByText('Rotación 0°')).toBeInTheDocument();await user.selectOptions(screen.getByLabelText('Formato de salida'),'pdf');await user.click(screen.getByRole('button',{name:'Descargar'}));expect(downloadJob).toHaveBeenCalledWith(job,'pdf');fireEvent.change(screen.getByLabelText('Kerf'),{target:{value:'0.3'}});expect(screen.getByRole('button',{name:'Descargar'})).toBeDisabled();expect(screen.getByRole('status')).toHaveTextContent('Los parámetros cambiaron');await user.click(screen.getByRole('button',{name:'Quitar archivo'}));expect(screen.getByRole('button',{name:'Generar despiece'})).toBeDisabled()})
  it('presenta errores del motor sin habilitar exportación',async()=>{processModel.mockRejectedValue(new Error('P001 no cabe en la lámina.'));const user=await enter();await user.upload(document.querySelector('input[type=file]') as HTMLInputElement,new File(['bad'],'panel.obj'));await user.click(screen.getByRole('button',{name:'Generar despiece'}));expect(await screen.findByRole('alert')).toHaveTextContent('P001 no cabe');expect(screen.getByRole('button',{name:'Descargar'})).toBeDisabled()})
  it('muestra guía y medidas personalizadas',async()=>{const user=await enter();await user.click(screen.getByRole('button',{name:'Guía rápida'}));expect(screen.getByRole('dialog')).toBeVisible();await user.click(screen.getByRole('button',{name:'Cerrar guía'}));await user.selectOptions(screen.getByLabelText('Formato de lámina'),'custom');expect(screen.getByLabelText('Ancho')).toHaveValue(600);expect(screen.getByLabelText('Alto')).toHaveValue(400)})
})

```

## frontend/src/tests/setup.ts

```typescript
import '@testing-library/jest-dom/vitest'
import {afterEach} from 'vitest'
import {cleanup} from '@testing-library/react'
afterEach(()=>{cleanup();sessionStorage.clear()})
HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')}
HTMLDialogElement.prototype.close=function(){this.removeAttribute('open')}

```

## frontend/src/types.ts

```typescript
export type Settings = {width:number;height:number;thickness:number;kerf:number;gap:number;margin:number;units:'mm'|'cm'|'m'|'in';rotate:boolean}
export type Piece = {id:string;rings:[number,number][][];label:[number,number];area:number;angle:number}
export type Sheet = {index:number;pieces:Piece[];utilization:number}
export type Job = {id:string;filename:string;settings:Settings;sheets:Sheet[];preview:{vertices:number[];faces:number[];bounds:number[]};warnings:string[];piece_count:number;utilization:number;area_mm2:number}
export type User = {name:string;email:string}
export const defaults: Settings = {width:600,height:400,thickness:3,kerf:0.15,gap:3,margin:5,units:'mm',rotate:true}

```

## frontend/tsconfig.json

```json
{"compilerOptions":{"target":"ES2022","lib":["ES2022","DOM","DOM.Iterable"],"module":"ESNext","skipLibCheck":true,"moduleResolution":"bundler","allowImportingTsExtensions":true,"resolveJsonModule":true,"isolatedModules":true,"noEmit":true,"jsx":"react-jsx","strict":true,"types":["vite/client"]},"include":["src","vite.config.ts"]}

```

## frontend/vite.config.ts

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {port: 5173, strictPort: true, proxy: {'/api': 'http://127.0.0.1:8000'}},
})

```

## frontend/vitest.config.ts

```typescript
import {defineConfig} from 'vitest/config'
import react from '@vitejs/plugin-react'
export default defineConfig({plugins:[react()],test:{environment:'jsdom',setupFiles:['./src/tests/setup.ts'],restoreMocks:true}})

```

## scripts/backend.cmd

```batch
@echo off
cd /d "%~dp0..\backend"
".venv\Scripts\python.exe" -m uvicorn main:app --host 127.0.0.1 --port 8000
if errorlevel 1 pause

```

## scripts/esperar-y-abrir.ps1

```powershell
$ErrorActionPreference = 'Stop'
Write-Host 'Esperando a que ambos servidores esten listos...'
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    try {
        $api = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/api/health' -TimeoutSec 2
        $web = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5173' -TimeoutSec 2
        $health = $api.Content | ConvertFrom-Json
        if ($api.StatusCode -eq 200 -and $health.status -eq 'ok' -and $web.StatusCode -eq 200 -and $web.Content -match 'PLANAR') {
            Start-Process 'http://127.0.0.1:5173'
            exit 0
        }
    } catch {
        # Startup is asynchronous; retry until both servers answer.
    }
    Start-Sleep -Seconds 1
}
Write-Host 'No respondieron ambos servidores. Revisa sus ventanas para ver el error.'
exit 1

```

## scripts/frontend.cmd

```batch
@echo off
cd /d "%~dp0..\frontend"
call npm run dev -- --host 127.0.0.1
if errorlevel 1 pause

```
