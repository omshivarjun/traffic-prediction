/**
 * Service for handling traffic data operations
 */

import { 
  TrafficData, 
  TrafficEvent, 
  ProcessedTrafficAggregate, 
  TrafficPrediction, 
  TrafficIncident,
  LegacyTrafficPrediction,
  CongestionLevel 
} from '../models/trafficData';
import { predictTraffic } from '../utils/predictionUtils';

// Mock data for development purposes - Legacy format
const mockTrafficData: TrafficData[] = [
  {
    id: '1',
    timestamp: new Date('2023-08-09T08:00:00'),
    location: {
      latitude: 40.7128,
      longitude: -74.0060,
      roadName: 'Broadway',
      city: 'New York'
    },
    volume: 1200,
    speed: 35,
    congestionLevel: 'medium',
    weatherCondition: 'clear'
  },
  {
    id: '2',
    timestamp: new Date('2023-08-09T09:00:00'),
    location: {
      latitude: 40.7128,
      longitude: -74.0060,
      roadName: 'Broadway',
      city: 'New York'
    },
    volume: 1500,
    speed: 25,
    congestionLevel: 'high',
    weatherCondition: 'clear'
  },
  {
    id: '3',
    timestamp: new Date('2023-08-09T10:00:00'),
    location: {
      latitude: 40.7128,
      longitude: -74.0060,
      roadName: 'Broadway',
      city: 'New York'
    },
    volume: 1300,
    speed: 30,
    congestionLevel: 'medium',
    weatherCondition: 'clear'
  },
];

// Mock data using new models
const mockTrafficEvents: TrafficEvent[] = [
  {
    event_id: 'event-1',
    segment_id: 'segment-101',
    timestamp: new Date(),
    speed: 35,
    volume: 1200,
    occupancy: 65,
    coordinates: {
      latitude: 40.7128,
      longitude: -74.0060
    },
    source: 'SENSOR',
    quality_score: 0.95,
    metadata: {
      roadName: 'Broadway',
      city: 'New York',
      weatherCondition: 'clear'
    }
  },
  {
    event_id: 'event-2',
    segment_id: 'segment-102',
    timestamp: new Date(),
    speed: 25,
    volume: 1500,
    occupancy: 80,
    coordinates: {
      latitude: 40.7128,
      longitude: -74.0060
    },
    source: 'CAMERA',
    quality_score: 0.88,
    metadata: {
      roadName: 'Broadway',
      city: 'New York',
      weatherCondition: 'clear'
    }
  }
];

export class TrafficService {
  /**
   * Get traffic data for a specific location (legacy method)
   */
  async getTrafficData(latitude: number, longitude: number): Promise<TrafficData[]> {
    // In a real application, this would fetch from an API or database
    return mockTrafficData.filter(data => 
      data.location.latitude.toFixed(4) === latitude.toFixed(4) &&
      data.location.longitude.toFixed(4) === longitude.toFixed(4)
    );
  }

  /**
   * Get traffic events for a specific location using new data model
   */
  async getTrafficEventsForLocation(latitude: number, longitude: number, radiusKm: number = 0.5): Promise<TrafficEvent[]> {
    // Simple distance calculation (not accounting for Earth's curvature for this mock)
    return mockTrafficEvents.filter(event => {
      const latDiff = Math.abs(event.coordinates.latitude - latitude);
      const lonDiff = Math.abs(event.coordinates.longitude - longitude);
      // Rough approximation: 0.01 degrees is about 1.1km at the equator
      return latDiff < (radiusKm / 110) && lonDiff < (radiusKm / 110);
    });
  }

  /**
   * Get all available traffic data (legacy method)
   */
  async getAllTrafficData(): Promise<TrafficData[]> {
    return mockTrafficData;
  }

  /**
   * Get all traffic events using new data model
   */
  async getAllTrafficEvents(): Promise<TrafficEvent[]> {
    return mockTrafficEvents;
  }

  /**
   * Get traffic events for a specific segment
   */
  async getTrafficEventsForSegment(segmentId: string): Promise<TrafficEvent[]> {
    return mockTrafficEvents.filter(event => event.segment_id === segmentId);
  }

  /**
   * Predict traffic for a specific location and time (legacy method)
   */
  async predictTrafficForLocation(
    latitude: number, 
    longitude: number, 
    targetDate: Date
  ): Promise<TrafficPrediction> {
    const locationId = `${latitude.toFixed(4)},${longitude.toFixed(4)}`;
    const historicalData = await this.getTrafficData(latitude, longitude);
    // Use legacy predictor, then adapt to new model
    const legacy = predictTraffic(historicalData, locationId, targetDate);

    // Map legacy congestion string to new enum
    const toEnum = (lvl: 'low' | 'medium' | 'high'): CongestionLevel => {
      switch (lvl) {
        case 'low': return CongestionLevel.LIGHT;
        case 'medium': return CongestionLevel.MODERATE;
        case 'high': return CongestionLevel.HEAVY;
        default: return CongestionLevel.UNKNOWN;
      }
    };

    const now = new Date();
    const horizonMinutes = Math.max(0, Math.round((targetDate.getTime() - now.getTime()) / 60000));

    const prediction: TrafficPrediction = {
      prediction_id: `legacy-bridge-${Date.now()}`,
      segment_id: `segment:${locationId}`,
      prediction_timestamp: now,
      horizon_minutes: horizonMinutes,
      target_timestamp: targetDate,
      predicted_speed: legacy.predictedSpeed,
      predicted_volume: legacy.predictedVolume,
      predicted_congestion_level: toEnum(legacy.predictedCongestionLevel),
      confidence_score: legacy.confidence,
      model_version: 'legacy-bridge-1.0.0',
      coordinates: {
        latitude,
        longitude,
      },
      feature_metadata: {
        source: 'legacy_predictTraffic',
        location_id: legacy.locationId,
      },
    };

    return prediction;
  }

  /**
   * Generate traffic prediction using new data model
   */
  async generateTrafficPrediction(segmentId: string, horizonMinutes: number): Promise<TrafficPrediction> {
    const now = new Date();
    const targetTime = new Date(now.getTime() + horizonMinutes * 60 * 1000);
    
    // Find a matching event to base the prediction on
    const matchingEvent = mockTrafficEvents.find(event => event.segment_id === segmentId);
    
    // Create a prediction based on the event or default values
    const prediction: TrafficPrediction = {
      prediction_id: `prediction-${Date.now()}`,
      segment_id: segmentId,
      prediction_timestamp: now,
      horizon_minutes: horizonMinutes,
      target_timestamp: targetTime,
      predicted_speed: matchingEvent?.speed || 40,
      predicted_volume: matchingEvent?.volume || 1000,
      predicted_congestion_level: matchingEvent?.speed && matchingEvent.speed < 30 ? 
        CongestionLevel.HEAVY : CongestionLevel.MODERATE,
      confidence_score: 0.85,
      model_version: '1.0.0',
      coordinates: matchingEvent?.coordinates || {
        latitude: 40.7128,
        longitude: -74.0060
      },
      feature_metadata: {
        model_type: 'time_series',
        features_used: 'speed,volume,time_of_day,day_of_week'
      }
    };
    
    return prediction;
  }

  /**
   * Add new traffic data point (legacy method)
   */
  async addTrafficData(data: Omit<TrafficData, 'id'>): Promise<TrafficData> {
    const newData: TrafficData = {
      ...data,
      id: `traffic-${Date.now()}`
    };
    
    // In a real application, this would save to a database
    mockTrafficData.push(newData);
    
    return newData;
  }

  /**
   * Add a new traffic event using new data model
   */
  async addTrafficEvent(newEvent: Omit<TrafficEvent, 'event_id'>): Promise<TrafficEvent> {
    const event: TrafficEvent = {
      ...newEvent,
      event_id: `event-${Date.now()}`
    };
    
    // In a real app, this would publish to Kafka
    mockTrafficEvents.push(event);
    
    return event;
  }

  /**
   * Get processed traffic aggregates for a segment
   */
  async getProcessedAggregates(segmentId: string, startTime: Date, endTime: Date): Promise<ProcessedTrafficAggregate[]> {
    // In a real app, this would fetch from a database or cache
    const mockAggregate: ProcessedTrafficAggregate = {
      segment_id: segmentId,
      window_start: startTime,
      window_end: endTime,
      avg_speed: 42,
      avg_volume: 950,
      avg_occupancy: 55,
      congestion_level: CongestionLevel.MODERATE,
      event_count: 120,
      processing_timestamp: new Date(),
      coordinates: mockTrafficEvents.find(e => e.segment_id === segmentId)?.coordinates || {
        latitude: 40.7128,
        longitude: -74.0060
      },
      active_incidents: [],
      metadata: {
        processor_version: '1.0.0'
      }
    };
    
    return [mockAggregate];
  }
}

// Export a singleton instance
export const trafficService = new TrafficService();