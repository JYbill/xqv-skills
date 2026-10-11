"""Offline protocol tests; does not contact a model or mutate a real Codex thread."""
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from bridge import Bridge, Store, summary_event

FAKE = '''import sys,json
for line in sys.stdin:
 m=json.loads(line)
 if 'method' not in m: continue
 if 'id' not in m: continue
 method=m['method'];p=m['params']
 if method=='initialize': result={'userAgent':'fake'}
 elif method=='thread/start': result={'thread':{'id':'test-thread'},'received_params':p}
 else: result={'turn':{'id':'test-turn'}}
 print(json.dumps({'id':m['id'],'result':result}),flush=True)
 if method=='turn/start':
  print(json.dumps({'method':'item/agentMessage/delta','params':{'threadId':'test-thread','delta':'working'}}),flush=True)
  print(json.dumps({'id':99,'method':'item/commandExecution/requestApproval','params':{'threadId':'test-thread','turnId':'test-turn','command':'example'}}),flush=True)
'''

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name)/'state.sqlite')
    def tearDown(self):
        self.store.db.close()
        self.tmp.cleanup()
    def test_pagination_and_thread_filter(self):
        for i in range(5):
            self.store.event('e',{'method':'item/x','params':{'threadId':'a' if i%2==0 else 'b','i':i}})
        a=self.store.poll(0,'a',2)
        self.assertTrue(a['has_more'])
        b=self.store.poll(a['cursor'],'a',2)
        self.assertEqual([x['event']['params']['i'] for x in a['events']+b['events']],[0,2,4])
        self.assertEqual(self.store.poll(b['cursor'],'a',2)['events'],[])
    def test_async_question_survives_cursor(self):
        self.store.event('e',{'method':'item/completed','params':{'threadId':'t','turnId':'v','item':{'type':'agentMessage','id':'q','questions':[{'title':'Choose?','options':['a','b']}],'text':'Choose?'}}})
        r=self.store.poll(0,'t',10)
        self.assertEqual(r['pending_requests'],[])
        self.assertEqual(self.store.poll(r['cursor'],'t',10)['question_messages'][0]['status'],'awaiting_reply')
        self.store.event('e',{'method':'item/completed','params':{'threadId':'t','item':{'type':'userMessage','id':'u'}}})
        self.assertEqual(self.store.poll(r['cursor'],'t',10)['question_messages'][0]['status'],'followup_observed_answer_unconfirmed')
    def poll_bridge(self):
        # Poll only needs a store and connection state, not a backend process.
        b=Bridge.__new__(Bridge)
        b.store=self.store; b.alive=True; b.epoch='e'
        return b
    def emit_later(self, messages):
        def emit():
            for delay, msg in messages:
                time.sleep(delay)
                self.store.event('e',msg)
        worker=threading.Thread(target=emit)
        worker.start()
        self.addCleanup(worker.join)
    def test_summary_pagination_preserves_key_events(self):
        noise=['item/agentMessage/delta','account/rateLimits/updated',
               'thread/tokenUsage/updated','skills/changed']
        for i in range(6):
            for method in noise*40:
                self.store.event('e',{'method':method,'params':{'threadId':'t'}})
            self.store.event('e',{'method':'item/completed','params':{'threadId':'t','item':{'id':str(i)}}})
        self.store.event('e',{'method':'turn/completed','params':{'threadId':'other'}})
        self.store.event('e',{'method':'turn/completed','params':{'threadId':'t'}})
        expected=self.store.poll(0,'t',2000)['events']
        expected=[x for x in expected if summary_event(x['event'])]
        cursor=0; actual=[]
        while True:
            started=time.monotonic()
            page=self.poll_bridge().handle({'op':'poll','thread':'t','cursor':cursor,
                'limit':2,'wait':50,'summary':True,'until_idle':True})
            self.assertLess(time.monotonic()-started,1)
            actual.extend(page['events']); cursor=page['cursor']
            if not page['has_more']: break
            self.assertEqual(cursor,page['events'][-1]['cursor'])
        self.assertEqual(actual,expected)
        self.assertEqual(self.store.poll(cursor,'t',2)['events'],[])
    def test_poll_wakes_on_new_event_and_existing_backlog(self):
        b=self.poll_bridge()
        self.emit_later([(.1,{'method':'item/completed','params':{'threadId':'t'}})])
        started=time.monotonic()
        r=b.handle({'op':'poll','thread':'t','cursor':0,'wait':50})
        self.assertLess(time.monotonic()-started,1)
        self.assertEqual(len(r['events']),1)
        started=time.monotonic()
        self.assertEqual(b.handle({'op':'poll','thread':'t','wait':50})['events'],r['events'])
        self.assertLess(time.monotonic()-started,1)
    def test_until_idle_ignores_progress_and_other_thread_completion(self):
        self.emit_later([(.05,{'method':'turn/completed','params':{'threadId':'other'}}),
            (.05,{'method':'thread/status/changed','params':{'threadId':'t','status':{'type':'idle'}}}),
            (.05,{'method':'item/completed','params':{'threadId':'t'}}),
            (.1,{'method':'turn/completed','params':{'threadId':'t'}})])
        started=time.monotonic()
        r=self.poll_bridge().handle({'op':'poll','thread':'t','wait':50,'until_idle':True,'summary':True})
        self.assertGreaterEqual(time.monotonic()-started,.2)
        self.assertLess(time.monotonic()-started,1)
        self.assertEqual(r['events'][-1]['event']['method'],'turn/completed')
        self.assertTrue(all(x['thread_id']=='t' for x in r['events']))
    def test_until_idle_wakes_on_request_and_question(self):
        for msg in [
            {'id':8,'method':'item/tool/requestUserInput','params':{'threadId':'request'}},
            {'method':'item/completed','params':{'threadId':'question','turnId':'v',
                'item':{'type':'agentMessage','id':'q','questions':[{'title':'Choose?'}]}}}]:
            tid=msg['params']['threadId']
            self.emit_later([(.1,msg)])
            started=time.monotonic()
            r=self.poll_bridge().handle({'op':'poll','thread':tid,'wait':50,'until_idle':True,'summary':True})
            self.assertLess(time.monotonic()-started,1)
            self.assertTrue(r['pending_requests'] or r['question_messages'])
    def test_poll_timeout_and_wait_validation(self):
        b=self.poll_bridge()
        for wait in [1,51,float('nan')]:
            with self.assertRaises(ValueError): b.handle({'op':'poll','wait':wait})
        with self.assertRaises(ValueError): b.handle({'op':'poll','wait':2,'until_idle':True})
        # Noise alone does not return a summary or make it wait beyond the deadline.
        self.emit_later([(.1,{'method':'skills/changed','params':{}})])
        started=time.monotonic()
        r=b.handle({'op':'poll','thread':'t','wait':2,'until_idle':True,'summary':True})
        self.assertGreaterEqual(time.monotonic()-started,2)
        self.assertLess(time.monotonic()-started,2.5)
        self.assertEqual(r['events'],[])
        self.assertEqual(r['cursor'],1)
    def test_request_lifecycle(self):
        self.store.event('e',{'id':5,'method':'item/tool/requestUserInput','params':{'threadId':'t'}})
        self.assertEqual(len(self.store.poll(0,'t',10)['pending_requests']),1)
        self.store.event('e',{'method':'serverRequest/resolved','params':{'threadId':'t','requestId':5}})
        self.assertEqual(self.store.poll(0,'t',10)['pending_requests'],[])
        self.store.event('e',{'id':6,'method':'item/tool/requestUserInput','params':{'threadId':'t'}})
        self.store.disconnected('e')
        self.assertEqual(self.store.poll(0,'t',10)['pending_requests'][0]['status'],'unknown_after_disconnect')
    def test_bridge_defaults_idempotency_and_human_gate(self):
        path=Path(self.tmp.name)/'fake.py';path.write_text(FAKE)
        b=Bridge(self.store,[sys.executable,str(path)])
        try:
            req={'op':'rpc','method':'thread/start','params':{'cwd':'/tmp'},'operation_id':'one'}
            first=b.handle(req)
            self.assertEqual(first['result']['received_params'],{'cwd':'/tmp'})
            self.assertEqual(b.handle(req),first)
            with self.assertRaises(ValueError):b.handle({**req,'params':{'cwd':'/elsewhere'}})
            b.handle({'op':'rpc','method':'turn/start','params':{'threadId':'test-thread','input':[]},'operation_id':'two'})
            for _ in range(100):
                rows=self.store.poll(0,'test-thread',50)['pending_requests']
                if rows: break
                time.sleep(.01)
            self.assertEqual(len(rows),1)
            with self.assertRaises(ValueError):
                b.handle({'op':'respond','request_key':rows[0]['key'],'result':{'decision':'accept'},'operation_id':'answer'})
            self.assertEqual(self.store.poll(0,'test-thread',50)['pending_requests'][0]['status'],'pending')
            result=b.handle({'op':'respond','request_key':rows[0]['key'],'result':{'decision':'decline'},'human_confirmed':True,'operation_id':'answer'})
            self.assertEqual(result['status'],'response_sent')
            b.proc.terminate();b.proc.wait(timeout=3)
            for _ in range(100):
                if not b.alive: break
                time.sleep(.01)
            with self.assertRaises(ValueError):
                b.handle({'op':'respond','request_key':rows[0]['key'],'result':{},'human_confirmed':True,'operation_id':'stale'})
        finally:
            if b.proc.poll() is None:b.proc.terminate();b.proc.wait(timeout=3)
            time.sleep(.05)
            b.proc.stdin.close();b.proc.stdout.close()

if __name__=='__main__': unittest.main()
