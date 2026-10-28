# Python API

The public package exports a small client and the protocol/model types used by scripts. The CLI remains the recommended interface for users who do not need a persistent RFCOMM session.

## Read battery status

```python
from gbuds import BudsClient

client = BudsClient(
    mac_address="AA:BB:CC:DD:EE:FF",
    model_code="SM-R400N",  # Supply the detected model for model-specific decoding.
)

try:
    client.connect()
    status = client.get_battery(timeout=3.0)
    if status is None:
        raise TimeoutError("No status event received from the earbuds")
    print(status.to_dict())
finally:
    client.disconnect()
```

`connect()` opens RFCOMM and sends the manager handshake. `get_battery()` waits for inbound status and returns the most recently decoded `BatteryStatus`, or `None` if no status has arrived. Always close the client in a `finally` block.

## Detect model metadata

```python
from gbuds import identify_device_from_uuids

model = identify_device_from_uuids(bluez_uuids, device_name="Galaxy Buds FE")
print(model.model_code, model.supported_noise_modes)
```

The model result contains declared capabilities, not proof that all commands work on that firmware. The CLI passes `model_info` to model-gated controls. Library callers should do the same:

```python
from gbuds import NoiseControlMode

client.set_noise_control(NoiseControlMode.AMBIENT_SOUND, model_info=model)
```

Passing no `model_info` to a control method may skip that method's capability guard. See the [support matrix](DEVICE_SUPPORT.md) before issuing controls.

## Session and transport notes

- `BudsClient(mac_address, transport_type="direct", channel=None, model_code=None)` uses the direct RFCOMM backend by default. Use `transport_type="bluez"` for the optional BlueZ Profile transport.
- `watch(interval=0.5)` yields the initial status and subsequent changes until interrupted or the peer closes the connection.
- `DirectRfcommTransport` and `BluezProfileTransport` are exported for advanced use; their interface is raw bytes.
- The library has no asynchronous API. Do not share one client/socket between concurrent threads without adding synchronization.
