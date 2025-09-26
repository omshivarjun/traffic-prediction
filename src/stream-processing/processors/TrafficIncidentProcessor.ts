import { KafkaStreams, KStream } from 'kafka-streams';
import { BaseProcessor } from './BaseProcessor';

/**
 * Processor for traffic incidents
 * Consumes traffic incidents and enriches processed traffic aggregates
 */
export class TrafficIncidentProcessor extends BaseProcessor {
  /**
   * Build the processing topology for traffic incidents
   */
  protected async buildTopology(): Promise<void> {
    console.log('Building TrafficIncidentProcessor topology...');
    
    // Create consumer stream for traffic incidents
    const trafficIncidentStream = this.createConsumerStream('topic.input.traffic-incidents', 'traffic-incident-stream');
    
    // Create consumer stream for processed traffic aggregates
    const processedAggregatesStream = this.createConsumerStream('topic.output.processed-aggregates', 'processed-aggregates-consumer');
    
    // Create producer stream for enriched traffic aggregates
    const enrichedAggregatesStream = this.createProducerStream('topic.output.enriched-aggregates', 'enriched-aggregates-stream');
    
    // Create a state store for active incidents
    const incidentStore = this.kafkaStreams.getKStorage('incident-store');
    
    // Process traffic incidents and store them
    trafficIncidentStream
      .mapJSONConvenience() // Parse JSON
      .filter(incident => {
        // Filter out invalid incidents
        return incident && incident.value && incident.value.segment_id && incident.value.incident_id;
      })
      .map(incident => {
        const value = incident.value;
        const currentTime = Date.now();
        
        // Check if incident is active
        const isActive = (
          (!value.end_time || new Date(value.end_time).getTime() > currentTime) &&
          (!value.start_time || new Date(value.start_time).getTime() <= currentTime)
        );
        
        return {
          key: value.segment_id,
          value: {
            ...value,
            is_active: isActive
          }
        };
      })
      .tap(incident => {
        // Store incident in state store
        const segmentId = incident.key;
        const incidentId = incident.value.incident_id;
        
        // Get existing incidents for this segment
        let segmentIncidents = incidentStore.get(segmentId) || {};
        
        if (incident.value.is_active) {
          // Add or update active incident
          segmentIncidents[incidentId] = incident.value;
        } else {
          // Remove inactive incident
          delete segmentIncidents[incidentId];
        }
        
        // Update state store
        incidentStore.set(segmentId, segmentIncidents);
      });
    
    // Enrich processed traffic aggregates with incident information
    processedAggregatesStream
      .mapJSONConvenience() // Parse JSON
      .map(aggregate => {
        const segmentId = aggregate.key;
        
        // Get active incidents for this segment
        const segmentIncidents = incidentStore.get(segmentId) || {};
        const activeIncidents = Object.values(segmentIncidents);
        
        // Extract incident descriptions
        const incidentDescriptions = activeIncidents.map((incident: any) => {
          return `${incident.incident_type} (${incident.severity}): ${incident.description || 'No description'}`;
        });
        
        // Enrich aggregate with incident information
        return {
          key: segmentId,
          value: {
            ...aggregate.value,
            active_incidents: incidentDescriptions,
            has_incidents: incidentDescriptions.length > 0
          }
        };
      })
      // Send to enriched aggregates stream
      .to(enrichedAggregatesStream);
    
    console.log('TrafficIncidentProcessor topology built successfully');
  }
}