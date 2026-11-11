"""
Re-exportar synthetic_enrichment para garantizar compatibilidad tanto con 'backend.servises'
como con 'backend.services'.
"""
from backend.servises.synthetic_enrichment import enrich_telemetry

__all__ = ["enrich_telemetry"]

