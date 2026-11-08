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
