# Architecture

## Request path

```text
Home Assistant camera request       Opted-in WebSocket request
             |                                  |
             +---------- shared API ------------+
                              |
                     per-TV lock and cache
                              |
              built-in webostv paired TLS client
                              |
                    tv/executeOneShot
                              |
            same-host HTTPS image + certificate pin
                              |
                 bounded JPEG -> small JPEG
```

`camera.py` registers a snapshot-only `Camera` with polling disabled. Its
`async_camera_image()` method calls the same capture object used by the
WebSocket API. Entity setup, configuration flows and options changes do not
request screenshots. No screenshot timer runs in the background.

`config_flow.py` selects enabled `media_player` entities from `webostv`; it never
accepts an IP address, URL or secret. Config entries store the entity registry
ID to survive renames. One capture entry per registry ID prevents duplicates.

`__init__.py` registers the WebSocket command and manages the loaded opt-in
allowlist. It exports `get_capture`, `async_get_frame` and `TVCapture` for trusted
Python integrations. Camera authentication itself belongs to Home Assistant.

## Shared capture core

`capture.py` is self-contained and has no relative imports. Its dependencies
are Python's standard library, Home Assistant, aiohttp and Pillow (already
included with supported Home Assistant releases). An integration may vendor
this exact file under the MIT license while pinning its upstream commit.
Prefer importing the installed integration when practical.

```python
from custom_components.lg_tv_capture import async_get_frame, get_capture

frame = await async_get_frame(hass, "media_player.test_tv")
# Equivalent; reuse this object when integrating with an existing backend:
capture = get_capture(hass, "media_player.test_tv")
frame = await capture.get()
```

Call these APIs from the Home Assistant event loop. They work without a
configured UI entry. `get_capture` resolves a stable entity registry ID and
shares one object through `hass.data["lg_tv_capture"]`. Exact vendored copies
use the same store and can share the cooldown too. Callers should not mutate
the store. Direct `TVCapture(hass, entity_id)` construction remains available
for compatibility and tests, but separate direct constructions have separate
caches; use `get_capture` in application code.

`get()` returns a new dictionary: `{"image": null}` or
`{"image": "data:image/jpeg;base64,...", "captured_at": <Unix seconds>}`.
`thumbnail(bytes)` provides the same bounded JPEG sanitization independently.

The lock serializes concurrent requests. An attempt reserves 60 seconds before
network I/O, including failure and cancellation. Source changes invalidate
images but never reset the cooldown. State events track source/power changes
between reads, including an A → B → A input change. Before and after network
I/O, the adapter checks active state, restore status, source, state transition
time and paired connection identity. Exceptions produce an empty result or
retain an unchanged source's old frame; cancellation propagates.

## Compatibility boundary

The adapter relies on these current Home Assistant and aiowebostv attributes:

- Entity registry `platform == "webostv"`, owning config entry and `data["host"]`.
- `entry.runtime_data.client`, `client.is_connected()` and `client.connection`.
- `client.connection.get_extra_info("ssl_object")` with a peer certificate.
- `await client.request("tv/executeOneShot")` returning `returnValue` and `imageUri`.

The private adapter fails closed if those interfaces are absent. The TV must
support the command and return the expected HTTPS JPEG resource. An older
plaintext webOS control connection is intentionally unsupported.

Reference implementations checked against Home Assistant 2026.10.1:

- [webOS setup](https://github.com/home-assistant/core/blob/2026.10.1/homeassistant/components/webostv/__init__.py)
- [webOS coordinator](https://github.com/home-assistant/core/blob/2026.10.1/homeassistant/components/webostv/coordinator.py)
- [Camera platform](https://github.com/home-assistant/core/blob/2026.10.1/homeassistant/components/camera/__init__.py)
- [Config-flow developer documentation](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)

Tests exercise the real Home Assistant integration loader, configuration flows,
camera setup and authenticated WebSocket handler. TV transport, state changes,
malformed replies, certificate pin configuration, image validation, concurrent
requests and cooldown behavior are tested without network or hardware access.
These tests establish the software contract, not support for every television.
