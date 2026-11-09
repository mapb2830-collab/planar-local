# Publicar Planar Studio

## Recursos preparados en esta sesión

- Repositorio: https://github.com/mapb2830-collab/planar-local
- Vercel: proyecto `planar-studio`, equipo `a-5b6b`, ID `prj_OIoWbNWC0vQTn354g8Us0fQaJy5O`.
  Panel: https://vercel.com/a-5b6b/planar-studio
- Supabase: proyecto `planar-studio`, referencia `vfytgqwmrwfgruxhyikk`, región us-east-1,
  organización del propietario, plan Free observado.
  Panel: https://supabase.com/dashboard/project/vfytgqwmrwfgruxhyikk
  Endpoint de Auth/datos: https://vfytgqwmrwfgruxhyikk.supabase.co
- Migración inicial aplicada: esquema `planar`, siete tablas y RLS activado.
- El endpoint de Supabase **no es la API Python de Planar**.
- Al preparar este documento no hay despliegue Vercel ni backend público verificado.

## 1. Plan comercial compatible

La cuenta Vercel accesible informa Hobby. La API del equipo no muestra su facturación;
confirmar/activar Pro en el equipo antes de desplegar esta beta de un SaaS comercial.
Vercel restringe Hobby a uso personal no comercial, incluso si los cobros están desactivados.
Pro figura desde USD 20/mes más consumo e impuestos; confirmar el importe al contratar.
No se ha comprado ni activado una suscripción de alojamiento pagada desde esta sesión.

Fuentes consultadas: https://vercel.com/docs/limits/fair-use-guidelines y https://vercel.com/pricing
Facturación del equipo: https://vercel.com/teams/a-5b6b/settings/billing

## 2. Supabase y correo

En Authentication:

1. Mantener **Confirm email** habilitado. Desactivar inicio anónimo si no se utiliza.
2. Configurar contraseña mínima de 12 caracteres y protección adicional disponible.
3. Tras conocer el dominio Vercel, establecer Site URL en ese origen HTTPS y permitir
   exactamente `/studio` y `/reset-password` como destinos de redirección. No usar comodines
   amplios para producción. Un enlace PKCE debe abrirse en el mismo navegador que inició el flujo.
4. Configurar SMTP autorizado para el dominio/correo del producto y los límites de envío.
   El servicio de correo predeterminado de Supabase tiene restricciones y no basta para
   garantizar registro público de cualquier dirección. Probar confirmación y recuperación.
5. Configurar CAPTCHA/controles antiabuso antes de abrir una beta masiva. Esta versión no
   integra todavía un widget CAPTCHA: requiere añadirlo al flujo si se habilita en Supabase.

La integración actual permite migraciones, pero no expone un método para cambiar estos ajustes
de Auth/SMTP ni recuperar la contraseña de PostgreSQL. Esas configuraciones quedan en el panel.

En Connect, copiar la URL del **session pooler** (puerto 5432). Introducir la contraseña fuerte
solo en el campo secreto `DATABASE_URL` del proveedor Python. Codificar caracteres especiales
como parte de una URL. No enviar la contraseña por chat, subir `.env` ni ponerla en Vercel.
El backend acepta `postgresql://` y lo normaliza a `postgresql+psycopg://`.

No agregar `planar` a los schemas expuestos por Data API. Los permisos/RLS están diseñados
para acceso exclusivo mediante backend. La migración está en `backend/migrations/001_cloud_studio.sql`.
El primer arranque también crea tablas faltantes; futuras alteraciones requieren una migración
versionada, no basta con `create_all`.

## 3. Backend en Render

Conectar Render a esta conversación y a GitHub, o importar `render.yaml` con Blueprints.
La plantilla define un Web Service Python en Virginia, plan Standard, disco persistente de 1 GB,
una sola instancia y health check `/api/health`. El coste de referencia consultado es USD 25/mes por el servicio y USD 0,25/mes por 1 GB de disco, más impuestos/consumo u otros cargos del workspace. Confirmar la cotización en el proveedor antes de crearlos. Fuentes: https://render.com/pricing y https://render.com/docs/compute-plans. Render Free no admite el disco necesario.

| Configuración | Valor |
|---|---|
| Root Directory | `backend` |
| Build | `pip install -r requirements-production-lock.txt` |
| Start | `python -m uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1 --limit-concurrency 16 --no-access-log --log-level info` |
| Python | 3.12.14 |
| Health check | `/api/health` |
| Persistent disk | `/var/data`, 1 GB |

Variables del backend:

| Variable | Valor / dónde obtenerlo |
|---|---|
| `PLANAR_MODE` | `cloud` |
| `PAYMENTS_MODE` | `disabled` |
| `DATABASE_URL` | Secreto, pooler Supabase |
| `SUPABASE_URL` | `https://vfytgqwmrwfgruxhyikk.supabase.co` |
| `SUPABASE_PUBLISHABLE_KEY` | Clave publishable del proyecto, no service_role |
| `CORS_ORIGINS` | Origen exacto del frontend público, separado por comas solo si hay varios autorizados |
| `STORAGE_PATH` | `/var/data/planar` |
| `OWNER_EMAIL` | `marcos.pacheco@cun.edu.co` |
| `OPENBLAS_NUM_THREADS`, `OMP_NUM_THREADS` | `1` |

La aplicación rechaza orígenes HTTP, comodines y loopback en cloud. Debe conocerse el dominio
asignado por Vercel para fijar CORS; no ampliar CORS a `*` para resolver la conexión.
En el primer despliegue comprobar logs y obtener `{"status":"ok","mode":"cloud","payments":"disabled"}`
en `/api/health`. Guardar la URL real HTTPS de Render como `VITE_API_URL`.

## 4. Frontend en Vercel

El proyecto ya está preparado con:

| Configuración | Valor |
|---|---|
| Root Directory | `frontend` |
| Framework | Vite |
| Node | 24.x |
| Install | `npm ci` |
| Build | `npm run build` |
| Output | `dist` |

Ya se establecieron `VITE_APP_MODE=cloud`, `VITE_SUPABASE_URL` y la clave publishable como
variables de producción/preview. Falta `VITE_API_URL` con el origen real del backend, sin `/api`.
No existe fallback productivo a localhost. Las variables VITE son públicas y se incorporan
al build: no colocar secretos en ellas. Recompilar tras cambiarlas.

Conectar el proyecto a `mapb2830-collab/planar-local`, rama `main`, cuando el cambio validado
esté integrado y Pro/API estén listos. El proyecto se creó sin conexión Git para no desplegar
la versión local original automáticamente. `frontend/vercel.json` conserva recursos y resuelve
rutas SPA. La protección Vercel por login se desactivó para permitir el acceso público solicitado;
la autenticación y los permisos de la aplicación siguen aplicando.

La CSP permite conexiones a Supabase y Render. Si se usa un dominio API personalizado u otro
proveedor, añadir su origen exacto a `connect-src` antes de compilar. No desactivar la CSP.
Para previews que accedan a datos reales, usar dominios explícitos aprobados en CORS y Auth;
preferir un proyecto Supabase separado para staging.

## 5. Propietario y administración

1. Registrarse con `marcos.pacheco@cun.edu.co` y una contraseña fuerte elegida por el propietario.
2. Abrir el correo de confirmación e iniciar sesión; `/api/me` debe crear la cuenta verificada.
3. En la consola autenticada del servicio Render, dentro de `backend`, ejecutar:

```bash
python -m app.bootstrap_owner
```

El comando exige que la cuenta verificada ya exista y que no haya propietario asignado.
Usa bloqueo de tabla PostgreSQL, audita la operación y no crea ni imprime una contraseña.
No existe endpoint HTTP público de bootstrap ni ascenso automático por conocer el correo.

4. Recargar sesión y abrir `/admin`. El propietario puede asignar administradores; estos pueden
   registrar simulaciones, pero no crear otros administradores ni modificar al propietario.

## 6. Verificación antes de anunciar publicación

- Abrir frontend en una ventana sin sesión Vercel; comprobar HTTP 200 y carga de recursos.
- Abrir directamente `/precios`, `/studio`, `/admin` y recargar sin 404 de Vercel.
- Registrar una cuenta de prueba real, confirmar correo, iniciar/cerrar sesión y recuperar contraseña.
- Verificar que un usuario sin sesión recibe 401 de API y un usuario común 403 en administración.
- Subir un STL/OBJ, generar paneles y descargar DXF/SVG/PDF; saldo gratuito disminuye una sola vez.
- Subir RVT a la biblioteca: almacenamiento y descarga correctos, aviso de conversión, sin despiece falso.
- Intentar leer/eliminar archivos y exportaciones de otra cuenta: 404.
- Verificar owner bootstrap y `/admin`; simular compra y comprobar `paid_credits=0`.
- Intentar checkout público: 403. Agotar gratis y comprobar que el saldo simulado no habilita despieces.
- Reiniciar el backend y comprobar archivos, historial y exportaciones.
- Cerrar las terminales locales: las URLs de proveedor deben seguir funcionando.

Hasta pasar estas comprobaciones no describir la aplicación como publicada y verificada.

## 7. Actualizar la carpeta Windows sin perder cambios

La carpeta `C:\Users\debor\Downloads\planar-local-main\planar-local-main\` no es accesible desde
el entorno Linux de esta sesión. No se han revisado ni sobrescrito sus archivos.

Si contiene `.git`, abrir una terminal allí, revisar `git status` y conservar cualquier cambio
local antes de sincronizar. Con el árbol limpio:

```powershell
git fetch origin
git switch main
git merge --ff-only origin/main
```

Si proviene de un ZIP, descargar el nuevo `main` y extraerlo en **otra carpeta**. Comparar los
archivos locales y trasladar solo los cambios necesarios. No borrar la carpeta anterior.
La copia trabajada por Codex fue un clon limpio de GitHub, base `3a44745`.

## 8. Pagos posteriores

Seguir [PAYMENTS_LATER.md](PAYMENTS_LATER.md). No introducir claves Wompi reales en esta beta.
