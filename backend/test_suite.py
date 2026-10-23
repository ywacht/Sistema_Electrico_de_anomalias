import unittest
from unittest.mock import MagicMock, patch
from bson import ObjectId
from app import create_app
from services.load_control import evaluar_riesgo


class TestEcoGridBackend(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    # ==========================================
    # 1. PRUEBAS DE INGESTION (ingest_routes)
    # ==========================================
    @patch("routes.ingest_routes.get_lecturas_col")
    def test_post_lectura_valida_esp32(self, mock_col):
        mock_instance = MagicMock()
        mock_instance.insert_one.return_value.inserted_id = ObjectId()
        mock_col.return_value = mock_instance

        payload = {
            "medidor_id": "MED_001",
            "timestamp": "2026-10-23T12:00:00Z",
            "voltaje": 127.5,
            "corriente": 5.2,
            "potencia_kw": 0.66,
            "origen": "esp32"
        }
        res = self.client.post("/api/lecturas", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.get_json()
        self.assertEqual(data["status"], "ok")
        mock_instance.insert_one.assert_called_once()

    @patch("routes.ingest_routes.get_lecturas_col")
    def test_post_lectura_valida_simulador(self, mock_col):
        mock_instance = MagicMock()
        mock_instance.insert_one.return_value.inserted_id = ObjectId()
        mock_col.return_value = mock_instance

        payload = {
            "medidor_id": "SIM_001",
            "timestamp": "2026-10-23T12:05:00Z",
            "voltaje": 120.0,
            "corriente": 10.0,
            "potencia_kw": 1.2,
            "origen": "simulador"
        }
        res = self.client.post("/api/lecturas", json=payload)
        self.assertEqual(res.status_code, 201)

    def test_post_lectura_falta_campo_contrato(self):
        # Falta potencia_kw
        payload = {
            "medidor_id": "MED_001",
            "timestamp": "2026-10-23T12:00:00Z",
            "voltaje": 127.5,
            "corriente": 5.2,
            "origen": "esp32"
        }
        res = self.client.post("/api/lecturas", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Falta el campo requerido", res.get_json()["error"])

    def test_post_lectura_tipo_invalido(self):
        payload = {
            "medidor_id": "MED_001",
            "timestamp": "2026-10-23T12:00:00Z",
            "voltaje": "alto_voltaje",  # No numérico
            "corriente": 5.2,
            "potencia_kw": 0.66,
            "origen": "esp32"
        }
        res = self.client.post("/api/lecturas", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("debe ser un valor numérico", res.get_json()["error"])

    def test_post_lectura_origen_invalido(self):
        payload = {
            "medidor_id": "MED_001",
            "timestamp": "2026-10-23T12:00:00Z",
            "voltaje": 127.5,
            "corriente": 5.2,
            "potencia_kw": 0.66,
            "origen": "desconocido"  # No permitido
        }
        res = self.client.post("/api/lecturas", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("no permitido", res.get_json()["error"])

    @patch("routes.ingest_routes.get_bitacoras_col")
    def test_post_bitacora_valida(self, mock_col):
        mock_instance = MagicMock()
        mock_instance.insert_one.return_value.inserted_id = ObjectId()
        mock_col.return_value = mock_instance

        payload = {
            "medidor_id": "MED_001",
            "texto": "Sobrecalentamiento en transformador principal",
            "severidad": "Crítico"
        }
        res = self.client.post("/api/bitacoras", json=payload)
        self.assertEqual(res.status_code, 201)

    def test_post_bitacora_severidad_invalida(self):
        payload = {
            "medidor_id": "MED_001",
            "texto": "Falla de prueba",
            "severidad": "Peligrosísimo"  # No permitida
        }
        res = self.client.post("/api/bitacoras", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("severidad", res.get_json()["error"])

    def test_post_bitacora_falta_medidor(self):
        payload = {
            "texto": "Falla sin medidor"
        }
        res = self.client.post("/api/bitacoras", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertIn("medidor_id", res.get_json()["error"])

    # ==========================================
    # 2. PRUEBAS DE CONSULTA (query_routes)
    # ==========================================
    @patch("routes.query_routes.get_lecturas_col")
    def test_get_lecturas_historico(self, mock_col):
        mock_instance = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value.limit.return_value = [
            {"_id": ObjectId(), "medidor_id": "MED_001", "voltaje": 127.0, "timestamp": "2026-10-23T10:00:00Z"}
        ]
        mock_instance.find.return_value = mock_cursor
        mock_col.return_value = mock_instance

        res = self.client.get("/api/lecturas?medidor_id=MED_001&desde=2026-10-23T00:00:00Z")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)

    @patch("routes.query_routes.get_lecturas_col")
    def test_get_ultima_lectura(self, mock_col):
        mock_instance = MagicMock()
        mock_instance.find_one.return_value = {
            "_id": ObjectId(),
            "medidor_id": "MED_001",
            "voltaje": 125.0,
            "timestamp": "2026-10-23T11:59:00Z"
        }
        mock_col.return_value = mock_instance

        res = self.client.get("/api/lecturas/ultima?medidor_id=MED_001")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["medidor_id"], "MED_001")
        self.assertIsInstance(data["_id"], str)

    def test_get_ultima_lectura_sin_medidor(self):
        res = self.client.get("/api/lecturas/ultima")
        self.assertEqual(res.status_code, 400)

    @patch("routes.query_routes.get_bitacoras_col")
    def test_get_bitacoras(self, mock_col):
        mock_instance = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = [
            {"_id": ObjectId(), "medidor_id": "MED_001", "texto": "Falla previa"}
        ]
        mock_instance.find.return_value = mock_cursor
        mock_col.return_value = mock_instance

        res = self.client.get("/api/bitacoras?medidor_id=MED_001")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.get_json()), 1)

    @patch("routes.query_routes.get_clasificaciones_col")
    def test_get_clasificaciones(self, mock_col):
        mock_instance = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = [
            {"_id": ObjectId(), "medidor_id": "MED_001", "severidad": "Crítico"}
        ]
        mock_instance.find.return_value = mock_cursor
        mock_col.return_value = mock_instance

        res = self.client.get("/api/clasificaciones?medidor_id=MED_001")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.get_json()), 1)

    @patch("routes.query_routes.get_predicciones_col")
    def test_get_predicciones(self, mock_col):
        mock_instance = MagicMock()
        mock_instance.find_one.return_value = {
            "_id": ObjectId(),
            "medidor_id": "MED_001",
            "pico_predicho": True,
            "probabilidad": 0.88
        }
        mock_col.return_value = mock_instance

        res = self.client.get("/api/predicciones?medidor_id=MED_001")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["probabilidad"], 0.88)

    @patch("routes.query_routes.get_eventos_seguridad_col")
    def test_get_eventos_seguridad(self, mock_col):
        mock_instance = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value.limit.return_value = [
            {"_id": ObjectId(), "tipo": "DoS_SYN_Flood", "ip": "192.168.1.100"}
        ]
        mock_instance.find.return_value = mock_cursor
        mock_col.return_value = mock_instance

        res = self.client.get("/api/eventos-seguridad")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.get_json()), 1)

    # ==========================================
    # 3. CONTROL DE CARGAS (load_control)
    # ==========================================
    @patch("services.load_control.get_cargas_col")
    def test_evaluar_riesgo_pico_alto(self, mock_col):
        mock_instance = MagicMock()
        mock_col.return_value = mock_instance

        prediccion = {"carga_id": "CARGA_A", "pico_predicho": True, "probabilidad": 0.85}
        clasificacion = {"severidad": "Bajo"}

        comando = evaluar_riesgo(prediccion, clasificacion)
        self.assertIsNotNone(comando)
        self.assertEqual(comando["carga_id"], "CARGA_A")
        self.assertEqual(comando["accion"], "desconectar")
        self.assertEqual(comando["estado"], "desconectada")
        mock_instance.update_one.assert_called_once()

    @patch("services.load_control.get_cargas_col")
    def test_evaluar_riesgo_severidad_critica(self, mock_col):
        mock_instance = MagicMock()
        mock_col.return_value = mock_instance

        prediccion = {"carga_id": "CARGA_B", "pico_predicho": False, "probabilidad": 0.20}
        clasificacion = {"severidad": "Crítico"}

        comando = evaluar_riesgo(prediccion, clasificacion)
        self.assertIsNotNone(comando)
        self.assertEqual(comando["carga_id"], "CARGA_B")
        self.assertEqual(comando["accion"], "desconectar")
        self.assertIn("Crítica", comando["motivo"])

    @patch("services.load_control.get_cargas_col")
    def test_evaluar_riesgo_sin_riesgo(self, mock_col):
        mock_instance = MagicMock()
        mock_col.return_value = mock_instance

        prediccion = {"pico_predicho": False, "probabilidad": 0.10}
        clasificacion = {"severidad": "Bajo"}

        comando = evaluar_riesgo(prediccion, clasificacion)
        self.assertIsNone(comando)
        mock_instance.update_one.assert_not_called()

    @patch("services.load_control.get_cargas_col")
    def test_post_cargas_accion_manual(self, mock_col):
        mock_instance = MagicMock()
        mock_col.return_value = mock_instance

        # Desconectar
        res = self.client.post("/api/cargas/accion", json={
            "carga_id": "CARGA_01",
            "accion": "desconectar"
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["carga"]["estado"], "desconectada")

        # Reconectar
        res = self.client.post("/api/cargas/accion", json={
            "carga_id": "CARGA_01",
            "accion": "reconectar"
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["carga"]["estado"], "conectada")

    def test_post_cargas_accion_invalida(self):
        res = self.client.post("/api/cargas/accion", json={
            "carga_id": "CARGA_01",
            "accion": "destruir"
        })
        self.assertEqual(res.status_code, 400)

    @patch("services.load_control.get_cargas_col")
    def test_get_cargas_estado_actual(self, mock_col):
        mock_instance = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = [
            {"_id": ObjectId(), "carga_id": "CARGA_01", "estado": "conectada"}
        ]
        mock_instance.find.return_value = mock_cursor
        mock_col.return_value = mock_instance

        res = self.client.get("/api/cargas")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["carga_id"], "CARGA_01")


if __name__ == "__main__":
    unittest.main()
