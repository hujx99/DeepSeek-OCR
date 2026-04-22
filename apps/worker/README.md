# DocFlow OCR Worker

The worker consumes RQ jobs from Redis and runs OCR through the configured provider.

Default provider:

```bash
OCR_PROVIDER=mock
```

DeepSeek-OCR-2 integration lives behind `app.providers.DeepSeekOCR2Provider`.

To use a remote OCR service:

```bash
OCR_PROVIDER=deepseek_ocr2
DEEPSEEK_OCR2_ENDPOINT=http://your-ocr-service/ocr
DEEPSEEK_OCR2_API_KEY=...
```
