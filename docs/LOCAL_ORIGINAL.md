# PLANAR — Estudio local de despiece y fabricación

Primera versión funcional de una aplicación de arquitectura: carga un archivo,
separa paneles planos, compensa el kerf, acomoda las piezas y exporta para corte.
Interfaz en español, acceso demo, React + Vite + TypeScript + Tailwind,
visor Three.js/React Three Fiber/Drei y API Python/FastAPI.

**Ejecución local. No utiliza base de datos, cuentas reales ni servicios de pago.**

## Inicio sencillo en Windows

1. En GitHub, inicia sesión y abre el repositorio privado. Pulsa **Code → Download ZIP**.
2. En Descargas, haz clic derecho en el ZIP y elige **Extraer todo**.
3. Dentro de la carpeta extraída, abre **INICIAR_WINDOWS.cmd** con doble clic.
4. El lanzador instala las dependencias, abre Backend y Frontend y espera a que
   ambos respondan antes de abrir el navegador. Conserva las dos ventanas abiertas.

Necesitas Python 3.12 y Node.js 22.12+ (se recomienda Node.js 24). Si falta alguno,
el lanzador lo indica. No requiere abrir PowerShell como administrador.
No ejecutes el archivo desde la vista interna del ZIP: extráelo primero.
Los scripts de Windows se entregan sin prueba de ejecución en Windows, porque
el entorno de desarrollo es Linux; el backend y frontend tienen sus pruebas propias.

## Requisitos

- Python **3.12** recomendado (versión usada en las pruebas).
- Node.js **22.12 o superior**, o Node 24, con npm.
- Navegador actual con WebGL para el visor 3D.
- Conexión a internet para instalar las dependencias; después no se necesita
  conexión para usar la aplicación. No hay fuentes ni modelos cargados desde CDN.

## Instalación y arranque

Descomprime la carpeta `planar`. Ejecuta cada servidor en una terminal distinta.
Los comandos parten de esa carpeta.

### Terminal 1 — backend, macOS / Linux

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Terminal 1 — backend, Windows PowerShell

No es necesario cambiar la política de ejecución de PowerShell ni activar el entorno:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Terminal 2 — frontend, todos los sistemas

```bash
cd frontend
npm ci
npm run dev
```

Abre **http://localhost:5173**. La API está en **http://127.0.0.1:8000** y
su documentación interactiva en **http://127.0.0.1:8000/docs**.

Pulsa **Acceder a la demo** y después **Probar con un pabellón de ejemplo**.
El ejemplo se envía al motor real y genera cinco paneles. La vista de ejemplo
mostrada antes de procesar es ilustrativa; no representa resultados calculados.

Para terminar, pulsa `Ctrl+C` en ambas terminales. No se publica ningún servicio.

### Versiones reproducibles

`frontend/package-lock.json` fija las dependencias npm. El backend incluye
`requirements-lock.txt`, un snapshot del entorno completo validado (incluye
herramientas de pruebas). Para reproducir exactamente ese entorno:

```bash
python -m pip install -r requirements-lock.txt
```

`requirements.txt` instala solo las dependencias de ejecución con versiones
principales compatibles; la instalación normal no requiere las herramientas de pruebas.

## Estructura

```text
planar/
├── README.md
├── CODIGO_COMPLETO.md              # Copia legible del código en un documento
├── VALIDACION.md
├── .gitignore
├── backend/
│   ├── main.py                    # API, límites, caché y descargas
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── requirements-lock.txt
│   ├── make_examples.py           # Regenera los seis formatos de ejemplo
│   ├── app/
│   │   ├── __init__.py
│   │   ├── models.py              # Parámetros y estructuras internas
│   │   ├── geometry.py            # Importación, paneles, agujeros y kerf
│   │   ├── nesting.py             # MaxRects, giros, márgenes y colisiones
│   │   └── exporters.py           # DXF, SVG, PDF y ZIP multilámina
│   └── tests/
│       └── test_pipeline.py
├── frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── index.html
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── vitest.config.ts
│   ├── .env.example
│   ├── public/
│   │   ├── favicon.svg
│   │   └── demo-pabellon.obj
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                # Estado del proyecto, procesamiento y exportación
│       ├── api.ts
│       ├── types.ts
│       ├── styles.css
│       ├── components/
│       │   ├── Brand.tsx
│       │   ├── Login.tsx
│       │   ├── Uploader.tsx
│       │   ├── MaterialPanel.tsx
│       │   ├── ModelViewer.tsx
│       │   └── SheetViewer.tsx
│       └── tests/
│           ├── setup.ts
│           └── App.test.tsx
└── examples/
    ├── pabellon.stl
    ├── pabellon.obj
    ├── pabellon.ply
    ├── pabellon.off
    ├── pabellon.3dm
    └── fachadas-con-huecos.dxf
```

## Flujo de trabajo

1. **Entra al estudio.** El login/registro es una simulación. El nombre y correo
   se conservan en `sessionStorage`; la contraseña no se guarda ni se envía.
2. **Sube el archivo.** Arrástralo a la zona de carga o selecciónalo en el diálogo.
3. **Indica las unidades del archivo.** Se aplican siempre las unidades elegidas,
   incluidas las de archivos con metadatos. No hay escalado automático a la lámina.
   Si tu maqueta es 1:100, prepara el modelo a esa escala antes de importarlo.
4. **Configura el material.** Láminas 600×400, 900×600, 1200×900 mm o personalizadas;
   espesor, kerf, separación entre trayectorias, margen y giros de 90°.
5. **Genera el despiece.** Inspecciona el 3D y las láminas; cambia de lámina con las
   flechas. Selecciona una pieza para ver su área y rotación. En la vista 2D,
   los botones +/− controlan el zoom, el icono de mano activa el desplazamiento,
   y «ajustar» restablece la vista. En 3D: arrastre para órbita, rueda para zoom,
   botón derecho para desplazar y el botón de reinicio para encuadrar.
6. **Revisa los avisos y las dimensiones.** Los cambios de parámetros invalidan
   la exportación anterior hasta volver a procesar.
7. **Exporta.** Escoge DXF, SVG o PDF. Si hay varias láminas, DXF/SVG descargan un
   ZIP con un archivo por lámina; el PDF tiene una página por lámina.

## Formatos de entrada y alcance

| Formato | Compatible en esta versión |
| --- | --- |
| STL | Mallas triangulares ASCII/binarias |
| OBJ | Mallas; se aplican transformaciones de escena. No se usan materiales/texturas externos |
| PLY | Mallas; una nube de puntos sin caras no es un panel |
| OFF | Mallas poligonales convertibles a triángulos |
| DXF | Polilíneas cerradas, círculos, elipses/splines compatibles y cadenas de líneas/arcos cerradas, en plano paralelo a XY |
| 3DM | Mesh, PolylineCurve cerradas en XY y Brep con mallas de render guardadas |

En DXF, curvas y arcos se aproximan con segmentos usando tolerancia de **0,03 mm**.
Se preservan agujeros mediante regla par/impar. Perfiles abiertos o
self-intersections producen errores; bloques/INSERT, textos y entidades no
convertibles se omiten con aviso. La capa `GRABADO` original no se importa:
esta versión crea sus propios identificadores. Un DXF solo de anotaciones no es válido.

`rhino3dm` lee 3DM pero **no es un motor general de mallado NURBS**. Para extrusiones,
superficies sin malla guardada o bloques, utiliza `Mesh` en Rhino y exporta las
mallas a 3DM o STL. Si una parte se omite, aparece identificada en los avisos;
no se declara un soporte general a superficies Rhino no malladas.

## Qué hace el motor

- Trabaja internamente en **milímetros**.
- Trimesh limpia triángulos degenerados/duplicados y agrupa triángulos conectados
  que pertenecen al mismo plano, tolerancia angular aproximada de 0,0008°.
  Proyecta cada grupo sobre una base local 2D y une los triángulos con Shapely.
- Conserva agujeros y paneles independientes. Rechaza aristas no manifold con
  más de dos caras y avisa sobre mallas abiertas o normales inconsistentes.
- Alinea cada panel con su caja de área mínima antes del acomodo; la orientación
  original del dibujo no se conserva. Los giros de 90° son adicionales a esa
  alineación. Esta V1 no modela dirección de veta.
- Pyclipper aplica **kerf/2** hacia fuera del perímetro y hacia dentro de los agujeros,
  con coordenadas enteras a escala 100 000. Si el kerf elimina un agujero, se rechaza
  la operación. **No apliques otra compensación en el controlador láser.**
- Acomodo **MaxRects** determinista de cajas envolventes, ordenadas por lado mayor,
  con giros 0/90°, margen y separación. Abre láminas adicionales cuando hace falta.
  Después verifica límites y distancia entre polígonos con Shapely.
- Aprovechamiento = suma de áreas nominales de los paneles (sin agujeros) dividida
  entre el área total de las láminas utilizadas. No cuenta el área de kerf.

El nesting es **heurístico y conservador**: no garantiza el óptimo global,
no encaja concavidades ni utiliza agujeros para alojar otras piezas.

El despiece genera **caras independientes**, no un desarrollo conectado con
bisagras. Las superficies curvas de mallas quedan facetadas; no hay aplanado
continuo de superficies curvas ni compensación de deformación. **El espesor es
metadato de material**, no genera encastres, biseles, uniones o ajustes de espesor.

## Exportaciones

- **DXF R2010**: `$INSUNITS=4` (mm), polilíneas cerradas en `CORTE` (ACI 1, rojo),
  identificadores TEXT en `GRABADO` (ACI 5, azul). No se exporta el borde de lámina
  como trayectoria de corte.
- **SVG**: ancho/alto físicos en mm, `viewBox` en mm, grupos `CORTE` rojo y
  `GRABADO` azul. Los agujeros son trayectorias independientes. La numeración
  sigue siendo texto: conviértela a curvas si tu controlador lo requiere.
- **PDF vectorial**: tamaño físico exacto de lámina; cortes rojos y texto azul,
  una página por lámina y sin rasterizar. **Imprimir al 100% / tamaño real**,
  desactivando «ajustar a página». La impresora debe admitir el tamaño seleccionado.

Revisa siempre dimensiones, identificadores, detalles finos y parámetros de
potencia/velocidad en el software de tu máquina antes de cortar.

## API

### Salud

`GET /api/health`

### Procesamiento

`POST /api/process`, `multipart/form-data`:

- `file`: archivo original.
- `settings`: JSON serializado, por ejemplo:

```json
{"width":600,"height":400,"thickness":3,"kerf":0.15,"gap":3,"margin":5,"units":"mm","rotate":true}
```

```bash
curl -X POST http://127.0.0.1:8000/api/process \
  -F 'file=@examples/pabellon.obj' \
  -F 'settings={"width":600,"height":400,"thickness":3,"kerf":0.15,"gap":3,"margin":5,"units":"mm","rotate":true}'
```

La respuesta incluye `id`, parámetros, piezas por lámina con anillos y etiquetas,
uso de material, preview de vértices/caras, advertencias y tiempo de expiración.

### Exportación

`GET /api/jobs/{id}/export/dxf` (también `svg` o `pdf`).

Límites: archivo de 20 MB, 40 000 triángulos, 250 paneles, 2000 contornos,
una operación de geometría simultánea y 20 resultados recientes. Los resultados
expiran después de una hora y se pierden al reiniciar el servidor. No hay archivos
subidos guardados permanentemente; la lectura DXF/3DM usa directorios temporales.
No ejecutar con varios workers: la caché es memoria local del proceso.

## Pruebas

Backend, con el entorno virtual activado:

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

En Windows, usa `.\.venv\Scripts\python.exe` en lugar de `python` si no activaste
el entorno. Frontend:

```bash
cd frontend
npm test
npm run build
```

El build queda en `frontend/dist`. Para previsualizar el build con la API, crea
`frontend/.env.local` con `VITE_API_URL=http://127.0.0.1:8000`, recompila y ejecuta
`npm run preview -- --port 5173`. Mantén FastAPI activo. El proxy `/api` es para
desarrollo; no se incluye dentro de los archivos estáticos del build.

## Problemas frecuentes

- **No conecta con backend**: comprueba que FastAPI está en 127.0.0.1:8000 y que
  ambas terminales siguen abiertas. Para desarrollo usa `npm run dev`.
- **Puerto 5173 ocupado**: detén el proceso previo. Vite usa `strictPort` para
  evitar cambiar silenciosamente a un origen no permitido por CORS.
- **Pieza demasiado grande**: revisa unidades; no se escala el modelo para hacerlo caber.
- **Muchos triángulos/paneles**: reduce la complejidad y convierte superficies a
  paneles planos en el CAD antes de importarlas.
- **Modelo sin visor**: habilita aceleración gráfica/WebGL. La vista 2D y las
  exportaciones pueden seguir utilizándose sin WebGL.
- **Descarga expirada**: procesa de nuevo. El resultado permanece una hora como máximo.
- **3DM sin objetos compatibles**: genera y guarda mallas en Rhino.

La autenticación es exclusivamente demo. El servidor se configura para localhost;
no está preparado para exposición pública. No hay OAuth, multiusuario, base de
datos, historial persistente ni cola de trabajos en esta primera versión.
