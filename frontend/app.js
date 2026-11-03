// EcoGrid AI - Frontend Application Logic

let energyChart = null;
const chartMaxPoints = 25;

// Inicialización de la aplicación
document.addEventListener("DOMContentLoaded", () => {
  initChart();
  refreshAllData();
  loadIncidentHistory();

  // Polling periódico cada 2.5 segundos
  setInterval(() => {
    refreshTelemetry();
    refreshRelay();
    refreshSecurity();
  }, 2500);
});

// -------------------------------------------------------------
// CONTROL DE PESTAÑAS (TABS)
// -------------------------------------------------------------
function switchTab(tabId) {
  const sections = ["tab-monitoring", "tab-relay", "tab-textmining", "tab-security", "tab-simulator"];
  sections.forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.style.display = id === tabId ? "block" : "none";
  });

  const buttons = document.querySelectorAll(".tab-btn");
  buttons.forEach((btn) => btn.classList.remove("active"));
  event.target.classList.add("active");

  if (tabId === "tab-security") {
    refreshSecurity();
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
    const res = await fetch("/api/telemetry/latest");
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
// CONTROL DEL RELÉ DE DESCONEXIÓN
// -------------------------------------------------------------
async function refreshRelay() {
  try {
    const res = await fetch("/api/actuators/relay/esp32_sensor_01");
    if (!res.ok) return;
    const data = await res.json();

    const isConnected = data.relay_state === 1;
    const title = document.getElementById("relayStatusTitle");
    const reason = document.getElementById("relayReasonText");
    const icon = document.getElementById("breakerIcon");
    const modeBadge = document.getElementById("relayModeBadge");
    const tripVal = document.getElementById("tripCountVal");

    tripVal.textContent = data.trip_count || 0;
    modeBadge.textContent = `MODO: ${data.mode || "AUTOMÁTICO"}`;

    if (isConnected) {
      title.textContent = "CARGA CONECTADA";
      title.style.color = "#00d26a";
      reason.textContent = data.reason || "Operación nominal autorizada";
      icon.className = "breaker-icon breaker-on";
      icon.textContent = "⚡";
    } else {
      title.textContent = "CARGA DESCONECTADA (CORTE ACTIVO)";
      title.style.color = "#ef4444";
      reason.textContent = data.reason || "Corte de protección ejecutado";
      icon.className = "breaker-icon breaker-off";
      icon.textContent = "⛔";
    }
  } catch (err) {
    console.error("Error refreshing relay:", err);
  }
}

async function toggleRelay(state) {
  try {
    const res = await fetch("/api/actuators/relay/esp32_sensor_01", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        state: state,
        reason: state === 1 ? "Reconexión manual desde Panel Web" : "Desconexión manual preventiva de emergencia",
        mode: "MANUAL_WEB",
      }),
    });
    if (res.ok) {
      refreshRelay();
    }
  } catch (err) {
    alert("Error al enviar comando al actuador: " + err);
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
    device_id: "esp32_sensor_01",
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
      refreshRelay();
    }
  } catch (err) {
    alert("Error inyectando telemetría: " + err);
  }
}

function refreshAllData() {
  refreshTelemetry();
  refreshRelay();
  refreshSecurity();
}
