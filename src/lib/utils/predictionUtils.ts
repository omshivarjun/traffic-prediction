/**
 * Utility functions for traffic prediction algorithms
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

/**
 * Calculate the average speed for a given set of traffic data points (legacy)
 */
export function calculateAverageSpeed(dataPoints: TrafficData[]): number {
  if (dataPoints.length === 0) return 0;
  
  const sum = dataPoints.reduce((total, point) => total + point.speed, 0);
  return sum / dataPoints.length;
}

/**
 * Calculate the average speed for a given set of traffic events
 */
export function calculateAverageEventSpeed(events: TrafficEvent[]): number {
  const validEvents = events.filter(event => event.speed !== undefined);
  if (validEvents.length === 0) return 0;
  
  const sum = validEvents.reduce((total, event) => total + (event.speed || 0), 0);
  return sum / validEvents.length;
}

/**
 * Calculate the average occupancy for a given set of traffic events
 */
export function calculateAverageOccupancy(events: TrafficEvent[]): number {
  const validEvents = events.filter(event => event.occupancy !== undefined);
  if (validEvents.length === 0) return 0;
  
  const sum = validEvents.reduce((total, event) => total + (event.occupancy || 0), 0);
  return sum / validEvents.length;
}

/**
 * Calculate the congestion level based on volume and speed (legacy)
 */
export function calculateCongestionLevel(volume: number, speed: number): 'low' | 'medium' | 'high' {
  // Simple algorithm - can be enhanced with more sophisticated logic
  if (speed > 50 && volume < 1000) return 'low';
  if (speed > 30 || volume < 2000) return 'medium';
  return 'high';
}

/**
 * Calculate the congestion level enum based on volume, speed, and occupancy
 */
export function determineCongestionLevel(
  speed?: number, 
  volume?: number, 
  occupancy?: number
): CongestionLevel {
  // If we don't have any data, return unknown
  if (speed === undefined && volume === undefined && occupancy === undefined) {
    return CongestionLevel.UNKNOWN;
  }
  
  // Prioritize occupancy if available as it's often the most reliable indicator
  if (occupancy !== undefined) {
    if (occupancy < 20) return CongestionLevel.FREE_FLOW;
    if (occupancy < 40) return CongestionLevel.LIGHT;
    if (occupancy < 60) return CongestionLevel.MODERATE;
    if (occupancy < 80) return CongestionLevel.HEAVY;
    return CongestionLevel.SEVERE;
  }
  
  // Fall back to speed and volume
  if (speed !== undefined) {
    if (speed > 60) return CongestionLevel.FREE_FLOW;
    if (speed > 45) return CongestionLevel.LIGHT;
    if (speed > 30) return CongestionLevel.MODERATE;
    if (speed > 15) return CongestionLevel.HEAVY;
    return CongestionLevel.SEVERE;
  }
  
  // Last resort, use volume if that's all we have
  if (volume !== undefined) {
    if (volume < 500) return CongestionLevel.FREE_FLOW;
    if (volume < 1000) return CongestionLevel.LIGHT;
    if (volume < 1500) return CongestionLevel.MODERATE;
    if (volume < 2000) return CongestionLevel.HEAVY;
    return CongestionLevel.SEVERE;
  }
  
  return CongestionLevel.UNKNOWN;
}

/**
 * Predict future traffic conditions based on historical data (legacy)
 * This is a simple implementation that can be replaced with more advanced ML algorithms
 */
export function predictTraffic(
  historicalData: TrafficData[], 
  locationId: string, 
  targetDate: Date
): LegacyTrafficPrediction {
  // Simple prediction based on averages of historical data
  // In a real implementation, this would use time series analysis or ML models
  
  const relevantData = historicalData.filter(data => 
    data.location.latitude.toFixed(4) === historicalData[0].location.latitude.toFixed(4) &&
    data.location.longitude.toFixed(4) === historicalData[0].location.longitude.toFixed(4)
  );
  
  const avgVolume = relevantData.reduce((sum, data) => sum + data.volume, 0) / relevantData.length;
  const avgSpeed = calculateAverageSpeed(relevantData);
  const congestionLevel = calculateCongestionLevel(avgVolume, avgSpeed);
  
  return {
    id: `pred-${Date.now()}`,
    locationId,
    predictedFor: targetDate,
    predictedVolume: avgVolume,
    predictedSpeed: avgSpeed,
    predictedCongestionLevel: congestionLevel,
    confidence: 0.7, // Placeholder confidence value
  };
}

/**
 * Generate a traffic prediction using the new data model
 */
export function generatePrediction(
  events: TrafficEvent[],
  segmentId: string,
  horizonMinutes: number
): TrafficPrediction {
  const now = new Date();
  const targetTime = new Date(now.getTime() + horizonMinutes * 60 * 1000);
  
  // Filter events for the specific segment
  const segmentEvents = events.filter(event => event.segment_id === segmentId);
  
  // If no events for this segment, return a default prediction
  if (segmentEvents.length === 0) {
    return {
      prediction_id: `pred-${Date.now()}`,
      segment_id: segmentId,
      prediction_timestamp: now,
      horizon_minutes: horizonMinutes,
      target_timestamp: targetTime,
      predicted_speed: 40, // Default values
      predicted_volume: 1000,
      predicted_congestion_level: CongestionLevel.MODERATE,
      confidence_score: 0.5, // Lower confidence due to lack of data
      model_version: '1.0.0',
      coordinates: {
        latitude: 0, // Default coordinates
        longitude: 0
      }
    };
  }
  
  // Calculate averages from segment events
  const avgSpeed = calculateAverageEventSpeed(segmentEvents);
  const avgVolume = segmentEvents.reduce((sum, event) => sum + (event.volume || 0), 0) / 
    segmentEvents.filter(event => event.volume !== undefined).length || 1000;
  const avgOccupancy = calculateAverageOccupancy(segmentEvents);
  
  // Determine congestion level
  const congestionLevel = determineCongestionLevel(avgSpeed, avgVolume, avgOccupancy);
  
  // Use coordinates from the most recent event
  const mostRecentEvent = segmentEvents.reduce((latest, event) => 
    event.timestamp > latest.timestamp ? event : latest, segmentEvents[0]);
  
  return {
    prediction_id: `pred-${Date.now()}`,
    segment_id: segmentId,
    prediction_timestamp: now,
    horizon_minutes: horizonMinutes,
    target_timestamp: targetTime,
    predicted_speed: avgSpeed,
    predicted_volume: avgVolume,
    predicted_congestion_level: congestionLevel,
    confidence_score: 0.7 + (segmentEvents.length > 10 ? 0.2 : 0), // Higher confidence with more data
    model_version: '1.0.0',
    coordinates: mostRecentEvent.coordinates,
    feature_metadata: {
      event_count: segmentEvents.length.toString(),
      time_of_day: targetTime.getHours().toString(),
      day_of_week: targetTime.getDay().toString()
    }
  };
}

/**
 * Calculate the impact of weather conditions on traffic
 */
export function calculateWeatherImpact(weatherCondition: string): number {
  // Impact factor (1.0 = no impact, higher values = more impact)
  switch(weatherCondition.toLowerCase()) {
    case 'rain': return 1.3;
    case 'snow': return 1.7;
    case 'fog': return 1.5;
    case 'storm': return 2.0;
    default: return 1.0; // Clear weather or unknown
  }
}

/**
 * Create a processed traffic aggregate from raw events
 */
export function createProcessedAggregate(
  events: TrafficEvent[],
  windowStartTime: Date,
  windowEndTime: Date,
  activeIncidents: string[] = []
): ProcessedTrafficAggregate {
  // Ensure we have events and they're all for the same segment
  if (events.length === 0) {
    throw new Error('Cannot create aggregate: no events provided');
  }
  
  const segmentId = events[0].segment_id;
  if (!events.every(event => event.segment_id === segmentId)) {
    throw new Error('Cannot create aggregate: events are for different segments');
  }
  
  // Calculate aggregate metrics
  const avgSpeed = calculateAverageEventSpeed(events);
  const avgVolume = events.reduce((sum, event) => sum + (event.volume || 0), 0) / 
    events.filter(event => event.volume !== undefined).length || 0;
  const avgOccupancy = calculateAverageOccupancy(events);
  
  // Determine congestion level
  const congestionLevel = determineCongestionLevel(avgSpeed, avgVolume, avgOccupancy);
  
  // Use coordinates from the most recent event
  const mostRecentEvent = events.reduce((latest, event) => 
    event.timestamp > latest.timestamp ? event : latest, events[0]);
  
  return {
    segment_id: segmentId,
    window_start: windowStartTime,
    window_end: windowEndTime,
    avg_speed: avgSpeed,
    avg_volume: avgVolume,
    avg_occupancy: avgOccupancy,
    congestion_level: congestionLevel,
    event_count: events.length,
    processing_timestamp: new Date(),
    coordinates: mostRecentEvent.coordinates,
    active_incidents: activeIncidents,
    metadata: {
      processor_version: '1.0.0',
      source_distribution: calculateSourceDistribution(events)
    }
  };
}

/**
 * Calculate the distribution of event sources
 */
function calculateSourceDistribution(events: TrafficEvent[]): string {
  const sources: Record<string, number> = {};
  
  events.forEach(event => {
    sources[event.source] = (sources[event.source] || 0) + 1;
  });
  
  return Object.entries(sources)
    .map(([source, count]) => `${source}:${count}`)
    .join(',');
}