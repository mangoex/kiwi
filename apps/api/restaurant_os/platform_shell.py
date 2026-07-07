# ruff: noqa: E501

from html import escape

MODULES = {
    "/admin": {
        "title": "Admin",
        "subtitle": "Organizacion, sucursales, usuarios y configuracion.",
        "status": "Fase 0",
    },
    "/pos": {
        "title": "POS",
        "subtitle": "Punto de venta preparado para el primer vertical slice.",
        "status": "Pendiente",
    },
    "/kds": {
        "title": "KDS",
        "subtitle": "Cocina, bebidas, empaque y entrega.",
        "status": "Pendiente",
    },
}


def render_platform_shell(active_path: str = "/") -> str:
    active_module = MODULES.get(active_path)
    page_title = active_module["title"] if active_module else "RestaurantOS"
    nav = "".join(_nav_item(path, module["title"], active_path) for path, module in MODULES.items())
    modules = "".join(_module_panel(path, module) for path, module in MODULES.items())
    headline = _headline(active_module)

    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(page_title)} | RestaurantOS</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8f6;
      --surface: #ffffff;
      --ink: #17201d;
      --muted: #5d6b64;
      --line: #dfe5df;
      --accent: #087f5b;
      --accent-soft: #dff4eb;
      --warn: #9a6700;
      --danger: #b42318;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    .layout {{
      display: grid;
      grid-template-columns: 248px minmax(0, 1fr);
      min-height: 100vh;
    }}
    aside {{
      border-right: 1px solid var(--line);
      background: #fbfcfa;
      padding: 24px 18px;
    }}
    .brand {{
      display: grid;
      gap: 4px;
      margin-bottom: 28px;
    }}
    .brand strong {{
      font-size: 20px;
      letter-spacing: 0;
    }}
    .brand span {{
      color: var(--muted);
      font-size: 13px;
    }}
    nav {{
      display: grid;
      gap: 6px;
    }}
    nav a {{
      color: var(--ink);
      text-decoration: none;
      border: 1px solid transparent;
      border-radius: 8px;
      padding: 10px 12px;
      font-size: 14px;
      font-weight: 650;
    }}
    nav a[aria-current="page"] {{
      background: var(--accent-soft);
      border-color: #b9e7d3;
      color: #075f45;
    }}
    main {{
      padding: 28px;
      display: grid;
      gap: 20px;
      align-content: start;
    }}
    .topbar {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      border-bottom: 1px solid var(--line);
      padding-bottom: 18px;
    }}
    h1 {{
      margin: 0;
      font-size: 28px;
      line-height: 1.15;
      letter-spacing: 0;
    }}
    .subtle {{
      color: var(--muted);
      margin: 8px 0 0;
      font-size: 14px;
      max-width: 760px;
    }}
    .status-pill {{
      white-space: nowrap;
      border: 1px solid var(--line);
      background: var(--surface);
      border-radius: 8px;
      padding: 9px 12px;
      font-size: 13px;
      font-weight: 700;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }}
    .panel {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      min-height: 144px;
      display: grid;
      align-content: space-between;
      gap: 18px;
    }}
    .panel h2 {{
      margin: 0;
      font-size: 17px;
      letter-spacing: 0;
    }}
    .panel p {{
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.45;
    }}
    .panel a {{
      color: var(--accent);
      font-weight: 700;
      text-decoration: none;
    }}
    .health {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
    }}
    .metric {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      min-height: 92px;
    }}
    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .metric strong {{
      display: block;
      margin-top: 8px;
      font-size: 18px;
      word-break: break-word;
    }}
    .ok {{ color: var(--accent); }}
    .degraded {{ color: var(--warn); }}
    .down {{ color: var(--danger); }}
    .links {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }}
    .links a {{
      color: var(--ink);
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 9px 12px;
      text-decoration: none;
      font-size: 13px;
      font-weight: 700;
    }}
    @media (max-width: 880px) {{
      .layout {{ grid-template-columns: 1fr; }}
      aside {{ border-right: 0; border-bottom: 1px solid var(--line); }}
      nav {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .topbar {{ align-items: flex-start; flex-direction: column; }}
      .grid, .health {{ grid-template-columns: 1fr; }}
      main {{ padding: 20px; }}
    }}
  </style>
</head>
<body>
  <div class="layout">
    <aside>
      <div class="brand">
        <strong>RestaurantOS</strong>
        <span>Kiwi Restaurante</span>
      </div>
      <nav aria-label="Modulos">
        <a href="/" {"aria-current='page'" if active_path == "/" else ""}>Inicio</a>
        {nav}
      </nav>
    </aside>
    <main>
      <section class="topbar">
        <div>{headline}</div>
        <div id="overall" class="status-pill">Verificando servicio</div>
      </section>
      <section class="health" aria-label="Estado de plataforma">
        <div class="metric"><span>API</span><strong id="api-status">...</strong></div>
        <div class="metric"><span>Postgres</span><strong id="postgres-status">...</strong></div>
        <div class="metric"><span>Redis</span><strong id="redis-status">...</strong></div>
        <div class="metric"><span>Ambiente</span><strong id="environment-status">...</strong></div>
      </section>
      <section class="health" aria-label="Datos base">
        <div class="metric"><span>Organizacion</span><strong id="organization-name">...</strong></div>
        <div class="metric"><span>Sucursal</span><strong id="branch-name">...</strong></div>
        <div class="metric"><span>Organizaciones</span><strong id="organization-count">...</strong></div>
        <div class="metric"><span>Sucursales</span><strong id="branch-count">...</strong></div>
      </section>
      <section class="health" aria-label="Control operativo">
        <div class="metric"><span>Usuarios</span><strong id="user-count">...</strong></div>
        <div class="metric"><span>Auditoria</span><strong id="audit-count">...</strong></div>
        <div class="metric"><span>Roles</span><strong id="role-count">...</strong></div>
        <div class="metric"><span>Almacenes</span><strong id="warehouse-count">...</strong></div>
      </section>
      <section class="grid" aria-label="Accesos">
        {modules}
      </section>
      <section class="links" aria-label="Herramientas">
        <a href="/docs">API Docs</a>
        <a href="/health/live">Live</a>
        <a href="/health/ready">Ready</a>
        <a href="/health/version">Version</a>
      </section>
    </main>
  </div>
  <script>
    const setText = (id, value, className) => {{
      const node = document.getElementById(id);
      node.textContent = value;
      node.className = className || "";
    }};

    fetch("/health/ready")
      .then((response) => response.json())
      .then((payload) => {{
        const deps = Object.fromEntries((payload.dependencies || []).map((item) => [item.name, item]));
        setText("api-status", payload.status || "unknown", payload.status || "");
        setText("postgres-status", deps.postgres?.status || "unknown", deps.postgres?.status || "");
        setText("redis-status", deps.redis?.status || "unknown", deps.redis?.status || "");
        setText("environment-status", payload.environment || "unknown", "");
        const ready = payload.status === "ok";
        const overall = document.getElementById("overall");
        overall.textContent = ready ? "Plataforma lista" : "Revision requerida";
        overall.className = "status-pill " + (ready ? "ok" : "degraded");
      }})
      .catch(() => {{
        setText("api-status", "down", "down");
        setText("postgres-status", "unknown", "degraded");
        setText("redis-status", "unknown", "degraded");
        setText("environment-status", "unknown", "");
        const overall = document.getElementById("overall");
        overall.textContent = "Servicio no disponible";
        overall.className = "status-pill down";
      }});

    fetch("/api/v1/platform/bootstrap-status")
      .then((response) => response.json())
      .then((payload) => {{
        const counts = payload.counts || {{}};
        setText("organization-name", payload.primary_organization?.name || "sin datos", "");
        setText("branch-name", payload.primary_branch?.name || "sin datos", "");
        setText("organization-count", counts.organizations ?? "0", "");
        setText("branch-count", counts.branches ?? "0", "");
        setText("user-count", counts.users ?? "0", "");
        setText("audit-count", counts.audit_events ?? "0", "");
        setText("role-count", counts.roles ?? "0", "");
        setText("warehouse-count", counts.warehouses ?? "0", "");
      }})
      .catch(() => {{
        setText("organization-name", "sin migrar", "degraded");
        setText("branch-name", "sin migrar", "degraded");
        setText("organization-count", "sin migrar", "degraded");
        setText("branch-count", "sin migrar", "degraded");
        setText("user-count", "sin migrar", "degraded");
        setText("audit-count", "sin migrar", "degraded");
        setText("role-count", "sin migrar", "degraded");
        setText("warehouse-count", "sin migrar", "degraded");
      }});
  </script>
</body>
</html>"""


def _headline(active_module: dict[str, str] | None) -> str:
    if active_module:
        return (
            f"<h1>{escape(active_module['title'])}</h1>"
            f"<p class='subtle'>{escape(active_module['subtitle'])}</p>"
        )

    return (
        "<h1>Consola inicial</h1>"
        "<p class='subtle'>Estado de plataforma, modulos base y accesos operativos de fase 0.</p>"
    )


def _nav_item(path: str, label: str, active_path: str) -> str:
    current = "aria-current='page'" if path == active_path else ""
    return f'<a href="{path}" {current}>{escape(label)}</a>'


def _module_panel(path: str, module: dict[str, str]) -> str:
    return f"""
        <article class="panel">
          <div>
            <h2>{escape(module["title"])}</h2>
            <p>{escape(module["subtitle"])}</p>
          </div>
          <a href="{path}">{escape(module["status"])}</a>
        </article>"""
