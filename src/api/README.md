# FastAPI Backend for Traffic Prediction System

## Overview

This FastAPI backend provides a comprehensive REST API and WebSocket streaming service for the traffic prediction system. It serves as the central API layer connecting the frontend, database, Kafka streaming, and machine learning prediction services.

## Features

### Core API Endpoints
- **Traffic Data API**: Current, historical, and sensor-specific traffic data
- **Prediction API**: Latest predictions, accuracy metrics, and on-demand generation
- **Analytics API**: Congestion analysis, pattern recognition, and trend analysis
- **System API**: Sensor management, incident tracking, and health monitoring

### Real-time Capabilities
- **WebSocket Streaming**: Real-time traffic data, predictions, and alerts
- **Kafka Integration**: Stream processing for traffic events and predictions
- **Live Analytics**: Real-time congestion and pattern updates

### Enterprise Features
- **Comprehensive Logging**: Structured JSON logging with request tracing
- **Health Monitoring**: Database, Kafka, and system health checks
- **Error Handling**: Robust error responses with detailed messaging
- **Performance Optimization**: Connection pooling, caching, and async operations

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │   FastAPI        │    │   PostgreSQL    │
│   (Next.js)     │◄──►│   Backend        │◄──►│   Database      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐    ┌─────────────────┐
                       │   Kafka          │    │   ML Prediction │
                       │   Streaming      │◄──►│   Service       │
                       └──────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   HDFS Storage   │
                       │   & Model Store  │
                       └──────────────────┘
```

## Quick Start

### Prerequisites
- Python 3.9+
- PostgreSQL 13+
- Apache Kafka 2.8+
- Redis (optional, for caching)

### Installation

1. **Install Dependencies**
   ```bash
   pip install -r requirements-fastapi.txt
   ```

2. **Environment Configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Database Setup**
   ```bash
   # Ensure PostgreSQL is running
   # Database migrations are handled automatically on startup
   ```

4. **Start the Server**
   
   **Development Mode:**
   ```bash
   python src/api/deploy.py --config development
   ```
   
   **Production Mode:**
   ```bash
   python src/api/deploy.py --config production --install-deps --health-check
   ```

5. **Access the API**
   - API Documentation: http://localhost:8000/docs
   - Alternative Docs: http://localhost:8000/redoc
   - Health Check: http://localhost:8000/health

## API Documentation

### Traffic Data Endpoints

#### GET /api/traffic/current
Get current traffic readings from all active sensors.

**Parameters:**
- `sensor_id` (optional): Filter by specific sensor
- `limit` (optional): Maximum number of results (default: 100, max: 1000)

**Response:**
```json
[
  {
    "id": "uuid",
    "sensor_id": "SENSOR_001",
    "speed": 45.5,
    "volume": 120,
    "density": 15.2,
    "occupancy": 0.85,
    "timestamp": "2024-01-15T10:30:00Z"
  }
]
```

#### GET /api/traffic/historical
Get historical traffic data with time-based filtering.

**Parameters:**
- `hours` (required): Hours of historical data (1-168)
- `sensor_id` (optional): Filter by specific sensor
- `limit` (optional): Maximum number of results

#### GET /api/traffic/statistics
Get aggregated traffic statistics.

**Parameters:**
- `hours` (required): Time window for statistics (1-168)
- `sensor_id` (optional): Filter by specific sensor

**Response:**
```json
{
  "avg_speed": 52.3,
  "min_speed": 15.0,
  "max_speed": 75.0,
  "avg_volume": 145,
  "total_readings": 1440,
  "time_window_hours": 24
}
```

### Prediction Endpoints

#### GET /api/predictions/latest
Get latest traffic predictions.

**Parameters:**
- `sensor_id` (optional): Filter by specific sensor
- `min_confidence` (optional): Minimum confidence threshold (0.0-1.0)
- `limit` (optional): Maximum number of results

#### POST /api/predictions/generate
Generate new traffic prediction for a sensor.

**Request Body:**
```json
{
  "sensor_id": "SENSOR_001",
  "horizon_minutes": 30
}
```

**Response:**
```json
{
  "message": "Prediction generation initiated",
  "prediction_id": "uuid",
  "estimated_completion": "2024-01-15T10:35:00Z"
}
```

### Analytics Endpoints

#### GET /api/analytics/congestion
Get traffic congestion analytics with time-series data.

**Parameters:**
- `hours` (required): Analysis time window (1-168)
- `sensor_id` (optional): Filter by specific sensor

**Response:**
```json
{
  "metric_name": "traffic_congestion",
  "time_period": "last_24_hours",
  "data_points": [
    {
      "timestamp": "2024-01-15T10:00:00Z",
      "avg_speed": 35.5,
      "avg_volume": 180,
      "congestion_level": "high",
      "reading_count": 60
    }
  ],
  "summary": {
    "congestion_percentage": 35.2,
    "avg_speed_overall": 45.8,
    "congested_hours": 8
  },
  "generated_at": "2024-01-15T10:30:00Z"
}
```

#### GET /api/analytics/patterns
Analyze daily and hourly traffic patterns.

#### GET /api/analytics/trends
Get long-term traffic trend analysis.

## WebSocket API

### Connection
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/real-time');
```

### Subscription Management
```javascript
// Subscribe to traffic data
ws.send(JSON.stringify({
  type: "subscribe",
  subscription: "traffic_data"
}));

// Subscribe to predictions
ws.send(JSON.stringify({
  type: "subscribe", 
  subscription: "predictions"
}));

// Subscribe to alerts
ws.send(JSON.stringify({
  type: "subscribe",
  subscription: "alerts"
}));
```

### Message Types

**Server Messages:**
- `welcome`: Connection established
- `traffic_update`: Real-time traffic data
- `prediction_update`: New prediction available
- `alert`: Traffic incident or system alert
- `system_status`: System health information
- `ping`: Heartbeat (respond with pong)

**Client Messages:**
- `subscribe`: Subscribe to data stream
- `unsubscribe`: Unsubscribe from data stream
- `pong`: Heartbeat response
- `get_status`: Request system status

## Configuration

### Environment Variables

```bash
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=traffic_db
DB_USER=postgres
DB_PASSWORD=password

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC_TRAFFIC_EVENTS=traffic-events
KAFKA_TOPIC_PROCESSED_AGGREGATES=processed-traffic-aggregates
KAFKA_TOPIC_PREDICTIONS=traffic-predictions

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=false
API_WORKERS=4

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE=/var/log/traffic-api/app.log

# Security
SECRET_KEY=your-secret-key-here
CORS_ORIGINS=http://localhost:3000,https://yourdomain.com
```

### Configuration Management

The system uses Pydantic settings with environment variable override support:

```python
from src.api.config import get_settings

settings = get_settings()
```

## Testing

### Unit Tests
```bash
cd src/api
python tests/run_tests.py --type unit
```

### Integration Tests
```bash
python tests/run_tests.py --type integration
```

### Load Testing
```bash
python tests/run_tests.py --type load --users 50 --duration 120s
```

### Full Test Suite
```bash
python tests/run_tests.py --type all
```

## Deployment

### Development Deployment
```bash
python src/api/deploy.py --config development
```

### Production Deployment

1. **Install dependencies and run health checks:**
   ```bash
   python src/api/deploy.py --config production --install-deps --health-check
   ```

2. **Create systemd service:**
   ```bash
   sudo python src/api/deploy.py --create-service --service-name traffic-api
   ```

3. **Create Nginx reverse proxy:**
   ```bash
   python src/api/deploy.py --create-nginx --domain api.yourdomain.com
   ```

4. **Start the service:**
   ```bash
   sudo systemctl start traffic-api
   sudo systemctl enable traffic-api
   ```

### Docker Deployment

```bash
# Build image
docker build -t traffic-api .

# Run container
docker run -d \
  --name traffic-api \
  -p 8000:8000 \
  -e DB_HOST=postgres \
  -e KAFKA_BOOTSTRAP_SERVERS=kafka:9092 \
  traffic-api
```

## Monitoring and Logging

### Health Checks
- `/health` - Basic health check
- `/health/detailed` - Comprehensive system status
- Database connectivity monitoring
- Kafka connectivity monitoring

### Logging
- Structured JSON logging
- Request/response logging
- Error tracking with stack traces
- Performance metrics logging

### Metrics
- Request latency and throughput
- Database query performance
- WebSocket connection counts
- Kafka message processing rates

## Performance Optimization

### Database
- Connection pooling with SQLAlchemy
- Query optimization with indexes
- Async database operations
- Connection health monitoring

### Caching
- In-memory caching for frequent queries
- Redis integration for distributed caching
- Response caching for analytics endpoints

### Scaling
- Multi-worker deployment with Uvicorn
- Horizontal scaling with load balancer
- Database read replicas for analytics
- Kafka partitioning for stream processing

## Troubleshooting

### Common Issues

1. **Database Connection Issues**
   ```bash
   python src/api/deploy.py --health-check
   ```

2. **Kafka Connection Issues**
   - Check Kafka broker status
   - Verify topic configurations
   - Review network connectivity

3. **Performance Issues**
   - Check database query performance
   - Monitor WebSocket connections
   - Review application logs

### Debug Mode
```bash
python src/api/deploy.py --config development
# Enables detailed logging and reload on code changes
```

## Security

### Authentication
- JWT token-based authentication (configurable)
- API key authentication for service-to-service

### Authorization
- Role-based access control
- Endpoint-level permissions

### Security Headers
- CORS configuration
- Security headers in responses
- Rate limiting (via Nginx)

## Contributing

1. Follow Python PEP 8 style guidelines
2. Add comprehensive tests for new features
3. Update API documentation
4. Run full test suite before submitting

## License

This FastAPI backend is part of the Traffic Prediction System project and follows the same licensing terms.