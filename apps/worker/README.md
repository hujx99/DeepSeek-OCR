# DocFlow OCR Worker

The worker consumes RQ jobs from Redis and runs OCR through the configured provider.

Default provider:

```bash
OCR_PROVIDER=mock
```

DeepSeek-OCR-2 integration is intentionally isolated behind `app.providers.DeepSeekOCR2Provider`.
