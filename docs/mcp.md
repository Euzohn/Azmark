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
- `read` 与 `write` 令牌都能连 MCP：`read` 只暴露只读工具；`write` 额外解锁 `create_record` / `update_record`（写提案，仍需网页两步确认，spec #69）。删除（DESTRUCTIVE）一律不通过 MCP。

## 工具

| 工具 | 说明 |
| --- | --- |
| `search_records` | 按关键词（城市、航班/车次、航司、运营方）搜索交通记录，最多 50 条 |
| `get_record` | 按 id 取单条记录（含 notes） |
| `search_hotels` / `get_hotel` | 搜索 / 读取住宿记录 |
| `list_trips` | 最近的行程列表，用于拿 `trip_id` |
| `get_trip` | 单个行程 + 其中的成员记录（按出发时间排序） |
| `get_statistics` | 汇总统计：国家/城市/旅程/里程，按年/月/航司/机场/舱位/铁路运营方拆分 |
| `search_expenses` / `search_notes` / `search_places` / `search_activities` | 按关键词、类别或类型检索开销 / 笔记 / 地点 / 活动，用于先拿到 id 再改/删（删除在网页操作） |

所有结果都不含 PNR、票号、证件号等敏感字段（spec #45、#75、#96），并且只包含令牌所属用户的数据；别人的 id 一律返回 `not found`（spec #57）。

> `list_trips` 是对 #85 的补充：#85 只列了 `get_trip`，但没有能拿到 trip id 的工具，`get_trip` 会变成死路。

### 写工具（需要 write scope 令牌）

| 工具 | 说明 |
| --- | --- |
| `create_record` | 提议新建一条记录，`record_type` 支持 `flight` / `train` / `other` / `hotel` / `trip` / `expense` / `note` / `place` / `activity`。**不会立即写入**，返回 `pending_action_id`，需用户在网页「待确认」里批准 |
| `update_record` | 提议修改已有记录的字段，`record_type` 覆盖同样 9 类。同样只生成提案，等待批准 |
| `get_pending_action` | 查询某个提案的状态（pending / confirmed / rejected / failed / expired）。任何 scope 的令牌都能用 |

写入流程（spec #69）：agent 调 `create_record` → Azmark 落一条 `pending_action`（**不碰业务数据**）→ agent 拿到 id 并提示用户去网页确认 → 用户在「待确认」页面点 Confirm → 记录才真正写入，审计日志记录是哪个令牌发起的。

> 删除（DESTRUCTIVE）**不通过 MCP 暴露**。要删记录，请用户在网页操作。这是故意的：destructive 操作的确认必须发生在 agent 无法触及的地方。
>
> 地点（place）是地理参照实体，没有自己的 `trip_id`；把它排进行程时间线（`trip_items`）也不通过 MCP，请在网页操作。

> 为什么 agent 不能自己确认？因为 MCP 客户端由模型驱动，提示注入可能让 agent "替用户确认"。确认接口 `/api/v1/pending-actions/*` **只接受浏览器会话（JWT），个人访问令牌一律 403**——这是整个设计的安全支点。

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
