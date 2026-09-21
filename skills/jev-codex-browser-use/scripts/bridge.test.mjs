import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, mkdir, writeFile, rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {loadConfig, createSession} from './bridge.mjs';

async function fixture(t) {
  const dir = await mkdtemp(join(tmpdir(), 'jev-codex-test-'));
  t.after(() => rm(dir, {recursive:true, force:true}));
  return dir;
}

async function config(dir, name, value) {
  const folder = join(dir, name);
  await mkdir(folder, {recursive:true});
  await writeFile(join(folder, 'config.json'), value);
}

test('新配置优先，缺失时兼容旧配置，配置错误不回退', async t => {
  const dir = await fixture(t);
  await config(dir, 'jev-browser-use', JSON.stringify({provider:'typesafe', model:'jev-old'}));
  assert.equal((await loadConfig({configDir:dir})).model, 'jev-old');
  await config(dir, 'jev-codex-browser-use', JSON.stringify({provider:'typesafe', model:'jev-new'}));
  assert.equal((await loadConfig({configDir:dir})).model, 'jev-new');
  await config(dir, 'jev-codex-browser-use', '{invalid');
  await assert.rejects(loadConfig({configDir:dir}), SyntaxError);
});

test('只有新配置时可加载，不依赖旧 skill 或配置', async t => {
  const dir = await fixture(t);
  await config(dir, 'jev-codex-browser-use', JSON.stringify({provider:'typesafe', model:'jev-latest'}));
  assert.equal((await loadConfig({configDir:dir})).model, 'jev-latest');
});

async function browserFixture(t, decisions, multiple = true) {
  const dir = await fixture(t);
  const envFile = join(dir, 'test.env');
  await writeFile(envFile, 'TYPESAFE_API_KEY=synthetic-test-key\n');
  const clicks = [];
  const requests = [];
  const tab = {
    async getAXState() {
      return 'Browser tab: Test URL: "https://example.test/".\n' +
        ['1 button Orders', '2 button Details', '3 text Order TEST-1042'][clicks.length] +
        (multiple ? '\n9 button Back\n10 button Help' : '');
    },
    async click(index) { clicks.push(index); }
  };
  t.mock.method(globalThis, 'fetch', async (_url, options) => {
    const body = JSON.parse(options.body);
    requests.push(body);
    const next = decisions.shift();
    assert.ok(next, 'Unexpected extra API request');
    const keys = Object.keys(body.questions.next.criteria);
    assert.equal(keys.includes('DONE'), false);
    assert.ok(keys.includes('HANDOFF'));
    const probabilities = Object.fromEntries(keys.map(key => [key, key === next.choice ? 1 : 0]));
    return {ok:true, async json() {return {model:'jev-latest', answers:{next:{type:'choice', ...next, probabilities}}};}};
  });
  const defaults = {envFile, provider:'typesafe', model:'jev-latest', allowedOrigins:['https://example.test']};
  const task = {goal:'Open order details', controls:[{op:'click',name:'Orders'}, {op:'click',name:'Details'}, ...(multiple ? [{op:'click',name:'Back'}, {op:'click',name:'Help'}] : [])]};
  return {tab, clicks, requests, defaults, task};
}

test('一次调用连续执行两个动作，HANDOFF 仅交回控制权，新会话隔离历史', async t => {
  const f = await browserFixture(t, [
    {choice:'a0',confidence:0.9}, {choice:'a0',confidence:0.9},
    {choice:'HANDOFF',confidence:0.9}, {choice:'HANDOFF',confidence:0.9}
  ]);
  const session = createSession(f.tab, f.defaults);
  const outcome = await session.run(f.task);
  assert.deepEqual(f.clicks, [1,2]);
  assert.equal(outcome.status, 'handoff');
  assert.equal(outcome.sessionMetrics.executedActions, 2);
  assert.equal(f.requests[1].state.history.length, 1);
  await createSession(f.tab, f.defaults).run(f.task);
  assert.deepEqual(f.requests[3].state.history, []);
});

test('动作后低置信度返回，已执行动作保留且不重复', async t => {
  const f = await browserFixture(t, [{choice:'a0',confidence:0.9}, {choice:'HANDOFF',confidence:0.13}]);
  const outcome = await createSession(f.tab, f.defaults).run(f.task);
  assert.equal(outcome.status, 'low_confidence');
  assert.deepEqual(f.clicks, [1]);
  assert.equal(outcome.sessionMetrics.executedActions, 1);
  assert.equal(f.requests.length, 2);
});


test('唯一候选直接点击，不请求模型，返回验收且不重复点击', async t => {
  const f = await browserFixture(t, [], false);
  const session = createSession(f.tab, f.defaults);
  const outcome = await session.run(f.task);
  assert.deepEqual(f.clicks, [1]);
  assert.equal(f.requests.length, 0);
  assert.equal(outcome.status, 'action_executed');
  assert.equal(outcome.sessionMetrics.decisions, 0);
  assert.equal(outcome.sessionMetrics.directActions, 1);
  assert.equal(outcome.sessionMetrics.apiMs, 0);
  assert.equal(session.history()[0].choice, 'DIRECT');
});

test('无候选交回验收，不请求模型或声明成功', async t => {
  const f = await browserFixture(t, [], false);
  const outcome = await createSession(f.tab, f.defaults).run({...f.task, controls:[{op:'click',name:'Missing'}]});
  assert.equal(outcome.status, 'no_candidates');
  assert.deepEqual(f.clicks, []);
  assert.equal(f.requests.length, 0);
});

test('唯一候选执行前页面改变，不点击旧索引', async t => {
  const f = await browserFixture(t, [], false);
  let reads = 0;
  f.tab.getAXState = async () => 'Browser tab: Test URL: "https://example.test/".\n' + (++reads === 1 ? '1 button Orders' : '3 text Loading');
  const outcome = await createSession(f.tab, f.defaults).run(f.task);
  assert.equal(outcome.status, 'no_candidates');
  assert.deepEqual(f.clicks, []);
  assert.equal(f.requests.length, 0);
  assert.equal(outcome.history[0].reason, 'stale_state');
});

test('唯一候选点击失败保留失败记录，不请求模型', async t => {
  const f = await browserFixture(t, [], false);
  f.tab.click = async () => { throw new Error('Click failed'); };
  const outcome = await createSession(f.tab, f.defaults).run(f.task);
  assert.equal(outcome.status, 'action_error');
  assert.equal(outcome.history[0].executed, null);
  assert.equal(outcome.history[0].executionStatus, 'unknown');
  assert.equal(outcome.sessionMetrics.unknownActions, 1);
  assert.equal(outcome.sessionMetrics.directActions, 0);
  assert.equal(f.requests.length, 0);
});

for (const multiple of [false, true]) {
  for (const failure of ['read', 'origin']) {
    test(`${multiple ? '模型' : '直接'}点击后${failure}异常保留已执行记录及累计统计`, async t => {
      const f = await browserFixture(t, [{choice:'a0',confidence:0.9}], multiple);
      const session = createSession(f.tab, f.defaults);
      const getState = f.tab.getAXState;
      const initial = await getState();
      f.tab.getAXState = async () => {
        if (!f.clicks.length) return getState();
        assert.equal(session.history()[0].executionStatus, 'executed');
        assert.equal(session.metrics().executedActions, 1);
        if (failure === 'read') throw new Error('Page unavailable');
        return 'Browser tab: Other URL: "https://unauthorized.test/".\n1 button Orders';
      };
      const outcome = await session.run(f.task);
      const status = failure === 'read' ? 'state_read_error' : 'state_validation_error';
      assert.equal(outcome.status, status);
      assert.equal(outcome.handoff, status);
      assert.equal(outcome.state, initial);
      assert.equal(outcome.stateMayBeStale, true);
      assert.equal(outcome.history.length, 1);
      assert.equal(outcome.history[0].executionStatus, 'executed');
      assert.equal(outcome.sessionMetrics.executedActions, 1);
      assert.equal(outcome.sessionMetrics.directActions, multiple ? 0 : 1);
      assert.equal(outcome.sessionMetrics.runs, 1);
      assert.equal(outcome.sessionMetrics.handoffs[status], 1);
      assert.deepEqual(f.clicks, [1]);
      assert.equal(f.requests.length, multiple ? 1 : 0);
      f.tab.getAXState = getState;
      const resumed = await session.run({...f.task,controls:[{op:'click',name:'Missing'}]});
      assert.equal(resumed.sessionMetrics.executedActions, 1);
      assert.equal(resumed.sessionMetrics.runs, 2);
      assert.deepEqual(f.clicks, [1]);
    });
  }
}

test('点击前已保存执行中记录，报错后更新同一条为未知，不重试', async t => {
  const f = await browserFixture(t, [], false);
  const session = createSession(f.tab, f.defaults);
  f.tab.click = async index => {
    assert.equal(session.history().length, 1);
    assert.equal(session.history()[0].executionStatus, 'executing');
    f.clicks.push(index);
    throw new Error('Response lost after click');
  };
  const outcome = await session.run(f.task);
  assert.equal(outcome.history.length, 1);
  assert.equal(outcome.history[0].executionStatus, 'unknown');
  assert.equal(outcome.history[0].executed, null);
  assert.equal(outcome.stateMayBeStale, true);
  assert.equal(outcome.sessionMetrics.executedActions, 0);
  assert.equal(outcome.sessionMetrics.unknownActions, 1);
  assert.deepEqual(f.clicks, [1]);
});

for (const failAt of [1, 2]) {
  test(`第 ${failAt} 次页面读取失败不点击，返回可用进度`, async t => {
    const f = await browserFixture(t, [], false);
    const getState = f.tab.getAXState;
    let reads = 0;
    f.tab.getAXState = async () => {
      if (++reads === failAt) throw new Error('Read failed');
      return getState();
    };
    const outcome = await createSession(f.tab, f.defaults).run(f.task);
    assert.equal(outcome.status, 'state_read_error');
    assert.equal(outcome.stateMayBeStale, true);
    assert.equal(outcome.history.length, failAt - 1);
    if (failAt === 1) assert.equal(outcome.state, null);
    else assert.equal(outcome.history[0].executionStatus, 'not_executed');
    assert.equal(outcome.sessionMetrics.executedActions, 0);
    assert.deepEqual(f.clicks, []);
  });
}


test('更名前的配置仍可加载，优先于最早配置且错误不回退', async t => {
  const dir = await fixture(t);
  await config(dir, 'jev-browser-use', JSON.stringify({model:'jev-old'}));
  await config(dir, 'jev-codex-computer-use', JSON.stringify({model:'jev-previous'}));
  assert.equal((await loadConfig({configDir:dir})).model, 'jev-previous');
  await config(dir, 'jev-codex-browser-use', JSON.stringify({model:'jev-current'}));
  assert.equal((await loadConfig({configDir:dir})).model, 'jev-current');
  await rm(join(dir, 'jev-codex-browser-use'), {recursive:true});
  await config(dir, 'jev-codex-computer-use', '{invalid');
  await assert.rejects(loadConfig({configDir:dir}), SyntaxError);
});
