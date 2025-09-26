# Traffic Prediction Data Models

## Overview

This document describes the data models implemented for the Traffic Prediction system. These models align with the Avro schemas used for Kafka data streaming and provide a consistent data structure throughout the application.

## Data Models

### TrafficEvent

Represents raw traffic events from sensors and other sources. This model matches the Avro schema in `schemas/traffic-event.avsc`.

```typescript
export interface TrafficEvent {
  event_id: string;
  segment_id: string;
  timestamp: Date; // Stored as timestamp-millis in Avro
  speed?: number; // Average speed in km/h
  volume?: number; // Number of vehicles detected
  occupancy?: number; // Percentage of time sensor detected a vehicle (0-100)
  coordinates: {
    latitude: number;
    longitude: number;
  };
  source: 'SENSOR' | 'CAMERA' | 'PROBE' | 'INCIDENT_REPORT' | 'WEATHER_STATION';
  quality_score: number; // Data quality score between 0 and 1
  metadata?: Record<string, string>; // Additional metadata
}
```

### ProcessedTrafficAggregate

Represents aggregated traffic data over a time window. This model matches the Avro schema in `schemas/processed-traffic-aggregate.avsc`.

```typescript
export interface ProcessedTrafficAggregate {
  segment_id: string;
  window_start: Date; // Stored as timestamp-millis in Avro
  window_end: Date; // Stored as timestamp-millis in Avro
  avg_speed: number;
  avg_volume: number;
  avg_occupancy: number;
  congestion_level: CongestionLevel;
  event_count: number;
  processing_timestamp: Date; // Stored as timestamp-millis in Avro
  coordinates: {
    latitude: number;
    longitude: number;
  };
  active_incidents?: string[]; // Array of incident IDs
  metadata?: Record<string, string>; // Additional metadata
}
```

### TrafficPrediction

Represents a prediction of future traffic conditions. This model matches the Avro schema in `schemas/traffic-prediction.avsc`.

```typescript
export interface TrafficPrediction {
  prediction_id: string;
  segment_id: string;
  prediction_timestamp: Date; // When the prediction was made
  horizon_minutes: number; // How far into the future this prediction is for
  target_timestamp: Date; // The time being predicted for
  predicted_speed: number;
  predicted_volume: number;
  predicted_congestion_level: CongestionLevel;
  confidence_score: number; // 0-1 value indicating prediction confidence
  model_version: string;
  coordinates: {
    latitude: number;
    longitude: number;
  };
  feature_metadata?: Record<string, string>; // Metadata about features used
}
```

### TrafficIncident

Represents traffic incidents such as accidents, roadwork, closures, etc.

```typescript
export interface TrafficIncident {
  incident_id: string;
  segment_id: string;
  incident_type: 'ACCIDENT' | 'ROADWORK' | 'CLOSURE' | 'EVENT' | 'WEATHER' | 'OTHER';
  description: string;
  start_time: Date;
  end_time?: Date;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  status: 'ACTIVE' | 'CLEARED' | 'SCHEDULED';
  coordinates: {
    latitude: number;
    longitude: number;
  };
  impact_radius_meters?: number;
  reported_by: string;
  metadata?: Record<string, string>;
}
```

### CongestionLevel Enum

Enumerates the possible congestion levels for traffic segments.

```typescript
export enum CongestionLevel {
  FREE_FLOW = 'FREE_FLOW',
  LIGHT = 'LIGHT',
  MODERATE = 'MODERATE',
  HEAVY = 'HEAVY',
  SEVERE = 'SEVERE',
  UNKNOWN = 'UNKNOWN'
}
```

## Legacy Models

The following legacy models are maintained for backward compatibility:

- `TrafficData`: Replaced by `TrafficEvent`
- `Incident`: Replaced by `TrafficIncident`
- `LegacyTrafficPrediction`: Replaced by `TrafficPrediction`

## Utility Functions

The following utility functions have been implemented to work with these data models:

- `calculateAverageEventSpeed`: Calculate average speed from traffic events
- `calculateAverageOccupancy`: Calculate average occupancy from traffic events
- `determineCongestionLevel`: Determine congestion level based on speed, volume, and occupancy
- `generatePrediction`: Generate a traffic prediction from traffic events
- `createProcessedAggregate`: Create a processed traffic aggregate from raw events

## Service Methods

The `TrafficService` class has been updated to include methods for working with the new data models:

- `getTrafficEvents`: Get all traffic events
- `getTrafficEventsForSegment`: Get traffic events for a specific segment
- `getTrafficEventsForLocation`: Get traffic events for a specific location
- `generateTrafficPrediction`: Generate a traffic prediction for a segment
- `addTrafficEvent`: Add a new traffic event
- `getProcessedAggregates`: Get processed traffic aggregates for a segment

## Data Flow

1. Raw traffic data is ingested as `TrafficEvent` objects
2. Events are processed and aggregated into `ProcessedTrafficAggregate` objects
3. Predictions are generated as `TrafficPrediction` objects based on aggregates and events
4. `TrafficIncident` objects are created when incidents are detected or reported

## Avro Schema Alignment

The TypeScript interfaces are designed to align with the Avro schemas used for Kafka:

- Field names match exactly
- Data types are compatible (with TypeScript equivalents)
- Optional fields are marked as such
- Nested structures are preserved
- Enums are represented as TypeScript enums

This alignment ensures seamless data flow between Kafka and the application.