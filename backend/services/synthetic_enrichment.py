
def enrich_telemetry(telemetry_data):

    if not isinstance(telemetry_data, dict):
        return telemetry_data

    # Copia de los datos originales para evitar mutaciones directas
    enriched_data = telemetry_data.copy()

    # Ejemplo de cálculo/enriquecimiento básico
    v = enriched_data.get("voltage", 0)
    i = enriched_data.get("current", 0)

    # Si el consumo de potencia no viene en la telemetría, se calcula
    if "power" not in enriched_data:
        enriched_data["power"] = round(v * i, 2)

    return enriched_data