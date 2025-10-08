import { KafkaStreams, KStream } from 'kafka-streams';
import { BaseProcessor } from './BaseProcessor';

/**
 * Processor for traffic predictions
 * Consumes enriched traffic aggregates and produces traffic predictions
 */
export class TrafficPredictionProcessor extends BaseProcessor {
  /**
   * Build the processing topology for traffic predictions
   */
  protected async buildTopology(): Promise<void> {
    console.log('Building TrafficPredictionProcessor topology...');
    
    // Create consumer stream for processed traffic aggregates
    const enrichedAggregatesStream = this.createConsumerStream('topic.output.enriched-aggregates', 'processed-aggregates-consumer');
    
    // Create producer stream for traffic predictions
    const trafficPredictionsStream = this.createProducerStream('topic.output.predictions', 'traffic-predictions-stream');
    
    // Create producer stream for traffic alerts
    const trafficAlertsStream = this.createProducerStream('topic.output.alerts', 'traffic-alerts-stream');
    
    // Get prediction configuration
    const predictionHorizons = (this.config['prediction.horizons.minutes'] || '15,30,60').split(',').map(Number);
    const alertThreshold = parseFloat(this.config['alert.congestion.threshold'] || '0.8');
    
    // Process enriched traffic aggregates and generate predictions
    enrichedAggregatesStream
      .mapJSONConvenience() // Parse JSON
      .filter(aggregate => {
        // Filter out invalid aggregates
        return aggregate && aggregate.value && aggregate.value.segment_id;
      })
      .map(async aggregate => {
        const segmentId = aggregate.key;
        const value = aggregate.value;
        
        // Generate predictions for each horizon
        const predictions = [];
        
        for (const horizonMinutes of predictionHorizons) {
          try {
            // In a real implementation, this would call the ML model service
            // For now, we'll simulate predictions based on current data
            const prediction = await this.generatePrediction(value, horizonMinutes);
            predictions.push(prediction);
            
            // Check if prediction warrants an alert
            if (this.shouldGenerateAlert(prediction, value, alertThreshold)) {
              const alert = this.createAlert(prediction, value);
              
              // Send alert to alerts stream
              trafficAlertsStream.writeToStream({
                key: segmentId,
                value: alert
              });
            }
          } catch (error) {
            console.error(`Error generating prediction for segment ${segmentId}:`, error);
          }
        }
        
        // Return all predictions for this segment
        return {
          key: segmentId,
          value: predictions
        };
      })
      // Send to predictions stream
      .asyncMap(async (result) => {
        // Wait for the async map operation to complete
        const resolvedResult = await result;
        return resolvedResult;
      })
      .to(trafficPredictionsStream);
    
    console.log('TrafficPredictionProcessor topology built successfully');
  }
  
  /**
   * Generate a traffic prediction for a given horizon
   * @param aggregate Current traffic aggregate
   * @param horizonMinutes Prediction horizon in minutes
   * @returns Traffic prediction
   */
  private async generatePrediction(aggregate: any, horizonMinutes: number): Promise<any> {
    // In a real implementation, this would call the ML model service
    // For now, we'll simulate a prediction based on current data
    
    // Simple prediction logic (in reality, this would use the ML model)
    const currentSpeed = aggregate.average_speed || 60;
    const hasIncidents = aggregate.has_incidents || false;
    
    // Simulate speed decrease based on horizon and incidents
    let predictedSpeed = currentSpeed;
    if (hasIncidents) {
      // More significant decrease if there are incidents
      predictedSpeed = Math.max(5, currentSpeed - (horizonMinutes / 10) * 5);
    } else {
      // Slight decrease over time
      predictedSpeed = Math.max(20, currentSpeed - (horizonMinutes / 30) * 5);
    }
    
    // Determine congestion level based on predicted speed
    let predictedCongestionLevel = 'UNKNOWN';
    if (predictedSpeed >= 80) {
      predictedCongestionLevel = 'FREE_FLOW';
    } else if (predictedSpeed >= 60) {
      predictedCongestionLevel = 'LIGHT';
    } else if (predictedSpeed >= 40) {
      predictedCongestionLevel = 'MODERATE';
    } else if (predictedSpeed >= 20) {
      predictedCongestionLevel = 'HEAVY';
    } else {
      predictedCongestionLevel = 'SEVERE';
    }
    
    // Create prediction object
    return {
      prediction_id: `${aggregate.segment_id}-${Date.now()}-${horizonMinutes}`,
      segment_id: aggregate.segment_id,
      timestamp: Date.now(),
      horizon_minutes: horizonMinutes,
      predicted_speed: predictedSpeed,
      predicted_volume: aggregate.average_volume, // Simple assumption for demo
      predicted_congestion_level: predictedCongestionLevel,
      confidence_score: 0.8, // Fixed value for demo
      model_version: '1.0.0', // Fixed value for demo
      coordinates: aggregate.coordinates,
      feature_metadata: {
        current_speed: aggregate.average_speed?.toString() || 'unknown',
        current_congestion: aggregate.congestion_level || 'UNKNOWN',
        has_incidents: hasIncidents.toString()
      }
    };
  }
  
  /**
   * Determine if an alert should be generated based on the prediction
   * @param prediction Traffic prediction
   * @param currentAggregate Current traffic aggregate
   * @param threshold Alert threshold
   * @returns Whether an alert should be generated
   */
  private shouldGenerateAlert(prediction: any, currentAggregate: any, threshold: number): boolean {
    // Generate alert if predicted congestion is severe or heavy
    // and current congestion is not already severe or heavy
    const severeCongestionsLevels = ['SEVERE', 'HEAVY'];
    
    const isPredictedCongestionSevere = severeCongestionsLevels.includes(prediction.predicted_congestion_level);
    const isCurrentCongestionSevere = severeCongestionsLevels.includes(currentAggregate.congestion_level);
    
    return isPredictedCongestionSevere && !isCurrentCongestionSevere;
  }
  
  /**
   * Create a traffic alert based on a prediction
   * @param prediction Traffic prediction
   * @param currentAggregate Current traffic aggregate
   * @returns Traffic alert
   */
  private createAlert(prediction: any, currentAggregate: any): any {
    return {
      alert_id: `alert-${prediction.prediction_id}`,
      segment_id: prediction.segment_id,
      timestamp: Date.now(),
      alert_type: 'CONGESTION_PREDICTION',
      severity: prediction.predicted_congestion_level === 'SEVERE' ? 'HIGH' : 'MEDIUM',
      message: `Predicted ${prediction.predicted_congestion_level} congestion in ${prediction.horizon_minutes} minutes`,
      current_speed: currentAggregate.average_speed,
      predicted_speed: prediction.predicted_speed,
      horizon_minutes: prediction.horizon_minutes,
      coordinates: prediction.coordinates,
      active_incidents: currentAggregate.active_incidents || []
    };
  }
}