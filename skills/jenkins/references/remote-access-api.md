# Jenkins Remote Access API

官方依据：[Remote Access API](https://www.jenkins.io/doc/book/using/remote-access-api/)、[脚本认证](https://www.jenkins.io/doc/book/system-administration/authenticating-scripted-clients/)、[CSRF](https://www.jenkins.io/doc/book/security/csrf-protection/)。插件字段以目标资源的 `/api/` 和当前插件文档为准。

## 环境与凭据选择

连接配置只读取当前进程已有的环境变量：`JENKINS_URL`、`JENKINS_USER_ID`，以及所选认证方式对应的 `JENKINS_API_TOKEN`、`JENKINS_AUTH_FILE` 或 `JENKINS_PASSWORD`。认证文件的格式与用户名规则见下文。所需变量缺失时报告变量名，不自动加载或写入项目配置。地址不在命令中固化，不输出完整环境或凭据。

按当前环境变量确定地址、用户及认证来源；用户明确指定的认证来源优先，不用其他来源覆盖。更换控制器时不自动携带原控制器凭据；未指定新凭据时先确认可用来源。

- 用户明确指定的认证来源优先；同一层级未指定来源时依次选择 API Token、认证文件、密码。
- `JENKINS_AUTH_FILE` 定义为 UTF-8 JSON：`{"username":"用户名","password":"密码"}` 或 `{"username":"用户名","apiToken":"Token"}`，两种 secret 必须且只能存在一种。文件权限为 `0600`，不存入仓库。读取后转成临时 curl 配置，不把 JSON 直接传给 `curl --config`。
- 文件用户名与显式 `JENKINS_USER_ID` 冲突时停止，不静默切换身份。未明确用户名时可采用文件中的用户名。
- 缺少所选来源、内容不合法或认证失败时报告错误，不静默换用另一账号或匿名身份。

本项目现有 HTTP 地址仅用于已确认的可信局域网；换到其他网络时核对访问方式。不得输出 secret，不启用 `set -x`、curl verbose 或 trace。

## 临时认证与 cookie

以下为 Bash 示例，在已载入并解析所选凭据的环境中执行；认证文件来源也先读入相应环境变量，只保留所选的 Token 或密码。示例不自动选择或覆盖用户配置。

```bash
set -euo pipefail
umask 077
jenkins_tmp_dir=$(mktemp -d "${TMPDIR:-/tmp}/jenkins.XXXXXXXX")
trap 'rm -rf -- "$jenkins_tmp_dir"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
chmod 700 "$jenkins_tmp_dir"
export JENKINS_CURL_CONFIG="$jenkins_tmp_dir/auth.conf"
export JENKINS_CRUMB_CONFIG="$jenkins_tmp_dir/crumb.conf"
jenkins_cookie_file="$jenkins_tmp_dir/cookies.txt"

python3 - <<'PY'
import os
from pathlib import Path

def quote(value):
    if any(c in value for c in '\r\n\0'):
        raise SystemExit('凭据不能包含换行或 NUL')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'

user = os.environ['JENKINS_USER_ID']
secret = os.environ.get('JENKINS_API_TOKEN') or os.environ.get('JENKINS_PASSWORD')
if not user or ':' in user or not secret:
    raise SystemExit('用户名或凭据无效')
p = Path(os.environ['JENKINS_CURL_CONFIG'])
p.write_text('user = ' + quote(user + ':' + secret) + '\n')
p.chmod(0o600)
PY

jenkins_curl_args=(--silent --show-error --globoff --connect-timeout 10 --max-time 60
  --config "$JENKINS_CURL_CONFIG")

# 先核对 HTTP 状态和身份，再执行后面的写操作准备。
curl "${jenkins_curl_args[@]}" --fail \
  "${JENKINS_URL%/}/whoAmI/api/json" > "$jenkins_tmp_dir/identity.json"
python3 - "$jenkins_tmp_dir/identity.json" <<'PY'
import json, os, sys
with open(sys.argv[1]) as f:
    identity = json.load(f)
if identity.get('authenticated') is not True or identity.get('name') != os.environ['JENKINS_USER_ID']:
    raise SystemExit('Jenkins 身份未通过核对')
PY

# 仅密码认证且即将执行已授权写操作时运行此段；Token 认证跳过。
if [ -z "${JENKINS_API_TOKEN:-}" ]; then
  curl "${jenkins_curl_args[@]}" --fail \
    --cookie-jar "$jenkins_cookie_file" \
    "${JENKINS_URL%/}/crumbIssuer/api/json" > "$jenkins_tmp_dir/crumb.json"
  chmod 600 "$jenkins_cookie_file"
  python3 - "$jenkins_tmp_dir/crumb.json" <<'PY'
import json, os, re, sys
from pathlib import Path
with open(sys.argv[1]) as f:
    data = json.load(f)
field, crumb = data.get('crumbRequestField'), data.get('crumb')
if not isinstance(field, str) or not re.fullmatch(r'[A-Za-z0-9-]+', field):
    raise SystemExit('crumb 请求头名称无效')
if not isinstance(crumb, str) or not crumb or any(c in crumb for c in '\r\n\0'):
    raise SystemExit('crumb 内容无效')
header = (field + ': ' + crumb).replace('\\', '\\\\').replace('"', '\\"')
p = Path(os.environ['JENKINS_CRUMB_CONFIG'])
p.write_text('header = "' + header + '"\n')
p.chmod(0o600)
PY
  jenkins_curl_args+=(--cookie "$jenkins_cookie_file" --config "$JENKINS_CRUMB_CONFIG")
fi
# 后续请求仍在同一 Bash 进程中使用该数组；退出时一起删除临时目录。
```

cookie 由 crumb 响应的 `Set-Cookie` 取得；后续 POST 同时携带原用户名/密码、crumb 和同一会话 cookie。不得只保存 crumb、从浏览器复制 cookie 或把 cookie 写入项目配置。会话失效时重新取得二者，但不得因此自动重发结果不明的 POST。

## 只读检查与故障诊断

以认证后的 `/whoAmI/api/json` 和目标资源响应为准。`/login` 的状态、`X-Jenkins` 版本头用于辅助定位；代理隐藏版本头或限制登录页，不单独判定 API 不可用。顶层任务列表只显示可见任务，成功不代表拥有某个目标任务的读取或构建权限。

请求默认连接超时 10 秒、总超时 60 秒；大制品下载可按大小调整。使用临时文件保存响应头和正文，`-w '%{http_code}'` 记录状态，同时保留 curl 退出码。诊断时不用 `--fail` 丢掉错误正文，但只输出脱敏摘要；HTTP 错误不能按 curl 退出码 0 判成成功。不盲目跟随重定向，先核对目标控制器，避免登录页被当成 JSON 或向其他主机发送认证信息。

| 现象                      | 检查与处理                                                                    |
| ------------------------- | ----------------------------------------------------------------------------- |
| DNS、连接拒绝、TLS 或超时 | 区分网络错误与 HTTP 错误；检查地址、代理和证书，不用 `-k` 掩盖问题            |
| 401 / 403                 | 核对身份与错误正文；403 可能是权限或 crumb/session 问题，不能一概归为密码错误 |
| 404                       | 核对实际 URL、Folder 层级和可见权限，不直接断定任务不存在                     |
| 3xx 或 200 HTML           | 检查登录跳转、反向代理及 Content-Type，不能当 API 成功                        |
| 429 / 5xx                 | 只读请求按 Retry-After 或短暂退避最多重试两次；写请求不自动重试               |

## 任务发现与参数

从 `${JENKINS_URL%/}/api/json?tree=jobs[name,url,_class]` 开始，按返回 URL 逐级读取 Folder 的 `jobs[name,url,_class]`。用户提供准确任务 URL 时可直接验证，不必枚举整个控制器。不要手工猜测中文或带斜杠分支的编码路径；返回地址与选定控制器不一致时先核对代理配置。

目标任务查询示例（复用上面的 curl 参数）：

```bash
curl "${jenkins_curl_args[@]}" --fail \
  "${job_url%/}/api/json?tree=name,url,_class,buildable,property[parameterDefinitions[name,type,description,defaultParameterValue[value],choices]]" \
  > "$jenkins_tmp_dir/job.json"
```

先识别普通任务、具体分支任务和多分支/Organization Folder 父任务。父任务的 `/build` 可能触发扫描，不能用它替代具体分支构建。依据参数定义决定使用 `/build` 或 `/buildWithParameters`，不是依据用户这次是否提供参数。核对参数名称、类型、选项及默认值；影响目标分支、平台或部署环境的值不能猜。插件字段缺失时读取目标 `/api/` 或在有权限时读取配置，不把缺失字段当作无参数。

## 构建、Revision、日志与制品

- 最近构建：`${job_url%/}/api/json?tree=builds[number,url,result,building,timestamp]{0,20}`。选定后固定具体构建 URL，后续不用 `lastBuild` 代替。
- 构建详情：`${build_url%/}/api/json?tree=number,url,queueId,result,building,timestamp,duration,actions[_class]`。先发现 action 类型，再按需要读取参数、SCM revision 或 Git BuildData；不默认输出 `actions[*]`。
- Revision：结合实际 action、SCM 配置和必要的 checkout 日志核对仓库、分支和 SHA。多仓库分别列出；PR head、目标分支 SHA、测试合并 SHA 不得混用。缺失或多个候选无法消歧时明确标注，不取遇到的第一个 SHA。不能仅凭构建参数中的分支名证明实际检出版本。
- 参数：只提取任务所需且允许展示的字段；密码、Token 和 webhook payload 等敏感参数不输出。
- 日志：通过 `/logText/progressiveText?start=<字节偏移>` 分段读取，`X-Text-Size` 是下次偏移，不是字符数。默认仅展示相关错误及邻近上下文。`consoleText` 全量下载仅在有必要时使用，存入临时文件后筛选，不直接倾倒到对话。
- 制品：先查询 `${build_url%/}/api/json?tree=artifacts[fileName,relativePath]`；按返回的 `relativePath` 对各路径段编码后从 `${build_url%/}/artifact/<编码路径>` 下载。固定构建号，默认保存临时目录；用户指定交付目录时按该目录保存，不覆盖已有文件。校验 HTTP 状态和预期内容，不能把登录页当制品。存在制品不等于构建或部署成功。

## 触发任务

先确认授权、实际任务类型、参数及该任务是否包含部署。无参数任务 POST `${job_url%/}/build`；参数化任务 POST `${job_url%/}/buildWithParameters`，普通参数使用 `--data-urlencode name=value`。敏感参数改用权限受限的临时文件配合 `--data-urlencode name@file`，不出现在命令参数中；文件参数按目标参数类型和 API 文档处理。

触发请求用 `--request POST`、`-D "$jenkins_tmp_dir/response.headers"`、`-o "$jenkins_tmp_dir/response.body"`、`-w '%{http_code}'` 保存证据，密码认证复用前述 cookie 和 crumb 配置。不要使用 `--retry` 或自动跟随重定向。

HTTP 201/202 视为请求已被接受，有 `Location` 时提供队列地址；缺少时仍报告已接受，但无法据此定位构建。其他状态按目标 API 和响应证据判断，不把任意 2xx 或重定向认作构建成功。超时、连接中断或响应不明时报告“可能已入队”，不重试。

默认在此结束，不查询队列、不等待构建、不输出日志。

## 重跑、阶段重启与 Replay

先确认用户要的是重新执行整个任务、从 Declarative Pipeline 的某个阶段继续，还是使用历史 Pipeline 脚本 Replay。这三种操作都会创建新构建，但入口和语义不同，不能互换。

| 意图 | 前置检查 | POST 目标 | 关键限制 |
| --- | --- | --- | --- |
| 重新执行整个任务 | 重新读取任务类型、参数定义和原构建允许复用的参数 | 普通任务使用 `${job_url%/}/build`；参数化任务使用 `${job_url%/}/buildWithParameters` | Cause、webhook payload、文件参数和不可展示的 secret 不保证能从原构建复用；新构建也不保证检出原 Revision |
| 从阶段重启 | 固定已完成的 Declarative Pipeline 构建；确认 `RestartDeclarativePipelineAction` 和页面提供的顶层 `stageName` | 以实际表单 action 为准；当前标准入口为 `${build_url%/}/restart/restart`，参数为 `stageName` | 只选择页面实际提供的顶层阶段；原构建 stash 是否可用取决于 Pipeline 的保留配置 |
| Replay | 确认目标构建提供 Replay action，并读取当前 Replay 表单 | 以实际表单 action 和字段为准；当前标准入口为 `${build_url%/}/replay/run` | Replay 可修改 Pipeline 及 Shared Library 脚本，不得把它当成普通重跑；提交前须核对实际脚本内容及 `Run / Replay` 权限 |

重新执行整个任务时，从原构建的 `ParametersAction` 提取候选参数，再与当前任务参数定义逐项核对。只复用本次授权范围内、值仍有效且允许展示或安全传递的参数；影响分支、平台、部署环境和发布目标的值必须明确，不能因为原构建使用过就默认沿用。要复现原 Revision 时，任务本身必须提供并接受相应 SHA 参数；否则只能在新构建完成后核对实际检出的 Revision。

阶段重启和 Replay 是 Pipeline 插件提供的构建 action，不是假定所有任务都有的 Remote Access API。先从构建 JSON 的 `actions[_class]` 和构建页面表单发现能力，按相对 URL 解析表单 action，并核对仍属于原控制器。不得仅凭常见路径发送 POST，也不得把页面脚本、Shared Library 内容或敏感隐藏字段输出到对话。

这些 POST 与普通触发一样保存响应头、正文、HTTP 状态和 curl 退出码，不自动重试。通过响应中的队列或新构建证据追踪；缺少唯一对应关系时只报告请求结果，不使用最新构建冒充本次操作。

## 停止构建

停止前固定具体构建 URL，并读取 `building`、`result` 和任务类型。已完成构建不发送停止请求；尚未取得构建 URL 的排队项不使用构建停止接口。

Jenkins Pipeline 的停止接口均为 POST：

| 等级 | POST 目标 | 使用条件 |
| --- | --- | --- |
| 普通停止 | `${build_url%/}/stop` | 用户要求停止该构建时的默认操作 |
| 强制终止 | `${build_url%/}/term` | `/stop` 已执行但构建仍未退出，且用户明确授权强制终止 |
| 硬终止 | `${build_url%/}/kill` | `/term` 仍无法结束，且用户明确授权最后手段的硬终止 |

每一级都使用写请求的 crumb/cookie 规则并保存响应证据。响应不明时不重发，也不自动升级到下一级。请求返回后轮询同一构建 URL；只有 `building=false` 且 `result` 有终态值时才报告已经停止，保留 ABORTED、FAILURE 等实际结果。超时只报告停止请求及当前状态，不把本地等待结束说成远端已经停止。

## 删除构建

这里只删除某个构建记录，不删除任务。执行前固定构建 URL 和构建号，确认目标仍属于预期任务、`building=false`，并说明其日志、制品和构建元数据将一并失去。用户必须明确授权删除这个目标构建；停止构建、清理制品或重跑的授权不包含删除。

从目标构建页面或 action 现场确认删除能力；标准表单向 `${build_url%/}/doDelete` 发送 POST。使用写请求的 crumb/cookie 规则并保存响应证据，响应不明时不得重试。随后以同一身份回读固定构建 URL 及任务的构建列表，确认该构建号已移除；POST 返回成功或重定向本身不能单独作为删除完成证据。

## 用户要求等待或跟随日志时

用户给定时限优先；未给定时默认每 10 秒查询一次、总计最多 30 分钟，开始时说明此上限。总时限包含排队和构建，超时只停止本地等待，不取消远端任务。单次等待不超过 60 秒，持续工作时定期反馈当前状态。

1. 验证 `Location`，相对地址按控制器解析；读取队列 `/api/json?tree=id,cancelled,why,blocked,buildable,executable[number,url]`。
2. 已取消则报告取消；尚无 executable 时报告排队原因；有 executable 时固定其构建 URL。
3. 队列记录消失时，用已知队列 ID 与目标任务最近构建的 `queueId` 对应，唯一匹配后才能继续；不能匹配则报告无法追踪。不用最新构建冒充本次构建。
4. 缺少 Location 且没有其他唯一证据时，报告请求已接受但无法可靠等待，不再次触发。用户提供明确构建 URL 时可直接跟踪。
5. 轮询 `/api/json?tree=number,building,result,url`。`building=false` 且 `result` 有值才报告终态，保留 SUCCESS、FAILURE、UNSTABLE、ABORTED、NOT_BUILT 的实际含义；SUCCESS 本身不证明部署验收完成。
6. 跟随日志时按 `X-Text-Size` 推进。`X-More-Data` 不为 true 时停止该日志流；最终构建结果仍由构建 API 确认，不能只因没有新文本判定成功。

## 配置修改

仅在用户授权修改对应目标时执行。先读取实际配置、插件能力和相关项目规则；有权限时 GET 目标 `config.xml`，原件仅存受限临时目录，避免展示其中的密钥或 webhook secret。

生成针对目标配置的最小差异并检查内容。用户要求保存前确认时，在提供脱敏差异后等待确认；已有授权且无此要求时直接推进，不重复确认。写入前重新读取配置，若与原件不同先处理并发变化，不能覆盖他人修改。

任务 XML 更新使用目标 `config.xml` 的 POST，`Content-Type: application/xml`、`--data-binary @<修改后的临时文件>`，并按认证方式携带 crumb/cookie。仅对确实使用该接口的任务执行；节点、插件、凭据及系统设置需另查对应接口，不套用任务配置流程。

写入后回读并按 XML 语义核对目标字段及无关配置是否保留。保存和回读成功仅证明配置生效，不代表 webhook、PR 回写或真实构建已经验证；额外触发仍需相应授权。
