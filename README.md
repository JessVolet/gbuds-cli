# Galaxy Buds Headless Controller (Linux)

Herramienta de consola (CLI) y biblioteca ultraligera en Python para controlar auriculares Samsung Galaxy Buds en Linux de forma totalmente autónoma, **sin dependencias de X11, Wayland, Avalonia ni entornos gráficos**.

## Características

- **Empaquetado y CRC16-CCITT**: Serialización y deserialización binaria exacta del protocolo SPP de Samsung.
- **Consulta de Batería**: Porcentajes de auricular izquierdo, derecho y estuche de carga.
- **Control de Ruido (ANC)**: Alternar o fijar modos Normal (Off), ANC (Cancelación Activa de Ruido), Sonido Ambiente y Adaptativo.
- **Bloqueo de Touchpad**: Bloquear o desbloquear los gestos táctiles.
- **Transporte Linux Dual**:
  - `bluez` (Recomendado): Registro de perfil `org.bluez.Profile1` en D-Bus e intercambio de descriptor de archivo Unix (mismo mecanismo que `GalaxyBudsClient.Platform.Linux`). Resuelve automáticamente canales RFCOMM y SDP.
  - `raw`: Conexión de socket de bajo nivel del kernel Linux mediante `socket(AF_BLUETOOTH, SOCK_STREAM, BTPROTO_RFCOMM)`.
- **Detección Automática**: Detecta la dirección MAC de auriculares Galaxy Buds emparejados a través de BlueZ sin necesidad de pasarla manualmente.

---

## Requisitos

- Linux con BlueZ 5+.
- Python 3.10+ (con módulos estándar `socket`, `dbus`, `gi`).
- Auriculares emparejados previamente vía Bluetooth (`bluetoothctl`).

---

## Uso del CLI

### 1. Información del dispositivo y hardware
Identifica el modelo exacto (código SM, color, capacidades de ANC/Adaptive) y, si están conectados, extrae versión de firmware y número de serie:
```bash
./buds_cli.py info
```
Salida de ejemplo:
```text
========================================
  Device:           Buds3 de Jose
  Model:            Galaxy Buds3 (SM-R530)
  Color:            Silver
  MAC Address:      24:24:B7:DD:38:90
  Bluetooth Link:   Connected
  Supports ANC:     Yes
  Supports Adaptive:Yes
  Firmware Version: R530XXU0AZD2
----------------------------------------
  • Battery Left:   97%
  • Battery Right:  98%
  • Noise Control:  OFF
  • Touchpad:       Locked
========================================
```

### 2. Consultar estado y nivel de batería
```bash
./buds_cli.py battery
```
Salida de ejemplo:
```text
=== Galaxy Buds Battery Status ===
  • Left earbud:  97%
  • Right earbud: 98%
  • Case:         N/A (Buds out of case or closed)
  • Noise Control: OFF
  • Touchpad:      Locked
```

### 3. Alternar o cambiar Cancelación de Ruido (ANC)
```bash
# Alternar entre ANC y Normal (Off)
./buds_cli.py anc toggle

# Activar ANC
./buds_cli.py anc on

# Desactivar ANC (Modo Normal)
./buds_cli.py anc off

# Activar Modo Ambiente
./buds_cli.py anc ambient

# Activar Modo Adaptativo (Buds3 / Buds3 Pro)
./buds_cli.py anc adaptive
```

### 3. Bloquear / Desbloquear Touchpad
```bash
# Bloquear gestos táctiles
./buds_cli.py touchpad lock

# Desbloquear gestos táctiles
./buds_cli.py touchpad unlock
```

### 4. Especificar MAC o transporte manualmente
```bash
./buds_cli.py --mac 24:24:B7:DD:38:90 battery
./buds_cli.py --transport raw --channel 1 battery
```

---

## Estructura del Proyecto

```text
main/
├── buds_cli.py          # Punto de entrada CLI autónomo
├── buds/
│   ├── __init__.py
│   ├── protocol.py      # Estructura de paquetes, CRC16-CCITT, MsgIds, serialización
│   ├── transport.py     # Transportes RFCOMM en Linux (BlueZ Profile D-Bus & AF_BLUETOOTH)
│   └── client.py        # Cliente de alto nivel (BudsClient)
├── tests/
│   └── test_protocol.py # Pruebas unitarias contra datos reales de GalaxyBudsClient
└── README.md
```

---

## Ejecutar Pruebas Unitarias

```bash
PYTHONPATH=. python3 -m unittest discover -s tests
```
