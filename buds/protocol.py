"""
Galaxy Buds RFCOMM Protocol implementation.
Based on Samsung Galaxy Buds RFCOMM reverse engineering in GalaxyBudsClient.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Tuple, List

# Start and End of Message delimiters
SOM = 0xFD          # Modern models: Buds+, Live, Pro, Buds2, Buds2 Pro, Buds FE, Buds3, Buds3 Pro
EOM = 0xDD          # Modern models
LEGACY_SOM = 0xFE   # Buds 1st gen
LEGACY_EOM = 0xEE   # Buds 1st gen
SMEP_SOM = 0xFC     # Alternative mode
SMEP_EOM = 0xCC

# Service UUIDs
SPP_UUID_NEW = "2e73a4ad-332d-41fc-90e2-16bef06523f2"       # Buds 2, Buds 2 Pro, Buds FE, Buds 3, Buds 3 Pro
SPP_UUID_STANDARD = "00001101-0000-1000-8000-00805f9b34fb"  # Standard SPP: Buds+, Buds Live, Buds Pro
SPP_UUID_LEGACY = "00001102-0000-1000-8000-00805f9b34fd"    # Buds 1st gen


class MsgIds(IntEnum):
    STATUS_UPDATED = 96               # 0x60
    EXTENDED_STATUS_UPDATED = 97      # 0x61
    NOISE_CONTROLS = 120              # 0x78
    SET_AMBIENT_MODE = 128            # 0x80 (Buds / Buds+)
    EQUALIZER = 134                   # 0x86
    MANAGER_INFO = 136                # 0x88
    LOCK_TOUCHPAD = 144               # 0x90
    SET_TOUCHPAD_OPTION = 146         # 0x92
    SET_NOISE_REDUCTION = 152         # 0x98 (Buds Live)
    PAIRING_MODE = 114                # 0x72
    FIND_MY_EARBUDS_START = 160       # 0xA0
    FIND_MY_EARBUDS_STOP = 161        # 0xA1


class MsgTypes(IntEnum):
    REQUEST = 0
    RESPONSE = 1


class NoiseControlMode(IntEnum):
    OFF = 0              # Normal (ANC and Ambient disabled)
    NOISE_REDUCTION = 1  # ANC active
    AMBIENT_SOUND = 2    # Ambient Sound active
    ADAPTIVE = 3         # Adaptive (Buds 3 / Buds 3 Pro)


# CRC-16/CCITT lookup table (polynomial 0x1021, init 0x0000)
CRC16_TABLE = [
    0, 4129, 8258, 12387, 16516, 20645, 24774, 28903, 33032, 37161, 41290,
    45419, 49548, 53677, 57806, 61935, 4657, 528, 12915, 8786, 21173, 17044, 29431, 25302,
    37689, 33560, 45947, 41818, 54205, 50076, 62463, 58334, 9314, 13379, 1056, 5121, 25830,
    29895, 17572, 21637, 42346, 46411, 34088, 38153, 58862, 62927, 50604, 54669, 13907,
    9842, 5649, 1584, 30423, 26358, 22165, 18100, 46939, 42874, 38681, 34616, 63455, 59390,
    55197, 51132, 18628, 22757, 26758, 30887, 2112, 6241, 10242, 14371, 51660, 55789,
    59790, 63919, 35144, 39273, 43274, 47403, 23285, 19156, 31415, 27286, 6769, 2640,
    14899, 10770, 56317, 52188, 64447, 60318, 39801, 35672, 47931, 43802, 27814, 31879,
    19684, 23749, 11298, 15363, 3168, 7233, 60846, 64911, 52716, 56781, 44330, 48395,
    36200, 40265, 32407, 28342, 24277, 20212, 15891, 11826, 7761, 3696, 65439, 61374,
    57309, 53244, 48923, 44858, 40793, 36728, 37256, 33193, 45514, 41451, 53516, 49453,
    61774, 57711, 4224, 161, 12482, 8419, 20484, 16421, 28742, 24679, 33721, 37784, 41979,
    46042, 49981, 54044, 58239, 62302, 689, 4752, 8947, 13010, 16949, 21012, 25207, 29270,
    46570, 42443, 38312, 34185, 62830, 58703, 54572, 50445, 13538, 9411, 5280, 1153, 29798,
    25671, 21540, 17413, 42971, 47098, 34713, 38840, 59231, 63358, 50973, 55100, 9939,
    14066, 1681, 5808, 26199, 30326, 17941, 22068, 55628, 51565, 63758, 59695, 39368,
    35305, 47498, 43435, 22596, 18533, 30726, 26663, 6336, 2273, 14466, 10403, 52093,
    56156, 60223, 64286, 35833, 39896, 43963, 48026, 19061, 23124, 27191, 31254, 2801,
    6864, 10931, 14994, 64814, 60687, 56684, 52557, 48554, 44427, 40424, 36297, 31782,
    27655, 23652, 19525, 15522, 11395, 7392, 3265, 61215, 65342, 53085, 57212, 44955,
    49082, 36825, 40952, 28183, 32310, 20053, 24180, 11923, 16050, 3793, 7920
]


def crc16_ccitt(data: bytes) -> int:
    """Calculates CRC16-CCITT checksum over bytes."""
    crc = 0
    for b in data:
        crc = (CRC16_TABLE[((crc >> 8) ^ b) & 0xFF] ^ (crc << 8)) & 0xFFFF
    return crc


@dataclass
class SppMessage:
    msg_id: int
    payload: bytes = b""
    msg_type: MsgTypes = MsgTypes.REQUEST
    is_fragment: bool = False

    @property
    def size(self) -> int:
        """Size field in packet: 1 (msg_id) + len(payload) + 2 (crc16)."""
        return 1 + len(self.payload) + 2


@dataclass
class BatteryStatus:
    left: int           # 0-100%
    right: int          # 0-100%
    case: Optional[int] # 0-100% (or None if unsupported/not in case)
    left_charging: bool = False
    right_charging: bool = False
    case_charging: bool = False
    is_coupled: bool = True
    noise_control_mode: Optional[NoiseControlMode] = None
    touchpad_locked: Optional[bool] = None


def build_packet(
    msg_id: int,
    payload: bytes = b"",
    msg_type: MsgTypes = MsgTypes.REQUEST,
    som: int = SOM,
    eom: int = EOM,
) -> bytes:
    """
    Builds a fully formatted RFCOMM packet:
    [SOF (1B)][Header UInt16 (2B)][MsgId (1B)][Payload (NB)][CRC16 Little-Endian (2B)][EOF (1B)]
    """
    body_size = 1 + len(payload) + 2  # MsgId(1) + Payload(N) + CRC(2)
    
    # Header: 10-bit size | (0x1000 if response)
    header_val = body_size & 0x03FF
    if msg_type == MsgTypes.RESPONSE:
        header_val |= 0x1000

    header_bytes = header_val.to_bytes(2, "little")
    
    # CRC calculated over [MsgId] + Payload
    crc_input = bytes([msg_id]) + payload
    crc_val = crc16_ccitt(crc_input)
    crc_bytes = crc_val.to_bytes(2, "little")

    return bytes([som]) + header_bytes + bytes([msg_id]) + payload + crc_bytes + bytes([eom])


def parse_packet(raw: bytes, som: int = SOM, eom: int = EOM) -> Optional[SppMessage]:
    """
    Parses a single packet from bytes. Returns None if invalid or incomplete.
    """
    if len(raw) < 7:  # SOM(1) + Header(2) + MsgId(1) + CRC(2) + EOM(1) = 7
        return None

    if raw[0] != som or raw[-1] != eom:
        return None

    header = int.from_bytes(raw[1:3], "little")
    size = header & 0x03FF
    is_fragment = bool(header & 0x2000)
    msg_type = MsgTypes.RESPONSE if (header & 0x1000) else MsgTypes.REQUEST

    if len(raw) != 3 + size + 1:  # SOM(1) + Header(2) + size + EOM(1)
        return None

    msg_id = raw[3]
    payload_size = size - 3
    payload = raw[4 : 4 + payload_size]
    received_crc = int.from_bytes(raw[4 + payload_size : 4 + payload_size + 2], "little")

    # Validate CRC
    crc_input = bytes([msg_id]) + payload
    calc_crc = crc16_ccitt(crc_input)
    if calc_crc != received_crc:
        return None

    return SppMessage(
        msg_id=msg_id,
        payload=payload,
        msg_type=msg_type,
        is_fragment=is_fragment,
    )


def decode_battery_status(msg: SppMessage) -> Optional[BatteryStatus]:
    """
    Decodes EXTENDED_STATUS_UPDATED (0x61) or STATUS_UPDATED (0x60).
    """
    if msg.msg_id == MsgIds.EXTENDED_STATUS_UPDATED:
        p = msg.payload
        if len(p) < 8:
            return None
        
        # Byte 0: Revision, 1: EarType, 2: BatL, 3: BatR, 4: Coupled, 5: MainConn, 6: Placement, 7: BatCase
        bat_l = p[2]
        bat_r = p[3]
        is_coupled = bool(p[4])
        bat_case = p[7] if len(p) > 7 and p[7] <= 100 else None

        # Noise control mode & touchpad lock (if available at byte 10/12)
        touchpad_locked = None
        nc_mode = None
        if len(p) > 10:
            touchpad_locked = bool(p[10] & 0x80) if (p[10] & 0x80) else bool(p[10])
        if len(p) > 12:
            try:
                nc_mode = NoiseControlMode(p[12])
            except ValueError:
                nc_mode = None

        return BatteryStatus(
            left=bat_l,
            right=bat_r,
            case=bat_case,
            is_coupled=is_coupled,
            noise_control_mode=nc_mode,
            touchpad_locked=touchpad_locked,
        )

    elif msg.msg_id == MsgIds.STATUS_UPDATED:
        p = msg.payload
        if len(p) < 7:
            return None
        bat_l = p[1]
        bat_r = p[2]
        bat_case = p[6] if len(p) > 6 and p[6] <= 100 else None
        
        l_charging = False
        r_charging = False
        case_charging = False
        if len(p) > 7:
            c = p[7]
            l_charging = bool(c & 16)
            r_charging = bool(c & 4)
            case_charging = bool(c & 1)

        return BatteryStatus(
            left=bat_l,
            right=bat_r,
            case=bat_case,
            left_charging=l_charging,
            right_charging=r_charging,
            case_charging=case_charging,
        )

    return None


def encode_noise_control(mode: NoiseControlMode) -> bytes:
    """Builds packet for setting noise control mode (MsgId 120 / 0x78)."""
    return build_packet(MsgIds.NOISE_CONTROLS, bytes([mode.value]))


def encode_lock_touchpad(lock: bool) -> bytes:
    """Builds packet for locking/unlocking touchpad (MsgId 144 / 0x90)."""
    # In modern Buds2/Buds3, AdvancedTouchLock uses 7 bytes:
    # [not_lock_all, tap, double, triple, hold, double_call, hold_call]
    # For full lock: [0, 0, 0, 0, 0, 0, 0]. For full unlock: [1, 1, 1, 1, 1, 1, 1]
    val = 0 if lock else 1
    advanced_payload = bytes([val] * 7)
    return build_packet(MsgIds.LOCK_TOUCHPAD, advanced_payload)


def encode_manager_info() -> bytes:
    """
    Builds MANAGER_INFO packet (MsgId 136 / 0x88).
    Samsung device = 1, Android SDK = 34.
    """
    return build_packet(MsgIds.MANAGER_INFO, bytes([1, 1, 34]))
