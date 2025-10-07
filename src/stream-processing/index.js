#!/usr/bin/env node

/**
 * Stream Processor Entry Point for Docker Container
 * Handles traffic event processing with Kafka Streams
 */

const { Kafka } = require('kafkajs');
const path = require('path');
const fs = require('fs');

// Configuration
const KAFKA_BROKERS = process.env.KAFKA_BROKERS || 'kafka-broker1:9092';
const GROUP_ID = process.env.GROUP_ID || 'stream-processor-group';
const CLIENT_ID = process.env.CLIENT_ID || 'stream-processor-client';
const INPUT_TOPIC = process.env.INPUT_TOPIC || 'traffic-raw';
const OUTPUT_TOPIC = process.env.OUTPUT_TOPIC || 'traffic-events';
const HEALTH_PORT = process.env.HEALTH_PORT || 3001;

// Health check server
const http = require('http');
let isHealthy = false;
let messagesProcessed = 0;
let lastMessageTime = null;

const healthServer = http.createServer((req, res) => {
  if (req.url === '/health') {
    const status = isHealthy ? 200 : 503;
    res.writeHead(status, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: isHealthy ? 'healthy' : 'unhealthy',
      messagesProcessed,
      lastMessageTime,
      uptime: process.uptime()
    }));
  } else if (req.url === '/metrics') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      messagesProcessed,
      lastMessageTime,
      uptime: process.uptime(),
      memoryUsage: process.memoryUsage()
    }));
  } else {
    res.writeHead(404);
    res.end();
  }
});

// Flatten METR-LA nested format
const flattenMetrLaFormat = (event) => {
  // Check if this is METR-LA nested format
  if (event.traffic_data && event.location && event.weather) {
    return {
      sensor_id: event.location.segment_id || event.location.sensor_id || 'unknown',
      timestamp: event.timestamp,
      speed: event.traffic_data.speed_mph,
      volume: event.traffic_data.volume_vehicles_per_hour,
      occupancy: event.traffic_data.occupancy_percent || null,
      lane_count: event.location.lanes || null,
      latitude: event.location.coordinates?.latitude || null,
      longitude: event.location.coordinates?.longitude || null,
      highway: event.location.highway_id || event.location.highway || null,
      direction: event.location.direction || null,
      weather_conditions: event.weather.condition || null,
      temperature: event.weather.temperature_fahrenheit || null
    };
  }
  // Already flat format
  return event;
};

// Validation function
const validateTrafficEvent = (event) => {
  try {
    // Flatten if needed
    const flatEvent = flattenMetrLaFormat(event);
    
    // Check required fields
    const required = ['sensor_id', 'timestamp', 'speed', 'volume'];
    for (const field of required) {
      if (!flatEvent[field] && flatEvent[field] !== 0) {
        return { isValid: false, errors: [`Missing required field: ${field}`] };
      }
    }

    // Validate ranges
    const errors = [];
    
    if (flatEvent.speed < 0 || flatEvent.speed > 120) {
      errors.push(`Invalid speed: ${flatEvent.speed} mph (must be 0-120)`);
    }
    
    if (flatEvent.volume < 0 || flatEvent.volume > 10000) {
      errors.push(`Invalid volume: ${flatEvent.volume} veh/hr (must be 0-10000)`);
    }
    
    // Validate timestamp
    const eventTime = new Date(flatEvent.timestamp);
    const now = new Date();
    const oneYearAgo = new Date(now.getTime() - 365 * 24 * 60 * 60 * 1000);
    
    if (eventTime > now) {
      errors.push(`Timestamp in future: ${flatEvent.timestamp}`);
    }
    
    if (eventTime < oneYearAgo) {
      errors.push(`Timestamp too old: ${flatEvent.timestamp}`);
    }

    return {
      isValid: errors.length === 0,
      errors,
      flatEvent  // Return flattened event
    };
  } catch (error) {
    return {
      isValid: false,
      errors: [`Validation error: ${error.message}`]
    };
  }
};

// Transform function
const transformEvent = (rawEvent) => {
  const { isValid, errors, flatEvent } = validateTrafficEvent(rawEvent);
  
  if (!isValid) {
    console.warn('Invalid event:', errors.join(', '));
    return null;
  }

  // Add processing metadata to the flattened event
  return {
    ...flatEvent,
    processed_at: new Date().toISOString(),
    processor_id: CLIENT_ID,
    validation_status: 'valid'
  };
};

// Main processing function
const startStreamProcessor = async () => {
  console.log('🚀 Starting Stream Processor...');
  console.log(`📊 Configuration:
    - Kafka Brokers: ${KAFKA_BROKERS}
    - Group ID: ${GROUP_ID}
    - Input Topic: ${INPUT_TOPIC}
    - Output Topic: ${OUTPUT_TOPIC}
    - Health Port: ${HEALTH_PORT}
  `);

  // Initialize Kafka
  const kafka = new Kafka({
    clientId: CLIENT_ID,
    brokers: KAFKA_BROKERS.split(','),
    retry: {
      initialRetryTime: 300,
      retries: 10
    },
    connectionTimeout: 10000,
    requestTimeout: 30000
  });

  const consumer = kafka.consumer({
    groupId: GROUP_ID,
    sessionTimeout: 30000,
    heartbeatInterval: 3000,
    maxWaitTimeInMs: 5000,
    maxBytesPerPartition: 1048576
  });

  const producer = kafka.producer({
    allowAutoTopicCreation: false,
    transactionTimeout: 30000,
    idempotent: true,
    maxInFlightRequests: 5,
    retry: {
      initialRetryTime: 300,
      retries: 10
    }
  });

  // Connect
  console.log('📡 Connecting to Kafka...');
  await consumer.connect();
  await producer.connect();
  console.log('✅ Connected to Kafka');

  // Subscribe to input topic
  await consumer.subscribe({
    topic: INPUT_TOPIC,
    fromBeginning: false
  });
  console.log(`✅ Subscribed to topic: ${INPUT_TOPIC}`);

  isHealthy = true;

  // Process messages
  await consumer.run({
    autoCommit: true,
    autoCommitInterval: 5000,
    eachMessage: async ({ topic, partition, message }) => {
      try {
        // Parse message
        const rawEvent = JSON.parse(message.value.toString());
        
        // Transform and validate
        const transformedEvent = transformEvent(rawEvent);
        
        if (transformedEvent) {
          // Send to output topic
          await producer.send({
            topic: OUTPUT_TOPIC,
            messages: [{
              key: message.key,
              value: JSON.stringify(transformedEvent),
              headers: {
                'processed_at': new Date().toISOString(),
                'processor_id': CLIENT_ID
              }
            }]
          });

          messagesProcessed++;
          lastMessageTime = new Date().toISOString();

          if (messagesProcessed % 100 === 0) {
            console.log(`✅ Processed ${messagesProcessed} messages (latest: ${transformedEvent.sensor_id})`);
          }
        }
      } catch (error) {
        console.error('❌ Error processing message:', error.message);
        // Continue processing other messages
      }
    }
  });

  console.log('🎯 Stream processor is running...');
};

// Graceful shutdown
const shutdown = async (signal) => {
  console.log(`\n📛 Received ${signal}, shutting down gracefully...`);
  isHealthy = false;
  
  healthServer.close(() => {
    console.log('✅ Health server closed');
  });

  console.log(`📊 Final stats: ${messagesProcessed} messages processed`);
  process.exit(0);
};

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

// Start health server
healthServer.listen(HEALTH_PORT, () => {
  console.log(`💚 Health check server listening on port ${HEALTH_PORT}`);
  console.log(`   - GET /health - Health status`);
  console.log(`   - GET /metrics - Processing metrics`);
});

// Start stream processor
startStreamProcessor().catch(error => {
  console.error('💥 Fatal error:', error);
  process.exit(1);
});
