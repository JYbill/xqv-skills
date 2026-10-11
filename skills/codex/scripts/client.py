"""Local bridge client, receiver startup and offline event reads."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

from config import STATE, SOCK, POLL_TIMEOUT, dumps
from store import Store, poll_events

def saved_poll(req):
    """Read retained events after the receiver has exited; never resend an RPC."""
    path = STATE / 'events.sqlite'
    if not path.exists():
        raise RuntimeError('No saved bridge events; start the bridge first.')
    store = Store(path)
    try:
        row = store.db.execute('SELECT epoch FROM events ORDER BY seq DESC LIMIT 1').fetchone()
        return poll_events(store, req, lambda: False, row[0] if row else None)
    finally:
        store.db.close()

def client(req):
    try:
        with socket.socket(socket.AF_UNIX) as conn:
            # 给 poll 返回和本地传输留出余量，避免客户端先于后台等待超时。
            conn.settimeout(POLL_TIMEOUT + 10)
            conn.connect(str(SOCK))
            conn.sendall((dumps(req) + '\n').encode())
            line = conn.makefile('r').readline()
            if not line:
                raise ConnectionError('Bridge closed the connection.')
            return json.loads(line)
    except (FileNotFoundError, ConnectionError):
        if req.get('op') == 'poll':
            return saved_poll(req)
        raise

def start():
    """Reuse a connected receiver, or start one after the old receiver exits."""
    # A disconnected receiver exits on its own; let it release socket/lock.
    for _ in range(30):
        try:
            status = client({'op': 'status'})
        except (OSError, ValueError):
            break
        if status.get('error'):
            return status
        if status.get('connected'):
            return status
        time.sleep(.1)
    else:
        raise RuntimeError('Disconnected bridge did not exit; inspect its process before restarting.')
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(STATE / 'bridge.log', 'a') as log:
        proc = subprocess.Popen([sys.executable, str(Path(__file__).with_name('bridge.py').resolve()), 'serve'], stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    for _ in range(100):
        try:
            status = client({'op': 'status'})
            if status.get('connected') and not status.get('error'):
                return status
            if status.get('error'):
                return status
            time.sleep(.1)
        except (OSError, ValueError):
            if proc.poll() is not None:
                raise RuntimeError('Bridge exited; inspect ' + str(STATE / 'bridge.log'))
            time.sleep(.1)
    raise RuntimeError('Startup still pending; inspect status/log. Do not start another backend.')
