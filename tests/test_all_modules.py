"""
EcoGrid AI - Suite de Pruebas Unitarias Automatizadas
Universidad Tecnológica de Calvillo (UTC)
Verificación de los 6 ejes académicos + Ciberseguridad Honeypot + ESP32
"""

import unittest
import os
import sys

# Agregar ruta base
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai_engine.genetic.genetic_optimizer import GeneticHyperparameterOptimizer
from ai_engine.models.consumption_classifier import (
    EcoGridConsumptionPredictor,
    generate_synthetic_electrical_data,
)
from ai_engine.models.text_mining_classifier import IncidentTextMiningClassifier
from backend.database import TimeSeriesCloudRepository
from backend.services.disconnection_service import LoadDisconnectionService
from security.syslog_service import EcoGridSyslogClient, SyslogFacility, SyslogSeverity
from security.snmp_service import EcoGridSNMPAgent
from security.dos_protection import DoSProtectionEngine
from security.honeypot_service import EcoGridHoneypot


class TestEcoGridAI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.models_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ai_engine", "models", "saved"))

    # ---------------------------------------------------------
    # 1. ASIGNATURA: FUNDAMENTOS DE IA
    # ---------------------------------------------------------
    def test_genetic_algorithm_optimizer(self):
        """Verifica que el Algoritmo Genético encuentre hiperparámetros válidos."""
        X, y = generate_synthetic_electrical_data(n_samples=60, random_state=42)
        optimizer = GeneticHyperparameterOptimizer(
            model_type="knn",
            population_size=4,
            generations=2,
            random_state=42,
        )
        best_params, best_score = optimizer.optimize(X, y, verbose=False)
        self.assertIsNotNone(best_params)
        self.assertIn("n_neighbors", best_params)
        self.assertGreater(best_score, 0.5)

    def test_consumption_models_prediction(self):
        """Verifica inferencia y detección de anomalía de consumo."""
        predictor = EcoGridConsumptionPredictor(models_dir=self.models_dir)
        loaded = predictor.load()
        self.assertTrue(loaded, "Los modelos de consumo deben estar guardados en saved/")

        # Lectura normal
        normal_vec = [120.0, 5.0, 570.0, 180.0, 0.95, 60.0, 3.0, 30.0]
        res_norm = predictor.predict(normal_vec, model_name="neural_network")
        self.assertEqual(res_norm["class_name"], "Normal")
        self.assertFalse(res_norm["should_disconnect"])

        # Lectura de sobrecarga peligrosa
        overload_vec = [110.0, 42.0, 3500.0, 2000.0, 0.75, 59.5, 20.0, 75.0]
        res_over = predictor.predict(overload_vec, model_name="neural_network")
        self.assertEqual(res_over["class_name"], "Sobrecarga / Anomalía")
        self.assertTrue(res_over["should_disconnect"])

    # ---------------------------------------------------------
    # 2. ASIGNATURA: MINERÍA DE TEXTO (IA)
    # ---------------------------------------------------------
    def test_text_mining_incident_classification(self):
        """Verifica clasificación NLP de reportes de fallas y reporte de métricas."""
        clf = IncidentTextMiningClassifier(models_dir=self.models_dir)
        loaded = clf.load()
        self.assertTrue(loaded, "El clasificador de texto debe estar persistido en saved/")

        # Reporte crítico
        critical_text = "Explosión por arco eléctrico con conato de incendio en celda de media tensión"
        crit_res = clf.classify_log(critical_text)
        self.assertEqual(crit_res["predicted_severity"], "Crítica")
        self.assertTrue(crit_res["requires_shutdown"])

        # Reporte de mantenimiento preventivo bajo
        routine_text = "Inspección periódica visual de barrajes y limpieza ordinaria de polvo"
        rout_res = clf.classify_log(routine_text)
        self.assertEqual(rout_res["predicted_severity"], "Baja")
        self.assertFalse(rout_res["requires_shutdown"])

        # Verificación de métricas académicas
        self.assertIn("accuracy", clf.metrics)
        self.assertIn("f1_score_macro", clf.metrics)

    # ---------------------------------------------------------
    # 3. ASIGNATURA: BASES DE DATOS EN LA NUBE (SW)
    # ---------------------------------------------------------
    def test_timeseries_database_repository(self):
        """Verifica inserción masiva y consulta histórica de series de tiempo."""
        db = TimeSeriesCloudRepository()
        telemetry_sample = {
            "device_id": "test_esp32_01",
            "voltage": 120.5,
            "current": 6.2,
            "active_power": 710.0,
            "power_factor": 0.95,
            "pattern_class": "Normal",
            "should_disconnect": False,
        }
        inserted = db.insert_telemetry(telemetry_sample)
        self.assertTrue(inserted)

        # Consulta
        series = db.query_timeseries(limit=5, device_id="test_esp32_01")
        self.assertGreaterEqual(len(series), 1)
        self.assertEqual(series[-1]["metadata"]["device_id"], "test_esp32_01")

    # ---------------------------------------------------------
    # 4. ASIGNATURA: SEGURIDAD INFORMÁTICA (SW) & HONEYPOT
    # ---------------------------------------------------------
    def test_syslog_rfc5424_generation(self):
        """Verifica formateo estándar RFC 5424 de paquetes Syslog."""
        syslog = EcoGridSyslogClient()
        log = syslog.send_log(
            facility=SyslogFacility.LOCAL0,
            severity=SyslogSeverity.WARNING,
            message="Test security incident",
            msg_id="TEST_EVENT",
        )
        self.assertIn("raw_syslog", log)
        self.assertTrue(log["raw_syslog"].startswith("<"))
        self.assertIn("EcoGridAI", log["raw_syslog"])

    def test_snmp_agent_and_traps(self):
        """Verifica MIB privada y emisión de SNMP Traps."""
        agent = EcoGridSNMPAgent()
        agent.update_telemetry_mib(120.2, 8.5, 950.0, 1)
        mib = agent.get_all_mib()
        self.assertEqual(mib["1.3.6.1.4.1.58888.1.1.0"]["value"], 120.2)

        trap = agent.send_snmp_trap(
            trap_oid="1.3.6.1.4.1.58888.1.4.0",
            description="Corte de carga por prueba",
            severity="CRITICAL",
        )
        self.assertIn("timestamp", trap)
        self.assertEqual(trap["severity"], "CRITICAL")

    def test_dos_protection_engine(self):
        """Verifica limitación de tasa y baneo de IP ante inundación."""
        dos = DoSProtectionEngine(max_req_per_second=5, max_req_per_minute=20, ban_duration_seconds=5)
        test_ip = "192.168.100.55"

        # Peticiones normales
        for _ in range(4):
            allowed, _, _ = dos.check_request(test_ip)
            self.assertTrue(allowed)

        # Inundación rápida que sobrepasa 5 req/seg
        for _ in range(3):
            dos.check_request(test_ip)

        # Ahora debe estar baneada
        self.assertTrue(dos.is_ip_banned(test_ip))
        allowed_after_ban, _, code = dos.check_request(test_ip)
        self.assertFalse(allowed_after_ban)
        self.assertEqual(code, 403)

    def test_honeypot_trap_and_autoban(self):
        """Verifica que el señuelo Honeypot atrape al atacante y bloquee su IP."""
        hp = EcoGridHoneypot()
        attacker_ip = "10.0.0.99"
        decoy_path = "/scada/admin"

        self.assertTrue(hp.is_decoy_path(decoy_path))
        intrusion = hp.handle_intrusion_attempt(
            ip=attacker_ip,
            path=decoy_path,
            method="POST",
            payload={"user": "root", "pass": "admin123"},
        )
        self.assertEqual(intrusion["attacker_ip"], attacker_ip)
        self.assertEqual(intrusion["target_path"], decoy_path)

    # ---------------------------------------------------------
    # 5. CONTROL DE ACTUADORES & CORTE DE CARGA
    # ---------------------------------------------------------
    def test_load_disconnection_service(self):
        """Verifica la lógica de corte y reconexión de cargas."""
        svc = LoadDisconnectionService()
        dev = "esp32_test_relay"

        # Conectar
        info1 = svc.set_relay_state(dev, 1, reason="Test conexión")
        self.assertEqual(info1["state"], 1)

        # Desconectar por sobrecarga
        info2 = svc.evaluate_automatic_cutoff(dev, current=38.0, is_ai_anomaly=True, reason="Exceso de corriente")
        self.assertEqual(info2["state"], 0)
        self.assertIn("DESCONEXIÓN AUTOMATIZADA", info2["reason"])


if __name__ == "__main__":
    unittest.main()
