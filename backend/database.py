
import os
import time
import json
import sqlite3
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()


class TimeSeriesCloudRepository:

    def __init__(self):
        self.mongo_uri = os.getenv("MONGO_URI", "")
        self.db_name = os.getenv("MONGO_DB_NAME", "ecogrid_ai_db")
        self.use_mongo = False
        self.client = None
        self.db = None
        self.local_db_path = os.path.join(os.path.dirname(__file__), "ecogrid_timeseries.db")

        # Intentar conexión a MongoDB Atlas / Cloud NoSQL
        if self.mongo_uri:
            try:
                from pymongo import MongoClient
                self.client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=2500)
                # Test de conexión
                self.client.admin.command("ping")
                self.db = self.client[self.db_name]
                self._setup_mongo_collections()
                self.use_mongo = True
                print(f"[DATABASE] Conectado exitosamente a MongoDB Cloud: {self.db_name}")
            except Exception as e:
                print(f"[DATABASE] No se pudo conectar a MongoDB ({e}). Utilizando repositorio local de series de tiempo.")
                self.use_mongo = False

        if not self.use_mongo:
            self._setup_local_sqlite()

    def _setup_mongo_collections(self):
        """Configura colecciones no relacionales con índices de series de tiempo en MongoDB."""
        try:
            collections = self.db.list_collection_names()
            if "telemetry_timeseries" not in collections:
                # Crear colección de series de tiempo nativa de MongoDB
                self.db.create_collection(
                    "telemetry_timeseries",
                    timeseries={
                        "timeField": "timestamp",
                        "metaField": "metadata",
                        "granularity": "seconds",
                    },
                )
            # Índices para consultas de alta velocidad
            self.db.telemetry_timeseries.create_index([("metadata.device_id", 1), ("timestamp", -1)])
            self.db.incident_logs.create_index([("created_at", -1)])
            self.db.security_events.create_index([("timestamp", -1)])
        except Exception as e:
            print(f"[DATABASE] Aviso en configuración de colecciones Mongo: {e}")

    def _setup_local_sqlite(self):
        """Inicializa repositorio local optimizado para series de tiempo."""
        conn = sqlite3.connect(self.local_db_path)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                epoch_time REAL,
                device_id TEXT,
                voltage REAL,
                current REAL,
                active_power REAL,
                reactive_power REAL,
                power_factor REAL,
                frequency REAL,
                thd REAL,
                temperature REAL,
                relay_state INTEGER,
                pattern_class TEXT,
                should_disconnect INTEGER
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_time ON telemetry(epoch_time DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_dev ON telemetry(device_id)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS incident_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT,
                log_text TEXT,
                predicted_severity TEXT,
                confidence REAL,
                action_taken TEXT
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS security_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                event_type TEXT,
                severity TEXT,
                source_ip TEXT,
                message TEXT,
                details TEXT
            )
        """)
        conn.commit()
        conn.close()

    def insert_telemetry(self, data):
        """
        Almacena una lectura de serie de tiempo de alta frecuencia enviada por ESP32.
        """
        now = datetime.now(timezone.utc)
        iso_time = now.isoformat()
        epoch = time.time()

        doc = {
            "timestamp": now if self.use_mongo else iso_time,
            "epoch_time": epoch,
            "metadata": {
                "device_id": data.get("device_id", "esp32_sensor_01"),
                "location": data.get("location", "Subestacion Principal"),
            },
            "metrics": {
                "voltage": float(data.get("voltage", 120.0)),
                "current": float(data.get("current", 0.0)),
                "active_power": float(data.get("active_power", 0.0)),
                "reactive_power": float(data.get("reactive_power", 0.0)),
                "power_factor": float(data.get("power_factor", 0.95)),
                "frequency": float(data.get("frequency", 60.0)),
                "thd": float(data.get("thd", 3.0)),
                "temperature": float(data.get("temperature", 28.0)),
                "relay_state": int(data.get("relay_state", 1)),
            },
            "ai_evaluation": {
                "pattern_class": data.get("pattern_class", "Normal"),
                "should_disconnect": bool(data.get("should_disconnect", False)),
            },
        }

        if self.use_mongo:
            self.db.telemetry_timeseries.insert_one(doc)
        else:
            conn = sqlite3.connect(self.local_db_path)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO telemetry (
                    timestamp, epoch_time, device_id, voltage, current,
                    active_power, reactive_power, power_factor, frequency,
                    thd, temperature, relay_state, pattern_class, should_disconnect
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                iso_time,
                epoch,
                doc["metadata"]["device_id"],
                doc["metrics"]["voltage"],
                doc["metrics"]["current"],
                doc["metrics"]["active_power"],
                doc["metrics"]["reactive_power"],
                doc["metrics"]["power_factor"],
                doc["metrics"]["frequency"],
                doc["metrics"]["thd"],
                doc["metrics"]["temperature"],
                doc["metrics"]["relay_state"],
                doc["ai_evaluation"]["pattern_class"],
                1 if doc["ai_evaluation"]["should_disconnect"] else 0,
            ))
            conn.commit()
            conn.close()

        return True

    def query_timeseries(self, limit=100, device_id=None):
        """Consulta histórica de lecturas de series de tiempo."""
        if self.use_mongo:
            query = {}
            if device_id:
                query["metadata.device_id"] = device_id
            cursor = self.db.telemetry_timeseries.find(query).sort("timestamp", -1).limit(limit)
            results = []
            for item in cursor:
                item["_id"] = str(item["_id"])
                if isinstance(item["timestamp"], datetime):
                    item["timestamp"] = item["timestamp"].isoformat()
                results.append(item)
            return results[::-1]
        else:
            conn = sqlite3.connect(self.local_db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            if device_id:
                cur.execute("SELECT * FROM telemetry WHERE device_id = ? ORDER BY id DESC LIMIT ?", (device_id, limit))
            else:
                cur.execute("SELECT * FROM telemetry ORDER BY id DESC LIMIT ?", (limit,))
            rows = cur.fetchall()
            conn.close()
            results = []
            for r in rows:
                results.append({
                    "timestamp": r["timestamp"],
                    "epoch_time": r["epoch_time"],
                    "metadata": {"device_id": r["device_id"]},
                    "metrics": {
                        "voltage": r["voltage"],
                        "current": r["current"],
                        "active_power": r["active_power"],
                        "reactive_power": r["reactive_power"],
                        "power_factor": r["power_factor"],
                        "frequency": r["frequency"],
                        "thd": r["thd"],
                        "temperature": r["temperature"],
                        "relay_state": r["relay_state"],
                    },
                    "ai_evaluation": {
                        "pattern_class": r["pattern_class"],
                        "should_disconnect": bool(r["should_disconnect"]),
                    },
                })
            return results[::-1]

    def get_latest_telemetry(self, device_id=None):
        """Retorna la última lectura recibida."""
        items = self.query_timeseries(limit=1, device_id=device_id)
        return items[-1] if items else None

    def insert_incident_log(self, log_entry):
        """Almacena un reporte clasificado de bitácora."""
        now = datetime.now(timezone.utc).isoformat()
        if self.use_mongo:
            doc = {
                "created_at": now,
                "log_text": log_entry.get("log_text", ""),
                "predicted_severity": log_entry.get("predicted_severity", "Baja"),
                "confidence": float(log_entry.get("confidence", 1.0)),
                "action_taken": log_entry.get("action_taken", ""),
            }
            res = self.db.incident_logs.insert_one(doc)
            doc["_id"] = str(res.inserted_id)
            return doc
        else:
            conn = sqlite3.connect(self.local_db_path)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO incident_logs (created_at, log_text, predicted_severity, confidence, action_taken)
                VALUES (?, ?, ?, ?, ?)
            """, (
                now,
                log_entry.get("log_text", ""),
                log_entry.get("predicted_severity", "Baja"),
                float(log_entry.get("confidence", 1.0)),
                log_entry.get("action_taken", ""),
            ))
            entry_id = cur.lastrowid
            conn.commit()
            conn.close()
            return {
                "id": entry_id,
                "created_at": now,
                **log_entry,
            }

    def query_incident_logs(self, limit=50):
        """Obtiene las bitácoras e incidentes registrados."""
        if self.use_mongo:
            cursor = self.db.incident_logs.find().sort("created_at", -1).limit(limit)
            items = []
            for item in cursor:
                item["_id"] = str(item["_id"])
                items.append(item)
            return items
        else:
            conn = sqlite3.connect(self.local_db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM incident_logs ORDER BY id DESC LIMIT ?", (limit,))
            rows = cur.fetchall()
            conn.close()
            return [dict(r) for r in rows]

    def log_security_event(self, event_type, severity, source_ip, message, details=None):
        """Registra un evento de seguridad (DoS, Honeypot, Syslog)."""
        now = datetime.now(timezone.utc).isoformat()
        details_str = json.dumps(details or {}) if isinstance(details, dict) else str(details or "")

        if self.use_mongo:
            self.db.security_events.insert_one({
                "timestamp": now,
                "event_type": event_type,
                "severity": severity,
                "source_ip": source_ip,
                "message": message,
                "details": details or {},
            })
        else:
            conn = sqlite3.connect(self.local_db_path)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO security_events (timestamp, event_type, severity, source_ip, message, details)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (now, event_type, severity, source_ip, message, details_str))
            conn.commit()
            conn.close()

    def query_security_events(self, limit=50):
        """Obtiene el historial de eventos de seguridad."""
        if self.use_mongo:
            cursor = self.db.security_events.find().sort("timestamp", -1).limit(limit)
            events = []
            for item in cursor:
                item["_id"] = str(item["_id"])
                events.append(item)
            return events
        else:
            conn = sqlite3.connect(self.local_db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM security_events ORDER BY id DESC LIMIT ?", (limit,))
            rows = cur.fetchall()
            conn.close()
            events = []
            for r in rows:
                d = dict(r)
                try:
                    d["details"] = json.loads(d["details"])
                except Exception:
                    pass
                events.append(d)
            return events


# Instancia singleton del repositorio
db_repo = TimeSeriesCloudRepository()
