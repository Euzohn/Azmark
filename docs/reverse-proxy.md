# 反向代理与客户端 IP（spec #47、#96）

审计日志里的「客户端」列要能反映真实来源，才能做溯源和限流。这份文档说明
为什么直接 `IP:3000` 访问时记录到的是内网地址、怎么用 nginx 反代修好，以及
`TRUSTED_PROXIES` 为什么必须配合反代一起用。

## 现象

服务器上用 `http://<公网IP>:3000` 访问，审计日志「客户端」列显示
`172.21.0.1` 之类的 Docker 网桥地址，而不是手机/电脑的公网 IP。

## 链路与根因

直连 3000 时的实际链路：

```text
浏览器 → 公网IP:3000 → Docker 端口映射 → web 容器(:3000)
       → Next.js 服务端反代(/api/*) → api 容器(:8000)
```

1. **Docker 端口映射改写了源地址。** 容器网络里有一条自动生成的规则：

   ```text
   MASQUERADE all -- * br-xxxx 0.0.0.0/0 172.21.0.0/16
   ```

   它把「发往容器网段」的流量源地址改成网桥网关。原本是为宿主机访问容器
   准备的 hairpin 规则，但外部进来的流量也一起被改了。抓包可以直接看到：

   ```text
   # 宿主机外网网卡：真实 IP 完好
   203.0.113.7.13270 > 10.0.0.5.3000
   # 到容器网桥：源地址已经变成网关
   172.21.0.1.59260 > 172.21.0.6.3000
   ```

   这条规则与 `userland-proxy` 无关，关掉它也不会消失。

2. **Next.js 把拿到的源地址写进 X-Forwarded-For。** 请求没有 XFF 时，
   Next 会注入 `X-Forwarded-For: <socket.remoteAddress>`，也就是上一步那个
   网关地址，然后原样透传给 api。

3. **api 读到的是伪造/错误的 XFF。** 于是审计记下 `172.21.0.1`。

**结论：真实 IP 在到达 web 容器前就丢了，应用层无法自行恢复。** 必须在
Docker 端口映射之前（宿主机上）接一跳能直接看到客户端 socket 的代理。

## 修复：宿主机 nginx 反代

```text
浏览器 → nginx(宿主机 :80, $remote_addr = 真实 IP)
       → web 容器(127.0.0.1:3000) → api 容器(:8000)
```

nginx 在宿主机上直连网卡，`$remote_addr` 就是真实客户端地址；它覆盖写入
`X-Forwarded-For`，Next 见到该头已存在就不再改写，api 最终拿到真实 IP。

### 1. 安装并写配置

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
        # 推荐覆盖而不是追加：$proxy_add_x_forwarded_for 会保留客户端自带的
        # 伪造值。api 侧也会从右往左跳过可信跳，属于第二层防护。
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

`docker-compose.yml` 里 web 默认对外直连，配置了 nginx 后建议改成只绑回环，
外部就只能走 nginx：

```yaml
ports:
  - "${WEB_BIND_IP:-0.0.0.0}:${WEB_PORT:-3000}:3000"
```

`.env` 里设 `WEB_BIND_IP=127.0.0.1` 即启用收紧；不设则保持 `0.0.0.0`，
外部仍可绕过 nginx 直连 3000（审计会记到网桥网关）。

### 3. 声明可信代理

`.env`：

```dotenv
# api 的直连 peer 是 web 容器，取 compose 网络网段：
#   docker network inspect azmark_default --format '{{(index .IPAM.Config 0).Subnet}}'
TRUSTED_PROXIES=172.21.0.0/16
```

然后 `docker compose up -d`。

## TRUSTED_PROXIES 为什么必需

`X-Forwarded-For` 是普通请求头，任何客户端都能自己带一个。若无条件采信：

```bash
curl -H 'X-Forwarded-For: 1.2.3.4' http://<host>/api/v1/auth/login
```

审计日志就会全部算到 `1.2.3.4` 头上，溯源彻底失效；以后若按 IP 做限流或封禁，
也会被一并绕过。所以 `client_ip()` 改成白名单制：

| 直连 peer（`request.client.host`） | 取值 |
| --- | --- |
| 命中 `TRUSTED_PROXIES` 的网段 | 从 `X-Forwarded-For` 右往左找，取第一个不在可信网段内的地址 |
| 不在白名单（含空白名单默认值） | 用 peer 地址本身 |

从右往左取，而不是直接取第一段，是因为链路里只有最右侧那几跳是可信的：
客户端自己塞进头里的伪造值会留在左边，无论代理是覆盖还是追加写入都骗不到。
头里出现非 IP 的畸形值时整条头都不采信，回退到 peer 地址。

空白名单 = 谁都不信，是最安全的默认值；接上反代后再显式声明。配置项按逗号
分隔 CIDR，非法项会被跳过（丢一项只是回到「不信任」，不会让服务起不来）。

## 验证

```bash
# 1) nginx 自身可达（宿主机回环，deploy.sh 的健康检查也走这条）
curl -fsS http://localhost:3000/api/v1/health
curl -fsS http://localhost/api/v1/health

# 2) 用手机流量（不要连同一 WiFi）访问 http://<公网IP>，
#    做一次操作，再看审计日志「客户端」列 → 应为手机的公网出口 IP
```

`172.x` / `10.x` 开头说明还是内网地址：确认访问的是 80（经 nginx）而不是
3000，且 `TRUSTED_PROXIES` 填的是 web 容器实际所在网段。

## 回滚

```bash
# 退回直连：在 .env 里删掉 WEB_BIND_IP（默认就是 0.0.0.0），浏览器仍访问 :3000
docker compose up -d web
systemctl disable --now nginx
```

审计 IP 会重新变成网桥网关地址——这只是显示问题，不影响功能。

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
