// EcoGrid AI - Frontend Application Logic

if (window.Chart) Chart.defaults.font.family = "Inter, system-ui, sans-serif";

function togglePasswordVisibility() {
  const input = document.getElementById("loginPassword");
  input.type = input.type === "password" ? "text" : "password";
}

let energyChart = null;
const chartMaxPoints = 25;

// Inicialización de la aplicación
document.addEventListener("DOMContentLoaded", () => {
  checkAuthSession();

  // Polling periódico cada 2.5 segundos
  setInterval(() => {
    if (isAuthenticated()) {
      refreshTelemetry();
      refreshRelay();
      refreshSecurity();
    }
  }, 2500);
});

// -------------------------------------------------------------
// CONTROL DE AUTENTICACIÓN (LOGIN / LOGOUT)
// -------------------------------------------------------------
function isAuthenticated() {
  return !!localStorage.getItem("ecogrid_user");
}

function checkAuthSession() {
  const savedUser = localStorage.getItem("ecogrid_user");
  const loginScreen = document.getElementById("loginScreen");
  const appScreen = document.getElementById("appScreen");

  if (savedUser) {
    try {
      const user = JSON.parse(savedUser);
      document.getElementById("userNameDisplay").textContent = user.name || "Operador";
      document.getElementById("userRoleDisplay").textContent = user.role || "Ingeniero SCADA";
      loginScreen.style.display = "none";
      appScreen.style.display = "block";

      if (!energyChart) initChart();
      refreshAllData();
      loadIncidentHistory();
    } catch (e) {
      handleLogout();
    }
  } else {
    loginScreen.style.display = "flex";
    appScreen.style.display = "none";
  }
}

async function handleLoginSubmit(event) {
  event.preventDefault();
  const email = document.getElementById("loginEmail").value.trim();
  const password = document.getElementById("loginPassword").value;
  const errorEl = document.getElementById("loginErrorMsg");

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    const data = await res.json();
    if (res.ok && data.status === "success") {
      localStorage.setItem("ecogrid_user", JSON.stringify(data.user));
      localStorage.setItem("ecogrid_token", data.token);
      errorEl.style.display = "none";
      checkAuthSession();
    } else {
      errorEl.textContent = data.message || "Credenciales incorrectas";
      errorEl.style.display = "block";
    }
  } catch (err) {
    // Modo offline / fallback
    const mockUser = {
      name: "Ing. Operador UTC",
      role: "Operador de Subestación",
      email: email,
    };
    localStorage.setItem("ecogrid_user", JSON.stringify(mockUser));
    checkAuthSession();
  }
}

function quickLoginDemo() {
  document.getElementById("loginEmail").value = "operador@utc.edu.mx";
  document.getElementById("loginPassword").value = "utc7mo2026";
  const fakeEvent = { preventDefault: () => {} };
  handleLoginSubmit(fakeEvent);
}

function handleLogout() {
  localStorage.removeItem("ecogrid_user");
  localStorage.removeItem("ecogrid_token");
  checkAuthSession();
}

// -------------------------------------------------------------
// CONTROL DE PESTAÑAS (TABS)
// -------------------------------------------------------------
function switchTab(tabId) {
  const sections = ["tab-monitoring", "tab-fleet", "tab-relay", "tab-textmining", "tab-security", "tab-simulator"];
  sections.forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.style.display = id === tabId ? "block" : "none";
  });

  const buttons = document.querySelectorAll(".tab-btn");
  buttons.forEach((btn) => btn.classList.remove("active"));
  (event.currentTarget || event.target).classList.add("active");

  if (tabId === "tab-security") {
    refreshSecurity();
  }
  if (tabId === "tab-fleet") {
    refreshFleet();
    resizeDeviceCharts();
  }
}

// -------------------------------------------------------------
// INICIALIZACIÓN DE CHART.JS
// -------------------------------------------------------------
function initChart() {
  const ctx = document.getElementById("energyChart").getContext("2d");
  energyChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Potencia Activa (W)",
          data: [],
          borderColor: "#00d26a",
          backgroundColor: "rgba(0, 210, 106, 0.1)",
          tension: 0.3,
          fill: true,
          yAxisID: "yPower",
        },
        {
          label: "Corriente RMS (A)",
          data: [],
          borderColor: "#3b82f6",
          backgroundColor: "transparent",
          borderDash: [5, 5],
          tension: 0.3,
          yAxisID: "yCurrent",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#94a3b8" },
        },
        yPower: {
          type: "linear",
          position: "left",
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#00d26a" },
          title: { display: true, text: "Potencia (W)", color: "#00d26a" },
        },
        yCurrent: {
          type: "linear",
          position: "right",
          grid: { drawOnChartArea: false },
          ticks: { color: "#3b82f6" },
          title: { display: true, text: "Corriente (A)", color: "#3b82f6" },
        },
      },
      plugins: {
        legend: { labels: { color: "#e2e8f0" } },
      },
    },
  });
}

// -------------------------------------------------------------
// ACTUALIZACIÓN DE TELEMETRÍA Y GAUGES
// -------------------------------------------------------------
async function refreshTelemetry() {
  try {
    const res = await fetch(monitorDeviceId ? `/api/telemetry/latest?device_id=${encodeURIComponent(monitorDeviceId)}` : "/api/telemetry/latest");
    if (!res.ok) return;
    const data = await res.json();
    const metrics = data.metrics || {};
    const ai = data.ai_evaluation || {};

    // Actualizar números en tarjetas
    document.getElementById("valVoltage").textContent = (metrics.voltage || 120.0).toFixed(1);
    document.getElementById("valCurrent").textContent = (metrics.current || 0.0).toFixed(2);
    document.getElementById("valPower").textContent = (metrics.active_power || 0.0).toFixed(1);
    document.getElementById("valPF").textContent = (metrics.power_factor || 0.95).toFixed(2);
    document.getElementById("valFreq").textContent = (metrics.frequency || 60.0).toFixed(1);

    // Actualizar badge de patrón clasificado por IA
    const pattern = ai.pattern_class || "Normal";
    const badge = document.getElementById("activePatternBadge");
    badge.textContent = `Patrón IA: ${pattern}`;

    const box = document.getElementById("aiInferenceBox");
    if (pattern === "Sobrecarga / Anomalía") {
      badge.style.background = "rgba(239, 68, 68, 0.25)";
      badge.style.borderColor = "#ef4444";
      badge.style.color = "#f87171";
      box.innerHTML = `<span style="color:#ef4444;">⚠️ SOBRECARGA DETECTADA — CORTE DE CARGA REQUERIDO</span>`;
    } else if (pattern === "Pico de Demanda") {
      badge.style.background = "rgba(245, 158, 11, 0.25)";
      badge.style.borderColor = "#f59e0b";
      badge.style.color = "#fbbf24";
      box.innerHTML = `<span style="color:#f59e0b;">⚡ Pico de Demanda Máxima en Horario Punta</span>`;
    } else if (pattern === "Fuga / Consumo Parásito") {
      badge.style.background = "rgba(139, 92, 246, 0.25)";
      badge.style.borderColor = "#8b5cf6";
      badge.style.color = "#c084fc";
      box.innerHTML = `<span style="color:#8b5cf6;">🔍 Fuga Eléctrica / Pérdida Parásita Continua</span>`;
    } else {
      badge.style.background = "rgba(0, 210, 106, 0.15)";
      badge.style.borderColor = "#00d26a";
      badge.style.color = "#00d26a";
      box.innerHTML = `<span style="color:#00d26a;">✅ Operación Normal dentro de Norma</span>`;
    }

    // Agregar punto a la serie de tiempo de Chart.js
    const nowTime = new Date().toLocaleTimeString();
    if (energyChart) {
      if (energyChart.data.labels.length > chartMaxPoints) {
        energyChart.data.labels.shift();
        energyChart.data.datasets[0].data.shift();
        energyChart.data.datasets[1].data.shift();
      }
      energyChart.data.labels.push(nowTime);
      energyChart.data.datasets[0].data.push(metrics.active_power || 0);
      energyChart.data.datasets[1].data.push(metrics.current || 0);
      energyChart.update("none");
    }

    // Consultar acumulado kWh
    const statsRes = await fetch("/api/telemetry/stats");
    if (statsRes.ok) {
      const stats = await statsRes.json();
      document.getElementById("valEnergy").textContent = (stats.total_energy_kwh || 0).toFixed(4);
    }
  } catch (err) {
    console.error("Error refreshing telemetry:", err);
  }
}

// -------------------------------------------------------------
// MINERÍA DE TEXTO
// -------------------------------------------------------------
function setSampleText(sample) {
  document.getElementById("incidentInput").value = sample;
}

async function analyzeIncidentText() {
  const text = document.getElementById("incidentInput").value.trim();
  if (!text) {
    alert("Por favor ingrese una bitácora o texto de incidente.");
    return;
  }

  try {
    const res = await fetch("/api/text-mining/classify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text }),
    });

    if (!res.ok) {
      alert("Error en el servidor al analizar texto");
      return;
    }

    const data = await res.json();
    const ana = data.analysis;

    const resBox = document.getElementById("textMiningResult");
    const title = document.getElementById("resSeverityTitle");
    const conf = document.getElementById("resConfidence");
    const action = document.getElementById("resAction");
    const kw = document.getElementById("resKeywords");

    resBox.style.display = "block";
    title.textContent = `Severidad Predicha: ${ana.predicted_severity.toUpperCase()}`;
    conf.textContent = `Nivel de Confianza: ${(ana.confidence * 100).toFixed(1)}%`;
    action.textContent = `Acción Operativa: ${ana.recommended_action}`;
    kw.textContent = `Términos Clave Extraídos: ${ana.keywords.join(", ")}`;

    // Color del borde según severidad
    const colorMap = {
      Crítica: "#ef4444",
      Alta: "#f59e0b",
      Media: "#3b82f6",
      Baja: "#00d26a",
    };
    resBox.style.borderLeftColor = colorMap[ana.predicted_severity] || "#00d26a";

    // Recargar tabla de incidentes
    loadIncidentHistory();
  } catch (err) {
    alert("Error conectando al servicio de minería de texto: " + err);
  }
}

async function loadIncidentHistory() {
  try {
    const res = await fetch("/api/text-mining/logs?limit=10");
    if (!res.ok) return;
    const data = await res.json();
    const tbody = document.getElementById("incidentTableBody");
    tbody.innerHTML = "";

    const tagClass = {
      Crítica: "tag-critical",
      Alta: "tag-high",
      Media: "tag-medium",
      Baja: "tag-low",
    };

    if (!data.logs || !data.logs.length) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty-cell">Aún no hay incidentes analizados. Los resultados aparecerán aquí.</td></tr>';
      return;
    }

    data.logs.forEach((item) => {
      const tr = document.createElement("tr");
      const sevTag = `<span class="${tagClass[item.predicted_severity] || "tag-low"}">${item.predicted_severity}</span>`;
      const dateStr = item.created_at ? new Date(item.created_at).toLocaleTimeString() : "Hoy";
      tr.innerHTML = `
        <td>${dateStr}</td>
        <td>${item.log_text}</td>
        <td>${sevTag}</td>
        <td>${((item.confidence || 1) * 100).toFixed(0)}%</td>
        <td>${item.action_taken || "-"}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    console.error("Error loading incident history:", err);
  }
}

// -------------------------------------------------------------
// CIBERSEGURIDAD, HONEYPOT, SYSLOG Y SNMP
// -------------------------------------------------------------
async function refreshSecurity() {
  try {
    const res = await fetch("/api/security/stats");
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("valHoneypotHits").textContent = data.honeypot.total_trapped;
    document.getElementById("valDosAnalyzed").textContent = data.dos_protection.attack_stats.total_requests_analyzed;
    document.getElementById("valBlockedIps").textContent = data.dos_protection.attack_stats.currently_banned_ips;
    document.getElementById("valSyslogCount").textContent = data.syslog_status.buffered_logs_count;

    // Actualizar tabla de Honeypot
    const hpRes = await fetch("/api/security/honeypot");
    if (hpRes.ok) {
      const hpData = await hpRes.json();
      const tbody = document.getElementById("honeypotTableBody");
      if (hpData.recent_intrusions && hpData.recent_intrusions.length > 0) {
        tbody.innerHTML = "";
        hpData.recent_intrusions.forEach((intru) => {
          const tr = document.createElement("tr");
          const time = new Date(intru.timestamp).toLocaleTimeString();
          tr.innerHTML = `
            <td>${time}</td>
            <td style="color:#ef4444; font-weight:bold;">${intru.attacker_ip}</td>
            <td><code>${intru.target_path}</code></td>
            <td><span class="badge" style="background:#27334d;">${intru.http_method}</span></td>
            <td style="font-size:0.75rem; color:#94a3b8;">${JSON.stringify(intru.payload_captured)}</td>
            <td><span class="badge" style="background:rgba(239, 68, 68, 0.2); color:#ef4444;">IP AUTO-BLOQUEADA</span></td>
          `;
          tbody.appendChild(tr);
        });
      }
    }

    // Actualizar consola Syslog
    const sysRes = await fetch("/api/security/syslog?limit=15");
    if (sysRes.ok) {
      const sysData = await sysRes.json();
      const consoleEl = document.getElementById("syslogConsole");
      consoleEl.innerHTML = "";
      if (!sysData.events || !sysData.events.length) {
        consoleEl.innerHTML = '<div class="log-placeholder">Esperando eventos…</div>';
      }
      sysData.events.forEach((ev) => {
        const div = document.createElement("div");
        div.className = "log-entry";
        let color = "#94a3b8";
        if (ev.severity <= 2) color = "#ef4444";
        else if (ev.severity === 4) color = "#f59e0b";
        else if (ev.severity === 6) color = "#00d26a";

        div.style.color = color;
        div.textContent = `[${ev.severity_name}] ${new Date(ev.timestamp).toLocaleTimeString()} - ${ev.message}`;
        consoleEl.appendChild(div);
      });
    }

    // Actualizar tabla SNMP MIB
    const snmpRes = await fetch("/api/security/snmp");
    if (snmpRes.ok) {
      const snmpData = await snmpRes.json();
      const tbody = document.getElementById("snmpTableBody");
      tbody.innerHTML = "";
      for (const [oid, obj] of Object.entries(snmpData.mib_objects)) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td><strong>${obj.name}</strong></td>
          <td><code>${oid}</code></td>
          <td style="color:#00d26a; font-weight:600;">${obj.value} ${obj.unit || ""}</td>
        `;
        tbody.appendChild(tr);
      }
    }
  } catch (err) {
    console.error("Error refreshing security data:", err);
  }
}

async function simulateHoneypotIntrusion() {
  try {
    const fakeIp = `192.168.1.${Math.floor(Math.random() * 150) + 50}`;
    const paths = ["/admin", "/scada/admin", "/firmware/update", "/api/v1/override_relay"];
    const chosenPath = paths[Math.floor(Math.random() * paths.length)];

    const res = await fetch("/api/security/honeypot/simulate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ip: fakeIp,
        path: chosenPath,
        payload: { attempt: "SQL_INJECTION", query: "admin' OR '1'='1" },
      }),
    });

    if (res.ok) {
      alert(`🎯 ¡Intrusión de prueba simulada!\nIP Atacante: ${fakeIp}\nRuta Señuelo: ${chosenPath}\n\nEl Honeypot ha atrapado al intruso, despachó un Syslog Alert y bloqueó la IP en el firewall.`);
      refreshSecurity();
    }
  } catch (err) {
    alert("Error simulando ataque: " + err);
  }
}

// -------------------------------------------------------------
// INYECCIÓN DE PRUEBAS / SIMULADOR
// -------------------------------------------------------------
async function injectTelemetry(mode) {
  let v = 120.0, i = 5.2, pf = 0.96, thd = 3.0, temp = 30.0;
  if (mode === "pico") {
    v = 117.5; i = 24.5; pf = 0.91; thd = 6.5; temp = 48.0;
  } else if (mode === "sobrecarga") {
    v = 111.0; i = 42.0; pf = 0.76; thd = 18.0; temp = 74.0;
  } else if (mode === "fuga") {
    v = 121.0; i = 1.8; pf = 0.62; thd = 11.0; temp = 29.0;
  }

  const payload = {
    device_id: (document.getElementById("injectDevice") || {}).value || "esp32_sensor_01",
    voltage: v,
    current: i,
    active_power: +(v * i * pf).toFixed(1),
    power_factor: pf,
    frequency: 60.0,
    thd: thd,
    temperature: temp,
  };

  try {
    const res = await fetch("/api/telemetry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      const data = await res.json();
      const ai = data.ai_evaluation;
      alert(`⚡ Inyección Exitosa:\nModo: ${mode.toUpperCase()}\nPatrón IA Clasificado: ${ai.class_name}\nAcción: ${ai.action}\nEstado de Relé: ${data.relay_state === 1 ? "CONECTADO" : "¡DESCONECTADO POR SEGURIDAD!"}`);
      refreshTelemetry();
      refreshDevices();
    }
  } catch (err) {
    alert("Error inyectando telemetría: " + err);
  }
}

function refreshAllData() {
  refreshTelemetry();
  refreshRelay();
  refreshSecurity();
  refreshFleet();
}

// -------------------------------------------------------------
// MULTI-NODO: detección dinámica de device_id, un módulo y una gráfica por dispositivo
// -------------------------------------------------------------
const FLEET_SEED_IDS = ["esp32_sensor_01", "esp32_virtual_01", "esp32_virtual_02", "esp32_virtual_03", "esp32_virtual_04"];
const DEVICE_COLORS = ["#2dd4bf", "#60a5fa", "#f59e0b", "#c084fc", "#f472b6", "#a3e635", "#fb923c", "#38bdf8"];
const knownDevices = [];     // orden de descubrimiento (colores estables)
const deviceCharts = {};     // device_id -> instancia Chart.js propia
let devicesBusy = false;
let devicesPending = false;
let monitorDeviceId = "";    // "" = última lectura de cualquier nodo

function escapeHtml(v) {
  return String(v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function fetchJson(url) {
  try {
    const res = await fetch(url);
    return res.ok ? await res.json() : null;
  } catch (e) {
    return null;
  }
}

function deviceColor(id) {
  let i = knownDevices.indexOf(id);
  if (i < 0) { knownDevices.push(id); i = knownDevices.length - 1; }
  return DEVICE_COLORS[i % DEVICE_COLORS.length];
}

function recordDate(r) {
  const raw = r && (r.timestamp || (r.metadata && r.metadata.timestamp) || r.time || r.created_at || r.ts);
  const d = raw ? new Date(raw) : null;
  return d && !isNaN(d) ? d : null;
}

function normalizeRecords(records) {
  const items = (records || []).filter((r) => r && r.metrics);
  // si todos traen fecha válida, ordenar de más antiguo a más reciente
  if (items.length > 1 && items.every((r) => recordDate(r))) items.sort((a, b) => recordDate(a) - recordDate(b));
  return items;
}

// 1) Detecta device_id: endpoint /devices si existe; si no, escanea el historial global. Siempre suma /actuators/all.
async function discoverDevices() {
  const candidates = new Set(FLEET_SEED_IDS);
  const registered = new Set();
  const [list, actuators] = await Promise.all([
    fetchJson("/api/telemetry/devices"),
    fetchJson("/api/actuators/all"),
  ]);

  if (list && Array.isArray(list.devices)) {
    list.devices.forEach((d) => {
      const id = typeof d === "string" ? d : d && d.device_id;
      if (id) candidates.add(id);
    });
  } else {
    const history = await fetchJson("/api/telemetry/timeseries?limit=300");
    if (history && Array.isArray(history.data)) {
      history.data.forEach((r) => {
        const id = r && r.metadata && r.metadata.device_id;
        if (id) candidates.add(id);
      });
    }
  }

  if (actuators && typeof actuators === "object") {
    Object.keys(actuators).forEach((id) => { candidates.add(id); registered.add(id); });
  }
  return { candidates: [...candidates], registered };
}

async function loadDeviceData(id) {
  const series = await fetchJson(`/api/telemetry/timeseries?device_id=${encodeURIComponent(id)}&limit=30`);
  const records = normalizeRecords(series && series.data);
  return { id, records, hasData: records.length > 0, relay: null };
}

function patternTone(pattern) {
  if (pattern === "Sobrecarga / Anomalía") return "bad";
  if (pattern === "Pico de Demanda") return "warn";
  if (pattern === "Fuga / Consumo Parásito") return "leak";
  return "ok";
}

// 2) Ciclo único: descubre → carga cada nodo → consulta su relé → pinta todo
async function refreshDevices() {
  if (devicesBusy) { devicesPending = true; return; }
  devicesBusy = true;
  try {
    do {
      devicesPending = false;
      const { candidates, registered } = await discoverDevices();
      const loaded = await Promise.all(candidates.map(loadDeviceData));
      // solo se muestran nodos con lecturas o registrados como actuadores (evita tarjetas fantasma)
      const visible = loaded.filter((d) => d.hasData || registered.has(d.id));
      await Promise.all(visible.map(async (d) => {
        d.relay = await fetchJson(`/api/actuators/relay/${encodeURIComponent(d.id)}`);
      }));
      visible.sort((a, b) => Number(b.hasData) - Number(a.hasData) || a.id.localeCompare(b.id));
      visible.forEach((d) => deviceColor(d.id));

      renderFleet(visible);
      renderRelayModules(visible);
      syncDeviceSelectors(visible);
    } while (devicesPending);
  } catch (err) {
    console.error("Error refreshing devices:", err);
  } finally {
    devicesBusy = false;
  }
}

function refreshFleet() { return refreshDevices(); }
function refreshRelay() { return refreshDevices(); }

function relayIsOn(d) {
  if (d.relay) return d.relay.relay_state === 1;
  const last = d.records[d.records.length - 1];
  return last && last.metrics ? last.metrics.relay_state === 1 : true;
}

// ---------- Tarjeta + gráfica de corriente por nodo (se crean una vez y se actualizan) ----------
function createDeviceCard(id) {
  const card = document.createElement("article");
  card.className = "node-card tone-idle";
  card.dataset.device = id;
  card.innerHTML = `
    <header class="node-head">
      <span class="node-dot"></span>
      <div class="node-title"><h3 data-f="name"></h3><p data-f="loc"></p></div>
      <span class="node-state" data-f="state"></span>
    </header>
    <div class="node-kpis">
      <div><span class="node-power-value" data-f="current">0.00</span><span class="node-power-unit">A</span></div>
      <div class="node-sub"><span data-f="power">0</span> W</div>
    </div>
    <div class="node-chart"><canvas></canvas></div>
    <dl class="node-metrics">
      <div><dt>Tensión</dt><dd data-f="voltage">0 V</dd></div>
      <div><dt>F. potencia</dt><dd data-f="pf">0.00</dd></div>
      <div><dt>Frecuencia</dt><dd data-f="freq">0 Hz</dd></div>
      <div><dt>Temp.</dt><dd data-f="temp">0 °C</dd></div>
    </dl>
    <footer class="node-foot">
      <span class="pill" data-f="pattern"></span>
      <span class="relay-chip" data-f="relay"></span>
      <button type="button" class="btn btn-secondary btn-sm" data-f="toggle"></button>
    </footer>`;
  card.querySelector('[data-f="name"]').textContent = id;
  card.querySelector('[data-f="toggle"]').addEventListener("click", (e) => {
    toggleDeviceRelay(id, Number(e.currentTarget.dataset.next));
  });
  return card;
}

function updateDeviceCard(card, d) {
  const f = (k) => card.querySelector(`[data-f="${k}"]`);
  const color = deviceColor(d.id);
  const last = d.records[d.records.length - 1];
  const m = (last && last.metrics) || {};
  const ai = (last && last.ai_evaluation) || {};
  const pattern = ai.pattern_class || "Normal";
  const tone = d.hasData ? patternTone(pattern) : "idle";
  const on = relayIsOn(d);

  card.className = `node-card tone-${tone}`;
  card.querySelector(".node-dot").style.background = color;
  f("loc").textContent = (last && last.metadata && last.metadata.location) || "Sin ubicación";
  f("state").textContent = d.hasData ? "En línea" : "Sin datos";
  f("state").className = `node-state ${d.hasData ? "is-live" : "is-idle"}`;
  f("current").textContent = (m.current || 0).toFixed(2);
  f("power").textContent = (m.active_power || 0).toFixed(0);
  f("voltage").textContent = `${(m.voltage || 0).toFixed(1)} V`;
  f("pf").textContent = (m.power_factor || 0).toFixed(2);
  f("freq").textContent = `${(m.frequency || 0).toFixed(1)} Hz`;
  f("temp").textContent = `${(m.temperature || 0).toFixed(0)} °C`;
  f("pattern").textContent = d.hasData ? pattern : "Inactivo";
  f("pattern").className = `pill pill-${tone}`;
  f("relay").textContent = on ? "Relé conectado" : "Relé abierto";
  f("relay").className = `relay-chip ${on ? "on" : "off"}`;
  f("toggle").textContent = on ? "Cortar" : "Reconectar";
  f("toggle").dataset.next = on ? 0 : 1;

  updateDeviceChart(card, d, color);
}

function updateDeviceChart(card, d, color) {
  if (typeof Chart === "undefined") return;
  const labels = d.records.map((r, i) => {
    const t = recordDate(r);
    return t ? t.toLocaleTimeString() : String(i + 1);
  });
  const values = d.records.map((r) => r.metrics.current || 0);
  let chart = deviceCharts[d.id];

  if (!chart) {
    chart = new Chart(card.querySelector("canvas").getContext("2d"), {
      type: "line",
      data: {
        labels,
        datasets: [{ label: "Corriente (A)", data: values, borderColor: color, backgroundColor: color + "22", fill: true, tension: 0.3, borderWidth: 2, pointRadius: 0 }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        scales: {
          x: { grid: { display: false }, ticks: { color: "#8b97ad", maxTicksLimit: 4, maxRotation: 0 } },
          y: { beginAtZero: true, grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: "#8b97ad", maxTicksLimit: 4 }, title: { display: true, text: "A", color: "#8b97ad" } },
        },
        plugins: { legend: { display: false } },
      },
    });
    deviceCharts[d.id] = chart;
  } else {
    chart.data.labels = labels;
    chart.data.datasets[0].data = values;
    chart.update("none");
  }
}

function destroyDeviceChart(id) {
  if (deviceCharts[id]) { deviceCharts[id].destroy(); delete deviceCharts[id]; }
}

function resizeDeviceCharts() {
  Object.values(deviceCharts).forEach((c) => c.resize());
}

function renderFleet(visible) {
  const grid = document.getElementById("fleetGrid");
  if (!grid) return;
  const ids = new Set(visible.map((d) => d.id));

  grid.querySelectorAll(".node-card").forEach((card) => {
    if (!ids.has(card.dataset.device)) { destroyDeviceChart(card.dataset.device); card.remove(); }
  });

  const empty = grid.querySelector(".fleet-empty");
  if (!visible.length) {
    if (!empty) grid.insertAdjacentHTML("beforeend", '<div class="fleet-empty">Aún no hay nodos reportando. Inyecta telemetría desde la pestaña 5 o enciende un ESP32.</div>');
  } else if (empty) {
    empty.remove();
  }

  visible.forEach((d) => {
    let card = [...grid.querySelectorAll(".node-card")].find((c) => c.dataset.device === d.id);
    if (!card) { card = createDeviceCard(d.id); grid.appendChild(card); }
    updateDeviceCard(card, d);
  });

  const live = visible.filter((d) => d.hasData);
  const totalPower = live.reduce((acc, d) => acc + (d.records[d.records.length - 1].metrics.active_power || 0), 0);
  const setText = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
  setText("fleetTotal", visible.length);
  setText("fleetOn", visible.filter(relayIsOn).length);
  setText("fleetOff", visible.filter((d) => !relayIsOn(d)).length);
  setText("fleetPower", totalPower.toFixed(0));
  setText("fleetUpdated", new Date().toLocaleTimeString());
  setText("fleetCountPill", visible.length);
}

// ---------- Pantalla 2: un módulo de relé por dispositivo ----------
function renderRelayModules(visible) {
  const box = document.getElementById("relayDevices");
  if (!box) return;
  if (!visible.length) {
    box.innerHTML = '<div class="fleet-empty">Aún no hay actuadores registrados.</div>';
    return;
  }
  box.innerHTML = visible.map((d) => {
    const on = relayIsOn(d);
    const r = d.relay || {};
    const id = escapeHtml(d.id);
    const reason = d.relay ? (r.reason || (on ? "Operación nominal autorizada" : "Corte de protección ejecutado")) : "Sin respuesta del actuador";
    return `
      <article class="relay-module ${on ? "is-on" : "is-off"}">
        <header class="relay-module-head">
          <span class="node-dot" style="background:${deviceColor(d.id)}"></span>
          <h3>${id}</h3>
          <span class="status-pill ${on ? "green" : "red"}">${escapeHtml(r.mode || "AUTOMÁTICO")}</span>
        </header>
        <div class="relay-module-body">
          <div class="breaker-icon ${on ? "breaker-on" : "breaker-off"}">${on ? "⚡" : "⛔"}</div>
          <div>
            <h4 class="relay-title ${on ? "ok" : "bad"}">${on ? "Carga conectada" : "Carga desconectada (corte activo)"}</h4>
            <p class="relay-reason">${escapeHtml(reason)}</p>
            <p class="relay-trips">Disparos acumulados: <strong>${Number(r.trip_count) || 0}</strong></p>
          </div>
        </div>
        <div class="btn-row">
          <button class="btn btn-primary btn-sm" data-relay-id="${id}" data-state="1">Reconectar</button>
          <button class="btn btn-danger btn-sm" data-relay-id="${id}" data-state="0">Desconectar</button>
        </div>
      </article>`;
  }).join("");
}

document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-relay-id]");
  if (btn) toggleDeviceRelay(btn.dataset.relayId, Number(btn.dataset.state));
});

async function toggleDeviceRelay(deviceId, state) {
  try {
    const res = await fetch(`/api/actuators/relay/${encodeURIComponent(deviceId)}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        state: state,
        reason: state === 1 ? "Reconexión manual desde Panel Web" : "Desconexión manual preventiva de emergencia",
        mode: "MANUAL_WEB",
      }),
    });
    if (res.ok) refreshDevices();
  } catch (err) {
    alert("Error al enviar comando al actuador: " + err);
  }
}

// ---------- Selectores de nodo (Monitoreo y Banco de pruebas) ----------
function fillSelect(sel, items) {
  if (!sel) return;
  const sig = items.map((i) => i.value).join("|");
  if (sel.dataset.sig === sig) return; // no tocar el desplegable si no cambió
  const current = sel.value;
  sel.innerHTML = items.map((i) => `<option value="${escapeHtml(i.value)}">${escapeHtml(i.label)}</option>`).join("");
  sel.dataset.sig = sig;
  if ([...sel.options].some((o) => o.value === current)) sel.value = current;
}

function syncDeviceSelectors(visible) {
  const ids = visible.map((d) => d.id);
  fillSelect(document.getElementById("monitorDevice"), [{ value: "", label: "Último nodo que reportó" }, ...ids.map((id) => ({ value: id, label: id }))]);
  const inject = ids.includes("esp32_sensor_01") ? ids : ["esp32_sensor_01", ...ids];
  fillSelect(document.getElementById("injectDevice"), inject.map((id) => ({ value: id, label: id })));
}

function onMonitorDeviceChange(sel) {
  monitorDeviceId = sel.value;
  if (energyChart) {
    energyChart.data.labels = [];
    energyChart.data.datasets.forEach((ds) => { ds.data = []; });
    energyChart.update("none");
  }
  refreshTelemetry();
}