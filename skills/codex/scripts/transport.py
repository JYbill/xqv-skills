"""WebSocket transport for the existing Codex App Server."""
import base64
import hashlib
import os
import socket
import struct
import threading

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
