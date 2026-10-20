#!/usr/bin/env python3
"""Health-gated local inference and a user-session supervisor for the owned pair."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.planet-runs'
UNITS = ('petlab-active', 'h2ol-petlab-gpu0', 'petlab-router')


def health():
    h2o = os.environ.get('PLANET_DECISION_URL', 'http://127.0.0.1:8741/v1/systemone')
    qwen = os.environ.get('PLANET_QWEN_URL', 'http://127.0.0.1:18020/v1')
    endpoints = {'h2o': h2o.split('/v1/')[0] + '/health', 'qwen': qwen + '/models'}
    result = {}
    for name, url in endpoints.items():
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                data = json.load(response)
            result[name] = bool(data.get('ok') if name == 'h2o' else data.get('data'))
        except (OSError, ValueError):
            result[name] = False
    return result


def ready(status):
    return bool(status) and all(status.values())


def record(phase, **fields):
    STATE.mkdir(exist_ok=True, mode=0o700)
    path = STATE / 'runtime.json'
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'phase': phase, 'time': time.time(), **fields}) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def active(unit):
    return subprocess.run(['systemctl', '--user', 'is-active', '--quiet', unit],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


@contextmanager
def model_session(emit, timeout=150):
    """Wait cancellably before inference; protect active requests from recovery."""
    STATE.mkdir(exist_ok=True, mode=0o700)
    deadline = time.monotonic() + timeout
    announced = False
    with (STATE / 'models.lock').open('a') as lock:
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
                if ready(health()):
                    break
                fcntl.flock(lock, fcntl.LOCK_UN)
            except BlockingIOError:
                pass
            if not announced:
                emit('state', phase='starting', message='Starting local models…', desktop=False)
                subprocess.run(['systemctl', '--user', 'start', 'planet-models.service'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
                announced = True
            if not active('planet-models.service'):
                raise RuntimeError('Local models are unavailable and automatic startup is not installed. Run the Planet runtime installer')
            if time.monotonic() >= deadline:
                raise RuntimeError('Local models did not become ready. Check planet-models.service; no model action was started')
            time.sleep(.5)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def recover(control):
    """Never restart during inference, or evict unrelated model services."""
    with (STATE / 'models.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        if ready(health()):
            return True
        record('starting')
        # The lab controller stops only its named units and checks free RAM,
        # GPU memory and occupied ports before starting anything.
        if any(active(unit) for unit in UNITS):
            subprocess.run([str(control), 'stop'], check=True, timeout=45)
        subprocess.run([str(control), 'start'], check=True, timeout=240)
        return ready(health())


def supervise():
    control = Path(os.environ['PLANET_MODEL_CONTROL']).expanduser().resolve()
    if not control.is_file():
        raise RuntimeError('The configured model controller does not exist.')
    STATE.mkdir(exist_ok=True, mode=0o700)
    with (STATE / 'runtime.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Enable accessibility before CEF applications start at login.
        from scripts.desktop import Desktop
        Desktop().ensure_accessibility()
        misses = 2
        while True:
            status = health()
            if ready(status):
                misses = 0
                record('ready', services=status)
            else:
                misses += 1
                record('waiting', services=status)
                if misses >= 3:
                    try:
                        if recover(control):
                            misses = 0
                            record('ready', services=health())
                    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                        record('unavailable', error=str(error)[:400])
                        print(str(error), flush=True)
                        time.sleep(30)
            time.sleep(10)


if __name__ == '__main__':
    import sys
    sys.path.insert(0, str(ROOT))
    supervise()
