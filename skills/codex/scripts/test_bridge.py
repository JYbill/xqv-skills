"""Offline protocol tests; does not contact a model or mutate a real Codex thread."""
import json
import io
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
from pathlib import Path
from bridge import main
from daemon import Bridge
from store import Store

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
 if method=='thread/resume':
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
            self.store.event('e',{'method':'item/completed','params':{'threadId':'a' if i%2==0 else 'b','i':i}})
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
    def test_filtered_pagination_preserves_key_events(self):
        noise=['item/agentMessage/delta','account/rateLimits/updated',
               'thread/tokenUsage/updated','skills/changed']
        for i in range(6):
            for method in noise*40:
                self.store.event('e',{'method':method,'params':{'threadId':'t'}})
            self.store.event('e',{'method':'item/completed','params':{'threadId':'t','item':{'id':str(i)}}})
        self.store.event('e',{'method':'turn/completed','params':{'threadId':'other'}})
        self.store.event('e',{'method':'turn/completed','params':{'threadId':'t'}})
        expected=self.store.poll(0,'t',2000)['events']
        cursor=0; actual=[]
        while True:
            started=time.monotonic()
            page=self.poll_bridge().handle({'op':'poll','thread':'t','cursor':cursor,
                'event_limit':2})
            self.assertLess(time.monotonic()-started,1)
            actual.extend(page['events']); cursor=page['cursor']
            if not page['has_more']: break
            self.assertEqual(cursor,page['events'][-1]['cursor'])
        self.assertEqual(actual,expected)
        self.assertEqual(self.store.poll(cursor,'t',2)['events'],[])
    def test_poll_always_filters_events(self):
        self.store.event('e',{'method':'item/agentMessage/delta','params':{'threadId':'t','delta':'hello'}})
        self.store.event('e',{'method':'turn/completed','params':{'threadId':'t'}})
        self.store.event('e',{'method':'skills/changed','params':{'threadId':'t'}})
        result=self.poll_bridge().handle({'op':'poll','thread':'t'})
        self.assertEqual([x['event']['method'] for x in result['events']],['turn/completed'])
        self.assertEqual(result['cursor'],3)
        self.assertFalse(result['has_more'])
    def test_cli_has_no_filter_switch(self):
        with patch.object(sys,'argv',['bridge.py','poll','--thread','t']), \
                patch('bridge.client',return_value={}) as client, patch('builtins.print'):
            main()
            self.assertNotIn('summary',client.call_args.args[0])
            self.assertEqual(client.call_args.args[0]['event_limit'],50)
        for flag in ['--summary','--no-summary','--wait','--limit','--until-idle']:
            with self.subTest(flag=flag), patch.object(sys,'argv',['bridge.py','poll','--thread','t',flag]), \
                    patch('sys.stderr'), self.assertRaises(SystemExit) as error:
                main()
            self.assertEqual(error.exception.code,2)
    def test_cli_event_limit_range(self):
        for value in [1,101,200]:
            with self.subTest(value=value), patch.object(sys,'argv',[
                    'bridge.py','poll','--thread','t','--event-limit',str(value)]), \
                    patch('bridge.client',return_value={}) as client, patch('builtins.print'):
                main()
                self.assertEqual(client.call_args.args[0]['event_limit'],value)
        for value in [0,201]:
            with self.subTest(value=value), patch.object(sys,'argv',[
                    'bridge.py','poll','--thread','t','--event-limit',str(value)]), \
                    patch('sys.stderr'), self.assertRaises(SystemExit) as error:
                main()
            self.assertEqual(error.exception.code,2)
    def test_poll_default_and_explicit_page_sizes(self):
        for _ in range(201):
            self.store.event('e',{'method':'item/completed','params':{'threadId':'t'}})
        for value in [None,1,101,200]:
            with self.subTest(value=value):
                req={'op':'poll','thread':'t'}
                if value is not None:
                    req['event_limit']=value
                result=self.poll_bridge().handle(req)
                self.assertEqual(len(result['events']),50 if value is None else value)
                self.assertEqual(result['return_reason'],'event_limit')
                self.assertTrue(result['has_more'])
    def test_poll_requires_thread(self):
        b=self.poll_bridge()
        for tid in [None, '', '   ', 123]:
            with self.subTest(tid=tid), self.assertRaisesRegex(ValueError,'thread ID'):
                b.handle({'op':'poll','thread':tid})
        with patch.object(sys,'argv',['bridge.py','poll']), \
                patch('sys.stderr'), self.assertRaises(SystemExit) as error:
            main()
        self.assertEqual(error.exception.code,2)
    def test_poll_wakes_on_new_event_and_existing_backlog(self):
        b=self.poll_bridge()
        self.emit_later([(.1,{'method':'item/completed','params':{'threadId':'t'}})])
        started=time.monotonic()
        r=b.handle({'op':'poll','thread':'t','cursor':0,'event_limit':1})
        self.assertLess(time.monotonic()-started,1)
        self.assertEqual(len(r['events']),1)
        started=time.monotonic()
        self.assertEqual(b.handle({'op':'poll','thread':'t','event_limit':1})['events'],r['events'])
        self.assertLess(time.monotonic()-started,1)
    def test_below_threshold_waits_for_target_completion(self):
        self.emit_later([(.05,{'method':'turn/completed','params':{'threadId':'other'}}),
            (.05,{'method':'thread/status/changed','params':{'threadId':'t','status':{'type':'idle'}}}),
            (.05,{'method':'item/completed','params':{'threadId':'t'}}),
            (.1,{'method':'turn/completed','params':{'threadId':'t'}})])
        started=time.monotonic()
        r=self.poll_bridge().handle({'op':'poll','thread':'t'})
        self.assertGreaterEqual(time.monotonic()-started,.2)
        self.assertLess(time.monotonic()-started,1)
        self.assertEqual(r['events'][-1]['event']['method'],'turn/completed')
        self.assertTrue(all(x['thread_id']=='t' for x in r['events']))
    def test_requests_and_questions_wake_before_threshold(self):
        for msg in [
            {'id':8,'method':'item/tool/requestUserInput','params':{'threadId':'request'}},
            {'method':'item/completed','params':{'threadId':'question','turnId':'v',
                'item':{'type':'agentMessage','id':'q','questions':[{'title':'Choose?'}]}}}]:
            tid=msg['params']['threadId']
            self.emit_later([(.1,msg)])
            started=time.monotonic()
            r=self.poll_bridge().handle({'op':'poll','thread':tid})
            self.assertLess(time.monotonic()-started,1)
            self.assertTrue(r['pending_requests'] or r['question_messages'])
    def test_poll_timeout_and_event_limit_validation(self):
        b=self.poll_bridge()
        for value in [0,201,1.5,True,'50']:
            with self.assertRaises(ValueError):
                b.handle({'op':'poll','thread':'t','event_limit':value})
        self.emit_later([(.05,{'method':'skills/changed','params':{}})])
        started=time.monotonic()
        with patch('store.POLL_TIMEOUT',.2):
            r=b.handle({'op':'poll','thread':'t'})
        self.assertGreaterEqual(time.monotonic()-started,.2)
        self.assertLess(time.monotonic()-started,1)
        self.assertEqual(r['events'],[])
        self.assertEqual(r['cursor'],1)
        self.assertEqual(r['return_reason'],'timeout')
    def test_waits_for_event_count(self):
        self.emit_later([(.05,{'method':'item/completed','params':{'threadId':'t'}}),
                         (.15,{'method':'item/completed','params':{'threadId':'t'}})])
        started=time.monotonic()
        r=self.poll_bridge().handle({'op':'poll','thread':'t','event_limit':2})
        self.assertGreaterEqual(time.monotonic()-started,.2)
        self.assertEqual(len(r['events']),2)
        self.assertEqual(r['return_reason'],'event_limit')
    def test_urgent_events_bypass_page_without_skipping_history(self):
        for _ in range(3):
            self.store.event('e',{'method':'item/completed','params':{'threadId':'t'}})
        self.store.event('e',{'method':'turn/completed','params':{'threadId':'t','turn':{'id':'done'}}})
        b=self.poll_bridge()
        r=b.handle({'op':'poll','thread':'t','event_limit':2})
        self.assertEqual(r['cursor'],2)
        self.assertTrue(r['has_more'])
        self.assertEqual(r['urgent_events'][0]['cursor'],4)
        self.assertEqual(r['return_reason'],'attention')
        page=b.handle({'op':'poll','thread':'t','cursor':r['cursor'],'event_limit':2})
        self.assertEqual([x['cursor'] for x in page['events']],[3,4])
    def test_disconnect_returns_partial_batch(self):
        b=self.poll_bridge(); b.alive=False
        self.store.event('e',{'method':'item/completed','params':{'threadId':'t'}})
        r=b.handle({'op':'poll','thread':'t'})
        self.assertEqual(len(r['events']),1)
        self.assertEqual(r['return_reason'],'disconnected')
    def test_server_exits_on_completion_and_poll_reads_saved_pages(self):
        self.run_server_shutdown_test(completed=True)

    def test_server_exits_on_backend_disconnect(self):
        self.run_server_shutdown_test(completed=False)

    def run_server_shutdown_test(self, completed):
        # Real bridge server/client sockets and process, with a fake model backend.
        import client as bridge_client
        import daemon
        state=Path(self.tmp.name)/'receiver'
        state.mkdir()
        home=Path(self.tmp.name)/'home'
        (home/'app-server-control').mkdir(parents=True)
        (home/'app-server-control/app-server-control.sock').touch()
        fake=Path(self.tmp.name)/'complete.py'
        fake.write_text(FAKE.replace(
            " if method=='thread/resume':",
            " if method=='thread/resume':\n  print(json.dumps({'method':'item/completed','params':{'threadId':'test-thread','item':{'type':'agentMessage','text':'done'}}}),flush=True)\n  print(json.dumps({'method':'turn/completed','params':{'threadId':'test-thread','turn':{'id':'test-turn','status':'completed'}}}),flush=True)\n  continue"))
        if not completed:
            fake.write_text(FAKE.split(" if method=='thread/resume':")[0] + " if method=='thread/resume': break\n")
        runner=Path(self.tmp.name)/'server.py'
        runner.write_text(
            'import sys,functools\nfrom pathlib import Path\n'
            + 'sys.path.insert(0,'+repr(str(Path(daemon.__file__).parent))+')\nimport daemon\n'
            + 'daemon.STATE=Path('+repr(str(state))+')\n'
            + 'daemon.SOCK=daemon.STATE/"bridge.sock"\n'
            + 'daemon.HOME=Path('+repr(str(home))+')\n'
            + 'daemon.Bridge=functools.partial(daemon.Bridge,command=['+repr(sys.executable)+','+repr(str(fake))+'])\n'
            + 'daemon.serve()\n')
        proc=subprocess.Popen([sys.executable,str(runner)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            with patch.object(bridge_client,'STATE',state), patch.object(bridge_client,'SOCK',state/'bridge.sock'):
                deadline=time.monotonic()+5
                while not bridge_client.SOCK.exists():
                    if proc.poll() is not None: self.fail(proc.communicate()[1])
                    if time.monotonic()>deadline: self.fail('Server did not start')
                    time.sleep(.02)
                result=bridge_client.client({'op':'rpc','method':'thread/resume','params':{'threadId':'test-thread','excludeTurns':True},'operation_id':'finish'})
                self.assertEqual(result['result']['turn']['id'],'test-turn')
                proc.wait(timeout=5)
                self.assertEqual(proc.returncode,0,proc.communicate()[1])
                self.assertFalse(bridge_client.SOCK.exists())
                cursor=0; events=[]
                while True:
                    page=bridge_client.client({'op':'poll','thread':'test-thread','cursor':cursor,'event_limit':1})
                    self.assertFalse(page['connected'])
                    events.extend(x['event'] for x in page['events'])
                    cursor=page['cursor']
                    if not page['has_more']: break
                if completed:
                    self.assertTrue(any(e['method']=='item/completed' and e['params']['item']['text']=='done' for e in events))
                    self.assertTrue(any(e['method']=='turn/completed' for e in events))
                else:
                    self.assertTrue(any(e['method']=='bridge/disconnected' for e in events))
                    self.assertFalse(any(e['method']=='turn/completed' for e in events))
        finally:
            if proc.poll() is None: proc.terminate(); proc.wait(timeout=3)
            proc.communicate()
    def test_request_lifecycle(self):
        self.store.event('e',{'id':5,'method':'item/tool/requestUserInput','params':{'threadId':'t'}})
        self.assertEqual(len(self.store.poll(0,'t',10)['pending_requests']),1)
        self.store.event('e',{'method':'serverRequest/resolved','params':{'threadId':'t','requestId':5}})
        self.assertEqual(self.store.poll(0,'t',10)['pending_requests'],[])
        self.store.event('e',{'id':6,'method':'item/tool/requestUserInput','params':{'threadId':'t'}})
        self.store.disconnected('e')
        self.assertEqual(self.store.poll(0,'t',10)['pending_requests'][0]['status'],'unknown_after_disconnect')
    def test_interrupt_requires_operation_id_and_deduplicates_retries(self):
        b=self.poll_bridge()
        b.mutation_lock=threading.Lock()
        b.rpc=Mock(return_value={'id':2,'result':{}})
        req={'op':'rpc','method':'turn/interrupt','params':{'threadId':'t'}}
        with self.assertRaisesRegex(ValueError,'operation-id'):
            b.handle(req)
        b.rpc.assert_not_called()
        req['operation_id']='interrupt-one'
        first=b.handle(req)
        self.assertEqual(first,{'id':2,'result':{}})
        self.assertEqual(b.handle(req),first)
        b.rpc.assert_called_once_with('turn/interrupt',{'threadId':'t'})
        with self.assertRaisesRegex(ValueError,'different arguments'):
            b.handle({**req,'params':{'threadId':'other'}})
        b.rpc.assert_called_once()
    def test_unlisted_mutation_is_still_rejected(self):
        b=self.poll_bridge()
        b.rpc=Mock()
        with self.assertRaisesRegex(ValueError,'Unsupported method'):
            b.handle({'op':'rpc','method':'thread/delete','params':{'threadId':'t'},
                'operation_id':'delete-one'})
        b.rpc.assert_not_called()
    def test_questions_do_not_wake_forever_after_followup_or_new_turn(self):
        self.store.event('e',{'method':'item/completed','params':{'threadId':'t','turnId':'one',
            'item':{'type':'agentMessage','id':'q','questions':[{'title':'Choose?'}]}}})
        self.store.event('e',{'method':'item/completed','params':{'threadId':'t',
            'item':{'type':'userMessage','id':'answer'}}})
        with patch('store.POLL_TIMEOUT',.01):
            r=self.poll_bridge().handle({'op':'poll','thread':'t','cursor':2})
        self.assertEqual(r['return_reason'],'timeout')
        self.assertEqual(r['question_messages'][0]['status'],'followup_observed_answer_unconfirmed')
        self.store.event('e',{'method':'turn/started','params':{'threadId':'t','turn':{'id':'two'}}})
        self.assertEqual(self.store.poll(3,'t',20)['question_messages'],[])
    def test_stale_requests_do_not_wake_new_connection(self):
        self.store.event('old',{'id':9,'method':'item/tool/requestUserInput','params':{'threadId':'t'}})
        self.store.disconnected('old')
        with patch('store.POLL_TIMEOUT',.01):
            r=self.poll_bridge().handle({'op':'poll','thread':'t','cursor':1})
        self.assertEqual(r['return_reason'],'timeout')
        self.assertEqual(r['pending_requests'][0]['status'],'unknown_after_disconnect')
    def test_reader_stops_only_for_target_thread_and_turn(self):
        b=self.poll_bridge(); b.guard=threading.RLock(); b.pending={}
        b.completed=threading.Event(); b.target_thread='t'; b.target_turn='current'
        messages=[
            {'method':'turn/completed','params':{'threadId':'other','turn':{'id':'current'}}},
            {'method':'turn/completed','params':{'threadId':'t','turn':{'id':'old'}}},
            {'method':'item/completed','params':{'threadId':'t','item':{'id':'still-running'}}},
            {'method':'turn/completed','params':{'threadId':'t','turn':{'id':'current'}}},
            {'method':'item/completed','params':{'threadId':'t','item':{'id':'after-stop'}}}]
        b.proc=Mock(stdout=io.StringIO(''.join(json.dumps(m)+'\n' for m in messages)))
        b.reader()
        recorded=[x['event'] for x in self.store.poll(0,'t',100)['events']]
        ids=[x.get('params',{}).get('item',{}).get('id') for x in recorded]
        self.assertIn('still-running',ids); self.assertNotIn('after-stop',ids)
        self.assertTrue(b.completed.is_set())
    def test_rejects_second_thread_and_resubscribes_after_restart(self):
        b=self.poll_bridge();b.guard=threading.RLock();b.mutation_lock=threading.Lock()
        b.target_thread=None;b.rpc=Mock(return_value={'result':{}})
        req={'op':'rpc','method':'thread/resume','params':{'threadId':'t'},'operation_id':'resume'}
        b.handle(req);b.handle(req)
        self.assertEqual(b.rpc.call_count,1)
        with self.assertRaisesRegex(ValueError,'another thread'):
            b.handle({**req,'params':{'threadId':'other'},'operation_id':'other'})
        b.epoch='restarted';b.target_thread=None
        b.handle(req)
        self.assertEqual(b.rpc.call_count,2)
    def test_start_waits_for_dead_receiver_and_launches_replacement(self):
        with patch.object(sys,'argv',['bridge.py','start']), patch('daemon.STATE',Path(self.tmp.name)), \
                patch('client.client',side_effect=[{'connected':False},ConnectionRefusedError(),{'connected':True}]), \
                patch('client.subprocess.Popen') as spawn, patch('client.time.sleep'), patch('builtins.print'):
            self.assertEqual(main(),0)
            spawn.assert_called_once()
            self.assertEqual(Path(spawn.call_args.args[0][1]).name,'bridge.py')
            self.assertEqual(spawn.call_args.args[0][2],'serve')
    def test_rpc_errors_return_failure_exit_code(self):
        with patch.object(sys,'argv',['bridge.py','rpc','--method','thread/read','--params-file','-']), \
                patch('sys.stdin',io.StringIO('{"threadId":"missing"}')), \
                patch('bridge.client',return_value={'error':{'message':'missing thread'}}), patch('builtins.print'):
            self.assertEqual(main(),1)
    def test_transport_import_does_not_load_daemon_or_storage(self):
        scripts=str(Path(__file__).resolve().parent)
        code="import sys; sys.path.insert(0,sys.argv[1]); import transport; assert not {'daemon','client','store','sqlite3'} & set(sys.modules)"
        subprocess.run([sys.executable,'-c',code,scripts],check=True,capture_output=True)
    def test_cli_owned_methods_are_rejected(self):
        b=self.poll_bridge(); b.rpc=Mock()
        for method in ['turn/start','thread/archive']:
            with self.subTest(method=method), self.assertRaisesRegex(ValueError,'Unsupported method'):
                b.handle({'op':'rpc','method':method,'params':{},'operation_id':'unused'})
        b.rpc.assert_not_called()
    def test_bridge_defaults_idempotency_and_human_gate(self):
        path=Path(self.tmp.name)/'fake.py';path.write_text(FAKE)
        b=Bridge(self.store,[sys.executable,str(path)])
        try:
            req={'op':'rpc','method':'thread/start','params':{'cwd':'/tmp'},'operation_id':'one'}
            first=b.handle(req)
            self.assertEqual(first['result']['received_params'],{'cwd':'/tmp'})
            self.assertEqual(b.handle(req),first)
            with self.assertRaises(ValueError):b.handle({**req,'params':{'cwd':'/elsewhere'}})
            b.handle({'op':'rpc','method':'thread/resume','params':{'threadId':'test-thread','excludeTurns':True},'operation_id':'two'})
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
