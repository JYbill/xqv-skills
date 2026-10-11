"""Shared paths, timeouts and protocol configuration; importing starts no service."""
import hashlib
import json
import os
from pathlib import Path
import tempfile

HOME = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))).expanduser().resolve()
ROOT = Path(os.environ.get('CODEX_SKILL_STATE', str(Path(tempfile.gettempdir()) / f'codex-skill-{os.getuid()}'))).expanduser().resolve()
TAG = hashlib.sha256(str(HOME).encode()).hexdigest()[:12]
STATE = ROOT / TAG
SOCK = STATE / 'bridge.sock'
# 长时间没有输出可能使主 Agent 或宿主工具终止调用。
# 100 秒后返回当前结果，避免无限等待；这不表示 Codex 卡住或任务完成。
# 宿主仍可能提前终止客户端，恢复时沿用最后确认的游标，不重新派发任务。
POLL_TIMEOUT = 100
RPC_METHODS = {'thread/start', 'thread/resume', 'thread/read', 'thread/list',
               'thread/turns/list', 'thread/items/list', 'turn/steer',
               'turn/interrupt', 'config/read'}
MUTATIONS = {'thread/start', 'thread/resume', 'turn/steer', 'turn/interrupt'}

def dumps(x):
    return json.dumps(x, ensure_ascii=False, separators=(',', ':'))
