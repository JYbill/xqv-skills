"""Settings protocol tests; no model requests or real thread mutations."""
import json
import unittest
from unittest.mock import patch
from settings import update_settings


class FakeSocket:
    def settimeout(self, timeout):
        pass


class FakeServer:
    def __init__(self, path):
        self.sock = FakeSocket()
        self.state = {'model': 'test-model', 'reasoningEffort': 'medium', 'serviceTier': 'priority'}
        self.requests = []
        self.responses = []
        self.closed = False
        self.error = False
        self.ignore = False
        self.disconnect = False

    def write(self, text):
        self.outgoing = json.loads(text)

    def flush(self):
        msg = self.outgoing
        self.requests.append(msg)
        if 'id' not in msg:
            return
        method = msg['method']
        if method == 'thread/settings/update':
            if self.disconnect:
                return
            if self.error:
                self.responses.append(json.dumps({'id': msg['id'], 'error': {'message': 'unsupported tier'}}))
                return
            if not self.ignore:
                for key, field in [('model', 'model'), ('effort', 'reasoningEffort'), ('serviceTier', 'serviceTier')]:
                    if key in msg['params']:
                        self.state[field] = ('default' if key == 'serviceTier' and msg['params'][key] is None else msg['params'][key])
        self.responses.append(json.dumps({'id': msg['id'], 'result': dict(self.state)}))

    def __iter__(self):
        return self

    def __next__(self):
        if not self.responses:
            raise StopIteration
        return self.responses.pop(0)

    def terminate(self):
        self.closed = True


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.server = FakeServer(None)
        self.patch = patch('settings.UnixWebSocket', return_value=self.server)
        self.factory = self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_fast_normal_and_omission_preserve_independent_settings(self):
        for params, effort, tier in [
            ({'effort': 'high', 'serviceTier': 'priority'}, 'high', 'priority'),
            ({'serviceTier': None}, 'high', 'default'),
            ({'effort': 'low'}, 'low', 'default'),
            ({'serviceTier': 'priority'}, 'low', 'priority'),
            ({'effort': 'high'}, 'high', 'priority'),
        ]:
            with self.subTest(params=params):
                result = update_settings({'threadId': 't', **params})
                self.assertTrue(result['verified'])
                self.assertEqual(result['reasoningEffort'], effort)
                self.assertEqual(result['serviceTier'], tier)
                request = self.server.requests[-2]
                self.assertEqual(request['method'], 'thread/settings/update')
                self.assertEqual(request['params'], {'threadId': 't', **params})
        self.assertFalse(any(r['method'] in ('turn/start', 'thread/queue/add') for r in self.server.requests))
        self.assertTrue(self.server.closed)

    def test_model_override_is_verified(self):
        self.assertEqual(update_settings({'threadId': 't', 'model': 'other'})['model'], 'other')

    def test_invalid_or_unrelated_settings_never_connect(self):
        for params in [None, {}, {'threadId': 't'}, {'threadId': '', 'effort': 'high'},
                       {'threadId': 't', 'effort': None}, {'threadId': 't', 'model': ''},
                       {'threadId': 't', 'serviceTier': 'fast'},
                       {'threadId': 't', 'approvalPolicy': 'never'}]:
            with self.subTest(params=params), self.assertRaises(ValueError):
                update_settings(params)
        self.factory.assert_not_called()

    def test_server_error_stops_without_retry(self):
        self.server.error = True
        with self.assertRaisesRegex(RuntimeError, 'unsupported tier'):
            update_settings({'threadId': 't', 'serviceTier': None})
        self.assertEqual(sum(r['method'] == 'thread/settings/update' for r in self.server.requests), 1)
        self.assertTrue(self.server.closed)

    def test_silent_ignored_update_fails_readback(self):
        self.server.ignore = True
        for params in [{'effort': 'high'}, {'serviceTier': None}]:
            with self.subTest(params=params), self.assertRaisesRegex(RuntimeError, 'did not match'):
                update_settings({'threadId': 't', **params})
        self.assertTrue(self.server.closed)

    def test_disconnect_does_not_retry(self):
        self.server.disconnect = True
        with self.assertRaisesRegex(RuntimeError, 'Connection closed'):
            update_settings({'threadId': 't', 'effort': 'high'})
        self.assertEqual(sum(r['method'] == 'thread/settings/update' for r in self.server.requests), 1)
        self.assertTrue(self.server.closed)


if __name__ == '__main__':
    unittest.main()
