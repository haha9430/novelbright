# Docker Deployment

## Docker build run

1. docker build 
```bash
docker build -t upstage-gangwon-backend:latest .
```

2. docker run
```bash
 docker run -d \
  --name upstage-gangwon-backend \
  -p 8800:8800 \
  upstage-gangwon-backend:latest
```

3. 이미지 내부 확인하기 
```bash
docker run --rm -it upstage-gangwon-backend:latest sh  
```

## Docker-compose 

1. Copy environment variables:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your Upstage API key:
   ```bash
   UPSTAGE_API_KEY=your_actual_api_key
   ```

3. Build the backend image:
   ```bash
   cd ../../
   docker build -t upstage-gangwon-backend:lite .
   ```

4. Start services:
   ```bash
   docker-compose up -d
   ```

## Services

- **Backend**: http://localhost:8800
- **ChromaDB**: http://localhost:8000

## Commands

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```