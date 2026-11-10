# 客户端 IP 与反向代理（spec #47、#96）

审计日志里的「客户端」列要能反映真实来源，才能做溯源。这份文档说明审计 IP
是怎么一路传下来的、`TRUSTED_PROXIES` 该怎么配，以及可选的宿主机 nginx 加固
（收紧端口、杜绝伪造）。

## 链路

```text
浏览器 → 公网IP:3000 → Docker 端口映射(DNAT) → web 容器(:3000, Next.js)
       → X-Forwarded-For → api 容器(:8000, 写审计)
```

## 事实一：标准 Docker 会保留真实源地址

标准 Linux 上的 Docker 对外发布端口用 DNAT：只改**目的**地址，源地址原样
保留。因此 web 容器通过 socket 看到的 `remoteAddress` 就是客户端的真实 IP。
宿主机自身发起的连接（如 `curl 127.0.0.1:3000`）例外——hairpin 会把源地址
改写成网桥网关，这是预期行为。

Next.js 在请求**没有** `X-Forwarded-For` 时，会用 socket 地址补上这个头再
透传给 api（见 `next/dist/server/base-server.js` 中的
`req.headers['x-forwarded-for'] ??= socket.remoteAddress`），真实 IP 由此进入
内网链路。

## 事实二：api 的直连 peer 永远是 web 容器

审计是 api 写的，而 web → api 是 compose 内部网络的一跳。api 看到的
`request.client.host` 是 web 容器的地址（如 `172.21.0.6`），不是客户端。
默认 `TRUSTED_PROXIES` 为空 = 谁都不信，api 不采信 XFF，只能记下这个内网
地址。

**所以默认配置下审计显示 `172.21.0.x` 是必然的，与有没有 nginx 无关。**
要让审计记到真实 IP，只需显式声明「web 容器是可信代理」。

## 配置：让 api 信任 web 的转发

`.env`：

```dotenv
# api 的直连 peer 是 web 容器，取 compose 网络网段：
#   docker network inspect azmark_default --format '{{(index .IPAM.Config 0).Subnet}}'
TRUSTED_PROXIES=172.21.0.0/16
```

```bash
docker compose up -d api
docker compose exec api env | grep TRUSTED_PROXIES   # 确认配置进了容器
```

**直连 `IP:3000` 就能生效，不需要 nginx**：外部流量的真实 IP 由 DNAT 原样
送达 web 容器 → Next 注入 XFF → api 按白名单采信。

## 验证

```bash
# 1) 容器里确有配置（输出为空说明没重建，用 --force-recreate api）
docker compose exec api env | grep TRUSTED_PROXIES

# 2) 用手机流量访问 http://<公网IP>:3000，做一次操作，
#    审计日志「客户端」列 → 应为手机的公网出口 IP
```

| 审计显示 | 含义 |
| --- | --- |
| 手机公网 IP | ✅ 正常 |
| `172.21.0.6`（web 容器） | api 没采信 XFF：`TRUSTED_PROXIES` 未设置、没进容器或网段不对 |
| `172.21.0.1`（网桥网关） | 服务器上有一条非标准 MASQUERADE 规则，见下节 |

宿主机上 `curl 127.0.0.1:3000` 触发的操作（若写审计）会显示 web 容器地址，
这是 hairpin 的正常结果，不代表配置有问题。

## 排查：审计显示 `172.21.0.1`（网关）

标准 Docker 不会改写外部流量的源地址。若审计出现网桥网关，说明 iptables 里
有一条非标准的宽规则，把进入网桥的流量 SNAT 成了网关：

```bash
sudo iptables -t nat -S POSTROUTING | grep -i masquerade
```

正常的规则只有三种形态（`br-xxx` 为该网络的网桥）：

```text
-A POSTROUTING -o br-xxx -m addrtype --src-type LOCAL -j MASQUERADE          # 宿主机本地源
-A POSTROUTING -s 172.21.0.0/16 ! -o br-xxx -j MASQUERADE                    # 容器出站
-A POSTROUTING -s 172.21.0.6/32 -d 172.21.0.6/32 --dport 3000 -j MASQUERADE  # 端口 hairpin
```

若出现 `-s 0.0.0.0/0 -d 172.21.0.0/16 -o br-xxx -j MASQUERADE` 这类「源地址
任意、目的为整个网段」的规则，删掉它：

```bash
sudo iptables -t nat -D POSTROUTING -s 0.0.0.0/0 -d 172.21.0.0/16 -o br-xxx -j MASQUERADE
```

compose 网络重建（`docker compose down` 后再 `up`）时，旧网桥的残留规则通常
会一并消失。

## 白名单语义

`X-Forwarded-For` 是普通请求头，任何客户端都能自己带一个。所以 `client_ip()`
是白名单制：

| 直连 peer（`request.client.host`） | 取值 |
| --- | --- |
| 命中 `TRUSTED_PROXIES` 的网段 | 从 `X-Forwarded-For` 右往左找，取第一个不在可信网段内的地址 |
| 不在白名单（含空白名单默认值） | 用 peer 地址本身 |

从右往左取，而不是直接取第一段，是因为链路里只有最右侧那几跳是可信的：
客户端自己塞进头里的伪造值会留在左边，无论代理是覆盖还是追加写入都骗不到。
头里出现非 IP 的畸形值时整条头都不采信，回退到 peer 地址。

空白名单 = 谁都不信，是最安全的默认值。配置项按逗号分隔 CIDR，非法项会被
跳过（丢一项只是回到「不信任」，不会让服务起不来）。

### 直连模式的局限

按上面的配置直连 `:3000` 时，任何能访问该端口的人都可以伪造 XFF（Next 只在
头不存在时注入，不会覆盖已存在的值），审计 IP 因此只是「尽力而为」。要杜绝
伪造，用下一节的 nginx 加固——它覆盖写入 XFF，并把 3000 收回本机。

## 可选加固：宿主机 nginx

适用场景：收紧对外端口、杜绝 XFF 伪造、以后上 HTTPS。

```text
浏览器 → nginx(宿主机 :80, $remote_addr = 真实 IP)
       → web 容器(127.0.0.1:3000) → api 容器(:8000)
```

### 1. 写配置

把下面的 `server` 块放进 nginx 的 http 配置里。具体路径取决于发行版：
Debian/Ubuntu 用 `/etc/nginx/sites-available/azmark.conf` 并软链到
`sites-enabled/`，RHEL 系用 `/etc/nginx/conf.d/azmark.conf`。

```nginx
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        # 覆盖而不是追加：$proxy_add_x_forwarded_for 会保留客户端自带的
        # 伪造值。api 侧从右往左跳过可信跳是第二层防护。
        proxy_set_header X-Forwarded-For $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # AI 流式响应与 MCP 的 SSE 需要关缓冲，否则会卡住不出字。
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

```bash
nginx -t && systemctl enable --now nginx
```

如果宿主机 80 端口已被别的站点占用，把 `server_name _` 换成 Azmark 实际使用
的域名或 IP，只接管该 Host 的请求，不影响现有站点。

若服务器前面还有防火墙或云平台安全组，记得放通入方向 TCP 80。

### 2. 收紧 web 端口

`.env`：

```dotenv
WEB_BIND_IP=127.0.0.1
```

然后 `docker compose up -d web`。此后 3000 只绑回环，外部只能走 nginx。

### 3. TRUSTED_PROXIES 不用改

前面配好的 compose 网段继续沿用：经 nginx 访问时 api 的 peer 仍是 web 容器，
机制完全相同。

## 回滚

```bash
# 退回直连：.env 里删掉 WEB_BIND_IP（默认就是 0.0.0.0）
docker compose up -d web
systemctl disable --now nginx
```

审计仍会记录真实 IP（`TRUSTED_PROXIES` 保留即可），只是失去防伪造加固。

## 贴诊断信息时如何打码

排查网络问题时经常要贴 `tcpdump`、`ss`、`docker inspect`、审计日志，注意：

| 内容 | 处理 |
| --- | --- |
| 公网 IP（如 `203.0.113.7`） | **必须打码**，可定位到城市/运营商/个人网络 |
| 主机名、实例 ID、容器 ID | 建议打码，可能含实例唯一标识 |
| 内网 IP（`172.16-31.x.x`、`10.x`、`192.168.x`） | 危害小，可保留 |
| 容器名、临时端口、Docker 网桥网段 | 无需处理 |
| 密钥、token、PNR、票号、护照信息 | **绝不外发**（spec #45、#75、#96） |

打码方式：把地址替换成 `x.x.x.x` 即可，不要保留后两段。