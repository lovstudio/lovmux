# Lovmux

Lovmux 是一个跑在你电脑本地的小代理服务，用来让 Claude App 的第三方 inference gateway 更好地接入 Zenmux。

简单说：

1. Claude App 连接 Lovmux
2. Lovmux 连接 Zenmux
3. Claude App 自动发现更多 Zenmux 模型
4. 你在 Claude App 里直接切换模型

## 为什么需要 Lovmux

Claude App 的第三方 inference gateway 支持配置自定义 `apiBase`，但它的模型发现有一个产品侧限制：模型 ID 需要看起来像 Anthropic/Claude 模型，例如：

```text
claude-*
anthropic/claude-*
```

Zenmux 这类 MaaS 平台会提供很多模型，比如：

```text
qwen/qwen3.7-max
google/gemini-3.5-flash
openai/gpt-5.5
deepseek/deepseek-v4-flash
```

这些模型本身是可用的，但 Claude App 的第三方模型选择器可能不会完整展示它们。你可能会遇到：

```text
Model discovery — found 14 models
```

明明 Zenmux 有很多模型，但 Claude App 最后只发现十几个。

Lovmux 的作用就是做一层“翻译”：

```text
qwen/qwen3.7-max
```

会被展示给 Claude App 为：

```text
anthropic/claude-route-cXdlbi9xd2VuMy43LW1heA
```

Claude App 看到的是合法的 `anthropic/claude-*` 风格模型 ID。实际调用模型时，Lovmux 会再把它还原成：

```text
qwen/qwen3.7-max
```

所以最终效果是：Claude App 里能看到并切换更多 Zenmux 模型，真正请求仍然转发给 Zenmux。

## 适合谁

适合你，如果你：

1. 已经有 Zenmux API Key
2. 想在 Claude App 的第三方 inference 里使用 Zenmux
3. 想让 Claude App 的模型下拉列表自动出现更多模型
4. 不想手动维护一大串 `inferenceModels`

不适合你，如果你只是想用 Claude 官方订阅账号。Lovmux 只解决第三方 gateway 接入 MaaS 的问题。

## 准备工作

你需要：

1. macOS 上已经安装 Claude App
2. 已经有 Zenmux API Key
3. 电脑上有 Python 3

检查 Python：

```bash
python3 --version
```

如果能看到类似 `Python 3.x.x`，就可以继续。

## 安装 Lovmux

先下载项目：

```bash
git clone https://github.com/lovstudio/lovmux.git
cd lovmux
```

创建 Python 虚拟环境：

```bash
python3 -m venv .venv
```

启用虚拟环境：

```bash
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

## 启动 Lovmux

推荐方式：把 Zenmux API Key 放在 Lovmux 进程里。

```bash
ZENMUX_PROXY_UPSTREAM_API_KEY="你的 Zenmux API Key" \
uvicorn app:app --host 127.0.0.1 --port 8787
```

看到类似下面的输出，表示启动成功：

```text
Uvicorn running on http://127.0.0.1:8787
```

不要关闭这个终端窗口。Claude App 调用 Zenmux 时，需要 Lovmux 一直运行。

## 检查 Lovmux 是否正常

新开一个终端窗口，运行：

```bash
curl http://127.0.0.1:8787/healthz
```

正常会看到：

```json
{"status":"ok","upstream":"https://zenmux.ai/api/anthropic"}
```

再检查模型列表：

```bash
curl "http://127.0.0.1:8787/v1/models?limit=1000"
```

如果返回一大段 JSON，就说明模型发现接口正常。

## 配置 Claude App

打开 Claude App，进入第三方 inference 配置页面。

一般路径是：

```text
Settings → Cowork → Configure third-party inference
```

按下面填写：

```text
Inference provider: Gateway
Gateway base URL: http://127.0.0.1:8787
Gateway auth scheme: bearer
Credential kind: static
API Key: 任意非空内容，例如 local-placeholder
Model discovery: 开启
```

为什么 API Key 可以填占位内容？

因为我们推荐把真正的 Zenmux API Key 放在 Lovmux 启动命令里：

```bash
ZENMUX_PROXY_UPSTREAM_API_KEY="你的 Zenmux API Key"
```

这样 Claude App 不需要保存真实 Zenmux Key。它发来的请求会被 Lovmux 接住，Lovmux 再用真实 Key 转发给 Zenmux。

如果你不想用环境变量，也可以：

1. 启动 Lovmux 时不设置 `ZENMUX_PROXY_UPSTREAM_API_KEY`
2. 在 Claude App 的 API Key 里填真实 Zenmux API Key

Lovmux 会把 Claude App 发来的 Authorization 继续转发给 Zenmux。

## 验证 Claude App 是否成功

保存配置后，重启 Claude App。

打开模型切换下拉框，如果看到类似下面的模型，就说明成功：

```text
Claude Sonnet 4.6
Qwen: Qwen3.7-Max
Google: Gemini 3.5 Flash
OpenAI: GPT-5.5
DeepSeek: DeepSeek V4 Flash
```

如果你能看到几十个甚至上百个模型，就说明 Claude App 已经通过 Lovmux 自动发现模型了。

## 模型 ID 是怎么翻译的

Lovmux 使用可逆算法，不需要数据库。

原始模型：

```text
qwen/qwen3.7-max
```

先做 URL-safe Base64 编码，去掉末尾的 `=`：

```text
cXdlbi9xd2VuMy43LW1heA
```

再加上 Claude App 能接受的前缀：

```text
anthropic/claude-route-cXdlbi9xd2VuMy43LW1heA
```

实际调用时反向解码：

```text
anthropic/claude-route-cXdlbi9xd2VuMy43LW1heA
→ qwen/qwen3.7-max
```

所以 Lovmux 重启后也能还原模型，不依赖内存状态。

## 常见问题

1）Claude App 里还是只发现十几个模型

通常是 Claude App 没有连到 Lovmux，而是直接连到了 Zenmux。

检查 Gateway base URL 是否是：

```text
http://127.0.0.1:8787
```

不要填：

```text
https://zenmux.ai/api/anthropic
```

直接填 Zenmux 时，Claude App 可能会过滤掉大量非 Anthropic 模型。

2）Claude App 里没有模型

先确认 Lovmux 是否还在运行：

```bash
curl http://127.0.0.1:8787/healthz
```

如果连不上，回到启动 Lovmux 的终端，重新运行：

```bash
source .venv/bin/activate
ZENMUX_PROXY_UPSTREAM_API_KEY="你的 Zenmux API Key" \
uvicorn app:app --host 127.0.0.1 --port 8787
```

3）模型列表有了，但调用时报错

常见原因：

1. Zenmux API Key 填错
2. Zenmux 账户额度不足
3. 选中的模型在 Zenmux 当前不可用
4. Claude App 里填了错误的 auth scheme

建议先用 Claude Sonnet 或 Zenmux 后台确认可用的模型测试。

4）为什么默认模型不是我想要的

Claude App 自动发现时通常会把模型列表第一项当成默认模型。Lovmux 默认会优先把 `claude-sonnet-4.6` 放前面。

如果你想换默认优先模型，可以启动时加：

```bash
ZENMUX_PROXY_DEFAULT_MODEL="deepseek-v4-flash" \
ZENMUX_PROXY_UPSTREAM_API_KEY="你的 Zenmux API Key" \
uvicorn app:app --host 127.0.0.1 --port 8787
```

5）Claude App 的模型下拉能不能搜索

目前 Claude App 原生第三方模型下拉没有开放搜索框配置。Lovmux 可以提供搜索参数，方便你自己做 UI：

```bash
curl "http://127.0.0.1:8787/v1/models?q=deepseek"
curl "http://127.0.0.1:8787/v1/models?search=qwen%20max"
curl "http://127.0.0.1:8787/v1/models?query=gemini%20flash"
```

但 Claude App 自己的下拉框是否支持搜索，取决于 Claude App 本身。

6）为什么终端里看到 `HEAD /`

这是 Claude App 或 Electron 做的连通性探测。Lovmux 已经支持 `HEAD /`，看到它是正常现象。

7）为什么不是几千个模型

Lovmux 展示的是 Zenmux 这个 Anthropic-compatible 端点实际返回的模型：

```text
https://zenmux.ai/api/anthropic/v1/models
```

如果你在 Zenmux 官网、模型市场或其它 API 里看到更多模型，不代表它们都会出现在这个 Anthropic-compatible endpoint，也不代表 Claude App 一定能用第三方 inference 调用。

可以用下面命令查看当前这个端点到底返回多少个模型：

```bash
curl "https://zenmux.ai/api/anthropic/v1/models?limit=1000" | jq '.data | length'
```

Lovmux 能解决的是“Claude App 过滤非 Anthropic 风格模型 ID”的问题；它不能凭空把 Zenmux 没有暴露在这个 endpoint 里的模型变成可调用模型。

## 常用命令

启动：

```bash
cd lovmux
source .venv/bin/activate
ZENMUX_PROXY_UPSTREAM_API_KEY="你的 Zenmux API Key" \
uvicorn app:app --host 127.0.0.1 --port 8787
```

检查健康状态：

```bash
curl http://127.0.0.1:8787/healthz
```

查看模型数量：

```bash
curl "http://127.0.0.1:8787/v1/models?limit=1000" | jq '.data | length'
```

搜索模型：

```bash
curl "http://127.0.0.1:8787/v1/models?q=qwen"
```

## 配置项

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `ZENMUX_PROXY_UPSTREAM_BASE_URL` | `https://zenmux.ai/api/anthropic` | Zenmux 的 Anthropic-compatible endpoint |
| `ZENMUX_PROXY_UPSTREAM_API_KEY` | 空 | 可选。设置后 Lovmux 会用它访问 Zenmux |
| `ZENMUX_PROXY_ROUTE_PREFIX` | `anthropic/claude-route-` | 伪装给 Claude App 的模型 ID 前缀 |
| `ZENMUX_PROXY_DEFAULT_MODEL` | `claude-sonnet-4.6` | 自动发现时优先排到前面的模型 |
| `ZENMUX_PROXY_SYNTHETIC_PREFIX` | `anthropic/` | 兼容早期实验版本的模型 ID |
| `ZENMUX_PROXY_TRUST_ENV` | 空 | 默认直连 Zenmux。设为 `1` 时读取系统里的 `HTTP_PROXY` / `HTTPS_PROXY` 等代理环境变量 |

## 注意事项

Lovmux 是本地代理，不是云服务。Claude App 要使用它时，你的电脑上必须保持 Lovmux 正在运行。

不要把你的 Zenmux API Key 提交到 GitHub、发给别人，或写进公开文档。

如果你把 Lovmux 部署到远程服务器，请务必加访问控制。默认教程只建议绑定本机地址：

```text
127.0.0.1
```

不要随便改成：

```text
0.0.0.0
```

否则局域网或公网里的其他人可能访问你的代理。

如果公司网络必须通过代理才能访问 Zenmux，可以这样启动：

```bash
ZENMUX_PROXY_TRUST_ENV=1 \
HTTPS_PROXY="http://127.0.0.1:7890" \
ZENMUX_PROXY_UPSTREAM_API_KEY="你的 Zenmux API Key" \
uvicorn app:app --host 127.0.0.1 --port 8787
```

## License

MIT
