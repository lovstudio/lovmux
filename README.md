# Lovmux

在 Claude App 里接入 Zenmux。

推荐普通用户使用 **方案 A**：直接用 Zenmux 官方 `apiBase`，关闭自动发现，一次性导入模型列表。不需要运行 Lovmux 代理。

## 先看结论

Claude App 的第三方 inference 配置里，调用地址和模型列表可以分开：

- `inferenceGatewayBaseUrl`：真正请求发到哪里。
- `modelDiscoveryEnabled` / `inferenceModels`：模型下拉框显示什么。

| 方案 | 怎么做 | 适合谁 |
| --- | --- | --- |
| A. 官方 apiBase + 固定模型列表 | 推荐。直连 Zenmux，导入 `inferenceModels` | 普通用户 |
| B. 官方 apiBase + 自动发现 | 最简单，但可能只看到十几个模型 | 快速测试 |
| C. Lovmux 代理 + 自动发现 | 需要本地维护代理 | 企业、极客 |
| D. cc-switch 等工具 | 主要面向 CLI 配置切换 | 进阶用户自行确认 |

截至 2026-05-23，`https://zenmux.ai/api/anthropic/v1/models?limit=1000` 实测返回 `102` 个模型。你在 Claude App 里直接自动发现只看到约 `14` 个，是 Claude App 自动发现阶段可能做了筛选。

## 方案 A：推荐，导入固定模型列表

这个方案最稳：

- Claude App 直接请求 Zenmux 官方接口。
- 不需要 Lovmux 常驻运行。
- 可以显示 Qwen、Gemini、OpenAI、DeepSeek 等非 Anthropic 风格模型。

### 1. 生成配置

```bash
git clone https://github.com/lovstudio/lovmux.git
cd lovmux
python3 scripts/generate_claude_3p_config.py --output claude-zenmux-config.json
```

脚本会生成一个 Claude App 可导入的 JSON：

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
    }
  ]
}
```

### 2. 导入 Claude App

打开：

```text
Settings -> Cowork -> Configure third-party inference -> View as JSON
```

把 `claude-zenmux-config.json` 里的内容粘进去。

然后把：

```text
PASTE_YOUR_ZENMUX_API_KEY_HERE
```

替换成你的 Zenmux API Key，保存并重启 Claude App。

确认这几个字段：

```text
inferenceGatewayBaseUrl = https://zenmux.ai/api/anthropic
modelDiscoveryEnabled = false
inferenceModels = 很多模型
```

### 常用脚本参数

只生成模型数组：

```bash
python3 scripts/generate_claude_3p_config.py --format models --output inference-models.json
```

指定默认模型，也就是排到列表第一项：

```bash
python3 scripts/generate_claude_3p_config.py \
  --default-model qwen/qwen3.7-max \
  --output claude-zenmux-config.json
```

限制模型数量：

```bash
python3 scripts/generate_claude_3p_config.py --max-models 30 --output claude-zenmux-config.json
```

## 方案 B：最简单，自动发现

Claude App 里直接填：

```text
Inference provider: Gateway
Gateway base URL: https://zenmux.ai/api/anthropic
Gateway auth scheme: bearer
Credential kind: static
API Key: 你的 Zenmux API Key
Model discovery: 开启
```

缺点：可能只看到十几个模型，例如：

```text
Model discovery - found 14 models
```

如果你想显示更多模型，改用方案 A。

## 方案 C：高级，运行 Lovmux 代理

Lovmux 是本地 FastAPI 代理：

```text
Claude App -> Lovmux -> Zenmux
```

它会把 Zenmux 的模型 ID 包装成 Claude App 更容易接受的形式。例如：

```text
qwen/qwen3.7-max
-> anthropic/claude-route-cXdlbi9xd2VuMy43LW1heA
```

实际调用时再还原成：

```text
qwen/qwen3.7-max
```

适合需要自动发现模型、统一管理 API Key、或企业内部部署的人。普通用户优先用方案 A。

### 安装与启动

```bash
git clone https://github.com/lovstudio/lovmux.git
cd lovmux
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

ZENMUX_PROXY_UPSTREAM_API_KEY="你的 Zenmux API Key" \
uvicorn app:app --host 127.0.0.1 --port 8787
```

检查：

```bash
curl http://127.0.0.1:8787/healthz
curl "http://127.0.0.1:8787/v1/models?limit=1000" | jq '.data | length'
```

Claude App 里填：

```text
Gateway base URL: http://127.0.0.1:8787
Gateway auth scheme: bearer
API Key: 任意非空内容，例如 local-placeholder
Model discovery: 开启
```

如果你不设置 `ZENMUX_PROXY_UPSTREAM_API_KEY`，也可以在 Claude App 里直接填真实 Zenmux API Key，Lovmux 会转发 Authorization。

## 方案 D：cc-switch 等社区工具

社区里有人推荐 `cc-switch`。我查到的主流用途更偏向 Claude Code / Codex / Gemini CLI 的 provider 切换，不是 Claude App 第三方 inference 的官方导入方案。

如果你要配置 Claude App 图形界面，先看方案 A、B、C。

## 常见问题

### 为什么不是几千个模型？

这里使用的是 Zenmux 的 Anthropic-compatible endpoint：

```text
https://zenmux.ai/api/anthropic/v1/models
```

Claude App 能不能调用，取决于模型是否出现在这个 endpoint，而不是 Zenmux 官网其它页面展示了多少模型。

### 导入后模型能显示，但调用失败？

常见原因：

- Zenmux API Key 错误。
- 账户额度不足。
- 模型当前不可用或账号没有权限。
- Claude App 的 auth scheme 填错。

先用 Claude Sonnet 或 Zenmux 后台确认可用模型测试。

### 固定模型列表会自动更新吗？

不会。Zenmux 新增模型后，重新运行脚本并导入一次。

### Claude App 下拉框能搜索吗？

目前没有找到官方配置项能给第三方模型下拉框加搜索。Lovmux 自己支持调试用搜索：

```bash
curl "http://127.0.0.1:8787/v1/models?q=qwen"
```

## Lovmux 环境变量

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `ZENMUX_PROXY_UPSTREAM_BASE_URL` | `https://zenmux.ai/api/anthropic` | Zenmux endpoint |
| `ZENMUX_PROXY_UPSTREAM_API_KEY` | 空 | 代理侧 Zenmux API Key |
| `ZENMUX_PROXY_ROUTE_PREFIX` | `anthropic/claude-route-` | 模型 ID 包装前缀 |
| `ZENMUX_PROXY_DEFAULT_MODEL` | `claude-sonnet-4.6` | 自动发现时优先模型 |
| `ZENMUX_PROXY_TRUST_ENV` | 空 | 设为 `1` 后读取 `HTTP_PROXY` / `HTTPS_PROXY` |

## 安全提醒

- 不要把 Zenmux API Key 提交到 GitHub。
- Lovmux 默认只建议绑定 `127.0.0.1`。
- 不要随便绑定 `0.0.0.0`，除非你知道如何做访问控制。

## 参考

- [Claude 第三方 inference 配置文档](https://claude.com/docs/cowork/3p/configuration)
- [Zenmux models endpoint](https://zenmux.ai/api/anthropic/v1/models)

## License

MIT
