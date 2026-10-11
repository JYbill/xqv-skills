#!/usr/bin/env python3
"""Persistent, local-only JSON-RPC bridge to an existing Codex managed daemon."""
import argparse
import base64
import struct
import fcntl
import hashlib
import json
import os
from pathlib import Path
import queue
import socket
import socketserver
import sqlite3
import subprocess
import sys
import threading
import time
import uuid

HOME = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))).expanduser().resolve()
ROOT = Path(os.environ.get('CODEX_SKILL_STATE', str(Path.home() / '.local/state/codex-skill'))).expanduser().resolve()
TAG = hashlib.sha256(str(HOME).encode()).hexdigest()[:12]
STATE = ROOT / TAG
SOCK = STATE / 'bridge.sock'
RPC_METHODS = {'thread/start', 'thread/resume', 'thread/read', 'thread/list',
               'thread/turns/list', 'thread/items/list', 'turn/start', 'turn/steer',
               'turn/interrupt', 'config/read'}
MUTATIONS = {'thread/start', 'thread/resume', 'turn/start', 'turn/steer', 'turn/interrupt'}

def dumps(x):
    return json.dumps(x, ensure_ascii=False, separators=(',', ':'))

def summary_event(msg):
    """Keep completed content, lifecycle, requests and bridge diagnostics."""
    method = msg.get('method', '')
    return ('id' in msg or method in {'item/completed', 'thread/status/changed',
            'turn/completed', 'serverRequest/resolved', 'error'} or
            method.startswith('bridge/') or bool((msg.get('params') or {}).get('questions')))

class UnixWebSocket:
    """RFC 6455 text transport on the existing user-private Codex Unix socket."""
    def __init__(self, path):
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.settimeout(10)
        self.sock.connect(str(path))
        key = base64.b64encode(os.urandom(16)).decode()
        request = ('GET /rpc HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\n'
                   'Connection: Upgrade\r\nSec-WebSocket-Version: 13\r\n'
                   'Sec-WebSocket-Key: ' + key + '\r\n\r\n')
        self.sock.sendall(request.encode())
        self.buffer = bytearray()
        while b'\r\n\r\n' not in self.buffer:
            data = self.sock.recv(4096)
            if not data:
                raise RuntimeError('Socket closed during WebSocket handshake')
            self.buffer.extend(data)
            if len(self.buffer) > 65536:
                raise RuntimeError('Oversized handshake')
        header, rest = bytes(self.buffer).split(b'\r\n\r\n', 1)
        headers = dict(line.split(b':', 1) for line in header.split(b'\r\n')[1:] if b':' in line)
        headers = {k.lower(): v.strip() for k, v in headers.items()}
        expected = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
        if header.split()[1] != b'101' or headers.get(b'sec-websocket-accept') != expected:
            raise RuntimeError('WebSocket handshake rejected')
        self.buffer = bytearray(rest)
        self.sock.settimeout(None)
        self.send_lock = threading.Lock()
        self.closed = False
        self.stdin = self.stdout = self
        self.outgoing = ''

    def exact(self, size):
        while len(self.buffer) < size:
            data = self.sock.recv(min(size - len(self.buffer), 65536))
            if not data:
                raise EOFError()
            self.buffer.extend(data)
        data = bytes(self.buffer[:size]); del self.buffer[:size]
        return data

    def frame(self, opcode, payload):
        if len(payload) > 32 * 1024 * 1024:
            raise ValueError('Frame too large')
        n = len(payload)
        head = bytes([0x80 | opcode])
        head += bytes([0x80 | n]) if n < 126 else (bytes([0xfe]) + struct.pack('!H', n) if n < 65536 else bytes([0xff]) + struct.pack('!Q', n))
        mask = os.urandom(4)
        masked = bytes(v ^ mask[i % 4] for i, v in enumerate(payload))
        with self.send_lock:
            self.sock.sendall(head + mask + masked)

    def __iter__(self):
        parts = bytearray()
        try:
            while not self.closed:
                a, b = self.exact(2)
                if a & 0x70:
                    raise RuntimeError('Unsupported WebSocket extension')
                opcode = a & 15
                n = b & 127
                if n == 126: n = struct.unpack('!H', self.exact(2))[0]
                elif n == 127: n = struct.unpack('!Q', self.exact(8))[0]
                if n > 32 * 1024 * 1024: raise RuntimeError('Frame too large')
                mask = self.exact(4) if b & 128 else None
                data = self.exact(n)
                if mask: data = bytes(v ^ mask[i % 4] for i, v in enumerate(data))
                if opcode == 8: return
                if opcode == 9:
                    self.frame(10, data); continue
                if opcode == 10: continue
                if opcode not in (0, 1): raise RuntimeError('Expected text WebSocket frame')
                parts.extend(data)
                if len(parts) > 32 * 1024 * 1024: raise RuntimeError('Message too large')
                if a & 128:
                    yield parts.decode('utf-8')
                    parts.clear()
        except (EOFError, OSError):
            return

    def write(self, text):
        self.outgoing += text

    def flush(self):
        text, self.outgoing = self.outgoing, ''
        self.frame(1, text.rstrip('\n').encode())

    def terminate(self):
        self.closed = True
        try: self.sock.shutdown(socket.SHUT_RDWR)
        except OSError: pass
        self.sock.close()

    def wait(self, timeout=None): return 0
    def poll(self): return 0 if self.closed else None
    def close(self): self.terminate()

class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.RLock()
        self.changed = threading.Condition(self.lock)
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, epoch TEXT, thread_id TEXT, body TEXT);
        CREATE TABLE IF NOT EXISTS requests(key TEXT PRIMARY KEY, epoch TEXT, thread_id TEXT, body TEXT, status TEXT);
        CREATE TABLE IF NOT EXISTS operations(key TEXT PRIMARY KEY, payload TEXT, result TEXT);
        ''')
        self.db.commit()

    def event(self, epoch, msg):
        p = msg.get('params') or {}
        tid = p.get('threadId') or p.get('thread_id') or (p.get('thread') or {}).get('id')
        with self.lock:
            self.db.execute('INSERT INTO events(epoch,thread_id,body) VALUES(?,?,?)', (epoch, tid, dumps(msg)))
            if 'method' in msg and 'id' in msg:
                self.db.execute('INSERT OR REPLACE INTO requests VALUES(?,?,?,?,?)',
                    (epoch + ':' + dumps(msg['id']), epoch, tid, dumps(msg), 'pending'))
            if msg.get('method') == 'serverRequest/resolved':
                self.db.execute('UPDATE requests SET status=? WHERE key=?',
                    ('resolved', epoch + ':' + dumps(p.get('requestId'))))
            if msg.get('method') == 'turn/completed':
                # A completed turn cannot retain a live approval request.
                turn_id = (p.get('turn') or {}).get('id')
                for key, raw in self.db.execute("SELECT key,body FROM requests WHERE epoch=? AND thread_id=? AND status='pending'", (epoch, tid)).fetchall():
                    if (json.loads(raw).get('params') or {}).get('turnId') == turn_id:
                        self.db.execute("UPDATE requests SET status='ended' WHERE key=?", (key,))
            self.db.commit()
            self.changed.notify_all()

    def disconnected(self, epoch):
        with self.lock:
            self.db.execute("UPDATE requests SET status='unknown_after_disconnect' WHERE epoch=? AND status IN ('pending','response_sent')", (epoch,))
            self.db.commit()
            self.changed.notify_all()

    def poll(self, cursor, tid, limit, summary=False):
        with self.lock:
            high = self.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]
            sql = 'SELECT seq,epoch,thread_id,body FROM events WHERE seq>?'
            args = [cursor]
            if tid:
                sql += ' AND (thread_id=? OR thread_id IS NULL)'
                args.append(tid)
            if summary:
                # Limit retained events, not raw rows. Stop before the first unread
                # key event; only advance to high after exhausting the snapshot.
                rows = []
                for row in self.db.execute(sql + ' ORDER BY seq', args):
                    if summary_event(json.loads(row[3])):
                        rows.append(row)
                        if len(rows) > limit:
                            break
            else:
                rows = self.db.execute(sql + ' ORDER BY seq LIMIT ?', (*args, limit + 1)).fetchall()
            more = len(rows) > limit
            rows = rows[:limit]
            pending = self.db.execute("SELECT key,epoch,thread_id,body,status FROM requests WHERE status IN ('pending','response_sent','unknown_after_disconnect')" + (' AND (thread_id=? OR thread_id IS NULL)' if tid else ''), (tid,) if tid else ()).fetchall()
            # Async questions are agent-message items, not server RPC requests.
            # Derive them from durable events so existing logs need no migration.
            question_messages = {}
            seen_rows = self.db.execute('SELECT seq,epoch,thread_id,body FROM events WHERE thread_id=? ORDER BY seq', (tid,)).fetchall() if tid else []
            for seq, epoch, thread_id, raw in seen_rows:
                event = json.loads(raw)
                item = (event.get('params') or {}).get('item') or {}
                if event.get('method') != 'item/completed':
                    continue
                if item.get('type') == 'userMessage':
                    for entry in question_messages.values():
                        entry['status'] = 'followup_observed_answer_unconfirmed'
                if item.get('type') == 'agentMessage' and item.get('questions'):
                    question_messages[item['id']] = {'item_id': item['id'], 'thread_id': thread_id,
                        'turn_id': (event.get('params') or {}).get('turnId'), 'questions': item['questions'],
                        'text': item.get('text'), 'status': 'awaiting_reply', 'cursor': seq}
            return {'cursor': rows[-1][0] if more else high, 'has_more': more,
                    'question_messages': list(question_messages.values()),
                    'events': [{'cursor': x[0], 'epoch': x[1], 'thread_id': x[2], 'event': json.loads(x[3])} for x in rows],
                    'pending_requests': [{'key': x[0], 'epoch': x[1], 'thread_id': x[2], 'request': json.loads(x[3]), 'status': x[4]} for x in pending]}

class Bridge:
    def __init__(self, store, command=None):
        self.store = store
        with store.lock:
            store.db.execute("UPDATE requests SET status='unknown_after_disconnect' WHERE status IN ('pending','response_sent')")
            store.db.commit()
        self.epoch = str(uuid.uuid4())
        self.alive = True
        self.pending = {}
        self.guard = threading.RLock()
        self.write_lock = threading.Lock()
        self.mutation_lock = threading.Lock()
        self.counter = 0
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1) if command else UnixWebSocket(HOME / 'app-server-control/app-server-control.sock')
        threading.Thread(target=self.reader, daemon=True).start()
        self.info = self.rpc('initialize', {'clientInfo': {'name': 'codex_skill_bridge', 'version': '1.0.0'}, 'capabilities': {'experimentalApi': True}})
        self.write({'method': 'initialized', 'params': {}})
        self.store.event(self.epoch, {'method': 'bridge/connected', 'params': {'backend': 'shared Codex Unix WebSocket'}})

    def write(self, obj):
        with self.write_lock:
            if not self.alive:
                raise RuntimeError('Backend disconnected; inspect original thread before reconnecting or retrying mutations.')
            self.proc.stdin.write(dumps(obj) + '\n')
            self.proc.stdin.flush()

    def reader(self):
        try:
            for line in self.proc.stdout:
                msg = json.loads(line)
                if 'method' in msg:
                    self.store.event(self.epoch, msg)
                elif 'id' in msg:
                    with self.guard:
                        waiter = self.pending.get(msg['id'])
                    if waiter:
                        waiter.put(msg)
                    else:
                        self.store.event(self.epoch, {'method': 'bridge/lateResponse', 'params': {'response': msg}})
        finally:
            self.alive = False
            self.store.disconnected(self.epoch)
            self.store.event(self.epoch, {'method': 'bridge/disconnected', 'params': {}})
            with self.guard:
                for waiter in self.pending.values():
                    waiter.put({'error': {'message': 'Backend disconnected; mutation outcome may be unknown.'}})

    def rpc(self, method, params):
        with self.guard:
            self.counter += 1
            rid = self.counter
            waiter = queue.Queue()
            self.pending[rid] = waiter
        try:
            self.write({'id': rid, 'method': method, 'params': params})
            try:
                return waiter.get(timeout=40)
            except queue.Empty:
                return {'error': {'message': 'RPC timeout; outcome unknown. Do not resubmit. Inspect lateResponse events and original thread.'}}
        finally:
            with self.guard:
                self.pending.pop(rid, None)

    def operation(self, req, run):
        key = req.get('operation_id')
        if not key:
            raise ValueError('Mutations require a stable --operation-id; reuse it after a client timeout.')
        payload = dumps(req)
        with self.mutation_lock:
            with self.store.lock:
                row = self.store.db.execute('SELECT payload,result FROM operations WHERE key=?', (key,)).fetchone()
                if row:
                    if row[0] != payload:
                        raise ValueError('Operation ID was already used with different arguments.')
                    return json.loads(row[1]) if row[1] else {'error': 'Previous outcome unknown; reconcile before any new mutation.'}
                self.store.db.execute('INSERT INTO operations VALUES(?,?,NULL)', (key, payload))
                self.store.db.commit()
            result = run()
            with self.store.lock:
                self.store.db.execute('UPDATE operations SET result=? WHERE key=?', (dumps(result), key))
                self.store.db.commit()
            return result

    def handle(self, req):
        op = req['op']
        if op == 'status':
            return {'connected': self.alive, 'epoch': self.epoch, 'codex_home': str(HOME), 'initialize': self.info}
        if op == 'poll':
            wait = float(req.get('wait', 2))
            if not 2 <= wait <= 50:
                raise ValueError('wait must be 2..50 seconds; choose below your client tool timeout.')
            tid = req.get('thread')
            until_idle = req.get('until_idle', False)
            if until_idle and not tid:
                raise ValueError('until-idle requires a target --thread.')
            deadline = time.monotonic() + wait
            with self.store.changed:
                while True:
                    result = self.store.poll(int(req.get('cursor', 0)), tid,
                        min(max(int(req.get('limit', 100)), 1), 500), req.get('summary', False))
                    completed = any(x['thread_id'] == tid and x['event'].get('method') == 'turn/completed'
                                    for x in result['events'])
                    ready = (completed if until_idle else bool(result['events']))
                    remaining = deadline - time.monotonic()
                    if (ready or result['has_more'] or result['pending_requests'] or
                            result['question_messages'] or not self.alive or remaining <= 0):
                        break
                    # Check and wait under the event writer's lock to avoid lost wakes.
                    self.store.changed.wait(remaining)
            result.update(connected=self.alive, epoch=self.epoch, coverage='Events observed by this bridge connection; not a complete historical request inventory.')
            return result
        if op == 'rpc':
            method = req['method']
            if method not in RPC_METHODS:
                raise ValueError('Unsupported method')
            params = req.get('params', {})
            run = lambda: self.rpc(method, params)
            return self.operation(req, run) if method in MUTATIONS else run()
        if op == 'respond':
            if not req.get('human_confirmed'):
                raise ValueError('An explicit human answer is required; do not infer approval.')
            def run():
                with self.store.lock:
                    row = self.store.db.execute('SELECT epoch,body,status FROM requests WHERE key=?', (req['request_key'],)).fetchone()
                if not row or row[0] != self.epoch or row[2] != 'pending':
                    raise ValueError('Request is stale, resolved, or from a disconnected transport; refresh first.')
                self.write({'id': json.loads(row[1])['id'], 'result': req['result']})
                with self.store.lock:
                    self.store.db.execute("UPDATE requests SET status='response_sent' WHERE key=? AND status='pending'", (req['request_key'],))
                    self.store.db.commit()
                return {'status': 'response_sent', 'note': 'Transport write succeeded; observe server events to confirm resolution.'}
            return self.operation(req, run)
        raise ValueError('Unknown operation')

def serve():
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = open(STATE / 'bridge.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    # An existing managed daemon is required. Never silently create an isolated engine.
    if not (HOME / 'app-server-control/app-server-control.sock').exists():
        raise RuntimeError('Shared daemon socket is absent. Start the intended daemon explicitly first.')
    bridge = Bridge(Store(STATE / 'events.sqlite'))
    if 'error' in bridge.info:
        raise RuntimeError(dumps(bridge.info))
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            try:
                data = self.rfile.readline(8 * 1024 * 1024)
                result = bridge.handle(json.loads(data))
            except Exception as exc:
                result = {'error': str(exc)}
            try:
                self.wfile.write((dumps(result) + '\n').encode())
            except BrokenPipeError:
                pass  # Result is retained for mutation retries with the same operation ID.
    class Server(socketserver.ThreadingUnixStreamServer):
        daemon_threads = True
    SOCK.unlink(missing_ok=True)
    try:
        with Server(str(SOCK), Handler) as server:
            os.chmod(SOCK, 0o600)
            server.serve_forever()
    finally:
        bridge.proc.terminate()
        SOCK.unlink(missing_ok=True)

def client(req):
    with socket.socket(socket.AF_UNIX) as conn:
        conn.settimeout(58)
        conn.connect(str(SOCK))
        conn.sendall((dumps(req) + '\n').encode())
        return json.loads(conn.makefile('r').readline())

def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('serve')
    sub.add_parser('start')
    sub.add_parser('status')
    q = sub.add_parser('poll')
    q.add_argument('--thread')
    q.add_argument('--cursor', type=int, default=0)
    q.add_argument('--wait', type=float, required=True)
    q.add_argument('--limit', type=int, default=100)
    q.add_argument('--until-idle', action='store_true', help='Wait for target thread completion, requests or questions')
    q.add_argument('--summary', action='store_true', help='Return key events without deltas or usage notifications')
    r = sub.add_parser('rpc')
    r.add_argument('--method', choices=sorted(RPC_METHODS), required=True)
    r.add_argument('--params-file', required=True, help='JSON file, or - for stdin')
    r.add_argument('--operation-id')
    r = sub.add_parser('respond')
    r.add_argument('--request-key', required=True)
    r.add_argument('--result-file', required=True)
    r.add_argument('--human-confirmed', action='store_true')
    r.add_argument('--operation-id', required=True)
    a = vars(p.parse_args())
    cmd = a.pop('cmd')
    if cmd == 'serve':
        serve()
        return
    if cmd == 'start':
        try:
            print(dumps(client({'op': 'status'})))
            return
        except (OSError, ValueError):
            pass
        STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
        with open(STATE / 'bridge.log', 'a') as log:
            proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'serve'], stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        for _ in range(100):
            try:
                print(dumps(client({'op': 'status'})))
                return
            except (OSError, ValueError):
                if proc.poll() is not None:
                    raise RuntimeError('Bridge exited; inspect ' + str(STATE / 'bridge.log'))
                time.sleep(.1)
        raise RuntimeError('Startup still pending; inspect status/log. Do not start another backend.')
    for key, target in [('params_file', 'params'), ('result_file', 'result')]:
        if key in a:
            path = a.pop(key)
            a[target] = json.load(sys.stdin) if path == '-' else json.loads(Path(path).read_text())
    print(dumps(client({'op': cmd, **a})))

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(dumps({'error': str(exc)}))
        sys.exit(1)
