"""SQLite event history, request state and event-batch waiting."""
import json
import sqlite3
import threading
import time

from config import POLL_TIMEOUT, dumps

COVERAGE = 'Events observed by this bridge connection; not a complete historical request inventory.'

def key_event(msg):
    """Keep completed content, lifecycle, requests and bridge diagnostics."""
    method = msg.get('method', '')
    item = (msg.get('params') or {}).get('item') or {}
    if method in {'item/started', 'item/completed'} and empty_reasoning(item):
        return False
    return ('id' in msg or method in {'item/completed', 'thread/status/changed',
            'turn/started', 'turn/completed', 'serverRequest/resolved', 'error'} or
            method.startswith('bridge/') or bool((msg.get('params') or {}).get('questions')))

def empty_reasoning(item):
    return item.get('type') == 'reasoning' and not item.get('summary') and not item.get('content')

def output_item(item, full):
    if full:
        return item
    if item.get('type') == 'commandExecution':
        item = {key: value for key, value in item.items() if key in {
            'id', 'type', 'command', 'cwd', 'status', 'exitCode', 'durationMs', 'aggregatedOutput'}}
        output = item.get('aggregatedOutput')
        if isinstance(output, str) and len(output) > 200:
            item['aggregatedOutput'] = output[:200] + f'…（共 {len(output)} 字符，已截断）'
    elif item.get('type') == 'userMessage':
        content = item.get('content') or []
        length = len(content) if isinstance(content, str) else sum(
            len(part.get('text', '')) for part in content if isinstance(part, dict))
        item = {key: item[key] for key in ('id', 'type') if key in item}
        item.update(text='收到用户消息', character_count=length)
    return item

def output_event(row, full, delivered):
    seq, epoch, tid, raw = row
    event = json.loads(raw)
    params = event.get('params') or {}
    if isinstance(params.get('item'), dict):
        params['item'] = output_item(params['item'], full)
    if event.get('method') == 'turn/completed':
        turn = params.get('turn') or {}
        if 'items' in turn:
            items = [output_item(item, full) for item in (turn['items'] or [])
                     if not empty_reasoning(item) and not (
                         item.get('type') == 'agentMessage' and item.get('id') is not None and
                         (epoch, tid, turn.get('id'), item['id']) in delivered)]
            if items:
                turn['items'] = items
            else:
                del turn['items']
    return {'cursor': seq, 'epoch': epoch, 'thread_id': tid, 'event': event}

def urgent_event(msg):
    params = msg.get('params') or {}
    return ('id' in msg or msg.get('method') == 'turn/completed' or
            bool(params.get('questions')) or bool((params.get('item') or {}).get('questions')))

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

    def poll(self, cursor, tid, limit, full=False):
        with self.lock:
            high = self.db.execute('SELECT coalesce(max(seq),0) FROM events').fetchone()[0]
            sql = 'SELECT seq,epoch,thread_id,body FROM events WHERE seq>?'
            args = [cursor]
            if tid:
                sql += ' AND (thread_id=? OR thread_id IS NULL)'
                args.append(tid)
            # Scan the snapshot for urgent events even beyond the normal page.
            rows = []
            urgent = []
            more = False
            for row in self.db.execute(sql + ' ORDER BY seq', args):
                event = json.loads(row[3])
                if not key_event(event):
                    continue
                if len(rows) < limit:
                    rows.append(row)
                else:
                    more = True
                if urgent_event(event):
                    urgent.append(row)
            pending = self.db.execute("SELECT key,epoch,thread_id,body,status FROM requests WHERE status IN ('pending','response_sent','unknown_after_disconnect')" + (' AND (thread_id=? OR thread_id IS NULL)' if tid else ''), (tid,) if tid else ()).fetchall()
            # Async questions are agent-message items, not server RPC requests.
            # Derive them from durable events so existing logs need no migration.
            question_messages = {}
            seen_rows = self.db.execute('SELECT seq,epoch,thread_id,body FROM events WHERE thread_id=? ORDER BY seq', (tid,)).fetchall() if tid else []
            delivered = set()
            page_cursor = rows[-1][0] if more else high
            for seq, epoch, thread_id, raw in seen_rows:
                event = json.loads(raw)
                item = (event.get('params') or {}).get('item') or {}
                if event.get('method') == 'turn/started':
                    # A later turn supersedes questions from the earlier interaction.
                    question_messages.clear()
                if event.get('method') != 'item/completed':
                    continue
                if seq <= page_cursor and item.get('type') == 'agentMessage' and item.get('id') is not None:
                    delivered.add((epoch, thread_id, (event.get('params') or {}).get('turnId'), item['id']))
                if item.get('type') == 'userMessage':
                    for entry in question_messages.values():
                        entry['status'] = 'followup_observed_answer_unconfirmed'
                        entry['followup_cursor'] = seq
                if item.get('type') == 'agentMessage' and item.get('questions'):
                    question_messages[item['id']] = {'item_id': item['id'], 'thread_id': thread_id,
                        'turn_id': (event.get('params') or {}).get('turnId'), 'questions': item['questions'],
                        'text': item.get('text'), 'status': 'awaiting_reply', 'cursor': seq}
            return {'cursor': rows[-1][0] if more else high, 'has_more': more,
                    'question_messages': list(question_messages.values()),
                    'urgent_events': [{'cursor': x[0], 'method': json.loads(x[3])['method']}
                                      if x[0] <= page_cursor else output_event(x, full, delivered) for x in urgent],
                    'events': [output_event(x, full, delivered) for x in rows],
                    'pending_requests': [{'key': x[0], 'epoch': x[1], 'thread_id': x[2], 'request': json.loads(x[3]), 'status': x[4]} for x in pending]}

def poll_events(store, req, connected, epoch):
    """Read a batch, waiting only while the supplied connection is alive."""
    if any(key in req for key in ('wait', 'limit', 'until_idle')):
        raise ValueError('Use event_limit instead of wait, limit or until_idle.')
    limit = req.get('event_limit', 50)
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError('event_limit must be an integer from 1 to 200.')
    tid = req.get('thread')
    if not isinstance(tid, str) or not tid.strip():
        raise ValueError('poll requires a non-empty Codex thread ID (--thread).')
    deadline = time.monotonic() + POLL_TIMEOUT
    with store.changed:
        while True:
            result = store.poll(int(req.get('cursor', 0)), tid, limit, req.get('full', False))
            remaining = deadline - time.monotonic()
            pending = any(x['status'] == 'pending' and x['epoch'] == epoch
                          for x in result['pending_requests'])
            questions = any(x['status'] == 'awaiting_reply' or
                            x.get('followup_cursor', 0) > int(req.get('cursor', 0))
                            for x in result['question_messages'])
            if result['urgent_events'] or pending or questions:
                reason = 'attention'
            elif not connected():
                reason = 'disconnected'
            elif len(result['events']) >= limit:
                reason = 'event_limit'
            elif remaining <= 0:
                reason = 'timeout'
            else:
                reason = None
            if reason:
                result['return_reason'] = reason
                break
            # Check and wait under the event writer's lock to avoid lost wakes.
            store.changed.wait(remaining)
    result.update(connected=connected(), epoch=epoch)
    events = result['events'] + [x for x in result['urgent_events'] if 'event' in x]
    failed = any(x['event'].get('method') in {'error', 'bridge/disconnected'} or
                 (x['event'].get('params') or {}).get('error') or
                 ((x['event'].get('params') or {}).get('turn') or {}).get('error')
                 for x in events)
    if req.get('full') or 'error' in result or failed:
        result['coverage'] = COVERAGE
    for key in ('question_messages', 'pending_requests', 'urgent_events'):
        if not result[key]:
            del result[key]
    return result
