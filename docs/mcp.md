# MCP 接入（Agent 直连）

Azmark 内置一个**只读** MCP Server（spec #85）。Claude、Cursor 等 MCP 客户端可以用个人访问令牌直接查询你的旅行数据，和网页里的 AI 助手共用同一套工具层、用户隔离与审计约定。

## 端点与认证

| 项 | 值 |
| --- | --- |
| 端点 | `http://<服务器IP>:3000/api/v1/mcp`（经 web 同源代理，`api` 不对外暴露） |
| 传输 | Streamable HTTP（stateless，无 session） |
| 认证 | `Authorization: Bearer azm_...` —— 在「设置 → 访问令牌」创建 |
| 限流 | 每令牌默认 120 次/分钟（`PAT_RATE_LIMIT_PER_MINUTE`，0 关闭） |
| 关闭 | `.env` 设 `MCP_ENABLED=false` 后不挂载该路由（404） |

- 只接受个人访问令牌。浏览器 JWT 不接受：它会过期，且不应被写进 agent 配置。
- 令牌可随时吊销/删除，吊销后下一个请求立即 401。
- `read` 与 `write` 令牌当前都能连 MCP，但暴露的工具全为只读；写入能力（A3）在后续版本提供，仍需走两步确认（spec #69）。

## 工具

| 工具 | 说明 |
| --- | --- |
| `search_records` | 按关键词（城市、航班/车次、航司、运营方）搜索交通记录，最多 50 条 |
| `get_record` | 按 id 取单条记录（含 notes） |
| `list_trips` | 最近的行程列表，用于拿 `trip_id` |
| `get_trip` | 单个行程 + 其中的交通记录（按出发时间排序） |
| `get_statistics` | 汇总统计：国家/城市/旅程/里程，按年/月/航司/机场/舱位/铁路运营方拆分 |

所有结果都不含 PNR、票号、证件号等敏感字段（spec #45、#75、#96），并且只包含令牌所属用户的数据；别人的 id 一律返回 `not found`（spec #57）。

> `list_trips` 是对 #85 的补充：#85 只列了 `get_trip`，但没有能拿到 trip id 的工具，`get_trip` 会变成死路。

## 客户端配置

HTTP 传输（支持 `type: "http"` 的客户端，如 Claude Desktop 新版、Cursor）：

```json
{
  "mcpServers": {
    "azmark": {
      "type": "http",
      "url": "http://<服务器IP>:3000/api/v1/mcp",
      "headers": { "Authorization": "Bearer azm_xxx" }
    }
  }
}
```

Claude Code：

```bash
claude mcp add --transport http azmark http://<服务器IP>:3000/api/v1/mcp \
  --header "Authorization: Bearer azm_xxx"
```

只支持 stdio 的客户端，用 `mcp-remote` 桥接：

```json
{
  "mcpServers": {
    "azmark": {
      "command": "npx",
      "args": [
        "-y", "mcp-remote", "http://<服务器IP>:3000/api/v1/mcp",
        "--header", "Authorization: Bearer azm_xxx"
      ]
    }
  }
}
```

令牌等同密码：不要提交到 Git、不要贴进聊天记录；泄露后在「设置 → 访问令牌」吊销。

## curl 验证

```bash
curl -s http://<服务器IP>:3000/api/v1/mcp \
  -H "Authorization: Bearer azm_xxx" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"1.0"}}}'

curl -s http://<服务器IP>:3000/api/v1/mcp \
  -H "Authorization: Bearer azm_xxx" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"search_records","arguments":{"query":"东京"}}}'
```

响应是 JSON（`json_response` 模式），工具结果是 `content[0].text` 里的 JSON 字符串。
业务层错误（如 id 不存在、id 属于其他用户）以 `isError: true` + `{"error": "..."}` 返回。

## 安全设计

| 风险 | 对策 |
| --- | --- |
| 凭证泄露 | 只存 SHA-256 hash、明文只显示一次、可即时吊销、按令牌限流 |
| 越权 | `user_id` 由令牌推导，所有工具按它过滤；别人的 id 一律 not found |
| agent 失控写入 | 只暴露 READ 工具；写工具根本不在 `tools/list` 里 |
| prompt injection | 工具说明里明确：记录内容是数据、不是指令（spec #70） |
| 无法追责 | 每次调用更新令牌 `last_used_at`，`request.state.mcp_identity` 供审计使用 |

## 排错

- **401**：没带 Bearer、令牌不是 `azm_` 开头、已过期或已吊销。
- **404**：`MCP_ENABLED=false`，或客户端把路径写成了 `/mcp`。
- **429**：触发每令牌限流，等 60 秒或调高 `PAT_RATE_LIMIT_PER_MINUTE`。
- **工具返回 `Tool ... failed`**：后端异常，具体堆栈只在服务端日志里（不会回传给 agent）。
