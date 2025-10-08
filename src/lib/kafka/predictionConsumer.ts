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
}

class PredictionConsumer {
  private kafka: Kafka;
  private consumer: Consumer | null = null;
  private isConnected = false;
  private isConnecting = false;
  private connectionPromise: Promise<void> | null = null;
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
      console.log('✅ Consumer already connected and running');
      return;
    }

    // If another connection is in progress, wait for it
    if (this.isConnecting && this.connectionPromise) {
      console.log('⏳ Waiting for existing connection attempt...');
      await this.connectionPromise;
      return;
    }

    // Set connecting flag and create promise
    this.isConnecting = true;
    this.connectionPromise = this._doConnect();
    
    try {
      await this.connectionPromise;
    } finally {
      this.connectionPromise = null;
    }
  }

  /**
   * Internal method to perform the actual connection
   */
  private async _doConnect(): Promise<void> {
    const fs = require('fs');
    const logPath = 'c:\\traffic-prediction\\consumer-debug.log';
    const log = (msg: string) => {
      const timestamp = new Date().toISOString();
      fs.appendFileSync(logPath, `[${timestamp}] ${msg}\n`);
      console.log(msg);
    };
    
    try {
      log('🔌 Starting _doConnect...');
      
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

      log('🔌 Connecting to Kafka...');
      await this.consumer.connect();
      log('✅ Connected to Kafka for predictions');

      // Add error listeners
      this.consumer.on('consumer.disconnect', () => {
        log('⚠️  Consumer disconnected from Kafka');
        this.isConnected = false;
      });

      this.consumer.on('consumer.crash', (error: any) => {
        log(`❌ Consumer crashed: ${error.error?.message || 'Unknown error'}`);
        log(`Stack: ${error.error?.stack || 'No stack'}`);
        this.isConnected = false;
      });

      this.consumer.on('consumer.group_join', (payload: any) => {
        log(`✅ Joined consumer group: ${JSON.stringify(payload)}`);
      });

      this.consumer.on('consumer.connect', () => {
        log('✅ Consumer connected event fired');
      });

      log('📝 Subscribing to traffic-predictions topic...');
      await this.consumer.subscribe({
        topic: 'traffic-predictions',
        fromBeginning: true,  // Read from beginning to get existing predictions
      });
      log('✅ Subscribed to topic');

      // Set connected state BEFORE run() since run() never returns (it keeps running)
      this.isConnected = true;
      this.isConnecting = false;
      log('🚀 Prediction consumer started successfully');

      // Start consuming messages (this runs indefinitely)
      log('▶️  Starting consumer.run()...');
      await this.consumer.run({
        eachMessage: async (payload: EachMessagePayload) => {
          log(`🎯 eachMessage callback triggered!`);
          await this.handleMessage(payload);
        },
      });
    } catch (error) {
      console.error('❌ Error starting prediction consumer:', error);
      this.isConnecting = false;
      
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
  private async handleMessage({ message, partition }: EachMessagePayload): Promise<void> {
    const fs = require('fs');
    const logPath = 'c:\\traffic-prediction\\consumer-debug.log';
    
    const log = (msg: string) => {
      const timestamp = new Date().toISOString();
      const logLine = `[${timestamp}] ${msg}\n`;
      fs.appendFileSync(logPath, logLine);
      console.log(msg);
    };
    
    try {
      log(`📨 RECEIVED MESSAGE: partition=${partition}, offset=${message.offset}`);
      
      if (!message.value) {
        log('⚠️ Received null message value');
        return;
      }

      const predictionData = JSON.parse(message.value.toString());
      log(`📦 Parsed data: ${JSON.stringify(predictionData).substring(0, 100)}`);
      
      // Calculate speed difference and category
      const currentSpeed = predictionData.actual_speed || predictionData.current_speed || 0;
      const predictedSpeed = predictionData.predicted_speed || 0;
      const currentVolume = predictionData.actual_volume || predictionData.current_volume || 0;
      const speedDiff = predictedSpeed - currentSpeed;
      
      log(`📊 Speeds: current=${currentSpeed}, predicted=${predictedSpeed}, diff=${speedDiff}`);
      
      // Determine traffic category based on predicted speed
      let category: 'free_flow' | 'moderate_traffic' | 'heavy_traffic' | 'severe_congestion';
      if (predictedSpeed >= 60) {
        category = 'free_flow';
      } else if (predictedSpeed >= 45) {
        category = 'moderate_traffic';
      } else if (predictedSpeed >= 30) {
        category = 'heavy_traffic';
      } else {
        category = 'severe_congestion';
      }
      
      const prediction: TrafficPrediction = {
        segment_id: predictionData.segment_id,
        timestamp: typeof predictionData.timestamp === 'string' 
          ? new Date(predictionData.timestamp).getTime() 
          : predictionData.timestamp || Date.now(),
        current_speed: currentSpeed,
        predicted_speed: predictedSpeed,
        current_volume: currentVolume,
        prediction_time: predictionData.prediction_time 
          ? new Date(predictionData.prediction_time).toISOString() 
          : new Date().toISOString(),
        speed_diff: speedDiff,
        category: category,
      };

      // Store latest prediction for this segment
      this.latestPredictions.set(prediction.segment_id, prediction);
      log(`💾 Stored prediction for ${prediction.segment_id}. Total cached: ${this.latestPredictions.size}`);

      // Notify all listeners
      log(`📤 Notifying ${this.listeners.size} listener(s)`);
      this.listeners.forEach((listener) => {
        try {
          listener(prediction);
          log(`✅ Listener notified successfully`);
        } catch (error) {
          log(`❌ Error in prediction listener: ${error}`);
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
let instanceId = Math.random().toString(36).substring(7);

/**
 * Get or create the singleton prediction consumer instance
 */
export function getPredictionConsumer(): PredictionConsumer {
  if (!predictionConsumerInstance) {
    instanceId = Math.random().toString(36).substring(7);
    console.log(`🆕 Creating NEW consumer singleton instance: ${instanceId}`);
    predictionConsumerInstance = new PredictionConsumer();
  } else {
    console.log(`♻️ Reusing EXISTING consumer singleton instance: ${instanceId}`);
  }
  return predictionConsumerInstance;
}

export default PredictionConsumer;
