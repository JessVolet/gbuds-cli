"""Command-line interface for gbuds."""

import argparse
import json
import sys
import time
from typing import Optional, Dict, Any

from .protocol import (
    NoiseControlMode,
    EqualizerPreset,
    BladeLightingMode,
    PlacementState,
    SPP_UUID_NEW,
    SPP_UUID_STANDARD,
)
from .client import BudsClient
from .models import identify_device_from_uuids, DEVICE_ID_PREFIX


def get_bluez_device_props(mac: str) -> Optional[Dict[str, Any]]:
    try:
        import dbus
        bus = dbus.SystemBus()
        bluez = bus.get_object("org.bluez", "/")
        om = dbus.Interface(bluez, "org.freedesktop.DBus.ObjectManager")
        for path, ifaces in om.GetManagedObjects().items():
            if "org.bluez.Device1" in ifaces:
                props = ifaces["org.bluez.Device1"]
                if props.get("Address", "").upper() == mac.upper():
                    return dict(props)
    except Exception:
        pass
    return None


def auto_detect_buds_mac() -> Optional[str]:
    try:
        import dbus
        bus = dbus.SystemBus()
        bluez = bus.get_object("org.bluez", "/")
        om = dbus.Interface(bluez, "org.freedesktop.DBus.ObjectManager")
        objects = om.GetManagedObjects()

        connected_candidates = []
        other_candidates = []

        for path, ifaces in objects.items():
            if "org.bluez.Device1" in ifaces:
                props = ifaces["org.bluez.Device1"]
                name = str(props.get("Name", ""))
                uuids = [str(u).lower() for u in props.get("UUIDs", [])]
                is_connected = bool(props.get("Connected", False))
                addr = str(props.get("Address"))

                is_buds = "Buds" in name or SPP_UUID_NEW.lower() in uuids or SPP_UUID_STANDARD.lower() in uuids
                if not is_buds:
                    for u in uuids:
                        if u.startswith(DEVICE_ID_PREFIX.lower()):
                            is_buds = True
                            break

                if is_buds:
                    if is_connected:
                        connected_candidates.append(addr)
                    else:
                        other_candidates.append(addr)

        if connected_candidates:
            return connected_candidates[0]
        if other_candidates:
            return other_candidates[0]
    except Exception:
        pass
    return None


def emit_json(data: dict):
    print(json.dumps(data, indent=2))


def emit_error(msg: str, as_json: bool, exit_code: int = 1):
    if as_json:
        emit_json({"success": False, "error": msg})
    else:
        print(f"Error: {msg}", file=sys.stderr)
    sys.exit(exit_code)


def format_placement(state: Optional[PlacementState]) -> str:
    if state is None:
        return "Unknown"
    mapping = {
        PlacementState.DISCONNECTED: "Disconnected",
        PlacementState.WEARING: "Wearing",
        PlacementState.IDLE: "Idle",
        PlacementState.IN_CASE: "In Case",
        PlacementState.CLOSED_CASE: "Closed Case",
    }
    return mapping.get(state, state.name)


def main():
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument(
        "--mac",
        type=str,
        default=None,
        help="Bluetooth MAC address of the Galaxy Buds. Auto-detected if omitted.",
    )
    common_parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON instead of plain text.",
    )
    common_parser.add_argument(
        "--transport",
        choices=["direct", "bluez"],
        default="direct",
        help="Transport backend: direct (kernel socket + SDP) or bluez (D-Bus Profile1).",
    )
    common_parser.add_argument(
        "--channel",
        type=int,
        default=None,
        help="Explicit RFCOMM channel. Auto-discovered via SDP if omitted.",
    )

    parser = argparse.ArgumentParser(
        prog="gbuds",
        description="Headless CLI and library for Samsung Galaxy Buds on Linux.",
        parents=[common_parser],
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Connect / Disconnect
    subparsers.add_parser("connect", parents=[common_parser], help="Connect Galaxy Buds via BlueZ Bluetooth.")
    subparsers.add_parser("disconnect", parents=[common_parser], help="Disconnect Galaxy Buds via BlueZ Bluetooth.")

    # Info / device metadata
    subparsers.add_parser("info", aliases=["device", "device-info"], parents=[common_parser], help="Show hardware metadata, model, color, and firmware.")

    # Battery command
    subparsers.add_parser("battery", aliases=["status"], parents=[common_parser], help="Check battery percentage, wearing status, and state.")

    # ANC command
    anc_parser = subparsers.add_parser("anc", parents=[common_parser], help="Control noise cancellation and ambient modes.")
    anc_parser.add_argument(
        "action",
        nargs="?",
        default="toggle",
        choices=["on", "off", "ambient", "adaptive", "toggle"],
        help="Action: on (ANC), off (Normal), ambient, adaptive, or toggle.",
    )

    # Touchpad command
    touch_parser = subparsers.add_parser("touchpad", parents=[common_parser], help="Lock or unlock earbuds touchpads.")
    touch_parser.add_argument(
        "action",
        choices=["lock", "unlock"],
        help="Action: lock or unlock.",
    )

    # Equalizer command
    eq_parser = subparsers.add_parser("eq", aliases=["equalizer"], parents=[common_parser], help="Configure sound equalizer preset.")
    eq_parser.add_argument(
        "preset",
        nargs="?",
        default=None,
        choices=["normal", "off", "bass", "soft", "dynamic", "clear", "treble", "bass_boost", "treble_boost"],
        help="Preset: normal/off, bass, soft, dynamic, clear, treble. Shows current preset if omitted.",
    )

    # Blade Lights command (Buds 3 / Buds 3 Pro)
    lights_parser = subparsers.add_parser("lights", aliases=["blade-lights"], parents=[common_parser], help="Control stem LED blade lights (Buds 3 / Buds 3 Pro).")
    lights_parser.add_argument(
        "mode",
        choices=["off", "steady", "fade", "blink"],
        help="Lighting mode: off, steady, fade, or blink.",
    )

    # Find My Earbuds command
    find_parser = subparsers.add_parser("find", aliases=["ring"], parents=[common_parser], help="Make earbuds beep to find them.")
    find_parser.add_argument(
        "target",
        nargs="?",
        default="both",
        choices=["left", "right", "both", "stop"],
        help="Target: left, right, both, or stop ringing.",
    )

    # Ambient volume command
    amb_parser = subparsers.add_parser("ambient-volume", parents=[common_parser], help="Set ambient sound amplification level.")
    amb_parser.add_argument(
        "level",
        type=int,
        choices=[0, 1, 2, 3, 4],
        help="Volume level (0 to 4).",
    )

    # Voice Detect command
    voice_parser = subparsers.add_parser("voice-detect", parents=[common_parser], help="Toggle conversation / voice detect auto-pause.")
    voice_parser.add_argument(
        "state",
        choices=["on", "off"],
        help="State: on or off.",
    )

    # Watch / Monitor stream command
    watch_parser = subparsers.add_parser("watch", aliases=["listen"], parents=[common_parser], help="Stream continuous telemetry updates for Waybar/widgets.")
    watch_parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="Polling interval in seconds (default: 0.5).",
    )

    args = parser.parse_args()

    if not args.command:
        if args.json:
            emit_error("No command specified.", as_json=True)
        parser.print_help()
        sys.exit(0)

    mac = args.mac or auto_detect_buds_mac()
    if not mac:
        emit_error("No Galaxy Buds MAC address specified and none auto-detected via BlueZ.", as_json=args.json)

    # Host-level connect / disconnect commands
    if args.command == "connect":
        try:
            BudsClient.connect_device(mac)
            if args.json:
                emit_json({"success": True, "connected": True, "mac_address": mac.upper()})
            else:
                print(f"Connected to device {mac.upper()}.")
            return
        except Exception as e:
            emit_error(f"Failed to connect device {mac}: {e}", as_json=args.json)

    if args.command == "disconnect":
        try:
            BudsClient.disconnect_device(mac)
            if args.json:
                emit_json({"success": True, "disconnected": True, "mac_address": mac.upper()})
            else:
                print(f"Disconnected from device {mac.upper()}.")
            return
        except Exception as e:
            emit_error(f"Failed to disconnect device {mac}: {e}", as_json=args.json)

    bluez_props = get_bluez_device_props(mac)
    is_connected = bool(bluez_props.get("Connected", False)) if bluez_props else False
    dev_name = str(bluez_props.get("Name", "Galaxy Buds")) if bluez_props else "Galaxy Buds"
    uuids = [str(u) for u in bluez_props.get("UUIDs", [])] if bluez_props else []
    model_info = identify_device_from_uuids(uuids, dev_name)

    if args.command in ["info", "device", "device-info"]:
        if not is_connected:
            if args.json:
                emit_json({
                    "success": True,
                    "connected": False,
                    "device": {
                        "name": dev_name,
                        "model": model_info.model_name,
                        "model_code": model_info.model_code,
                        "color": model_info.color or "Standard",
                        "mac_address": mac.upper(),
                        "firmware_prefix": model_info.firmware_prefix,
                        "has_anc": model_info.has_anc,
                        "has_ambient": model_info.has_ambient,
                        "supports_adaptive": model_info.supports_adaptive,
                        "has_blade_lights": model_info.has_blade_lights,
                        "has_voice_detect": model_info.has_voice_detect,
                        "supported_noise_modes": model_info.supported_noise_modes,
                    },
                    "note": "Earbuds are not actively connected in BlueZ. Showing cached Bluetooth metadata.",
                })
            else:
                print("=== Galaxy Buds Device Info (Disconnected) ===")
                print(f"Device Name:       {dev_name}")
                print(f"Model:             {model_info.model_name} ({model_info.model_code})")
                print(f"Color:             {model_info.color or 'Standard'}")
                print(f"MAC Address:       {mac.upper()}")
                print(f"Active Connection: No (Connect via 'gbuds connect' or bluetoothctl)")
                print(f"Hardware ANC:      {'Yes' if model_info.has_anc else 'No'}")
                print(f"Hardware Ambient:  {'Yes' if model_info.has_ambient else 'No'}")
                print(f"Adaptive Mode:     {'Yes' if model_info.supports_adaptive else 'No'}")
                print(f"Blade Lights:      {'Yes' if model_info.has_blade_lights else 'No'}")
                print(f"Voice Detect:      {'Yes' if model_info.has_voice_detect else 'No'}")
                print(f"Noise Modes:       {', '.join(model_info.supported_noise_modes)}")
                print("==============================================")
            return

    client = BudsClient(mac_address=mac, transport_type=args.transport, channel=args.channel)
    try:
        client.connect()
    except Exception as e:
        emit_error(f"Failed to connect to {mac}: {e}", as_json=args.json)

    try:
        active_ch = getattr(client.transport, "channel", None)
        busy_chs = getattr(client.transport, "busy_channels", [])

        if args.command in ["info", "device", "device-info"]:
            info = client.get_device_info(timeout=2.0)
            bat = info.get("battery")
            if args.json:
                emit_json({
                    "success": True,
                    "connected": True,
                    "device": {
                        "name": info["bluetooth_name"],
                        "model": info["model_name"],
                        "model_code": info["model_code"],
                        "color": info["color"],
                        "mac_address": info["mac_address"],
                        "firmware_version": info["firmware_version"],
                        "cradle_serial": info["cradle_serial"],
                        "left_serial": info["left_serial"],
                        "right_serial": info["right_serial"],
                        "has_anc": info["has_anc"],
                        "has_ambient": info["has_ambient"],
                        "supports_adaptive": info["supports_adaptive"],
                        "has_blade_lights": info["has_blade_lights"],
                        "has_voice_detect": info["has_voice_detect"],
                        "supported_noise_modes": info["supported_noise_modes"],
                    },
                    "transport": {
                        "backend": info["transport_type"],
                        "active_channel": info["active_channel"],
                        "busy_channels": info["busy_channels"],
                    },
                    "battery": bat.to_dict() if bat else None,
                })
            else:
                print("=== Galaxy Buds Device Metadata ===")
                print(f"Device Name:       {info['bluetooth_name']}")
                print(f"Model:             {info['model_name']} ({info['model_code']})")
                print(f"Color:             {info['color']}")
                print(f"MAC Address:       {info['mac_address']}")
                print(f"Firmware:          {info['firmware_version'] or 'N/A'}")
                print(f"Cradle S/N:        {info['cradle_serial'] or 'N/A'}")
                print(f"Left Earbud S/N:   {info['left_serial'] or 'N/A'}")
                print(f"Right Earbud S/N:  {info['right_serial'] or 'N/A'}")
                print(f"RFCOMM Channel:    {info['active_channel']}" + (f" (coexisting with {info['busy_channels']})" if info['busy_channels'] else ""))
                print(f"Hardware ANC:      {'Yes' if info['has_anc'] else 'No'}")
                print(f"Hardware Ambient:  {'Yes' if info['has_ambient'] else 'No'}")
                print(f"Adaptive Mode:     {'Yes' if info['supports_adaptive'] else 'No'}")
                print(f"Blade Lights:      {'Yes' if info['has_blade_lights'] else 'No'}")
                print(f"Voice Detect:      {'Yes' if info['has_voice_detect'] else 'No'}")
                if bat:
                    print(f"- Left Earbud:     {bat.left}% ({format_placement(bat.placement_left)})" + (" [Charging]" if bat.left_charging else ""))
                    print(f"- Right Earbud:    {bat.right}% ({format_placement(bat.placement_right)})" + (" [Charging]" if bat.right_charging else ""))
                    if bat.case is not None and bat.case > 0:
                        print(f"- Case:            {bat.case}%" + (" [Charging]" if bat.case_charging else ""))
                    if bat.noise_control_mode is not None:
                        print(f"- Noise Control:   {bat.noise_control_mode.name}")
                    if bat.equalizer_preset is not None:
                        print(f"- Equalizer:       {bat.equalizer_preset.name}")
                    if bat.touchpad_locked is not None:
                        print(f"- Touchpad:        {'Locked' if bat.touchpad_locked else 'Unlocked'}")
                print("========================================")

        elif args.command in ["battery", "status"]:
            status = client.get_battery(timeout=3.0)
            if not status:
                emit_error("Connected, but did not receive battery update within timeout.", as_json=args.json)

            if args.json:
                emit_json({
                    "success": True,
                    "connection": {
                        "active_channel": active_ch,
                        "busy_channels": busy_chs,
                    },
                    "battery": {
                        "left": status.left,
                        "right": status.right,
                        "case": status.case if (status.case is not None and status.case > 0) else None,
                        "left_charging": status.left_charging,
                        "right_charging": status.right_charging,
                        "case_charging": status.case_charging,
                        "is_coupled": status.is_coupled,
                    },
                    "placement": {
                        "left": status.placement_left.name if status.placement_left else None,
                        "right": status.placement_right.name if status.placement_right else None,
                    },
                    "noise_control": status.noise_control_mode.name if status.noise_control_mode else None,
                    "equalizer": status.equalizer_preset.name if status.equalizer_preset else None,
                    "touchpad_locked": status.touchpad_locked,
                })
            else:
                print("=== Galaxy Buds Battery & Placement ===")
                print(f"- Left earbud:     {status.left}% [{format_placement(status.placement_left)}]" + (" [Charging]" if status.left_charging else ""))
                print(f"- Right earbud:    {status.right}% [{format_placement(status.placement_right)}]" + (" [Charging]" if status.right_charging else ""))
                if status.case is not None and status.case > 0:
                    print(f"- Case:            {status.case}%" + (" [Charging]" if status.case_charging else ""))
                else:
                    print("- Case:            N/A (Buds out of case or closed)")
                if status.noise_control_mode is not None:
                    print(f"- Noise Control:   {status.noise_control_mode.name}")
                if status.equalizer_preset is not None:
                    print(f"- Equalizer:       {status.equalizer_preset.name}")
                if status.touchpad_locked is not None:
                    print(f"- Touchpad:        {'Locked' if status.touchpad_locked else 'Unlocked'}")
                if busy_chs:
                    print(f"[Notice] External daemon detected on channel {busy_chs}; active via channel {active_ch}.")

        elif args.command == "anc":
            if args.action != "toggle" and args.action not in model_info.supported_noise_modes:
                modes_str = ", ".join(model_info.supported_noise_modes)
                detail = ""
                if args.action == "ambient" and not model_info.has_ambient:
                    detail = " (open-type earbuds lack passive isolation and do not have Ambient Sound)"
                elif args.action == "adaptive" and not model_info.supports_adaptive:
                    detail = " (Adaptive mode is exclusive to Galaxy Buds3 Pro)"
                emit_error(
                    f"{model_info.model_name} does not support '{args.action}'{detail}. Supported modes: {modes_str}",
                    as_json=args.json
                )

            if args.action == "toggle":
                new_mode = client.toggle_anc(model_info=model_info)
                if args.json:
                    emit_json({
                        "success": True,
                        "action": "toggle",
                        "noise_control": new_mode.name,
                    })
                else:
                    print(f"Noise control toggled to: {new_mode.name}")
            else:
                mode_map = {
                    "on": NoiseControlMode.NOISE_REDUCTION,
                    "off": NoiseControlMode.OFF,
                    "ambient": NoiseControlMode.AMBIENT_SOUND,
                    "adaptive": NoiseControlMode.ADAPTIVE,
                }
                mode = mode_map[args.action]
                try:
                    client.set_noise_control(mode, model_info=model_info)
                except ValueError as err:
                    emit_error(str(err), as_json=args.json)

                if args.json:
                    emit_json({
                        "success": True,
                        "action": args.action,
                        "noise_control": mode.name,
                    })
                else:
                    print(f"Noise control set to: {mode.name}")

        elif args.command in ["eq", "equalizer"]:
            eq_map = {
                "normal": EqualizerPreset.OFF,
                "off": EqualizerPreset.OFF,
                "bass": EqualizerPreset.BASS_BOOST,
                "bass_boost": EqualizerPreset.BASS_BOOST,
                "soft": EqualizerPreset.SOFT,
                "dynamic": EqualizerPreset.DYNAMIC,
                "clear": EqualizerPreset.CLEAR,
                "treble": EqualizerPreset.TREBLE_BOOST,
                "treble_boost": EqualizerPreset.TREBLE_BOOST,
            }
            if args.preset:
                preset = eq_map[args.preset.lower()]
                client.set_equalizer(preset)
                if args.json:
                    emit_json({
                        "success": True,
                        "action": "set",
                        "equalizer": preset.name,
                    })
                else:
                    print(f"Equalizer preset set to: {preset.name}")
            else:
                status = client.get_battery(timeout=1.5)
                current_eq = status.equalizer_preset.name if (status and status.equalizer_preset) else "UNKNOWN"
                if args.json:
                    emit_json({
                        "success": True,
                        "equalizer": current_eq,
                        "available_presets": ["normal", "bass", "soft", "dynamic", "clear", "treble"],
                    })
                else:
                    print(f"Current equalizer preset: {current_eq}")

        elif args.command in ["lights", "blade-lights"]:
            if not model_info.has_blade_lights:
                emit_error(
                    f"{model_info.model_name} does not have Blade Lights hardware (LED light strips are exclusive to Galaxy Buds3 Pro).",
                    as_json=args.json,
                )

            light_map = {
                "off": BladeLightingMode.OFF,
                "steady": BladeLightingMode.STEADY,
                "fade": BladeLightingMode.FADE,
                "blink": BladeLightingMode.BLINK,
            }
            mode = light_map[args.mode.lower()]
            client.set_blade_lights(mode, model_info=model_info)
            if args.json:
                emit_json({
                    "success": True,
                    "blade_lights": mode.name,
                })
            else:
                print(f"Blade lights mode set to: {mode.name}")

        elif args.command in ["find", "ring"]:
            client.find_earbuds(args.target)
            if args.json:
                emit_json({
                    "success": True,
                    "find_target": args.target,
                })
            else:
                if args.target == "stop":
                    print("Earbuds ringing stopped.")
                else:
                    print(f"Ringing earbuds: {args.target}")

        elif args.command == "ambient-volume":
            if not model_info.has_ambient:
                emit_error(
                    f"{model_info.model_name} does not support Ambient Sound (open-type earbud design).",
                    as_json=args.json,
                )
            client.set_ambient_volume(args.level, model_info=model_info)
            if args.json:
                emit_json({
                    "success": True,
                    "ambient_volume": args.level,
                })
            else:
                print(f"Ambient volume set to: {args.level}")

        elif args.command == "voice-detect":
            if not model_info.has_voice_detect:
                emit_error(
                    f"{model_info.model_name} does not support Voice Detect (conversation auto-pause is exclusive to Pro models).",
                    as_json=args.json,
                )
            enable = args.state.lower() == "on"
            client.set_voice_detect(enable, model_info=model_info)
            if args.json:
                emit_json({
                    "success": True,
                    "voice_detect": enable,
                })
            else:
                print(f"Voice detect set to: {'Enabled' if enable else 'Disabled'}")

        elif args.command == "touchpad":
            lock = args.action == "lock"
            client.lock_touchpad(lock)
            if args.json:
                emit_json({
                    "success": True,
                    "action": args.action,
                    "touchpad_locked": lock,
                })
            else:
                print(f"Touchpad {'locked' if lock else 'unlocked'}.")

        elif args.command in ["watch", "listen"]:
            try:
                for status in client.watch(interval=args.interval):
                    if args.json:
                        print(json.dumps(status.to_dict()), flush=True)
                    else:
                        timestamp = time.strftime("%H:%M:%S")
                        l_plac = format_placement(status.placement_left)
                        r_plac = format_placement(status.placement_right)
                        anc_mode = status.noise_control_mode.name if status.noise_control_mode else "N/A"
                        eq_mode = status.equalizer_preset.name if status.equalizer_preset else "N/A"
                        case_str = f"{status.case}%" if status.case is not None else "N/A"
                        print(
                            f"[{timestamp}] L: {status.left}% ({l_plac}) | R: {status.right}% ({r_plac}) | "
                            f"Case: {case_str} | ANC: {anc_mode} | EQ: {eq_mode}",
                            flush=True,
                        )
            except KeyboardInterrupt:
                pass

    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
