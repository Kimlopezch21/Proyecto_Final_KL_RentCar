# Proyecto Final KL RentCar

Sistema web para la gestión de renta de vehículos. La aplicación permite administrar catálogos, clientes, empleados, inspecciones, rentas, devoluciones, reportes y usuarios desde una interfaz centralizada.

El proyecto está preparado para ejecutarse localmente utilizando Python, archivos estáticos y una base de datos SQLite.

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

## Pruebas

Para ejecutar las pruebas principales:

```powershell
python tests.py
```

Las pruebas validan autenticacion, permisos, inspecciones, rentas, devoluciones, usuarios y reportes.
