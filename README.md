# Lovmux

Lovmux 帮你在 Claude App 里接入 Zenmux。

不过先说结论：普通用户不一定需要运行 Lovmux 代理。

Claude App 的第三方 inference 配置里，`apiBase` 和模型列表是可以解耦的：

- `apiBase` 决定真正把请求发到哪里。
- `modelDiscoveryEnabled` / `inferenceModels` 决定模型下拉框里显示什么。

因此，配置 Zenmux 有几种路线。最推荐普通用户使用：

```text
Zenmux 官方 apiBase + 关闭自动发现 + 一次性导入完整模型列表
```

Lovmux 更适合企业、极客或需要自动发现大量非 Anthropic 风格模型 ID 的用户。

## 方案总览

| 方案 | 适合谁 | 模型数量 | 是否需要本地代理 | 推荐度 |
| --- | --- | --- | --- | --- |
| 1. Zenmux 官方 apiBase + 自动发现 | 只想最快跑通、主要用 Claude 模型 | 可能只有十几个，数量会变 | 不需要 | 可用 |
| 2. Zenmux 官方 apiBase + 固定模型列表 | 大多数普通用户 | Zenmux Anthropic endpoint 当前暴露的模型 | 不需要 | 推荐 |
| 3. Lovmux 代理 + 自动发现 | 企业、极客、需要自动更新列表的人 | Zenmux Anthropic endpoint 当前暴露的模型 | 需要 | 高级 |
| 4. cc-switch 等社区工具 | 已经在用 Claude Code / Codex 配置切换的人 | 取决于工具能力 | 取决于工具 | 需要自行确认 |

## 背后的事实

截至 2026-05-23，我核对到的情况是：

1. Claude 官方第三方 inference 文档提供了 `modelDiscoveryEnabled` 和 `inferenceModels` 两条模型配置路径。
2. 官方文档说明，关闭模型发现后，`inferenceModels` 是必填项；每个模型需要 `name`，可以有 `labelOverride`。
3. 官方文档说明，`labelOverride` 只影响 Claude App 里的显示名称，真正发给 provider 的仍然是 `name`。
4. 我们实测 Zenmux 的 `https://zenmux.ai/api/anthropic/v1/models?limit=1000` 当前返回 `102` 个模型，`has_more=false`。
5. 你实测 Claude App 直接自动发现 Zenmux 时只显示 `14` 个左右，这更像是 Claude App 产品侧对自动发现结果做了筛选；这个筛选规则官方文档没有完整公开。

所以更准确的说法是：

```text
Claude App 调用 LLM 的 apiBase 和 Claude App 展示模型列表的来源可以分开配置。
如果自动发现被产品侧筛选，就改用固定 inferenceModels。
```

## 方案 1：Zenmux 官方 apiBase + 自动发现

这是最简单的方案，但可能只能看到一小部分模型。

### 怎么配置

打开 Claude App：

```text
Settings -> Cowork -> Configure third-party inference
```

填写：

```text
Inference provider: Gateway
Gateway base URL: https://zenmux.ai/api/anthropic
Gateway auth scheme: bearer
Credential kind: static
API Key: 你的 Zenmux API Key
Model discovery: 开启
```

保存后重启 Claude App。

### 你会看到什么

如果成功，Claude App 会在启动时请求：

```text
https://zenmux.ai/api/anthropic/v1/models
```

但你可能只看到十几个模型，例如：

```text
Model discovery - found 14 models
```

这不一定是 Zenmux 只有 14 个模型，而是 Claude App 自动发现后的模型选择器可能只接受或优先展示某些 Anthropic 风格模型。

### 什么时候用这个方案

如果你只需要 Claude / Anthropic 系列模型，或者只是想最快确认 Zenmux API Key 能不能跑通，可以先用这个方案。

如果你想看到 Qwen、Gemini、OpenAI、DeepSeek 等更多模型，直接看方案 2。

## 方案 2：Zenmux 官方 apiBase + 固定模型列表

这是推荐给普通用户的方案。

它不需要运行 Lovmux，也不需要维护本地代理。Claude App 仍然直接调用 Zenmux 官方 endpoint：

```text
https://zenmux.ai/api/anthropic
```

但模型列表不再依赖 Claude App 自动发现，而是一次性写入 `inferenceModels`。

### 为什么推荐

优点：

1. 不需要本地服务一直运行。
2. 不改变请求链路，LLM 调用直接从 Claude App 发到 Zenmux。
3. 模型列表可以包含非 Anthropic 风格 ID，例如 `qwen/qwen3.7-max`。
4. 普通用户复制一次 JSON 就能完成。

代价：

1. 模型列表不是自动更新的。
2. Zenmux 新增模型后，你需要重新生成并导入一次。
3. 如果某个模型被 Zenmux 下线，Claude App 里仍可能显示它，但调用时会报错。

### 生成配置 JSON

先下载项目：

```bash
git clone https://github.com/lovstudio/lovmux.git
cd lovmux
```

运行脚本：

```bash
python3 scripts/generate_claude_3p_config.py --output claude-zenmux-config.json
```

脚本会请求：

```text
https://zenmux.ai/api/anthropic/v1/models?limit=1000
```

然后生成一个 Claude App 可用的第三方 inference 配置文件：

```text
claude-zenmux-config.json
```

这个文件面向 Claude App 配置窗口里的 `View as JSON`。如果你是企业管理员，要写 `.mobileconfig`、Windows registry 或 MDM 策略，请以 Claude 官方文档为准；MDM 里的数组字段通常需要写成 JSON 字符串。

里面大致长这样：

```json
{
  "inferenceProvider": "gateway",
  "inferenceCredentialKind": "static",
  "inferenceGatewayBaseUrl": "https://zenmux.ai/api/anthropic",
  "inferenceGatewayApiKey": "PASTE_YOUR_ZENMUX_API_KEY_HERE",
  "inferenceGatewayAuthScheme": "bearer",
  "modelDiscoveryEnabled": false,
  "inferenceModels": [
    {
      "name": "anthropic/claude-sonnet-4.6",
      "labelOverride": "Anthropic: Claude Sonnet 4.6"
    },
    {
      "name": "anthropic/claude-sonnet-4.5",
      "labelOverride": "Anthropic: Claude Sonnet 4.5"
    }
  ]
}
```

### 导入到 Claude App

打开 Claude App 的第三方 inference 配置页面：

```text
Settings -> Cowork -> Configure third-party inference
```

点击：

```text
View as JSON
```

把 `claude-zenmux-config.json` 里的内容粘进去。

然后把：

```text
PASTE_YOUR_ZENMUX_API_KEY_HERE
```

替换成你的 Zenmux API Key。

确认这些字段：

```text
inferenceGatewayBaseUrl: https://zenmux.ai/api/anthropic
modelDiscoveryEnabled: false
inferenceModels: 有很多模型
```

保存配置并重启 Claude App。

### 只生成模型列表

如果你不想生成完整配置，只想拿到 `inferenceModels` 数组，可以运行：

```bash
python3 scripts/generate_claude_3p_config.py --format models --output inference-models.json
```

### 设置默认模型

Claude App 通常会把模型列表第一项当成默认模型。脚本默认优先把 `claude-sonnet-4.6` 排到前面。

你可以换成别的模型：

```bash
python3 scripts/generate_claude_3p_config.py \
  --default-model qwen/qwen3.7-max \
  --output claude-zenmux-config.json
```

## 方案 3：Lovmux 代理 + 自动发现

这是本仓库最早实现的方案。

Lovmux 是一个本地 FastAPI 代理：

```text
Claude App -> Lovmux -> Zenmux
```

它做两件事：

1. `/v1/models`：把 Zenmux 的非 Anthropic 模型 ID 改写成 Claude App 更容易接受的 `anthropic/claude-*` 风格 ID。
2. `/v1/messages`：实际调用时再把模型 ID 还原成 Zenmux 原始 ID。

例如：

```text
qwen/qwen3.7-max
```

会展示给 Claude App 为：

```text
anthropic/claude-route-cXdlbi9xd2VuMy43LW1heA
```

实际调用时 Lovmux 会还原成：

```text
qwen/qwen3.7-max
```

### 什么时候用 Lovmux

适合你，如果你：

1. 希望 Claude App 每次启动都自动从 Zenmux 拉模型列表。
2. 不想把几百个模型写死进 `inferenceModels`。
3. 可以接受本地一直运行一个代理服务。
4. 需要把真实 Zenmux API Key 放在代理侧，而不是保存在 Claude App 配置里。

不适合你，如果你只是普通用户，希望配置一次就能用。普通用户优先用方案 2。

### 安装 Lovmux

```bash
git clone https://github.com/lovstudio/lovmux.git
cd lovmux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 启动 Lovmux

推荐把真实 Zenmux API Key 放在 Lovmux 进程里：

```bash
ZENMUX_PROXY_UPSTREAM_API_KEY="你的 Zenmux API Key" \
uvicorn app:app --host 127.0.0.1 --port 8787
```

不要关闭这个终端窗口。Claude App 调用 Zenmux 时，需要 Lovmux 一直运行。

### 检查 Lovmux

```bash
curl http://127.0.0.1:8787/healthz
```

正常会看到：

```json
{"status":"ok","upstream":"https://zenmux.ai/api/anthropic"}
```

查看模型数量：

```bash
curl "http://127.0.0.1:8787/v1/models?limit=1000" | jq '.data | length'
```

搜索模型：

```bash
curl "http://127.0.0.1:8787/v1/models?q=qwen"
```

### 在 Claude App 里配置 Lovmux

```text
Inference provider: Gateway
Gateway base URL: http://127.0.0.1:8787
Gateway auth scheme: bearer
Credential kind: static
API Key: 任意非空内容，例如 local-placeholder
Model discovery: 开启
```

为什么 API Key 可以填占位内容？

因为真正的 Zenmux API Key 已经在 Lovmux 启动命令里：

```bash
ZENMUX_PROXY_UPSTREAM_API_KEY="你的 Zenmux API Key"
```

Claude App 发来的请求会被 Lovmux 接住，Lovmux 再用真实 Key 转发给 Zenmux。

如果你不想用环境变量，也可以：

1. 启动 Lovmux 时不设置 `ZENMUX_PROXY_UPSTREAM_API_KEY`
2. 在 Claude App 的 API Key 里填真实 Zenmux API Key

Lovmux 会把 Claude App 发来的 Authorization 继续转发给 Zenmux。

## 方案 4：cc-switch 等社区工具

社区里有人推荐 `cc-switch`。这个名字下有多个项目，我查到的主流方向更偏向：

```text
Claude Code / Codex / Gemini CLI 的配置、模型、provider 切换
```

它们可能适合管理多个 CLI 工具的 provider 配置，但是否能直接解决 Claude App 里的第三方 inference `inferenceModels` 导入问题，需要你看具体项目文档和实测。

如果你的目标是：

```text
在 Claude App 图形界面里配置 Zenmux
```

那么优先看方案 1、2、3。

如果你的目标是：

```text
在 Claude Code / Codex CLI 之间快速切换不同 MaaS provider
```

那 `cc-switch` 这类社区工具可能值得研究。

## 为什么不是几千个模型

Lovmux 和脚本默认使用的是 Zenmux 的 Anthropic-compatible endpoint：

```text
https://zenmux.ai/api/anthropic/v1/models
```

这个 endpoint 返回多少模型，Claude App 才可能调用多少模型。

如果你在 Zenmux 官网、模型市场或其它 API 里看到更多模型，不代表它们都会出现在这个 Anthropic-compatible endpoint，也不代表 Claude App 一定能用第三方 inference 调用。

你可以自己检查当前数量：

```bash
curl "https://zenmux.ai/api/anthropic/v1/models?limit=1000" | jq '.data | length'
```

截至 2026-05-23，我实测这个 endpoint 返回 `102` 个模型。

## 常见问题

### 1. 自动发现为什么只有十几个模型

这通常发生在方案 1。

Claude App 官方文档说明 gateway 会从 provider 的 model-list endpoint 自动填充模型选择器，但没有公开完整的筛选规则。你看到 `found 14 models` 时，说明 Claude App 确实发现了一部分模型，但没有把 Zenmux endpoint 返回的所有模型都展示出来。

解决方式：用方案 2，关闭 `modelDiscoveryEnabled`，改用固定 `inferenceModels`。

### 2. 方案 2 导入后，模型能显示但调用失败

常见原因：

1. Zenmux API Key 错误。
2. Zenmux 账户额度不足。
3. 选中的模型在 Zenmux 当前不可用。
4. Claude App 里的 auth scheme 填错。
5. 模型虽然在列表里，但 Zenmux 当前账号没有权限调用。

建议先选 Claude Sonnet 或 Zenmux 后台确认可用的模型测试。

### 3. 固定模型列表会自动更新吗

不会。

如果 Zenmux 新增模型，重新运行：

```bash
python3 scripts/generate_claude_3p_config.py --output claude-zenmux-config.json
```

然后再导入一次。

### 4. Claude App 的模型下拉能不能搜索

目前我没有找到 Claude App 第三方模型下拉框可由 gateway 配置搜索框的官方说明。

Lovmux 自己支持搜索参数，方便你自己做 UI 或调试：

```bash
curl "http://127.0.0.1:8787/v1/models?q=deepseek"
curl "http://127.0.0.1:8787/v1/models?search=qwen%20max"
curl "http://127.0.0.1:8787/v1/models?query=gemini%20flash"
```

但 Claude App 自己的下拉框是否支持搜索，取决于 Claude App 本身。

### 5. 为什么 Lovmux 终端里看到 `HEAD /`

这是 Claude App 或 Electron 做的连通性探测。Lovmux 已经支持 `HEAD /`，看到它是正常现象。

## Lovmux 配置项

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `ZENMUX_PROXY_UPSTREAM_BASE_URL` | `https://zenmux.ai/api/anthropic` | Zenmux 的 Anthropic-compatible endpoint |
| `ZENMUX_PROXY_UPSTREAM_API_KEY` | 空 | 可选。设置后 Lovmux 会用它访问 Zenmux |
| `ZENMUX_PROXY_ROUTE_PREFIX` | `anthropic/claude-route-` | 伪装给 Claude App 的模型 ID 前缀 |
| `ZENMUX_PROXY_DEFAULT_MODEL` | `claude-sonnet-4.6` | 自动发现时优先排到前面的模型 |
| `ZENMUX_PROXY_SYNTHETIC_PREFIX` | `anthropic/` | 兼容早期实验版本的模型 ID |
| `ZENMUX_PROXY_TRUST_ENV` | 空 | 默认直连 Zenmux。设为 `1` 时读取系统里的 `HTTP_PROXY` / `HTTPS_PROXY` 等代理环境变量 |

如果公司网络必须通过代理才能访问 Zenmux，可以这样启动：

```bash
ZENMUX_PROXY_TRUST_ENV=1 \
HTTPS_PROXY="http://127.0.0.1:7890" \
ZENMUX_PROXY_UPSTREAM_API_KEY="你的 Zenmux API Key" \
uvicorn app:app --host 127.0.0.1 --port 8787
```

## 安全注意事项

不要把你的 Zenmux API Key 提交到 GitHub、发给别人，或写进公开文档。

如果你运行 Lovmux，本教程只建议绑定本机地址：

```text
127.0.0.1
```

不要随便改成：

```text
0.0.0.0
```

否则局域网或公网里的其他人可能访问你的代理。

## 参考资料

- [Claude 官方第三方 inference 配置文档](https://claude.com/docs/cowork/3p/configuration)
- [Zenmux Anthropic-compatible models endpoint](https://zenmux.ai/api/anthropic/v1/models)
- [Lovmux GitHub 仓库](https://github.com/lovstudio/lovmux)

## License

MIT
