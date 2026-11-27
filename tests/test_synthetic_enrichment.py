"""
EcoGrid AI - Pruebas Unitarias para Enriquecimiento Sintético de Telemetría
Universidad Tecnológica de Calvillo (UTC)
"""

import unittest
from backend.app import create_app
from backend.services.synthetic_enrichment import enrich_telemetry
from backend.services.ai_service import ai_service


class TestSyntheticEnrichment(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_enrich_normal_current(self):
        """Verifica que una lectura normal genera un vector coherente."""
        raw = {"device_id": "esp32_sensor_01", "current": 5.5, "relay_state": 1}
        enriched = enrich_telemetry(raw)

        self.assertIn("voltage", enriched)
        self.assertTrue(118.0 <= enriched["voltage"] <= 122.5)
        self.assertTrue(0.92 <= enriched["power_factor"] <= 0.98)
        self.assertTrue(2.0 <= enriched["thd"] <= 5.0)
        self.assertTrue(27.0 <= enriched["temperature"] <= 36.0)
        self.assertTrue(59.8 <= enriched["frequency"] <= 60.2)
        self.assertTrue(enriched["_synthetic_enrichment"])

    def test_enrich_overload_current(self):
        """Verifica que una lectura de sobrecarga (>32A) genera THD alto y temperatura alta."""
        raw = {"device_id": "esp32_sensor_01", "current": 38.0, "relay_state": 1}
        enriched = enrich_telemetry(raw)

        self.assertTrue(enriched["voltage"] < 115.0, "Debe haber caída de tensión severa")
        self.assertTrue(enriched["thd"] >= 15.0, "THD debe superar umbral de anomalía (15%)")
        self.assertTrue(enriched["temperature"] >= 68.0, "Temperatura debe reflejar sobrecalentamiento crítico")

        # Evaluar con IA
        ai_res = ai_service.evaluate_telemetry(
            enriched["voltage"], enriched["current"], enriched["active_power"],
            enriched["reactive_power"], enriched["power_factor"], enriched["frequency"],
            enriched["thd"], enriched["temperature"]
        )
        self.assertTrue(ai_res["should_disconnect"])
        self.assertEqual(ai_res["class_name"], "Sobrecarga / Anomalía")

    def test_enrich_relay_open(self):
        """Verifica que si relay_state=0, la corriente se fija en 0."""
        raw = {"device_id": "esp32_sensor_01", "current": 10.0, "relay_state": 0}
        enriched = enrich_telemetry(raw)

        self.assertEqual(enriched["current"], 0.0)
        self.assertTrue(119.0 <= enriched["voltage"] <= 121.0)
        self.assertEqual(enriched["active_power"], 0.0)

    def test_telemetry_route_auto_enrichment(self):
        """Verifica que POST /api/telemetry aplica enriquecimiento si faltan campos."""
        minimal_payload = {
            "device_id": "esp32_sensor_01",
            "current": 6.2,
            "relay_state": 1
        }
        res = self.client.post("/api/telemetry", json=minimal_payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()

        self.assertTrue(data.get("synthetic_enrichment"))
        self.assertIn("voltage", data.get("enriched_fields", []))
        self.assertEqual(data["relay_state"], 1)
        self.assertIn("ai_evaluation", data)

    def test_ai_service_text_mining_fallback_moderado(self):
        """Verifica que el fallback de minería de texto retorne 'Moderado' (esquema de 3 clases)."""
        # Temporalmente forzar loaded = False para validar fallback
        original_state = ai_service.text_mining_loaded
        try:
            ai_service.text_mining_loaded = False
            res = ai_service.classify_maintenance_text("Texto de prueba sin modelo")
            self.assertEqual(res["predicted_severity"], "Moderado")
        finally:
            ai_service.text_mining_loaded = original_state


if __name__ == "__main__":
    unittest.main()

