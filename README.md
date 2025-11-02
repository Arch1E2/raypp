# RayPP - Dockerized FastAPI Application

A production-ready FastAPI application with PostgreSQL, ChromaDB, and Redis integration, fully containerized with Docker Compose.

## Features

- **FastAPI** - Modern, fast web framework for building APIs
- **PostgreSQL** - Robust relational database
- **ChromaDB** - Vector database for embeddings and similarity search
- **Redis** - In-memory data store for caching
- **Docker Compose** - Easy deployment and orchestration

## Prerequisites

- Docker (version 20.10 or higher)
- Docker Compose (version 2.0 or higher)

## Quick Start

1. Clone the repository:
```bash
git clone <repository-url>
cd raypp
```

2. Create environment file (optional):
```bash
cp .env.example .env
# Edit .env with your configuration if needed
```

3. Start all services:
```bash
docker-compose up -d
```

4. Check service health:
```bash
# Check all containers are running
docker-compose ps

# Check application logs
docker-compose logs -f app
```

5. Access the application:
- API Documentation: http://localhost:8000/docs
- API Base URL: http://localhost:8000
- PostgreSQL: localhost:5432
- Redis: localhost:6379
- ChromaDB: localhost:8001

## API Endpoints

### Health Checks
- `GET /api/health` - Overall health check
- `GET /api/health/postgres` - PostgreSQL connection check
- `GET /api/health/redis` - Redis connection check
- `GET /api/health/chromadb` - ChromaDB connection check

### PostgreSQL Operations (Items)
- `POST /api/items` - Create a new item
- `GET /api/items` - Get all items (with pagination)
- `GET /api/items/{item_id}` - Get item by ID

### Redis Cache Operations
- `POST /api/cache/{key}` - Set a value in cache (with optional TTL)
- `GET /api/cache/{key}` - Get a value from cache

### ChromaDB Vector Operations
- `POST /api/vectors/add` - Add documents to a collection
- `POST /api/vectors/query` - Query documents from a collection

## Project Structure

```
raypp/
├── app/
│   ├── api/
│   │   └── routes.py          # API endpoints
│   ├── core/
│   │   └── config.py          # Configuration settings
│   ├── db/
│   │   ├── database.py        # PostgreSQL connection
│   │   ├── redis_client.py    # Redis client
│   │   └── chroma_client.py   # ChromaDB client
│   ├── models/
│   │   └── item.py            # Database models
│   └── main.py                # FastAPI application
├── docker-compose.yml         # Docker services configuration
├── Dockerfile                 # Application container image
├── requirements.txt           # Python dependencies
└── .env.example              # Environment variables template
```

## Configuration

Environment variables can be set in `.env` file:

```env
# PostgreSQL
POSTGRES_USER=raypp
POSTGRES_PASSWORD=raypp_password
POSTGRES_DB=raypp_db

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# ChromaDB
CHROMA_HOST=chromadb
CHROMA_PORT=8000

# Application
APP_HOST=0.0.0.0
APP_PORT=8000
```

## Development

### Running in development mode:
```bash
docker-compose up
```

The application will auto-reload on code changes thanks to volume mounting.

### Viewing logs:
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f app
docker-compose logs -f postgres
docker-compose logs -f redis
docker-compose logs -f chromadb
```

### Stopping services:
```bash
docker-compose down
```

### Stopping and removing volumes:
```bash
docker-compose down -v
```

## Testing the API

### Using curl:

```bash
# Health check
curl http://localhost:8000/api/health

# Create an item (PostgreSQL)
curl -X POST http://localhost:8000/api/items \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Item", "description": "A test item"}'

# Get all items
curl http://localhost:8000/api/items

# Set cache value (Redis)
curl -X POST "http://localhost:8000/api/cache/mykey?value=myvalue&ttl=60"

# Get cache value
curl http://localhost:8000/api/cache/mykey

# Add vectors (ChromaDB)
curl -X POST http://localhost:8000/api/vectors/add \
  -H "Content-Type: application/json" \
  -d '{"collection_name": "test", "documents": ["Hello world", "Goodbye world"], "ids": ["1", "2"]}'

# Query vectors
curl -X POST http://localhost:8000/api/vectors/query \
  -H "Content-Type: application/json" \
  -d '{"collection_name": "test", "query_texts": ["Hello"], "n_results": 2}'
```

### Using the interactive API documentation:
Navigate to http://localhost:8000/docs to explore and test all endpoints interactively.

## Troubleshooting

### Services not starting:
```bash
# Check logs for errors
docker-compose logs

# Restart services
docker-compose restart

# Rebuild containers
docker-compose up --build
```

### Database connection issues:
```bash
# Check PostgreSQL is ready
docker-compose exec postgres pg_isready -U raypp

# Connect to PostgreSQL
docker-compose exec postgres psql -U raypp -d raypp_db
```

### Redis connection issues:
```bash
# Check Redis is running
docker-compose exec redis redis-cli ping
```

### ChromaDB connection issues:
```bash
# Check ChromaDB health
curl http://localhost:8001/api/v1/heartbeat
```

## License

MIT