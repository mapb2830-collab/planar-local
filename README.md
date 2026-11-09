# Planar Studio

Estudio de arquitectura para importar modelos, preparar paneles y exportar archivos de corte.
React 19 + Vite + TypeScript, visor Three.js y motor Python/FastAPI.

La versión 0.2 conserva el motor original y añade una interfaz responsive, biblioteca privada,
historial persistente, cuentas Supabase verificadas, roles y administración. **Los pagos reales
están desactivados.** Las simulaciones administrativas nunca conceden créditos pagados ni
permiten consumirlos como saldo real.

## Dos modos explícitos

| Modo | Uso | Identidad y almacenamiento |
|---|---|---|
| Local | `INICIAR_WINDOWS.cmd` o servidores de desarrollo | Demo offline; resultados temporales, sin cuentas reales |
| Cloud | Vercel + servicio Python + Supabase | Sesión verificada, PostgreSQL privado y disco persistente |

El desarrollo usa modo local por defecto. Los builds de producción usan cloud y fallan si
faltan variables o si una URL apunta a loopback. Vercel rechaza explícitamente el modo local.
El proxy de Vite solo existe durante desarrollo.

## Funciones

- Estudio: material, unidades, kerf, márgenes, giros, paneles, láminas, selección y visor 3D.
- Procesamiento: STL, OBJ, DXF, 3DM, PLY y OFF; exportaciones DXF, SVG y PDF, incluido ZIP multilámina.
- Biblioteca cloud: los anteriores más RVT, IFC, DWG y SKP para **almacenamiento**, sin prometer conversión.
- Cuentas: registro, confirmación de correo, inicio/cierre de sesión y recuperación de contraseña con Supabase.
- Roles: usuario, administrador y propietario; sin privilegios derivados de `user_metadata`.
- Historial: trabajos y exportaciones conservados entre reinicios.
- Comercial: Gratis, Pro y Premium; 5 créditos gratuitos únicos por cuenta verificada,
  saldo simulado separado, cancelación de suscripción simulada y auditoría.
- Administración: simulaciones limitadas, usuarios, roles y apertura/cierre de nuevas cuentas.

## Ejecución local

Se mantienen los lanzadores Windows y la [guía original](docs/LOCAL_ORIGINAL.md).
Python 3.12 y Node 24 recomendados.

```bash
cd backend
python -m venv .venv
# Usa .venv/bin/python en Linux, .venv\Scripts\python.exe en Windows.
.venv/bin/python -m pip install -r requirements-production-lock.txt
.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

En otra terminal:

```bash
cd frontend
npm ci
npm run dev
```

Para compilar exclusivamente una distribución offline: `VITE_APP_MODE=local npm run build`
(en PowerShell, asigna `$env:VITE_APP_MODE="local"` antes del comando). Ese build no se publica en Vercel.

## Publicación

La configuración está en `frontend/vercel.json`, `render.yaml` y los `.env.example`.
Sigue [DEPLOYMENT.md](docs/DEPLOYMENT.md) para servicios, variables, autenticación, propietario,
pruebas públicas y sincronización con Windows. Consulta [ARCHITECTURE.md](docs/ARCHITECTURE.md)
para límites del motor, RVT, almacenamiento y escalado.

Rutas web: `/studio`, `/archivos`, `/historial`, `/precios`, `/cuenta`, `/admin` y `/reset-password`.
La API cloud exige Bearer en todos los recursos salvo `GET /api/health`.

## Pruebas

```bash
cd backend
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pytest -q
# Base de pruebas aislada; nunca usar DATABASE_URL de producción:
TEST_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1:5432/postgres .venv/bin/python -m pytest tests/test_cloud.py -q
```

```bash
cd frontend
npm test
npm run build # Requiere las variables cloud descritas en .env.example.
```

GitHub Actions ejecuta frontend y backend, incluida una base PostgreSQL efímera.
[VALIDACION.md](VALIDACION.md) distingue las pruebas locales, la base real provisionada y las
comprobaciones públicas todavía pendientes. `CODIGO_COMPLETO.md` es una instantánea histórica
0.1: los archivos fuente del repositorio son la versión vigente.
