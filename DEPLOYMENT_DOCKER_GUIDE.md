# Deployment & Docker Guide for OCR Fallback

## Docker Deployment

### Updated Dockerfile Requirements

The existing Dockerfile should already support the new OCR fallback feature. Ensure the following:

```dockerfile
ARG PYTHON_IMAGE=public.ecr.aws/docker/library/python:3.11-slim
FROM ${PYTHON_IMAGE}

WORKDIR /app

# Install system dependencies (if not already present)
RUN apt-get update && apt-get install -y \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app ./app

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Key Considerations

1. **New Dependencies**: 
   - `pymupdf>=1.25.1` - Already in requirements.txt, used for PDF-to-image conversion
   - `Pillow>=10.0.0` - New dependency added for image support

2. **Python Version**: Python 3.10+ is recommended (3.11+ for better performance)

3. **System Dependencies**: No additional system packages required beyond standard Python setup

### Build & Run Commands

```bash
# Build image with new dependencies
docker build -t resume-parser-ocr:latest .

# Run container with OCR configuration
docker run -p 8000:8000 \
  -e OCR_FALLBACK_ENABLED=true \
  -e OCR_MIN_TEXT_LENGTH=300 \
  -e OCR_MODEL=gpt-4.1-mini \
  -e OCR_MAX_PAGES=5 \
  -e OCR_DPI=200 \
  -e OPENAI_API_KEY=sk-... \
  -e MONGO_URI=mongodb://mongo:27017 \
  -e MONGO_EDITED_COLLECTION=edited_resumes \
  resume-parser-ocr:latest

# Or use docker-compose (see below)
```

### Docker Compose Example

Create or update `docker-compose.yml`:

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      APP_NAME: Resume Parser Service
      MAX_FILE_SIZE_MB: 5
      CORS_ORIGINS: "http://localhost:4200,http://127.0.0.1:4200,http://localhost:4300,http://127.0.0.1:4300"
      
      # LLM Configuration
      LLM_PROVIDER: openai
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      OPENAI_MODEL: gpt-4.1-mini
      
      # MongoDB Configuration
      MONGO_URI: mongodb://mongo:27017
      MONGO_DATABASE: resume_parser
      MONGO_COLLECTION: parsed_resumes
      MONGO_EDITED_COLLECTION: edited_resumes
      
      # OCR Fallback Configuration
      OCR_FALLBACK_ENABLED: "true"
      OCR_MIN_TEXT_LENGTH: "300"
      OCR_MODEL: "gpt-4.1-mini"
      OCR_MAX_PAGES: "5"
      OCR_DPI: "200"
    
    depends_on:
      - mongo
    
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  mongo:
    image: mongo:latest
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  mongo_data:
```

### Deploy with Docker Compose

```bash
# Set required environment variables
export OPENAI_API_KEY="sk-..."

# Start services
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down

# Clean up (including volumes)
docker-compose down -v
```

### Environment Variable Best Practices

1. **Use .env file (local development)**:
   ```bash
   # Create .env.docker
   LLM_PROVIDER=openai
   OPENAI_API_KEY=sk-...
   MONGO_URI=mongodb://mongo:27017
   OCR_FALLBACK_ENABLED=true
   
   # Load with docker-compose
   docker-compose --env-file .env.docker up
   ```

2. **Use Docker secrets (production)**:
   ```yaml
   services:
     api:
       secrets:
         - openai_api_key
   
   secrets:
     openai_api_key:
       file: ./secrets/openai_api_key.txt
   ```

3. **Use environment variables (CI/CD pipeline)**:
   ```bash
   docker run -e OPENAI_API_KEY="$OPENAI_API_KEY" ...
   ```

## Kubernetes Deployment

### Example Deployment Manifest

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: resume-parser
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: resume-parser
  template:
    metadata:
      labels:
        app: resume-parser
    spec:
      containers:
      - name: api
        image: resume-parser-ocr:latest
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
        env:
        - name: OCR_FALLBACK_ENABLED
          value: "true"
        - name: OCR_MIN_TEXT_LENGTH
          value: "300"
        - name: OCR_MAX_PAGES
          value: "5"
        - name: OCR_DPI
          value: "200"
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: openai-secret
              key: api-key
        - name: MONGO_URI
          valueFrom:
            secretKeyRef:
              name: mongo-secret
              key: uri
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1024Mi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: resume-parser-service
spec:
  selector:
    app: resume-parser
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

### Deploy to Kubernetes

```bash
# Create secret for API keys
kubectl create secret generic openai-secret --from-literal=api-key="sk-..."
kubectl create secret generic mongo-secret --from-literal=uri="mongodb://..."

# Deploy application
kubectl apply -f deployment.yaml

# Check deployment status
kubectl get deployments
kubectl get pods
kubectl logs deployment/resume-parser

# Scale deployment
kubectl scale deployment resume-parser --replicas=3

# Update image
kubectl set image deployment/resume-parser api=resume-parser-ocr:v2 --record
```

## Performance Tuning for OCR

### Memory & CPU Optimization

The OCR fallback service requires additional resources:

- **PDF-to-Image Conversion**: ~50-100MB per PDF (depending on page count and DPI)
- **OpenAI API Calls**: Network I/O, minimal CPU/memory
- **Text Processing**: Minimal overhead

### Recommended Resource Allocation

| Scenario | Memory | CPU | Notes |
|----------|--------|-----|-------|
| Low OCR usage (<10% scanned) | 512Mi | 500m | Standard configuration |
| Medium OCR usage (10-30% scanned) | 1Gi | 1000m | Default recommended |
| High OCR usage (30%+ scanned) | 2Gi | 2000m | Increase container limits |

### Optimization Tips

1. **Reduce OCR_DPI** (200 → 150):
   ```bash
   # Less memory per PDF, faster processing
   OCR_DPI=150
   ```

2. **Limit OCR_MAX_PAGES** (5 → 3):
   ```bash
   # Reduce API calls and memory usage
   OCR_MAX_PAGES=3
   ```

3. **Increase OCR_MIN_TEXT_LENGTH** (300 → 500):
   ```bash
   # Fewer OCR fallbacks triggered
   OCR_MIN_TEXT_LENGTH=500
   ```

4. **Enable request queuing**:
   ```python
   # In routes_resume.py, add request limiter
   from slowapi import Limiter
   from slowapi.util import get_remote_address
   
   limiter = Limiter(key_func=get_remote_address)
   app.state.limiter = limiter
   ```

## Monitoring & Observability

### Health Check Endpoint

```bash
# Health check for load balancers
curl http://localhost:8000/health
# Response: {"status": "ok", "service": "Resume Parser Service"}
```

### Logging Configuration

The application logs include OCR fallback information:

```bash
# View logs with OCR info
docker-compose logs api | grep -E "extraction|OCR"

# Output examples:
# INFO - Normal text extraction completed: 5432 characters
# INFO - Normal extraction produced sufficient text (5432 chars)
# INFO - OCR extraction completed: 3900 total characters from 2 pages
# INFO - OCR fallback succeeded: 3900 characters extracted
```

### Metrics to Monitor

1. **Extraction method distribution**:
   - % of resumes using normal extraction
   - % of resumes using OCR fallback

2. **Processing times**:
   - Average time for normal extraction
   - Average time for OCR fallback

3. **Error rates**:
   - PDF conversion failures
   - OpenAI API failures
   - Empty extraction results

4. **Cost tracking**:
   - Estimated cost per OCR request
   - Total OCR API costs per day/month

### Example Monitoring Setup (Prometheus)

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'resume-parser'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

## Troubleshooting Deployment

### OCR not working in Docker

1. **Check API key is set**:
   ```bash
   docker exec <container-id> env | grep OPENAI_API_KEY
   ```

2. **Check network connectivity**:
   ```bash
   docker exec <container-id> curl -I https://api.openai.com/v1/models
   ```

3. **Check logs for errors**:
   ```bash
   docker logs <container-id> | grep -i "ocr\|error"
   ```

### High memory usage

1. **Reduce OCR_DPI**:
   ```bash
   docker exec <container-id> env | grep OCR_DPI
   # Update docker-compose.yml and restart
   ```

2. **Limit PDF pages**:
   ```bash
   # Set OCR_MAX_PAGES to smaller value
   ```

3. **Monitor container memory**:
   ```bash
   docker stats <container-id>
   ```

## Scaling Considerations

### For High Volume

1. **Use message queue** (e.g., Redis, RabbitMQ):
   - Queue PDF uploads
   - Process asynchronously
   - Reduce memory pressure

2. **Batch processing**:
   - Group OCR requests
   - Reduce API overhead

3. **Caching**:
   - Cache OCR results
   - Avoid re-processing identical files

### Example Queue Integration

```python
# With Redis queue
from rq import Queue
from redis import Redis

redis_conn = Redis()
q = Queue(connection=redis_conn)

# Queue OCR job
job = q.enqueue(process_resume_ocr, pdf_content)
```

## Maintenance

### Update Dependencies

```bash
# Check for updates
pip list --outdated

# Update requirements.txt
pip install --upgrade pymupdf pillow httpx

# Rebuild Docker image
docker-compose build --no-cache

# Restart container
docker-compose restart api
```

### Backup & Recovery

```bash
# Backup MongoDB data
docker-compose exec mongo mongodump --archive > backup.archive

# Restore from backup
docker-compose exec -T mongo mongorestore --archive < backup.archive
```

## Cost Optimization

### For Scanned Resumes

- **OpenAI gpt-4-vision**: ~$0.01-0.03 per image
- **Average resume**: 2-5 pages = $0.02-0.15 per resume
- **Alternative options**:
  - AWS Textract: ~$0.01 per page ($100/month for 10k images)
  - Google Vision: ~$0.0015 per image (~$0.01 per resume)

### Cost Reduction Strategies

1. **Lower DPI**: 200 → 100 (faster, cheaper, less API usage)
2. **Limit pages**: 5 → 2 pages maximum
3. **Batch process**: Off-peak hours, bulk discount rates
4. **Caching**: Avoid duplicate OCR for identical files
