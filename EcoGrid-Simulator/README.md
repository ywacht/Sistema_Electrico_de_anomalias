# EcoGrid AI - Simulador de nodo ESP32

Simula la telemetría HTTP de un ESP32 para el backend Flask, con OLED virtual, carga, sensor ACS712, umbral de corte local y control remoto del relé.

## Requisitos
- Python 3
- Tkinter (en algunas distribuciones Linux se instala por separado)
- requests
- Backend Flask ejecutándose y accesible por HTTP

## Instalación (Arch Linux)
```bash
sudo pacman -S python python-tkinter
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecutar un nodo
```bash
python simulator.py --id esp32_virtual_01 --host http://127.0.0.1:5000 --load Ventilador --amps 0.45 --threshold 1.5
```

Cambia `127.0.0.1` por la IP del PC servidor si Flask está en otra máquina. Flask debe escuchar en una interfaz accesible, por ejemplo `0.0.0.0`, y el firewall debe permitir el puerto.

## Lanzar cuatro nodos
Abre cuatro terminales, activa el entorno virtual en cada una y ejecuta:
```bash
python simulator.py --id esp32_virtual_01 --load Ventilador --amps 0.45 --threshold 1.5
python simulator.py --id esp32_virtual_02 --load Motor --amps 0.80 --threshold 1.8
python simulator.py --id esp32_virtual_03 --load Iluminacion --amps 0.25 --threshold 1.0
python simulator.py --id esp32_virtual_04 --load Carga-prueba --amps 1.10 --threshold 2.0
```

Cada ventana representa un nodo distinto. Los botones permiten activar/desactivar la carga, generar una anomalía y simular la pérdida de WiFi.

## API esperada
- POST `/api/telemetry` con JSON: `device_id`, `current`, `relay_state`
- GET `/api/actuators/relay/<device_id>` con JSON: `relay_state`
- La respuesta POST puede contener `should_disconnect` (booleano).

La simulación de corriente y los componentes visuales son aproximados, no representan mediciones físicas ni protecciones certificadas.
