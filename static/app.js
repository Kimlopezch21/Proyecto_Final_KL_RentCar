const { useEffect, useMemo, useState } = React;

const money = new Intl.NumberFormat("es-DO", { style: "currency", currency: "DOP" });

async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) throw new Error(data.error || "No se pudo completar la solicitud.");
  return data;
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

const statusOptions = ["Activo", "Inactivo"];
const vehicleStatus = ["Disponible", "Rentado", "Mantenimiento", "Inactivo"];
const rentalStatus = ["Abierta", "Cerrada", "Cancelada"];
const inspectionStatus = ["Aprobada", "Pendiente", "Anulada"];
const tireStatus = ["Buena", "Regular", "Mala"];

const navIcons = {
  dashboard: "M3 12l9-8 9 8M5 10v10h14V10",
  clientes: "M16 21v-2a4 4 0 0 0-8 0v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M20 21v-2a3 3 0 0 0-2-2.8M4 21v-2a3 3 0 0 1 2-2.8",
  inspecciones: "M9 5h6M9 9h6M9 13h4M6 3h12v18H6z",
  rentas: "M5 16l2-6h10l2 6M7 16h10M8 19h.01M16 19h.01M6 16v3M18 16v3",
  reportes: "M5 19V5h14v14H5zM8 16V9M12 16V7M16 16v-5",
  vehiculos: "M4 15l2-5h12l2 5M6 15h12M7 18h.01M17 18h.01",
  "tipos-vehiculos": "M4 6h16M4 12h16M4 18h16",
  marcas: "M12 3l2.7 5.5 6.1.9-4.4 4.3 1 6-5.4-2.9-5.4 2.9 1-6-4.4-4.3 6.1-.9z",
  modelos: "M4 7h16v10H4zM8 7V5h8v2",
  "tipos-combustible": "M8 3h7l3 3v13a2 2 0 0 1-2 2H8zM15 3v5h5M8 12h4",
  empleados: "M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8M5 21a7 7 0 0 1 14 0",
  usuarios: "M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6M2 21a6 6 0 0 1 12 0M17 8h4M19 6v4",
};

const navGroups = [
  {
    label: "Operación",
    items: [
      { key: "dashboard", label: "Inicio" },
      { key: "clientes", label: "Clientes" },
      { key: "inspecciones", label: "Inspecciones" },
      { key: "rentas", label: "Rentas y devoluciones" },
      { key: "reportes", label: "Reportes" },
    ],
  },
  {
    label: "Flota",
    items: [
      { key: "vehiculos", label: "Vehículos", adminWrite: true },
      { key: "tipos-vehiculos", label: "Tipos de vehículos", adminWrite: true },
      { key: "marcas", label: "Marcas", adminWrite: true },
      { key: "modelos", label: "Modelos", adminWrite: true },
      { key: "tipos-combustible", label: "Tipos de combustible", adminWrite: true },
      { key: "empleados", label: "Empleados", adminWrite: true },
    ],
  },
  {
    label: "Administración",
    items: [{ key: "usuarios", label: "Usuarios", adminOnly: true }],
  },
];

const allModules = navGroups.flatMap((group) => group.items);

const commonDescriptionField = {
  name: "description",
  label: "Descripción",
  required: true,
  maxLength: 80,
  placeholder: "Ej. Automóvil",
};

const configs = {
  "tipos-vehiculos": {
    title: "Tipos de vehículos",
    endpoint: "/api/tipos-vehiculos",
    adminWrite: true,
    columns: [
      ["id", "ID"],
      ["description", "Descripción"],
      ["status", "Estado"],
    ],
    fields: [
      { ...commonDescriptionField },
      { name: "status", label: "Estado", type: "select", options: statusOptions, default: "Activo", required: true },
    ],
  },
  marcas: {
    title: "Marcas",
    endpoint: "/api/marcas",
    adminWrite: true,
    columns: [
      ["id", "ID"],
      ["description", "Descripción"],
      ["status", "Estado"],
    ],
    fields: [
      { ...commonDescriptionField, placeholder: "Ej. Toyota" },
      { name: "status", label: "Estado", type: "select", options: statusOptions, default: "Activo", required: true },
    ],
  },
  modelos: {
    title: "Modelos",
    endpoint: "/api/modelos",
    adminWrite: true,
    columns: [
      ["id", "ID"],
      ["brand", "Marca"],
      ["description", "Descripción"],
      ["status", "Estado"],
    ],
    fields: [
      { name: "brand_id", label: "Marca", type: "lookup", lookup: "marcas", required: true },
      { ...commonDescriptionField, placeholder: "Ej. Corolla" },
      { name: "status", label: "Estado", type: "select", options: statusOptions, default: "Activo", required: true },
    ],
  },
  "tipos-combustible": {
    title: "Tipos de combustible",
    endpoint: "/api/tipos-combustible",
    adminWrite: true,
    columns: [
      ["id", "ID"],
      ["description", "Descripción"],
      ["status", "Estado"],
    ],
    fields: [
      { ...commonDescriptionField, placeholder: "Ej. Gasolina" },
      { name: "status", label: "Estado", type: "select", options: statusOptions, default: "Activo", required: true },
    ],
  },
  vehiculos: {
    title: "Vehículos",
    endpoint: "/api/vehiculos",
    adminWrite: true,
    columns: [
      ["id", "ID"],
      ["description", "Descripción"],
      ["plate_no", "Placa"],
      ["vehicle_type", "Tipo"],
      ["brand", "Marca"],
      ["model", "Modelo"],
      ["fuel_type", "Combustible"],
      ["status", "Estado"],
    ],
    fields: [
      { name: "description", label: "Descripción", required: true, maxLength: 120, placeholder: "Ej. Toyota Corolla 2024 blanco" },
      { name: "chassis_no", label: "No. chasis", required: true, maxLength: 30, transform: "uppercase", placeholder: "CHS-001" },
      { name: "motor_no", label: "No. motor", required: true, maxLength: 30, transform: "uppercase", placeholder: "MTR-001" },
      { name: "plate_no", label: "No. placa", required: true, maxLength: 10, pattern: "[A-Z0-9\\-]{6,10}", transform: "uppercase", placeholder: "A123456" },
      { name: "vehicle_type_id", label: "Tipo de vehículo", type: "lookup", lookup: "tiposVehiculos", required: true },
      { name: "brand_id", label: "Marca", type: "lookup", lookup: "marcas", required: true },
      { name: "model_id", label: "Modelo", type: "lookup", lookup: "modelos", required: true },
      { name: "fuel_type_id", label: "Tipo de combustible", type: "lookup", lookup: "combustibles", required: true },
      { name: "status", label: "Estado", type: "select", options: vehicleStatus, default: "Disponible", required: true },
    ],
  },
  clientes: {
    title: "Clientes",
    endpoint: "/api/clientes",
    columns: [
      ["id", "ID"],
      ["name", "Nombre"],
      ["cedula", "Cédula/RNC"],
      ["credit_limit", "Límite de crédito"],
      ["person_type", "Tipo de persona"],
      ["status", "Estado"],
    ],
    fields: [
      { name: "name", label: "Nombre", required: true, maxLength: 100, placeholder: "Nombre completo o empresa" },
      { name: "cedula", label: "Cédula/RNC", required: true, pattern: "[0-9\\-]{9,13}", inputMode: "numeric", placeholder: "00112345678" },
      { name: "credit_card_no", label: "Tarjeta de crédito (últimos 4 dígitos)", required: true, pattern: "[0-9]{4}", maxLength: 4, inputMode: "numeric", placeholder: "1111" },
      { name: "credit_limit", label: "Límite de crédito", type: "number", default: 0, min: 0, step: "100" },
      { name: "person_type", label: "Tipo de persona", type: "select", options: ["Física", "Jurídica"], default: "Física", required: true },
      { name: "status", label: "Estado", type: "select", options: statusOptions, default: "Activo", required: true },
    ],
  },
  empleados: {
    title: "Empleados",
    endpoint: "/api/empleados",
    adminWrite: true,
    columns: [
      ["id", "ID"],
      ["name", "Nombre"],
      ["cedula", "Cédula"],
      ["work_shift", "Tanda"],
      ["commission_percent", "% comisión"],
      ["hire_date", "Fecha de ingreso"],
      ["status", "Estado"],
    ],
    fields: [
      { name: "name", label: "Nombre", required: true, maxLength: 100, placeholder: "Nombre completo" },
      { name: "cedula", label: "Cédula", required: true, pattern: "[0-9]{3}-[0-9]{7}-[0-9]", inputMode: "numeric", placeholder: "001-0000002-2" },
      { name: "work_shift", label: "Tanda laboral", type: "select", options: ["Matutina", "Vespertina", "Nocturna"], default: "Matutina", required: true },
      { name: "commission_percent", label: "% comisión", type: "number", default: 0, min: 0, max: 100, step: "0.01" },
      { name: "hire_date", label: "Fecha de ingreso", type: "date", default: today(), max: today() },
      { name: "status", label: "Estado", type: "select", options: statusOptions, default: "Activo", required: true },
    ],
  },
};

function defaultForm(fields) {
  return Object.fromEntries(fields.map((field) => [field.name, field.default ?? (field.type === "checkbox" ? 0 : "")]));
}

function visibleName(item) {
  if (!item) return "";
  if (item.plate_no) return `${item.description} · ${item.plate_no}`;
  return item.name || item.description || item.email || `#${item.id}`;
}

function activeOnly(items = []) {
  return items.filter((item) => !item.status || item.status === "Activo" || item.status === "Disponible");
}

function normalizePayload(payload, fields) {
  const cleaned = { ...payload };
  fields.forEach((field) => {
    if (field.transform === "uppercase" && typeof cleaned[field.name] === "string") {
      cleaned[field.name] = cleaned[field.name].trim().toUpperCase();
    }
    if (field.type === "number") cleaned[field.name] = Number(cleaned[field.name] || 0);
    if (field.type === "lookup") cleaned[field.name] = Number(cleaned[field.name]);
    if (typeof cleaned[field.name] === "string") cleaned[field.name] = cleaned[field.name].trim();
  });
  return cleaned;
}

function searchableText(item, columns) {
  return normalizeSearch(columns.map(([key]) => key === "cedula" ? `${item[key] ?? ""} ${formatIdentifier(item[key])}` : item[key] ?? "").join(" "));
}

function matchesSearch(item, columns, search) {
  const term = normalizeSearch(search);
  if (!term) return true;
  if ((term === "activo" || term === "inactivo") && columns.some(([key]) => key === "status")) {
    return normalizeSearch(item.status) === term;
  }
  return searchableText(item, columns).includes(term);
}

function normalizeSearch(value) {
  return String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function formatIdentifier(value) {
  const text = String(value || "");
  const digits = text.replace(/\D/g, "");
  if (digits.length === 11) return `${digits.slice(0, 3)}-${digits.slice(3, 10)}-${digits.slice(10)}`;
  if (digits.length === 9) return `${digits.slice(0, 3)}-${digits.slice(3, 8)}-${digits.slice(8)}`;
  return text;
}

function statusAction(config, item) {
  if (config.endpoint === "/api/inspecciones") {
    return item.status === "Anulada"
      ? { label: "Restaurar", className: "btn success small", confirm: "¿Restaurar esta inspección?" }
      : { label: "Anular", className: "btn danger small", confirm: "¿Anular esta inspección?" };
  }
  return item.status === "Inactivo"
    ? { label: "Activar", className: "btn success small", confirm: "¿Activar este registro?" }
    : { label: "Inactivar", className: "btn danger small", confirm: "El registro se marcará como inactivo. ¿Continuar?" };
}

function displayRole(value) {
  return value === "admin" ? "Administrador" : "Empleado";
}

function Status({ value }) {
  return <span className={`status ${value || ""}`}>{value || "N/D"}</span>;
}

function Notice({ message, type }) {
  if (!message) return null;
  return <div className={`notice ${type === "error" ? "error" : ""}`}>{message}</div>;
}

function NavIcon({ name }) {
  return (
    <svg className="nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d={navIcons[name] || navIcons.dashboard} />
    </svg>
  );
}

function Field({ field, value, onChange, lookups }) {
  const fieldId = field.id || field.name;
  const setValue = (next) => {
    const normalized = field.transform === "uppercase" && typeof next === "string" ? next.toUpperCase() : next;
    onChange(field.name, normalized);
  };
  const commonProps = {
    id: fieldId,
    value: value ?? "",
    required: field.required,
    min: field.min,
    max: field.max,
    step: field.step || (field.type === "number" ? "0.01" : undefined),
    maxLength: field.maxLength,
    minLength: field.minLength,
    pattern: field.pattern,
    title: field.title,
    inputMode: field.inputMode,
    placeholder: field.placeholder,
    autoComplete: field.autoComplete || "off",
  };

  if (field.type === "lookup" || field.type === "select") {
    const options = field.type === "lookup" ? lookups[field.lookup] || [] : field.options || [];
    const optionalLabel = field.allLabel || "Todos";
    return (
      <div className={`field ${field.className || ""}`}>
        <label htmlFor={fieldId}>{field.label}</label>
        <select
          id={fieldId}
          value={value || ""}
          onChange={(event) => setValue(event.target.value)}
          required={field.required}
        >
          {field.required ? (
            <option value="" disabled hidden>{field.placeholder || "Elige una opción"}</option>
          ) : (
            <option value="">{optionalLabel}</option>
          )}
          {options.map((option) => {
            const optionValue = typeof option === "string" ? option : option.id;
            const label = typeof option === "string" ? option : visibleName(option);
            return (
              <option key={optionValue} value={optionValue}>
                {label}
              </option>
            );
          })}
        </select>
      </div>
    );
  }

  if (field.type === "checkbox") {
    return (
      <div className={`field check ${field.className || ""}`}>
        <label>
          <input type="checkbox" checked={Boolean(Number(value))} onChange={(event) => setValue(event.target.checked ? 1 : 0)} />
          {field.label}
        </label>
      </div>
    );
  }

  if (field.type === "textarea") {
    return (
      <div className={`field ${field.wide === false ? "" : "field-wide"} ${field.className || ""}`}>
        <label htmlFor={fieldId}>{field.label}</label>
        <textarea id={fieldId} value={value || ""} maxLength={field.maxLength || 300} placeholder={field.placeholder} onChange={(event) => setValue(event.target.value)} />
      </div>
    );
  }

  return (
    <div className={`field ${field.className || ""}`}>
      <label htmlFor={fieldId}>{field.label}</label>
      <input
        {...commonProps}
        type={field.type || "text"}
        onChange={(event) => setValue(event.target.value)}
      />
    </div>
  );
}

function Login({ onLogin }) {
  const [form, setForm] = useState({ username: "", password: "" });
  const [message, setMessage] = useState("");

  async function submit(event) {
    event.preventDefault();
    setMessage("");
    try {
      const data = await api("/api/auth/password", { method: "POST", body: JSON.stringify(form) });
      onLogin(data.user);
    } catch (error) {
      setMessage(error.message);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-visual">
        <div className="login-copy">
          <h1>RentCar</h1>
          <p>Vehículos, inspecciones, rentas y devoluciones en un solo panel.</p>
        </div>
      </section>
      <section className="login-panel">
        <div className="login-box">
          <span className="eyebrow dark">Acceso al sistema</span>
          <h2>Iniciar sesión</h2>
          <Notice type="error" message={message} />
          <form className="login-form" onSubmit={submit}>
            <Field
              field={{ id: "login-username", name: "username", label: "Usuario", required: true, maxLength: 30, autoComplete: "username", placeholder: "Ingresar usuario" }}
              value={form.username}
              onChange={(name, value) => setForm({ ...form, [name]: value })}
              lookups={{}}
            />
            <Field
              field={{ id: "login-password", name: "password", label: "Contraseña", type: "password", required: true, maxLength: 30, autoComplete: "current-password", placeholder: "Ingresar contraseña" }}
              value={form.password}
              onChange={(name, value) => setForm({ ...form, [name]: value })}
              lookups={{}}
            />
            <button className="btn" type="submit">Entrar</button>
          </form>
          <div className="demo-block">
            <h3>Acceso de prueba para demostración</h3>
            <p className="muted">Usa admin / 12345 o empleado / 12345.</p>
          </div>
        </div>
      </section>
    </main>
  );
}

function Dashboard({ lookups, setView }) {
  const [summary, setSummary] = useState(null);

  useEffect(() => {
    api("/api/summary").then(setSummary);
  }, []);

  if (!summary) return <p className="muted">Cargando resumen...</p>;

  const cards = [
    ["Disponibles", summary.vehiculosDisponibles],
    ["Rentados", summary.vehiculosRentados],
    ["Rentas abiertas", summary.rentasAbiertas],
    ["Clientes activos", summary.clientesActivos],
    ["Ingresos cerrados", money.format(summary.ingresos || 0)],
  ];
  const availableVehicles = (lookups.vehiculos || []).filter((item) => item.status === "Disponible").slice(0, 4);
  const flow = [
    ["1", "Cliente", "clientes"],
    ["2", "Inspección", "inspecciones"],
    ["3", "Renta", "rentas"],
    ["4", "Devolución", "rentas"],
    ["5", "Reporte", "reportes"],
  ];

  return (
    <div className="dashboard">
      <section className="command-strip">
        <div>
          <span className="eyebrow dark">Panel operativo</span>
          <h2>Flujo de renta</h2>
        </div>
        <div className="flow-actions">
          {flow.map(([number, label, target]) => (
            <button key={`${number}-${label}`} className="flow-step" onClick={() => setView(target)}>
              <span>{number}</span>
              {label}
            </button>
          ))}
        </div>
      </section>

      <section className="grid stats">
        {cards.map(([label, value]) => (
          <div className={`stat ${label === "Ingresos cerrados" ? "stat-money" : ""}`} key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </section>

      <section className="split-grid">
        <div className="panel">
          <div className="panel-head">
            <h3>Vehículos listos</h3>
            <button className="btn ghost" onClick={() => setView("vehiculos")}>Ver flota</button>
          </div>
          <DataTable
            compact
            rows={availableVehicles}
            columns={[
              ["description", "Vehículo"],
              ["plate_no", "Placa"],
              ["status", "Estado"],
            ]}
          />
        </div>
        <div className="panel dark-panel">
          <span className="eyebrow">Siguiente paso</span>
          <h3>Antes de crear una renta, registra una inspección aprobada para el cliente y el vehículo.</h3>
          <div className="actions">
            <button className="btn light" onClick={() => setView("inspecciones")}>Registrar inspección</button>
            <button className="btn outline-light" onClick={() => setView("rentas")}>Ir a rentas</button>
          </div>
        </div>
      </section>
    </div>
  );
}

function GenericModule({ config, lookups, refreshLookups, user }) {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(defaultForm(config.fields));
  const [editing, setEditing] = useState(null);
  const [search, setSearch] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const canWrite = user.role === "admin" || !config.adminWrite;
  const formIdPrefix = config.endpoint.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "");

  async function load() {
    setItems(await api(config.endpoint));
  }

  useEffect(() => {
    load();
  }, [config.endpoint]);

  function update(name, value) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setMessage("");
    setError("");
    try {
      const payload = normalizePayload(form, config.fields);
      await api(editing ? `${config.endpoint}/${editing}` : config.endpoint, {
        method: editing ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      setForm(defaultForm(config.fields));
      setEditing(null);
      setMessage(editing ? "Registro actualizado." : "Registro creado.");
      await load();
      await refreshLookups();
    } catch (err) {
      setError(err.message);
    }
  }

  async function changeStatus(item) {
    const action = statusAction(config, item);
    if (!confirm(action.confirm)) return;
    try {
      await api(`${config.endpoint}/${item.id}`, { method: "DELETE" });
      setMessage(item.status === "Inactivo" || item.status === "Anulada" ? "Registro actualizado." : "Registro actualizado.");
      await load();
      await refreshLookups();
    } catch (err) {
      setError(err.message);
    }
  }

  const filtered = items.filter((item) => matchesSearch(item, config.columns, search));

  return (
    <section className="module">
      <div className="module-head">
        <div className="table-count">{filtered.length} registros</div>
      </div>
      {!canWrite && <Notice type="error" message="Tu rol permite consultar este módulo, pero no modificarlo." />}
      <Notice message={message} />
      <Notice type="error" message={error} />

      {canWrite && (
        <form className={`record-form ${config.formClassName || ""}`} onSubmit={submit}>
          <div className={`form-grid ${config.gridClassName || ""}`}>
            {config.fields.map((field) => (
              <Field key={field.name} field={{ ...field, id: `${formIdPrefix}-${field.name}` }} value={form[field.name]} onChange={update} lookups={lookups} />
            ))}
          </div>
          <div className="actions">
            <button className="btn" type="submit">{editing ? "Guardar cambios" : "Crear registro"}</button>
            {editing && (
              <button className="btn secondary" type="button" onClick={() => { setEditing(null); setForm(defaultForm(config.fields)); }}>
                Cancelar
              </button>
            )}
          </div>
        </form>
      )}

      <div className="table-tools">
        <div className="field search-field">
          <label htmlFor={`${config.endpoint}-search`}>Buscar</label>
          <input id={`${config.endpoint}-search`} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Filtrar registros" />
        </div>
      </div>

      <DataTable
        rows={filtered}
        columns={config.columns}
        actions={canWrite ? (item) => (
          <div className="row-actions">
            <button className="btn secondary small" onClick={() => { setEditing(item.id); setForm({ ...defaultForm(config.fields), ...item }); }}>Editar</button>
            <button className={statusAction(config, item).className} onClick={() => changeStatus(item)}>{statusAction(config, item).label}</button>
          </div>
        ) : null}
      />
    </section>
  );
}

function formatCell(key, value) {
  if (value === null || value === undefined || value === "") return "";
  if (key === "status") return <Status value={value} />;
  if (key === "role") return displayRole(value);
  if (key === "cedula") return formatIdentifier(value);
  if (["total_amount", "daily_amount", "credit_limit"].includes(key)) return money.format(Number(value || 0));
  return String(value);
}

function DataTable({ rows, columns, actions, compact = false }) {
  return (
    <div className={`table-wrap ${compact ? "compact-table" : ""}`}>
      <table>
        <thead>
          <tr>
            {columns.map(([, label]) => <th key={label}>{label}</th>)}
            {actions && <th>Acciones</th>}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length + (actions ? 1 : 0)} className="muted">Sin registros.</td>
            </tr>
          )}
          {rows.map((row) => (
            <tr key={row.id}>
              {columns.map(([key]) => (
                <td key={key}>{formatCell(key, row[key])}</td>
              ))}
              {actions && <td>{actions(row)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Inspections({ lookups, user }) {
  const inspectionLookups = {
    ...lookups,
    vehiculos: (lookups.vehiculos || []).filter((item) => item.status === "Disponible"),
    clientes: activeOnly(lookups.clientes),
    empleados: activeOnly(lookups.empleados),
  };
  const fields = [
    { name: "vehicle_id", label: "Vehículo", type: "lookup", lookup: "vehiculos", required: true },
    { name: "customer_id", label: "Cliente", type: "lookup", lookup: "clientes", required: true },
    { name: "employee_id", label: "Empleado que inspecciona", type: "lookup", lookup: "empleados", required: true },
    { name: "inspection_date", label: "Fecha", type: "date", default: today(), max: today() },
    { name: "fuel_amount", label: "Combustible", type: "select", options: ["1/4", "1/2", "3/4", "Lleno"], default: "Lleno", required: true },
    { name: "status", label: "Estado", type: "select", options: inspectionStatus, default: "Aprobada", required: true },
    { name: "tire_front_left", label: "Goma delantera izquierda", type: "select", options: tireStatus, default: "Buena", required: true },
    { name: "tire_front_right", label: "Goma delantera derecha", type: "select", options: tireStatus, default: "Buena", required: true },
    { name: "tire_rear_left", label: "Goma trasera izquierda", type: "select", options: tireStatus, default: "Buena", required: true },
    { name: "tire_rear_right", label: "Goma trasera derecha", type: "select", options: tireStatus, default: "Buena", required: true },
    { name: "has_scratches", label: "Tiene ralladuras", type: "checkbox", default: 0, className: "inspection-check" },
    { name: "has_spare_tire", label: "Tiene goma de repuesto", type: "checkbox", default: 1, className: "inspection-check" },
    { name: "has_jack", label: "Tiene gato", type: "checkbox", default: 1, className: "inspection-check" },
    { name: "has_glass_breaks", label: "Tiene roturas en cristales", type: "checkbox", default: 0, className: "inspection-check" },
    { name: "notes", label: "Comentario", type: "textarea", maxLength: 300, wide: false, className: "inspection-notes" },
  ];
  const config = {
    title: "Inspecciones",
    endpoint: "/api/inspecciones",
    gridClassName: "inspection-grid",
    fields,
    columns: [
      ["id", "ID"],
      ["inspection_date", "Fecha"],
      ["vehicle", "Vehículo"],
      ["customer", "Cliente"],
      ["employee", "Empleado"],
      ["fuel_amount", "Combustible"],
      ["status", "Estado"],
    ],
  };
  return <GenericModule config={config} lookups={inspectionLookups} refreshLookups={async () => {}} user={user} />;
}

function Rentals({ lookups, refreshLookups }) {
  const [items, setItems] = useState([]);
  const [filters, setFilters] = useState({ customer_id: "", vehicle_id: "", status: "", from: "", to: "" });
  const [form, setForm] = useState({ employee_id: "", vehicle_id: "", customer_id: "", rent_date: today(), daily_amount: 2500, days: 1, comment: "" });
  const [editing, setEditing] = useState(null);
  const [returning, setReturning] = useState(null);
  const [returnForm, setReturnForm] = useState({ return_date: today(), comment: "" });
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const selectedVehicle = (lookups.vehiculos || []).find((item) => String(item.id) === String(form.vehicle_id));
  const availableVehicles = (lookups.vehiculos || []).filter((item) => item.status === "Disponible");
  const rentalLookups = {
    ...lookups,
    vehiculos: selectedVehicle && !availableVehicles.some((item) => item.id === selectedVehicle.id)
      ? [selectedVehicle, ...availableVehicles]
      : availableVehicles,
    clientes: activeOnly(lookups.clientes),
    empleados: activeOnly(lookups.empleados),
  };

  async function load() {
    const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
    setItems(await api(`/api/rentas?${params.toString()}`));
  }

  useEffect(() => {
    load();
  }, []);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      const fields = [
        { name: "employee_id", type: "lookup" },
        { name: "vehicle_id", type: "lookup" },
        { name: "customer_id", type: "lookup" },
        { name: "daily_amount", type: "number" },
        { name: "days", type: "number" },
      ];
      await api(editing ? `/api/rentas/${editing}` : "/api/rentas", {
        method: editing ? "PUT" : "POST",
        body: JSON.stringify(normalizePayload(form, fields)),
      });
      setMessage(editing ? "Renta actualizada." : "Renta creada. El vehículo cambió a estado Rentado.");
      setEditing(null);
      setForm({ employee_id: "", vehicle_id: "", customer_id: "", rent_date: today(), daily_amount: 2500, days: 1, comment: "" });
      await load();
      await refreshLookups();
    } catch (err) {
      setError(err.message);
    }
  }

  function editar(item) {
    setError("");
    setMessage("");
    setReturning(null);
    setEditing(item.id);
    setForm({
      employee_id: item.employee_id,
      vehicle_id: item.vehicle_id,
      customer_id: item.customer_id,
      rent_date: item.rent_date || today(),
      daily_amount: item.daily_amount || 2500,
      days: item.days || 1,
      comment: item.comment || "",
    });
  }

  function cancelEdit() {
    setEditing(null);
    setForm({ employee_id: "", vehicle_id: "", customer_id: "", rent_date: today(), daily_amount: 2500, days: 1, comment: "" });
  }

  async function devolver(event) {
    event.preventDefault();
    if (!returning) return;
    try {
      const result = await api(`/api/rentas/${returning.id}/devolver`, {
        method: "POST",
        body: JSON.stringify(returnForm),
      });
      setMessage(`Devolución registrada. Días: ${result.days}. Total: ${money.format(result.total)}.`);
      setReturning(null);
      setReturnForm({ return_date: today(), comment: "" });
      await load();
      await refreshLookups();
    } catch (err) {
      setError(err.message);
    }
  }

  async function cancelar(item) {
    if (!confirm("¿Cancelar esta renta?")) return;
    try {
      await api(`/api/rentas/${item.id}`, { method: "DELETE" });
      await load();
      await refreshLookups();
    } catch (err) {
      setError(err.message);
    }
  }

  async function reabrir(item) {
    if (!confirm("¿Reabrir esta renta?")) return;
    try {
      await api(`/api/rentas/${item.id}/reabrir`, { method: "POST" });
      setMessage("Renta reabierta.");
      await load();
      await refreshLookups();
    } catch (err) {
      setError(err.message);
    }
  }

  const totalPreview = Number(form.daily_amount || 0) * Math.max(Number(form.days || 1), 1);
  const rentalColumns = [
    ["id", "No. renta"],
    ["rent_date", "Fecha renta"],
    ["return_date", "Fecha devolución"],
    ["customer", "Cliente"],
    ["vehicle", "Vehículo"],
    ["employee", "Empleado"],
    ["days", "Días"],
    ["total_amount", "Total"],
    ["status", "Estado"],
  ];

  return (
    <section className="module">
      <div className="module-head">
        <div className="table-count">Total estimado: {money.format(totalPreview)}</div>
      </div>
      <Notice message={message} />
      <Notice type="error" message={error} />

      <form className="record-form" onSubmit={submit}>
        <div className="form-grid">
          <Field field={{ id: "rental-employee", name: "employee_id", label: "Empleado", type: "lookup", lookup: "empleados", required: true }} value={form.employee_id} onChange={(name, value) => setForm({ ...form, [name]: value })} lookups={rentalLookups} />
          <Field field={{ id: "rental-vehicle", name: "vehicle_id", label: "Vehículo disponible", type: "lookup", lookup: "vehiculos", required: true }} value={form.vehicle_id} onChange={(name, value) => setForm({ ...form, [name]: value })} lookups={rentalLookups} />
          <Field field={{ id: "rental-customer", name: "customer_id", label: "Cliente", type: "lookup", lookup: "clientes", required: true }} value={form.customer_id} onChange={(name, value) => setForm({ ...form, [name]: value })} lookups={rentalLookups} />
          <Field field={{ id: "rental-date", name: "rent_date", label: "Fecha de renta", type: "date", max: today(), required: true }} value={form.rent_date} onChange={(name, value) => setForm({ ...form, [name]: value })} lookups={lookups} />
          <Field field={{ id: "rental-daily-amount", name: "daily_amount", label: "Monto por día", type: "number", min: 1, step: "0.01", required: true }} value={form.daily_amount} onChange={(name, value) => setForm({ ...form, [name]: value })} lookups={lookups} />
          <Field field={{ id: "rental-days", name: "days", label: "Cantidad de días", type: "number", min: 1, step: "1", required: true }} value={form.days} onChange={(name, value) => setForm({ ...form, [name]: value })} lookups={lookups} />
          <Field field={{ id: "rental-comment", name: "comment", label: "Comentario", type: "textarea", maxLength: 300 }} value={form.comment} onChange={(name, value) => setForm({ ...form, [name]: value })} lookups={lookups} />
        </div>
        <div className="actions">
          <button className="btn" type="submit">{editing ? "Guardar renta" : "Crear renta"}</button>
          {editing && <button className="btn secondary" type="button" onClick={cancelEdit}>Cancelar edición</button>}
        </div>
      </form>

      {returning && (
        <form className="return-panel" onSubmit={devolver}>
          <div>
            <span className="eyebrow dark">Devolución</span>
            <h3>{returning.vehicle}</h3>
            <p className="muted">{returning.customer} · renta #{returning.id}</p>
          </div>
          <Field field={{ id: "return-date", name: "return_date", label: "Fecha de devolución", type: "date", required: true }} value={returnForm.return_date} onChange={(name, value) => setReturnForm({ ...returnForm, [name]: value })} lookups={lookups} />
          <Field field={{ id: "return-comment", name: "comment", label: "Comentario", type: "textarea", maxLength: 300 }} value={returnForm.comment} onChange={(name, value) => setReturnForm({ ...returnForm, [name]: value })} lookups={lookups} />
          <div className="actions">
            <button className="btn" type="submit">Registrar devolución</button>
            <button className="btn secondary" type="button" onClick={() => setReturning(null)}>Cancelar</button>
          </div>
        </form>
      )}

      <h3 className="section-title">Consulta por criterios</h3>
      <div className="filters">
        <Field field={{ id: "rental-filter-customer", name: "customer_id", label: "Cliente", type: "lookup", lookup: "clientes", allLabel: "Todos los clientes" }} value={filters.customer_id} onChange={(name, value) => setFilters({ ...filters, [name]: value })} lookups={lookups} />
        <Field field={{ id: "rental-filter-vehicle", name: "vehicle_id", label: "Vehículo", type: "lookup", lookup: "vehiculos", allLabel: "Todos los vehículos" }} value={filters.vehicle_id} onChange={(name, value) => setFilters({ ...filters, [name]: value })} lookups={lookups} />
        <Field field={{ id: "rental-filter-status", name: "status", label: "Estado", type: "select", options: rentalStatus, allLabel: "Todos los estados" }} value={filters.status} onChange={(name, value) => setFilters({ ...filters, [name]: value })} lookups={lookups} />
        <Field field={{ id: "rental-filter-from", name: "from", label: "Desde", type: "date" }} value={filters.from} onChange={(name, value) => setFilters({ ...filters, [name]: value })} lookups={lookups} />
        <Field field={{ id: "rental-filter-to", name: "to", label: "Hasta", type: "date" }} value={filters.to} onChange={(name, value) => setFilters({ ...filters, [name]: value })} lookups={lookups} />
        <button className="btn blue" type="button" onClick={load}>Buscar</button>
      </div>

      <DataTable
        rows={items}
        columns={rentalColumns}
        actions={(item) => (
          <div className="row-actions">
            {item.status === "Abierta" ? (
              <>
                <button className="btn secondary small" onClick={() => editar(item)}>Editar</button>
                <button className="btn secondary small" onClick={() => { setReturning(item); setReturnForm({ return_date: today(), comment: "" }); }}>Devolver</button>
                <button className="btn danger small" onClick={() => cancelar(item)}>Cancelar</button>
              </>
            ) : item.status === "Cerrada" ? (
              <button className="btn success small" onClick={() => reabrir(item)}>Reabrir</button>
            ) : item.status === "Cancelada" ? (
              <button className="btn success small" onClick={() => reabrir(item)}>Restaurar</button>
            ) : null}
          </div>
        )}
      />
    </section>
  );
}

function Users() {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({ name: "", role: "empleado", status: "Activo" });
  const [editing, setEditing] = useState(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function load() {
    try {
      setItems(await api("/api/usuarios"));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function submit(event) {
    event.preventDefault();
    if (!editing) return;
    setError("");
    setMessage("");
    try {
      await api(`/api/usuarios/${editing}`, {
        method: "PUT",
        body: JSON.stringify(form),
      });
      setEditing(null);
      setForm({ name: "", role: "empleado", status: "Activo" });
      setMessage("Usuario actualizado.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function toggleStatus(item) {
    const next = item.status === "Activo" ? "Inactivar" : "Activar";
    if (!confirm(`¿${next} este usuario?`)) return;
    setError("");
    setMessage("");
    try {
      await api(`/api/usuarios/${item.id}`, { method: "DELETE" });
      setMessage("Usuario actualizado.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="module">
      <Notice message={message} />
      <Notice type="error" message={error} />
      {editing && (
        <form className="record-form" onSubmit={submit}>
          <div className="form-grid">
            <Field field={{ id: "user-name", name: "name", label: "Nombre", required: true, maxLength: 100 }} value={form.name} onChange={(name, value) => setForm({ ...form, [name]: value })} lookups={{}} />
            <Field field={{ id: "user-role", name: "role", label: "Rol", type: "select", options: [{ id: "admin", description: "Administrador" }, { id: "empleado", description: "Empleado" }], required: true }} value={form.role} onChange={(name, value) => setForm({ ...form, [name]: value })} lookups={{}} />
            <Field field={{ id: "user-status", name: "status", label: "Estado", type: "select", options: statusOptions, required: true }} value={form.status} onChange={(name, value) => setForm({ ...form, [name]: value })} lookups={{}} />
          </div>
          <div className="actions">
            <button className="btn" type="submit">Guardar cambios</button>
            <button className="btn secondary" type="button" onClick={() => { setEditing(null); setForm({ name: "", role: "empleado", status: "Activo" }); }}>Cancelar</button>
          </div>
        </form>
      )}
      <DataTable
        rows={items}
        columns={[
          ["id", "ID"],
          ["name", "Nombre"],
          ["role", "Rol"],
          ["status", "Estado"],
        ]}
        actions={(item) => (
          <div className="row-actions">
            <button className="btn secondary small" onClick={() => { setEditing(item.id); setForm({ name: item.name, role: item.role, status: item.status }); }}>Editar</button>
            <button className={item.status === "Activo" ? "btn danger small" : "btn success small"} onClick={() => toggleStatus(item)}>
              {item.status === "Activo" ? "Inactivar" : "Activar"}
            </button>
          </div>
        )}
      />
    </section>
  );
}

function Reports({ lookups }) {
  const [filters, setFilters] = useState({ from: "", to: "", vehicle_type_id: "" });
  const [report, setReport] = useState({ rows: [], summary: [], total: 0 });
  const [error, setError] = useState("");

  async function load() {
    try {
      const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
      setReport(await api(`/api/reportes/rentas?${params.toString()}`));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function pdfUrl() {
    const params = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
    return `/api/reportes/rentas/pdf?${params.toString()}`;
  }

  return (
    <section className="report">
      <div className="module-head">
        <a className="btn secondary" href={pdfUrl()} download="reporte-rentas.pdf">Exportar PDF</a>
      </div>
      <Notice type="error" message={error} />
      <div className="filters">
        <Field field={{ id: "report-from", name: "from", label: "Desde", type: "date" }} value={filters.from} onChange={(name, value) => setFilters({ ...filters, [name]: value })} lookups={lookups} />
        <Field field={{ id: "report-to", name: "to", label: "Hasta", type: "date" }} value={filters.to} onChange={(name, value) => setFilters({ ...filters, [name]: value })} lookups={lookups} />
        <Field field={{ id: "report-vehicle-type", name: "vehicle_type_id", label: "Tipo de vehículo", type: "lookup", lookup: "tiposVehiculos", allLabel: "Todos los tipos" }} value={filters.vehicle_type_id} onChange={(name, value) => setFilters({ ...filters, [name]: value })} lookups={lookups} />
        <button className="btn blue" type="button" onClick={load}>Generar</button>
      </div>
      <section className="grid stats report-stats">
        <div className="stat">
          <span>Total general</span>
          <strong>{money.format(report.total || 0)}</strong>
        </div>
        {report.summary.map((item) => (
          <div className="stat" key={item.vehicle_type}>
            <span>{item.vehicle_type}</span>
            <strong>{item.count} rentas</strong>
            <span className="stat-subtotal">{money.format(item.total || 0)}</span>
          </div>
        ))}
      </section>
      <DataTable
        rows={report.rows}
        columns={[
          ["id", "No."],
          ["rent_date", "Fecha renta"],
          ["return_date", "Fecha devolución"],
          ["customer", "Cliente"],
          ["vehicle", "Vehículo"],
          ["vehicle_type", "Tipo"],
          ["employee", "Empleado"],
          ["days", "Días"],
          ["total_amount", "Total"],
          ["status", "Estado"],
        ]}
      />
    </section>
  );
}

function Shell({ user, onLogout }) {
  const [view, setView] = useState("dashboard");
  const [lookups, setLookups] = useState({});
  const [menuOpen, setMenuOpen] = useState(false);

  async function refreshLookups() {
    setLookups(await api("/api/lookups"));
  }

  useEffect(() => {
    refreshLookups();
  }, []);

  const visibleGroups = useMemo(() => navGroups.map((group) => ({
    ...group,
    items: group.items.filter((item) => !item.adminOnly || user.role === "admin"),
  })).filter((group) => group.items.length > 0), [user.role]);
  const title = allModules.find((item) => item.key === view)?.label || "Inicio";

  function go(target) {
    setView(target);
    setMenuOpen(false);
  }

  let content = <Dashboard lookups={lookups} setView={go} />;
  if (configs[view]) content = <GenericModule config={configs[view]} lookups={lookups} refreshLookups={refreshLookups} user={user} />;
  if (view === "inspecciones") content = <Inspections lookups={lookups} user={user} />;
  if (view === "rentas") content = <Rentals lookups={lookups} refreshLookups={refreshLookups} />;
  if (view === "reportes") content = <Reports lookups={lookups} />;
  if (view === "usuarios") content = <Users />;

  return (
    <main className="app-shell">
      <aside className={`sidebar ${menuOpen ? "open" : ""}`}>
        <div className="brand-row">
          <div className="brand">RentCar</div>
          <button className="menu-toggle" onClick={() => setMenuOpen(!menuOpen)}>Menú</button>
        </div>
        <div className="user-chip">
          <span>Rol: {displayRole(user.role)}</span>
        </div>
        <nav className="nav">
          {visibleGroups.map((group) => (
            <div className="nav-group" key={group.label}>
              <span>{group.label}</span>
              {group.items.map((item) => (
                <button key={item.key} className={view === item.key ? "active" : ""} onClick={() => go(item.key)}>
                  <NavIcon name={item.key} />
                  <span>{item.label}</span>
                </button>
              ))}
            </div>
          ))}
        </nav>
      </aside>
      <section className="main">
        <header className="topbar">
          <div>
            <span className="eyebrow dark">RentCar</span>
            <h1>{title}</h1>
          </div>
          <button className="btn ghost" onClick={onLogout}>Cerrar sesión</button>
        </header>
        {content}
      </section>
    </main>
  );
}

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api("/api/auth/me")
      .then((data) => setUser(data.user))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  async function logout() {
    await api("/api/auth/logout", { method: "POST" });
    setUser(null);
  }

  if (loading) return <div className="main"><p className="muted">Cargando...</p></div>;
  if (!user) return <Login onLogin={setUser} />;
  return <Shell user={user} onLogout={logout} />;
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
