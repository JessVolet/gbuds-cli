"""
Unit tests for Galaxy Buds protocol serialization, CRC16, and decoders.
"""

import unittest
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch
import json
import sys
from gbuds.cli import main, _select_buds_mac, _watch_status_dict, auto_detect_buds_mac
from gbuds.client import BudsClient
from gbuds.models import DEVICE_ID_PREFIX, build_model_info, identify_device_from_uuids
from gbuds.sdp import parse_element
from gbuds.protocol import (
    SOM,
    EOM,
    MsgIds,
    MsgTypes,
    NoiseControlMode,
    EqualizerPreset,
    BladeLightingMode,
    PlacementState,
    BatteryStatus,
    crc16_ccitt,
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
)


class TestBudsProtocol(unittest.TestCase):

    def test_sdp_parser_rejects_truncated_and_invalid_remote_data(self):
        malformed_elements = (
            b"",                 # missing header
            b"\x25\x04\x01",   # truncated variable-width payload
            b"\x18\x01",       # UUID with an invalid size
            b"\x29",           # boolean with an invalid size
            b"\x35\x01",       # sequence ending before its nested element
        )
        for element in malformed_elements:
            with self.subTest(element=element), self.assertRaises(ValueError):
                parse_element(element)

    def test_watch_json_normalizes_unavailable_zero_case_like_battery(self):
        status = BatteryStatus(left=96, right=100, case=0)
        self.assertIsNone(_watch_status_dict(status)["case"])
        status.case = 46
        self.assertEqual(_watch_status_dict(status)["case"], 46)

    def test_cli_json_option_works_before_and_after_subcommand(self):
        for argv in (("gbuds", "--json", "battery"), ("gbuds", "battery", "--json")):
            with self.subTest(argv=argv):
                output = StringIO()
                with patch.object(sys, "argv", list(argv)), \
                     patch("gbuds.cli.auto_detect_buds_mac", return_value=None), \
                     redirect_stdout(output):
                    with self.assertRaises(SystemExit) as exit_result:
                        main()
                self.assertEqual(exit_result.exception.code, 1)
                self.assertFalse(json.loads(output.getvalue())["success"])

    def test_device_selection_is_deterministic_and_requires_mac_for_ambiguity(self):
        self.assertEqual(_select_buds_mac(["AA:00"], ["BB:00"]), "AA:00")
        self.assertEqual(_select_buds_mac([], ["BB:00"]), "BB:00")
        with self.assertRaisesRegex(ValueError, "Multiple Galaxy Buds are connected"):
            _select_buds_mac(["AA:00", "BB:00"], [])
        with self.assertRaisesRegex(ValueError, "Multiple paired Galaxy Buds"):
            _select_buds_mac([], ["AA:00", "BB:00"])

    def test_auto_detection_ignores_unpaired_disconnected_devices(self):
        devices = {
            "/org/bluez/hci0/dev_AA": {"org.bluez.Device1": {
                "Address": "AA:00", "Name": "Galaxy Buds FE", "UUIDs": [],
                "Connected": False, "Paired": False,
            }},
            "/org/bluez/hci0/dev_BB": {"org.bluez.Device1": {
                "Address": "BB:00", "Name": "Galaxy Buds3", "UUIDs": [],
                "Connected": False, "Paired": True,
            }},
        }

        class ObjectManager:
            @staticmethod
            def GetManagedObjects():
                return devices

        bus = type("Bus", (), {"get_object": lambda self, *_args: ObjectManager()})()
        fake_dbus = type("DBus", (), {
            "SystemBus": staticmethod(lambda: bus),
            "Interface": staticmethod(lambda obj, _interface: obj),
        })
        with patch.dict(sys.modules, {"dbus": fake_dbus}):
            self.assertEqual(auto_detect_buds_mac(), "BB:00")

    def test_model_capabilities_follow_reference_device_specs(self):
        buds3 = build_model_info("Galaxy Buds3", "SM-R530", "Silver", "R530")
        buds3_pro = build_model_info("Galaxy Buds3 Pro", "SM-R630", "Silver", "R630")
        buds_pro = build_model_info("Galaxy Buds Pro", "SM-R190", "Black", "R190")
        buds2_pro = build_model_info("Galaxy Buds2 Pro", "SM-R510", "Graphite", "R510")
        fe = build_model_info("Galaxy Buds FE", "SM-R400N", "Graphite", "R400N")
        live = build_model_info("Galaxy Buds Live", "SM-R180", "Black", "R180")
        self.assertTrue(buds3.has_ambient)
        self.assertEqual(buds3.max_ambient_volume, 2)
        self.assertFalse(buds3.supports_adaptive)
        self.assertFalse(buds3.has_blade_lights)
        self.assertEqual(buds3_pro.max_ambient_volume, 2)
        self.assertEqual(buds_pro.max_ambient_volume, 3)
        self.assertEqual(buds2_pro.max_ambient_volume, 2)
        self.assertEqual(fe.max_ambient_volume, 2)
        self.assertFalse(live.has_ambient)

    def test_capability_report_separates_hardware_support_from_cli_support(self):
        buds3 = build_model_info("Galaxy Buds3", "SM-R530", "Silver", "R530")
        capabilities = buds3.capabilities_dict()

        self.assertEqual(capabilities["noise_control_modes"], ["off", "on", "ambient", "toggle"])
        self.assertEqual(capabilities["features"]["ambient_volume"]["max_level"], 2)
        self.assertEqual(capabilities["features"]["blade_lights"]["device_support"], "unsupported")
        self.assertEqual(capabilities["features"]["blade_lights"]["gbuds_support"], "rejected")
        self.assertEqual(capabilities["features"]["equalizer"]["device_support"], "unknown")

    def test_capability_report_marks_unknown_model_and_legacy_protocol(self):
        unknown = build_model_info("Galaxy Buds", "Unknown", "Standard", "Unknown")
        unknown_report = unknown.capabilities_dict()
        self.assertIsNone(unknown_report["noise_control_modes"])
        self.assertEqual(unknown_report["features"]["anc"]["device_support"], "unknown")

        legacy = build_model_info("Galaxy Buds", "SM-R170", "White/Black", "R170")
        legacy_report = legacy.capabilities_dict()
        self.assertEqual(legacy_report["features"]["ambient_sound"]["device_support"], "supported")
        self.assertEqual(legacy_report["features"]["ambient_sound"]["gbuds_support"], "not_implemented")

    def test_capabilities_command_outputs_json_without_connecting(self):
        props = {"Connected": False, "Name": "Galaxy Buds3 test", "UUIDs": []}
        output = StringIO()
        with patch.object(sys, "argv", ["gbuds", "--json", "capabilities"]), \
             patch("gbuds.cli.auto_detect_buds_mac", return_value="AA:BB:CC:DD:EE:FF"), \
             patch("gbuds.cli.get_bluez_device_props", return_value=props), \
             patch("gbuds.cli.BudsClient") as client_class, \
             redirect_stdout(output):
            main()

        payload = json.loads(output.getvalue())
        self.assertTrue(payload["success"])
        self.assertEqual(payload["device"]["model_code"], "SM-R530")
        self.assertEqual(payload["capabilities"]["features"]["adaptive_noise"]["device_support"], "unsupported")
        client_class.assert_not_called()

    def test_capabilities_command_prints_readable_report_without_connecting(self):
        props = {"Connected": False, "Name": "Galaxy Buds FE test", "UUIDs": []}
        output = StringIO()
        with patch.object(sys, "argv", ["gbuds", "capabilities"]), \
             patch("gbuds.cli.auto_detect_buds_mac", return_value="AA:BB:CC:DD:EE:FF"), \
             patch("gbuds.cli.get_bluez_device_props", return_value=props), \
             patch("gbuds.cli.BudsClient") as client_class, \
             redirect_stdout(output):
            main()

        self.assertIn("Capabilities: Galaxy Buds FE (SM-R400N)", output.getvalue())
        self.assertIn("Ambient volume", output.getvalue())
        self.assertIn("Supported (max 2)", output.getvalue())
        self.assertIn("Unknown means the model metadata does not classify this feature.", output.getvalue())
        client_class.assert_not_called()

    def test_current_reference_models_are_recognized_without_claiming_physical_validation(self):
        buds3_fe = identify_device_from_uuids([], "Galaxy Buds3 FE de Jose")
        buds4 = identify_device_from_uuids([], "Galaxy Buds4 de Jose")
        buds4_pro = identify_device_from_uuids([], "Galaxy Buds4 Pro de Jose")
        buds4_from_id = identify_device_from_uuids([f"{DEVICE_ID_PREFIX}{355:x}"])
        self.assertEqual(buds3_fe.model_code, "SM-R420")
        self.assertEqual(buds4.model_code, "SM-R540")
        self.assertEqual(buds4_pro.model_code, "SM-R640")
        self.assertEqual(buds4_from_id.model_code, "SM-R540")
        self.assertEqual(buds4.max_ambient_volume, 2)
        self.assertEqual(buds4_pro.max_ambient_volume, 4)
        self.assertTrue(buds4_pro.has_voice_detect)

    def test_ambient_volume_rejects_values_above_model_limit(self):
        fe = build_model_info("Galaxy Buds FE", "SM-R400N", "Graphite", "R400N")
        client = BudsClient("00:11:22:33:44:55", model_code=fe.model_code)
        with self.assertRaisesRegex(ValueError, "levels 0 to 2"):
            client.set_ambient_volume(3, model_info=fe)

    def test_reference_fixtures_match_model_specific_status_fields(self):
        fixture_dir = Path(__file__).parent / "fixtures"
        cases = {
            "BudsFe_rev2.bin": ("SM-R400N", 58, 89, 0, EqualizerPreset.OFF, NoiseControlMode.OFF, False),
            "Buds2_rev10.bin": ("SM-R177", 100, 100, 51, EqualizerPreset.DYNAMIC, NoiseControlMode.NOISE_REDUCTION, True),
            "BudsPlus_rev13.bin": ("SM-R175", 87, 84, None, EqualizerPreset.DYNAMIC, None, False),
            "BudsLive_rev9.bin": ("SM-R180", 15, 97, 100, EqualizerPreset.OFF, NoiseControlMode.NOISE_REDUCTION, False),
            "BudsPro_rev10.bin": ("SM-R190", 89, 94, 100, EqualizerPreset.BASS_BOOST, NoiseControlMode.OFF, False),
            "Buds2Pro_rev13.bin": ("SM-R510", 100, 100, 88, EqualizerPreset.BASS_BOOST, NoiseControlMode.OFF, False),
        }
        for filename, expected in cases.items():
            with self.subTest(model=filename):
                msg = parse_packet((fixture_dir / filename).read_bytes())
                self.assertIsNotNone(msg)
                status = decode_battery_status(msg, model_code=expected[0])
                self.assertIsNotNone(status)
                self.assertEqual(
                    (status.left, status.right, status.case, status.equalizer_preset,
                     status.noise_control_mode, status.touchpad_locked),
                    expected[1:],
                )

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
        self.assertEqual(status.placement_left, PlacementState.WEARING)
        self.assertEqual(status.placement_right, PlacementState.WEARING)
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

    def test_equalizer_packet(self):
        pkt_bass = encode_equalizer(EqualizerPreset.BASS_BOOST)
        msg_bass = parse_packet(pkt_bass)
        self.assertIsNotNone(msg_bass)
        self.assertEqual(msg_bass.msg_id, MsgIds.EQUALIZER)
        self.assertEqual(msg_bass.payload, bytes([1]))

        pkt_off = encode_equalizer(EqualizerPreset.OFF)
        msg_off = parse_packet(pkt_off)
        self.assertIsNotNone(msg_off)
        self.assertEqual(msg_off.msg_id, MsgIds.EQUALIZER)
        self.assertEqual(msg_off.payload, bytes([0]))

    def test_blade_lights_packet(self):
        pkt_blink = encode_blade_lights(BladeLightingMode.BLINK)
        msg_blink = parse_packet(pkt_blink)
        self.assertIsNotNone(msg_blink)
        self.assertEqual(msg_blink.msg_id, MsgIds.BUDS_LIGHTING_SYNC)
        self.assertEqual(msg_blink.payload, bytes([3]))

    def test_find_earbuds_and_mute(self):
        pkt_start = encode_find_earbuds(start=True)
        msg_start = parse_packet(pkt_start)
        self.assertIsNotNone(msg_start)
        self.assertEqual(msg_start.msg_id, MsgIds.FIND_MY_EARBUDS_START)

        pkt_stop = encode_find_earbuds(start=False)
        msg_stop = parse_packet(pkt_stop)
        self.assertIsNotNone(msg_stop)
        self.assertEqual(msg_stop.msg_id, MsgIds.FIND_MY_EARBUDS_STOP)

        pkt_mute = encode_mute_earbud(left_mute=True, right_mute=False)
        msg_mute = parse_packet(pkt_mute)
        self.assertIsNotNone(msg_mute)
        self.assertEqual(msg_mute.msg_id, MsgIds.MUTE_EARBUD)
        self.assertEqual(msg_mute.payload, bytes([1, 0]))

    def test_ambient_volume_and_voice_detect(self):
        pkt_amb = encode_ambient_volume(3)
        msg_amb = parse_packet(pkt_amb)
        self.assertIsNotNone(msg_amb)
        self.assertEqual(msg_amb.msg_id, MsgIds.AMBIENT_VOLUME)
        self.assertEqual(msg_amb.payload, bytes([3]))

        pkt_vd = encode_voice_detect(True)
        msg_vd = parse_packet(pkt_vd)
        self.assertIsNotNone(msg_vd)
        self.assertEqual(msg_vd.msg_id, MsgIds.SET_DETECT_CONVERSATIONS)
        self.assertEqual(msg_vd.payload, bytes([1]))


if __name__ == "__main__":
    unittest.main()
