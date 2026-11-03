"""
EcoGrid AI - Script de Inicio del Servidor y Plataforma Web
Universidad Tecnológica de Calvillo (UTC)
"""

import os
import sys

# Asegurar path de importación
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from backend.app import create_app

if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("PORT", 5000))
    print("=" * 75)
    print("  ⚡ ECOGRID AI: PLATAFORMA GESTORA DE ENERGÍA Y CIBERSEGURIDAD")
    print("  Universidad Tecnológica de Calvillo (UTC) - 7mo Cuatrimestre")
    print("=" * 75)
    print(f"  -> Servidor Web Activo en:  http://127.0.0.1:{port}")
    print(f"  -> Panel de Ciberseguridad: http://127.0.0.1:{port}/#tab-security")
    print(f"  -> Trampas Honeypot activas en: /admin, /scada/admin, /firmware/update")
    print("=" * 75)
    app.run(host="0.0.0.0", port=port, debug=False)
