# Entity Ghost

[![hacs_badge](https://img.shields.io/github/v/release/haedwin/homeassistant-entity_ghost)](https://github.com/haedwin/homeassistant-entity_ghost)
[![Validate with HACS](https://github.com/HAEdwin/homeassistant-entity_ghost/actions/workflows/validate%20with%20HACS.yaml/badge.svg)](https://github.com/HAEdwin/homeassistant-entity_ghost/actions/workflows/validate%20with%20HACS.yaml)
[![hacs_badge](https://img.shields.io/maintenance/yes/2026)](https://github.com/haedwin/homeassistant-entity_ghost)

<img src="https://github.com/HAEdwin/homeassistant-entity_ghost/blob/main/icon.png" alt="Entity Ghost" width="31%" height="31%"/>

Entity Ghost is a Home Assistant custom integration that shares entity states
between Home Assistant instances over the local network via UDP. It couples a
**sender** instance to one or more **receiver** instances: the sender publishes
the states of the entities it owns, and a receiver makes those states available
as local ghost entities.

Use it, for example, to develop templates, automations and dashboards against
real production data without touching the production instance — a reboot of the
development environment has no impact on production.

> [!TIP]
> If you need to link full instances across networks, take a look at
> [remote_homeassistant](https://github.com/custom-components/remote_homeassistant).
> Entity Ghost does not mirror an instance: it only copies the entities of the
> integrations you select. This ensures that the production and development environments are kept strictly separate.

## Features

When you add the integration you choose one of two modes:

| Mode        | What it does                                                              |
|-------------|---------------------------------------------------------------------------|
| **Broadcaster** | Publishes the states of entities from the selected integrations on the network |
| **Receiver**    | Listens for broadcasts and creates ghost entities for the received states     |

The scope is selected **by integration, not by individual entity IDs** — all
relevant entities of the selected integrations are handled dynamically. New or
removed entities are picked up automatically.

### Broadcaster mode

- Select one or more installed integration domains; their entities are broadcast.
- Entity state changes are published in real time over UDP broadcast.
- Only a safe subset of metadata is sent per entity: `friendly_name`,
  `device_class`, `unit_of_measurement`, `state_class`, `icon` and
  `entity_category`. All other attributes stay out of the datagram.
- An icon set in the entity registry takes precedence over the state attribute.

### Receiver mode

- Creates a ghost entity for every received entity.
- Ghost entities:
  - every received entity is mirrored as a **sensor** ghost, keeping its
    friendly name, state and metadata. This includes received
    `binary_sensor` entities — there is no `binary_sensor` ghost;
  - received **switch** entities additionally get a controllable ghost switch.
    Operating it sends a `command` back to the sender, which executes it only
    after validating message type, entity selection, domain and the allowed
    action (`turn_on` / `turn_off` only).
- Groups all received entities under a single device.
- Provides a switch to enable/disable the UDP listener.
- Automatically removes stale entities (see below).

### Limitations

- Broadcasts stay on the local network/subnet; they do not cross routers by
  default. Both instances must run on the same subnet and use the same UDP port.
- Overusing broadcasts can congest the network.
- Commands are restricted to `switch` entities and to `turn_on` / `turn_off`.
- `sensor` states `unknown` and `unavailable` are never published as literal
  values; the ghost sensor becomes `unavailable` so numeric device classes stay
  valid. ISO-8601 strings for the `timestamp` and `uptime` device classes are
  converted to timezone-aware values; invalid values become `unavailable`.
- A received device class is only published when the associated unit is valid
  for that class. If the unit is missing or incompatible, the device class is
  omitted — the receiver never guesses a unit.
- SNR/diagnostics: when the sender skips an oversized payload it logs a warning
  and the entity is not broadcast.

### Stale entity cleanup

Received entities that stop sending updates are marked `unavailable` after a
stale timeout, then removed from Home Assistant together with their recorded
history. The timeout is configurable in the receiver options (minutes, default
**10**, minimum **0** which disables cleanup). Forgetting to clean up never
becomes a manual chore: leftover registry entries from earlier sessions are
removed automatically as well, and a returning entity is recreated without
duplicate IDs.

> [!IMPORTANT]
> Please open an issue if you would like a feature added to Entity Ghost.

## Requirements

- A reasonably current Home Assistant installation (no pinned minimum in the
  manifest; developed and tested on Home Assistant 2026.9).
- Home Assistant instances reachable from each other on the **same subnet**,
  with the chosen UDP port open (default `8888`).
- No account, API key, cloud service or physical device is required.
- No third-party Python packages: it ships with `requirements: []` and only
  uses Home Assistant core.
- Most option changes take effect without a restart (a receiver UDP port
  change is picked up after a restart); changes to the integration files
  themselves require a full Home Assistant restart.

## Installation

### Installing via HACS

1. In Home Assistant, open **HACS**.
2. Open **⋮ → Custom repositories**.
   - **Repository**: `https://github.com/HAEdwin/homeassistant-entity_ghost`
   - **Category**: Integration
   - Click **Add**.
3. In **HACS → Integrations**, search for **Entity Ghost**.
4. Click **Install**.
5. Restart Home Assistant (Settings → System → Restart).
6. Add the integration (see [Configuration](#configuration)).

### Manual installation

1. Copy the `entity_ghost` folder into your `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration (see [Configuration](#configuration)).

## Configuration

Add the integration via **Settings → Devices & Services → Add Integration** and
search for **Entity Ghost**. First you pick the **mode**; the fields asked for
depend on it.

**Broadcaster** flow:

- **Integrations** — the integration domains to broadcast (`entity_ghost`
  itself is excluded). Select them on the instance that owns the remote
  entities.
- **UDP port** — the port to broadcast on (`1024`–`65535`, default `8888`).
- **Name** — a recognizable name for this broadcaster.

**Receiver** flow:

- **UDP port** — the port to listen on (`1024`–`65535`, default `8888`). Use
  the same port as the broadcaster.
- **Broadcaster name** — optional label of the expected broadcaster (default
  `Remote Home Assistant`); shown as metadata on received entities.

**Options** lets you adjust the settings after setup:

- Broadcaster: integrations, UDP port and name — applied immediately.
- Receiver: broadcaster name and **stale timeout** — applied immediately; a UDP
  port change is only picked up after a restart.

> [!NOTE]
> New configurations select integrations. The old per-entity selection key
> remains temporarily supported for migration and is not used by new setups.

## Usage

Once configured, states flow automatically in real time:

1. The broadcaster watches entity changes on the selected integrations and
   sends a UDP `state` message per change.
2. The receiver listens on the configured port, creates a ghost entity per
   received entity and updates it in real time.


### Created entities

Ghost sensors are named `Received <original entity>` (the friendly name is
kept when the sender provides one); ghost switches follow the same naming. The
entity IDs are derived from that name — a broadcast `sensor.smartplug_power`
becomes e.g. `sensor.received_smartplug_power` on a fresh receiver. The
`sensor` ghosts use a stable `unique_id` (`entity_ghost_<entry_id>_<entity>`),
so restarts and re-setup never duplicate entities, and installations that
already had older versions keep their historical entity IDs and friendly
names.

Every received entity gets a sensor ghost; received `switch` entities get a
controllable ghost switch as well. Toggling it sends a `command`
(`turn_on` / `turn_off`) back to the sender, which validates and executes it
locally.

All ghosts, together with an *Entity Ghost Receiver* switch that
enables/disables the UDP listener, are grouped under one device named
`Entity Ghost Receiver (Port <port>)`.

Example: use a received ghost sensor in an automation:

```yaml
automation:
  - alias: "Notify when remote temperature changes"
    trigger:
      - platform: state
        entity_id: sensor.received_temperature
    action:
      - service: notify.persistent_notification
        data:
          message: "Remote temperature is now {{ trigger.to_state.state }} °C"
```

## Troubleshooting

Known points of attention:

- **Same subnet and same port** — broadcasts do not cross routers. Put sender
  and receiver on the same subnet and use the same UDP port on both sides.
- **Firewall** — make sure nothing blocks the chosen UDP port on either side.
- **No updates received** — verify the sender still has the integration in
  scope and the entity is being broadcast (see logging below).
- **Stale entities linger longer than expected** — the timeout counts from the
  last received update; leftovers from earlier sessions are cleaned up after
  the same timeout.

### Logging

At the default log level (INFO) Entity Ghost only writes on listener
start/stop, configuration changes and actual errors — it does not log per
message. Debug-level logging produces one or more lines per received/sent
message and can make logs grow quickly; only enable it while investigating.

To enable debug logging for this integration:

- go to **Settings → System → Logs**, or
- add to `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.entity_ghost: debug
```

Debug logs intentionally omit full datagram payloads: they include the source
address, payload size and entity ID where known, and for entity updates the new
state value — but never the complete JSON payload or the attributes map.

### When reporting a bug, please include

- Home Assistant version (Settings → About or **About** in the sidebar) and
  whether it runs under HA OS/Supervised/Container/Core.
- The relevant log excerpt with debug logging for `custom_components.entity_ghost`
  enabled, if possible.
- A description of the steps to reproduce, and which instances (sender /
  receiver) were involved.

## Issues & Support

Report bugs, feature requests and questions at the GitHub issue tracker:

- **Repository**: <https://github.com/HAEdwin/homeassistant-entity_ghost>
- **Issues**: <https://github.com/HAEdwin/homeassistant-entity_ghost/issues>

## License

MIT License — see the [LICENSE](https://github.com/HAEdwin/homeassistant-entity_ghost/blob/main/LICENSE)
file for details.