/**
 * Test script to verify Kafka consumer can connect and subscribe
 */

const { Kafka } = require('kafkajs');

const kafka = new Kafka({
  clientId: 'test-consumer',
  brokers: ['localhost:9092'],
  retry: {
    retries: 8,
    initialRetryTime: 300,
    maxRetryTime: 30000,
  },
  connectionTimeout: 10000,
  requestTimeout: 30000,
});

const consumer = kafka.consumer({
  groupId: 'test-consumer-group',
  sessionTimeout: 60000,
  heartbeatInterval: 5000,
  rebalanceTimeout: 60000,
  retry: {
    retries: 5,
    initialRetryTime: 300,
  },
});

async function test() {
  try {
    console.log('🔌 Connecting to Kafka...');
    await consumer.connect();
    console.log('✅ Connected to Kafka');

    // Wait 1 second after connect
    console.log('⏳ Waiting 1 second for broker to be ready...');
    await new Promise(resolve => setTimeout(resolve, 1000));

    console.log('📝 Subscribing to traffic-predictions topic...');
    await consumer.subscribe({
      topic: 'traffic-predictions',
      fromBeginning: false,
    });
    console.log('✅ Subscribed successfully');

    console.log('🚀 Starting consumer...');
    await consumer.run({
      eachMessage: async ({ topic, partition, message }) => {
        const value = message.value?.toString();
        console.log(`📨 Received message: ${value?.substring(0, 100)}...`);
      },
    });

    console.log('✅ Consumer running successfully!');

    // Keep running for 30 seconds
    setTimeout(async () => {
      console.log('⏹️ Stopping consumer...');
      await consumer.disconnect();
      console.log('✅ Test complete!');
      process.exit(0);
    }, 30000);

  } catch (error) {
    console.error('❌ Error:', error.message);
    console.error('Stack:', error.stack);
    process.exit(1);
  }
}

test();
