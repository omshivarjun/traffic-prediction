# 🔄 Traffic Prediction System - Data Flow & Integration Guide

**Date:** October 6, 2025  
**Purpose:** Explain current data flow, system workflow, and steps to integrate dashboard with real-time pipeline

---

## 📊 Current System Data Flow

### **Complete End-to-End Pipeline Architecture**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DATA INGESTION LAYER                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
     ┌──────────────────────────────────────────────────────────────┐
     │  METR-LA CSV Data / Test Scenarios                            │
     │  • Historical traffic data (207 sensors)                      │
     │  • 5-minute intervals                                         │
     │  • Speed, volume, occupancy metrics                           │
     └──────────────────────────────────────────────────────────────┘
                                    ↓
     ┌──────────────────────────────────────────────────────────────┐
     │  Python Kafka Producer                                        │
     │  Script: scripts/kafka_producer.py                            │
     │  • Reads JSONL test scenario files                            │
     │  • Sends to traffic-raw topic                                 │
     │  • Rate: ~22-35 msg/sec                                       │
     └──────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                        KAFKA MESSAGE BUS (12 Topics)                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
     ┌──────────────────────────────────────────────────────────────┐
     │  Kafka Topic: traffic-raw                                     │
     │  • 5 partitions                                               │
     │  • Unprocessed events                                         │
     │  • Current offset: 1,009 messages                             │
     └──────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                       STREAM PROCESSING LAYER                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
     ┌──────────────────────────────────────────────────────────────┐
     │  Stream Processor (Node.js + KafkaJS)                         │
     │  Container: stream-processor (port 3001)                      │
     │  File: src/stream-processing/index.ts                         │
     │  • Consumes from traffic-raw                                  │
     │  • Validates event structure                                  │
     │  • Enriches with metadata                                     │
     │  • Performance: <100ms latency                                │
     │  • Status: ✅ Healthy, LAG=0                                  │
     └──────────────────────────────────────────────────────────────┘
                                    ↓
                    ┌───────────────┴───────────────┐
                    ↓                               ↓
     ┌──────────────────────────┐    ┌──────────────────────────┐
     │  Kafka Topic:            │    │  Kafka Topic:            │
     │  traffic-events          │    │  processed-traffic-      │
     │  • 10 partitions         │    │  aggregates              │
     │  • Validated events      │    │  • 6 partitions          │
     │  • Ready for ML models   │    │  • 5-min windows         │
     └──────────────────────────┘    └──────────────────────────┘
                    ↓                               ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ML PREDICTION LAYER                                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
     ┌──────────────────────────────────────────────────────────────┐
     │  ML Models (Spark MLlib - NOT YET ACTIVE)                    │
     │  • sklearn_rf - Random Forest                                 │
     │  • sklearn_gbt - Gradient Boosted Trees                       │
     │  • spark_rf_speed - Spark Random Forest                       │
     │  • spark_gbt_speed - Spark GBT                                │
     │  • Training: Batch on HDFS historical data                    │
     │  • Inference: Real-time on streaming data                     │
     └──────────────────────────────────────────────────────────────┘
                                    ↓
     ┌──────────────────────────────────────────────────────────────┐
     │  Kafka Topic: traffic-predictions                             │
     │  • 6 partitions                                               │
     │  • Prediction horizon: 15/30/60 minutes                       │
     │  • Includes confidence scores                                 │
     │  • Current: EMPTY (no ML pipeline active yet)                 │
     └──────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                        STORAGE & SERVING LAYER                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    ↓
            ┌────────────────┴────────────────┐
            ↓                                  ↓
     ┌────────────────┐              ┌─────────────────┐
     │  PostgreSQL    │              │  HDFS Storage   │
     │  Port: 5433    │              │  NameNode: 9871 │
     │  • 5 tables    │              │  • Historical   │
     │  • Real-time   │              │  • Batch data   │
     │    queries     │              │  • Parquet      │
     └────────────────┘              └─────────────────┘
            ↓                                  ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                         API & FRONTEND LAYER                                  │
└─────────────────────────────────────────────────────────────────────────────┘
            ↓
     ┌──────────────────────────────────────────────────────────────┐
     │  Backend APIs                                                 │
     │  • FastAPI (port 8000) - Python ML service                    │
     │  • Traffic Backend (port 8001) - Node.js REST API             │
     │  • Next.js API Routes (port 3000)                             │
     │    - /api/traffic - Current traffic data                      │
     │    - /api/predictions - ML predictions                        │
     │    - /api/system/status - Health checks                       │
     └──────────────────────────────────────────────────────────────┘
            ↓
     ┌──────────────────────────────────────────────────────────────┐
     │  Next.js Frontend Dashboard (port 3000)                       │
     │  File: src/app/dashboard/page.tsx                             │
     │  • Currently: Mock data generator                             │
     │  • Updates: Every 5 seconds                                   │
     │  • Heatmap: Leaflet.js (8 sensors displayed)                  │
     │  • Status: ✅ Running, all pages accessible                   │
     └──────────────────────────────────────────────────────────────┘
```

---

## 🎯 Current Workflow - Step by Step

### **Phase 1: Data Generation (✅ WORKING)**

1. **Generate Test Scenarios**
   ```powershell
   python scripts/generate_test_scenarios.py
   ```
   - Creates 4,000 events across 5 realistic scenarios
   - Output: `data/test_scenarios/*.jsonl`
   - Format: METR-LA nested structure with sensor metadata

2. **Send to Kafka**
   ```powershell
   python scripts/kafka_producer.py --scenario scenario_1_normal_traffic --topic traffic-raw --rate 0
   ```
   - Reads JSONL file line by line
   - Publishes to `traffic-raw` topic
   - Performance: 22-35 msg/sec
   - Success rate: 100%

### **Phase 2: Stream Processing (✅ WORKING)**

3. **Stream Processor Consumes Events**
   - Container: `stream-processor` (always running)
   - Consumer group: `stream-processor-group`
   - Reads from: `traffic-raw` topic
   - Current LAG: 0 (fully caught up)

4. **Event Validation & Transformation**
   - Validates required fields: `sensor_id`, `timestamp`, `speed`, `volume`
   - Rejects future timestamps
   - Enriches with metadata
   - Calculates derived metrics

5. **Publishes Processed Events**
   - Writes to: `traffic-events` topic
   - Format: Validated, structured events
   - Ready for ML model consumption

### **Phase 3: Aggregation (✅ WORKING)**

6. **Windowed Aggregation**
   - Window: 5-minute tumbling windows
   - Groups by: `segment_id`
   - Calculates: avg speed, avg volume, avg occupancy
   - Determines congestion level: FREE_FLOW, LIGHT, MODERATE, HEAVY, SEVERE

7. **Publishes Aggregates**
   - Writes to: `processed-traffic-aggregates` topic
   - Used for: Historical analysis, trend detection

### **Phase 4: ML Predictions (⚠️ NOT YET ACTIVE)**

8. **Batch Training (Optional - Not Configured)**
   - Spark MLlib reads historical HDFS data
   - Trains 4 models (RF, GBT variants)
   - Exports models for real-time inference

9. **Real-Time Inference (Not Yet Implemented)**
   - Consumes from `traffic-events` or `processed-traffic-aggregates`
   - Runs predictions using trained models
   - Publishes to `traffic-predictions` topic

### **Phase 5: Frontend Display (✅ WORKING - MOCK DATA)**

10. **Dashboard Displays Data**
    - Currently: Generates mock predictions every 5 seconds
    - Shows: 8 LA highway sensors with real coordinates
    - Heatmap: Leaflet.js with intensity based on speed
    - Metrics: Avg speed, congestion count, model accuracy

---

## 🚀 Next Steps: Connecting Dashboard to Real Pipeline

### **Option A: WebSocket Real-Time Integration (Recommended)**

This approach provides true real-time updates without polling.

#### **Step 1: Create WebSocket Server**

Create `src/lib/services/websocketService.ts`:

```typescript
import { Server } from 'socket.io';
import { Kafka, Consumer, EachMessagePayload } from 'kafkajs';

export class WebSocketService {
  private io: Server;
  private kafka: Kafka;
  private consumer: Consumer | null = null;

  constructor(server: any) {
    this.io = new Server(server, {
      cors: { origin: '*' }
    });

    this.kafka = new Kafka({
      clientId: 'dashboard-websocket',
      brokers: ['localhost:9092']
    });

    this.setupWebSocket();
  }

  private setupWebSocket() {
    this.io.on('connection', (socket) => {
      console.log('Dashboard client connected:', socket.id);

      socket.on('subscribe-predictions', async () => {
        console.log('Client subscribed to predictions');
        await this.startKafkaConsumer();
      });

      socket.on('disconnect', () => {
        console.log('Dashboard client disconnected:', socket.id);
      });
    });
  }

  private async startKafkaConsumer() {
    if (this.consumer) return; // Already running

    this.consumer = this.kafka.consumer({
      groupId: 'dashboard-websocket-group'
    });

    await this.consumer.connect();
    await this.consumer.subscribe({
      topic: 'traffic-predictions',
      fromBeginning: false
    });

    await this.consumer.run({
      eachMessage: async ({ message }: EachMessagePayload) => {
        try {
          const prediction = JSON.parse(message.value?.toString() || '{}');
          
          // Broadcast to all connected clients
          this.io.emit('new-prediction', prediction);
        } catch (error) {
          console.error('Error processing Kafka message:', error);
        }
      }
    });
  }

  async shutdown() {
    if (this.consumer) {
      await this.consumer.disconnect();
    }
    this.io.close();
  }
}
```

#### **Step 2: Update Next.js Server**

Modify `server.js` (create if needed):

```javascript
const { createServer } = require('http');
const { parse } = require('url');
const next = require('next');
const { WebSocketService } = require('./src/lib/services/websocketService');

const dev = process.env.NODE_ENV !== 'production';
const app = next({ dev });
const handle = app.getRequestHandler();

app.prepare().then(() => {
  const server = createServer((req, res) => {
    const parsedUrl = parse(req.url, true);
    handle(req, res, parsedUrl);
  });

  // Initialize WebSocket service
  const wsService = new WebSocketService(server);

  server.listen(3000, () => {
    console.log('> Ready on http://localhost:3000');
    console.log('> WebSocket server ready for connections');
  });

  process.on('SIGTERM', async () => {
    await wsService.shutdown();
    process.exit(0);
  });
});
```

#### **Step 3: Update Dashboard Component**

Modify `src/app/dashboard/page.tsx`:

```typescript
'use client';

import { useEffect, useState, useRef } from 'react';
import dynamic from 'next/dynamic';
import { io, Socket } from 'socket.io-client';

// ... existing imports ...

export default function TrafficDashboard() {
  const [predictions, setPredictions] = useState<TrafficPrediction[]>([]);
  const [heatmapData, setHeatmapData] = useState<TrafficHeatmapData[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<string>('');
  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    // Connect to WebSocket server
    const socket = io('http://localhost:3000', {
      transports: ['websocket']
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      
      // Subscribe to predictions
      socket.emit('subscribe-predictions');
    });

    socket.on('new-prediction', (prediction: TrafficPrediction) => {
      console.log('Received new prediction:', prediction);
      
      setPredictions(prev => {
        // Keep last 50 predictions
        const updated = [prediction, ...prev].slice(0, 50);
        return updated;
      });

      setHeatmapData(prev => {
        // Update heatmap with new prediction
        const existing = prev.find(d => d.sensor_id === prediction.sensor_id);
        
        if (existing) {
          return prev.map(d =>
            d.sensor_id === prediction.sensor_id
              ? {
                  ...d,
                  speed: prediction.predicted_speed,
                  intensity: Math.max(1, 10 - prediction.predicted_speed / 10)
                }
              : d
          );
        } else {
          return [...prev, convertToHeatmapData([prediction])[0]];
        }
      });

      setLastUpdate(new Date().toLocaleTimeString());
    });

    socket.on('disconnect', () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
    });

    socket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error);
      setIsConnected(false);
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  // Remove the mock data generation interval
  // Keep the rest of your component as-is...

  return (
    // ... existing JSX ...
  );
}
```

---

### **Option B: REST API Polling (Simpler, Less Real-Time)**

#### **Step 1: Create Kafka Consumer API Endpoint**

Create `src/app/api/predictions/latest/route.ts`:

```typescript
import { NextRequest, NextResponse } from 'next/server';
import { Kafka, Consumer } from 'kafkajs';

let consumer: Consumer | null = null;
let latestPredictions: any[] = [];
let isConsuming = false;

// Initialize Kafka consumer (runs once)
async function initializeConsumer() {
  if (isConsuming) return;

  const kafka = new Kafka({
    clientId: 'nextjs-api-consumer',
    brokers: ['localhost:9092']
  });

  consumer = kafka.consumer({
    groupId: 'nextjs-api-group',
    sessionTimeout: 30000
  });

  await consumer.connect();
  await consumer.subscribe({
    topic: 'traffic-predictions',
    fromBeginning: false
  });

  isConsuming = true;

  await consumer.run({
    eachMessage: async ({ message }) => {
      try {
        const prediction = JSON.parse(message.value?.toString() || '{}');
        
        // Keep last 100 predictions in memory
        latestPredictions = [prediction, ...latestPredictions].slice(0, 100);
      } catch (error) {
        console.error('Error parsing prediction:', error);
      }
    }
  });

  console.log('Kafka consumer initialized for predictions API');
}

export async function GET(request: NextRequest) {
  try {
    // Initialize consumer on first request
    if (!isConsuming) {
      await initializeConsumer();
    }

    const searchParams = request.nextUrl.searchParams;
    const limit = parseInt(searchParams.get('limit') || '50');

    return NextResponse.json({
      success: true,
      data: {
        predictions: latestPredictions.slice(0, limit),
        total: latestPredictions.length,
        timestamp: new Date().toISOString(),
        source: 'kafka-real-time'
      }
    });

  } catch (error) {
    console.error('Error fetching predictions:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to fetch predictions' },
      { status: 500 }
    );
  }
}
```

#### **Step 2: Update Dashboard to Poll API**

Modify `src/app/dashboard/page.tsx`:

```typescript
export default function TrafficDashboard() {
  const [predictions, setPredictions] = useState<TrafficPrediction[]>([]);
  // ... other state ...

  useEffect(() => {
    // Fetch predictions from real API
    const fetchPredictions = async () => {
      try {
        const response = await fetch('/api/predictions/latest?limit=50');
        const data = await response.json();

        if (data.success && data.data.predictions.length > 0) {
          setPredictions(data.data.predictions);
          setHeatmapData(convertToHeatmapData(data.data.predictions));
          setLastUpdate(new Date().toLocaleTimeString());
          setIsConnected(true);
        }
      } catch (error) {
        console.error('Error fetching predictions:', error);
        setIsConnected(false);
      }
    };

    // Initial fetch
    fetchPredictions();

    // Poll every 5 seconds
    const interval = setInterval(fetchPredictions, 5000);

    return () => clearInterval(interval);
  }, []);

  // ... rest of component ...
}
```

---

### **Option C: Server-Sent Events (SSE) - Middle Ground**

Provides real-time updates with simpler setup than WebSockets.

#### **Create SSE Endpoint**

Create `src/app/api/predictions/stream/route.ts`:

```typescript
import { NextRequest } from 'next/server';
import { Kafka, Consumer } from 'kafkajs';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      const kafka = new Kafka({
        clientId: 'sse-stream-client',
        brokers: ['localhost:9092']
      });

      const consumer = kafka.consumer({
        groupId: `sse-stream-${Date.now()}`
      });

      await consumer.connect();
      await consumer.subscribe({
        topic: 'traffic-predictions',
        fromBeginning: false
      });

      // Send initial connection message
      controller.enqueue(
        encoder.encode(`data: ${JSON.stringify({ type: 'connected' })}\n\n`)
      );

      await consumer.run({
        eachMessage: async ({ message }) => {
          try {
            const prediction = JSON.parse(message.value?.toString() || '{}');
            
            controller.enqueue(
              encoder.encode(
                `data: ${JSON.stringify({ type: 'prediction', data: prediction })}\n\n`
              )
            );
          } catch (error) {
            console.error('SSE stream error:', error);
          }
        }
      });

      // Cleanup on client disconnect
      request.signal.addEventListener('abort', async () => {
        await consumer.disconnect();
        controller.close();
      });
    }
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive'
    }
  });
}
```

#### **Update Dashboard for SSE**

```typescript
export default function TrafficDashboard() {
  useEffect(() => {
    const eventSource = new EventSource('/api/predictions/stream');

    eventSource.onmessage = (event) => {
      const message = JSON.parse(event.data);

      if (message.type === 'connected') {
        setIsConnected(true);
        console.log('SSE connected');
      } else if (message.type === 'prediction') {
        setPredictions(prev => [message.data, ...prev].slice(0, 50));
        setLastUpdate(new Date().toLocaleTimeString());
      }
    };

    eventSource.onerror = () => {
      setIsConnected(false);
      console.error('SSE connection error');
    };

    return () => {
      eventSource.close();
    };
  }, []);

  // ... rest of component ...
}
```

---

## 🗺️ Adding Interactive Leaflet Maps

### **Step 1: Install Leaflet**

```powershell
npm install leaflet @types/leaflet react-leaflet
```

### **Step 2: Create Enhanced Map Component**

Create `src/components/InteractiveTrafficMap.tsx`:

```typescript
'use client';

import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

interface TrafficMapData {
  latitude: number;
  longitude: number;
  speed: number;
  sensor_id: string;
  road_name?: string;
  predicted_speed: number;
  confidence_score: number;
}

interface InteractiveTrafficMapProps {
  data: TrafficMapData[];
  center?: [number, number];
  zoom?: number;
}

// Auto-fit map to show all markers
function MapUpdater({ data }: { data: TrafficMapData[] }) {
  const map = useMap();

  useEffect(() => {
    if (data.length > 0) {
      const bounds = L.latLngBounds(
        data.map(d => [d.latitude, d.longitude])
      );
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [data, map]);

  return null;
}

export default function InteractiveTrafficMap({
  data,
  center = [34.0522, -118.2437], // Los Angeles center
  zoom = 10
}: InteractiveTrafficMapProps) {
  const [mapReady, setMapReady] = useState(false);

  const getMarkerColor = (speed: number): string => {
    if (speed >= 60) return '#22c55e'; // Green - free flow
    if (speed >= 40) return '#eab308'; // Yellow - moderate
    if (speed >= 20) return '#f97316'; // Orange - heavy
    return '#ef4444'; // Red - severe
  };

  const getMarkerRadius = (speed: number): number => {
    if (speed < 20) return 15; // Larger for severe congestion
    if (speed < 40) return 12;
    if (speed < 60) return 10;
    return 8;
  };

  useEffect(() => {
    setMapReady(true);
  }, []);

  if (!mapReady) {
    return (
      <div className="h-[500px] bg-gray-100 animate-pulse rounded-lg flex items-center justify-center">
        Loading map...
      </div>
    );
  }

  return (
    <MapContainer
      center={center}
      zoom={zoom}
      className="h-[500px] rounded-lg shadow-lg z-0"
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a>'
      />

      <MapUpdater data={data} />

      {data.map((point, index) => (
        <CircleMarker
          key={`${point.sensor_id}-${index}`}
          center={[point.latitude, point.longitude]}
          radius={getMarkerRadius(point.speed)}
          fillColor={getMarkerColor(point.speed)}
          color="#fff"
          weight={2}
          opacity={0.9}
          fillOpacity={0.7}
        >
          <Popup>
            <div className="p-2">
              <h3 className="font-bold text-sm">{point.sensor_id}</h3>
              {point.road_name && (
                <p className="text-xs text-gray-600">{point.road_name}</p>
              )}
              <div className="mt-2 space-y-1 text-xs">
                <p>
                  <strong>Current Speed:</strong>{' '}
                  <span style={{ color: getMarkerColor(point.speed) }}>
                    {point.speed.toFixed(1)} mph
                  </span>
                </p>
                <p>
                  <strong>Predicted:</strong> {point.predicted_speed.toFixed(1)} mph
                </p>
                <p>
                  <strong>Confidence:</strong>{' '}
                  {(point.confidence_score * 100).toFixed(1)}%
                </p>
              </div>
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
```

### **Step 3: Use in Dashboard**

```typescript
import dynamic from 'next/dynamic';

const InteractiveTrafficMap = dynamic(
  () => import('@/components/InteractiveTrafficMap'),
  { ssr: false, loading: () => <div>Loading map...</div> }
);

export default function TrafficDashboard() {
  // ... existing code ...

  return (
    <div className="bg-white rounded-lg shadow-md p-6 mb-6">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">
        Real-time Traffic Map
      </h2>
      <InteractiveTrafficMap data={heatmapData} />
    </div>
  );
}
```

---

## 📝 Summary & Recommendations

### **Current Status**
✅ **Working:** Data ingestion → Kafka → Stream processing → Validated events  
⚠️ **Gap:** No ML predictions being generated yet  
✅ **Working:** Frontend displays mock data with realistic scenarios

### **Recommended Integration Path**

**Phase 1 (Immediate - 2 hours):**
1. Implement **Option A: WebSocket** for real-time updates
2. Connect to existing `traffic-events` topic (shows processed events)
3. Test with current test data flow

**Phase 2 (Short-term - 4 hours):**
1. Add **Interactive Leaflet Map** component
2. Implement popup details and clustering
3. Add heatmap layer for density visualization

**Phase 3 (Medium-term - 1-2 days):**
1. Set up Spark ML batch training pipeline
2. Configure real-time inference on stream
3. Publish predictions to `traffic-predictions` topic
4. Switch WebSocket to consume from predictions topic

**Phase 4 (Long-term - 1 week):**
1. Add historical data playback
2. Implement alerting system
3. Add route planning features
4. Performance optimization and caching

### **Key Files to Modify**
- `src/app/dashboard/page.tsx` - Dashboard component
- `src/lib/services/websocketService.ts` - **NEW** WebSocket server
- `src/components/InteractiveTrafficMap.tsx` - **NEW** Map component
- `package.json` - Add socket.io, leaflet dependencies

### **Required Dependencies**
```json
{
  "socket.io": "^4.7.5",
  "socket.io-client": "^4.7.5",
  "kafkajs": "^2.2.4",
  "leaflet": "^1.9.4",
  "react-leaflet": "^4.2.1",
  "@types/leaflet": "^1.9.12"
}
```

---

**The system is ready for real-time integration! All infrastructure is operational and waiting for the ML prediction pipeline to be activated.** 🚀
