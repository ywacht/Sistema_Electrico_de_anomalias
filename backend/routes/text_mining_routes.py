"""
EcoGrid AI - Rutas de Minería de Texto para Incidentes Eléctricos
Asignatura: Minería de Texto (IA)
Universidad Tecnológica de Calvillo (UTC)
"""

from flask import Blueprint, request, jsonify
from backend.database import db_repo
from backend.services.ai_service import ai_service
from security.syslog_service import syslog_client, SyslogFacility, SyslogSeverity

text_mining_bp = Blueprint("text_mining", __name__, url_prefix="/api/text-mining")


@text_mining_bp.route("/classify", methods=["POST"])
def classify_incident_text():
    """
    Recibe texto no estructurado de bitácora técnica de mantenimiento
    y retorna la severidad clasificada, términos clave y recomendaciones.
    """
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()

    if not text:
        return jsonify({"error": "El campo 'text' es obligatorio"}), 400

    result = ai_service.classify_maintenance_text(text)

    # Persistir en base de datos
    log_doc = db_repo.insert_incident_log({
        "log_text": text,
        "predicted_severity": result["predicted_severity"],
        "confidence": result["confidence"],
        "action_taken": result["recommended_action"],
    })

    # Si la severidad es Alta o Crítica, generar alerta Syslog
    if result.get("requires_shutdown"):
        syslog_client.send_log(
            facility=SyslogFacility.LOCAL2,
            severity=SyslogSeverity.CRITICAL if result["predicted_severity"] == "Crítica" else SyslogSeverity.WARNING,
            message=f"[INCIDENT_ALERT] Bitácora clasificada como '{result['predicted_severity']}': {text[:90]}",
            msg_id="MAINT_ALERT",
        )

    return jsonify({
        "status": "success",
        "entry_id": log_doc.get("id") or log_doc.get("_id"),
        "analysis": result,
    }), 200


@text_mining_bp.route("/logs", methods=["GET"])
def get_incident_logs():
    """Obtiene el historial de bitácoras e incidentes registrados."""
    limit = int(request.args.get("limit", 40))
    logs = db_repo.query_incident_logs(limit=limit)
    return jsonify({
        "total": len(logs),
        "logs": logs,
    })


@text_mining_bp.route("/metrics", methods=["GET"])
def get_model_metrics():
    """Retorna las métricas académicas oficiales del modelo de minería de texto."""
    metrics = ai_service.get_text_mining_metrics()
    return jsonify({
        "subject": "Minería de Texto (IA) - UTC",
        "model_architecture": "TF-IDF N-Gram Vectorizer + Linear Support Vector Classifier (LinearSVC)",
        "metrics": metrics,
    })
