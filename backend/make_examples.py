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
