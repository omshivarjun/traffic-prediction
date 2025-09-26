import { KafkaStreams, KStream } from 'kafka-streams';
import { BaseProcessor } from './BaseProcessor';

/**
 * Processor for traffic events
 * Consumes raw traffic events and produces processed traffic aggregates
 */
export class TrafficEventProcessor extends BaseProcessor {
  /**
   * Build the processing topology for traffic events
   */
  protected async buildTopology(): Promise<void> {
    console.log('Building TrafficEventProcessor topology...');
    
    // Create consumer stream for traffic events
    const trafficEventStream = this.createConsumerStream('topic.input.traffic-events', 'traffic-event-stream');
    
    // Create producer stream for processed traffic aggregates
    const processedAggregatesStream = this.createProducerStream('topic.output.processed-aggregates', 'processed-aggregates-stream');
    
    // Get window configuration
    const windowSizeMinutes = parseInt(this.config['window.size.minutes'] || '5', 10);
    const windowAdvanceSeconds = parseInt(this.config['window.advance.seconds'] || '60', 10);
    
    // Process traffic events
    trafficEventStream
      .mapJSONConvenience() // Parse JSON
      .filter(event => {
        // Filter out invalid events
        return event && event.value && event.value.segment_id && event.value.timestamp;
      })
      .map(event => {
        // Transform event for processing
        const value = event.value;
        return {
          key: value.segment_id,
          value: {
            segment_id: value.segment_id,
            timestamp: value.timestamp,
            speed: value.speed || null,
            volume: value.volume || null,
            occupancy: value.occupancy || null,
            coordinates: value.coordinates,
            source: value.source,
            quality_score: value.quality_score,
            metadata: value.metadata || {}
          }
        };
      })
      // Group by segment_id for windowed aggregation
      .groupByKey()
      // Apply tumbling window
      .window(KStream.windows.tumbling(windowSizeMinutes * 60 * 1000), 'traffic-window')
      // Aggregate events in the window
      .reduce((agg, next) => {
        if (!agg) {
          return {
            segment_id: next.value.segment_id,
            events: [next.value],
            count: 1
          };
        }
        
        return {
          segment_id: next.value.segment_id,
          events: [...agg.events, next.value],
          count: agg.count + 1
        };
      }, 'traffic-aggregation')
      // Process the aggregated data
      .map(windowedAgg => {
        const { segment_id, events, count } = windowedAgg.value;
        const windowStart = windowedAgg.window.start;
        const windowEnd = windowedAgg.window.end;
        
        // Calculate averages
        let totalSpeed = 0;
        let speedCount = 0;
        let totalVolume = 0;
        let volumeCount = 0;
        let totalOccupancy = 0;
        let occupancyCount = 0;
        let coordinates = null;
        
        // Process each event in the window
        events.forEach(event => {
          if (event.speed !== null && event.speed !== undefined) {
            totalSpeed += event.speed;
            speedCount++;
          }
          
          if (event.volume !== null && event.volume !== undefined) {
            totalVolume += event.volume;
            volumeCount++;
          }
          
          if (event.occupancy !== null && event.occupancy !== undefined) {
            totalOccupancy += event.occupancy;
            occupancyCount++;
          }
          
          // Use the most recent coordinates
          if (event.coordinates) {
            coordinates = event.coordinates;
          }
        });
        
        // Calculate averages
        const averageSpeed = speedCount > 0 ? totalSpeed / speedCount : null;
        const averageVolume = volumeCount > 0 ? totalVolume / volumeCount : null;
        const averageOccupancy = occupancyCount > 0 ? totalOccupancy / occupancyCount : null;
        
        // Determine congestion level based on average speed
        let congestionLevel = 'UNKNOWN';
        if (averageSpeed !== null) {
          if (averageSpeed >= 80) {
            congestionLevel = 'FREE_FLOW';
          } else if (averageSpeed >= 60) {
            congestionLevel = 'LIGHT';
          } else if (averageSpeed >= 40) {
            congestionLevel = 'MODERATE';
          } else if (averageSpeed >= 20) {
            congestionLevel = 'HEAVY';
          } else {
            congestionLevel = 'SEVERE';
          }
        }
        
        // Create processed aggregate
        return {
          key: segment_id,
          value: {
            segment_id,
            window_start: windowStart,
            window_end: windowEnd,
            average_speed: averageSpeed,
            average_volume: averageVolume,
            average_occupancy: averageOccupancy,
            congestion_level: congestionLevel,
            event_count: count,
            processing_timestamp: Date.now(),
            coordinates,
            active_incidents: [], // Will be populated by the incident processor
            metadata: {}
          }
        };
      })
      // Send to processed aggregates stream
      .to(processedAggregatesStream);
    
    console.log('TrafficEventProcessor topology built successfully');
  }
}