"""Command-line interface for gbuds."""

import argparse
import json
import sys
from typing import Optional, Dict, Any

from .protocol import NoiseControlMode, SPP_UUID_NEW, SPP_UUID_STANDARD
from .client import BudsClient
from .models import identify_device_from_uuids


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

        for path, ifaces in objects.items():
            if "org.bluez.Device1" in ifaces:
                props = ifaces["org.bluez.Device1"]
                name = props.get("Name", "")
                uuids = props.get("UUIDs", [])
                if "Buds" in name or SPP_UUID_NEW in uuids or SPP_UUID_STANDARD in uuids:
                    return str(props.get("Address"))
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


def main():
    parser = argparse.ArgumentParser(
        prog="gbuds",
        description="Headless CLI and library for Samsung Galaxy Buds on Linux.",
    )
    parser.add_argument(
        "--mac",
        type=str,
        default=None,
        help="Bluetooth MAC address of the Galaxy Buds. Auto-detected if omitted.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON instead of plain text.",
    )
    parser.add_argument(
        "--transport",
        choices=["direct", "bluez"],
        default="direct",
        help="Transport backend: direct (kernel socket + SDP) or bluez (D-Bus Profile1).",
    )
    parser.add_argument(
        "--channel",
        type=int,
        default=None,
        help="Explicit RFCOMM channel. Auto-discovered via SDP if omitted.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Info / device metadata
    subparsers.add_parser("info", aliases=["device", "device-info"], help="Show hardware metadata, model, color, and firmware.")

    # Battery command
    subparsers.add_parser("battery", aliases=["status"], help="Check battery percentage (left, right, case).")

    # ANC command
    anc_parser = subparsers.add_parser("anc", help="Control noise cancellation and ambient modes.")
    anc_parser.add_argument(
        "action",
        nargs="?",
        default="toggle",
        choices=["on", "off", "ambient", "adaptive", "toggle"],
        help="Action: on (ANC), off (Normal), ambient, adaptive, or toggle.",
    )

    # Touchpad command
    touch_parser = subparsers.add_parser("touchpad", help="Lock or unlock earbuds touchpads.")
    touch_parser.add_argument(
        "action",
        choices=["lock", "unlock"],
        help="Action: lock or unlock.",
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
                        "connected": False,
                        "supports_anc": model_info.has_anc,
                        "supports_adaptive": model_info.supports_adaptive,
                        "firmware_version": None,
                        "cradle_serial": None,
                        "left_serial": None,
                        "right_serial": None,
                    },
                    "battery": None,
                    "noise_control": None,
                    "touchpad_locked": None,
                    "notice": "Device is currently disconnected from Bluetooth",
                })
            else:
                print("========================================")
                print(f"Device:            {dev_name}")
                print(f"Model:             {model_info.model_name} ({model_info.model_code})")
                print(f"Color:             {model_info.color or 'Standard'}")
                print(f"MAC Address:       {mac.upper()}")
                print(f"Bluetooth Link:    Disconnected")
                print(f"Supports ANC:      {'Yes' if model_info.has_anc else 'No'}")
                print(f"Supports Adaptive: {'Yes' if model_info.supports_adaptive else 'No'}")
                print("----------------------------------------")
                print("[Notice] Device is currently disconnected from Bluetooth.")
                print("         Connect device to retrieve live telemetry and firmware.")
                print("========================================")
            return

    client = BudsClient(mac_address=mac, transport_type=args.transport, channel=args.channel)

    try:
        client.connect()
    except Exception as e:
        emit_error(f"Failed to connect to {mac}: {e}", as_json=args.json)

    try:
        if args.command in ["info", "device", "device-info"]:
            info = client.get_device_info(timeout=2.5)
            bat = info["battery"]

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
                        "connected": True,
                        "supports_anc": info["has_anc"],
                        "supports_adaptive": info["supports_adaptive"],
                        "firmware_version": info["firmware_version"],
                        "cradle_serial": info["cradle_serial"],
                        "left_serial": info["left_serial"],
                        "right_serial": info["right_serial"],
                    },
                    "battery": {
                        "left": bat.left if bat else None,
                        "right": bat.right if bat else None,
                        "case": bat.case if (bat and bat.case and bat.case > 0) else None,
                        "left_charging": bat.left_charging if bat else False,
                        "right_charging": bat.right_charging if bat else False,
                        "case_charging": bat.case_charging if bat else False,
                        "is_coupled": bat.is_coupled if bat else True,
                    } if bat else None,
                    "noise_control": bat.noise_control_mode.name if (bat and bat.noise_control_mode) else None,
                    "touchpad_locked": bat.touchpad_locked if bat else None,
                })
            else:
                print("========================================")
                print(f"Device:            {info['bluetooth_name']}")
                print(f"Model:             {info['model_name']} ({info['model_code']})")
                print(f"Color:             {info['color']}")
                print(f"MAC Address:       {info['mac_address']}")
                print(f"Bluetooth Link:    Connected")
                print(f"Supports ANC:      {'Yes' if info['has_anc'] else 'No'}")
                print(f"Supports Adaptive: {'Yes' if info['supports_adaptive'] else 'No'}")
                if info["firmware_version"]:
                    print(f"Firmware Version:  {info['firmware_version']}")
                if info["cradle_serial"]:
                    print(f"Cradle Serial:     {info['cradle_serial']}")
                if info["left_serial"]:
                    print(f"Left Serial:       {info['left_serial']}")
                if info["right_serial"]:
                    print(f"Right Serial:      {info['right_serial']}")
                print("----------------------------------------")
                if bat:
                    print(f"- Battery Left:    {bat.left}%" + (" [Charging]" if bat.left_charging else ""))
                    print(f"- Battery Right:   {bat.right}%" + (" [Charging]" if bat.right_charging else ""))
                    if bat.case is not None and bat.case > 0:
                        print(f"- Battery Case:    {bat.case}%" + (" [Charging]" if bat.case_charging else ""))
                    if bat.noise_control_mode is not None:
                        print(f"- Noise Control:   {bat.noise_control_mode.name}")
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
                    "battery": {
                        "left": status.left,
                        "right": status.right,
                        "case": status.case if (status.case is not None and status.case > 0) else None,
                        "left_charging": status.left_charging,
                        "right_charging": status.right_charging,
                        "case_charging": status.case_charging,
                        "is_coupled": status.is_coupled,
                    },
                    "noise_control": status.noise_control_mode.name if status.noise_control_mode else None,
                    "touchpad_locked": status.touchpad_locked,
                })
            else:
                print("=== Galaxy Buds Battery Status ===")
                print(f"- Left earbud:     {status.left}%" + (" [Charging]" if status.left_charging else ""))
                print(f"- Right earbud:    {status.right}%" + (" [Charging]" if status.right_charging else ""))
                if status.case is not None and status.case > 0:
                    print(f"- Case:            {status.case}%" + (" [Charging]" if status.case_charging else ""))
                else:
                    print("- Case:            N/A (Buds out of case or closed)")
                if status.noise_control_mode is not None:
                    print(f"- Noise Control:   {status.noise_control_mode.name}")
                if status.touchpad_locked is not None:
                    print(f"- Touchpad:        {'Locked' if status.touchpad_locked else 'Unlocked'}")

        elif args.command == "anc":
            if args.action == "toggle":
                new_mode = client.toggle_anc()
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
                client.set_noise_control(mode)
                if args.json:
                    emit_json({
                        "success": True,
                        "action": args.action,
                        "noise_control": mode.name,
                    })
                else:
                    print(f"Noise control set to: {mode.name}")

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

    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
