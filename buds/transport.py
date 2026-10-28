"""
Linux RFCOMM Transport implementations for Galaxy Buds.

Provides two transport methods:
1. DirectRfcommTransport: Direct kernel socket via socket(AF_BLUETOOTH, SOCK_STREAM, BTPROTO_RFCOMM).
   Uses dynamic pure-Python SDP queries over L2CAP PSM 1 to resolve RFCOMM channels automatically,
   falling back across available Samsung SPP services if one is busy.
2. BluezProfileTransport: Uses BlueZ D-Bus Profile1 API (same mechanism as GalaxyBudsClient.Platform.Linux).
"""

import os
import socket
import threading
import time
from abc import ABC, abstractmethod
from typing import Optional, List
from .protocol import SPP_UUID_NEW, SPP_UUID_STANDARD, SPP_UUID_LEGACY
from .sdp import find_rfcomm_channel


class BaseTransport(ABC):
    """Abstract transport for reading and writing RFCOMM frames."""

    @abstractmethod
    def connect(self) -> None:
        """Connect to the earbuds."""
        pass

    @abstractmethod
    def send(self, data: bytes) -> None:
        """Send raw bytes over the RFCOMM channel."""
        pass

    @abstractmethod
    def receive(self, timeout: float = 3.0) -> bytes:
        """Receive raw bytes from the RFCOMM channel."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close connection."""
        pass


class DirectRfcommTransport(BaseTransport):
    """
    Direct RFCOMM connection using Linux kernel socket:
    socket(AF_BLUETOOTH, SOCK_STREAM, BTPROTO_RFCOMM).

    Automatically discovers RFCOMM channels via SDP (e.g. SppNew, SppStandard)
    and tries alternative channels if a channel is already occupied.
    """

    def __init__(self, mac_address: str, channel: Optional[int] = None):
        self.mac_address = mac_address.upper()
        self.explicit_channel = channel
        self.channel: Optional[int] = None
        self.sock: Optional[socket.socket] = None

    def connect(self) -> None:
        if not hasattr(socket, "AF_BLUETOOTH") or not hasattr(socket, "BTPROTO_RFCOMM"):
            raise RuntimeError("Linux Bluetooth RFCOMM sockets are not supported on this kernel/system.")

        candidate_channels: List[int] = []

        if self.explicit_channel is not None:
            candidate_channels.append(self.explicit_channel)
        else:
            # Query SDP for Samsung SPP UUIDs
            for uuid in [SPP_UUID_NEW, SPP_UUID_STANDARD, SPP_UUID_LEGACY]:
                try:
                    ch = find_rfcomm_channel(self.mac_address, uuid, timeout=2.5)
                    if ch and ch not in candidate_channels:
                        candidate_channels.append(ch)
                except Exception:
                    pass

            # Standard fallbacks if SDP query was blocked
            for fb in [27, 20, 1, 2]:
                if fb not in candidate_channels:
                    candidate_channels.append(fb)

        last_err: Optional[Exception] = None

        for ch in candidate_channels:
            s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
            s.settimeout(4.0)
            try:
                s.connect((self.mac_address, ch))
                s.setblocking(False)
                self.sock = s
                self.channel = ch
                return
            except OSError as err:
                s.close()
                last_err = err
                # If resource is busy (e.g. another daemon is holding this channel), try next channel
                continue

        error_msg = f"Failed to connect to {self.mac_address} on channels {candidate_channels}: {last_err}"
        if last_err and getattr(last_err, "errno", None) in (16, 111):
            error_msg += " (Device or resource busy. Check if another process like orbit_anc or GalaxyBudsClient is holding the connection)."
        raise ConnectionError(error_msg)

    def send(self, data: bytes) -> None:
        if not self.sock:
            raise RuntimeError("Socket is not connected.")
        self.sock.sendall(data)

    def receive(self, timeout: float = 3.0) -> bytes:
        if not self.sock:
            raise RuntimeError("Socket is not connected.")

        self.sock.settimeout(timeout)
        try:
            return self.sock.recv(1024)
        except (socket.timeout, BlockingIOError):
            return b""

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None


class BluezProfileTransport(BaseTransport):
    """
    BlueZ D-Bus Profile1 transport (same pattern as GalaxyBudsClient.Platform.Linux).
    Registers an org.bluez.Profile1 client, calls ConnectProfile on the Device,
    and takes the connected Unix file descriptor.
    """

    PROFILE_PATH = "/org/bluez/galaxybudsclient/profile"

    def __init__(self, mac_address: str, service_uuid: str = SPP_UUID_NEW):
        self.mac_address = mac_address.upper()
        self.service_uuid = service_uuid
        self.sock: Optional[socket.socket] = None
        self._connected_event = threading.Event()
        self._fd: Optional[int] = None
        self._bus = None
        self._profile = None
        self._mainloop = None
        self._thread = None

    def connect(self) -> None:
        try:
            import dbus
            import dbus.service
            import dbus.mainloop.glib
            from gi.repository import GLib
        except ImportError as e:
            raise RuntimeError(f"dbus / glib not available for BlueZ profile: {e}")

        # Ensure GLib mainloop is set as default before any bus calls
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self._bus = dbus.SystemBus()

        class BluezProfile(dbus.service.Object):
            def __init__(profile_self, bus, path, on_conn):
                super().__init__(bus, path)
                profile_self.on_conn = on_conn

            @dbus.service.method("org.bluez.Profile1", in_signature="", out_signature="")
            def Release(profile_self):
                pass

            @dbus.service.method("org.bluez.Profile1", in_signature="oha{sv}", out_signature="")
            def NewConnection(profile_self, device_path, fd, options):
                profile_self.on_conn(fd.take())

            @dbus.service.method("org.bluez.Profile1", in_signature="o", out_signature="")
            def RequestDisconnection(profile_self, device_path):
                pass

        def on_connection(fd_int: int):
            self._fd = fd_int
            self.sock = socket.fromfd(fd_int, socket.AF_BLUETOOTH, socket.SOCK_STREAM)
            self.sock.setblocking(False)
            self._connected_event.set()

        self._profile = BluezProfile(self._bus, self.PROFILE_PATH, on_connection)

        self._mainloop = GLib.MainLoop()
        self._thread = threading.Thread(target=self._mainloop.run, daemon=True)
        self._thread.start()

        profile_mgr = dbus.Interface(
            self._bus.get_object("org.bluez", "/org/bluez"),
            "org.bluez.ProfileManager1",
        )
        opts = {
            "Role": "client",
            "Name": "GalaxyBudsHeadless",
        }

        try:
            profile_mgr.UnregisterProfile(self.PROFILE_PATH)
        except Exception:
            pass

        try:
            profile_mgr.RegisterProfile(self.PROFILE_PATH, self.service_uuid, opts)
        except dbus.DBusException as e:
            if "AlreadyExists" not in str(e):
                raise

        bluez_root = dbus.Interface(self._bus.get_object("org.bluez", "/"), "org.freedesktop.DBus.ObjectManager")
        objects = bluez_root.GetManagedObjects()
        dev_obj_path = None
        for path, ifaces in objects.items():
            if "org.bluez.Device1" in ifaces:
                props = ifaces["org.bluez.Device1"]
                if props.get("Address", "").upper() == self.mac_address:
                    dev_obj_path = path
                    break

        if not dev_obj_path:
            raise RuntimeError(f"Device {self.mac_address} not found in BlueZ. Pair it first via bluetoothctl.")

        dev = dbus.Interface(self._bus.get_object("org.bluez", dev_obj_path), "org.bluez.Device1")

        try:
            dev.ConnectProfile(self.service_uuid)
        except Exception as e:
            # Fallback to standard SPP UUID
            if self.service_uuid == SPP_UUID_NEW:
                try:
                    self.service_uuid = SPP_UUID_STANDARD
                    profile_mgr.RegisterProfile(self.PROFILE_PATH, self.service_uuid, opts)
                    dev.ConnectProfile(self.service_uuid)
                except Exception as inner:
                    raise RuntimeError(f"ConnectProfile failed: {inner}")
            else:
                raise RuntimeError(f"ConnectProfile failed: {e}")

        if not self._connected_event.wait(timeout=6.0):
            raise TimeoutError("Timed out waiting for BlueZ NewConnection callback.")

    def send(self, data: bytes) -> None:
        if not self.sock:
            raise RuntimeError("Socket is not connected.")
        self.sock.sendall(data)

    def receive(self, timeout: float = 3.0) -> bytes:
        if not self.sock:
            raise RuntimeError("Socket is not connected.")
        self.sock.settimeout(timeout)
        try:
            return self.sock.recv(1024)
        except (socket.timeout, BlockingIOError):
            return b""

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        if self._mainloop and self._mainloop.is_running():
            self._mainloop.quit()
