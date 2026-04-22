# DeepSeek-OCR-2 部署与 DocFlow 对接技术文档

> 作者:先生  
> 日期:2026-04-22  
> 版本:v1.0  
> 服务器:AMD EPYC 7K62 / 8×RTX 4090 / ~1TB RAM / NVMe 3.5TB

-----

## 目录

1. [环境概览](#1-环境概览)
1. [从零搭建 conda 环境](#2-从零搭建-conda-环境)
1. [安装 PyTorch 和项目依赖](#3-安装-pytorch-和项目依赖)
1. [下载模型权重](#4-下载模型权重)
1. [单卡推理验证](#5-单卡推理验证)
1. [FastAPI OCR 服务](#6-fastapi-ocr-服务)
1. [DocFlow 对接方案](#7-docflow-对接方案)
1. [服务常驻 (systemd)](#8-服务常驻-systemd)
1. [常见问题 & 踩坑记录](#9-常见问题--踩坑记录)
1. [后续扩展方向](#10-后续扩展方向)

-----

## 1. 环境概览

### 服务器信息

|项目   |配置                                       |
|-----|-----------------------------------------|
|CPU  |AMD EPYC 7K62                            |
|GPU  |8 × RTX 4090 (24GB 各)                    |
|RAM  |~1 TB                                    |
|系统盘  |`/` 142 GB SSD                           |
|数据盘  |`/matrix-data` 3.5 TB NVMe ← **模型/服务放这里**|
|OS   |Linux (CentOS/RHEL)                      |
|conda|Miniconda (路径 `/root/miniconda`)         |

### 软件版本栈(官方钉死,不要随意修改)

|组件          |版本               |说明                  |
|------------|-----------------|--------------------|
|Python      |3.12.9           |conda 环境            |
|PyTorch     |2.6.0+cu118      |cu118 专用 wheel      |
|torchvision |0.21.0+cu118     |                    |
|transformers|4.46.3           |版本钉死,不要升级           |
|tokenizers  |0.20.3           |版本钉死                |
|CUDA toolkit|11.8 (PyTorch 绑定)|系统 CUDA 是 12.4,推理不影响|
|flash-attn  |跳过               |CUDA 版本冲突,用 eager 替代|
|FastAPI     |0.136.0          |OCR API 服务框架        |
|uvicorn     |0.45.0           |ASGI 服务器            |


> **为什么不用 flash-attn?**  
> 系统 CUDA toolkit 是 12.4,而 PyTorch 绑定的是 cu118,编译 flash-attn 时版本冲突。  
> 替代方案:推理代码中使用 `_attn_implementation='eager'`,性能损失约 20-30%,单卡 4090 完全可接受。

-----

## 2. 从零搭建 conda 环境

```bash
# 接受 Anaconda 官方 channel 的服务条款(新版本必须)
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r

# 创建独立环境,Python 锁定 3.12
conda create -n deepseek-ocr2 python=3.12 -y
conda activate deepseek-ocr2

# 验证
python --version   # Python 3.12.x
pip --version      # pip xx.x from .../deepseek-ocr2/...
```

> **注意**:以下所有操作均需在 `conda activate deepseek-ocr2` 之后执行。

-----

## 3. 安装 PyTorch 和项目依赖

### 3.1 pip 换源(国内必做)

```bash
# 永久换阿里云源(最稳)
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
```

> ⚠️ PyTorch 本身**不走 pip 全局源**,要单独指定官方 whl 源(见下方)。

### 3.2 安装 PyTorch(cu118 版本)

```bash
pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 \
  --index-url https://download.pytorch.org/whl/cu118
```

下载量约 2.5 GB,国内速度 2-5 MB/s,耗时约 5-10 分钟。

### 3.3 验证 PyTorch + GPU

```bash
python -c "
import torch
print(torch.__version__)          # 期望: 2.6.0+cu118
print(torch.cuda.is_available())  # 期望: True
print(torch.cuda.device_count())  # 期望: 8
print(torch.cuda.get_device_name(0))  # 期望: NVIDIA GeForce RTX 4090
"
```

### 3.4 Clone 项目仓库

```bash
cd /root
git clone https://github.com/deepseek-ai/DeepSeek-OCR-2.git
cd DeepSeek-OCR-2
```

### 3.5 安装项目依赖

```bash
pip install -r requirements.txt
```

`requirements.txt` 内容:

```
transformers==4.46.3
tokenizers==0.20.3
PyMuPDF
img2pdf
einops
easydict
addict
Pillow
numpy
```

### 3.6 验证依赖

```bash
pip list | grep -E "transformers|tokenizers|PyMuPDF|einops|easydict|addict|img2pdf"
```

期望输出(7 行全部出现):

```
addict          2.4.0
easydict        1.13
einops          0.8.x
img2pdf         0.6.x
PyMuPDF         1.27.x
tokenizers      0.20.3
transformers    4.46.3
```

### 3.7 安装 FastAPI 服务依赖

```bash
pip install -i https://mirrors.aliyun.com/pypi/simple/ \
  fastapi uvicorn[standard] python-multipart
```

-----

## 4. 下载模型权重

### 4.1 设置国内镜像(必做)

```bash
export HF_ENDPOINT=https://hf-mirror.com
# 永久生效
echo 'export HF_ENDPOINT=https://hf-mirror.com' >> ~/.bashrc
```

### 4.2 建模型目录

```bash
mkdir -p /matrix-data/models
cd /matrix-data/models
```

### 4.3 用 tmux 挂起下载(避免 SSH 断连导致下载中断)

```bash
# 安装 tmux
yum install tmux -y

# 创建会话
tmux new -s download

# 在 tmux 内执行下载
conda activate deepseek-ocr2
cd /matrix-data/models
export HF_ENDPOINT=https://hf-mirror.com
hf download deepseek-ai/DeepSeek-OCR-2 --local-dir ./DeepSeek-OCR-2

# 下载进行中可以安全 detach:Ctrl+B 然后按 D
# 重新 attach 看进度:
tmux attach -t download
```

> **断点续传**:下载中断后重新跑同一条命令会自动续传(文件级别)。

### 4.4 监控下载进度

```bash
# 实时看下载大小(MB)
watch -n 2 "du -sm /matrix-data/models/DeepSeek-OCR-2/"
```

### 4.5 验证模型文件完整

```bash
ls -lh /matrix-data/models/DeepSeek-OCR-2/
du -sh /matrix-data/models/DeepSeek-OCR-2/
```

期望看到的关键文件:

```
-rw-r--r--  config.json                       ~2.6 KB
-rw-r--r--  model-00001-of-000001.safetensors  6.4 GB   ← 主权重
-rw-r--r--  model.safetensors.index.json       ~242 KB
-rw-r--r--  tokenizer.json                     ~9.6 MB
-rw-r--r--  tokenizer_config.json              ~163 KB
-rw-r--r--  modeling_deepseekocr2.py           (模型代码)
-rw-r--r--  deepencoderv2.py                   (编码器)
drwxr-xr-x  assets/                            (示例图片)
```

总大小约 **6.4 GB**。

-----

## 5. 单卡推理验证

### 5.1 创建测试脚本

```bash
cd /root/DeepSeek-OCR-2
mkdir -p output

cat > test_ocr.py << 'EOF'
import os
import sys
os.environ["CUDA_VISIBLE_DEVICES"] = "0"   # 只用第 0 块卡

import torch
import time
from transformers import AutoModel, AutoTokenizer

# 命令行用法:python test_ocr.py <图片路径>
image_file = sys.argv[1] if len(sys.argv) > 1 else "./assets/fig1.png"
model_path = "/matrix-data/models/DeepSeek-OCR-2"

print(f"Image: {image_file}")

t0 = time.time()
tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
model = AutoModel.from_pretrained(
    model_path,
    _attn_implementation="eager",   # 不用 flash-attn
    trust_remote_code=True,
    use_safetensors=True,
)
model = model.eval().cuda().to(torch.bfloat16)
print(f"Model loaded in {time.time()-t0:.1f}s | GPU: {torch.cuda.memory_allocated()/1024**3:.2f} GB")

prompt = "<image>\n<|grounding|>Convert the document to markdown."

t0 = time.time()
model.infer(
    tokenizer,
    prompt=prompt,
    image_file=image_file,
    output_path="./output",
    base_size=1024,
    image_size=768,
    crop_mode=True,
    save_results=True,
)
print(f"OCR done in {time.time()-t0:.1f}s")
print("Results in ./output/")
EOF
```

### 5.2 运行测试

```bash
python test_ocr.py ./assets/fig1.png
```

### 5.3 期望输出

```
Model loaded in 9.4s | GPU: 6.46 GB
OCR done in 1.2s
Results in ./output/
```

输出文件:

|文件                            |说明                        |
|------------------------------|--------------------------|
|`output/result.mmd`           |OCR 结果(markdown with math)|
|`output/result_with_boxes.jpg`|带 bounding box 可视化图       |
|`output/images/`              |切分的图块                     |

### 5.4 两种 prompt 模式

```python
# 模式 1:纯文字提取(快)
prompt = "<image>\nFree OCR."

# 模式 2:保留 layout 转 markdown(慢,效果好,适合文档/报告)
prompt = "<image>\n<|grounding|>Convert the document to markdown."
```

-----

## 6. FastAPI OCR 服务

将模型包装成 HTTP 服务,供 DocFlow 或任何客户端通过 API 调用。

### 6.1 服务特性

- 模型启动时一次性加载,常驻 GPU
- Bearer token 鉴权
- GPU 串行锁(防止多请求同时打 GPU 导致 OOM)
- 健康检查端点(DocFlow 可用于就绪探测)
- 支持 markdown / plain 两种 OCR 模式

### 6.2 目录结构

```
/matrix-data/services/deepseek-ocr-api/
├── server.py          # FastAPI 核心服务
├── start.sh           # 启动脚本
├── .api_key           # API 密钥(chmod 600)
└── deepseek-ocr.service  # systemd 服务文件(见第 8 节)
```

### 6.3 创建服务目录

```bash
mkdir -p /matrix-data/services/deepseek-ocr-api
cd /matrix-data/services/deepseek-ocr-api
```

### 6.4 server.py 完整代码

```python
"""
DeepSeek-OCR-2 HTTP Service
单卡常驻 + Bearer token 鉴权 + Tailscale 内网暴露
"""
import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import io
import time
import tempfile
import logging
import threading
import shutil
from pathlib import Path
from contextlib import asynccontextmanager

import torch
from PIL import Image
from fastapi import FastAPI, UploadFile, File, HTTPException, Header, Form
from transformers import AutoModel, AutoTokenizer
import uvicorn

# ---------- 配置 ----------
MODEL_PATH = os.getenv("MODEL_PATH", "/matrix-data/models/DeepSeek-OCR-2")
API_KEY    = os.getenv("API_KEY", "change-me-please")
HOST       = os.getenv("HOST", "0.0.0.0")
PORT       = int(os.getenv("PORT", "8000"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/tmp/deepseek_ocr_output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ocr-api")

state    = {"model": None, "tokenizer": None}
gpu_lock = threading.Lock()   # 单卡串行,防 OOM

# ---------- 启动时加载模型 ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(f"Loading model from {MODEL_PATH} ...")
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    model = AutoModel.from_pretrained(
        MODEL_PATH,
        _attn_implementation="eager",
        trust_remote_code=True,
        use_safetensors=True,
    ).eval().cuda().to(torch.bfloat16)
    state["tokenizer"] = tokenizer
    state["model"]     = model
    log.info(f"✅ Model loaded in {time.time()-t0:.1f}s | "
             f"GPU mem: {torch.cuda.memory_allocated()/1024**3:.2f} GB")
    yield
    log.info("Shutting down ...")
    state.clear()
    torch.cuda.empty_cache()

app = FastAPI(
    title="DeepSeek-OCR-2 API",
    description="Internal OCR service for DocFlow",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------- 鉴权 ----------
def check_auth(authorization: str | None):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing Bearer token")
    if authorization[7:].strip() != API_KEY:
        raise HTTPException(401, "Invalid API key")

# ---------- 健康检查 ----------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": state.get("model") is not None,
        "gpu_memory_gb": round(torch.cuda.memory_allocated() / 1024**3, 2),
    }

# ---------- OCR 接口 ----------
@app.post("/ocr")
async def ocr(
    file: UploadFile = File(...),
    mode: str = Form("markdown"),         # markdown | plain
    authorization: str | None = Header(default=None),
):
    check_auth(authorization)

    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty file")
    if len(raw) > 50 * 1024 * 1024:
        raise HTTPException(413, "File too large (>50MB)")

    try:
        Image.open(io.BytesIO(raw)).verify()
    except Exception as e:
        raise HTTPException(400, f"Invalid image: {e}")

    prompt = ("<image>\n<|grounding|>Convert the document to markdown."
              if mode == "markdown" else "<image>\nFree OCR.")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False,
                                     dir=OUTPUT_DIR) as f:
        f.write(raw)
        tmp_path = f.name
    job_output = Path(tempfile.mkdtemp(dir=OUTPUT_DIR))

    t0 = time.time()
    try:
        with gpu_lock:
            log.info(f"OCR start: {file.filename} ({len(raw)/1024:.1f} KB)")
            state["model"].infer(
                state["tokenizer"],
                prompt=prompt,
                image_file=tmp_path,
                output_path=str(job_output),
                base_size=1024,
                image_size=768,
                crop_mode=True,
                save_results=True,
            )
        elapsed = time.time() - t0

        result_file = job_output / "result.mmd"
        text = result_file.read_text(encoding="utf-8") if result_file.exists() else ""

        log.info(f"OCR done: {file.filename} in {elapsed:.2f}s | {len(text)} chars")

        return {
            "text": text,
            "metadata": {
                "filename": file.filename,
                "elapsed_seconds": round(elapsed, 2),
                "char_count": len(text),
                "mode": mode,
            },
        }
    except Exception as e:
        log.exception("OCR failed")
        raise HTTPException(500, f"OCR error: {e}")
    finally:
        try:
            os.unlink(tmp_path)
            shutil.rmtree(job_output, ignore_errors=True)
        except Exception:
            pass

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
```

### 6.5 生成 API Key

```bash
# 生成强随机密钥
API_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
echo "$API_KEY" > .api_key
chmod 600 .api_key
echo "Your API key: $API_KEY"
```

### 6.6 start.sh 启动脚本

```bash
cat > start.sh << EOF
#!/bin/bash
set -e

source /root/miniconda/etc/profile.d/conda.sh
conda activate deepseek-ocr2

export MODEL_PATH=/matrix-data/models/DeepSeek-OCR-2
export API_KEY="$(cat /matrix-data/services/deepseek-ocr-api/.api_key)"
export HOST=0.0.0.0
export PORT=8000
export CUDA_VISIBLE_DEVICES=0

cd /matrix-data/services/deepseek-ocr-api
python server.py
EOF

chmod +x start.sh
```

> ⚠️ 这里用的是 `<< EOF`(没有单引号),目的是让 `$(cat ...)` 在写入时被 shell 替换成实际密钥值。

### 6.7 用 tmux 启动测试

```bash
tmux new -s ocr-api
./start.sh
# 看到 "Uvicorn running on http://0.0.0.0:8000" = 成功

# detach(保持后台运行)
# Ctrl+B 然后 D
```

### 6.8 接口测试

```bash
API_KEY=$(cat /matrix-data/services/deepseek-ocr-api/.api_key)

# 健康检查(无需 token)
curl http://localhost:8000/health
# 期望: {"status":"ok","model_loaded":true,"gpu_memory_gb":6.46}

# OCR 推理
curl -X POST http://localhost:8000/ocr \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@/root/DeepSeek-OCR-2/assets/fig1.png" \
  -F "mode=markdown"
# 期望: {"text":"...","metadata":{"elapsed_seconds":1.18,...}}

# 鉴权测试(应返回 401)
curl -X POST http://localhost:8000/ocr \
  -F "file=@/root/DeepSeek-OCR-2/assets/fig1.png"
```

### 6.9 自动文档

服务启动后访问(Tailscale 内网可达):

```
http://<服务器 Tailscale IP>:8000/docs
```

FastAPI 自动生成交互式文档,可直接在浏览器测试各接口。

-----

## 7. DocFlow 对接方案

DocFlow 通过 `OCR_PROVIDER` 环境变量切换 OCR 提供者,内置 `mock` 和 `deepseek_ocr2` 两种。

### 7.1 整体架构

```
[DocFlow Web UI]
      │ 上传文件
      ▼
[DocFlow API (FastAPI)]
      │ 创建 OCR Job,投入队列
      ▼
[Redis Queue]
      │
      ▼
[DocFlow Worker (RQ)]
      │ 调用 OCRProvider
      ▼
[DeepSeek-OCR-2 Service]  ← 本文档搭建的服务
      │ HTTP POST /ocr
      ▼
[GPU 推理结果]
      │
      ▼
[存回数据库 / 供用户审阅导出]
```

### 7.2 环境变量配置

在 DocFlow 的 `.env` 中设置:

```bash
# 切换到 DeepSeek-OCR-2 provider
OCR_PROVIDER=deepseek_ocr2

# OCR 服务地址(Tailscale 内网 IP + 端口)
DEEPSEEK_OCR2_ENDPOINT=http://<服务器 Tailscale IP>:8000

# 对应 OCR 服务里生成的 API key
DEEPSEEK_OCR2_API_KEY=<你的 API key>
```

查看 Tailscale IP:

```bash
# 在 GPU 服务器上运行
tailscale ip -4
# 例如输出: 100.64.0.5
```

### 7.3 DeepSeek OCR Provider 实现

在 DocFlow 的 `apps/worker/providers/` 或 `apps/api/app/providers/` 下新建 `deepseek_ocr2.py`:

```python
"""
DeepSeek-OCR-2 Provider for DocFlow
调用独立部署的 OCR HTTP Service
"""
import os
import httpx
from pathlib import Path


class DeepseekOcr2Provider:
    """
    通过 HTTP 调用 DeepSeek-OCR-2 推理服务。
    接口契约与 MockProvider 保持一致。
    """

    def __init__(self):
        self.endpoint = os.getenv(
            "DEEPSEEK_OCR2_ENDPOINT", "http://localhost:8000"
        ).rstrip("/")
        self.api_key = os.getenv("DEEPSEEK_OCR2_API_KEY", "")
        self.timeout = float(os.getenv("DEEPSEEK_OCR2_TIMEOUT", "120"))

    # ------ 同步版本(RQ worker 场景) ------
    def process_image(self, file_path: str, mode: str = "markdown") -> dict:
        """
        输入:本地图片路径
        输出:{"text": "...", "metadata": {...}}
        """
        with open(file_path, "rb") as f:
            filename = Path(file_path).name
            files = {"file": (filename, f, "image/png")}
            data  = {"mode": mode}
            headers = {"Authorization": f"Bearer {self.api_key}"}

            resp = httpx.post(
                f"{self.endpoint}/ocr",
                files=files,
                data=data,
                headers=headers,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()

    # ------ 异步版本(FastAPI 场景) ------
    async def process_image_async(
        self, file_path: str, mode: str = "markdown"
    ) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            with open(file_path, "rb") as f:
                filename = Path(file_path).name
                files = {"file": (filename, f, "image/png")}
                data  = {"mode": mode}
                headers = {"Authorization": f"Bearer {self.api_key}"}

                resp = await client.post(
                    f"{self.endpoint}/ocr",
                    files=files,
                    data=data,
                    headers=headers,
                )
                resp.raise_for_status()
                return resp.json()

    def health_check(self) -> bool:
        """检查 OCR 服务是否可达(DocFlow 可用于就绪检测)"""
        try:
            resp = httpx.get(f"{self.endpoint}/health", timeout=5)
            return resp.status_code == 200 and resp.json().get("model_loaded")
        except Exception:
            return False
```

### 7.4 在 Provider 工厂中注册

找到 DocFlow 的 provider 工厂文件(通常是 `providers/__init__.py` 或 `factory.py`),添加:

```python
import os

def get_ocr_provider():
    provider_name = os.getenv("OCR_PROVIDER", "mock")

    if provider_name == "mock":
        from .mock import MockProvider
        return MockProvider()

    elif provider_name == "deepseek_ocr2":
        from .deepseek_ocr2 import DeepseekOcr2Provider
        return DeepseekOcr2Provider()

    else:
        raise ValueError(f"Unknown OCR provider: {provider_name}")
```

### 7.5 Worker 中调用示例

```python
# apps/worker/tasks.py (示例)
from providers import get_ocr_provider

def run_ocr_job(job_id: str, file_path: str):
    provider = get_ocr_provider()
    
    try:
        result = provider.process_image(file_path, mode="markdown")
        text = result["text"]
        # 存回数据库 ...
        update_job_result(job_id, text, status="completed")
    except Exception as e:
        update_job_result(job_id, "", status="failed", error=str(e))
```

### 7.6 安装客户端依赖

在 DocFlow 的 `apps/worker/requirements.txt` 中添加:

```
httpx>=0.23.0
```

```bash
pip install httpx
```

### 7.7 端到端验证

```bash
# 1. 确认 OCR 服务健康
curl http://<Tailscale IP>:8000/health

# 2. 改 DocFlow .env
OCR_PROVIDER=deepseek_ocr2
DEEPSEEK_OCR2_ENDPOINT=http://<Tailscale IP>:8000
DEEPSEEK_OCR2_API_KEY=<你的 key>

# 3. 重启 DocFlow worker
# (具体命令取决于你的 DocFlow 启动方式)
docker compose restart worker
# 或
rq worker --url redis://localhost:6379/0 ocr

# 4. 在 DocFlow UI 上传一张图,观察 Job 状态变为 completed
```

-----

## 8. 服务常驻 (systemd)

让 OCR 服务**开机自启 + 崩溃自动重启**。

### 8.1 创建 systemd 服务文件

```bash
cat > /etc/systemd/system/deepseek-ocr.service << 'EOF'
[Unit]
Description=DeepSeek-OCR-2 API Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/matrix-data/services/deepseek-ocr-api
ExecStart=/matrix-data/services/deepseek-ocr-api/start.sh
Restart=on-failure
RestartSec=10
StandardOutput=append:/var/log/deepseek-ocr.log
StandardError=append:/var/log/deepseek-ocr.log

[Install]
WantedBy=multi-user.target
EOF
```

### 8.2 启用并启动

```bash
# 先停掉 tmux 里的服务(避免端口冲突)
# tmux attach -t ocr-api  →  Ctrl+C  →  exit

systemctl daemon-reload
systemctl enable deepseek-ocr    # 开机自启
systemctl start deepseek-ocr

# 检查状态
systemctl status deepseek-ocr

# 实时查看日志
tail -f /var/log/deepseek-ocr.log
```

### 8.3 常用管理命令

```bash
systemctl start   deepseek-ocr   # 启动
systemctl stop    deepseek-ocr   # 停止
systemctl restart deepseek-ocr   # 重启
systemctl status  deepseek-ocr   # 状态
journalctl -u deepseek-ocr -f    # systemd 日志流
```

-----

## 9. 常见问题 & 踩坑记录

### 9.1 PyTorch CUDA 版本

**问题**:系统 CUDA 是 12.4,但 PyTorch 绑定 cu118。

**正确理解**:两者不冲突。PyTorch 的 `cu118` 版本自带 CUDA 11.8 runtime libraries,**不依赖系统 CUDA toolkit**。只需系统 NVIDIA driver 版本 ≥ 450 即可,driver 版本可通过 `nvidia-smi` 查看。

### 9.2 flash-attn 无法编译

**问题**:

```
RuntimeError: The detected CUDA version (12.4) mismatches the version that was
used to compile PyTorch (11.8).
```

**解决方案**:代码中将 `_attn_implementation='flash_attention_2'` 改为 `_attn_implementation='eager'`。性能损失约 20-30%,但 4090 性能完全够用。

### 9.3 vLLM wheel 找不到

**问题**:

```
ERROR: No such file or directory: 'vllm-0.8.5+cu118-....whl'
```

**原因**:官方 README 要求手动下载 wheel 文件,文件不在当前目录就报错。

**解决方案**:单卡 transformers 路径完全不需要 vLLM,跳过。

### 9.4 pip 下载极慢 / 超时

**解决方案**:

```bash
# 方法 1:本次临时用阿里源
pip install -i https://mirrors.aliyun.com/pypi/simple/ <包名>

# 方法 2:永久设置
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
```

> ⚠️ PyTorch 不走 pip 全局源,必须用 `--index-url https://download.pytorch.org/whl/cu118`。

### 9.5 HuggingFace 模型下载超时

**解决方案**:

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

写入 `~/.bashrc` 永久生效。hf-mirror.com 是国内最稳定的 HF 镜像。

### 9.6 SSH 断开导致下载中断

**解决方案**:所有长耗时任务通过 tmux 运行。

```bash
tmux new -s <会话名>   # 新建
# ... 运行任务 ...
# Ctrl+B D             # detach(任务继续后台运行)
tmux attach -t <会话名>  # 重新连接
```

### 9.7 conda ToS 警告

Anaconda 2024 年起要求用官方 channel 前接受服务条款:

```bash
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
```

### 9.8 OCR 结果为 `![](images/0.jpg)` 而非文字

**原因**:测试图是纯示意图/图表,没有可提取的文字。模型正确识别了这是”图”,不是”文字”。

**解决方案**:换文字密集的文档图(扫描件、截图等)测试。

-----

## 10. 后续扩展方向

|方向                |说明                                            |优先级|
|------------------|----------------------------------------------|---|
|**PDF 多页支持**      |服务端用 PyMuPDF 自动拆页,每页单独 OCR 后拼接                |高  |
|**systemd 常驻**    |开机自启 + 崩溃重启(见第 8 节)                           |高  |
|**Tailscale 限定监听**|`HOST=$(tailscale ip -4)` 只监听 Tailscale 接口,更安全|中  |
|**多卡并行**          |8 个进程各用一块 GPU,Nginx 负载均衡,吞吐 8 倍               |中  |
|**Prometheus 监控** |暴露 QPS、延迟、GPU 利用率指标                           |中  |
|**vLLM 引擎替换**     |用 vLLM 替换 transformers,吞吐提升 5-10 倍            |低  |
|**结果缓存**          |对相同文件 hash 做缓存,避免重复推理                         |低  |

-----

## 附录:关键路径速查

```
模型权重:   /matrix-data/models/DeepSeek-OCR-2/
项目代码:   /root/DeepSeek-OCR-2/
OCR 服务:   /matrix-data/services/deepseek-ocr-api/
  ├── server.py
  ├── start.sh
  └── .api_key          (chmod 600)
conda 环境: deepseek-ocr2
服务端口:   8000
API 文档:   http://<Tailscale IP>:8000/docs
服务日志:   /var/log/deepseek-ocr.log
systemd:    systemctl status deepseek-ocr
```

```
API_KEY 查看:   cat /matrix-data/services/deepseek-ocr-api/.api_key
健康检查:       curl http://localhost:8000/health
快速 OCR 测试:  curl -X POST http://localhost:8000/ocr \
                  -H "Authorization: Bearer $(cat .api_key)" \
                  -F "file=@your_image.png" -F "mode=markdown"
```