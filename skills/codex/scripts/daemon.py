"""Receive Codex events and serve local bridge requests."""
import fcntl
import json
import os
import queue
import socketserver
import subprocess
import threading
import uuid

from config import HOME, STATE, SOCK, RPC_METHODS, MUTATIONS, dumps
from store import Store, poll_events
from transport import UnixWebSocket

class Bridge:
    def __init__(self, store, command=None):
        self.store = store
        with store.lock:
            store.db.execute("UPDATE requests SET status='unknown_after_disconnect' WHERE status IN ('pending','response_sent')")
            store.db.commit()
        self.epoch = str(uuid.uuid4())
        self.alive = True
        self.completed = threading.Event()
        self.target_thread = None
        self.target_turn = None
        self.pending = {}
        self.guard = threading.RLock()
        self.write_lock = threading.Lock()
        self.mutation_lock = threading.Lock()
        self.counter = 0
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1) if command else UnixWebSocket(HOME / 'app-server-control/app-server-control.sock')
        self.reader_thread = threading.Thread(target=self.reader, daemon=True)
        self.reader_thread.start()
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
                    params = msg.get('params') or {}
                    tid = params.get('threadId') or params.get('thread_id')
                    turn_id = (params.get('turn') or {}).get('id')
                    with self.guard:
                        if tid and tid == self.target_thread:
                            if msg.get('method') == 'turn/started':
                                self.target_turn = turn_id
                            if (msg.get('method') == 'turn/completed' and turn_id and
                                    (self.target_turn is None or self.target_turn == turn_id)):
                                self.completed.set()
                                break
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
        # Subscription belongs to a connection, unlike persisted thread creation.
        if req.get('method') == 'thread/resume':
            key = self.epoch + ':' + key
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
            return poll_events(self.store, req, lambda: self.alive, self.epoch)
        if op == 'rpc':
            method = req['method']
            if method not in RPC_METHODS:
                raise ValueError('Unsupported method')
            params = req.get('params', {})
            def run():
                if method in ('thread/start', 'thread/resume'):
                    with self.guard:
                        target = params.get('threadId')
                        if method == 'thread/resume' and (not isinstance(target, str) or not target.strip()):
                            raise ValueError('thread/resume requires a non-empty threadId.')
                        if self.target_thread and (method == 'thread/start' or target != self.target_thread):
                            raise ValueError('Bridge already tracks another thread; use a separate bridge state directory.')
                        if method == 'thread/resume':
                            self.target_thread = target
                result = self.rpc(method, params)
                if method == 'thread/start' and 'result' in result:
                    with self.guard:
                        self.target_thread = result['result']['thread']['id']
                return result
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
        daemon_threads = False
    SOCK.unlink(missing_ok=True)
    try:
        with Server(str(SOCK), Handler) as server:
            os.chmod(SOCK, 0o600)
            server.timeout = .2
            while bridge.alive and not bridge.completed.is_set():
                server.handle_request()
    finally:
        bridge.proc.terminate()
        bridge.proc.wait(timeout=3)
        bridge.reader_thread.join(timeout=3)
        SOCK.unlink(missing_ok=True)
        if not bridge.reader_thread.is_alive():
            bridge.store.db.close()
