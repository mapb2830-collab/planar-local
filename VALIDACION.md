# Validación de la V1

- Python 3.12.14, Node 24.22.1.
- `python -m pytest -q`: **16 pruebas aprobadas**.
- `npm test`: **5 pruebas de interfaz aprobadas** (Vitest, jsdom).
- `npm run build`: TypeScript y build de Vite correctos.
- Se procesaron los seis archivos de `examples/`: STL, OBJ, PLY, OFF y 3DM
  producen cinco paneles; el DXF produce dos paneles conservando los huecos.
- Verificados: agrupación coplanar, unidades, instancias OBJ, huecos y kerf,
  colisiones, límites de lámina, rotación, exportaciones multilámina, capas y
  colores DXF, XML SVG, páginas PDF a tamaño real sin imágenes rasterizadas,
  entradas inválidas y piezas que no caben.
- Interfaz: acceso demo y registro, cierre de sesión, carga/procesamiento,
  selección de pieza, elección y solicitud de descarga, invalidación del
  resultado al editar parámetros, mensajes de error, guía y medidas custom.
- El visor 3D se sustituye por un mock únicamente en las pruebas de interfaz;
  la aplicación utiliza Three.js / React Three Fiber / Drei reales.

## Límites de la verificación

No se pudo realizar inspección visual en un navegador ni verificar WebGL en
este entorno: no está disponible la herramienta de control de navegador de
la infraestructura de preview. La compilación del visor sí fue verificada.
Prueba órbita, zoom, encuadre y sombras en tu navegador al ejecutar localmente.

El build informa que el chunk del visor 3D supera 500 KB. Se carga bajo demanda,
separado del acceso y del resto de la aplicación. El test client de Starlette
emite un aviso de deprecación de httpx; las peticiones y comprobaciones pasan.
