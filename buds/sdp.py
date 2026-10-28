"""
Pure-Python Bluetooth SDP (Service Discovery Protocol) client.
Queries the remote device over L2CAP PSM 1 to dynamically resolve RFCOMM channels for SPP UUIDs.
Zero external tools or C-libraries required.
"""

import socket
import struct
import uuid as uuidlib
from typing import Optional, List

SDP_PSM = 1
ATTR_PROTOCOL_DESCRIPTOR_LIST = 0x0004
UUID_RFCOMM = 0x0003

PDU_SEARCH_ATTR_REQUEST = 0x06
PDU_SEARCH_ATTR_RESPONSE = 0x07

# SDP Data element types
T_NIL, T_UINT, T_INT, T_UUID, T_TEXT, T_BOOL, T_SEQ, T_ALT, T_URL = range(9)


def parse_element(buf: bytes, pos: int = 0):
    """Decodes one SDP data element; returns (value, next_pos)."""
    if pos >= len(buf):
        return None, pos
    head = buf[pos]
    kind, size_index = head >> 3, head & 7
    pos += 1
    if kind == T_NIL:
        return None, pos
    if size_index < 5:
        size = (1, 2, 4, 8, 16)[size_index]
    else:
        width = (1, 2, 4)[size_index - 5]
        size = int.from_bytes(buf[pos : pos + width], "big")
        pos += width
    data = buf[pos : pos + size]
    end = pos + size
    if kind in (T_SEQ, T_ALT):
        items, inner = [], 0
        while inner < len(data):
            value, inner = parse_element(data, inner)
            items.append(value)
        return items, end
    if kind == T_UUID:
        return (uuidlib.UUID(bytes=bytes(data)) if size == 16 else int.from_bytes(data, "big")), end
    if kind == T_UINT:
        return int.from_bytes(data, "big"), end
    if kind == T_INT:
        return int.from_bytes(data, "big", signed=True), end
    if kind == T_BOOL:
        return bool(data[0]), end
    return bytes(data), end


def build_request(service_uuid: str, transaction: int = 1, continuation: bytes = b"") -> bytes:
    """Builds a ServiceSearchAttributeRequest PDU for a 128-bit UUID and attribute 0x0004."""
    pattern = b"\x35\x11\x1c" + uuidlib.UUID(service_uuid).bytes
    attributes = b"\x35\x03\x09" + struct.pack(">H", ATTR_PROTOCOL_DESCRIPTOR_LIST)
    params = pattern + struct.pack(">H", 0xFFFF) + attributes + bytes([len(continuation)]) + continuation
    return struct.pack(">BHH", PDU_SEARCH_ATTR_REQUEST, transaction, len(params)) + params


def extract_rfcomm_channel(attribute_lists: bytes) -> Optional[int]:
    """Finds the RFCOMM channel number inside the decoded ProtocolDescriptorList."""
    records, _ = parse_element(attribute_lists)
    for record in records or []:
        for i in range(0, len(record) - 1, 2):
            if record[i] != ATTR_PROTOCOL_DESCRIPTOR_LIST:
                continue
            for layer in record[i + 1]:
                if isinstance(layer, list) and len(layer) >= 2 and layer[0] == UUID_RFCOMM:
                    return int(layer[1])
    return None


def find_rfcomm_channel(address: str, service_uuid: str, timeout: float = 3.0) -> Optional[int]:
    """Queries remote device over SDP for the RFCOMM channel serving service_uuid."""
    if not hasattr(socket, "AF_BLUETOOTH") or not hasattr(socket, "BTPROTO_L2CAP"):
        return None

    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
    sock.settimeout(timeout)
    try:
        sock.connect((address.upper(), SDP_PSM))
        collected, continuation, transaction = b"", b"", 1
        while True:
            req = build_request(service_uuid, transaction, continuation)
            sock.sendall(req)
            resp = sock.recv(1024)
            if len(resp) < 7:
                break
            pdu_id, _trans, _len = struct.unpack(">BHH", resp[:5])
            if pdu_id != PDU_SEARCH_ATTR_RESPONSE:
                break
            count = struct.unpack(">H", resp[5:7])[0]
            collected += resp[7 : 7 + count]
            cont_len = resp[7 + count]
            continuation = resp[8 + count : 8 + count + cont_len]
            if not continuation:
                break
            transaction += 1
        return extract_rfcomm_channel(collected)
    except Exception:
        return None
    finally:
        sock.close()
