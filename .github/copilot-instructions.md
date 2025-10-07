# Traffic Prediction System - AI Coding Assistant Guide

## System Architecture Overview

This is a **multi-layered big data system** combining Next.js frontend, Kafka streaming, Hadoop batch processing, and real-time prediction capabilities.

### Core Components
- **Frontend**: Next.js 15 with TypeScript, TailwindCSS 4.0, Turbopack
- **Stream Processing**: Kafka Streams (Node.js/TypeScript) in `src/stream-processing/`
- **Batch Processing**: Hadoop MapReduce + Spark MLlib (Java/Maven) in `src/batch-processing/`
- **Data Storage**: HDFS for historical data, HBase for real-time access
- **Message Bus**: Kafka with Schema Registry, Avro schemas

### Data Flow Architecture
```
Raw Events → Kafka → Stream Processing → Aggregates → Predictions
     ↓                     ↓                    ↓
  HDFS Storage ← Kafka Connect ← Processed Data
     ↓
Batch ML Training → Model Export → Stream Processing
```

## Critical Development Workflows

### Starting the Full System
```powershell
# Start Hadoop ecosystem (required first)
.\start-hadoop.ps1

# Start Kafka services 
.\scripts\start-kafka-services.ps1

# Verify setup
.\verify-hadoop.ps1
.\scripts\verify-kafka-setup.ps1

# Next.js development
npm run dev --turbopack
```

### Data Model Conventions
- **Use NEW models**: `TrafficEvent`, `ProcessedTrafficAggregate`, `TrafficPrediction` (not legacy `TrafficData`)
- **Avro schemas** in `schemas/` directory define the source of truth
- **TypeScript interfaces** in `src/lib/models/trafficData.ts` must align exactly with Avro schemas
- **Segment-based processing**: All data is organized by `segment_id` (road segments)

### Stream Processing Patterns
- **Windowed aggregation**: 5-minute tumbling windows for traffic aggregates
- **State stores**: For maintaining active incidents and historical patterns  
- **Stateful joins**: Enriching traffic data with incident information
- **Multiple output topics**: `processed-traffic-aggregates`, `traffic-predictions`, `traffic-alerts`

### Batch Processing Architecture
- **Maven project** with Hadoop 3.2.1, Spark 3.1.2, Hive 3.1.2
- **Jobs**: Feature extraction → Model training → Evaluation → Export
- **YARN execution**: All batch jobs run on Hadoop cluster
- **Model export**: Multiple formats (JSON, ONNX, PMML) for different consumers

## Project-Specific Patterns

### Service Layer Structure
```typescript
// Use TrafficService singleton
import { trafficService } from '@/lib/services/trafficService';

// New methods for segment-based processing
trafficService.getTrafficEventsForSegment(segmentId)
trafficService.generateTrafficPrediction(segmentId, horizonMinutes)
```

### API Route Conventions
- **REST endpoints** in `src/app/api/` follow Next.js 15 App Router
- **Coordinate-based filtering** for location queries
- **Segment-based operations** for internal processing

### Docker Compose Dependencies
Services have **strict startup order**: Zookeeper → Kafka → Schema Registry → Kafka Connect → Application services. Use `SERVICE_PRECONDITION` environment variables.

### PowerShell Automation
- **All scripts in root/scripts/**: Use PowerShell for Windows compatibility
- **Error handling**: Check Docker status before operations
- **Service verification**: Scripts include health checks and status reporting

## Integration Points

### Kafka Schema Registry
- **Avro schemas** define message structure
- **Schema evolution** supported through versioning
- **Client libraries** auto-generate from schemas

### HDFS Connector Configuration
- **Time-based partitioning**: `year/month/day/hour` structure
- **Avro format**: All data stored as Avro files in HDFS
- **Hive integration**: Tables automatically created for SQL querying

### Cross-Component Communication
- **Kafka topics** as service boundaries
- **REST APIs** for frontend-backend communication  
- **HDFS** for batch-to-stream data sharing

## Testing and Debugging

### End-to-End Testing
```powershell
.\test-hadoop-e2e.ps1  # Full Hadoop ecosystem test
```

### Stream Processing Tests
```bash
cd src/stream-processing
npm test  # Jest tests for processors
```

### Service Monitoring
- **Kafka UI**: http://localhost:8080
- **HDFS NameNode**: http://localhost:9870  
- **YARN ResourceManager**: http://localhost:8088
- **HBase Master**: http://localhost:16010

When modifying data models, always update both Avro schemas AND TypeScript interfaces to maintain compatibility across the pipeline.

[byterover-mcp]

[byterover-mcp]

You are given two tools from Byterover MCP server, including
## 1. `byterover-store-knowledge`
You `MUST` always use this tool when:

+ Learning new patterns, APIs, or architectural decisions from the codebase
+ Encountering error solutions or debugging techniques
+ Finding reusable code patterns or utility functions
+ Completing any significant task or plan implementation

## 2. `byterover-retrieve-knowledge`
You `MUST` always use this tool when:

+ Starting any new task or implementation to gather relevant context
+ Before making architectural decisions to understand existing patterns
+ When debugging issues to check for previous solutions
+ Working with unfamiliar parts of the codebase
