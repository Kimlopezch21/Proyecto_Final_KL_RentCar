import io
import json
import os
import tempfile
from pathlib import Path


tmp = tempfile.TemporaryDirectory()
os.environ["RENTCAR_DB"] = str(Path(tmp.name) / "rentcar-test.sqlite")
os.environ["RENTCAR_DEMO_AUTH"] = "1"

from app import application  # noqa: E402


class Client:
    def __init__(self):
        self.cookie = ""

    def request(self, path, method="GET", body=None, expected=200, raw_response=False):
        raw = json.dumps(body).encode() if body is not None else b""
        if "?" in path:
            path_info, query = path.split("?", 1)
        else:
            path_info, query = path, ""
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path_info,
            "QUERY_STRING": query,
            "CONTENT_LENGTH": str(len(raw)),
            "CONTENT_TYPE": "application/json",
            "wsgi.input": io.BytesIO(raw),
        }
        if self.cookie:
            environ["HTTP_COOKIE"] = self.cookie
        status_headers = []

        def start_response(status, headers):
            status_headers.append((status, headers))

        response_bytes = b"".join(application(environ, start_response))
        status = int(status_headers[0][0].split()[0])
        for key, value in status_headers[0][1]:
            if key.lower() == "set-cookie":
                self.cookie = value.split(";", 1)[0]
        if status != expected:
            raise AssertionError(f"{method} {path} devolvio {status}: {response_bytes.decode(errors='replace')}")
        if raw_response:
            return response_bytes, status_headers[0][1]
        response = response_bytes.decode()
        return json.loads(response) if response else {}


def main():
    admin = Client()
    employee = Client()
    admin.request("/api/auth/password", "POST", {"username": "admin", "password": "12345"})
    employee.request("/api/auth/password", "POST", {"username": "empleado", "password": "12345"})
    valid_admin_cookie = admin.cookie

    admin.cookie = f"rentcar_session=sesion-vieja-invalida; {valid_admin_cookie}"
    me = admin.request("/api/auth/me")
    assert me["user"]["role"] == "admin"

    admin.cookie = f"{valid_admin_cookie}; rentcar_session=sesion-vieja-invalida"
    me = admin.request("/api/auth/me")
    assert me["user"]["role"] == "admin"

    admin.cookie = valid_admin_cookie

    summary = admin.request("/api/summary")
    assert summary["vehiculosDisponibles"] >= 1

    created_customer = admin.request(
        "/api/clientes",
        "POST",
        {
            "name": "Cliente Cedula Valida",
            "cedula": "00112345673",
            "credit_card_no": "1234",
            "credit_limit": 10000,
            "person_type": "Física",
            "status": "Activo",
        },
        expected=201,
    )
    admin.request(f"/api/clientes/{created_customer['id']}", "DELETE")
    customers = admin.request("/api/clientes")
    assert any(item["id"] == created_customer["id"] and item["status"] == "Inactivo" for item in customers)
    admin.request(f"/api/clientes/{created_customer['id']}", "DELETE")
    customers = admin.request("/api/clientes")
    assert any(item["id"] == created_customer["id"] and item["status"] == "Activo" for item in customers)
    admin.request(
        "/api/clientes",
        "POST",
        {
            "name": "Cliente Cedula Invalida",
            "cedula": "00112345678",
            "credit_card_no": "1234",
            "credit_limit": 10000,
            "person_type": "Física",
            "status": "Activo",
        },
        expected=400,
    )

    employee.request("/api/marcas", "POST", {"description": "Ford", "status": "Activo"}, expected=403)
    brands = admin.request("/api/marcas")
    toyota = next(item for item in brands if item["description"] == "Toyota")
    error = admin.request(f"/api/marcas/{toyota['id']}", "DELETE", expected=400)
    assert "vehículos asociados" in error["error"]

    users = admin.request("/api/usuarios")
    assert [item["name"] for item in users] == ["Administrador", "Empleado"]
    administrador = next(item for item in users if item["role"] == "admin")
    error = admin.request(f"/api/usuarios/{administrador['id']}", "DELETE", expected=400)
    assert error["error"] == "No se puede inactivar el único administrador activo."
    empleado = next(item for item in users if item["role"] == "empleado")
    admin.request(f"/api/usuarios/{empleado['id']}", "DELETE")
    users = admin.request("/api/usuarios")
    assert any(item["id"] == empleado["id"] and item["status"] == "Inactivo" for item in users)
    admin.request(f"/api/usuarios/{empleado['id']}", "DELETE")
    users = admin.request("/api/usuarios")
    assert any(item["id"] == empleado["id"] and item["status"] == "Activo" for item in users)

    admin.request(
        "/api/inspecciones",
        "POST",
        {
            "vehicle_id": 1,
            "customer_id": 1,
            "employee_id": 1,
            "inspection_date": "2026-06-01",
            "fuel_amount": "Lleno",
            "status": "Aprobada",
            "has_scratches": 0,
            "has_spare_tire": 1,
            "has_jack": 1,
            "has_glass_breaks": 0,
            "tire_front_left": "Buena",
            "tire_front_right": "Buena",
            "tire_rear_left": "Buena",
            "tire_rear_right": "Buena",
            "notes": "Lista para renta",
        },
        expected=201,
    )
    rental = admin.request(
        "/api/rentas",
        "POST",
        {
            "employee_id": 1,
            "vehicle_id": 1,
            "customer_id": 1,
            "rent_date": "2026-06-01",
            "daily_amount": 2500,
            "days": 2,
            "comment": "Prueba automatizada",
        },
        expected=201,
    )
    admin.request(
        "/api/rentas",
        "POST",
        {
            "employee_id": 1,
            "vehicle_id": 1,
            "customer_id": 1,
            "rent_date": "2026-06-01",
            "daily_amount": 2500,
            "days": 1,
        },
        expected=400,
    )
    returned = admin.request(f"/api/rentas/{rental['id']}/devolver", "POST", {"return_date": "2026-06-03"})
    assert returned["days"] == 2
    assert returned["total"] == 5000
    admin.request(f"/api/rentas/{rental['id']}/reabrir", "POST")
    reopened = admin.request(f"/api/rentas/{rental['id']}")
    assert reopened["status"] == "Abierta"
    returned = admin.request(f"/api/rentas/{rental['id']}/devolver", "POST", {"return_date": "2026-06-03"})
    assert returned["total"] == 5000

    report = admin.request("/api/reportes/rentas?from=2026-06-01&to=2026-06-30")
    assert report["total"] == 5000
    pdf, headers = admin.request("/api/reportes/rentas/pdf?from=2026-06-01&to=2026-06-30", raw_response=True)
    assert pdf.startswith(b"%PDF-1.4")
    assert b"REPORTE DE RENTAS Y DEVOLUCIONES" in pdf
    assert b"Autorizado por" in pdf
    assert b"/MediaBox [0 0 612 792]" in pdf
    assert b"0 535 842 60" not in pdf
    assert any(key.lower() == "content-type" and value == "application/pdf" for key, value in headers)
    print("OK - pruebas principales completadas")


if __name__ == "__main__":
    main()
