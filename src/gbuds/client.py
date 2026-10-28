"""
High-level headless client for Samsung Galaxy Buds.
"""

import time
from typing import Optional, Dict, Any, Generator
from .protocol import (
    MsgIds,
    NoiseControlMode,
    EqualizerPreset,
    BladeLightingMode,
    PlacementState,
    BatteryStatus,
    SppMessage,
    build_packet,
    parse_packet,
    decode_battery_status,
    encode_noise_control,
    encode_equalizer,
    encode_blade_lights,
    encode_find_earbuds,
    encode_mute_earbud,
    encode_ambient_volume,
    encode_voice_detect,
    encode_lock_touchpad,
    encode_manager_info,
    SOM,
    EOM,
)
from .transport import BaseTransport, DirectRfcommTransport, BluezProfileTransport
from .models import DeviceModelInfo, identify_device_from_uuids


class BudsClient:
    """Headless client for Samsung Galaxy Buds control and inspection."""

    def __init__(self, mac_address: str, transport_type: str = "direct", channel: Optional[int] = None):
        self.mac_address = mac_address.upper()
        self.transport_type = transport_type
        
        if transport_type == "bluez":
            self.transport: BaseTransport = BluezProfileTransport(self.mac_address)
        else:
            self.transport = DirectRfcommTransport(self.mac_address, channel=channel)
        
        self.buffer = bytearray()
        self.last_battery_status: Optional[BatteryStatus] = None
        self.firmware_version: Optional[str] = None
        self.cradle_serial: Optional[str] = None
        self.left_serial: Optional[str] = None
        self.right_serial: Optional[str] = None

    def connect(self) -> None:
        """Connects transport, sends MANAGER_INFO, and establishes session."""
        self.transport.connect()
        # Handshake: Samsung Manager Info
        self.transport.send(encode_manager_info())

    def disconnect(self) -> None:
        """Closes connection."""
        self.transport.close()

    @staticmethod
    def connect_device(mac: str) -> None:
        """Connects Bluetooth device at the BlueZ host level via D-Bus."""
        import dbus
        bus = dbus.SystemBus()
        bluez = bus.get_object("org.bluez", "/")
        om = dbus.Interface(bluez, "org.freedesktop.DBus.ObjectManager")
        for path, ifaces in om.GetManagedObjects().items():
            if "org.bluez.Device1" in ifaces:
                props = ifaces["org.bluez.Device1"]
                if props.get("Address", "").upper() == mac.upper():
                    dev_obj = bus.get_object("org.bluez", path)
                    dev_iface = dbus.Interface(dev_obj, "org.bluez.Device1")
                    dev_iface.Connect()
                    return
        raise RuntimeError(f"Device {mac} not found in BlueZ.")

    @staticmethod
    def disconnect_device(mac: str) -> None:
        """Disconnects Bluetooth device at the BlueZ host level via D-Bus."""
        import dbus
        bus = dbus.SystemBus()
        bluez = bus.get_object("org.bluez", "/")
        om = dbus.Interface(bluez, "org.freedesktop.DBus.ObjectManager")
        for path, ifaces in om.GetManagedObjects().items():
            if "org.bluez.Device1" in ifaces:
                props = ifaces["org.bluez.Device1"]
                if props.get("Address", "").upper() == mac.upper():
                    dev_obj = bus.get_object("org.bluez", path)
                    dev_iface = dbus.Interface(dev_obj, "org.bluez.Device1")
                    dev_iface.Disconnect()
                    return
        raise RuntimeError(f"Device {mac} not found in BlueZ.")

    def _read_messages(self, timeout: float = 3.0) -> list[SppMessage]:
        """Polls transport for incoming valid SppMessages."""
        messages = []
        end_time = time.time() + timeout

        while time.time() < end_time:
            chunk = self.transport.receive(timeout=0.3)
            if chunk:
                self.buffer.extend(chunk)

            while len(self.buffer) >= 7:
                try:
                    som_idx = self.buffer.index(SOM)
                except ValueError:
                    self.buffer.clear()
                    break

                if som_idx > 0:
                    del self.buffer[:som_idx]

                if len(self.buffer) < 4:
                    break

                header = int.from_bytes(self.buffer[1:3], "little")
                body_size = header & 0x03FF
                total_packet_len = 3 + body_size + 1

                if len(self.buffer) < total_packet_len:
                    break

                packet_bytes = bytes(self.buffer[:total_packet_len])
                del self.buffer[:total_packet_len]

                msg = parse_packet(packet_bytes)
                if msg:
                    messages.append(msg)
                    self._process_incoming_message(msg)

            if self.last_battery_status and self.firmware_version:
                break

        return messages

    def _process_incoming_message(self, msg: SppMessage) -> None:
        """Processes message IDs to update cached status and info."""
        if msg.msg_id in (MsgIds.EXTENDED_STATUS_UPDATED, MsgIds.STATUS_UPDATED):
            bat = decode_battery_status(msg)
            if bat:
                self.last_battery_status = bat

        # MsgId 104 (0x68): VERSION_INFO_LONG
        elif msg.msg_id == MsgIds.VERSION_INFO_LONG and len(msg.payload) >= 14:
            try:
                raw_str = msg.payload[2:].split(b"\x00")[0]
                fw = raw_str.decode("ascii", errors="ignore").strip()
                if fw:
                    self.firmware_version = fw
            except Exception:
                pass

        # MsgId 205 (0xCD): CRADLE_SERIAL_NUMBER
        elif msg.msg_id == MsgIds.CRADLE_SERIAL_NUMBER and len(msg.payload) >= 11:
            try:
                self.cradle_serial = msg.payload.decode("ascii", errors="ignore").strip("\x00")
            except Exception:
                pass

        # MsgId 41 (0x29): DEBUG_SERIAL_NUMBER
        elif msg.msg_id == MsgIds.DEBUG_SERIAL_NUMBER and len(msg.payload) >= 22:
            try:
                self.left_serial = msg.payload[:11].decode("ascii", errors="ignore")
                self.right_serial = msg.payload[11:22].decode("ascii", errors="ignore")
            except Exception:
                pass

        # MsgId 132 (0x84): AMBIENT_VOLUME
        elif msg.msg_id == MsgIds.AMBIENT_VOLUME and len(msg.payload) >= 1:
            if self.last_battery_status:
                self.last_battery_status.ambient_volume = msg.payload[0]

    def get_battery(self, timeout: float = 3.0) -> Optional[BatteryStatus]:
        """Retrieves battery, placement, and telemetry status from the earbuds."""
        self._read_messages(timeout=timeout)
        return self.last_battery_status

    def set_noise_control(self, mode: NoiseControlMode, model_info: Optional[DeviceModelInfo] = None) -> None:
        """Sets noise control mode, validating device capabilities."""
        if model_info:
            if mode == NoiseControlMode.AMBIENT_SOUND and not model_info.has_ambient:
                raise ValueError(f"{model_info.model_name} does not support Ambient Sound mode.")
            if mode == NoiseControlMode.NOISE_REDUCTION and not model_info.has_anc:
                raise ValueError(f"{model_info.model_name} does not support Active Noise Cancellation (ANC).")
            if mode == NoiseControlMode.ADAPTIVE and not model_info.supports_adaptive:
                raise ValueError(f"{model_info.model_name} does not support Adaptive mode.")

        pkt = encode_noise_control(mode)
        self.transport.send(pkt)

    def toggle_anc(self, model_info: Optional[DeviceModelInfo] = None) -> NoiseControlMode:
        """Toggles noise control mode according to device hardware capabilities."""
        status = self.get_battery(timeout=1.0)
        current_mode = status.noise_control_mode if status else None

        if model_info and not model_info.has_anc:
            new_mode = NoiseControlMode.OFF if current_mode == NoiseControlMode.AMBIENT_SOUND else NoiseControlMode.AMBIENT_SOUND
        else:
            new_mode = NoiseControlMode.OFF if current_mode == NoiseControlMode.NOISE_REDUCTION else NoiseControlMode.NOISE_REDUCTION

        self.set_noise_control(new_mode, model_info=model_info)
        return new_mode

    def set_equalizer(self, preset: EqualizerPreset) -> None:
        """Sets the equalizer sound profile."""
        pkt = encode_equalizer(preset)
        self.transport.send(pkt)

    def set_blade_lights(self, mode: BladeLightingMode, model_info: Optional[DeviceModelInfo] = None) -> None:
        """Controls stem LED Blade Lights (Buds 3 / Buds 3 Pro)."""
        if model_info and not model_info.has_blade_lights:
            raise ValueError(f"{model_info.model_name} does not have Blade Lights hardware.")
        pkt = encode_blade_lights(mode)
        self.transport.send(pkt)

    def find_earbuds(self, action: str) -> None:
        """
        Rings earbuds for locating them:
        - 'left': Rings left earbud (mutes right).
        - 'right': Rings right earbud (mutes left).
        - 'both': Rings both earbuds.
        - 'stop': Stops ringing.
        """
        action = action.lower().strip()
        if action == "stop":
            self.transport.send(encode_find_earbuds(start=False))
        elif action == "left":
            self.transport.send(encode_mute_earbud(left_mute=False, right_mute=True))
            self.transport.send(encode_find_earbuds(start=True))
        elif action == "right":
            self.transport.send(encode_mute_earbud(left_mute=True, right_mute=False))
            self.transport.send(encode_find_earbuds(start=True))
        elif action == "both":
            self.transport.send(encode_mute_earbud(left_mute=False, right_mute=False))
            self.transport.send(encode_find_earbuds(start=True))
        else:
            raise ValueError(f"Unknown find action: {action}. Expected: left, right, both, or stop.")

    def set_ambient_volume(self, level: int, model_info: Optional[DeviceModelInfo] = None) -> None:
        """Sets the ambient sound amplification level (0 to 4)."""
        if model_info and not model_info.has_ambient:
            raise ValueError(f"{model_info.model_name} does not support Ambient Sound.")
        pkt = encode_ambient_volume(level)
        self.transport.send(pkt)

    def set_voice_detect(self, enable: bool, model_info: Optional[DeviceModelInfo] = None) -> None:
        """Toggles conversation / voice detect auto-pause."""
        if model_info and not model_info.has_voice_detect:
            raise ValueError(f"{model_info.model_name} does not support Voice Detect.")
        pkt = encode_voice_detect(enable)
        self.transport.send(pkt)

    def lock_touchpad(self, lock: bool) -> None:
        """Locks or unlocks the touchpads on both earbuds."""
        pkt = encode_lock_touchpad(lock)
        self.transport.send(pkt)

    def watch(self, interval: float = 0.5) -> Generator[BatteryStatus, None, None]:
        """
        Keeps RFCOMM connection open and yields BatteryStatus on telemetry events.
        Ideal for Waybar, QuickShell, Polybar, or shell monitoring scripts.
        """
        last_yielded = None
        last_poll_time = 0.0

        # Initial query
        self.transport.send(build_packet(MsgIds.STATUS_UPDATED))
        
        while True:
            # Poll messages
            chunk = self.transport.receive(timeout=interval)
            if chunk:
                self.buffer.extend(chunk)

            packet_received = False
            while len(self.buffer) >= 7:
                try:
                    som_idx = self.buffer.index(SOM)
                except ValueError:
                    self.buffer.clear()
                    break

                if som_idx > 0:
                    del self.buffer[:som_idx]

                if len(self.buffer) < 4:
                    break

                header = int.from_bytes(self.buffer[1:3], "little")
                body_size = header & 0x03FF
                total_packet_len = 3 + body_size + 1

                if len(self.buffer) < total_packet_len:
                    break

                packet_bytes = bytes(self.buffer[:total_packet_len])
                del self.buffer[:total_packet_len]

                msg = parse_packet(packet_bytes)
                if msg:
                    self._process_incoming_message(msg)
                    packet_received = True

            now = time.time()
            # Send keep-alive / poll every 10 seconds if no spontaneous updates
            if now - last_poll_time > 10.0:
                try:
                    self.transport.send(build_packet(MsgIds.STATUS_UPDATED))
                    last_poll_time = now
                except Exception:
                    break

            if self.last_battery_status:
                current_dict = self.last_battery_status.to_dict()
                if last_yielded is None or current_dict != last_yielded:
                    last_yielded = current_dict
                    yield self.last_battery_status

    def get_device_info(self, timeout: float = 3.0) -> Dict[str, Any]:
        """
        Gathers full hardware, model, color, and firmware metadata:
        - From BlueZ Bluetooth advertisements (Model name, Code, Color).
        - From active RFCOMM queries (Firmware build, Serials, Battery).
        """
        device_name = "Galaxy Buds"
        advertised_uuids = []
        try:
            import dbus
            bus = dbus.SystemBus()
            bluez = bus.get_object("org.bluez", "/")
            om = dbus.Interface(bluez, "org.freedesktop.DBus.ObjectManager")
            for path, ifaces in om.GetManagedObjects().items():
                if "org.bluez.Device1" in ifaces:
                    props = ifaces["org.bluez.Device1"]
                    if props.get("Address", "").upper() == self.mac_address:
                        device_name = str(props.get("Name", device_name))
                        advertised_uuids = [str(u) for u in props.get("UUIDs", [])]
                        break
        except Exception:
            pass

        model_info = identify_device_from_uuids(advertised_uuids, device_name)

        # Gather RFCOMM live telemetry
        self._read_messages(timeout=timeout)

        # Request serial numbers if not received yet
        try:
            self.transport.send(build_packet(MsgIds.DEBUG_SERIAL_NUMBER))
            self._read_messages(timeout=1.0)
        except Exception:
            pass

        return {
            "mac_address": self.mac_address,
            "bluetooth_name": device_name,
            "model_name": model_info.model_name,
            "model_code": model_info.model_code,
            "color": model_info.color or "Standard",
            "has_anc": model_info.has_anc,
            "has_ambient": model_info.has_ambient,
            "supports_adaptive": model_info.supports_adaptive,
            "has_blade_lights": model_info.has_blade_lights,
            "has_voice_detect": model_info.has_voice_detect,
            "supported_noise_modes": model_info.supported_noise_modes,
            "transport_type": self.transport_type,
            "active_channel": getattr(self.transport, "channel", None),
            "busy_channels": getattr(self.transport, "busy_channels", []),
            "firmware_version": self.firmware_version,
            "cradle_serial": self.cradle_serial,
            "left_serial": self.left_serial,
            "right_serial": self.right_serial,
            "battery": self.last_battery_status,
            "model_info": model_info,
        }
