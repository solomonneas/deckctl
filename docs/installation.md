# Installation walkthrough

The minimum to go from "fresh Ubuntu" to "daemon running at login pushing icons to my Stream Deck".

## 1. System packages

```bash
sudo apt update
sudo apt install -y \
    libhidapi-libusb0 \
    xdotool \
    playerctl \
    pulseaudio-utils    # or pipewire-pulse on PipeWire systems
```

`libhidapi-libusb0` is the only one strictly required to start the daemon. The others are loaded lazily by their corresponding action types.

## 2. Python package

Recommended via pipx (isolated):

```bash
pipx install deckctl
deckctl --version
```

Or from a checkout for development:

```bash
git clone https://github.com/solomonneas/deckctl
cd deckctl
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## 3. Write a config

```bash
mkdir -p ~/.config/deckctl
chmod 700 ~/.config/deckctl
```

Drop a `~/.config/deckctl/config.yaml` with at least:

```yaml
version: 1
default_profile: coding
profiles:
  coding:
    default_page: home
    pages:
      home:
        keys:
          0:
            icon: {text: "Hello"}
            action: {type: shell, cmd: "notify-send 'Stream Deck' 'hello'"}
```

Validate it:

```bash
deckctl validate ~/.config/deckctl/config.yaml
```

Optionally preview it (no device needed):

```bash
deckctl preview ~/.config/deckctl/config.yaml --out /tmp/preview.png && xdg-open /tmp/preview.png
```

## 4. Test the daemon in the foreground

```bash
deckctl daemon --config ~/.config/deckctl/config.yaml -v
```

Press key 0 on your Deck; you should see the `notify-send` desktop notification. Stop with Ctrl+C.

## 5. Install as a service

```bash
deckctl install-service --config ~/.config/deckctl/config.yaml
```

This prompts once for your sudo password to install `/etc/udev/rules.d/60-streamdeck.rules`. The systemd user unit is written to `~/.config/systemd/user/deckctl.service` and immediately started.

Verify everything is healthy:

```bash
deckctl doctor --config ~/.config/deckctl/config.yaml
```

Inspect logs at any time:

```bash
journalctl --user -u deckctl -f
```

## 6. Uninstall

```bash
deckctl uninstall-service              # remove unit + udev rule
deckctl uninstall-service --keep-udev  # remove unit, keep udev rule
```
