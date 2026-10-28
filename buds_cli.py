#!/usr/bin/env python3
"""
Galaxy Buds Headless CLI Tool
Ultra-lightweight Linux CLI and daemon tool for controlling Samsung Galaxy Buds.
No X11, Wayland, or GUI frameworks required.
"""

import argparse
import sys
from typing import Optional, Dict, Any
from buds.protocol import NoiseControlMode, SPP_UUID_NEW, SPP_UUID_STANDARD
from buds.client import BudsClient
from buds.models import identify_device_from_uuids


def get_bluez_device_props(mac: str) -> Optional[Dict[str, Any]]:
    """Reads device properties directly from BlueZ D-Bus without connecting RFCOMM."""
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
    """Attempts to auto-detect paired Galaxy Buds MAC address via BlueZ D-Bus."""
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


def main():
    parser = argparse.ArgumentParser(
        description="Galaxy Buds Headless CLI - Control Samsung Galaxy Buds without GUI."
    )
    parser.add_argument(
        "--mac",
        type=str,
        default=None,
        help="Bluetooth MAC address of the Galaxy Buds (e.g. 24:24:B7:DD:38:90). Auto-detected if omitted.",
    )
    parser.add_argument(
        "--transport",
        choices=["direct", "bluez"],
        default="direct",
        help="Transport backend: 'direct' (kernel socket + dynamic SDP resolution, recommended) or 'bluez' (D-Bus Profile1).",
    )
    parser.add_argument(
        "--channel",
        type=int,
        default=None,
        help="Explicit RFCOMM channel (e.g. 20 or 27). Omit to auto-discover via SDP.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Info / Device info
    subparsers.add_parser("info", aliases=["device", "device-info"], help="Show detailed device metadata, model, color, and firmware.")

    # Battery command
    subparsers.add_parser("battery", aliases=["status"], help="Check battery percentage (Left, Right, Case).")

    # ANC command
    anc_parser = subparsers.add_parser("anc", help="Control Active Noise Cancellation / Ambient mode.")
    anc_parser.add_argument(
        "action",
        nargs="?",
        default="toggle",
        choices=["on", "off", "ambient", "adaptive", "toggle"],
        help="Action: on (ANC), off (Normal), ambient, adaptive, or toggle (default).",
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
        parser.print_help()
        sys.exit(0)

    mac = args.mac or auto_detect_buds_mac()
    if not mac:
        print("Error: No Galaxy Buds MAC address specified and none auto-detected via BlueZ.", file=sys.stderr)
        print("Please provide --mac XX:XX:XX:XX:XX:XX or pair your device first via bluetoothctl.", file=sys.stderr)
        sys.exit(1)

    # Handle info command even if the buds are currently disconnected
    bluez_props = get_bluez_device_props(mac)
    is_connected = bool(bluez_props.get("Connected", False)) if bluez_props else False

    if args.command in ["info", "device", "device-info"]:
        dev_name = str(bluez_props.get("Name", "Galaxy Buds")) if bluez_props else "Galaxy Buds"
        uuids = [str(u) for u in bluez_props.get("UUIDs", [])] if bluez_props else []
        model_info = identify_device_from_uuids(uuids, dev_name)

        print("========================================")
        print(f"  Device:           {dev_name}")
        print(f"  Model:            {model_info.model_name} ({model_info.model_code})")
        print(f"  Color:            {model_info.color or 'Standard'}")
        print(f"  MAC Address:      {mac.upper()}")
        print(f"  Bluetooth Link:   {'Connected' if is_connected else 'Disconnected'}")
        print(f"  Supports ANC:     {'Yes' if model_info.has_anc else 'No'}")
        print(f"  Supports Adaptive:{'Yes' if model_info.supports_adaptive else 'No'}")

        if not is_connected:
            print("----------------------------------------")
            print("  [Notice] Device is currently disconnected from Bluetooth.")
            print("           Connect them to fetch live battery & firmware versions.")
            print("========================================")
            return

    client = BudsClient(mac_address=mac, transport_type=args.transport, channel=args.channel)

    try:
        client.connect()
    except Exception as e:
        print(f"Error connecting to {mac}: {e}", file=sys.stderr)
        if not is_connected:
            print("Hint: Earbuds are disconnected from Bluetooth. Open the case or connect via bluetoothctl.", file=sys.stderr)
        sys.exit(1)

    try:
        if args.command in ["info", "device", "device-info"]:
            info = client.get_device_info(timeout=2.5)
            if info["firmware_version"]:
                print(f"  Firmware Version: {info['firmware_version']}")
            if info["cradle_serial"]:
                print(f"  Cradle Serial:    {info['cradle_serial']}")
            if info["left_serial"]:
                print(f"  Left Serial:      {info['left_serial']}")
            if info["right_serial"]:
                print(f"  Right Serial:     {info['right_serial']}")
            print("----------------------------------------")
            bat = info["battery"]
            if bat:
                print(f"  • Battery Left:   {bat.left}%" + (" [Charging]" if bat.left_charging else ""))
                print(f"  • Battery Right:  {bat.right}%" + (" [Charging]" if bat.right_charging else ""))
                if bat.case is not None and bat.case > 0:
                    print(f"  • Battery Case:   {bat.case}%" + (" [Charging]" if bat.case_charging else ""))
                if bat.noise_control_mode is not None:
                    print(f"  • Noise Control:  {bat.noise_control_mode.name}")
                if bat.touchpad_locked is not None:
                    print(f"  • Touchpad:       {'Locked' if bat.touchpad_locked else 'Unlocked'}")
            print("========================================")

        elif args.command in ["battery", "status"]:
            status = client.get_battery(timeout=3.0)
            if not status:
                print("Connected, but did not receive battery update within timeout.", file=sys.stderr)
                sys.exit(1)

            print("=== Galaxy Buds Battery Status ===")
            print(f"  • Left earbud:  {status.left}%" + (" [Charging]" if status.left_charging else ""))
            print(f"  • Right earbud: {status.right}%" + (" [Charging]" if status.right_charging else ""))
            if status.case is not None and status.case > 0:
                print(f"  • Case:         {status.case}%" + (" [Charging]" if status.case_charging else ""))
            else:
                print("  • Case:         N/A (Buds out of case or closed)")
            if status.noise_control_mode is not None:
                print(f"  • Noise Control: {status.noise_control_mode.name}")
            if status.touchpad_locked is not None:
                print(f"  • Touchpad:      {'Locked' if status.touchpad_locked else 'Unlocked'}")

        elif args.command == "anc":
            if args.action == "toggle":
                new_mode = client.toggle_anc()
                print(f"ANC toggled -> {new_mode.name}")
            else:
                mode_map = {
                    "on": NoiseControlMode.NOISE_REDUCTION,
                    "off": NoiseControlMode.OFF,
                    "ambient": NoiseControlMode.AMBIENT_SOUND,
                    "adaptive": NoiseControlMode.ADAPTIVE,
                }
                mode = mode_map[args.action]
                client.set_noise_control(mode)
                print(f"Noise control set to: {mode.name}")

        elif args.command == "touchpad":
            lock = args.action == "lock"
            client.lock_touchpad(lock)
            print(f"Touchpad {'locked' if lock else 'unlocked'}.")

    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
