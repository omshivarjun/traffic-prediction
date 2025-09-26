import { KafkaStreams, KafkaStreamsConfig } from 'kafka-streams';
import * as fs from 'fs';
import * as path from 'path';
import { TrafficEventProcessor } from './processors/TrafficEventProcessor';
import { TrafficIncidentProcessor } from './processors/TrafficIncidentProcessor';
import { TrafficPredictionProcessor } from './processors/TrafficPredictionProcessor';

// Load configuration
const loadConfig = (): Record<string, string> => {
  const configPath = path.join(__dirname, 'config', 'application.properties');
  const configContent = fs.readFileSync(configPath, 'utf8');
  const config: Record<string, string> = {};
  
  configContent.split('\n').forEach(line => {
    if (line && !line.startsWith('#')) {
      const [key, value] = line.split('=');
      if (key && value) {
        config[key.trim()] = value.trim();
      }
    }
  });
  
  return config;
};

// Initialize Kafka Streams
const initKafkaStreams = (config: Record<string, string>): KafkaStreams => {
  const kafkaConfig: KafkaStreamsConfig = {
    'noptions': {
      'metadata.broker.list': config['bootstrap.servers'],
      'group.id': config['application.id'],
      'client.id': `${config['application.id']}-client`,
      'event_cb': true,
      'dr_cb': true,
      'socket.keepalive.enable': true,
      'queue.buffering.max.messages': 100000,
      'queue.buffering.max.ms': 1000,
      'batch.num.messages': 1000,
      'fetch.message.max.bytes': 1024 * 1024,
      'enable.auto.commit': false
    },
    'tconf': {
      'auto.offset.reset': 'earliest',
      'request.required.acks': 1
    },
    'batchOptions': {
      'batchSize': 500,
      'commitEveryNBatch': 1,
      'concurrency': 1,
      'commitSync': false,
      'noBatchCommits': false
    }
  };
  
  return new KafkaStreams(kafkaConfig);
};

// Main function
const main = async () => {
  try {
    console.log('Starting Traffic Prediction Stream Processing...');
    
    // Load configuration
    const config = loadConfig();
    console.log('Configuration loaded successfully');
    
    // Initialize Kafka Streams
    const kafkaStreams = initKafkaStreams(config);
    console.log('Kafka Streams initialized');
    
    // Initialize processors
    const trafficEventProcessor = new TrafficEventProcessor(kafkaStreams, config);
    const trafficIncidentProcessor = new TrafficIncidentProcessor(kafkaStreams, config);
    const trafficPredictionProcessor = new TrafficPredictionProcessor(kafkaStreams, config);
    
    // Start processors
    await trafficEventProcessor.start();
    await trafficIncidentProcessor.start();
    await trafficPredictionProcessor.start();
    
    console.log('All processors started successfully');
    
    // Handle shutdown
    const shutdown = async () => {
      console.log('Shutting down stream processing...');
      
      await trafficEventProcessor.stop();
      await trafficIncidentProcessor.stop();
      await trafficPredictionProcessor.stop();
      
      kafkaStreams.closeAll();
      console.log('Stream processing shutdown complete');
      process.exit(0);
    };
    
    process.on('SIGINT', shutdown);
    process.on('SIGTERM', shutdown);
    
  } catch (error) {
    console.error('Error in stream processing:', error);
    process.exit(1);
  }
};

// Run the application
main();