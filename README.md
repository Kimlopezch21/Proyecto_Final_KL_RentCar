# Proyecto Final KL RentCar

Sistema web para la gestion de renta de vehiculos. La aplicacion permite administrar catalogos, clientes, empleados, inspecciones, rentas, devoluciones, reportes y usuarios desde una interfaz centralizada.

El proyecto esta preparado para ejecutarse localmente o desplegarse en PythonAnywhere usando Python, archivos estaticos y una base de datos local incluida en el proyecto.

## Caracteristicas principales

- Inicio de sesion con usuario y contrasena.
- Control de acceso por roles: Administrador y Empleado.
- Administracion de tipos de vehiculos, marcas, modelos y tipos de combustible.
- Registro y mantenimiento de vehiculos.
- Gestion de clientes y empleados.
- Inspeccion previa al proceso de renta.
- Registro de rentas, devoluciones, cancelaciones y reaperturas.
- Consulta de rentas por cliente, vehiculo, estado y fechas.
- Reporte profesional de rentas y devoluciones en PDF.
- Panel inicial con resumen operativo.
- Activacion e inactivacion de registros sin perdida de informacion.

## Credenciales de acceso

Administrador:

```text
Usuario: admin
Contrasena: 12345
```

Empleado:

```text
Usuario: empleado
Contrasena: 12345
```

## Requisitos

- Python 3.11 o superior.
- Navegador web moderno.

No requiere instalacion de paquetes externos para ejecutarse en modo local.

## Ejecucion local

Desde la carpeta del proyecto:

```powershell
python app.py
```

Luego abre en el navegador:

```text
http://127.0.0.1:8000
```

## Estructura del proyecto

```text
Proyecto_Final_KL_RentCar/
|-- app.py
|-- pythonanywhere_wsgi.py
|-- rentcar.sqlite
|-- tests.py
|-- README.md
`-- static/
    |-- index.html
    |-- app.js
    |-- styles.css
    `-- assets/
```

## Modulos incluidos

- Inicio
- Clientes
- Inspecciones
- Rentas y devoluciones
- Reportes
- Vehiculos
- Tipos de vehiculos
- Marcas
- Modelos
- Tipos de combustible
- Empleados
- Usuarios

## Despliegue en PythonAnywhere

1. Crea una cuenta en PythonAnywhere.
2. Sube la carpeta `Proyecto_Final_KL_RentCar` a tu cuenta.
3. Crea una nueva aplicacion web manual con Python 3.
4. Configura el archivo WSGI usando `pythonanywhere_wsgi.py`.
5. Verifica que `PROJECT_DIR` apunte a la ruta donde subiste el proyecto:

```python
PROJECT_DIR = "/home/tu_usuario/Proyecto_Final_KL_RentCar"
```

6. Recarga la aplicacion web desde el panel de PythonAnywhere.
7. Accede al sistema con las credenciales indicadas.

## Pruebas

Para ejecutar las pruebas principales:

```powershell
python tests.py
```

Las pruebas validan autenticacion, permisos, inspecciones, rentas, devoluciones, usuarios y reportes.

## Observaciones

Este sistema fue desarrollado como proyecto academico para demostrar un flujo completo de gestion de renta de vehiculos, desde el registro de catalogos hasta la emision de reportes finales.
