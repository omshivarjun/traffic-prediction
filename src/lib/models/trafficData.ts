/**
 * Data model for raw traffic events from sensors and other sources
 * Matches the Avro schema in schemas/traffic-event.avsc
 */
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

/**
 * Legacy interface maintained for backward compatibility
 * @deprecated Use TrafficEvent instead
 */
export interface TrafficData {
  id: string;
  timestamp: Date;
  location: {
    latitude: number;
    longitude: number;
    roadName?: string;
    city?: string;
  };
  volume: number; // Number of vehicles
  speed: number; // Average speed in km/h
  congestionLevel: 'low' | 'medium' | 'high';
  weatherCondition?: string;
  incidents?: Incident[];
}

/**
 * Enum for congestion levels
 */
export enum CongestionLevel {
  FREE_FLOW = 'FREE_FLOW',
  LIGHT = 'LIGHT',
  MODERATE = 'MODERATE',
  HEAVY = 'HEAVY',
  SEVERE = 'SEVERE',
  UNKNOWN = 'UNKNOWN'
}

/**
 * Data model for traffic incidents
 */
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

/**
 * Legacy interface maintained for backward compatibility
 * @deprecated Use TrafficIncident instead
 */
export interface Incident {
  id: string;
  type: 'accident' | 'roadwork' | 'closure' | 'event';
  description: string;
  startTime: Date;
  endTime?: Date;
  severity: 'low' | 'medium' | 'high';
}

/**
 * Data model for processed traffic aggregates
 * Matches the Avro schema in schemas/processed-traffic-aggregate.avsc
 */
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

/**
 * Data model for traffic predictions
 * Matches the Avro schema in schemas/traffic-prediction.avsc
 */
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

/**
 * Legacy interface maintained for backward compatibility
 * @deprecated Use the new TrafficPrediction interface instead
 */
export interface LegacyTrafficPrediction {
  id: string;
  locationId: string;
  predictedFor: Date;
  predictedVolume: number;
  predictedSpeed: number;
  predictedCongestionLevel: 'low' | 'medium' | 'high';
  confidence: number; // 0-1 value indicating prediction confidence
}