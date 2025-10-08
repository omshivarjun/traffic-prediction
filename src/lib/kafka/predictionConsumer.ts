/**
 * Kafka Consumer for ML Predictions
 * Consumes predictions from the 'traffic-predictions' topic
 * and makes them available to the frontend via WebSocket
 */

import { Kafka, Consumer, EachMessagePayload } from 'kafkajs';

export interface TrafficPrediction {
  segment_id: string;
  timestamp: number;
  current_speed: number;
  predicted_speed: number;
  current_volume: number;
  prediction_time: string;
  speed_diff: number;
  category: 'free_flow' | 'moderate_traffic' | 'heavy_traffic' | 'severe_congestion';
  coordinates?: {
    latitude: number;
    longitude: number;
  };
}

class PredictionConsumer {
  private kafka: Kafka;
  private consumer: Consumer | null = null;
  private isConnected = false;
  private listeners: Set<(prediction: TrafficPrediction) => void> = new Set();
  private latestPredictions: Map<string, TrafficPrediction> = new Map();

  constructor() {
    // Use localhost for external access (Next.js runs outside Docker)
    // Use kafka-broker1 for internal Docker services
    const brokers = process.env.KAFKA_BROKERS?.split(',') || ['localhost:9092'];
    
    this.kafka = new Kafka({
      clientId: 'nextjs-prediction-consumer',
      brokers,
      connectionTimeout: 10000,
      requestTimeout: 30000,
      retry: {
        initialRetryTime: 300,
        retries: 8,
        maxRetryTime: 30000,
        multiplier: 2,
      },
    });
  }

  /**
   * Start consuming predictions from Kafka
   */
  async start(): Promise<void> {
    if (this.isConnected) {
      console.log('⚠️ Prediction consumer already started');
      return;
    }

    // Prevent multiple simultaneous start attempts
    if (this.consumer) {
      console.log('⚠️ Consumer already exists, waiting for connection...');
      // Wait up to 10 seconds for existing consumer to connect
      for (let i = 0; i < 20; i++) {
        if (this.isConnected) {
          return;
        }
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      throw new Error('Consumer connection timeout');
    }

    try {
      this.consumer = this.kafka.consumer({
        groupId: 'nextjs-prediction-consumer-group',
        sessionTimeout: 60000,
        heartbeatInterval: 5000,
        rebalanceTimeout: 60000,
        retry: {
          retries: 5,
          initialRetryTime: 300,
        },
      });

      console.log('🔌 Connecting to Kafka...');
      await this.consumer.connect();
      console.log('✅ Connected to Kafka for predictions');

      // Wait a moment after connect to ensure broker is ready
      await new Promise(resolve => setTimeout(resolve, 1000));

      console.log('📝 Subscribing to traffic-predictions topic...');
      await this.consumer.subscribe({
        topic: 'traffic-predictions',
        fromBeginning: false,
      });
      console.log('✅ Subscribed to topic');

      await this.consumer.run({
        eachMessage: async (payload: EachMessagePayload) => {
          await this.handleMessage(payload);
        },
      });

      this.isConnected = true;
      console.log('🚀 Prediction consumer started successfully');
    } catch (error) {
      console.error('❌ Error starting prediction consumer:', error);
      // Clean up failed consumer
      if (this.consumer) {
        try {
          await this.consumer.disconnect();
        } catch (e) {
          // Ignore disconnect errors
        }
        this.consumer = null;
      }
      throw error;
    }
  }

  /**
   * Handle incoming Kafka message
   */
  private async handleMessage({ message }: EachMessagePayload): Promise<void> {
    try {
      if (!message.value) {
        console.warn('⚠️ Received null message value');
        return;
      }

      const predictionData = JSON.parse(message.value.toString());
      const prediction: TrafficPrediction = {
        segment_id: predictionData.segment_id,
        timestamp: predictionData.timestamp,
        current_speed: predictionData.current_speed,
        predicted_speed: predictionData.predicted_speed,
        current_volume: predictionData.current_volume,
        prediction_time: predictionData.prediction_time,
        speed_diff: predictionData.speed_diff,
        category: predictionData.category,
        coordinates: predictionData.coordinates, // ✅ ADD COORDINATES FROM KAFKA MESSAGE
      };

      // Store latest prediction for this segment
      this.latestPredictions.set(prediction.segment_id, prediction);

      // Notify all listeners
      this.listeners.forEach((listener) => {
        try {
          listener(prediction);
        } catch (error) {
          console.error('❌ Error in prediction listener:', error);
        }
      });

      console.log(
        `📊 Prediction: ${prediction.segment_id} - Current: ${prediction.current_speed.toFixed(1)} mph → Predicted: ${prediction.predicted_speed.toFixed(1)} mph [${prediction.category}]`
      );
    } catch (error) {
      console.error('❌ Error processing prediction message:', error);
    }
  }

  /**
   * Subscribe to prediction updates
   */
  onPrediction(callback: (prediction: TrafficPrediction) => void): () => void {
    this.listeners.add(callback);
    
    // Return unsubscribe function
    return () => {
      this.listeners.delete(callback);
    };
  }

  /**
   * Get latest predictions for all segments
   */
  getLatestPredictions(): Map<string, TrafficPrediction> {
    return new Map(this.latestPredictions);
  }

  /**
   * Get latest prediction for a specific segment
   */
  getLatestPrediction(segmentId: string): TrafficPrediction | undefined {
    return this.latestPredictions.get(segmentId);
  }

  /**
   * Get all predictions as array
   */
  getAllPredictions(): TrafficPrediction[] {
    return Array.from(this.latestPredictions.values());
  }

  /**
   * Get prediction statistics
   */
  getStats() {
    const predictions = Array.from(this.latestPredictions.values());
    const categories = {
      free_flow: 0,
      moderate_traffic: 0,
      heavy_traffic: 0,
      severe_congestion: 0,
    };

    predictions.forEach((pred) => {
      categories[pred.category]++;
    });

    return {
      total: predictions.length,
      categories,
      avgSpeedDiff:
        predictions.length > 0
          ? predictions.reduce((sum, p) => sum + p.speed_diff, 0) / predictions.length
          : 0,
    };
  }

  /**
   * Stop consuming and disconnect
   */
  async stop(): Promise<void> {
    if (this.consumer) {
      try {
        await this.consumer.disconnect();
        this.isConnected = false;
        this.listeners.clear();
        console.log('✅ Prediction consumer stopped');
      } catch (error) {
        console.error('❌ Error stopping prediction consumer:', error);
        throw error;
      }
    }
  }

  /**
   * Check if consumer is connected
   */
  isRunning(): boolean {
    return this.isConnected;
  }
}

// Singleton instance
let predictionConsumerInstance: PredictionConsumer | null = null;

/**
 * Get or create the singleton prediction consumer instance
 */
export function getPredictionConsumer(): PredictionConsumer {
  if (!predictionConsumerInstance) {
    predictionConsumerInstance = new PredictionConsumer();
  }
  return predictionConsumerInstance;
}

export default PredictionConsumer;
