# YAML schema reference (v1)

See [`tests/fixtures/configs/comprehensive.yaml`](../tests/fixtures/configs/comprehensive.yaml) for a working example.

## Top level

```yaml
version: 1
default_profile: <profile-name>
vars: { <key>: <value> }                # optional, available as {{vars.key}} in actions (resolved at execute-time in Phase 2)
obs_hosts:                              # optional in Phase 1, required in Phase 3
  <name>:
    url: obsws://<host>:<port>/<password-or-${ENV_VAR}>
profile_rules:                          # optional, used by Phase 4 active-window watcher
  - profile: <profile>
    when:
      app_class: [...]                  # Linux WM_CLASS
      app_name:  [...]                  # Windows process names
profiles:
  <profile-name>: <Profile>
```

## Profile

```yaml
default_page: <page-name>
pages:
  <page-name>: <Page>
```

## Page

```yaml
keys:
  <index 0..14>: <Key>
```

## Key

```yaml
icon: <IconSpec>
action: <Action>      # one of 21 types, discriminator: `type`
indicator: <Indicator?>  # optional live state binding
```

## IconSpec

```yaml
text: <str?>
emoji: <str?>          # any unicode emoji
image: <path?>         # path resolved relative to the config file
bg: "#rrggbb"          # default background
bg_idle: ...           # alias for bg, takes precedence
bg_active: ...         # used when bound indicator is true
bg_pressed: ...        # used briefly after press
bg_error: ...          # used on action failure (default #b71c1c)
bg_disconnected: ...   # used when an OBS host is unreachable (default #424242)
fg: "#rrggbb"          # text color (default #ffffff)
```

At least one of `text`, `emoji`, `image` must be set.

## Actions

**Phase 2a runtime note:** the `obs.*` action types validate in the schema but their handlers currently raise `NotImplementedError` at dispatch. Real OBS execution arrives in Phase 3. All other action types execute normally.

| `type` | Required fields | Optional |
|---|---|---|
| `shell` | `cmd` | `cwd`, `shell` |
| `key.chord` | `keys` | — |
| `key.text` | `text` | — |
| `open.url` | `url` | — |
| `open.app` | exactly one of `path`/`name` | — |
| `obs.scene.switch` | `host`, `scene` | — |
| `obs.recording.toggle`, `obs.streaming.toggle`, `obs.replay.save`, `obs.virtualcam.toggle` | `host` | — |
| `obs.input.mute.toggle` | `host`, `input_name` | — |
| `system.volume.up`/`down` | — | `step` (default 5) |
| `system.volume.mute`, `media.play`, `media.pause`, `media.next`, `media.prev` | — | — |
| `page.go` | `page` | — |
| `profile.switch` | `profile` | — |
| `compound` | `actions: [Action]` | `continue_on_error` (bool) |

## Indicator (live state binding, Phase 3+)

```yaml
bind: obs.recording.state | obs.streaming.state | obs.replay.state |
      obs.virtualcam.state | obs.scene.current | obs.input.muted
host: <obs_host name>
scene: <scene name?>      # required with obs.scene.current
input_name: <str?>        # required with obs.input.muted
```

When the bound source is "active", the key renders with the `active` state variant (uses `bg_active`).

## Environment variable substitution

Any string field can include `${VAR_NAME}`. Resolution happens before schema validation. Missing variables raise `ConfigError`. Recommended for OBS passwords.

```yaml
obs_hosts:
  roc:
    url: obsws://127.0.0.1:4455/${SDAC_OBS_ROC_PASS}
```

## File permissions

On POSIX, `sdac` warns when the config file is readable by group or others (mode bits `0o077`). Pass `--strict-perms` to reject instead. Recommended: `chmod 0600`.
