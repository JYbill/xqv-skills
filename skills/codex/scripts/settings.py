#!/usr/bin/env python3
"""Update explicit thread model settings over a short shared-server connection."""
import argparse
import json
from pathlib import Path
import sys

from config import HOME, dumps
from transport import UnixWebSocket


def validate_settings(params):
    if not isinstance(params, dict):
        raise ValueError('Settings must be a JSON object.')
    if set(params) - {'threadId', 'model', 'effort', 'serviceTier'}:
        raise ValueError('Only threadId, model, effort and serviceTier are supported.')
    if not isinstance(params.get('threadId'), str) or not params['threadId'].strip():
        raise ValueError('A non-empty threadId is required.')
    if not (set(params) - {'threadId'}):
        raise ValueError('Specify at least one explicit setting.')
    for key in ('model', 'effort'):
        if key in params and (not isinstance(params[key], str) or not params[key].strip()):
            raise ValueError(f'{key} must be a non-empty string when specified.')
    if 'serviceTier' in params and params['serviceTier'] not in ('priority', None):
        raise ValueError('serviceTier must be "priority" (Fast) or null (normal); omit to preserve.')


def update_settings(params):
    validate_settings(params)
    ws = UnixWebSocket(HOME / 'app-server-control/app-server-control.sock')
    ws.sock.settimeout(40)
    messages = iter(ws)
    def rpc(rid, method, body):
        ws.write(dumps({'id': rid, 'method': method, 'params': body}) + '\n')
        ws.flush()
        for raw in messages:
            msg = json.loads(raw)
            if msg.get('id') == rid and 'method' not in msg:
                if 'error' in msg:
                    raise RuntimeError(dumps(msg['error']))
                return msg['result']
        raise RuntimeError('Connection closed; inspect original thread before retrying or queueing.')
    try:
        rpc(1, 'initialize', {'clientInfo': {'name': 'codex_skill_settings', 'version': '1'},
                              'capabilities': {'experimentalApi': True}})
        ws.write(dumps({'method': 'initialized', 'params': {}}) + '\n')
        ws.flush()
        # Resume loads the existing thread without overriding its settings or sending input.
        rpc(2, 'thread/resume', {'threadId': params['threadId'], 'excludeTurns': True})
        rpc(3, 'thread/settings/update', params)
        effective = rpc(4, 'thread/resume', {'threadId': params['threadId'], 'excludeTurns': True})
        for key, response_key in [('model', 'model'), ('effort', 'reasoningEffort'), ('serviceTier', 'serviceTier')]:
            if key not in params:
                continue
            actual = effective.get(response_key)
            matches = actual == params[key]
            # The server canonicalizes a cleared tier to "default" on current versions.
            if key == 'serviceTier' and params[key] is None:
                matches = actual in (None, 'default')
            if response_key not in effective or not matches:
                raise RuntimeError(f'Setting {key} did not match server readback; do not queue.')
        return {'threadId': params['threadId'], 'verified': True,
                **{key: effective[key] for key in ('model', 'reasoningEffort', 'serviceTier') if key in effective}}
    finally:
        ws.terminate()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--params-file', required=True, help='Private JSON file containing explicit settings')
    args = parser.parse_args()
    try:
        print(dumps(update_settings(json.loads(Path(args.params_file).read_text()))))
        return 0
    except Exception as exc:
        print(dumps({'error': str(exc), 'note': 'Do not queue until settings are reconciled; no automatic retry.'}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
