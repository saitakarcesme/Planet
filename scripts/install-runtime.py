#!/usr/bin/env python3
"""Install persistent startup/recovery for this machine's existing model pair."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def unit_quote(text):
    return '"' + str(text).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-control', required=True, type=Path)
    args = parser.parse_args()
    control = args.model_control.expanduser().resolve()
    if not control.is_file():
        parser.error('The model controller must be an existing file.')
    folder = Path.home() / '.config/systemd/user'
    folder.mkdir(parents=True, exist_ok=True)
    unit = folder / 'planet-models.service'
    if unit.exists():
        shutil.copy2(unit, unit.with_suffix('.service.bak.' + str(int(time.time()))))
    unit.write_text(f'''[Unit]
Description=Planet local model startup and recovery

[Service]
Type=simple
WorkingDirectory={str(ROOT).replace('%', '%%')}
Environment={unit_quote("PLANET_MODEL_CONTROL=" + str(control))}
ExecStart={unit_quote(sys.executable)} {unit_quote(ROOT / "scripts/model_runtime.py")}
Restart=on-failure
RestartSec=10
TimeoutStopSec=10

[Install]
WantedBy=default.target
''')
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', '--user', 'enable', '--now', unit.name], check=True)
    print('Planet model startup and recovery are enabled for future logins.')


if __name__ == '__main__':
    main()
