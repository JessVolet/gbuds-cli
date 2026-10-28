"""
Model definitions, Device IDs, and Color mappings for Samsung Galaxy Buds.
Reverse-engineered from GalaxyBudsClient and official Samsung Wearable Manager.
"""

from dataclasses import dataclass
from typing import Optional, Dict, List

DEVICE_ID_PREFIX = "d908aab5-7a90-4cbe-8641-86a553db"

@dataclass
class DeviceModelInfo:
    model_name: str
    model_code: str       # e.g. SM-R530
    firmware_prefix: str  # e.g. R530
    color: Optional[str] = None
    has_anc: bool = False
    has_ambient: bool = True
    supports_adaptive: bool = False
    has_blade_lights: bool = False
    has_voice_detect: bool = False
    max_ambient_volume: int = 3
    advanced_touch_lock: bool = False

    @property
    def supported_noise_modes(self) -> List[str]:
        modes = ["off"]
        if self.has_anc:
            modes.append("on")
        if self.has_ambient:
            modes.append("ambient")
        if self.supports_adaptive:
            modes.append("adaptive")
        modes.append("toggle")
        return modes

    def to_dict(self) -> dict:
        return {
            "model_name": self.model_name,
            "model_code": self.model_code,
            "firmware_prefix": self.firmware_prefix,
            "color": self.color,
            "has_anc": self.has_anc,
            "has_ambient": self.has_ambient,
            "supports_adaptive": self.supports_adaptive,
            "has_blade_lights": self.has_blade_lights,
            "has_voice_detect": self.has_voice_detect,
            "max_ambient_volume": self.max_ambient_volume,
            "advanced_touch_lock": self.advanced_touch_lock,
            "supported_noise_modes": self.supported_noise_modes,
        }


# Map of Samsung DeviceId integer -> (Model Name, Model Code, Color, FW Prefix)
DEVICE_ID_MAP: Dict[int, tuple[str, str, str, str]] = {
    # Buds (2019)
    257: ("Galaxy Buds", "SM-R170", "White/Black", "R170"),
    # Buds+
    258: ("Galaxy Buds+", "SM-R175", "Blue", "R175"),
    259: ("Galaxy Buds+", "SM-R175", "Pink", "R175"),
    260: ("Galaxy Buds+", "SM-R175", "Black", "R175"),
    261: ("Galaxy Buds+", "SM-R175", "White", "R175"),
    262: ("Galaxy Buds+", "SM-R175", "Thom Browne", "R175"),
    263: ("Galaxy Buds+", "SM-R175", "Red", "R175"),
    264: ("Galaxy Buds+", "SM-R175", "Deep Blue", "R175"),
    266: ("Galaxy Buds+", "SM-R175", "Purple", "R175"),
    # Buds Live
    278: ("Galaxy Buds Live", "SM-R180", "Mystic Black", "R180"),
    279: ("Galaxy Buds Live", "SM-R180", "Mystic White", "R180"),
    280: ("Galaxy Buds Live", "SM-R180", "Mystic Bronze", "R180"),
    281: ("Galaxy Buds Live", "SM-R180", "Mystic Red", "R180"),
    282: ("Galaxy Buds Live", "SM-R180", "Mystic Blue", "R180"),
    284: ("Galaxy Buds Live", "SM-R180", "Mystic Grey", "R180"),
    # Buds Pro
    298: ("Galaxy Buds Pro", "SM-R190", "Phantom Black", "R190"),
    299: ("Galaxy Buds Pro", "SM-R190", "Phantom Silver", "R190"),
    300: ("Galaxy Buds Pro", "SM-R190", "Phantom Violet", "R190"),
    301: ("Galaxy Buds Pro", "SM-R190", "Phantom White", "R190"),
    # Buds2
    313: ("Galaxy Buds2", "SM-R177", "White", "R177"),
    314: ("Galaxy Buds2", "SM-R177", "Graphite", "R177"),
    316: ("Galaxy Buds2", "SM-R177", "Olive", "R177"),
    317: ("Galaxy Buds2", "SM-R177", "Lavender", "R177"),
    320: ("Galaxy Buds2", "SM-R177", "Onyx", "R177"),
    # Buds2 Pro
    326: ("Galaxy Buds2 Pro", "SM-R510", "Graphite", "R510"),
    327: ("Galaxy Buds2 Pro", "SM-R510", "White", "R510"),
    328: ("Galaxy Buds2 Pro", "SM-R510", "Bora Purple", "R510"),
    # Buds FE
    330: ("Galaxy Buds FE", "SM-R400N", "Graphite", "R400N"),
    331: ("Galaxy Buds FE", "SM-R400N", "White", "R400N"),
    # Buds3
    333: ("Galaxy Buds3", "SM-R530", "Silver", "R530"),
    334: ("Galaxy Buds3", "SM-R530", "White", "R530"),
    # Buds3 Pro
    340: ("Galaxy Buds3 Pro", "SM-R630", "Silver", "R630"),
    341: ("Galaxy Buds3 Pro", "SM-R630", "White", "R630"),
    # Buds3 FE
    347: ("Galaxy Buds3 FE", "SM-R420", "Silver", "R420"),
    348: ("Galaxy Buds3 FE", "SM-R420", "White", "R420"),
}


def identify_device_from_uuids(uuids: list[str], device_name: str = "") -> DeviceModelInfo:
    device_id = None
    for u in uuids:
        u_clean = u.lower().strip()
        if u_clean.startswith(DEVICE_ID_PREFIX):
            suffix = u_clean.replace(DEVICE_ID_PREFIX, "")
            try:
                device_id = int(suffix, 16)
                break
            except ValueError:
                pass

    if device_id and device_id in DEVICE_ID_MAP:
        name, code, color, fw_prefix = DEVICE_ID_MAP[device_id]
        has_anc = "Live" in name or "Pro" in name or "Buds2" in name or "Buds3" in name or "FE" in name
        has_ambient = "Live" not in name
        supports_adaptive = "Buds3" in name
        adv_lock = "Buds2" in name or "Buds3" in name or "FE" in name
        blade_lights = "Buds3" in name
        voice_detect = "Pro" in name or ("Buds3" in name and "FE" not in name)
        max_amb = 0 if "Live" in name else (2 if "Buds+" in name or name == "Galaxy Buds" else 3)
        return DeviceModelInfo(
            model_name=name,
            model_code=code,
            firmware_prefix=fw_prefix,
            color=color,
            has_anc=has_anc,
            has_ambient=has_ambient,
            supports_adaptive=supports_adaptive,
            has_blade_lights=blade_lights,
            has_voice_detect=voice_detect,
            max_ambient_volume=max_amb,
            advanced_touch_lock=adv_lock,
        )

    # Fallback to name inspection
    name_upper = device_name.upper()
    if "BUDS3 PRO" in name_upper:
        return DeviceModelInfo("Galaxy Buds3 Pro", "SM-R630", "R630", has_anc=True, has_ambient=True, supports_adaptive=True, has_blade_lights=True, has_voice_detect=True, advanced_touch_lock=True)
    if "BUDS3" in name_upper:
        return DeviceModelInfo("Galaxy Buds3", "SM-R530", "R530", has_anc=True, has_ambient=True, supports_adaptive=True, has_blade_lights=True, has_voice_detect=True, advanced_touch_lock=True)
    if "BUDS2 PRO" in name_upper:
        return DeviceModelInfo("Galaxy Buds2 Pro", "SM-R510", "R510", has_anc=True, has_ambient=True, has_voice_detect=True, advanced_touch_lock=True)
    if "BUDS2" in name_upper:
        return DeviceModelInfo("Galaxy Buds2", "SM-R177", "R177", has_anc=True, has_ambient=True, advanced_touch_lock=True)
    if "BUDS FE" in name_upper:
        return DeviceModelInfo("Galaxy Buds FE", "SM-R400N", "R400N", has_anc=True, has_ambient=True, advanced_touch_lock=True)
    if "BUDS LIVE" in name_upper:
        return DeviceModelInfo("Galaxy Buds Live", "SM-R180", "R180", has_anc=True, has_ambient=False, max_ambient_volume=0)
    if "BUDS PRO" in name_upper:
        return DeviceModelInfo("Galaxy Buds Pro", "SM-R190", "R190", has_anc=True, has_ambient=True, has_voice_detect=True)
    if "BUDS+" in name_upper or "BUDS PLUS" in name_upper:
        return DeviceModelInfo("Galaxy Buds+", "SM-R175", "R175", has_anc=False, has_ambient=True, max_ambient_volume=2)

    return DeviceModelInfo("Galaxy Buds (Generic)", "Unknown", "Unknown", has_anc=True, has_ambient=True)
