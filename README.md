# RentCar con Google Sign-In

Sistema web para la práctica de exoneración: React, Python estándar y SQLite.

## Ejecutar localmente

Desde esa carpeta:

```powershell
python app.py
```

Si `python` no está en el PATH, instala Python 3 y vuelve a ejecutar el comando anterior.

Abre:

```text
http://127.0.0.1:8000
```

La app crea `rentcar.sqlite` automáticamente con datos de ejemplo.

## Login

Variables de entorno principales:

```powershell
$env:GOOGLE_CLIENT_ID="TU_CLIENT_ID.apps.googleusercontent.com"
$env:RENTCAR_ADMIN_EMAIL="tu_correo@gmail.com"
$env:RENTCAR_SESSION_SECRET="cambia-este-secreto"
$env:RENTCAR_DEMO_AUTH="1"
python app.py
```

En desarrollo, `RENTCAR_DEMO_AUTH=1` muestra botones demo:

- `admin@rentcar.local`
- `empleado@rentcar.local`

En PythonAnywhere se recomienda `RENTCAR_DEMO_AUTH=0`.

## Configurar Google Sign-In

1. Entra a Google Cloud Console.
2. Crea un proyecto.
3. Configura la pantalla de consentimiento OAuth.
4. Crea credenciales de tipo `OAuth client ID`.
5. Tipo de aplicación: `Web application`.
6. Agrega los orígenes autorizados:
   - Local: `http://127.0.0.1:8000`
   - PythonAnywhere: `https://tu_usuario.pythonanywhere.com`
7. Copia el Client ID en `GOOGLE_CLIENT_ID`.

Los usuarios deben existir en la pantalla `Usuarios` con estado `Activo`. Si alguien intenta entrar con Google y no está registrado, queda pendiente.

## Despliegue en PythonAnywhere gratis

1. Crea una cuenta gratis en PythonAnywhere.
2. Sube la carpeta `Proyecto_Final_KL_RentCar` a `/home/tu_usuario/Proyecto_Final_KL_RentCar`.
3. En la sección `Web`, crea una nueva app manual con Python 3.
4. En el archivo WSGI de PythonAnywhere, copia el contenido de `pythonanywhere_wsgi.py`.
5. Cambia esta línea:

```python
PROJECT_DIR = "/home/tu_usuario/Proyecto_Final_KL_RentCar"
```

6. En `Web > Environment variables`, configura:

```text
GOOGLE_CLIENT_ID=TU_CLIENT_ID.apps.googleusercontent.com
RENTCAR_ADMIN_EMAIL=tu_correo@gmail.com
RENTCAR_SESSION_SECRET=un_texto_largo_y_privado
RENTCAR_DEMO_AUTH=0
```

7. Recarga la web app.
8. Entra con el correo definido en `RENTCAR_ADMIN_EMAIL`.

Nota: PythonAnywhere gratis restringe llamadas salientes a dominios permitidos. Google APIs está en su lista permitida, por eso la verificación del token de Google puede funcionar desde el backend gratis.

## Módulos incluidos

- Tipos de vehículos
- Marcas
- Modelos
- Tipos de combustible
- Vehículos
- Clientes
- Empleados
- Inspecciones
- Renta y devolución
- Consulta por criterios
- Reporte de rentas con CSV
- Usuarios y roles

## Pruebas

```powershell
python tests.py
```

Las pruebas usan una base SQLite temporal y validan login demo, permisos, inspección, renta, devolución y reporte.
