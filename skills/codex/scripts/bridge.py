#!/usr/bin/env python3
"""CLI entry point for the Codex event bridge."""
import argparse
import json
import os
from pathlib import Path
import sys

from client import client, start
from config import RPC_METHODS, dumps
from store import COVERAGE

def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('serve')
    sub.add_parser('start')
    sub.add_parser('status')
    q = sub.add_parser('poll')
    q.add_argument('--thread', required=True, help='Codex thread ID to read')
    q.add_argument('--full', action='store_true', help='Include complete item content and coverage')
    q.add_argument('--cursor', type=int, default=0)
    q.add_argument('--event-limit', type=int, choices=range(1, 201), default=50,
                   metavar='1..200', help='Wait for this many key events (default: 50); urgent events return early')
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
        from daemon import serve
        serve()
        return
    if cmd == 'start':
        try:
            result = start()
        except Exception as exc:
            result = {'connected': False, 'error': str(exc)}
        output = {'connected': result.get('connected', False), 'epoch': result.get('epoch')}
        if 'error' in result:
            output['error'] = result['error']
        print(dumps(output))
        return 0 if result.get('connected') and 'error' not in result else 1
    for key, target in [('params_file', 'params'), ('result_file', 'result')]:
        if key in a:
            path = a.pop(key)
            a[target] = json.load(sys.stdin) if path == '-' else json.loads(Path(path).read_text())
    try:
        result = client({'op': cmd, **a})
    except Exception as exc:
        if cmd != 'poll':
            raise
        result = {'error': str(exc)}
    if cmd == 'poll' and 'error' in result:
        result['coverage'] = COVERAGE
    print(dumps(result))
    return 1 if 'error' in result or (cmd == 'status' and not result.get('connected')) else 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(dumps({'error': str(exc)}))
        sys.exit(1)
