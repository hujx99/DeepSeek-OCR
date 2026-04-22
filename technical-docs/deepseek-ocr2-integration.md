# DeepSeek OCR2 集成技术说明

## 1. 背景

本文档记录了 `2026-04-22` 完成的 DeepSeek OCR2 集成工作，用于说明本地 DocFlow 项目如何接入运行在 4090 服务器上的远程 OCR 服务，以及为支持 PDF、预览和部署稳定性所做的调整。

本次工作的目标包括：

- 将本地项目从 mock OCR provider 切换为真实的 DeepSeek OCR2 HTTP 集成
- 通过 `.env` 和 `docker-compose.yml` 完成可配置化接入
- 打通 PDF 识别链路
- 优化前端 Docker 构建稳定性
- 记录 4090 远程 OCR 服务端为支持 PDF 所做的改造

## 2. 本地仓库改动

### 2.1 OCR Provider 接入

本地 API Provider 文件 [deepseek_ocr2.py](<C:/Users/workpc/Documents/github/DeepSeek-OCR/apps/api/app/providers/deepseek_ocr2.py:1>) 已从占位实现改为真实 HTTP 客户端。

当前行为如下：

- 从环境变量读取：
  - `DEEPSEEK_OCR2_ENDPOINT`
  - `DEEPSEEK_OCR2_API_KEY`
- 通过 `multipart/form-data` 发起 OCR 请求
- 会发送以下表单字段：
  - `file`
  - `page_no`
  - `page`
  - `page_number`
  - `mode`
  - `template_type`
- 配置了 API Key 时，会带上以下鉴权头：
  - `Authorization: Bearer <key>`
  - `X-API-Key`
  - `api-key`
- 对返回格式做了宽松兼容，支持：
  - 直接返回 `text` 或 `markdown` 的 JSON
  - 含有 `pages`、`results`、`predictions` 等嵌套结构的 JSON
  - 纯文本响应

### 2.2 本地 Provider 的 PDF 处理

在远程 4090 OCR 服务升级前，远程 `/ocr` 接口只能接收图片，不能直接接收 PDF。因此本地 Provider 一度承担了“PDF 单页转图片”的工作。

当前本地 Provider 的兼容逻辑如下：

- 如果上传文件不是 PDF，则直接上传原文件
- 如果上传文件是 PDF，则使用 `PyMuPDF` 渲染指定页为 PNG，再发送到远程 OCR 服务

对应依赖已加入 [requirements.txt](<C:/Users/workpc/Documents/github/DeepSeek-OCR/apps/api/requirements.txt:1>)。

需要注意：

- 远程 4090 服务现在已经支持直接上传 PDF
- 但本地 Provider 仍保留了“本地 PDF 转图片”逻辑，作为兼容和兜底方案
- 后续可以进一步清理，把 PDF 直接透传给远程服务

### 2.3 环境变量和 Compose 配置

[docker-compose.yml](<C:/Users/workpc/Documents/github/DeepSeek-OCR/docker-compose.yml:1>) 已更新，使 `api` 和 `worker` 都能接收到以下变量：

```text
OCR_PROVIDER
DEEPSEEK_OCR2_ENDPOINT
DEEPSEEK_OCR2_API_KEY
```

[.env.example](<C:/Users/workpc/Documents/github/DeepSeek-OCR/.env.example:1>) 也已补充 DeepSeek OCR2 的示例配置：

```text
OCR_PROVIDER=mock
DEEPSEEK_OCR2_ENDPOINT=http://your-ocr-service/ocr
DEEPSEEK_OCR2_API_KEY=
```

本地实际使用的 `.env` 已被 `.gitignore` 忽略，不会被正常 `git add` 带进仓库。

### 2.4 API 层的文件预览改动

[routes.py](<C:/Users/workpc/Documents/github/DeepSeek-OCR/apps/api/app/api/routes.py:1>) 为结果页预览做了两处调整：

- `/api/files/{file_id}/download?inline=1`
  - 支持用 `Content-Disposition: inline` 返回文件
- `/api/files/{file_id}/preview?page_no=N`
  - 新增 PDF 单页预览接口
  - 如果是 PDF，会将指定页渲染成 PNG 返回

这样做的原因是：浏览器即便访问下载接口，如果响应头是附件下载，也仍然会弹出下载，无法稳定内嵌显示 PDF。

### 2.5 前端结果页预览改动

[page.tsx](<C:/Users/workpc/Documents/github/DeepSeek-OCR/apps/web/app/results/[id]/page.tsx:1>) 已更新为：

- 非 PDF 文件使用 `download?inline=1`
- PDF 文件使用 `/api/files/{file_id}/preview?page_no=N`

这样结果页不再依赖浏览器对 PDF 的原生内嵌渲染，而是直接显示后端生成的页面图片。

当前状态说明：

- 后端预览接口已经实现
- 前端逻辑也已经切换
- 但由于此前 `web` 镜像多次构建被中断，前端预览行为仍建议在一次完整成功构建后重新回归验证

### 2.6 Web Docker 构建优化

前端镜像构建慢、经常失败的主要原因，是 `next build` 在镜像构建期间反复下载 SWC 二进制。

已完成的优化包括：

- [Dockerfile](<C:/Users/workpc/Documents/github/DeepSeek-OCR/apps/web/Dockerfile:1>)
  - 改为 `node:22-slim`
  - 使用 `package-lock.json`
  - 使用 `npm ci`
  - 在依赖层预装 `@next/swc-linux-x64-gnu@14.2.16`
- [docker-compose.yml](<C:/Users/workpc/Documents/github/DeepSeek-OCR/docker-compose.yml:1>)
  - `web` 的 build context 改成 `./apps/web`
- [.dockerignore](<C:/Users/workpc/Documents/github/DeepSeek-OCR/apps/web/.dockerignore:1>)
  - 排除 `.next`、`node_modules`、本地 env 等无关内容
- [apps/web/public/.gitkeep](<C:/Users/workpc/Documents/github/DeepSeek-OCR/apps/web/public/.gitkeep:1>)
  - 作为 `public` 目录占位，避免构建时缺目录

预期效果：

- 第一次完整构建仍需要下载依赖
- 之后如果缓存命中，构建会明显更稳定，且不必每次重新下载 SWC

## 3. 远程 4090 OCR 服务改动

### 3.1 服务定位

远程 OCR 服务已确认运行在：

```text
主机: 100.105.19.115
用户: root
工作目录: /matrix-data/services/deepseek-ocr-api
主程序: /matrix-data/services/deepseek-ocr-api/server.py
启动脚本: /matrix-data/services/deepseek-ocr-api/start.sh
端口: 8000
```

该服务当前不是通过 Docker 运行，而是以 Python 进程方式直接启动。

### 3.2 原始问题

远程 4090 服务最初的 `/ocr` 接口只支持图片：

- 会对上传内容直接执行 `PIL.Image.open(...).verify()`
- 不接受 `page_no`
- 直接上传 PDF 时会返回 `400 Invalid image`

这也是前面本地 Provider 必须先把 PDF 渲染成图片再上传的原因。

### 3.3 远程服务升级内容

远程文件 `/matrix-data/services/deepseek-ocr-api/server.py` 已更新，现在 `/ocr` 同时支持图片和 PDF。

升级后行为如下：

- 可接收表单字段：
  - `file`
  - `mode`
  - `page_no`
  - `template_type`
- 通过以下方式识别上传是否为 PDF：
  - 文件名后缀
  - `content-type`
  - `%PDF-` 文件头
- 如果是 PDF：
  - 用 `PyMuPDF` 渲染指定页
  - 将渲染出的 PNG 复用现有 OCR 推理逻辑
- 如果是图片：
  - 沿用原先的图片 OCR 流程

接口返回的 `metadata` 现在会额外带上：

- `page_no`
- `page_count`
- `input_type`
- `template_type`

健康检查接口也新增了：

```json
{
  "pdf_support": true
}
```

### 3.4 备份与重启

替换远程服务文件前，已先创建备份：

```text
/matrix-data/services/deepseek-ocr-api/server.py.bak-20260422-ocr-pdf
```

服务重启后日志输出到：

```text
/matrix-data/services/deepseek-ocr-api/server.log
```

## 4. 已完成验证

### 4.1 本地栈验证

本地已验证：

- `docker compose up -d` 能拉起主服务
- `http://localhost:8000/api/health` 返回 `{"status":"ok"}`
- DeepSeek OCR2 Provider 已被真实任务调用

### 4.2 远程 PDF 升级前的验证

在远程服务升级前，已经验证过：

- 图片 OCR 可以成功调用 `http://100.105.19.115:8000/ocr`
- PDF 也能在产品侧跑通

但当时 PDF 能跑通的原因是：

- 本地 Provider 先把 PDF 页转成图片
- 再将图片上传给远程 `/ocr`

不是因为远程 `/ocr` 原生支持 PDF。

### 4.3 远程 4090 原生 PDF 验证

远程服务更新后，已在 4090 机器上直接执行两类真实请求：

1. 图片请求
2. PDF 请求，带 `page_no=2`

实际结果如下：

- 两个请求都返回 HTTP `200`
- 图片请求返回了第一页测试图的 OCR 内容
- PDF 请求返回了第二页测试内容
- 返回 metadata 明确包含：

```json
{
  "page_no": 2,
  "page_count": 2,
  "input_type": "pdf"
}
```

健康检查同时返回：

```json
{
  "status": "ok",
  "model_loaded": true,
  "pdf_support": true
}
```

这说明远程 4090 服务已经具备原生 PDF 支持能力。

## 5. 当前架构状态

当前整体状态如下：

- 本地 DocFlow 已能调用远程 DeepSeek OCR2 服务
- 远程 4090 OCR 服务现已支持直接上传 PDF
- 本地 Provider 仍保留 PDF 转图片逻辑，作为兼容方案
- 结果页 PDF 预览已改成后端渲染图片预览路径
- Web Docker 构建已做提速和缓存优化，但建议再完成一次完整构建后做回归验证

## 6. 建议的后续工作

建议下一步继续做以下优化：

1. 清理 [deepseek_ocr2.py](<C:/Users/workpc/Documents/github/DeepSeek-OCR/apps/api/app/providers/deepseek_ocr2.py:1>)，让 PDF 直接透传给远程 4090 服务，不再本地先渲染
2. 在一次完整成功的 `web` 镜像重建后，重新验证结果页中的 PDF 预览是否完全正常
3. 将远程 OCR 服务接入 `systemd`、`supervisor` 或 Docker Compose，避免手动重启
4. 如果当前 API Key 曾暴露在聊天或不安全环境中，建议尽快轮换

## 7. 常用运维命令

### 7.1 本地项目

启动：

```bash
docker compose up --build
```

停止：

```bash
docker compose down
```

### 7.2 远程 4090 OCR 服务

连接：

```bash
ssh -i ~/.ssh/4090_key root@100.105.19.115
```

进入服务目录：

```bash
cd /matrix-data/services/deepseek-ocr-api
```

手动启动：

```bash
nohup bash -lc 'cd /matrix-data/services/deepseek-ocr-api && ./start.sh' > /matrix-data/services/deepseek-ocr-api/server.log 2>&1 < /dev/null &
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

查看日志：

```bash
tail -f /matrix-data/services/deepseek-ocr-api/server.log
```

## 8. 回滚方案

如果远程 OCR 服务需要回滚：

```bash
cp /matrix-data/services/deepseek-ocr-api/server.py.bak-20260422-ocr-pdf /matrix-data/services/deepseek-ocr-api/server.py
nohup bash -lc 'cd /matrix-data/services/deepseek-ocr-api && ./start.sh' > /matrix-data/services/deepseek-ocr-api/server.log 2>&1 < /dev/null &
```

如果本地项目需要临时切回 mock：

```text
OCR_PROVIDER=mock
```

## 9. 安全说明

- 不要提交 `.env`
- 不要提交远程 `.api_key`
- 更推荐把 OCR API Key 放到部署环境变量或密钥管理系统中，而不是明文文件
- 如果 Key 已被分享给非受信环境，建议及时轮换
