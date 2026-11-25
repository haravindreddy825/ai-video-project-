# Start Celery GPU worker (Windows requires --pool=solo; concurrency=1 + CrossProcessGPULock)
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\..\backend"
.\.venv\Scripts\celery.exe -A app.workers.celery_app worker --loglevel=info --pool=solo -Q gpu,celery
