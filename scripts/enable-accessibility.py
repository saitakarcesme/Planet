#!/usr/bin/env python3
"""Opt-in local launcher configuration, never a model tool or task recipe."""
import argparse
from pathlib import Path
import time
import gi

gi.require_version('Gio', '2.0')
from gi.repository import Gio, GLib


def configure(app_id):
    app = Gio.DesktopAppInfo.new(app_id)
    if app is None or '/' in app_id or not app_id.endswith('.desktop'):
        raise ValueError('Use an installed desktop application ID.')
    source = Path(app.get_filename())
    data = GLib.KeyFile()
    data.load_from_file(str(source), GLib.KeyFileFlags.KEEP_COMMENTS | GLib.KeyFileFlags.KEEP_TRANSLATIONS)
    original = data.get_string('Desktop Entry', 'Exec')
    if '--force-renderer-accessibility' not in original:
        # Add the documented Chromium flag after its executable, preserving
        # field codes and arguments. Refuse wrappers requiring different rules.
        import re
        match = re.fullmatch(r'("[^"]+"|[^\s"]+)(.*)', original)
        if not match or Path(match[1].strip('"')).name in ('env', 'sh', 'bash', 'flatpak'):
            raise ValueError('Wrapped launcher: configure its accessibility flag manually.')
        data.set_string('Desktop Entry', 'Exec', match[1]+' --force-renderer-accessibility'+match[2])
    target = Path(GLib.get_user_data_dir())/'applications'/app_id
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = data.to_data()[0]
    if target.exists() and target.read_text() != payload:
        target.with_name(target.name+f'.planet-backup-{time.time_ns()}').write_bytes(target.read_bytes())
    target.write_text(payload)
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    bus.call_sync('org.a11y.Bus', '/org/a11y/bus', 'org.freedesktop.DBus.Properties', 'Set',
                  GLib.Variant('(ssv)', ('org.a11y.Status', 'IsEnabled', GLib.Variant('b', True))),
                  None, Gio.DBusCallFlags.NONE, 3000, None)
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app_id', help='Installed Chromium/CEF application desktop ID.')
    args = parser.parse_args()
    print(f'Accessibility launcher configured: {configure(args.app_id)}')
    print('Restart that application normally to use the updated launcher.')
