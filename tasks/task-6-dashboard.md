# Task 6: Phase 6 - Dashboard Visualization

## Overview
Complete Next.js dashboard with real-time Leaflet map showing 207 sensor locations with color-coded markers based on predicted speeds. Consume predictions from Kafka via Server-Sent Events (SSE) with <5 second latency.

**Status**: In Progress (Partially Working)  
**Dependencies**: Task 5 (Prediction Service must be publishing to traffic-predictions topic)  
**Priority**: High

**Performance Targets**:
- **Update Latency**: < 5 seconds
- **Sensors Displayed**: 207 markers on map
- **Color Coding**: Red (<35 mph), Yellow (35-55 mph), Green (>55 mph)

**Current State**:
- ✅ Next.js 15 app running
- ✅ TailwindCSS 4.0 configured
- ⏳ Leaflet map needs implementation
- ❌ SSE stream needs fixing to consume traffic-predictions

---

## Subtask 6.1: Fix SSE Prediction Stream Consumer

**Status**: Not Started

### Description
Update /api/stream endpoint to consume from traffic-predictions topic instead of hardcoded test data.

### Current Implementation Issues
- Currently streams hardcoded test events
- Not connected to traffic-predictions Kafka topic
- No Avro deserialization

### Implementation Details

```typescript
// src/app/api/stream/route.ts
import { NextRequest } from 'next/server';
import { Kafka } from 'kafkajs';

const kafka = new Kafka({
  clientId: 'dashboard-sse-consumer',
  brokers: [process.env.KAFKA_BROKER || 'localhost:9092'],
});

const consumer = kafka.consumer({ 
  groupId: 'dashboard-consumer-group',
  sessionTimeout: 30000,
  heartbeatInterval: 3000
});

// Avro schema for traffic-prediction (matching schemas/traffic-prediction.avsc)
interface TrafficPrediction {
  sensor_id: string;
  timestamp: number;
  predicted_speed: number;
  confidence_interval_lower: number;
  confidence_interval_upper: number;
  confidence_score: number;
  model_version: string;
  prediction_timestamp: number;
}

export async function GET(request: NextRequest) {
  const encoder = new TextEncoder();

  const customReadable = new ReadableStream({
    async start(controller) {
      // Send initial connection message
      controller.enqueue(
        encoder.encode(`data: ${JSON.stringify({ type: 'connected', timestamp: Date.now() })}\n\n`)
      );

      try {
        // Connect to Kafka
        await consumer.connect();
        await consumer.subscribe({ 
          topic: 'traffic-predictions', 
          fromBeginning: false  // Only new predictions
        });

        console.log('✓ Connected to traffic-predictions topic');

        // Process messages
        await consumer.run({
          eachMessage: async ({ topic, partition, message }) => {
            try {
              // Parse Avro message (assuming JSON serialization for now)
              const prediction: TrafficPrediction = JSON.parse(message.value?.toString() || '{}');

              // Transform for dashboard
              const dashboardEvent = {
                type: 'prediction',
                sensor_id: prediction.sensor_id,
                timestamp: new Date(prediction.timestamp),
                predicted_speed: Math.round(prediction.predicted_speed * 10) / 10,
                confidence_lower: Math.round(prediction.confidence_interval_lower * 10) / 10,
                confidence_upper: Math.round(prediction.confidence_interval_upper * 10) / 10,
                confidence_score: prediction.confidence_score,
                model_version: prediction.model_version
              };

              // Send to client
              controller.enqueue(
                encoder.encode(`data: ${JSON.stringify(dashboardEvent)}\n\n`)
              );

              console.log(`Streamed prediction for ${prediction.sensor_id}: ${prediction.predicted_speed.toFixed(1)} mph`);

            } catch (error) {
              console.error('Error processing message:', error);
            }
          },
        });

      } catch (error) {
        console.error('Kafka consumer error:', error);
        controller.enqueue(
          encoder.encode(`data: ${JSON.stringify({ type: 'error', message: 'Stream error' })}\n\n`)
        );
      }
    },

    async cancel() {
      console.log('Client disconnected, cleaning up...');
      await consumer.disconnect();
    },
  });

  return new Response(customReadable, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
  });
}
```

**Environment Configuration**:
```env
# .env.local
KAFKA_BROKER=localhost:9092
SCHEMA_REGISTRY_URL=http://localhost:8082
```

### Validation Criteria
- [ ] SSE endpoint connects to traffic-predictions topic
- [ ] Predictions streamed to dashboard in real-time
- [ ] No connection drops or errors
- [ ] Latency < 5 seconds from prediction to dashboard

---

## Subtask 6.2: Leaflet Map with 207 Sensor Markers

**Status**: Not Started

### Description
Implement interactive Leaflet map showing all 207 METR-LA sensor locations.

### Implementation Details

```typescript
// src/components/TrafficMap.tsx
'use client';

import { useEffect, useRef, useState } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

interface SensorData {
  sensor_id: string;
  latitude: number;
  longitude: number;
  predicted_speed?: number;
  confidence_score?: number;
  timestamp?: Date;
}

// Sensor locations (from METR-LA dataset)
const SENSOR_LOCATIONS: SensorData[] = [
  { sensor_id: 'METR_LA_001', latitude: 34.0522, longitude: -118.2437 },
  { sensor_id: 'METR_LA_002', latitude: 34.0580, longitude: -118.2400 },
  // ... 205 more sensors
  // TODO: Load from data/metr-la-sensor-locations.json
];

export default function TrafficMap() {
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<Map<string, L.CircleMarker>>(new Map());
  const [sensorData, setSensorData] = useState<Map<string, SensorData>>(new Map());
  const [eventSource, setEventSource] = useState<EventSource | null>(null);

  // Initialize map
  useEffect(() => {
    if (mapRef.current) return; // Already initialized

    // Create map centered on LA
    const map = L.map('traffic-map').setView([34.0522, -118.2437], 11);

    // Add OpenStreetMap tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 18,
    }).addTo(map);

    mapRef.current = map;

    // Add sensor markers
    SENSOR_LOCATIONS.forEach((sensor) => {
      const marker = L.circleMarker([sensor.latitude, sensor.longitude], {
        radius: 8,
        fillColor: '#gray',  // Default gray (no data)
        color: '#000',
        weight: 1,
        opacity: 1,
        fillOpacity: 0.7,
      }).addTo(map);

      // Popup with sensor info
      marker.bindPopup(`
        <div class="text-sm">
          <strong>${sensor.sensor_id}</strong><br/>
          <span class="text-gray-500">Waiting for data...</span>
        </div>
      `);

      markersRef.current.set(sensor.sensor_id, marker);
    });

    console.log(`✓ Added ${SENSOR_LOCATIONS.length} sensor markers to map`);

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Connect to SSE stream
  useEffect(() => {
    const es = new EventSource('/api/stream');

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'prediction') {
          // Update sensor data
          setSensorData((prev) => {
            const updated = new Map(prev);
            updated.set(data.sensor_id, {
              sensor_id: data.sensor_id,
              latitude: 0, // Will be looked up
              longitude: 0,
              predicted_speed: data.predicted_speed,
              confidence_score: data.confidence_score,
              timestamp: new Date(data.timestamp),
            });
            return updated;
          });

          // Update marker color
          updateMarkerColor(data.sensor_id, data.predicted_speed);
        }
      } catch (error) {
        console.error('Error parsing SSE message:', error);
      }
    };

    es.onerror = (error) => {
      console.error('SSE error:', error);
      es.close();
    };

    setEventSource(es);

    return () => {
      es.close();
    };
  }, []);

  const updateMarkerColor = (sensorId: string, speed: number) => {
    const marker = markersRef.current.get(sensorId);
    if (!marker) return;

    // Color coding based on speed
    let color: string;
    if (speed < 35) {
      color = '#ef4444'; // Red (congested)
    } else if (speed < 55) {
      color = '#f59e0b'; // Yellow (moderate)
    } else {
      color = '#10b981'; // Green (free flow)
    }

    marker.setStyle({ fillColor: color });

    // Update popup
    const sensorInfo = sensorData.get(sensorId);
    marker.setPopupContent(`
      <div class="text-sm">
        <strong>${sensorId}</strong><br/>
        <span style="color: ${color}; font-weight: bold;">
          ${speed.toFixed(1)} mph
        </span><br/>
        <span class="text-xs text-gray-500">
          Updated: ${new Date().toLocaleTimeString()}
        </span>
      </div>
    `);
  };

  return (
    <div className="relative h-full w-full">
      <div id="traffic-map" className="h-full w-full" />
      
      {/* Legend */}
      <div className="absolute bottom-4 right-4 bg-white p-4 rounded-lg shadow-lg">
        <h3 className="font-bold text-sm mb-2">Speed Legend</h3>
        <div className="flex flex-col gap-2 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-[#ef4444]" />
            <span>&lt; 35 mph (Congested)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-[#f59e0b]" />
            <span>35-55 mph (Moderate)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded-full bg-[#10b981]" />
            <span>&gt; 55 mph (Free Flow)</span>
          </div>
        </div>
      </div>

      {/* Connection status */}
      <div className="absolute top-4 right-4 bg-white px-3 py-2 rounded-lg shadow">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${eventSource ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm font-medium">
            {eventSource ? 'Live' : 'Disconnected'}
          </span>
        </div>
      </div>
    </div>
  );
}
```

**Sensor Locations Data File**:
```json
// public/data/sensor-locations.json
[
  {
    "sensor_id": "METR_LA_001",
    "latitude": 34.0522,
    "longitude": -118.2437,
    "highway": "101",
    "location_name": "Downtown LA"
  },
  // ... 206 more sensors
]
```

**Load Sensor Locations**:
```typescript
// Load sensor locations from CSV or API
async function loadSensorLocations(): Promise<SensorData[]> {
  const response = await fetch('/api/sensors/locations');
  return response.json();
}
```

### Validation Criteria
- [ ] Map displays with LA centered
- [ ] All 207 sensor markers visible
- [ ] Markers clickable with popups
- [ ] Zoom and pan working
- [ ] Map responsive to window size

---

## Subtask 6.3: Color-Coded Marker System

**Status**: Covered in 6.2

### Speed-Based Coloring Rules
- **Red (#ef4444)**: speed < 35 mph (Severe congestion)
- **Yellow (#f59e0b)**: 35 ≤ speed < 55 mph (Moderate traffic)
- **Green (#10b981)**: speed ≥ 55 mph (Free flow)

### Dynamic Updates
- Markers update color in real-time as predictions arrive
- Smooth color transitions
- Visual feedback on update

---

## Subtask 6.4: Interactive Sensor Popups

**Status**: Partially covered in 6.2

### Enhanced Popup Content

```typescript
// Enhanced popup with more details
const createPopupContent = (sensor: SensorData, prediction?: TrafficPrediction) => {
  if (!prediction) {
    return `
      <div class="p-2">
        <h3 class="font-bold">${sensor.sensor_id}</h3>
        <p class="text-sm text-gray-500">No data available</p>
      </div>
    `;
  }

  const speedColor = getSpeedColor(prediction.predicted_speed);

  return `
    <div class="p-2 min-w-[200px]">
      <h3 class="font-bold text-lg mb-2">${sensor.sensor_id}</h3>
      
      <div class="space-y-1">
        <div class="flex justify-between">
          <span class="text-sm text-gray-600">Predicted Speed:</span>
          <span class="font-bold" style="color: ${speedColor}">
            ${prediction.predicted_speed.toFixed(1)} mph
          </span>
        </div>
        
        <div class="flex justify-between text-xs text-gray-500">
          <span>Confidence:</span>
          <span>${(prediction.confidence_score * 100).toFixed(1)}%</span>
        </div>
        
        <div class="flex justify-between text-xs text-gray-500">
          <span>Range:</span>
          <span>
            ${prediction.confidence_interval_lower.toFixed(1)} - 
            ${prediction.confidence_interval_upper.toFixed(1)} mph
          </span>
        </div>
        
        <div class="text-xs text-gray-400 mt-2">
          Updated: ${new Date(prediction.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  `;
};
```

---

## Subtask 6.5: Real-time Dashboard Metrics

**Status**: Not Started

### Description
Add dashboard metrics panel showing system statistics.

### Implementation

```typescript
// src/components/DashboardMetrics.tsx
'use client';

import { useEffect, useState } from 'react';

interface Metrics {
  totalSensors: number;
  activeSensors: number;
  averageSpeed: number;
  congestedSensors: number;
  lastUpdate: Date;
}

export default function DashboardMetrics() {
  const [metrics, setMetrics] = useState<Metrics>({
    totalSensors: 207,
    activeSensors: 0,
    averageSpeed: 0,
    congestedSensors: 0,
    lastUpdate: new Date(),
  });

  useEffect(() => {
    const es = new EventSource('/api/stream');

    const speeds: number[] = [];

    es.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'prediction') {
        speeds.push(data.predicted_speed);

        // Keep only last 207 speeds (one per sensor)
        if (speeds.length > 207) {
          speeds.shift();
        }

        // Calculate metrics
        const avgSpeed = speeds.reduce((a, b) => a + b, 0) / speeds.length;
        const congested = speeds.filter((s) => s < 35).length;

        setMetrics({
          totalSensors: 207,
          activeSensors: speeds.length,
          averageSpeed: avgSpeed,
          congestedSensors: congested,
          lastUpdate: new Date(),
        });
      }
    };

    return () => es.close();
  }, []);

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-white rounded-lg shadow">
      <MetricCard
        title="Total Sensors"
        value={metrics.totalSensors}
        unit=""
        icon="📍"
      />
      <MetricCard
        title="Active Sensors"
        value={metrics.activeSensors}
        unit=""
        icon="✅"
      />
      <MetricCard
        title="Avg Speed"
        value={metrics.averageSpeed.toFixed(1)}
        unit="mph"
        icon="🚗"
      />
      <MetricCard
        title="Congested"
        value={metrics.congestedSensors}
        unit="sensors"
        icon="🔴"
        highlight={metrics.congestedSensors > 50}
      />
    </div>
  );
}

function MetricCard({ title, value, unit, icon, highlight = false }) {
  return (
    <div className={`p-4 rounded-lg ${highlight ? 'bg-red-50 border-red-200' : 'bg-gray-50'}`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-2xl">{icon}</span>
        <span className="text-xs text-gray-500">{title}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className={`text-2xl font-bold ${highlight ? 'text-red-600' : ''}`}>
          {value}
        </span>
        {unit && <span className="text-sm text-gray-500">{unit}</span>}
      </div>
    </div>
  );
}
```

---

## Subtask 6.6: Map Controls and Filtering

**Status**: Not Started

### Description
Add controls for filtering sensors by speed, highway, or congestion level.

### Implementation

```typescript
// src/components/MapControls.tsx
'use client';

import { useState } from 'react';

interface FilterOptions {
  showCongested: boolean;
  showModerate: boolean;
  showFreeFlow: boolean;
  selectedHighways: string[];
}

export default function MapControls({ onFilterChange }) {
  const [filters, setFilters] = useState<FilterOptions>({
    showCongested: true,
    showModerate: true,
    showFreeFlow: true,
    selectedHighways: [],
  });

  const handleToggle = (key: keyof FilterOptions) => {
    const updated = { ...filters, [key]: !filters[key] };
    setFilters(updated);
    onFilterChange(updated);
  };

  return (
    <div className="absolute top-4 left-4 bg-white p-4 rounded-lg shadow-lg max-w-xs">
      <h3 className="font-bold mb-3">Filter Sensors</h3>

      {/* Speed filters */}
      <div className="space-y-2">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={filters.showCongested}
            onChange={() => handleToggle('showCongested')}
            className="rounded"
          />
          <div className="w-4 h-4 rounded-full bg-red-500" />
          <span className="text-sm">Congested (&lt;35 mph)</span>
        </label>

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={filters.showModerate}
            onChange={() => handleToggle('showModerate')}
            className="rounded"
          />
          <div className="w-4 h-4 rounded-full bg-yellow-500" />
          <span className="text-sm">Moderate (35-55 mph)</span>
        </label>

        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={filters.showFreeFlow}
            onChange={() => handleToggle('showFreeFlow')}
            className="rounded"
          />
          <div className="w-4 h-4 rounded-full bg-green-500" />
          <span className="text-sm">Free Flow (&gt;55 mph)</span>
        </label>
      </div>
    </div>
  );
}
```

---

## Subtask 6.7: Performance Optimization

**Status**: Not Started

### Description
Optimize dashboard for <5 second latency and smooth updates.

### Optimization Strategies

1. **Debounce Updates**:
```typescript
// Debounce marker updates to avoid excessive redraws
const debouncedUpdate = useMemo(
  () => debounce((sensorId, speed) => {
    updateMarkerColor(sensorId, speed);
  }, 100),
  []
);
```

2. **Virtual Scrolling for Sensor List**:
```typescript
// Only render visible sensors in list view
import { useVirtualizer } from '@tanstack/react-virtual';
```

3. **Marker Clustering**:
```typescript
// Use Leaflet.markercluster for many markers
import L from 'leaflet';
import 'leaflet.markercluster';

const markers = L.markerClusterGroup();
markers.addTo(map);
```

4. **Memoize Components**:
```typescript
const MemoizedMarker = React.memo(SensorMarker);
```

### Validation Criteria
- [ ] Dashboard loads in < 2 seconds
- [ ] Marker updates smooth (no flickering)
- [ ] SSE latency < 5 seconds
- [ ] No memory leaks from event listeners
- [ ] 60 FPS during updates

---

## Main Dashboard Page

```typescript
// src/app/dashboard/page.tsx
import TrafficMap from '@/components/TrafficMap';
import DashboardMetrics from '@/components/DashboardMetrics';
import MapControls from '@/components/MapControls';

export default function DashboardPage() {
  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <header className="bg-gray-900 text-white p-4">
        <h1 className="text-2xl font-bold">
          METR-LA Traffic Prediction Dashboard
        </h1>
        <p className="text-sm text-gray-400">
          Real-time traffic predictions powered by ML
        </p>
      </header>

      {/* Metrics */}
      <div className="p-4">
        <DashboardMetrics />
      </div>

      {/* Map */}
      <div className="flex-1 relative">
        <TrafficMap />
      </div>
    </div>
  );
}
```

---

## Completion Criteria

### Phase 6 Complete When:
- [ ] SSE stream consuming traffic-predictions topic
- [ ] Leaflet map displaying 207 sensors
- [ ] Color-coded markers (red/yellow/green)
- [ ] Interactive popups with prediction details
- [ ] Real-time metrics dashboard
- [ ] Map controls and filtering working
- [ ] Update latency < 5 seconds
- [ ] No UI errors or crashes
- [ ] Responsive design working

### Performance Targets
- **Latency**: < 5 seconds from prediction to dashboard
- **Frame Rate**: 60 FPS during updates
- **Load Time**: < 2 seconds initial load
- **Concurrent Users**: Support 10+ simultaneous viewers

---

## Next Steps
→ Proceed to **Task 7: Infrastructure & Operations**
