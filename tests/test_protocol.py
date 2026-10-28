"""
Unit tests for Galaxy Buds protocol serialization, CRC16, and decoders.
"""

import unittest
from gbuds.protocol import (
    SOM,
    EOM,
    MsgIds,
    MsgTypes,
    NoiseControlMode,
    crc16_ccitt,
    build_packet,
    parse_packet,
    decode_battery_status,
    encode_noise_control,
    encode_lock_touchpad,
    encode_manager_info,
)


class TestBudsProtocol(unittest.TestCase):

    def test_crc16_and_packet_with_recorded_fixture(self):
        # Buds2_rev10.bin raw fixture:
        # fd 28 10 61 0a 03 64 64 01 01 11 33 00 03 3f 22 01 00 3c 01 3c 01 02 00 03 66 00 01 00 10 00 00 00 00 11 02 01 01 00 00 00 be a3 dd
        import os
        candidates = [
            "GalaxyBudsClient/GalaxyBudsClient.Tests/TestData/ExtendedStatusUpdate/Buds2_rev10.bin",
            "../GalaxyBudsClient/GalaxyBudsClient.Tests/TestData/ExtendedStatusUpdate/Buds2_rev10.bin",
        ]
        raw = None
        for p in candidates:
            if os.path.exists(p):
                with open(p, "rb") as f:
                    raw = f.read()
                break
        if raw is None:
            # Fallback to embedded fixture bytes
            raw = bytes.fromhex(
                "fd2810610a0364640101113300033f2201003c013c0102000366000100100000000011020101000000bea3dd"
            )

        msg = parse_packet(raw)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.msg_id, MsgIds.EXTENDED_STATUS_UPDATED)
        self.assertEqual(msg.msg_type, MsgTypes.RESPONSE)

        status = decode_battery_status(msg)
        self.assertIsNotNone(status)
        self.assertEqual(status.left, 100)
        self.assertEqual(status.right, 100)
        self.assertEqual(status.case, 51)
        self.assertTrue(status.is_coupled)
        self.assertEqual(status.noise_control_mode, NoiseControlMode.NOISE_REDUCTION)

    def test_packet_build_and_parse(self):
        payload = bytes([NoiseControlMode.AMBIENT_SOUND.value])
        pkt = build_packet(MsgIds.NOISE_CONTROLS, payload)

        self.assertEqual(pkt[0], SOM)
        self.assertEqual(pkt[-1], EOM)

        msg = parse_packet(pkt)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.msg_id, MsgIds.NOISE_CONTROLS)
        self.assertEqual(msg.payload, payload)
        self.assertEqual(msg.msg_type, MsgTypes.REQUEST)

    def test_manager_info_packet(self):
        pkt = encode_manager_info()
        msg = parse_packet(pkt)
        self.assertIsNotNone(msg)
        self.assertEqual(msg.msg_id, MsgIds.MANAGER_INFO)
        self.assertEqual(msg.payload, bytes([1, 1, 34]))

    def test_lock_touchpad_packet(self):
        pkt_lock = encode_lock_touchpad(True)
        msg_lock = parse_packet(pkt_lock)
        self.assertIsNotNone(msg_lock)
        self.assertEqual(msg_lock.msg_id, MsgIds.LOCK_TOUCHPAD)
        self.assertEqual(msg_lock.payload, bytes([0] * 7))

        pkt_unlock = encode_lock_touchpad(False)
        msg_unlock = parse_packet(pkt_unlock)
        self.assertIsNotNone(msg_unlock)
        self.assertEqual(msg_unlock.msg_id, MsgIds.LOCK_TOUCHPAD)
        self.assertEqual(msg_unlock.payload, bytes([1] * 7))


if __name__ == "__main__":
    unittest.main()
