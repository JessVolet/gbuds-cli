# Device support and validation

## How to read this page

Gbuds has three different levels of model information:

1. **Recognized**: BlueZ name or Samsung device ID maps to a model entry.
2. **Fixture-checked**: an offline status packet from GalaxyBudsClient is parsed and compared against expected fields.
3. **Physically tested**: the maintainer has exercised the CLI with that hardware.

Recognition does not mean every protocol command is implemented. Fixtures cover status decoding only; they do not prove control commands or all firmware revisions. Capability declarations are based on the local model table, cross-checked against GalaxyBudsClient device specifications.

## Model matrix

| Model | Model code | Declared features | Status fixture | Physical test |
| --- | --- | --- | :---: | :---: |
| Galaxy Buds (2019) | SM-R170 | Ambient volume metadata; legacy SPP framing is not implemented | No | No |
| Galaxy Buds+ | SM-R175 | Ambient Sound, max level 2 | Yes | No |
| Galaxy Buds Live | SM-R180 | ANC; no Ambient Sound | Yes | No |
| Galaxy Buds Pro | SM-R190 | ANC, Ambient Sound (max 3), Voice Detect | Yes | No |
| Galaxy Buds2 | SM-R177 | ANC, Ambient Sound (max 2) | Yes | No |
| Galaxy Buds2 Pro | SM-R510 | ANC, Ambient Sound (max 2), Voice Detect | Yes | No |
| Galaxy Buds FE | SM-R400N | ANC, Ambient Sound (max 2) | Yes | **Yes** |
| Galaxy Buds3 | SM-R530 | ANC, Ambient Sound (max 2); no Adaptive mode or Blade Lights | No | **Yes** |
| Galaxy Buds3 Pro | SM-R630 | ANC, Ambient Sound (max 2), Adaptive, Voice Detect, Blade Lights | No | No |
| Galaxy Buds3 FE | SM-R420 | ANC, Ambient Sound (max 2) | No | No |
| Galaxy Buds4 | SM-R540 | ANC, Ambient Sound (max 2) | No | No |
| Galaxy Buds4 Pro | SM-R640 | ANC, Ambient Sound (max 4), Voice Detect | No | No |

Physical validation is limited to the maintainer's Buds FE and Buds3. The hardware smoke checks covered battery/status queries and `watch`; they do not cover every mutating command. GalaxyBudsClient fixture captures cover Buds+, Buds Live, Buds Pro, Buds2, Buds2 Pro, and Buds FE.

## Important limitations

- The first-generation Galaxy Buds is recognized by model name/ID, but its legacy packet header is unsupported; do not treat it as a working device target.
- Buds3 has no corresponding status fixture in the current reference test data. Ambient Sound, ANC, and max level 2 follow its device specification; only the hardware battery/status path has been physically smoke-tested.
- Buds3 FE and Buds4 families are recognized and have declared capabilities, but there are no local packet fixtures or physical tests for them.
- Firmware differences may change payload layout or available functions. An unsupported command should be rejected, but a supported declaration should still be verified on the actual model before relying on it.
- No model in this table has been tested against every firmware revision or every transport backend.

Report a missing model with its marketing name, model code, firmware version, and a redacted CLI error. Do not attach serial numbers or Bluetooth addresses unless they are necessary and you have reviewed the issue's visibility.
