from __future__ import annotations

import base64
import csv
import datetime as dt
import hashlib
import hmac
import io
import json
import os
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = Path(os.environ.get("RENTCAR_DB", BASE_DIR / "rentcar.sqlite"))
SESSION_SECRET = os.environ.get("RENTCAR_SESSION_SECRET", "dev-secret-change-me")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
DEMO_AUTH = os.environ.get("RENTCAR_DEMO_AUTH", "1") == "1"
ADMIN_EMAIL = os.environ.get("RENTCAR_ADMIN_EMAIL", "").strip().lower()
SESSION_COOKIE_NAME = "rentcar_session"
SESSION_MAX_AGE = 60 * 60 * 8
DB_INITIALIZED = False


ROUTES = {
    "tipos-vehiculos": {
        "table": "vehicle_types",
        "admin_write": True,
        "fields": ["description", "status"],
    },
    "marcas": {
        "table": "brands",
        "admin_write": True,
        "fields": ["description", "status"],
    },
    "modelos": {
        "table": "models",
        "admin_write": True,
        "fields": ["brand_id", "description", "status"],
    },
    "tipos-combustible": {
        "table": "fuel_types",
        "admin_write": True,
        "fields": ["description", "status"],
    },
    "vehiculos": {
        "table": "vehicles",
        "admin_write": True,
        "fields": [
            "description",
            "chassis_no",
            "motor_no",
            "plate_no",
            "vehicle_type_id",
            "brand_id",
            "model_id",
            "fuel_type_id",
            "status",
        ],
    },
    "clientes": {
        "table": "customers",
        "admin_write": False,
        "fields": [
            "name",
            "cedula",
            "credit_card_no",
            "credit_limit",
            "person_type",
            "status",
        ],
    },
    "empleados": {
        "table": "employees",
        "admin_write": True,
        "fields": [
            "name",
            "cedula",
            "work_shift",
            "commission_percent",
            "hire_date",
            "status",
        ],
    },
}


def now_iso() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def rows_to_dicts(rows) -> list[dict]:
    return [dict(row) for row in rows]


def execute_script(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT 'empleado',
            status TEXT NOT NULL DEFAULT 'Pendiente',
            provider TEXT NOT NULL DEFAULT 'google',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT
        );

        CREATE TABLE IF NOT EXISTS vehicle_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'Activo'
        );

        CREATE TABLE IF NOT EXISTS brands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'Activo'
        );

        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand_id INTEGER NOT NULL REFERENCES brands(id),
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Activo',
            UNIQUE (brand_id, description)
        );

        CREATE TABLE IF NOT EXISTS fuel_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'Activo'
        );

        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT NOT NULL,
            chassis_no TEXT NOT NULL UNIQUE,
            motor_no TEXT NOT NULL UNIQUE,
            plate_no TEXT NOT NULL UNIQUE,
            vehicle_type_id INTEGER NOT NULL REFERENCES vehicle_types(id),
            brand_id INTEGER NOT NULL REFERENCES brands(id),
            model_id INTEGER NOT NULL REFERENCES models(id),
            fuel_type_id INTEGER NOT NULL REFERENCES fuel_types(id),
            status TEXT NOT NULL DEFAULT 'Disponible'
        );

        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cedula TEXT NOT NULL UNIQUE,
            credit_card_no TEXT NOT NULL,
            credit_limit REAL NOT NULL DEFAULT 0,
            person_type TEXT NOT NULL DEFAULT 'Física',
            status TEXT NOT NULL DEFAULT 'Activo'
        );

        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cedula TEXT NOT NULL UNIQUE,
            work_shift TEXT NOT NULL DEFAULT 'Matutina',
            commission_percent REAL NOT NULL DEFAULT 0,
            hire_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Activo'
        );

        CREATE TABLE IF NOT EXISTS inspections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            has_scratches INTEGER NOT NULL DEFAULT 0,
            fuel_amount TEXT NOT NULL,
            has_spare_tire INTEGER NOT NULL DEFAULT 1,
            has_jack INTEGER NOT NULL DEFAULT 1,
            has_glass_breaks INTEGER NOT NULL DEFAULT 0,
            tire_front_left TEXT NOT NULL DEFAULT 'Bueno',
            tire_front_right TEXT NOT NULL DEFAULT 'Bueno',
            tire_rear_left TEXT NOT NULL DEFAULT 'Bueno',
            tire_rear_right TEXT NOT NULL DEFAULT 'Bueno',
            notes TEXT NOT NULL DEFAULT '',
            inspection_date TEXT NOT NULL,
            employee_id INTEGER NOT NULL REFERENCES employees(id),
            status TEXT NOT NULL DEFAULT 'Aprobada'
        );

        CREATE TABLE IF NOT EXISTS rentals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL REFERENCES employees(id),
            vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            rent_date TEXT NOT NULL,
            return_date TEXT,
            daily_amount REAL NOT NULL,
            days INTEGER NOT NULL DEFAULT 1,
            total_amount REAL NOT NULL DEFAULT 0,
            comment TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Abierta',
            inspection_id INTEGER REFERENCES inspections(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            action TEXT NOT NULL,
            entity TEXT NOT NULL,
            entity_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )


def seed_data(conn: sqlite3.Connection) -> None:
    def insert_missing(table: str, columns: list[str], values: list[tuple]) -> None:
        placeholders = ", ".join(["?"] * len(columns))
        conn.executemany(
            f"INSERT OR IGNORE INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
            values,
        )

    insert_missing(
        "vehicle_types",
        ["description", "status"],
        [
            ("Automóvil", "Activo"),
            ("SUV", "Activo"),
            ("Camioneta", "Activo"),
            ("Furgoneta", "Activo"),
            ("Jeep", "Activo"),
            ("Minivan", "Activo"),
            ("Camión", "Activo"),
        ],
    )
    insert_missing(
        "brands",
        ["description", "status"],
        [
            ("Toyota", "Activo"),
            ("Honda", "Activo"),
            ("Kia", "Activo"),
            ("Hyundai", "Activo"),
            ("Nissan", "Activo"),
            ("Chevrolet", "Activo"),
            ("Ford", "Activo"),
            ("BMW", "Activo"),
            ("Mercedes-Benz", "Activo"),
            ("Audi", "Activo"),
        ],
    )
    insert_missing(
        "fuel_types",
        ["description", "status"],
        [
            ("Gasolina", "Activo"),
            ("Gasóleo", "Activo"),
            ("Gas Natural", "Activo"),
            ("Eléctrico", "Activo"),
            ("Híbrido", "Activo"),
        ],
    )

    brand_ids = {row["description"]: row["id"] for row in conn.execute("SELECT id, description FROM brands")}
    demo_models = {
        "Toyota": ["Corolla", "Camry", "RAV4"],
        "Honda": ["Civic", "Accord", "CR-V"],
        "Kia": ["Sportage", "Sorento", "Seltos"],
        "Hyundai": ["Tucson", "Santa Fe", "Elantra"],
        "Nissan": ["Sentra", "Altima", "X-Trail"],
        "Ford": ["Explorer", "Escape", "Ranger"],
        "Chevrolet": ["Tahoe", "Traverse", "Silverado"],
        "BMW": ["X5", "Serie 3"],
        "Audi": ["Q5", "A4"],
        "Mercedes-Benz": ["Clase C", "GLC"],
    }
    insert_missing(
        "models",
        ["brand_id", "description", "status"],
        [(brand_ids[brand], model, "Activo") for brand, models in demo_models.items() for model in models],
    )

    vehicle_type_ids = {row["description"]: row["id"] for row in conn.execute("SELECT id, description FROM vehicle_types")}
    fuel_ids = {row["description"]: row["id"] for row in conn.execute("SELECT id, description FROM fuel_types")}
    for invalid_type, replacement_type in [("BMW X5", "SUV"), ("Audi Q5", "SUV"), ("Automovil", "Automóvil")]:
        row = conn.execute("SELECT id FROM vehicle_types WHERE description=?", (invalid_type,)).fetchone()
        if row:
            conn.execute("UPDATE vehicles SET vehicle_type_id=? WHERE vehicle_type_id=?", (vehicle_type_ids[replacement_type], row["id"]))
            conn.execute("DELETE FROM vehicle_types WHERE id=?", (row["id"],))
    vehicle_type_ids = {row["description"]: row["id"] for row in conn.execute("SELECT id, description FROM vehicle_types")}
    for invalid_fuel in ["Sorento"]:
        row = conn.execute("SELECT id FROM fuel_types WHERE description=?", (invalid_fuel,)).fetchone()
        if row:
            conn.execute("UPDATE vehicles SET fuel_type_id=? WHERE fuel_type_id=?", (fuel_ids["Gasolina"], row["id"]))
            conn.execute("DELETE FROM fuel_types WHERE id=?", (row["id"],))
    fuel_ids = {row["description"]: row["id"] for row in conn.execute("SELECT id, description FROM fuel_types")}
    model_ids = {
        (row["brand"], row["description"]): row["id"]
        for row in conn.execute(
            """
            SELECT m.id, m.description, b.description AS brand
            FROM models m
            JOIN brands b ON b.id = m.brand_id
            """
        )
    }
    insert_missing(
        "vehicles",
        [
            "description",
            "chassis_no",
            "motor_no",
            "plate_no",
            "vehicle_type_id",
            "brand_id",
            "model_id",
            "fuel_type_id",
            "status",
        ],
        [
            ("Toyota Corolla 2022 Blanco", "9BRBL3HE5N0123456", "2ZR123456", "A123456", vehicle_type_ids["Automóvil"], brand_ids["Toyota"], model_ids[("Toyota", "Corolla")], fuel_ids["Gasolina"], "Disponible"),
            ("Honda Civic 2021 Gris", "19XFC2F59ME123456", "L15B123456", "B234567", vehicle_type_ids["Automóvil"], brand_ids["Honda"], model_ids[("Honda", "Civic")], fuel_ids["Gasolina"], "Disponible"),
            ("Kia Sportage 2024 Azul", "KNAPU81BPN7123456", "G4NA123456", "C345678", vehicle_type_ids["SUV"], brand_ids["Kia"], model_ids[("Kia", "Sportage")], fuel_ids["Gasolina"], "Disponible"),
            ("BMW X5 2022 Negro", "5UXCR6C05N9123456", "B58B301234", "D456789", vehicle_type_ids["SUV"], brand_ids["BMW"], model_ids[("BMW", "X5")], fuel_ids["Gasolina"], "Disponible"),
            ("Audi Q5 2021 Gris", "WA1BAAFYXM2123456", "CYRB123456", "E567890", vehicle_type_ids["SUV"], brand_ids["Audi"], model_ids[("Audi", "Q5")], fuel_ids["Gasolina"], "Disponible"),
            ("Hyundai Tucson 2023 Negra", "KM8JBCAE7NU123456", "G4FJ123456", "F678901", vehicle_type_ids["SUV"], brand_ids["Hyundai"], model_ids[("Hyundai", "Tucson")], fuel_ids["Gasolina"], "Disponible"),
            ("Nissan Sentra 2020 Plata", "3N1AB8CVXLY123456", "MR20123456", "G789012", vehicle_type_ids["Automóvil"], brand_ids["Nissan"], model_ids[("Nissan", "Sentra")], fuel_ids["Gasolina"], "Disponible"),
            ("Ford Explorer 2023 Negro", "1FMSK8DHXPGA12345", "ECOB123456", "H890123", vehicle_type_ids["SUV"], brand_ids["Ford"], model_ids[("Ford", "Explorer")], fuel_ids["Gasolina"], "Disponible"),
            ("Chevrolet Tahoe 2021 Blanco", "1GNSKPKD8MR123456", "L84123456", "I901234", vehicle_type_ids["SUV"], brand_ids["Chevrolet"], model_ids[("Chevrolet", "Tahoe")], fuel_ids["Gasolina"], "Disponible"),
            ("Mercedes-Benz GLC 2022 Gris", "W1N0G8EB8NV123456", "M264123456", "J012345", vehicle_type_ids["SUV"], brand_ids["Mercedes-Benz"], model_ids[("Mercedes-Benz", "GLC")], fuel_ids["Gasolina"], "Mantenimiento"),
        ],
    )
    for description, chassis_no, motor_no, plate_no, vehicle_type_id, brand_id, model_id, fuel_type_id, status in [
        ("Toyota Corolla 2022 Blanco", "9BRBL3HE5N0123456", "2ZR123456", "A123456", vehicle_type_ids["Automóvil"], brand_ids["Toyota"], model_ids[("Toyota", "Corolla")], fuel_ids["Gasolina"], "Disponible"),
        ("Honda Civic 2021 Gris", "19XFC2F59ME123456", "L15B123456", "B234567", vehicle_type_ids["Automóvil"], brand_ids["Honda"], model_ids[("Honda", "Civic")], fuel_ids["Gasolina"], "Disponible"),
        ("Kia Sportage 2024 Azul", "KNAPU81BPN7123456", "G4NA123456", "C345678", vehicle_type_ids["SUV"], brand_ids["Kia"], model_ids[("Kia", "Sportage")], fuel_ids["Gasolina"], "Disponible"),
        ("Hyundai Tucson 2023 Negra", "KM8JBCAE7NU123456", "G4FJ123456", "F678901", vehicle_type_ids["SUV"], brand_ids["Hyundai"], model_ids[("Hyundai", "Tucson")], fuel_ids["Gasolina"], "Disponible"),
    ]:
        conn.execute(
            """
            UPDATE vehicles
            SET description=?, chassis_no=?, motor_no=?, vehicle_type_id=?, brand_id=?, model_id=?, fuel_type_id=?
            WHERE plate_no=?
            """,
            (description, chassis_no, motor_no, vehicle_type_id, brand_id, model_id, fuel_type_id, plate_no),
        )
    demo_customers = [
        ("María Pérez", "001-0000000-9", "1111", 50000, "Física", "Activo"),
        ("Kevin Lantigua", "001-0000001-7", "2222", 55000, "Física", "Activo"),
        ("Ambar Santos", "001-0000002-5", "3333", 60000, "Física", "Activo"),
        ("José Ortega", "001-0000003-3", "4444", 55000, "Física", "Activo"),
        ("Ana Domínguez", "001-0000004-1", "5555", 45000, "Física", "Activo"),
        ("Comercial Caribe SRL", "101-00000-1", "0004", 150000, "Jurídica", "Activo"),
        ("Transportes Nacionales SRL", "102-00000-2", "5005", 250000, "Jurídica", "Activo"),
    ]
    insert_missing(
        "customers",
        ["name", "cedula", "credit_card_no", "credit_limit", "person_type", "status"],
        demo_customers,
    )
    for name, cedula, credit_card_no, credit_limit, person_type, status in demo_customers:
        conn.execute(
            """
            UPDATE customers
            SET name=?, credit_card_no=?, credit_limit=?, person_type=?
            WHERE cedula=?
            """,
            (name, credit_card_no, credit_limit, person_type, cedula),
        )
    insert_missing(
        "employees",
        ["name", "cedula", "work_shift", "commission_percent", "hire_date", "status"],
        [
            ("Ana Santos", "001-0000003-3", "Matutina", 4, "2024-03-10", "Activo"),
            ("Luis Pérez", "001-0000005-8", "Matutina", 5, "2024-01-15", "Activo"),
            ("María Rodríguez", "001-0000006-6", "Vespertina", 4, "2024-05-20", "Activo"),
            ("Carlos Martínez", "001-0000007-4", "Vespertina", 4.5, "2024-08-01", "Activo"),
        ],
    )
    for name, cedula, work_shift, commission_percent, hire_date, status in [
        ("Ana Santos", "001-0000003-3", "Matutina", 4, "2024-03-10", "Activo"),
        ("Luis Pérez", "001-0000005-8", "Matutina", 5, "2024-01-15", "Activo"),
        ("María Rodríguez", "001-0000006-6", "Vespertina", 4, "2024-05-20", "Activo"),
        ("Carlos Martínez", "001-0000007-4", "Vespertina", 4.5, "2024-08-01", "Activo"),
    ]:
        conn.execute(
            "UPDATE employees SET name=?, work_shift=?, commission_percent=?, hire_date=? WHERE cedula=?",
            (name, work_shift, commission_percent, hire_date, cedula),
        )
    for tire_field in ["tire_front_left", "tire_front_right", "tire_rear_left", "tire_rear_right"]:
        conn.execute(f"UPDATE inspections SET {tire_field}='Buena' WHERE {tire_field}='Bueno'")
        conn.execute(f"UPDATE inspections SET {tire_field}='Mala' WHERE {tire_field}='Malo'")

    for table, column in [
        ("brands", "brand_id"),
        ("models", "model_id"),
        ("vehicle_types", "vehicle_type_id"),
        ("fuel_types", "fuel_type_id"),
    ]:
        conn.execute(
            f"""
            UPDATE {table}
            SET status='Activo'
            WHERE status='Inactivo'
              AND id IN (SELECT {column} FROM vehicles WHERE status!='Inactivo')
            """
        )

    users = [
        ("admin@rentcar.local", "Administrador", "admin", "Activo", "demo"),
        ("empleado@rentcar.local", "Empleado", "empleado", "Activo", "demo"),
    ]
    if ADMIN_EMAIL:
        users.append((ADMIN_EMAIL, ADMIN_EMAIL.split("@")[0], "admin", "Activo", "google"))
    for email, name, role, status, provider in users:
        conn.execute(
            """
            INSERT INTO users (email, name, role, status, provider)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET name=excluded.name, role=excluded.role
            """,
            (email, name, role, status, provider),
        )
    conn.execute("UPDATE users SET status='Activo' WHERE email IN ('admin@rentcar.local', 'empleado@rentcar.local')")
    conn.execute(
        "DELETE FROM users WHERE email NOT IN ('admin@rentcar.local', 'empleado@rentcar.local')"
    )
    conn.commit()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        execute_script(conn)
        seed_data(conn)


def ensure_db_initialized() -> None:
    global DB_INITIALIZED
    if not DB_INITIALIZED:
        init_db()
        DB_INITIALIZED = True


def b64_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def b64_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def sign_payload(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    body = b64_encode(raw)
    sig = hmac.new(SESSION_SECRET.encode(), body.encode(), hashlib.sha256).digest()
    return f"{body}.{b64_encode(sig)}"


def read_payload(token: str) -> dict | None:
    try:
        body, sig = token.split(".", 1)
        expected = b64_encode(hmac.new(SESSION_SECRET.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(b64_decode(body))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def session_cookie_header(value: str, max_age: int = SESSION_MAX_AGE, path: str = "/") -> str:
    return f"{SESSION_COOKIE_NAME}={value}; Path={path}; Max-Age={max_age}; HttpOnly; SameSite=Lax"


def clear_session_cookie_header(path: str = "/") -> str:
    return session_cookie_header("", max_age=0, path=path)


def cookie_values(raw_cookie: str, name: str) -> list[str]:
    values: list[str] = []
    for part in raw_cookie.split(";"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        if key.strip() == name:
            values.append(value.strip().strip('"'))
    if values:
        return values
    try:
        jar = cookies.SimpleCookie(raw_cookie)
    except cookies.CookieError:
        return []
    morsel = jar.get(name)
    return [morsel.value] if morsel else []


def verify_google_token(id_token: str) -> dict:
    if not GOOGLE_CLIENT_ID:
        raise ValueError("GOOGLE_CLIENT_ID no está configurado.")
    query = urllib.parse.urlencode({"id_token": id_token})
    with urllib.request.urlopen(f"https://oauth2.googleapis.com/tokeninfo?{query}", timeout=10) as response:
        data = json.loads(response.read().decode())
    if data.get("aud") != GOOGLE_CLIENT_ID:
        raise ValueError("El token de Google no pertenece a este Client ID.")
    if data.get("email_verified") not in ("true", True):
        raise ValueError("Google no confirmó el correo.")
    return data


def parse_date(value: str | None) -> dt.date | None:
    if not value:
        return None
    return dt.date.fromisoformat(value[:10])


def calculate_days(start: str, end: str) -> int:
    start_date = parse_date(start) or dt.date.today()
    end_date = parse_date(end) or dt.date.today()
    return max((end_date - start_date).days, 1)


def valida_cedula_dominicana(value: str) -> bool:
    cedula = value.replace("-", "").strip()
    multipliers = [1, 2, 1, 2, 1, 2, 1, 2, 1, 2, 1]
    if len(cedula) != 11 or not cedula.isdigit():
        return False
    total = 0
    for index, digit in enumerate(cedula):
        calculation = int(digit) * multipliers[index]
        if calculation < 10:
            total += calculation
        else:
            text = str(calculation)
            total += int(text[0]) + int(text[1])
    return total % 10 == 0


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def format_cedula(value: str) -> str:
    digits = only_digits(value)
    if len(digits) != 11:
        raise ValueError("Cédula debe contener 11 dígitos.")
    return f"{digits[:3]}-{digits[3:10]}-{digits[10]}"


def format_rnc(value: str) -> str:
    digits = only_digits(value)
    if len(digits) == 9:
        return f"{digits[:3]}-{digits[3:8]}-{digits[8]}"
    if len(digits) == 11:
        return f"{digits[:3]}-{digits[3:10]}-{digits[10]}"
    raise ValueError("RNC debe contener 9 u 11 dígitos.")


BASIC_STATUS = {"Activo", "Inactivo"}
VEHICLE_STATUS = {"Disponible", "Rentado", "Mantenimiento", "Inactivo"}
PERSON_TYPES = {"Física", "Jurídica"}
WORK_SHIFTS = {"Matutina", "Vespertina", "Nocturna"}
INSPECTION_STATUS = {"Aprobada", "Pendiente", "Anulada"}
FUEL_AMOUNTS = {"1/4", "1/2", "3/4", "Lleno"}
TIRE_STATUS = {"Buena", "Regular", "Mala"}
RENTAL_STATUS = {"Abierta", "Cerrada", "Cancelada"}
USER_ROLES = {"admin", "empleado"}
USER_STATUS = {"Activo", "Pendiente", "Inactivo"}
CEDULA_RE = re.compile(r"^[0-9]{3}-[0-9]{7}-[0-9]$")
CEDULA_FORMAT_RE = re.compile(r"^([0-9]{11}|[0-9]{3}-[0-9]{7}-[0-9])$")
CEDULA_RNC_RE = re.compile(r"^([0-9]{9}|[0-9]{11}|[0-9]{3}-[0-9]{5,7}-[0-9])$")
CARD_LAST4_RE = re.compile(r"^[0-9]{4}$")
PLATE_RE = re.compile(r"^[A-Z0-9-]{6,10}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def clean_text(body: dict, field: str, label: str, max_len: int = 120, required: bool = True) -> str:
    value = str(body.get(field) or "").strip()
    if required and not value:
        raise ValueError(f"{label} es obligatorio.")
    if len(value) > max_len:
        raise ValueError(f"{label} no puede exceder {max_len} caracteres.")
    body[field] = value
    return value


def clean_status(body: dict, field: str, allowed: set[str], label: str = "Estado") -> str:
    value = clean_text(body, field, label, 30)
    if value not in allowed:
        raise ValueError(f"{label} no es válido.")
    return value


def clean_int(body: dict, field: str, label: str, minimum: int = 1) -> int:
    try:
        value = int(body.get(field))
    except Exception as exc:
        raise ValueError(f"{label} debe ser numérico.") from exc
    if value < minimum:
        raise ValueError(f"{label} debe ser mayor o igual a {minimum}.")
    body[field] = value
    return value


def clean_float(body: dict, field: str, label: str, minimum: float = 0, maximum: float | None = None) -> float:
    try:
        value = float(body.get(field) or 0)
    except Exception as exc:
        raise ValueError(f"{label} debe ser numérico.") from exc
    if value < minimum:
        raise ValueError(f"{label} debe ser mayor o igual a {minimum}.")
    if maximum is not None and value > maximum:
        raise ValueError(f"{label} no puede ser mayor que {maximum}.")
    body[field] = value
    return value


def clean_date(body: dict, field: str, label: str, required: bool = True) -> str:
    value = str(body.get(field) or "").strip()
    if not value:
        if required:
            raise ValueError(f"{label} es obligatoria.")
        body[field] = ""
        return ""
    try:
        dt.date.fromisoformat(value[:10])
    except Exception as exc:
        raise ValueError(f"{label} no tiene un formato válido.") from exc
    body[field] = value[:10]
    return body[field]


def clean_bool(body: dict, field: str) -> int:
    value = body.get(field)
    body[field] = 1 if value in (1, "1", True, "true", "True", "on") else 0
    return body[field]


def validate_crud_payload(key: str, body: dict) -> dict:
    if key in {"tipos-vehiculos", "marcas", "tipos-combustible"}:
        clean_text(body, "description", "Descripción", 80)
        clean_status(body, "status", BASIC_STATUS)
    elif key == "modelos":
        clean_int(body, "brand_id", "Marca")
        clean_text(body, "description", "Descripción", 80)
        clean_status(body, "status", BASIC_STATUS)
    elif key == "vehiculos":
        clean_text(body, "description", "Descripción", 120)
        for field, label in [
            ("chassis_no", "No. chasis"),
            ("motor_no", "No. motor"),
        ]:
            value = clean_text(body, field, label, 30).upper()
            body[field] = value
        plate = clean_text(body, "plate_no", "No. placa", 10).upper()
        if not PLATE_RE.match(plate):
            raise ValueError("No. placa tiene un formato inválido.")
        body["plate_no"] = plate
        for field, label in [
            ("vehicle_type_id", "Tipo de vehículo"),
            ("brand_id", "Marca"),
            ("model_id", "Modelo"),
            ("fuel_type_id", "Tipo de combustible"),
        ]:
            clean_int(body, field, label)
        clean_status(body, "status", VEHICLE_STATUS)
    elif key == "clientes":
        clean_text(body, "name", "Nombre", 100)
        clean_status(body, "person_type", PERSON_TYPES, "Tipo de persona")
        cedula = clean_text(body, "cedula", "Cédula/RNC", 20)
        if not CEDULA_RNC_RE.match(cedula):
            raise ValueError("Cédula/RNC debe usar un formato válido.")
        if body["person_type"] == "Física":
            cedula = format_cedula(cedula)
            if not valida_cedula_dominicana(cedula):
                raise ValueError("Cédula dominicana inválida. Verifica el número ingresado.")
            body["cedula"] = cedula
        else:
            body["cedula"] = format_rnc(cedula)
        card = clean_text(body, "credit_card_no", "Tarjeta CR", 4)
        if not CARD_LAST4_RE.match(card):
            raise ValueError("Tarjeta CR debe contener solo los últimos 4 dígitos.")
        clean_float(body, "credit_limit", "Límite de crédito", 0)
        clean_status(body, "status", BASIC_STATUS)
    elif key == "empleados":
        clean_text(body, "name", "Nombre", 100)
        cedula = clean_text(body, "cedula", "Cédula", 20)
        if not CEDULA_RE.match(cedula):
            raise ValueError("Cédula debe usar el formato 001-0000001-1.")
        clean_status(body, "work_shift", WORK_SHIFTS, "Tanda laboral")
        clean_float(body, "commission_percent", "% comisión", 0, 100)
        clean_date(body, "hire_date", "Fecha de ingreso")
        clean_status(body, "status", BASIC_STATUS)
    return body


def validate_inspection_payload(body: dict) -> dict:
    for field, label in [
        ("vehicle_id", "Vehículo"),
        ("customer_id", "Cliente"),
        ("employee_id", "Empleado que inspecciona"),
    ]:
        clean_int(body, field, label)
    clean_status(body, "fuel_amount", FUEL_AMOUNTS, "Combustible")
    clean_status(body, "status", INSPECTION_STATUS)
    clean_date(body, "inspection_date", "Fecha")
    for field in ["has_scratches", "has_spare_tire", "has_jack", "has_glass_breaks"]:
        clean_bool(body, field)
    for field, label in [
        ("tire_front_left", "Goma delantera izquierda"),
        ("tire_front_right", "Goma delantera derecha"),
        ("tire_rear_left", "Goma trasera izquierda"),
        ("tire_rear_right", "Goma trasera derecha"),
    ]:
        clean_status(body, field, TIRE_STATUS, label)
    clean_text(body, "notes", "Comentario", 300, required=False)
    return body


def validate_rental_payload(body: dict) -> dict:
    for field, label in [
        ("employee_id", "Empleado"),
        ("vehicle_id", "Vehículo"),
        ("customer_id", "Cliente"),
    ]:
        clean_int(body, field, label)
    clean_date(body, "rent_date", "Fecha de renta")
    clean_float(body, "daily_amount", "Monto por día", 1)
    clean_int(body, "days", "Cantidad de días")
    clean_text(body, "comment", "Comentario", 300, required=False)
    return body


def validate_return_payload(body: dict) -> dict:
    clean_date(body, "return_date", "Fecha de devolución")
    clean_text(body, "comment", "Comentario", 300, required=False)
    return body


def validate_user_payload(body: dict) -> dict:
    email = clean_text(body, "email", "Correo Google", 120).lower()
    if not EMAIL_RE.match(email):
        raise ValueError("Correo Google no tiene un formato válido.")
    body["email"] = email
    clean_text(body, "name", "Nombre", 100, required=False)
    clean_status(body, "role", USER_ROLES, "Rol")
    clean_status(body, "status", USER_STATUS, "Estado")
    return body


def validate_user_update_payload(body: dict) -> dict:
    clean_text(body, "name", "Nombre", 100)
    clean_status(body, "role", USER_ROLES, "Rol")
    clean_status(body, "status", BASIC_STATUS, "Estado")
    return body


def ensure_catalog_can_be_inactivated(conn: sqlite3.Connection, table: str, item_id: int) -> None:
    vehicle_columns = {
        "brands": ("brand_id", "esta marca"),
        "models": ("model_id", "este modelo"),
        "vehicle_types": ("vehicle_type_id", "este tipo de vehículo"),
        "fuel_types": ("fuel_type_id", "este tipo de combustible"),
    }
    dependency = vehicle_columns.get(table)
    if not dependency:
        return
    column, label = dependency
    total = conn.execute(
        f"SELECT COUNT(*) AS total FROM vehicles WHERE {column}=? AND status!='Inactivo'",
        (item_id,),
    ).fetchone()["total"]
    if total:
        raise ValueError(f"No es posible inactivar {label} porque posee vehículos asociados.")


def operational_vehicle_sql(where: str = "") -> str:
    return f"""
        SELECT v.*
        FROM vehicles v
        JOIN vehicle_types vt ON vt.id = v.vehicle_type_id
        JOIN brands b ON b.id = v.brand_id
        JOIN models m ON m.id = v.model_id
        JOIN fuel_types f ON f.id = v.fuel_type_id
        WHERE v.status!='Inactivo'
          AND vt.status='Activo'
          AND b.status='Activo'
          AND m.status='Activo'
          AND f.status='Activo'
          {where}
    """


def get_operational_vehicle(conn: sqlite3.Connection, vehicle_id: int):
    return conn.execute(operational_vehicle_sql("AND v.id=?"), (vehicle_id,)).fetchone()


def active_admin_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS total FROM users WHERE role='admin' AND status='Activo'").fetchone()["total"]


class App(BaseHTTPRequestHandler):
    server_version = "RentCarHTTP/1.0"

    def do_GET(self) -> None:
        self.dispatch("GET")

    def do_POST(self) -> None:
        self.dispatch("POST")

    def do_PUT(self) -> None:
        self.dispatch("PUT")

    def do_DELETE(self) -> None:
        self.dispatch("DELETE")

    def dispatch(self, method: str) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if path.startswith("/api/"):
                return self.handle_api(method, path, query)
            return self.serve_static(path)
        except PermissionError as exc:
            self.json_response({"error": str(exc)}, 403)
        except ValueError as exc:
            self.json_response({"error": str(exc)}, 400)
        except sqlite3.IntegrityError as exc:
            self.json_response({"error": friendly_integrity_error(str(exc))}, 409)
        except Exception as exc:
            self.json_response({"error": f"Error interno: {exc}"}, 500)

    def cookie_header(self) -> str:
        values: list[str] = []
        if hasattr(self.headers, "get_all"):
            values.extend(self.headers.get_all("Cookie", []) or [])
        for key in ("Cookie", "cookie", "HTTP_COOKIE"):
            value = self.headers.get(key, "") if hasattr(self.headers, "get") else ""
            if value and value not in values:
                values.append(value)
        return "; ".join(values)

    def current_user(self) -> dict | None:
        raw_cookie = self.cookie_header()
        for token in cookie_values(raw_cookie, SESSION_COOKIE_NAME):
            payload = read_payload(token)
            if not payload:
                continue
            with db() as conn:
                row = conn.execute(
                    "SELECT id, email, name, role, status FROM users WHERE id=?",
                    (payload.get("uid"),),
                ).fetchone()
            if row and row["status"] == "Activo":
                return dict(row)
        return None

    def require_user(self) -> dict:
        user = self.current_user()
        if not user:
            raise PermissionError("Debe iniciar sesión.")
        return user

    def require_admin(self) -> dict:
        user = self.require_user()
        if user["role"] != "admin":
            raise PermissionError("Esta acción requiere rol admin.")
        return user

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def set_session_cookie(self, user: sqlite3.Row) -> None:
        payload = {
            "uid": user["id"],
            "email": user["email"],
            "role": user["role"],
            "exp": int(time.time()) + SESSION_MAX_AGE,
        }
        self.extra_headers = [
            ("Set-Cookie", clear_session_cookie_header("/api")),
            ("Set-Cookie", session_cookie_header(sign_payload(payload))),
        ]

    def clear_session_cookie(self) -> None:
        self.extra_headers = [
            ("Set-Cookie", clear_session_cookie_header("/api")),
            ("Set-Cookie", clear_session_cookie_header("/")),
        ]

    def json_response(self, data, status: int = 200, extra_headers: list[tuple[str, str]] | None = None) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        for key, value in getattr(self, "extra_headers", []):
            self.send_header(key, value)
        for key, value in extra_headers or []:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)
        self.extra_headers = []

    def text_response(self, data: str, content_type: str, status: int = 200) -> None:
        raw = data.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def binary_response(self, data: bytes, content_type: str, filename: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_static(self, path: str) -> None:
        if path in ("", "/"):
            file_path = STATIC_DIR / "index.html"
        else:
            file_path = (STATIC_DIR / path.lstrip("/")).resolve()
            if not str(file_path).startswith(str(STATIC_DIR.resolve())):
                self.send_error(404)
                return
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404)
            return
        content_types = {
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".svg": "image/svg+xml",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
        }
        raw = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_types.get(file_path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def handle_api(self, method: str, path: str, query: dict[str, list[str]]) -> None:
        parts = [part for part in path.split("/") if part][1:]
        if parts == ["config"] and method == "GET":
            return self.json_response({"googleClientId": GOOGLE_CLIENT_ID, "demoAuth": DEMO_AUTH})
        if parts[:1] == ["auth"]:
            return self.handle_auth(method, parts)

        user = self.require_user()
        if parts == ["summary"] and method == "GET":
            return self.handle_summary()
        if parts == ["lookups"] and method == "GET":
            return self.handle_lookups()
        if parts[:1] == ["usuarios"]:
            self.require_admin()
            return self.handle_users(method, parts)
        if parts[:1] == ["inspecciones"]:
            return self.handle_inspections(method, parts, query, user)
        if parts[:1] == ["rentas"]:
            return self.handle_rentals(method, parts, query, user)
        if parts[:1] == ["reportes"]:
            return self.handle_reports(method, parts, query)
        if parts and parts[0] in ROUTES:
            return self.handle_crud(method, parts, query, user)
        raise ValueError("Ruta API no encontrada.")

    def handle_auth(self, method: str, parts: list[str]) -> None:
        if parts == ["auth", "me"] and method == "GET":
            return self.json_response({"user": self.current_user()})
        if parts == ["auth", "logout"] and method == "POST":
            self.clear_session_cookie()
            return self.json_response({"ok": True})
        if parts == ["auth", "password"] and method == "POST":
            body = self.read_json()
            username = str(body.get("username") or "").strip().lower()
            password = str(body.get("password") or "")
            accounts = {
                "admin": "admin@rentcar.local",
                "empleado": "empleado@rentcar.local",
            }
            if password != "12345" or username not in accounts:
                raise PermissionError("Usuario o contraseña inválidos.")
            with db() as conn:
                user = conn.execute(
                    "SELECT id, email, name, role, status FROM users WHERE email=?",
                    (accounts[username],),
                ).fetchone()
                if not user or user["status"] != "Activo":
                    raise PermissionError("Usuario no autorizado.")
                conn.execute("UPDATE users SET last_login=? WHERE id=?", (now_iso(), user["id"]))
                conn.commit()
            self.set_session_cookie(user)
            return self.json_response({"user": dict(user)})
        if parts == ["auth", "demo"] and method == "POST":
            if not DEMO_AUTH:
                raise PermissionError("El acceso demo está desactivado.")
            body = self.read_json()
            role = "admin" if body.get("role") == "admin" else "empleado"
            email = "admin@rentcar.local" if role == "admin" else "empleado@rentcar.local"
            with db() as conn:
                user = conn.execute(
                    "SELECT id, email, name, role, status FROM users WHERE email=?",
                    (email,),
                ).fetchone()
                conn.execute("UPDATE users SET last_login=? WHERE id=?", (now_iso(), user["id"]))
                conn.commit()
            self.set_session_cookie(user)
            return self.json_response({"user": dict(user)})
        if parts == ["auth", "google"] and method == "POST":
            body = self.read_json()
            profile = verify_google_token(body.get("credential", ""))
            email = profile["email"].strip().lower()
            name = profile.get("name") or email.split("@")[0]
            with db() as conn:
                row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
                if not row:
                    conn.execute(
                        "INSERT INTO users (email, name, role, status, provider) VALUES (?, ?, 'empleado', 'Pendiente', 'google')",
                        (email, name),
                    )
                    conn.commit()
                    self.json_response({"error": "Usuario pendiente de aprobación por un administrador."}, 403)
                    return
                if row["status"] != "Activo":
                    raise PermissionError("Usuario no autorizado o pendiente de aprobación.")
                conn.execute("UPDATE users SET name=?, last_login=? WHERE id=?", (name, now_iso(), row["id"]))
                conn.commit()
                user = conn.execute(
                    "SELECT id, email, name, role, status FROM users WHERE id=?",
                    (row["id"],),
                ).fetchone()
            self.set_session_cookie(user)
            return self.json_response({"user": dict(user)})
        raise ValueError("Ruta de autenticacion no encontrada.")

    def log_action(self, conn: sqlite3.Connection, user: dict, action: str, entity: str, entity_id: int | None) -> None:
        conn.execute(
            "INSERT INTO audit_log (user_email, action, entity, entity_id) VALUES (?, ?, ?, ?)",
            (user["email"], action, entity, entity_id),
        )

    def handle_summary(self) -> None:
        with db() as conn:
            data = {
                "vehiculosDisponibles": conn.execute(operational_vehicle_sql("AND v.status='Disponible'").replace("SELECT v.*", "SELECT COUNT(*) AS total")).fetchone()["total"],
                "vehiculosRentados": conn.execute(operational_vehicle_sql("AND v.status='Rentado'").replace("SELECT v.*", "SELECT COUNT(*) AS total")).fetchone()["total"],
                "rentasAbiertas": conn.execute("SELECT COUNT(*) AS total FROM rentals WHERE status='Abierta'").fetchone()["total"],
                "clientesActivos": conn.execute("SELECT COUNT(*) AS total FROM customers WHERE status='Activo'").fetchone()["total"],
                "ingresos": conn.execute("SELECT COALESCE(SUM(total_amount), 0) AS total FROM rentals WHERE status='Cerrada'").fetchone()["total"],
            }
        self.json_response(data)

    def handle_lookups(self) -> None:
        with db() as conn:
            data = {
                "tiposVehiculos": rows_to_dicts(conn.execute("SELECT * FROM vehicle_types ORDER BY description")),
                "marcas": rows_to_dicts(conn.execute("SELECT * FROM brands ORDER BY description")),
                "modelos": rows_to_dicts(conn.execute("SELECT * FROM models ORDER BY description")),
                "combustibles": rows_to_dicts(conn.execute("SELECT * FROM fuel_types ORDER BY description")),
                "vehiculos": rows_to_dicts(conn.execute(operational_vehicle_sql("ORDER BY v.description"))),
                "clientes": rows_to_dicts(conn.execute("SELECT * FROM customers ORDER BY name")),
                "empleados": rows_to_dicts(conn.execute("SELECT * FROM employees ORDER BY name")),
            }
        self.json_response(data)

    def select_for_route(self, key: str, item_id: int | None = None) -> tuple[str, list]:
        table = ROUTES[key]["table"]
        params: list = []
        alias = table
        if table == "vehicles":
            alias = "v"
            sql = """
                SELECT v.*, vt.description AS vehicle_type, b.description AS brand,
                       m.description AS model, f.description AS fuel_type
                FROM vehicles v
                JOIN vehicle_types vt ON vt.id = v.vehicle_type_id
                JOIN brands b ON b.id = v.brand_id
                JOIN models m ON m.id = v.model_id
                JOIN fuel_types f ON f.id = v.fuel_type_id
            """
        elif table == "models":
            alias = "m"
            sql = """
                SELECT m.*, b.description AS brand
                FROM models m
                JOIN brands b ON b.id = m.brand_id
            """
        else:
            sql = f"SELECT * FROM {table}"
        if item_id:
            sql += f" WHERE {alias}.id=?"
            params.append(item_id)
        sql += f" ORDER BY {alias}.id DESC"
        return sql, params

    def handle_crud(self, method: str, parts: list[str], query: dict[str, list[str]], user: dict) -> None:
        key = parts[0]
        route = ROUTES[key]
        table = route["table"]
        item_id = int(parts[1]) if len(parts) > 1 else None
        if method in ("POST", "PUT", "DELETE") and route["admin_write"] and user["role"] != "admin":
            raise PermissionError("Solo admin puede modificar este módulo.")
        with db() as conn:
            if method == "GET":
                sql, params = self.select_for_route(key, item_id)
                rows = rows_to_dicts(conn.execute(sql, params))
                return self.json_response(rows[0] if item_id and rows else rows)
            if method == "POST":
                body = validate_crud_payload(key, self.read_json())
                fields = route["fields"]
                values = [body.get(field) for field in fields]
                placeholders = ", ".join(["?"] * len(fields))
                cur = conn.execute(
                    f"INSERT INTO {table} ({', '.join(fields)}) VALUES ({placeholders})",
                    values,
                )
                self.log_action(conn, user, "crear", table, cur.lastrowid)
                conn.commit()
                return self.json_response({"id": cur.lastrowid}, 201)
            if method == "PUT" and item_id:
                body = validate_crud_payload(key, self.read_json())
                fields = route["fields"]
                assignments = ", ".join([f"{field}=?" for field in fields])
                conn.execute(
                    f"UPDATE {table} SET {assignments} WHERE id=?",
                    [body.get(field) for field in fields] + [item_id],
                )
                self.log_action(conn, user, "actualizar", table, item_id)
                conn.commit()
                return self.json_response({"ok": True})
            if method == "DELETE" and item_id:
                current = conn.execute(f"SELECT status FROM {table} WHERE id=?", (item_id,)).fetchone()
                if not current:
                    raise ValueError("Registro no encontrado.")
                if table == "vehicles":
                    status = "Disponible" if current["status"] == "Inactivo" else "Inactivo"
                else:
                    status = "Activo" if current["status"] == "Inactivo" else "Inactivo"
                if status == "Inactivo":
                    ensure_catalog_can_be_inactivated(conn, table, item_id)
                conn.execute(f"UPDATE {table} SET status=? WHERE id=?", (status, item_id))
                self.log_action(conn, user, "cambiar_estado", table, item_id)
                conn.commit()
                return self.json_response({"ok": True})
        raise ValueError("Operación CRUD inválida.")

    def handle_users(self, method: str, parts: list[str]) -> None:
        item_id = int(parts[1]) if len(parts) > 1 else None
        with db() as conn:
            if method == "GET":
                rows = conn.execute(
                    """
                    SELECT id, name, role, status
                    FROM users
                    WHERE email IN ('admin@rentcar.local', 'empleado@rentcar.local')
                    ORDER BY role
                    """
                ).fetchall()
                return self.json_response(rows_to_dicts(rows))
            if method == "POST":
                body = validate_user_payload(self.read_json())
                cur = conn.execute(
                    "INSERT INTO users (email, name, role, status, provider) VALUES (?, ?, ?, ?, 'google')",
                    (
                        body["email"].strip().lower(),
                        body.get("name") or body["email"].split("@")[0],
                        body.get("role", "empleado"),
                        body.get("status", "Activo"),
                    ),
                )
                conn.commit()
                return self.json_response({"id": cur.lastrowid}, 201)
            if method == "PUT" and item_id:
                body = validate_user_update_payload(self.read_json())
                current = conn.execute("SELECT role, status FROM users WHERE id=?", (item_id,)).fetchone()
                if not current:
                    raise ValueError("Usuario no encontrado.")
                removes_active_admin = (
                    current["role"] == "admin"
                    and current["status"] == "Activo"
                    and (body.get("role") != "admin" or body.get("status") != "Activo")
                )
                if removes_active_admin and active_admin_count(conn) <= 1:
                    raise ValueError("No se puede inactivar el único administrador activo.")
                conn.execute(
                    "UPDATE users SET name=?, role=?, status=? WHERE id=?",
                    (body.get("name", ""), body.get("role", "empleado"), body.get("status", "Activo"), item_id),
                )
                conn.commit()
                return self.json_response({"ok": True})
            if method == "DELETE" and item_id:
                current = conn.execute(
                    "SELECT role, status FROM users WHERE id=? AND email IN ('admin@rentcar.local', 'empleado@rentcar.local')",
                    (item_id,),
                ).fetchone()
                if not current:
                    raise ValueError("Usuario no encontrado.")
                status = "Inactivo" if current["status"] == "Activo" else "Activo"
                if current["role"] == "admin" and status == "Inactivo" and active_admin_count(conn) <= 1:
                    raise ValueError("No se puede inactivar el único administrador activo.")
                conn.execute("UPDATE users SET status=? WHERE id=?", (status, item_id))
                conn.commit()
                return self.json_response({"ok": True})
        raise ValueError("Operación de usuarios inválida.")

    def inspection_rows(self, conn: sqlite3.Connection, item_id: int | None = None) -> list[dict]:
        sql = """
            SELECT i.*, v.description AS vehicle, c.name AS customer, e.name AS employee
            FROM inspections i
            JOIN vehicles v ON v.id = i.vehicle_id
            JOIN customers c ON c.id = i.customer_id
            JOIN employees e ON e.id = i.employee_id
        """
        params = []
        if item_id:
            sql += " WHERE i.id=?"
            params.append(item_id)
        sql += " ORDER BY i.id DESC"
        return rows_to_dicts(conn.execute(sql, params))

    def handle_inspections(self, method: str, parts: list[str], query: dict[str, list[str]], user: dict) -> None:
        item_id = int(parts[1]) if len(parts) > 1 else None
        fields = [
            "vehicle_id",
            "customer_id",
            "has_scratches",
            "fuel_amount",
            "has_spare_tire",
            "has_jack",
            "has_glass_breaks",
            "tire_front_left",
            "tire_front_right",
            "tire_rear_left",
            "tire_rear_right",
            "notes",
            "inspection_date",
            "employee_id",
            "status",
        ]
        with db() as conn:
            if method == "GET":
                rows = self.inspection_rows(conn, item_id)
                return self.json_response(rows[0] if item_id and rows else rows)
            if method == "POST":
                body = self.read_json()
                body.setdefault("inspection_date", dt.date.today().isoformat())
                body = validate_inspection_payload(body)
                placeholders = ", ".join(["?"] * len(fields))
                cur = conn.execute(
                    f"INSERT INTO inspections ({', '.join(fields)}) VALUES ({placeholders})",
                    [body.get(field) for field in fields],
                )
                self.log_action(conn, user, "crear", "inspections", cur.lastrowid)
                conn.commit()
                return self.json_response({"id": cur.lastrowid}, 201)
            if method == "PUT" and item_id:
                body = validate_inspection_payload(self.read_json())
                assignments = ", ".join([f"{field}=?" for field in fields])
                conn.execute(
                    f"UPDATE inspections SET {assignments} WHERE id=?",
                    [body.get(field) for field in fields] + [item_id],
                )
                self.log_action(conn, user, "actualizar", "inspections", item_id)
                conn.commit()
                return self.json_response({"ok": True})
            if method == "DELETE" and item_id:
                current = conn.execute("SELECT status FROM inspections WHERE id=?", (item_id,)).fetchone()
                if not current:
                    raise ValueError("Inspección no encontrada.")
                next_status = "Aprobada" if current["status"] == "Anulada" else "Anulada"
                conn.execute("UPDATE inspections SET status=? WHERE id=?", (next_status, item_id))
                self.log_action(conn, user, "cambiar_estado", "inspections", item_id)
                conn.commit()
                return self.json_response({"ok": True})
        raise ValueError("Operación de inspección inválida.")

    def rental_rows(self, conn: sqlite3.Connection, query: dict[str, list[str]], item_id: int | None = None) -> list[dict]:
        sql = """
            SELECT r.*, v.description AS vehicle, v.plate_no, c.name AS customer,
                   e.name AS employee, vt.description AS vehicle_type
            FROM rentals r
            JOIN vehicles v ON v.id = r.vehicle_id
            JOIN vehicle_types vt ON vt.id = v.vehicle_type_id
            JOIN customers c ON c.id = r.customer_id
            JOIN employees e ON e.id = r.employee_id
            WHERE 1=1
        """
        params: list = []
        if item_id:
            sql += " AND r.id=?"
            params.append(item_id)
        filters = {
            "customer_id": "r.customer_id",
            "vehicle_id": "r.vehicle_id",
            "employee_id": "r.employee_id",
            "status": "r.status",
        }
        for key, column in filters.items():
            value = query.get(key, [""])[0]
            if value:
                sql += f" AND {column}=?"
                params.append(value)
        date_from = query.get("from", [""])[0]
        date_to = query.get("to", [""])[0]
        if date_from:
            sql += " AND r.rent_date>=?"
            params.append(date_from)
        if date_to:
            sql += " AND r.rent_date<=?"
            params.append(date_to)
        sql += " ORDER BY r.id DESC"
        return rows_to_dicts(conn.execute(sql, params))

    def handle_rentals(self, method: str, parts: list[str], query: dict[str, list[str]], user: dict) -> None:
        item_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        with db() as conn:
            if method == "GET":
                rows = self.rental_rows(conn, query, item_id)
                return self.json_response(rows[0] if item_id and rows else rows)
            if method == "POST" and len(parts) == 1:
                body = validate_rental_payload(self.read_json())
                vehicle = get_operational_vehicle(conn, body["vehicle_id"])
                if not vehicle or vehicle["status"] != "Disponible":
                    raise ValueError("El vehículo no está disponible para renta.")
                customer = conn.execute("SELECT * FROM customers WHERE id=?", (body["customer_id"],)).fetchone()
                if not customer or customer["status"] != "Activo":
                    raise ValueError("El cliente no está activo.")
                inspection = conn.execute(
                    """
                    SELECT * FROM inspections
                    WHERE vehicle_id=? AND customer_id=? AND status='Aprobada'
                    ORDER BY inspection_date DESC, id DESC LIMIT 1
                    """,
                    (body["vehicle_id"], body["customer_id"]),
                ).fetchone()
                if not inspection:
                    raise ValueError("Debe registrar una inspección aprobada antes de rentar.")
                rent_date = body.get("rent_date") or dt.date.today().isoformat()
                days = max(int(body.get("days") or 1), 1)
                daily_amount = float(body.get("daily_amount") or 0)
                cur = conn.execute(
                    """
                    INSERT INTO rentals
                    (employee_id, vehicle_id, customer_id, rent_date, daily_amount, days, total_amount, comment, status, inspection_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Abierta', ?)
                    """,
                    (
                        body["employee_id"],
                        body["vehicle_id"],
                        body["customer_id"],
                        rent_date,
                        daily_amount,
                        days,
                        daily_amount * days,
                        body.get("comment", ""),
                        inspection["id"],
                    ),
                )
                conn.execute("UPDATE vehicles SET status='Rentado' WHERE id=?", (body["vehicle_id"],))
                self.log_action(conn, user, "crear", "rentals", cur.lastrowid)
                conn.commit()
                return self.json_response({"id": cur.lastrowid}, 201)
            if method == "PUT" and item_id:
                body = validate_rental_payload(self.read_json())
                rental = conn.execute("SELECT * FROM rentals WHERE id=?", (item_id,)).fetchone()
                if not rental:
                    raise ValueError("Renta no encontrada.")
                if rental["status"] != "Abierta":
                    raise ValueError("Solo se pueden editar rentas abiertas.")
                vehicle = get_operational_vehicle(conn, body["vehicle_id"])
                if not vehicle:
                    raise ValueError("El vehículo no está disponible para renta.")
                if body["vehicle_id"] != rental["vehicle_id"] and vehicle["status"] != "Disponible":
                    raise ValueError("El vehículo no está disponible para renta.")
                customer = conn.execute("SELECT * FROM customers WHERE id=?", (body["customer_id"],)).fetchone()
                if not customer or customer["status"] != "Activo":
                    raise ValueError("El cliente no está activo.")
                inspection = conn.execute(
                    """
                    SELECT * FROM inspections
                    WHERE vehicle_id=? AND customer_id=? AND status='Aprobada'
                    ORDER BY inspection_date DESC, id DESC LIMIT 1
                    """,
                    (body["vehicle_id"], body["customer_id"]),
                ).fetchone()
                if not inspection:
                    raise ValueError("Debe registrar una inspección aprobada antes de rentar.")
                rent_date = body.get("rent_date") or rental["rent_date"]
                days = max(int(body.get("days") or rental["days"] or 1), 1)
                daily_amount = float(body.get("daily_amount") or 0)
                conn.execute(
                    """
                    UPDATE rentals
                    SET employee_id=?, vehicle_id=?, customer_id=?, rent_date=?,
                        daily_amount=?, days=?, total_amount=?, comment=?, inspection_id=?
                    WHERE id=?
                    """,
                    (
                        body["employee_id"],
                        body["vehicle_id"],
                        body["customer_id"],
                        rent_date,
                        daily_amount,
                        days,
                        daily_amount * days,
                        body.get("comment", ""),
                        inspection["id"],
                        item_id,
                    ),
                )
                if body["vehicle_id"] != rental["vehicle_id"]:
                    conn.execute("UPDATE vehicles SET status='Disponible' WHERE id=?", (rental["vehicle_id"],))
                    conn.execute("UPDATE vehicles SET status='Rentado' WHERE id=?", (body["vehicle_id"],))
                self.log_action(conn, user, "actualizar", "rentals", item_id)
                conn.commit()
                return self.json_response({"ok": True})
            if method == "POST" and len(parts) == 3 and parts[2] == "devolver" and item_id:
                body = validate_return_payload(self.read_json())
                rental = conn.execute("SELECT * FROM rentals WHERE id=?", (item_id,)).fetchone()
                if not rental or rental["status"] != "Abierta":
                    raise ValueError("La renta no está abierta.")
                return_date = body.get("return_date") or dt.date.today().isoformat()
                if parse_date(return_date) < parse_date(rental["rent_date"]):
                    raise ValueError("La fecha de devolución no puede ser anterior a la fecha de renta.")
                days = calculate_days(rental["rent_date"], return_date)
                total = days * float(rental["daily_amount"])
                comment = (rental["comment"] or "") + ("\n" + body.get("comment", "") if body.get("comment") else "")
                conn.execute(
                    """
                    UPDATE rentals
                    SET return_date=?, days=?, total_amount=?, comment=?, status='Cerrada'
                    WHERE id=?
                    """,
                    (return_date, days, total, comment.strip(), item_id),
                )
                conn.execute("UPDATE vehicles SET status='Disponible' WHERE id=?", (rental["vehicle_id"],))
                self.log_action(conn, user, "devolver", "rentals", item_id)
                conn.commit()
                return self.json_response({"ok": True, "days": days, "total": total})
            if method == "POST" and len(parts) == 3 and parts[2] == "reabrir" and item_id:
                rental = conn.execute("SELECT * FROM rentals WHERE id=?", (item_id,)).fetchone()
                if not rental:
                    raise ValueError("Renta no encontrada.")
                if rental["status"] == "Abierta":
                    return self.json_response({"ok": True})
                vehicle = get_operational_vehicle(conn, rental["vehicle_id"])
                if not vehicle or vehicle["status"] != "Disponible":
                    raise ValueError("El vehículo no está disponible para reabrir esta renta.")
                conn.execute(
                    "UPDATE rentals SET status='Abierta', return_date=NULL WHERE id=?",
                    (item_id,),
                )
                conn.execute("UPDATE vehicles SET status='Rentado' WHERE id=?", (rental["vehicle_id"],))
                self.log_action(conn, user, "reabrir", "rentals", item_id)
                conn.commit()
                return self.json_response({"ok": True})
            if method == "DELETE" and item_id:
                rental = conn.execute("SELECT * FROM rentals WHERE id=?", (item_id,)).fetchone()
                if not rental:
                    raise ValueError("Renta no encontrada.")
                if rental["status"] == "Abierta":
                    conn.execute("UPDATE vehicles SET status='Disponible' WHERE id=?", (rental["vehicle_id"],))
                conn.execute("UPDATE rentals SET status='Cancelada' WHERE id=?", (item_id,))
                self.log_action(conn, user, "cancelar", "rentals", item_id)
                conn.commit()
                return self.json_response({"ok": True})
        raise ValueError("Operación de renta inválida.")

    def handle_reports(self, method: str, parts: list[str], query: dict[str, list[str]]) -> None:
        if method != "GET" or len(parts) < 2 or parts[1] != "rentas":
            raise ValueError("Reporte no encontrado.")
        with db() as conn:
            sql = """
                SELECT r.id, r.rent_date, r.return_date, r.status, r.daily_amount, r.days,
                       r.total_amount, c.name AS customer, v.description AS vehicle,
                       v.plate_no, vt.description AS vehicle_type, e.name AS employee
                FROM rentals r
                JOIN customers c ON c.id = r.customer_id
                JOIN vehicles v ON v.id = r.vehicle_id
                JOIN vehicle_types vt ON vt.id = v.vehicle_type_id
                JOIN employees e ON e.id = r.employee_id
                WHERE 1=1
            """
            params: list = []
            if query.get("from", [""])[0]:
                sql += " AND r.rent_date>=?"
                params.append(query["from"][0])
            if query.get("to", [""])[0]:
                sql += " AND r.rent_date<=?"
                params.append(query["to"][0])
            vehicle_type_filter = "Todos"
            if query.get("vehicle_type_id", [""])[0]:
                sql += " AND v.vehicle_type_id=?"
                params.append(query["vehicle_type_id"][0])
                vehicle_type = conn.execute(
                    "SELECT description FROM vehicle_types WHERE id=?",
                    (query["vehicle_type_id"][0],),
                ).fetchone()
                if vehicle_type:
                    vehicle_type_filter = vehicle_type["description"]
            rows = rows_to_dicts(conn.execute(sql + " ORDER BY r.rent_date DESC, r.id DESC", params))
        summary: dict[str, dict] = {}
        for row in rows:
            item = summary.setdefault(row["vehicle_type"], {"vehicle_type": row["vehicle_type"], "count": 0, "total": 0})
            item["count"] += 1
            item["total"] += row["total_amount"] or 0
        total = sum(row["total_amount"] or 0 for row in rows)
        if len(parts) == 3 and parts[2] == "csv":
            output = []
            header = ["No. Renta", "Fecha de renta", "Fecha de devolución", "Estado", "Cliente", "Vehículo", "Tipo", "Empleado", "Días", "Monto diario", "Total"]
            output.append(",".join(header))
            for row in rows:
                values = [
                    row["id"],
                    row["rent_date"],
                    row.get("return_date") or "",
                    row["status"],
                    row["customer"],
                    row["vehicle"],
                    row["vehicle_type"],
                    row["employee"],
                    row["days"],
                    row["daily_amount"],
                    row["total_amount"],
                ]
                output.append(",".join(csv_escape(value) for value in values))
            return self.text_response("\ufeff" + "\n".join(output), "text/csv; charset=utf-8")
        if len(parts) == 3 and parts[2] == "pdf":
            filters = {
                "Desde": query.get("from", [""])[0] or "Sin filtro",
                "Hasta": query.get("to", [""])[0] or "Sin filtro",
                "Tipo de vehículo": vehicle_type_filter,
            }
            pdf = build_rentals_pdf(rows, list(summary.values()), total, filters)
            return self.binary_response(pdf, "application/pdf", "reporte-rentas.pdf")
        self.json_response({"rows": rows, "summary": list(summary.values()), "total": total})

    def log_message(self, fmt: str, *args) -> None:
        return


def csv_escape(value) -> str:
    value = "" if value is None else str(value)
    if any(char in value for char in [",", '"', "\n"]):
        return '"' + value.replace('"', '""') + '"'
    return value


def money_text(value) -> str:
    return f"RD${float(value or 0):,.2f}"


def pdf_escape(value) -> str:
    text = str(value or "")
    if "Ã" in text or "Â" in text:
        try:
            text = text.encode("latin-1").decode("utf-8")
        except UnicodeError:
            pass
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_text(value, max_len: int | None = None) -> str:
    text = str(value or "")
    if max_len and len(text) > max_len:
        text = text[: max_len - 3] + "..."
    return pdf_escape(text)


def pdf_line(x: int, y: int, text: str, size: int = 9, font: str = "F1") -> str:
    return f"0.07 0.08 0.09 rg BT /{font} {size} Tf {x} {y} Td ({pdf_text(text)}) Tj ET\n"


def build_pdf(pages: list[str]) -> bytes:
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids ["
        + b" ".join(f"{3 + index * 2} 0 R".encode("ascii") for index in range(len(pages)))
        + b"] /Count "
        + str(len(pages)).encode("ascii")
        + b" >>",
    ]
    for index, content in enumerate(pages):
        page_id = 3 + index * 2
        stream_id = page_id + 1
        stream = content.encode("latin-1", "replace")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >> /F2 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >> >> >> /Contents {stream_id} 0 R >>".encode("ascii")
        )
        objects.append(b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream")
    output = io.BytesIO()
    output.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(output.tell())
        output.write(f"{number} 0 obj\n".encode("ascii"))
        output.write(obj)
        output.write(b"\nendobj\n")
    xref_at = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode("ascii")
    )
    return output.getvalue()


def build_rentals_pdf(rows: list[dict], summary: list[dict], total: float, filters: dict[str, str]) -> bytes:
    pages: list[str] = []
    lines: list[str] = []
    y = 674
    generated_at = dt.datetime.now()
    status_counts = {
        "Abierta": sum(1 for row in rows if row["status"] == "Abierta"),
        "Cerrada": sum(1 for row in rows if row["status"] == "Cerrada"),
        "Cancelada": sum(1 for row in rows if row["status"] == "Cancelada"),
    }

    def new_page():
        nonlocal lines, y
        if lines:
            pages.append("".join(lines))
        lines = []
        y = 674
        lines.append("1 1 1 rg 0 0 612 792 re f\n")
        lines.append(pdf_line(42, 746, "RENTCAR", 20, "F2"))
        lines.append(pdf_line(42, 718, "REPORTE DE RENTAS Y DEVOLUCIONES", 12, "F2"))
        lines.append(pdf_line(382, 746, f"Fecha de generación: {generated_at.date().isoformat()}", 9, "F1"))
        lines.append(pdf_line(382, 731, f"Hora de generación: {generated_at.strftime('%H:%M:%S')}", 9, "F1"))
        lines.append("0.82 0.85 0.88 RG 42 700 528 0.8 re S\n")

    def ensure_space(height: int = 18):
        nonlocal y
        if y < 82 + height:
            new_page()

    new_page()
    lines.append(pdf_line(42, y, "Período", 11, "F2"))
    y -= 16
    lines.append(pdf_line(54, y, f"Desde: {filters['Desde']}     Hasta: {filters['Hasta']}     Tipo de vehículo: {filters['Tipo de vehículo']}", 9, "F1"))
    y -= 26

    lines.append(pdf_line(42, y, "Resumen ejecutivo", 11, "F2"))
    y -= 18
    cards = [
        ("Total de rentas", len(rows)),
        ("Rentas abiertas", status_counts["Abierta"]),
        ("Rentas cerradas", status_counts["Cerrada"]),
        ("Rentas canceladas", status_counts["Cancelada"]),
        ("Total generado", money_text(total)),
    ]
    x = 42
    for label, value in cards:
        lines.append("0.96 0.97 0.98 rg {0} {1} 98 42 re f\n".format(x, y - 28))
        lines.append("0.82 0.85 0.88 RG {0} {1} 98 42 re S\n".format(x, y - 28))
        lines.append(pdf_line(x + 8, y - 7, label, 8, "F1"))
        lines.append(pdf_line(x + 8, y - 25, str(value), 10, "F2"))
        x += 107
    y -= 58

    lines.append(pdf_line(42, y, "Resumen por tipo de vehículo", 11, "F2"))
    y -= 16
    if summary:
        for item in summary:
            ensure_space()
            lines.append(pdf_line(54, y, f"{item['vehicle_type']}: {item['count']} rentas - {money_text(item['total'])}", 9, "F1"))
            y -= 14
    else:
        lines.append(pdf_line(54, y, "Sin rentas para los filtros seleccionados.", 9, "F1"))
        y -= 14

    y -= 12
    ensure_space(50)
    lines.append(pdf_line(42, y, "Detalle de rentas", 11, "F2"))
    y -= 18
    lines.append("0.93 0.94 0.96 rg 42 {0} 528 20 re f\n".format(y - 5))
    lines.append("0.78 0.81 0.85 RG 42 {0} 528 20 re S\n".format(y - 5))
    headers = [
        ("ID", 46),
        ("Cliente", 68),
        ("Vehículo", 144),
        ("Tipo", 223),
        ("Fecha inicio", 285),
        ("Fecha fin", 336),
        ("Días", 385),
        ("Estado", 420),
        ("Total", 492),
    ]
    for label, x in headers:
        lines.append(pdf_line(x, y, label, 8, "F2"))
    y -= 18
    for row in rows:
        ensure_space(22)
        lines.append("0.88 0.90 0.92 RG 42 {0} 528 16 re S\n".format(y - 4))
        values = [
            (row["id"], 46, 4),
            (row["customer"], 68, 14),
            (row["vehicle"], 144, 14),
            (row["vehicle_type"], 223, 11),
            (row["rent_date"], 285, 10),
            (row.get("return_date") or "Pendiente", 336, 9),
            (row["days"], 385, 4),
            (row["status"], 420, 10),
            (money_text(row["total_amount"]), 492, 14),
        ]
        for value, x, max_len in values:
            lines.append(pdf_line(x, y, str(value or "")[:max_len], 8, "F1"))
        y -= 16

    ensure_space(74)
    y -= 22
    lines.append("0.12 0.14 0.17 RG 42 {0} 240 0.8 re S\n".format(y))
    y -= 16
    lines.append(pdf_line(42, y, "Autorizado por", 9, "F1"))
    y -= 16
    lines.append(pdf_line(42, y, "Departamento de Contabilidad y Finanzas", 10, "F2"))
    pages.append("".join(lines))
    total_pages = len(pages)
    pages = [
        page
        + pdf_line(42, 42, "RentCar", 8, "F2")
        + pdf_line(42, 29, "Sistema de Gestión de Renta de Vehículos", 8, "F1")
        + pdf_line(220, 29, "Documento emitido por el sistema", 8, "F1")
        + pdf_line(522, 29, f"Página {index} de {total_pages}", 8, "F1")
        for index, page in enumerate(pages, start=1)
    ]
    return build_pdf(pages)


def friendly_integrity_error(message: str) -> str:
    duplicate_fields = {
        "users.email": "ese correo",
        "vehicle_types.description": "ese tipo de vehículo",
        "brands.description": "esa marca",
        "models.brand_id, models.description": "ese modelo para esa marca",
        "fuel_types.description": "ese tipo de combustible",
        "vehicles.chassis_no": "ese chasis",
        "vehicles.motor_no": "ese motor",
        "vehicles.plate_no": "esa placa",
        "customers.cedula": "esa cédula/RNC",
        "employees.cedula": "esa cédula",
    }
    if "UNIQUE constraint failed:" in message:
        failed = message.split("UNIQUE constraint failed:", 1)[1].strip()
        return f"Ya existe un registro con {duplicate_fields.get(failed, 'ese valor')}."
    if "FOREIGN KEY constraint failed" in message:
        return "Hay una referencia inválida. Verifica los catálogos seleccionados."
    return "No se pudo guardar el registro por datos duplicados o una referencia inválida."


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    init_db()
    httpd = ThreadingHTTPServer((host, port), App)
    print(f"RentCar listo en http://{host}:{port}")
    httpd.serve_forever()


class WSGIRequest(App):
    def __init__(self, method: str, path: str, headers: dict[str, str], body: bytes):
        self.command = method
        self.path = path
        self.headers = headers
        self.rfile = io.BytesIO(body)
        self.wfile = io.BytesIO()
        self.status_code = 200
        self.response_headers: list[tuple[str, str]] = []
        self.extra_headers: list[tuple[str, str]] = []

    def send_response(self, code: int, message: str | None = None) -> None:
        self.status_code = code

    def send_header(self, key: str, value: str) -> None:
        self.response_headers.append((key, value))

    def end_headers(self) -> None:
        return

    def send_error(self, code: int, message: str | None = None) -> None:
        message = message or self.responses.get(code, ("Error", ""))[0]
        self.status_code = code
        self.response_headers = [("Content-Type", "text/plain; charset=utf-8")]
        self.wfile.write(message.encode("utf-8"))


def application(environ, start_response):
    ensure_db_initialized()
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/") or "/"
    query = environ.get("QUERY_STRING", "")
    if query:
        path = f"{path}?{query}"
    length = int(environ.get("CONTENT_LENGTH") or "0")
    body = environ["wsgi.input"].read(length) if length else b""
    headers = {}
    for key, value in environ.items():
        if key.startswith("HTTP_"):
            name = key[5:].replace("_", "-").title()
            headers[name] = value
    if environ.get("CONTENT_TYPE"):
        headers["Content-Type"] = environ["CONTENT_TYPE"]
    if environ.get("CONTENT_LENGTH"):
        headers["Content-Length"] = environ["CONTENT_LENGTH"]

    request = WSGIRequest(method, path, headers, body)
    request.dispatch(method)
    phrase = BaseHTTPRequestHandler.responses.get(request.status_code, ("OK", ""))[0]
    start_response(f"{request.status_code} {phrase}", request.response_headers)
    return [request.wfile.getvalue()]


if __name__ == "__main__":
    run(
        os.environ.get("HOST", "127.0.0.1"),
        int(os.environ.get("PORT", "8000")),
    )
