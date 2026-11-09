# Validación — Planar Studio 0.2

Fecha: 9 de noviembre de 2026. Entorno de trabajo Linux, Python 3.12, Node 24.

## Resultados comprobados

| Comprobación | Resultado |
|---|---|
| Suite Python completa | 26 pruebas aprobadas: 16 del motor original y 10 cloud |
| Suite cloud contra PostgreSQL 17 efímero | 10 aprobadas |
| React/Vitest | 11 aprobadas: 5 flujo local y 6 cloud |
| Build cloud Vite/TypeScript | Aprobado usando orígenes reservados de prueba, sin desplegar ese artefacto |
| Build con API productiva en loopback | Rechazado intencionalmente con error de URL HTTPS pública |
| Chromium, escritorio 1440 px | Flujo del estudio, biblioteca, planes y administración comprobados |
| Chromium, móvil 390 px | Sin desbordamiento horizontal en estudio ni precios |
| Consola del navegador | Cero errores JavaScript en el recorrido |
| Supabase provisionado | Siete tablas privadas, todas con RLS |
| Privilegios Supabase | `anon_access=false`, `user_access=false`, `rls_tables=7` |
| Vercel | Proyecto creado y variables de Auth preparadas; `live=false`, sin deployment |

## Flujo comprobado en navegador

Inicio de sesión con proveedor de identidad simulado exclusivamente en el arnés de pruebas →
API Python real → base SQLite persistente de laboratorio → subproceso CAD → cinco paneles
para `pabellon.obj` → visor 3D y láminas → descarga DXF. También se cargó RVT como original,
se consultó la biblioteca y se registró una simulación administrativa. Ningún usuario ni
archivo de laboratorio se insertó en el Supabase real.

La prueba de navegador **no acredita funcionamiento de SMTP ni login Supabase en producción**.
La suite cloud prueba por separado respuestas del proveedor de identidad, correo sin verificar,
permisos y rechazo de tokens inválidos mediante un transporte simulado.

## Seguridad y consistencia cubiertas

- Usuario sin token: 401; token inválido: 401; correo no verificado: 403.
- Los metadatos de usuario no conceden roles; el correo del dueño por sí solo no lo promueve.
- Bootstrap protegido, propietario único, delegación de rol solo por propietario y auditoría.
- Archivos y resultados de otra cuenta: 404; rutas generadas por UUID y nombres normalizados.
- Límites de cuerpo/carga y biblioteca; RVT almacenado, pero rechazado para despiece.
- Resultado/exportación disponible al recrear la API; reembolso por fallo y por interrupción.
- Dos peticiones concurrentes con un único crédito: solo una operación se autoriza.
- Compra pública rechazada; simulación limitada/idempotente; saldo pagado permanece en cero.
- Saldo simulado no permite procesar cuando se agota el saldo gratuito.
- CORS con origen exacto; configuración cloud falla ante loopback y ante pagos reales.

## Límites y advertencias de verificación

- Falta desplegar la API y el frontend, configurar SMTP/redirecciones y completar el recorrido
  desde sus dominios públicos. No hay URL pública funcional de Planar certificada todavía.
- Windows no está montado en este entorno. No se ejecutaron los `.cmd` ni se inspeccionó la
  carpeta local del propietario; se preservaron los lanzadores originales.
- Vite advierte del tamaño del motor Three.js (aprox. 753 KB / 193 KB gzip). Es un chunk
  diferido del visor, y el render es bajo demanda para reducir consumo cuando está inactivo.
- FastAPI/Starlette emite una advertencia de deprecación sobre el transporte httpx de TestClient;
  no afectó las pruebas. No se sustituyó por una dependencia no requerida por producción.
- El asesor Supabase muestra avisos INFO de RLS sin políticas: es la denegación por defecto
  intencional del esquema privado, adicional a los privilegios revocados. No hay políticas
  públicas que permitan editar roles o créditos.
- Reiniciar el entorno de trabajo detuvo servicios temporales de pruebas; se recreó PostgreSQL
  y la ejecución final de diez pruebas contra esa base pasó.

CI en `.github/workflows/validate.yml` reproduce backend, PostgreSQL, frontend y build.
La lista de verificación pública y los pasos pendientes están en `docs/DEPLOYMENT.md`.
