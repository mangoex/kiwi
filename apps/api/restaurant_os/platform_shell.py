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
    admin_panel = _admin_section(active_path)
    pos_catalog = _pos_catalog_section(active_path)
    kds_board = _kds_board_section(active_path)

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
      --surface-alt: #f1f5f2;
      --ink: #17201d;
      --muted: #5d6b64;
      --line: #dfe5df;
      --accent: #087f5b;
      --accent-soft: #dff4eb;
      --info: #1d4ed8;
      --info-soft: #dbeafe;
      --success: #0f7a4f;
      --warn: #9a6700;
      --warn-soft: #fff4de;
      --danger: #b42318;
      --danger-soft: #fee4e2;
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
      gap: 18px;
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
    .login-panel {{
      display: none;
      max-width: 1040px;
      min-height: 520px;
      background: linear-gradient(135deg, #f6fbff 0%, #ffffff 48%, #f4fff6 100%);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 24px 70px rgba(34, 48, 68, 0.12);
      overflow: hidden;
      grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
    }}
    .login-panel.active {{
      display: grid;
    }}
    .login-visual {{
      padding: 34px;
      display: grid;
      gap: 18px;
      align-content: center;
      background: radial-gradient(circle at 22% 18%, rgba(194, 255, 41, 0.32), transparent 30%),
        radial-gradient(circle at 80% 72%, rgba(47, 100, 246, 0.18), transparent 34%),
        #f8fafc;
    }}
    .login-card-stack {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .soft-card {{
      background: rgba(255, 255, 255, 0.82);
      border: 1px solid rgba(224, 231, 240, 0.9);
      border-radius: 8px;
      padding: 16px;
      box-shadow: 10px 14px 30px rgba(74, 85, 104, 0.12), -10px -10px 26px rgba(255, 255, 255, 0.9);
      min-height: 108px;
    }}
    .soft-card strong {{
      display: block;
      font-size: 24px;
      margin-top: 8px;
    }}
    .login-form {{
      padding: 34px;
      background: var(--surface);
      display: grid;
      gap: 16px;
      align-content: center;
    }}
    .login-form input {{
      max-width: none;
      min-height: 44px;
    }}
    .session-strip {{
      display: none;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px 14px;
    }}
    .session-strip.active {{
      display: flex;
    }}
    .admin-secured {{
      display: none;
    }}
    .admin-secured.active {{
      display: grid;
      gap: 16px;
    }}
    .action-row {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }}
    button {{
      border: 1px solid #0a6f52;
      background: var(--accent);
      color: white;
      border-radius: 8px;
      padding: 9px 12px;
      min-height: 40px;
      font-size: 13px;
      font-weight: 750;
      cursor: pointer;
      transition: background 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
    }}
    button:hover {{ box-shadow: 0 0 0 3px rgba(8, 127, 91, 0.14); }}
    button:focus-visible, a:focus-visible, input:focus-visible, select:focus-visible {{
      outline: 3px solid rgba(8, 127, 91, 0.26);
      outline-offset: 2px;
    }}
    button.secondary {{
      background: var(--surface);
      color: var(--ink);
      border-color: var(--line);
    }}
    input {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 9px 10px;
      font: inherit;
      max-width: 140px;
    }}
    select {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 9px 10px;
      font: inherit;
      min-height: 40px;
      background: var(--surface);
    }}
    label {{
      display: grid;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 750;
      text-transform: uppercase;
    }}
    label input, label select {{
      color: var(--ink);
      text-transform: none;
      font-weight: 500;
      max-width: none;
    }}
    .workbench {{
      display: grid;
      grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
      gap: 16px;
      align-items: start;
    }}
    .workbench.wide {{
      grid-template-columns: minmax(300px, 420px) minmax(0, 1fr);
    }}
    .stack {{
      display: grid;
      gap: 14px;
    }}
    .form-grid {{
      display: grid;
      gap: 12px;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      min-width: 680px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 11px 12px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0;
      background: #fbfcfa;
      position: sticky;
      top: 0;
      z-index: 1;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    .row-title {{
      display: grid;
      gap: 3px;
    }}
    .row-title strong {{
      font-size: 13px;
    }}
    .row-title span {{
      color: var(--muted);
      font-size: 12px;
    }}
    .chip {{
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      border-radius: 8px;
      border: 1px solid #b9e7d3;
      background: var(--accent-soft);
      color: #075f45;
      padding: 3px 7px;
      font-size: 12px;
      font-weight: 750;
      margin: 0 4px 4px 0;
    }}
    .chip.warn {{
      background: var(--warn-soft);
      border-color: #ffd89a;
      color: var(--warn);
    }}
    .chip.danger {{
      background: var(--danger-soft);
      border-color: #fecdca;
      color: var(--danger);
    }}
    .chip.info {{
      background: var(--info-soft);
      border-color: #bfdbfe;
      color: var(--info);
    }}
    .amount {{
      font-variant-numeric: tabular-nums;
      font-weight: 800;
    }}
    .amount.positive {{ color: var(--success); }}
    .amount.negative {{ color: var(--danger); }}
    .amount.neutral {{ color: var(--muted); }}
    .message {{
      min-height: 20px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 650;
    }}
    .module-tabs {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 12px;
    }}
    .module-tabs button {{
      background: var(--surface);
      color: var(--ink);
      border-color: var(--line);
      min-height: 40px;
    }}
    .module-tabs button[aria-pressed="true"] {{
      background: var(--accent);
      border-color: #0a6f52;
      color: white;
    }}
    .admin-view {{
      display: none;
    }}
    .admin-view.active {{
      display: grid;
      gap: 16px;
    }}
    .hero-band {{
      background: linear-gradient(135deg, #10251e 0%, #174633 58%, #284230 100%);
      color: white;
      border-radius: 8px;
      padding: 22px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 16px;
      align-items: center;
    }}
    .hero-band p {{
      color: #c9ded5;
      margin: 8px 0 0;
    }}
    .hero-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      justify-content: flex-end;
    }}
    .hero-actions a {{
      color: white;
      border-color: rgba(255, 255, 255, 0.32);
      background: rgba(255, 255, 255, 0.12);
      text-decoration: none;
    }}
    .section-kicker {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .module-strip {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }}
    .module-card {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      min-height: 116px;
      text-decoration: none;
      color: var(--ink);
      display: grid;
      gap: 8px;
      align-content: start;
    }}
    .module-card:hover {{
      border-color: #b9e7d3;
      box-shadow: 0 12px 28px rgba(23, 32, 29, 0.08);
    }}
    .module-card strong {{
      font-size: 16px;
    }}
    .module-card span {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }}
    .command-center {{
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(260px, 0.65fr);
      gap: 14px;
      align-items: stretch;
    }}
    .readiness-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .readiness-step {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      min-height: 132px;
      display: grid;
      gap: 10px;
      align-content: space-between;
    }}
    .readiness-step.ready {{
      border-color: #b9e7d3;
      background: linear-gradient(180deg, #ffffff 0%, #f4fbf8 100%);
    }}
    .readiness-step.pending {{
      border-color: #ffd89a;
      background: linear-gradient(180deg, #ffffff 0%, #fffaf0 100%);
    }}
    .readiness-head {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: flex-start;
    }}
    .readiness-head strong {{
      display: block;
      font-size: 15px;
    }}
    .readiness-step p {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }}
    .progress-track {{
      height: 8px;
      border-radius: 999px;
      background: var(--surface-alt);
      overflow: hidden;
    }}
    .progress-bar {{
      display: block;
      height: 100%;
      border-radius: inherit;
      background: var(--accent);
    }}
    .ops-pulse {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      display: grid;
      gap: 12px;
    }}
    .ops-pulse-row {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      border-bottom: 1px solid var(--line);
      padding-bottom: 10px;
      font-size: 13px;
    }}
    .ops-pulse-row:last-child {{
      border-bottom: 0;
      padding-bottom: 0;
    }}
    .ops-pulse-row span {{
      color: var(--muted);
      font-weight: 700;
    }}
    .ops-pulse-row strong {{
      text-align: right;
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
    }}
    .toolbar h2 {{
      margin: 0;
    }}
    .metric.compact {{
      min-height: 74px;
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
    .catalog-list {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }}
    .product-tile {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      min-height: 132px;
      display: grid;
      gap: 12px;
    }}
    .product-tile h2 {{
      margin: 0;
      font-size: 17px;
      letter-spacing: 0;
    }}
    .product-meta {{
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }}
    .product-footer {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      font-weight: 750;
    }}
    .availability {{
      border-radius: 8px;
      background: var(--accent-soft);
      color: #075f45;
      padding: 5px 8px;
      font-size: 12px;
    }}
    .availability.unavailable {{
      background: #fff4de;
      color: var(--warn);
    }}
    @media (max-width: 880px) {{
      .layout {{ grid-template-columns: 1fr; }}
      aside {{ border-right: 0; border-bottom: 1px solid var(--line); }}
      nav {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .topbar {{ align-items: flex-start; flex-direction: column; }}
      .grid, .health, .catalog-list, .workbench, .workbench.wide, .hero-band, .module-strip, .command-center, .readiness-grid, .login-panel, .login-card-stack {{ grid-template-columns: 1fr; }}
      .hero-actions {{ justify-content: flex-start; }}
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
      <section class="health" aria-label="Catalogo minimo">
        <div class="metric"><span>Categorias</span><strong id="category-count">...</strong></div>
        <div class="metric"><span>Productos</span><strong id="product-count">...</strong></div>
        <div class="metric"><span>Precios</span><strong id="price-count">...</strong></div>
        <div class="metric"><span>Menu</span><strong id="menu-status">...</strong></div>
      </section>
      <section class="health" aria-label="Operacion fase 1">
        <div class="metric"><span>Turnos</span><strong id="cash-shift-count">...</strong></div>
        <div class="metric"><span>Pedidos</span><strong id="order-count">...</strong></div>
        <div class="metric"><span>Tareas KDS</span><strong id="task-count">...</strong></div>
        <div class="metric"><span>Flujo</span><strong id="flow-status">...</strong></div>
      </section>
      <section class="grid" aria-label="Accesos">
        {modules}
      </section>
      {admin_panel}
      {pos_catalog}
      {kds_board}
      <section class="links" aria-label="Herramientas">
        <a href="/docs">API Docs</a>
        <a href="/health/live">Live</a>
        <a href="/health/ready">Ready</a>
        <a href="/api/v1/catalog/products">Catalogo API</a>
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
    const apiJson = async (url, options) => {{
      const requestOptions = options || {{}};
      const headers = {{
        ...(authSession?.token ? {{ Authorization: `Bearer ${{authSession.token}}` }} : {{}}),
        ...(authSession?.user?.id ? {{ "X-Actor-User-Id": authSession.user.id }} : {{}}),
        ...(requestOptions.headers || {{}}),
      }};
      const response = await fetch(url, {{ ...requestOptions, headers }});
      const payload = await response.json();
      if (!response.ok) throw payload;
      return payload;
    }};
    const authStorageKey = "restaurantos.session";
    let authSession = null;
    try {{
      authSession = JSON.parse(localStorage.getItem(authStorageKey) || "null");
    }} catch {{
      authSession = null;
    }}
    const setAuthSession = (session) => {{
      authSession = session;
      if (session) localStorage.setItem(authStorageKey, JSON.stringify(session));
      else localStorage.removeItem(authStorageKey);
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
        setText("category-count", counts.product_categories ?? "0", "");
        setText("product-count", counts.products ?? "0", "");
        setText("price-count", counts.price_versions ?? "0", "");
        setText("menu-status", (counts.products || 0) > 0 ? "semilla lista" : "pendiente", "");
        setText("cash-shift-count", counts.cash_shifts ?? "0", "");
        setText("order-count", counts.orders ?? "0", "");
        setText("task-count", counts.production_tasks ?? "0", "");
        setText("flow-status", `pagos ${{counts.payments || 0}} · sync ${{counts.sync_commands || 0}} · prints ${{counts.print_jobs || 0}}`, "");
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
        setText("category-count", "sin migrar", "degraded");
        setText("product-count", "sin migrar", "degraded");
        setText("price-count", "sin migrar", "degraded");
        setText("menu-status", "sin migrar", "degraded");
        setText("cash-shift-count", "sin migrar", "degraded");
        setText("order-count", "sin migrar", "degraded");
        setText("task-count", "sin migrar", "degraded");
        setText("flow-status", "sin migrar", "degraded");
      }});

    const adminMessage = document.getElementById("admin-message");
    const setAdminMessage = (value) => {{
      if (adminMessage) adminMessage.textContent = value;
    }};
    const catalogMessage = document.getElementById("catalog-message");
    const setCatalogMessage = (value) => {{
      if (catalogMessage) catalogMessage.textContent = value;
    }};
    const inventoryMessage = document.getElementById("inventory-message");
    const setInventoryMessage = (value) => {{
      if (inventoryMessage) inventoryMessage.textContent = value;
    }};
    let adminUsers = [];
    let adminRoles = [];
    let adminBranches = [];
    let adminProducts = [];
    let inventoryStock = [];
    const initializeAdminSession = () => {{
      const loginPanel = document.getElementById("login-panel");
      const loginMessage = document.getElementById("login-message");
      const sessionStrip = document.getElementById("session-strip");
      const sessionName = document.getElementById("session-name");
      const securedBlocks = document.querySelectorAll(".admin-secured");
      if (!loginPanel) return true;
      const isSignedIn = Boolean(authSession?.token && authSession?.user);
      loginPanel.classList.toggle("active", !isSignedIn);
      sessionStrip?.classList.toggle("active", isSignedIn);
      securedBlocks.forEach((block) => block.classList.toggle("active", isSignedIn));
      if (sessionName && isSignedIn) {{
        sessionName.textContent = `${{authSession.user.display_name}} · ${{authSession.user.email}}`;
      }}
      if (loginMessage && !isSignedIn) loginMessage.textContent = "Ingresa con tu cuenta superadmin.";
      return isSignedIn;
    }};
    const activateAdminTab = (name) => {{
      document.querySelectorAll("[data-admin-tab]").forEach((button) => {{
        button.setAttribute("aria-pressed", button.dataset.adminTab === name ? "true" : "false");
      }});
      document.querySelectorAll(".admin-view").forEach((view) => view.classList.remove("active"));
      const target = document.getElementById(`admin-${{name}}`);
      if (target) target.classList.add("active");
    }};
    document.querySelectorAll("[data-admin-tab]").forEach((button) => {{
      button.addEventListener("click", () => activateAdminTab(button.dataset.adminTab));
    }});
    document.querySelectorAll("[data-admin-jump]").forEach((link) => {{
      link.addEventListener("click", (event) => {{
        event.preventDefault();
        activateAdminTab(link.dataset.adminJump);
        window.scrollTo({{ top: 0, behavior: "smooth" }});
      }});
    }});
    const loginButton = document.getElementById("login-button");
    if (loginButton) {{
      loginButton.addEventListener("click", () => {{
        const email = document.getElementById("login-email").value;
        const password = document.getElementById("login-password").value;
        const loginMessage = document.getElementById("login-message");
        if (loginMessage) loginMessage.textContent = "Validando acceso...";
        apiJson("/api/v1/auth/login", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ email, password }}),
        }})
          .then((session) => {{
            setAuthSession(session);
            initializeAdminSession();
            refreshAdmin();
          }})
          .catch(() => {{
            if (loginMessage) loginMessage.textContent = "Correo o contraseña no validos.";
          }});
      }});
    }}
    const logoutButton = document.getElementById("logout-button");
    if (logoutButton) {{
      logoutButton.addEventListener("click", () => {{
        setAuthSession(null);
        initializeAdminSession();
      }});
    }}
    const renderReadinessStep = (step) => `
      <article class="readiness-step ${{step.ready ? "ready" : "pending"}}" data-readiness-key="${{step.key}}">
        <div class="readiness-head">
          <div>
            <span class="section-kicker">${{step.label}}</span>
            <strong>${{step.title}}</strong>
          </div>
          <span class="chip ${{step.ready ? "" : "warn"}}">${{step.status}}</span>
        </div>
        <p>${{step.detail}}</p>
        <div class="progress-track" aria-label="Avance ${{step.title}}">
          <span class="progress-bar" style="width: ${{step.progress}}%"></span>
        </div>
        <button class="secondary" type="button" data-admin-jump="${{step.target}}">${{step.action}}</button>
      </article>`;
    const bindAdminJumpControls = (root) => {{
      root.querySelectorAll("[data-admin-jump]").forEach((control) => {{
        control.addEventListener("click", (event) => {{
          event.preventDefault();
          activateAdminTab(control.dataset.adminJump);
          window.scrollTo({{ top: 0, behavior: "smooth" }});
        }});
      }});
    }};
    const updateSaasCommandCenter = ({{
      branches,
      products,
      users,
      roles,
      stock,
      kardex,
      syncStatus,
    }}) => {{
      const readinessSteps = document.getElementById("readiness-steps");
      const opsPulse = document.getElementById("ops-pulse");
      const lowStock = stock.filter((item) => Number(item.quantity_on_hand || 0) <= 0).length;
      const protectedRoles = roles.filter((role) => (role.permissions || []).length > 0).length;
      const steps = [
        {{
          key: "catalogs",
          label: "Catalogos",
          title: "Sucursal y menu listos",
          ready: branches.length > 0 && products.length > 0,
          status: branches.length > 0 && products.length > 0 ? "Listo" : "Pendiente",
          detail: `${{branches.length}} sucursal(es), ${{products.length}} producto(s) y precios vigentes para venta.`,
          progress: branches.length > 0 && products.length > 0 ? 100 : branches.length > 0 ? 50 : 20,
          target: "catalogs",
          action: "Abrir Catalogos",
        }},
        {{
          key: "inventory",
          label: "Inventario",
          title: "Stock trazable",
          ready: stock.length > 0 && kardex.length > 0,
          status: stock.length > 0 && kardex.length > 0 ? "Listo" : "Pendiente",
          detail: `${{stock.length}} insumo(s), ${{kardex.length}} movimiento(s), ${{lowStock}} alerta(s).`,
          progress: stock.length > 0 && kardex.length > 0 ? 100 : stock.length > 0 ? 60 : 25,
          target: "inventory",
          action: "Abrir Inventario",
        }},
        {{
          key: "users",
          label: "Accesos",
          title: "Roles y permisos",
          ready: users.length > 0 && protectedRoles > 0,
          status: users.length > 0 && protectedRoles > 0 ? "Listo" : "Pendiente",
          detail: `${{users.length}} usuario(s), ${{roles.length}} rol(es), ${{protectedRoles}} rol(es) con permisos sensibles.`,
          progress: users.length > 0 && protectedRoles > 0 ? 100 : users.length > 0 ? 65 : 30,
          target: "users",
          action: "Abrir Usuarios",
        }},
        {{
          key: "system",
          label: "Sistema",
          title: "Sincronizacion observable",
          ready: Boolean(syncStatus),
          status: syncStatus ? "Listo" : "Pendiente",
          detail: syncStatus
            ? `Checkpoint ${{syncStatus.last_checkpoint}} con ${{syncStatus.event_count}} evento(s).`
            : "Estado de sincronizacion aun no disponible.",
          progress: syncStatus ? 100 : 35,
          target: "system",
          action: "Abrir Sistema",
        }},
      ];
      if (readinessSteps) {{
        readinessSteps.innerHTML = steps.map(renderReadinessStep).join("");
        bindAdminJumpControls(readinessSteps);
      }}
      if (opsPulse) {{
        opsPulse.innerHTML = `
          <div class="ops-pulse-row"><span>Preparacion</span><strong>${{steps.filter((step) => step.ready).length}}/4 modulos listos</strong></div>
          <div class="ops-pulse-row"><span>Catalogo</span><strong>${{branches.length}} sucursal(es) Â· ${{products.length}} producto(s)</strong></div>
          <div class="ops-pulse-row"><span>Inventario</span><strong>${{stock.length}} insumo(s) Â· ${{lowStock}} alerta(s)</strong></div>
          <div class="ops-pulse-row"><span>Accesos</span><strong>${{users.length}} usuario(s) Â· ${{protectedRoles}} rol(es) protegido(s)</strong></div>
          <div class="ops-pulse-row"><span>Sync</span><strong>${{syncStatus ? syncStatus.last_checkpoint : "pendiente"}}</strong></div>`;
      }}
    }};
    const refreshAdmin = () => {{
      const usersTable = document.getElementById("users-table");
      const rolesTable = document.getElementById("roles-table");
      const branchesTable = document.getElementById("branches-table");
      const productsTable = document.getElementById("products-table");
      const inventoryTable = document.getElementById("inventory-stock-table");
      const kardexTable = document.getElementById("inventory-kardex-table");
      const recipesTable = document.getElementById("recipes-table");
      if (!usersTable && !rolesTable && !branchesTable && !productsTable && !inventoryTable && !kardexTable && !recipesTable) return;
      Promise.all([
        apiJson("/api/v1/users"),
        apiJson("/api/v1/roles"),
        apiJson("/api/v1/branches"),
        apiJson("/api/v1/catalog/products"),
        apiJson("/api/v1/inventory/stock"),
        apiJson("/api/v1/inventory/kardex"),
        apiJson("/api/v1/recipes"),
        apiJson("/api/v1/sync/status").catch(() => null),
      ])
        .then(([users, roles, branches, products, stock, kardex, recipes, syncStatus]) => {{
          adminUsers = users;
          adminRoles = roles;
          adminBranches = branches;
          adminProducts = products;
          inventoryStock = stock;
          setText("admin-branch-count", branches.length, "");
          setText("admin-product-count", products.length, "");
          setText("admin-user-count", users.length, "");
          setText("admin-sync-count", syncStatus ? syncStatus.last_checkpoint : "pendiente", "");
          setText("inventory-item-count", stock.length, "");
          setText("inventory-movement-count", kardex.length, "");
          const lowStock = stock.filter((item) => Number(item.quantity_on_hand || 0) <= 0).length;
          setText("inventory-alert-count", lowStock, "");
          updateSaasCommandCenter({{ branches, products, users, roles, stock, kardex, syncStatus }});
          const systemSummary = document.getElementById("admin-system-summary");
          if (systemSummary && syncStatus) {{
            systemSummary.textContent = `Checkpoint ${{syncStatus.last_checkpoint}} · comandos ${{syncStatus.command_count}} · eventos ${{syncStatus.event_count}}`;
          }}
          if (usersTable) usersTable.innerHTML = users.length
            ? users.map((user) => `
              <tr>
                <td>${{user.display_name}}</td>
                <td>${{user.email}}</td>
                <td><span class="chip">${{user.status}}</span></td>
                <td>${{user.roles.length ? user.roles.map((role) => `<span class="chip">${{role.role_name}}</span>`).join("") : "Sin rol"}}</td>
              </tr>`).join("")
            : '<tr><td colspan="4">Sin usuarios registrados.</td></tr>';
          if (rolesTable) rolesTable.innerHTML = roles.length
            ? roles.map((role) => `
              <tr>
                <td>${{role.name}}</td>
                <td><span class="chip">${{role.scope}}</span></td>
                <td>${{role.permissions?.length ? role.permissions.map((permission) => `<span class="chip info">${{permission}}</span>`).join("") : '<span class="chip warn">Sin permisos sensibles</span>'}}</td>
                <td>${{new Date(role.created_at).toLocaleString("es-MX")}}</td>
              </tr>`).join("")
            : '<tr><td colspan="4">Sin roles registrados.</td></tr>';
          if (branchesTable) branchesTable.innerHTML = branches.length
            ? branches.map((branch) => `
              <tr>
                <td><span class="row-title"><strong>${{branch.name}}</strong><span>${{branch.status || "active"}}</span></span></td>
                <td><span class="chip">${{branch.code}}</span></td>
                <td>${{branch.legal_entity_name}}</td>
                <td>${{branch.warehouse_name}}</td>
              </tr>`).join("")
            : '<tr><td colspan="4">Sin sucursales registradas.</td></tr>';
          if (productsTable) productsTable.innerHTML = products.length
            ? products.map((product) => `
              <tr>
                <td><span class="row-title"><strong>${{product.name}}</strong><span>${{product.description || "Producto activo"}}</span></span></td>
                <td><span class="chip">${{product.sku}}</span></td>
                <td>${{product.category_name}}</td>
                <td><span class="chip info">${{product.station}}</span></td>
                <td>${{formatMoney(product.price_cents)}}</td>
                <td>${{product.is_available ? '<span class="chip">Disponible</span>' : '<span class="chip warn">No disponible</span>'}}</td>
              </tr>`).join("")
            : '<tr><td colspan="6">Sin productos registrados.</td></tr>';
          if (inventoryTable) inventoryTable.innerHTML = stock.length
            ? stock.map((item) => `
              <tr>
                <td><span class="row-title"><strong>${{item.name}}</strong><span>${{item.item_type || "ingredient"}}</span></span></td>
                <td><span class="chip">${{item.sku}}</span></td>
                <td>${{item.warehouse_name || "Sin almacen"}}</td>
                <td><span class="amount ${{Number(item.quantity_on_hand || 0) <= 0 ? "negative" : "positive"}}">${{item.quantity_on_hand}} ${{item.unit_code}}</span></td>
                <td>${{item.last_movement_at ? new Date(item.last_movement_at).toLocaleString("es-MX") : "Sin movimiento"}}</td>
              </tr>`).join("")
            : '<tr><td colspan="5">Sin insumos registrados.</td></tr>';
          if (kardexTable) kardexTable.innerHTML = kardex.length
            ? kardex.map((movement) => `
              <tr>
                <td>${{new Date(movement.created_at).toLocaleString("es-MX")}}</td>
                <td>${{movement.item_name}}</td>
                <td><span class="chip ${{movement.movement_type === "WASTE" ? "warn" : movement.movement_type === "RECOVERY" ? "" : movement.movement_type === "SALE_CONSUMPTION" || movement.movement_type === "SALE_RESERVATION" ? "danger" : "info"}}">${{movement.movement_type}}</span></td>
                <td><span class="amount ${{Number(movement.quantity_delta || 0) > 0 ? "positive" : Number(movement.quantity_delta || 0) < 0 ? "negative" : "neutral"}}">${{movement.quantity_delta}} ${{movement.unit_code}}</span></td>
                <td>${{movement.reason}}</td>
              </tr>`).join("")
            : '<tr><td colspan="5">Sin movimientos.</td></tr>';
          if (recipesTable) recipesTable.innerHTML = recipes.length
            ? recipes.map((recipe) => `
              <tr>
                <td><span class="row-title"><strong>${{recipe.product_name}}</strong><span>${{recipe.product_sku}}</span></span></td>
                <td><span class="chip">v${{recipe.version}}</span></td>
                <td>${{recipe.yield_quantity}} ${{recipe.yield_unit_code}}</td>
                <td>${{recipe.components.map((component) => `${{component.item_name}} ${{component.quantity_base_units}}${{component.unit_code}}`).join(", ")}}</td>
              </tr>`).join("")
            : '<tr><td colspan="4">Sin recetas vigentes.</td></tr>';
          const userSelect = document.getElementById("assign-user");
          const roleSelect = document.getElementById("assign-role");
          const inventoryItemSelect = document.getElementById("inventory-item-input");
          if (userSelect) {{
            userSelect.innerHTML = users.map((user) => `<option value="${{user.id}}">${{user.display_name}}</option>`).join("");
          }}
          if (roleSelect) {{
            roleSelect.innerHTML = roles.map((role) => `<option value="${{role.id}}">${{role.name}}</option>`).join("");
          }}
          if (inventoryItemSelect) {{
            inventoryItemSelect.innerHTML = stock.map((item) => `<option value="${{item.id}}">${{item.name}} (${{item.unit_code}})</option>`).join("");
          }}
        }})
        .catch(() => {{
          setAdminMessage("No se pudo cargar Admin.");
          setCatalogMessage("No se pudieron cargar catalogos.");
          setInventoryMessage("No se pudo cargar inventario.");
        }});
    }};
    const createRoleButton = document.getElementById("create-role");
    if (createRoleButton) {{
      createRoleButton.addEventListener("click", () => {{
        const name = document.getElementById("role-name").value;
        const scope = document.getElementById("role-scope").value;
        setAdminMessage("Creando rol...");
        apiJson("/api/v1/roles", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ name, scope }}),
        }})
          .then(() => {{
            setAdminMessage("Rol creado.");
            refreshAdmin();
          }})
          .catch((error) => setAdminMessage(error?.detail?.message || "No se pudo crear el rol."));
      }});
    }}
    const createUserButton = document.getElementById("create-user");
    if (createUserButton) {{
      createUserButton.addEventListener("click", () => {{
        const display_name = document.getElementById("user-display-name").value;
        const email = document.getElementById("user-email").value;
        const password = document.getElementById("user-password").value;
        setAdminMessage("Invitando usuario...");
        apiJson("/api/v1/users", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ display_name, email, password }}),
        }})
          .then(() => {{
            setAdminMessage("Usuario invitado.");
            refreshAdmin();
          }})
          .catch((error) => setAdminMessage(error?.detail?.message || "No se pudo invitar el usuario."));
      }});
    }}
    const assignRoleButton = document.getElementById("assign-role-button");
    if (assignRoleButton) {{
      assignRoleButton.addEventListener("click", () => {{
        const userId = document.getElementById("assign-user").value;
        const roleId = document.getElementById("assign-role").value;
        if (!userId || !roleId) {{
          setAdminMessage("Selecciona usuario y rol.");
          return;
        }}
        setAdminMessage("Asignando rol...");
        apiJson(`/api/v1/users/${{userId}}/roles`, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ role_id: roleId }}),
        }})
          .then(() => {{
            setAdminMessage("Rol asignado.");
            refreshAdmin();
          }})
          .catch((error) => setAdminMessage(error?.detail?.message || "No se pudo asignar el rol."));
      }});
    }}
    const createBranchButton = document.getElementById("create-branch");
    if (createBranchButton) {{
      createBranchButton.addEventListener("click", () => {{
        const name = document.getElementById("branch-name-input").value;
        const code = document.getElementById("branch-code-input").value;
        setCatalogMessage("Creando sucursal...");
        apiJson("/api/v1/branches", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ name, code }}),
        }})
          .then(() => {{
            setCatalogMessage("Sucursal creada.");
            refreshAdmin();
          }})
          .catch((error) => setCatalogMessage(error?.detail?.message || "No se pudo crear la sucursal."));
      }});
    }}
    const createProductButton = document.getElementById("create-product");
    if (createProductButton) {{
      createProductButton.addEventListener("click", () => {{
        const name = document.getElementById("product-name-input").value;
        const sku = document.getElementById("product-sku-input").value;
        const category_name = document.getElementById("product-category-input").value;
        const station = document.getElementById("product-station-input").value;
        const price_cents = Math.round(Number(document.getElementById("product-price-input").value || 0) * 100);
        setCatalogMessage("Creando producto...");
        apiJson("/api/v1/catalog/products", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ name, sku, category_name, station, price_cents }}),
        }})
          .then(() => {{
            setCatalogMessage("Producto creado.");
            refreshAdmin();
          }})
          .catch((error) => setCatalogMessage(error?.detail?.message || "No se pudo crear el producto."));
      }});
    }}
    const openingBalanceButton = document.getElementById("record-opening-balance");
    if (openingBalanceButton) {{
      openingBalanceButton.addEventListener("click", () => {{
        const item_id = document.getElementById("inventory-item-input").value;
        const quantity_base_units = Number(document.getElementById("inventory-quantity-input").value || 0);
        const reason = document.getElementById("inventory-reason-input").value;
        setInventoryMessage("Registrando movimiento...");
        apiJson("/api/v1/inventory/opening-balances", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ item_id, quantity_base_units, reason }}),
        }})
          .then(() => {{
            setInventoryMessage("Movimiento registrado.");
            refreshAdmin();
          }})
          .catch((error) => setInventoryMessage(error?.detail?.message || "No se pudo registrar el movimiento."));
      }});
    }}
    if (initializeAdminSession()) refreshAdmin();

    const catalogNode = document.getElementById("pos-catalog");
    if (catalogNode) {{
      const money = new Intl.NumberFormat("es-MX", {{
        style: "currency",
        currency: "MXN",
      }});
      fetch("/api/v1/catalog/products")
        .then((response) => response.json())
        .then((products) => {{
          if (!Array.isArray(products) || products.length === 0) {{
            catalogNode.innerHTML = '<article class="panel"><h2>Catalogo pendiente</h2><p>No hay productos activos para POS.</p></article>';
            return;
          }}

          catalogNode.innerHTML = products
            .map((product) => {{
              const available = Boolean(product.is_available);
              const price = money.format((product.price_cents || 0) / 100);
              return `
                <article class="product-tile">
                  <div>
                    <h2>${{product.name || "Producto"}}</h2>
                    <div class="product-meta">
                      ${{product.category_name || "Sin categoria"}} · ${{product.sku || "sin-sku"}}<br />
                      Estacion: ${{product.station || "sin estacion"}}
                    </div>
                  </div>
                  <div class="product-footer">
                    <span>${{price}}</span>
                    <button data-product-id="${{product.id}}" ${{available ? "" : "disabled"}}>
                      ${{available ? "Crear pedido" : "Agotado"}}
                    </button>
                  </div>
                </article>`;
            }})
            .join("");
          catalogNode.querySelectorAll("button[data-product-id]").forEach((button) => {{
            button.addEventListener("click", () => createOrder(button.dataset.productId));
          }});
        }})
        .catch(() => {{
          catalogNode.innerHTML = '<article class="panel"><h2>Catalogo no disponible</h2><p>Ejecuta migraciones y revisa la conexion de Postgres.</p></article>';
        }});
    }}

    const cashStatus = document.getElementById("cash-status");
    const cashSummary = document.getElementById("cash-summary");
    const orderStatus = document.getElementById("order-status");
    const setCashStatus = (value) => {{
      if (cashStatus) cashStatus.textContent = value;
    }};
    const setOrderStatus = (value) => {{
      if (orderStatus) orderStatus.textContent = value;
    }};
    const formatMoney = (cents) => `$${{((cents || 0) / 100).toFixed(2)}} MXN`;
    const refreshCash = () => {{
      if (!cashStatus) return;
      fetch("/api/v1/cash-shifts/summary")
        .then((response) => response.json())
        .then((payload) => {{
          const shift = payload.cash_shift;
          const summary = payload.summary || payload.cut;
          setCashStatus(shift ? `Turno ${{shift.status.toLowerCase()}}: ${{shift.register_code}}` : "Sin turno abierto");
          if (cashSummary && summary) {{
            cashSummary.textContent = `Ventas ${{formatMoney(summary.sales_total_cents)}} · esperado ${{formatMoney(summary.expected_cash_cents)}}`;
            const counted = document.getElementById("counted-cash");
            if (counted && shift?.status === "OPEN") counted.value = String((summary.expected_cash_cents || 0) / 100);
          }} else if (cashSummary) {{
            cashSummary.textContent = "Sin corte disponible.";
          }}
        }})
        .catch(() => setCashStatus("Caja no disponible"));
    }};
    const createOrder = (productId) => {{
      setOrderStatus("Creando pedido...");
      fetch("/api/v1/orders", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ product_id: productId, quantity: 1 }}),
      }})
        .then(async (response) => {{
          const payload = await response.json();
          if (!response.ok) throw payload;
          setOrderStatus(`Pedido ${{payload.folio}} creado y enviado a KDS`);
          refreshOrders();
          refreshCash();
        }})
        .catch((error) => {{
          const message = error?.detail?.message || "No se pudo crear el pedido";
          setOrderStatus(message);
        }});
    }};
    const refreshOrders = () => {{
      const node = document.getElementById("recent-orders");
      if (!node) return;
      fetch("/api/v1/orders")
        .then((response) => response.json())
        .then((orders) => {{
          node.innerHTML = orders.length
            ? orders.map((order) => `
              <article class="panel">
                <div>
                  <h2>${{order.folio}}</h2>
                  <p>${{order.status}} · ${{formatMoney(order.total_cents)}}</p>
                </div>
                ${{order.status === "ACCEPTED" ? `
                  <div class="action-row">
                    <button data-pay-order-id="${{order.id}}" data-total-cents="${{order.total_cents}}">Cobrar</button>
                    <button class="secondary" data-cancel-order-id="${{order.id}}">Cancelar</button>
                  </div>` : ""}}
              </article>`).join("")
            : '<article class="panel"><h2>Sin pedidos</h2><p>Crea un pedido desde el catalogo.</p></article>';
          node.querySelectorAll("button[data-pay-order-id]").forEach((button) => {{
            button.addEventListener("click", () => payOrder(button.dataset.payOrderId, Number(button.dataset.totalCents)));
          }});
          node.querySelectorAll("button[data-cancel-order-id]").forEach((button) => {{
            button.addEventListener("click", () => cancelOrder(button.dataset.cancelOrderId));
          }});
        }})
        .catch(() => {{
          node.innerHTML = '<article class="panel"><h2>Pedidos no disponibles</h2><p>Revisa migraciones.</p></article>';
        }});
    }};
    const payOrder = (orderId, totalCents) => {{
      setOrderStatus("Registrando pago...");
      fetch(`/api/v1/orders/${{orderId}}/payments`, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ amount_cents: totalCents, method: "cash" }}),
      }})
        .then(async (response) => {{
          const payload = await response.json();
          if (!response.ok) throw payload;
          setOrderStatus("Pago confirmado, pedido cerrado e impresion simulada creada");
          refreshOrders();
          refreshCash();
          refreshPrintJobs();
        }})
        .catch((error) => setOrderStatus(error?.detail?.message || "No se pudo cobrar el pedido"));
    }};
    const cancelOrder = (orderId) => {{
      setOrderStatus("Cancelando pedido...");
      submitCancellation(orderId, null);
    }};
    const submitCancellation = (orderId, classification) => {{
      fetch(`/api/v1/orders/${{orderId}}/cancel`, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ reason: "Cancelado desde POS", classification }}),
      }})
        .then(async (response) => {{
          const payload = await response.json();
          if (!response.ok) throw payload;
          const label = payload.classification === "recovery" ? "recuperacion registrada" : payload.classification === "waste" ? "merma registrada" : "reserva liberada";
          setOrderStatus(`Pedido ${{payload.folio}} cancelado: ${{label}}`);
          refreshOrders();
          refreshCash();
          refreshKds();
        }})
        .catch((error) => {{
          if (error?.detail?.code === "cancellation_classification_required") {{
            const selected = window.prompt("El pedido ya fue producido. Escribe merma o recuperacion.", "merma");
            const normalized = (selected || "").trim().toLowerCase();
            const mapped = normalized === "recuperacion" || normalized === "recovery" ? "recovery" : normalized === "merma" || normalized === "waste" ? "waste" : "";
            if (mapped) {{
              setOrderStatus("Registrando cancelacion clasificada...");
              submitCancellation(orderId, mapped);
              return;
            }}
            setOrderStatus("Cancelacion detenida: falta clasificar merma o recuperacion");
            return;
          }}
          setOrderStatus(error?.detail?.message || "No se pudo cancelar el pedido");
        }});
    }};
    const openButton = document.getElementById("open-cash");
    if (openButton) {{
      openButton.addEventListener("click", () => {{
        const input = document.getElementById("opening-cash");
        const pesos = Number(input.value || 0);
        fetch("/api/v1/cash-shifts/open", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ opening_cash_cents: Math.round(pesos * 100) }}),
        }})
          .then(async (response) => {{
            const payload = await response.json();
            if (!response.ok) throw payload;
            setCashStatus(`Turno abierto: ${{payload.register_code}}`);
            refreshCash();
          }})
          .catch((error) => setCashStatus(error?.detail?.message || "No se pudo abrir caja"));
      }});
      refreshCash();
      refreshOrders();
    }}
    const closeButton = document.getElementById("close-cash");
    if (closeButton) {{
      closeButton.addEventListener("click", () => {{
        const counted = document.getElementById("counted-cash");
        const pesos = Number(counted.value || 0);
        fetch("/api/v1/cash-shifts/close", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ counted_cash_cents: Math.round(pesos * 100) }}),
        }})
          .then(async (response) => {{
            const payload = await response.json();
            if (!response.ok) throw payload;
            setCashStatus(`Turno cerrado: ${{payload.register_code}}`);
            refreshCash();
          }})
          .catch((error) => setCashStatus(error?.detail?.message || "No se pudo cerrar caja"));
      }});
    }}

    const printJobsNode = document.getElementById("print-jobs");
    const refreshPrintJobs = () => {{
      if (!printJobsNode) return;
      fetch("/api/v1/print-jobs")
        .then((response) => response.json())
        .then((jobs) => {{
          printJobsNode.innerHTML = jobs.length
            ? jobs.map((job) => `
              <article class="panel">
                <div>
                  <h2>${{job.folio}} · ${{job.job_type}}</h2>
                  <p>${{job.target}} · ${{job.status}} · intentos ${{job.attempts}}</p>
                </div>
                ${{job.status !== "PRINTED" ? `<button data-print-job-id="${{job.id}}">Reintentar</button>` : ""}}
              </article>`).join("")
            : '<article class="panel"><h2>Sin impresiones</h2><p>Al cobrar un pedido se crean ticket y comanda.</p></article>';
          printJobsNode.querySelectorAll("button[data-print-job-id]").forEach((button) => {{
            button.addEventListener("click", () => retryPrintJob(button.dataset.printJobId));
          }});
        }})
        .catch(() => {{
          printJobsNode.innerHTML = '<article class="panel"><h2>Impresion no disponible</h2><p>Revisa migraciones.</p></article>';
        }});
    }};
    const retryPrintJob = (jobId) => {{
      fetch(`/api/v1/print-jobs/${{jobId}}/retry`, {{ method: "POST" }})
        .then(() => refreshPrintJobs());
    }};
    refreshPrintJobs();

    const kdsNode = document.getElementById("kds-board");
    const renderTasks = (tasks) => {{
      if (!kdsNode) return;
      if (!Array.isArray(tasks) || tasks.length === 0) {{
        kdsNode.innerHTML = '<article class="panel"><h2>Sin tareas</h2><p>Los pedidos aceptados apareceran aqui.</p></article>';
        return;
      }}
      kdsNode.innerHTML = tasks.map((task) => `
        <article class="product-tile">
          <div>
            <h2>${{task.folio}} · ${{task.product_name}}</h2>
            <div class="product-meta">${{task.station}} · cantidad ${{task.quantity}}</div>
          </div>
          <div class="product-footer">
            <span>${{task.status}}</span>
            <div class="action-row">
              <button data-task-id="${{task.id}}" data-status="IN_PROGRESS" class="secondary">Iniciar</button>
              <button data-task-id="${{task.id}}" data-status="COMPLETED">Completar</button>
            </div>
          </div>
        </article>`).join("");
      kdsNode.querySelectorAll("button[data-task-id]").forEach((button) => {{
        button.addEventListener("click", () => transitionTask(button.dataset.taskId, button.dataset.status));
      }});
    }};
    const refreshKds = () => {{
      if (!kdsNode) return;
      fetch("/api/v1/kds/tasks")
        .then((response) => response.json())
        .then(renderTasks)
        .catch(() => {{
          kdsNode.innerHTML = '<article class="panel"><h2>KDS no disponible</h2><p>Revisa migraciones.</p></article>';
        }});
    }};
    const transitionTask = (taskId, status) => {{
      fetch(`/api/v1/kds/tasks/${{taskId}}/transition`, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ status }}),
      }}).then(() => refreshKds());
    }};
    refreshKds();
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


def _admin_section(active_path: str) -> str:
    if active_path != "/admin":
        return ""

    return """
      <section aria-label="Consola Admin SaaS">
        <div class="topbar">
          <div>
            <h1>Admin RestaurantOS</h1>
            <p class="subtle">Consola de configuracion para sucursales, catalogos, inventario, usuarios y sincronizacion.</p>
          </div>
          <div class="status-pill">SaaS operativo</div>
        </div>
        <section id="login-panel" class="login-panel" aria-label="Acceso superadmin">
          <div class="login-visual">
            <div>
              <span class="section-kicker">RestaurantOS SaaS</span>
              <h1>Acceso superadmin</h1>
              <p class="subtle">Entra para administrar usuarios, roles, catalogos, inventario y operacion del negocio.</p>
            </div>
            <div class="login-card-stack">
              <div class="soft-card"><span class="section-kicker">Catalogos</span><strong>Productos</strong></div>
              <div class="soft-card"><span class="section-kicker">Inventario</span><strong>Kardex</strong></div>
              <div class="soft-card"><span class="section-kicker">Accesos</span><strong>Roles</strong></div>
              <div class="soft-card"><span class="section-kicker">POS</span><strong>Pedidos</strong></div>
            </div>
          </div>
          <div class="login-form">
            <div>
              <span class="section-kicker">Cuenta principal</span>
              <h2>Iniciar sesion</h2>
              <p id="login-message" class="message">Ingresa con tu cuenta superadmin.</p>
            </div>
            <label>Correo
              <input id="login-email" type="email" value="mangoex@gmail.com" autocomplete="email" />
            </label>
            <label>Contraseña
              <input id="login-password" type="password" autocomplete="current-password" />
            </label>
            <button id="login-button" type="button">Entrar al panel</button>
          </div>
        </section>
        <div id="session-strip" class="session-strip">
          <div>
            <span class="section-kicker">Sesion activa</span>
            <strong id="session-name">Usuario conectado</strong>
          </div>
          <button id="logout-button" class="secondary" type="button">Cerrar sesion</button>
        </div>
        <div class="admin-secured">
          <div class="module-tabs" aria-label="Modulos Admin">
            <button data-admin-tab="overview" aria-pressed="true">Inicio</button>
            <button data-admin-tab="catalogs" aria-pressed="false">Catalogos</button>
            <button data-admin-tab="inventory" aria-pressed="false">Inventario</button>
            <button data-admin-tab="users" aria-pressed="false">Usuarios</button>
            <button data-admin-tab="system" aria-pressed="false">Sistema</button>
          </div>
        </div>
        <div id="admin-overview" class="admin-view admin-secured active">
          <div class="hero-band">
            <div>
              <h1>Operacion central Kiwi</h1>
              <p>Panel operativo para sucursales, productos, inventario, roles y continuidad de servicio.</p>
            </div>
            <div class="hero-actions">
              <a class="status-pill" href="/pos">Abrir POS</a>
              <a class="status-pill" href="/kds">Abrir KDS</a>
            </div>
          </div>
          <section class="module-strip" aria-label="Accesos operativos Admin">
            <a class="module-card" href="#admin-catalogs" data-admin-jump="catalogs">
              <span class="section-kicker">Catalogos</span>
              <strong>Sucursales y productos</strong>
              <span>Almacenes formales, precios vigentes y estaciones de produccion.</span>
            </a>
            <a class="module-card" href="#admin-inventory" data-admin-jump="inventory">
              <span class="section-kicker">Inventario</span>
              <strong>Existencias, recetas y kardex</strong>
              <span>Movimiento inmutable, stock teorico y consumo por receta.</span>
            </a>
            <a class="module-card" href="#admin-users" data-admin-jump="users">
              <span class="section-kicker">Accesos</span>
              <strong>Usuarios y roles</strong>
              <span>Invitaciones, perfiles y alcance por sucursal u organizacion.</span>
            </a>
            <a class="module-card" href="#admin-system" data-admin-jump="system">
              <span class="section-kicker">Sistema</span>
              <strong>Sincronizacion</strong>
              <span>Checkpoint, comandos, eventos y salud de dependencias.</span>
            </a>
          </section>
          <section class="health" aria-label="Resumen Admin">
            <div class="metric compact"><span>Sucursales</span><strong id="admin-branch-count">...</strong></div>
            <div class="metric compact"><span>Productos</span><strong id="admin-product-count">...</strong></div>
            <div class="metric compact"><span>Usuarios</span><strong id="admin-user-count">...</strong></div>
            <div class="metric compact"><span>Sync</span><strong id="admin-sync-count">...</strong></div>
          </section>
          <section id="saas-command-center" class="command-center" aria-label="Centro de mando SaaS">
            <article class="panel">
              <div class="toolbar">
                <div>
                  <span class="section-kicker">Preparacion operativa</span>
                  <h2>Centro de mando SaaS</h2>
                </div>
                <span class="chip info">Datos en vivo</span>
              </div>
              <div id="readiness-steps" class="readiness-grid">
                <article class="readiness-step pending">
                  <div class="readiness-head">
                    <div>
                      <span class="section-kicker">Catalogos</span>
                      <strong>Cargando modulo</strong>
                    </div>
                    <span class="chip warn">Pendiente</span>
                  </div>
                  <p>Consultando sucursales, productos y precios.</p>
                  <div class="progress-track" aria-label="Avance Catalogos"><span class="progress-bar" style="width: 35%"></span></div>
                </article>
              </div>
            </article>
            <div id="ops-pulse" class="ops-pulse" aria-label="Pulso operativo">
              <div class="ops-pulse-row"><span>Preparacion</span><strong>consultando</strong></div>
              <div class="ops-pulse-row"><span>Catalogo</span><strong>consultando</strong></div>
              <div class="ops-pulse-row"><span>Inventario</span><strong>consultando</strong></div>
              <div class="ops-pulse-row"><span>Accesos</span><strong>consultando</strong></div>
            </div>
          </section>
        </div>
        <div id="admin-catalogs" class="admin-view admin-secured">
          <div class="toolbar">
            <div>
              <span class="section-kicker">Catalogos operativos</span>
              <h2>Sucursales y productos</h2>
            </div>
            <p id="catalog-message" class="message">Catalogos listos.</p>
          </div>
          <div id="catalog-workbench" class="workbench wide">
            <div class="stack">
              <article class="panel">
                <div>
                  <h2>Nueva sucursal</h2>
                  <p>Crea la sucursal y su almacen formal en una sola accion.</p>
                </div>
                <div class="form-grid">
                  <label>Nombre
                    <input id="branch-name-input" type="text" value="Sucursal Norte" autocomplete="off" />
                  </label>
                  <label>Codigo
                    <input id="branch-code-input" type="text" value="NORTE" autocomplete="off" />
                  </label>
                  <button id="create-branch">Crear sucursal</button>
                </div>
              </article>
              <article class="panel">
                <div>
                  <h2>Nuevo producto</h2>
                  <p>Alta rapida con categoria, estacion, precio vigente y disponibilidad.</p>
                </div>
                <div class="form-grid">
                  <label>Nombre
                    <input id="product-name-input" type="text" value="Wrap Kiwi" autocomplete="off" />
                  </label>
                  <label>SKU
                    <input id="product-sku-input" type="text" value="KIWI-WRAP" autocomplete="off" />
                  </label>
                  <label>Categoria
                    <input id="product-category-input" type="text" value="Comida" autocomplete="off" />
                  </label>
                  <label>Estacion
                    <select id="product-station-input">
                      <option value="kitchen">Cocina</option>
                      <option value="drinks">Bebidas</option>
                      <option value="packing">Empaque</option>
                    </select>
                  </label>
                  <label>Precio MXN
                    <input id="product-price-input" type="number" min="1" step="1" value="89" />
                  </label>
                  <button id="create-product">Crear producto</button>
                </div>
              </article>
            </div>
            <div class="stack">
              <article class="panel">
                <div class="toolbar">
                  <div>
                    <span class="section-kicker">Organizacion</span>
                    <h2>Sucursales</h2>
                  </div>
                  <span class="chip info">Almacen automatico</span>
                </div>
                <div class="table-wrap">
                  <table>
                    <thead><tr><th>Sucursal</th><th>Codigo</th><th>Razon social</th><th>Almacen</th></tr></thead>
                    <tbody id="branches-table"><tr><td colspan="4">Cargando sucursales...</td></tr></tbody>
                  </table>
                </div>
              </article>
              <article class="panel">
                <div class="toolbar">
                  <div>
                    <span class="section-kicker">Menu vendible</span>
                    <h2>Productos</h2>
                  </div>
                  <span class="chip info">Precio vigente</span>
                </div>
                <div class="table-wrap">
                  <table>
                    <thead><tr><th>Producto</th><th>SKU</th><th>Categoria</th><th>Estacion</th><th>Precio</th><th>Estado</th></tr></thead>
                    <tbody id="products-table"><tr><td colspan="6">Cargando productos...</td></tr></tbody>
                  </table>
                </div>
              </article>
            </div>
          </div>
        </div>
        <div id="admin-inventory" class="admin-view admin-secured">
          <div class="toolbar">
            <div>
              <span class="section-kicker">Control inventariable</span>
              <h2>Inventario, recetas y kardex</h2>
            </div>
            <p id="inventory-message" class="message">Inventario listo.</p>
          </div>
          <section class="health" aria-label="Resumen de inventario">
            <div class="metric compact"><span>Insumos</span><strong id="inventory-item-count">...</strong></div>
            <div class="metric compact"><span>Movimientos</span><strong id="inventory-movement-count">...</strong></div>
            <div class="metric compact"><span>Alertas</span><strong id="inventory-alert-count">...</strong></div>
          </section>
          <div id="inventory-workbench" class="workbench wide">
            <div class="stack">
              <article class="panel">
                <div>
                  <h2>Saldo inicial</h2>
                  <p>Registra movimientos append-only; la existencia se calcula desde kardex.</p>
                </div>
                <div class="form-grid">
                  <label>Insumo
                    <select id="inventory-item-input"></select>
                  </label>
                  <label>Cantidad base
                    <input id="inventory-quantity-input" type="number" min="1" step="1" value="1000" />
                  </label>
                  <label>Motivo
                    <input id="inventory-reason-input" type="text" value="Saldo inicial operativo" autocomplete="off" />
                  </label>
                  <button id="record-opening-balance">Registrar movimiento</button>
                </div>
              </article>
              <article class="panel">
                <div class="toolbar">
                  <div>
                    <span class="section-kicker">Produccion</span>
                    <h2>Recetas vigentes</h2>
                  </div>
                  <span class="chip info">Versionadas</span>
                </div>
                <div class="table-wrap">
                  <table>
                    <thead><tr><th>Producto</th><th>Version</th><th>Rendimiento</th><th>Componentes</th></tr></thead>
                    <tbody id="recipes-table"><tr><td colspan="4">Cargando recetas...</td></tr></tbody>
                  </table>
                </div>
              </article>
            </div>
            <div class="stack">
              <article class="panel">
                <div class="toolbar">
                  <div>
                    <span class="section-kicker">Almacenes</span>
                    <h2>Existencia teorica</h2>
                  </div>
                  <span class="chip info">Ledger</span>
                </div>
                <div class="table-wrap">
                  <table>
                    <thead><tr><th>Insumo</th><th>SKU</th><th>Almacen</th><th>Existencia</th><th>Ultimo movimiento</th></tr></thead>
                    <tbody id="inventory-stock-table"><tr><td colspan="5">Cargando existencias...</td></tr></tbody>
                  </table>
                </div>
              </article>
              <article class="panel">
                <div class="toolbar">
                  <div>
                    <span class="section-kicker">Trazabilidad</span>
                    <h2>Kardex</h2>
                  </div>
                  <span class="chip info">Append-only</span>
                </div>
                <div class="table-wrap">
                  <table>
                    <thead><tr><th>Fecha</th><th>Insumo</th><th>Tipo</th><th>Cantidad</th><th>Motivo</th></tr></thead>
                    <tbody id="inventory-kardex-table"><tr><td colspan="5">Cargando kardex...</td></tr></tbody>
                  </table>
                </div>
              </article>
            </div>
          </div>
        </div>
        <div id="admin-users" class="admin-view admin-secured">
          <div class="workbench">
            <div class="stack">
              <article class="panel">
                <div>
                  <h2>Crear rol</h2>
                  <p>Define el alcance operativo antes de asignarlo a usuarios.</p>
                </div>
                <div class="form-grid">
                  <label>Nombre del rol
                    <input id="role-name" type="text" value="Cajero" autocomplete="off" />
                  </label>
                  <label>Alcance
                    <select id="role-scope">
                      <option value="branch">Sucursal</option>
                      <option value="organization">Corporativo</option>
                    </select>
                  </label>
                  <button id="create-role">Crear rol</button>
                </div>
              </article>
              <article class="panel">
                <div>
                  <h2>Invitar usuario</h2>
                  <p>El usuario queda en estado invitado hasta conectar autenticacion formal.</p>
                </div>
                <div class="form-grid">
                  <label>Nombre visible
                    <input id="user-display-name" type="text" value="Cajero Piloto" autocomplete="name" />
                  </label>
                  <label>Correo
                    <input id="user-email" type="email" value="cajero@kiwi.local" autocomplete="email" />
                  </label>
                  <label>Contraseña temporal
                    <input id="user-password" type="password" autocomplete="new-password" />
                  </label>
                  <button id="create-user">Invitar usuario</button>
                </div>
              </article>
              <article class="panel">
                <div>
                  <h2>Asignar rol</h2>
                  <p>Los roles de sucursal se asignan por defecto a Sucursal Piloto.</p>
                </div>
                <div class="form-grid">
                  <label>Usuario
                    <select id="assign-user"></select>
                  </label>
                  <label>Rol
                    <select id="assign-role"></select>
                  </label>
                  <button id="assign-role-button">Asignar rol</button>
                </div>
                <p id="admin-message" class="message">Listo para operar.</p>
              </article>
            </div>
            <div class="stack">
              <article class="panel">
                <div>
                  <h2>Usuarios</h2>
                  <p>Colaboradores registrados y roles asignados.</p>
                </div>
                <div class="table-wrap">
                  <table>
                    <thead><tr><th>Nombre</th><th>Correo</th><th>Estado</th><th>Roles</th></tr></thead>
                    <tbody id="users-table"><tr><td colspan="4">Cargando usuarios...</td></tr></tbody>
                  </table>
                </div>
              </article>
              <article class="panel">
                <div>
                  <h2>Roles</h2>
                  <p>Perfiles disponibles para la operacion.</p>
                </div>
                <div class="table-wrap">
                  <table>
                    <thead><tr><th>Rol</th><th>Alcance</th><th>Permisos</th><th>Creado</th></tr></thead>
                    <tbody id="roles-table"><tr><td colspan="4">Cargando roles...</td></tr></tbody>
                  </table>
                </div>
              </article>
            </div>
          </div>
        </div>
        <div id="admin-system" class="admin-view admin-secured">
          <article class="panel">
            <h2>Sincronizacion y auditoria</h2>
            <p id="admin-system-summary">Consultando estado de sincronizacion...</p>
            <div class="links">
              <a href="/api/v1/sync/events">Eventos sync</a>
              <a href="/api/v1/sync/status">Estado sync</a>
              <a href="/health/ready">Ready</a>
            </div>
          </article>
        </div>
      </section>"""


def _pos_catalog_section(active_path: str) -> str:
    if active_path != "/pos":
        return ""

    return """
      <section aria-label="Catalogo POS">
        <div class="topbar">
          <div>
            <h1>Catalogo POS</h1>
            <p class="subtle">Productos activos de la Sucursal Piloto para vender, cobrar y generar impresion simulada.</p>
          </div>
          <div class="status-pill">Venta local</div>
        </div>
        <div id="pos-catalog" class="catalog-list">
          <article class="panel">
            <h2>Cargando catalogo</h2>
            <p>Consultando productos, precios y disponibilidad.</p>
          </article>
        </div>
        <div class="panel">
          <h2>Caja</h2>
          <p id="cash-status">Consultando caja...</p>
          <p id="cash-summary" class="subtle">Resumen pendiente.</p>
          <div class="action-row">
            <input id="opening-cash" type="number" min="0" step="1" value="500" aria-label="Fondo inicial" />
            <button id="open-cash">Abrir caja</button>
            <input id="counted-cash" type="number" min="0" step="1" value="0" aria-label="Efectivo contado" />
            <button id="close-cash" class="secondary">Cerrar caja</button>
          </div>
          <p id="order-status" class="subtle">Crea pedidos desde los productos disponibles.</p>
        </div>
        <section>
          <h1>Pedidos recientes</h1>
          <div id="recent-orders" class="catalog-list">
            <article class="panel"><h2>Cargando pedidos</h2><p>Consultando venta local.</p></article>
          </div>
        </section>
        <section>
          <h1>Impresion simulada</h1>
          <div id="print-jobs" class="catalog-list">
            <article class="panel"><h2>Cargando impresion</h2><p>Consultando ticket y comanda.</p></article>
          </div>
        </section>
      </section>"""


def _kds_board_section(active_path: str) -> str:
    if active_path != "/kds":
        return ""

    return """
      <section aria-label="Tablero KDS">
        <div class="topbar">
          <div>
            <h1>Tablero KDS</h1>
            <p class="subtle">Tareas generadas por pedidos aceptados en POS.</p>
          </div>
          <div class="status-pill">Produccion inicial</div>
        </div>
        <div id="kds-board" class="catalog-list">
          <article class="panel">
            <h2>Cargando tareas</h2>
            <p>Consultando cocina y bebidas.</p>
          </article>
        </div>
      </section>"""
