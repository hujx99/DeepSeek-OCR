# 跨平台 Docker 构建与部署指南

> 目标：**Mac / Windows 本地改代码 → Linux（openEuler / 欧拉）部署完整服务**
> 覆盖服务：`postgres`、`redis`、`api`、`worker`、`web`（后三者为自建镜像）

---

## 1. 架构与风险概览

| 服务 | 基础镜像 | 构建阶段风险点 |
|---|---|---|
| `api` | `python:3.12-slim` | pip 编译型依赖较少，跨平台风险低 |
| `worker` | `python:3.12-slim` | 同 api |
| `web` | `node:22-slim` | Next.js SWC 有架构原生二进制，是**主要跨平台坑**所在 |

三台典型开发/部署机的架构差异：

| 机器 | OS | CPU 架构 | Docker 默认构建平台 |
|---|---|---|---|
| Mac（M 芯片） | macOS | `arm64` | `linux/arm64` |
| Mac（Intel） / Win / 大部分云主机 | macOS / Windows / Linux | `x86_64` | `linux/amd64` |
| 欧拉（鲲鹏） | openEuler | `aarch64` (=arm64) | `linux/arm64` |
| 欧拉（Intel/AMD 服务器） | openEuler | `x86_64` | `linux/amd64` |

**结论**：不能假设 `linux/amd64`，也不能假设 `linux/arm64`。Dockerfile 必须架构无关。

---

## 2. macOS（Apple Silicon）已踩过的坑

### 2.1 `@next/swc-linux-x64-gnu` EBADPLATFORM

**错误现象**

```
npm error code EBADPLATFORM
npm error notsup Unsupported platform for @next/swc-linux-x64-gnu@14.2.16:
  wanted {"os":"linux","cpu":"x64",...}
  (current: {"os":"linux","cpu":"arm64",...})
```

**原因**

[apps/web/Dockerfile](../apps/web/Dockerfile) 里的 fallback 硬编码了 x64 的 SWC 包：

```dockerfile
|| npm install ... @next/swc-linux-x64-gnu@14.2.16
```

Apple Silicon 构建出来的 `linux` 容器是 `arm64`，npm 校验时拒绝安装 x64 原生二进制包。

**为什么需要这个 fallback**

Next.js 14 的 SWC 编译器是平台原生二进制（`@next/swc-<os>-<arch>-<libc>`），通过 npm 的 `optionalDependencies` 按平台挑选。`npm ci` 有时会漏装当前平台的可选依赖（特别是从别的平台生成的 `package-lock.json`），缺失时 `next build` 会失败。所以 Dockerfile 里加了一条"装不到就强装"的兜底。

**修复（已提交）**

按 `uname -m` 动态选择 SWC 包：

```dockerfile
RUN --mount=type=cache,target=/root/.npm \
    npm ci --include=optional --no-audit --no-fund \
    && case "$(uname -m)" in \
         x86_64) SWC_PKG=@next/swc-linux-x64-gnu ;; \
         aarch64|arm64) SWC_PKG=@next/swc-linux-arm64-gnu ;; \
         *) echo "unsupported arch: $(uname -m)" >&2; exit 1 ;; \
       esac \
    && (npm ls "$SWC_PKG" >/dev/null 2>&1 \
    || npm install --no-save --no-package-lock --no-audit --no-fund "${SWC_PKG}@14.2.16")
```

**验证**

```
docker compose up --build -d
docker compose ps           # 5 容器全部 Up
curl http://localhost:8000/api/health   # 200
curl http://localhost:3000              # 200
```

### 2.2 其它 Mac 常见但本项目目前未触发的坑（备查）

- **Docker Desktop 资源不足**：默认 2 CPU / 2 GB，`next build` 容易 OOM。Docker Desktop → Settings → Resources 调到 ≥ 4 CPU / 6 GB。
- **文件挂载性能**：`./storage:/app/storage` 在 macOS 下走 VirtioFS/osxfs，大量小文件 IO 慢。开发用够，生产不应采用这种 bind mount。
- **端口占用**：AirPlay Receiver 占 5000；本项目用 3000/8000/5432/6379，一般无冲突。

---

## 3. Windows（Docker Desktop + WSL2）预期问题与预防

Windows 开发场景下，**没在本机亲自复现，但以下是此项目 Dockerfile + compose 结构下高概率会遇到的问题**，按优先级给出预防方案。

### 3.1 换行符 CRLF 污染 shell 脚本（优先级最高）

**典型症状**

- `exec /bin/sh: exec format error`
- `: not found` / `\r: command not found`
- [apps/worker/Dockerfile](../apps/worker/Dockerfile) 的 `CMD ["sh", "-c", "rq worker ..."]` 在 Windows 仓库上构建后报 `\r` 相关错误

**原因**

Windows Git 默认 `core.autocrlf=true`，Checkout 时把 LF 转成 CRLF。`COPY` 进容器后 `sh` 执行脚本时无法识别 `\r`。

**预防（推荐进仓库）**

仓库根添加 `.gitattributes`：

```
* text=auto eol=lf
*.sh  text eol=lf
*.py  text eol=lf
Dockerfile text eol=lf
```

已有仓库执行一次规范化：

```bash
git add --renormalize .
git commit -m "chore: normalize line endings to LF"
```

Windows 开发者本地也设一下：

```bash
git config --global core.autocrlf input
```

### 3.2 文件名大小写

**症状**：Mac/Win 不区分大小写，Linux 区分。`import app.worker_tasks` 在 Windows 能跑，Linux 报 `ModuleNotFoundError`。

**预防**

- 统一小写、下划线命名（本项目已是如此）
- CI 里跑一次 `docker compose build`（GitHub Actions Linux runner 会暴露问题）

### 3.3 WSL2 下的挂载路径

docker-compose.yml 里用 `./storage:/app/storage`。如果代码放在 `C:\Users\xxx`，Docker Desktop 会走 `/mnt/c/...`，IO 慢且经常权限异常。

**预防**：把项目 clone 到 WSL 内部（`\\wsl$\Ubuntu\home\<user>\...` 或直接 `~/code/` 在 WSL 里）。

### 3.4 Hyper-V 端口保留

Windows 动态端口池会随机保留几段端口，Docker 绑定时会报 `Ports are not available`。

**排查**：

```cmd
netsh interface ipv4 show excludedportrange protocol=tcp
```

**修复**：若 3000/8000/5432/6379 落在保留段，用管理员重启 winnat：

```cmd
net stop winnat
net start winnat
```

### 3.5 `.env` 编码

Windows 记事本默认保存为 UTF-8-BOM，Python 读 `.env` 可能在第一行出现隐形字符。用 VSCode 或 Notepad++ 保存为 UTF-8（无 BOM）。

---

## 4. Linux openEuler 部署

欧拉是 RHEL 系，常见于鲲鹏（aarch64）或 x86_64 云主机。以下是部署到欧拉的注意事项。

### 4.1 Docker / Compose 安装

欧拉官方源的 `docker` 版本较旧，建议装 Docker CE（或使用欧拉自带的 `iSulad` + `docker-compose` 组合不推荐，兼容性较差）。

```bash
# 使用阿里云 Docker CE 源（欧拉可直接用 CentOS 8 源）
sudo dnf install -y dnf-plugins-core
sudo dnf config-manager --add-repo \
  https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
```

验证：`docker compose version`（注意是 `docker compose` 空格，不是老的 `docker-compose`）。

### 4.2 CPU 架构与镜像构建策略

开发机是 Mac(arm64) / Win(x86_64)，部署机可能是鲲鹏(arm64) 或 x86_64。**不要在开发机 build 完把镜像 tar 传到部署机**，除非架构一致。

三种工作流选一：

**方案 A（最简单，推荐）：在欧拉主机上直接 build**

```bash
git pull
cp .env.example .env   # 修改生产配置
docker compose up --build -d
```

优点：零额外基础设施。缺点：部署机需要编译资源（Node.js 构建 `web` 镜像需要内存 ≥ 2 GB）。

**方案 B：buildx 多架构镜像 + 私有 registry**

适合有多台部署机、架构混合（既有鲲鹏又有 x86）的情况：

```bash
docker buildx create --name cross --use
docker buildx build --platform linux/amd64,linux/arm64 \
  -t registry.internal/docflow-web:latest --push \
  -f apps/web/Dockerfile .
```

然后在欧拉上 `docker compose pull && docker compose up -d`（compose 里把 `build:` 换成 `image:`）。

**方案 C：CI 里构建**

GitHub Actions 用 `docker/setup-buildx-action` + `docker/build-push-action` 推多架构镜像，欧拉 `pull` 即可。未来工程化时采用。

### 4.3 SELinux

欧拉默认 `enforcing`，compose 里的 `./storage:/app/storage` bind mount 会被 SELinux 拦截，容器内报 `Permission denied`。

**修复（二选一）**

- 推荐：给 volume 加 label
  ```yaml
  volumes:
    - ./storage:/app/storage:Z
  ```
  `:Z` 会把目录重新标签为容器可读写。`:z` 是共享标签（多容器共用同一目录时用）。

- 备选（临时 / 非生产）：`sudo setenforce 0`，但重启后失效；改 `/etc/selinux/config` 设为 `permissive` 更稳。生产机不建议全关 SELinux。

### 4.4 防火墙

欧拉默认开 `firewalld`。只对外暴露 web 和 api，postgres/redis 绝不要开到公网：

```bash
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

生产上建议把 web/api 放到 nginx 后面，只开 80/443。

### 4.5 开机自启

compose 文件里给每个服务加 `restart: unless-stopped`，或创建 systemd unit 调 `docker compose up -d`。当前 [docker-compose.yml](../docker-compose.yml) 未设 restart policy，生产部署时需要补。

### 4.6 存储目录权限

`./storage` 在宿主机由当前用户所有（通常 uid=1000），容器内进程若以其它 uid 运行会写不进去。本项目 api/worker 容器以 root 跑（Dockerfile 未 `USER`），当前没问题；若未来换成非 root，需要在 Dockerfile 里 `RUN chown -R app:app /app/storage` 或在宿主机 `chown`。

### 4.7 时区

容器内默认 UTC，日志时间与运维人员时区不一致容易误判。api/worker Dockerfile 加：

```dockerfile
ENV TZ=Asia/Shanghai
RUN ln -sf /usr/share/zoneinfo/$TZ /etc/localtime
```

---

## 5. 国内网络环境（Linux 部署机无法访问 docker.io / pypi / npmjs）

这是国内服务器（尤其欧拉政企环境）最常见的一关。**Docker 构建对外网有三层依赖**，三层都要分别配国内源，缺一层都会在构建中卡死或超时：

| 层 | 谁在拉 | 默认地址 | 影响的镜像 |
|---|---|---|---|
| 基础镜像（`FROM python:3.12-slim` 等） | `dockerd` | `registry-1.docker.io` | 全部 |
| Python 依赖（`pip install`） | 容器内 pip | `pypi.org` | api / worker |
| Node 依赖（`npm ci`） | 容器内 npm | `registry.npmjs.org` | web |

### 5.1 Docker 基础镜像加速

编辑（无则新建）`/etc/docker/daemon.json`：

```json
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://dockerproxy.com",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ]
}
```

重启并验证：

```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
docker info | grep -A4 "Registry Mirrors"
docker pull alpine:latest    # 冒烟测试
```

> 国内镜像站可用性会波动，一旦某个挂了把它从列表删掉即可（Docker 会按顺序 fallback）。使用前先 `curl -I https://<host>/v2/` 测一下。

### 5.2 pip 国内源（api / worker 镜像）

推荐 **build-arg** 方式，开发机不受影响、部署机按需启用。

改 [apps/api/Dockerfile](../apps/api/Dockerfile) 和 [apps/worker/Dockerfile](../apps/worker/Dockerfile)：

```dockerfile
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=$PIP_INDEX_URL
COPY apps/api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
```

部署机 build：

```bash
docker compose build \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

备选源：`https://mirrors.aliyun.com/pypi/simple`、`https://mirrors.cloud.tencent.com/pypi/simple`。

### 5.3 npm 国内源（web 镜像）

改 [apps/web/Dockerfile](../apps/web/Dockerfile)，加在 `COPY package.json` 之前：

```dockerfile
ARG NPM_REGISTRY=https://registry.npmjs.org
RUN npm config set registry "$NPM_REGISTRY"
```

部署机 build 一次把三套 arg 都带上：

```bash
docker compose build \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  --build-arg NPM_REGISTRY=https://registry.npmmirror.com
```

可以在欧拉上写个 `deploy.sh` 固化这几个 arg，避免每次手敲。

### 5.4 完全离线部署（禁外网的内网机房）

如果欧拉主机**连国内镜像站也访问不了**（政企内网），只能在有网的跳板机构建，再 `save` / `load`：

```bash
# 跳板机（架构必须与目标欧拉一致！鲲鹏就得 arm64 构建）
docker compose build

docker save \
  deepseek-ocr-api:latest \
  deepseek-ocr-worker:latest \
  deepseek-ocr-web:latest \
  postgres:16-alpine redis:7-alpine \
  -o docflow-images.tar

# scp docflow-images.tar 到欧拉

# 欧拉侧
docker load -i docflow-images.tar
# 把 docker-compose.yml 里所有 build: 块换成 image: 对应 tag
docker compose up -d
```

关键点：

- **架构必须一致**。Mac(arm64) 构建的镜像不能直接跑在 x86 欧拉上。跳板机与目标架构不同时，用 buildx 指定目标架构：
  ```bash
  docker buildx build --platform linux/arm64 -t deepseek-ocr-web:latest --load -f apps/web/Dockerfile .
  ```
- 每次 `requirements.txt` / `package-lock.json` 改动都要重新 save/load。

### 5.5 上机前的连通性自检

在欧拉主机先跑一圈，定位问题层：

```bash
# 1. Docker 能拉基础镜像（验 §5.1）
docker pull alpine:latest

# 2. pip 能连国内源（验 §5.2）
docker run --rm python:3.12-slim sh -c \
  "pip install --dry-run -i https://pypi.tuna.tsinghua.edu.cn/simple requests"

# 3. npm 能连国内源（验 §5.3）
docker run --rm node:22-slim \
  npm ping --registry=https://registry.npmmirror.com
```

任何一项失败，先定位是 DNS、防火墙还是代理问题，再动 `docker compose up`。别硬跑浪费时间。

---

## 6. 统一推荐做法

### 5.1 仓库级（全员生效）

- 已有：[apps/web/Dockerfile](../apps/web/Dockerfile) 架构无关化（2.1 的修复）
- 待加：仓库根 `.gitattributes` 强制 LF（解决 Windows 换行符问题，3.1）
- 待加：`.dockerignore` 避免把 `.venv`、`node_modules`、`storage`、`*.db` 拷进构建上下文（构建变快，避免污染）

### 5.2 Dockerfile 通用规则

- 永远不写死 `linux-x64` / `amd64` / `arm64`
- `CMD`/`ENTRYPOINT` 用 exec 形式（数组），避免依赖 shell 脚本
- 若必须用 shell 脚本（如 [apps/worker/Dockerfile](../apps/worker/Dockerfile) 里的 `sh -c`），保证源文件 LF
- 生产镜像考虑加非 root `USER`

### 5.3 工作流建议

```
Mac / Win 改代码
    │
    ├── 本地 docker compose up --build    (自测)
    │
    ▼
git push
    │
    ▼
欧拉主机 git pull && docker compose up --build -d   (方案 A)
```

二期若要引入 CI/CD，切到方案 B：CI 构建多架构镜像 → 私有 registry → 欧拉 pull。

---

## 7. 故障排查速查表

| 症状 | 可能原因 | 定位命令 / 处置 |
|---|---|---|
| `EBADPLATFORM` / `Unsupported platform` | Dockerfile 架构硬编码 | `grep -r "linux-x64\|linux-arm64" apps/*/Dockerfile` |
| `exec format error` | CRLF 或架构不匹配 | `file some_script.sh`；`docker run --rm alpine uname -m` |
| `\r: command not found` | 脚本是 CRLF | 执行 `git add --renormalize .` |
| `Permission denied` 访问 `/app/storage` | SELinux | `ls -Z ./storage`，compose 加 `:Z` |
| `bind: address already in use` | 端口被占 | macOS `lsof -i :3000`；Win `netsh interface ipv4 show excludedportrange` |
| `pg_isready` 健康检查超时 | 容器启动失败 | `docker compose logs postgres` |
| `web` OOM killed | Node 构建内存不够 | 增大 Docker 内存；或 `NODE_OPTIONS=--max_old_space_size=4096` |
| Linux 上 `ModuleNotFoundError`，Win/Mac 正常 | 文件名大小写 | `git ls-files | grep -i <name>` 对比实际 import |
| api 能起，worker 起不来 | `PYTHONPATH` 缺失 | 确认 [apps/worker/Dockerfile](../apps/worker/Dockerfile) 的 `ENV PYTHONPATH=/app/apps/api:/app/apps/worker` |
| `Get "https://registry-1.docker.io/v2/": ... i/o timeout` | Docker 没配镜像加速 | 按 §5.1 配 `/etc/docker/daemon.json` |
| `ReadTimeoutError: HTTPSConnectionPool(host='pypi.org'...)` | 构建时 pip 连不上 pypi | 按 §5.2 传 `--build-arg PIP_INDEX_URL=...` |
| `npm error ... ETIMEDOUT ... registry.npmjs.org` | 构建时 npm 连不上 | 按 §5.3 传 `--build-arg NPM_REGISTRY=...` |
| 连镜像加速站也超时 | 完全内网 | 走 §5.4 离线 save/load |

---

## 8. 后续动作清单

- [x] 修复 `web` Dockerfile 架构硬编码（§2.1）
- [ ] 添加仓库根 `.gitattributes` 强制 LF（§3.1 / §6.1）
- [ ] 补 `.dockerignore`（§6.1）
- [ ] 三个 Dockerfile 加 `PIP_INDEX_URL` / `NPM_REGISTRY` 的 `ARG`（§5.2 / §5.3）
- [ ] 欧拉部署前按 §5.5 做一次连通性自检
- [ ] compose 加 `restart: unless-stopped`（§4.5）
- [ ] 欧拉首次部署按 §4 + §5 逐项核对
- [ ] 若部署机是鲲鹏，先用方案 A（机上直接 build）跑通，再评估是否需要 CI 多架构
