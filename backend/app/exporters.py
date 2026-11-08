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
