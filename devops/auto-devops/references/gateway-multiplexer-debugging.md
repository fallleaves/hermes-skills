# Gateway Multiplexer Debugging Reference

## How multiplexer works

`gateway.multiplex_profiles: true` on the default profile makes a single gateway
process serve ALL profiles. The entry point is
`_start_secondary_profile_adapters()` in `gateway/run.py`, called during startup
after the primary profile's adapters connect.

Log signals for a working multiplexer:

```
✓ telegram connected (profile: jf)
✓ telegram connected (profile: ws)
Gateway running with 3 platform(s)
```

## If secondary profiles don't connect

### 1. Check the config flag

```bash
grep multiplex_profiles ~/.hermes/config.yaml
```

Must show `multiplex_profiles: true` under the `gateway:` section.

### 2. Check load_gateway_config() reads it

Bug (v2026.5.x): `load_gateway_config()` in `gateway/config.py` extracts
`multiplex_profiles` from the **top-level** of `yaml_cfg` but NOT from the
nested `gateway:` section. If set via `hermes config set gateway.multiplex_profiles true`,
the flag lands under `gateway:` in YAML and is silently lost.

**Fix:** Add the nested extraction:

```python
gateway_section = yaml_cfg.get("gateway")
if isinstance(gateway_section, dict) and "multiplex_profiles" in gateway_section:
    gw_data["multiplex_profiles"] = gateway_section["multiplex_profiles"]
```

### 3. Check the log

```bash
grep "Gateway running with" ~/.hermes/logs/gateway.log | tail -1
```

If it says `1 platform(s)`, the multiplexer didn't start secondary adapters.

### 4. Check for port-binding conflicts

Secondary profiles must NOT enable port-binding platforms (`webhook`, `api_server`,
`sms`, etc.). The default profile's listener serves them via `/p/<profile>/` prefix.
If a secondary profile has one, the gateway will fail startup with a
`MultiplexConfigError`.

### 5. Check token conflicts

Two profiles with the same bot token for the same platform will be detected at
startup with a log error naming both profiles. Each profile needs its own token.
