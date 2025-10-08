/**
 * Test the SSE endpoint to verify it connects without errors
 */

const http = require('http');

console.log('🔍 Testing SSE endpoint at http://localhost:3000/api/predictions/stream');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

const options = {
  hostname: 'localhost',
  port: 3000,
  path: '/api/predictions/stream',
  method: 'GET',
  headers: {
    'Accept': 'text/event-stream',
  },
};

const req = http.request(options, (res) => {
  console.log(`✅ Connected! Status: ${res.statusCode}`);
  console.log(`📋 Headers:`, res.headers);
  console.log('\n📨 Messages:\n');

  let messageCount = 0;
  
  res.on('data', (chunk) => {
    const data = chunk.toString();
    messageCount++;
    
    // Parse SSE data
    const lines = data.split('\n');
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const json = JSON.parse(line.substring(6));
          console.log(`[${messageCount}] Type: ${json.type}`);
          
          if (json.type === 'error') {
            console.error('❌ ERROR:', json.message);
            console.error('   Details:', json.error);
            process.exit(1);
          } else if (json.type === 'connected') {
            console.log('✅ Connected message received');
          } else if (json.type === 'initial') {
            console.log(`✅ Initial predictions: ${json.count} items`);
          } else if (json.type === 'prediction') {
            console.log(`✅ Prediction for segment: ${json.data?.segment_id}`);
          } else if (json.type === 'stats') {
            console.log(`📊 Stats: ${json.data?.totalPredictions || 0} total predictions`);
          }
        } catch (e) {
          console.log('Raw:', line);
        }
      }
    }
  });

  res.on('end', () => {
    console.log('\n✅ Stream ended');
  });

  // Stop after 10 seconds
  setTimeout(() => {
    console.log('\n⏹️ Stopping test after 10 seconds');
    req.abort();
    process.exit(0);
  }, 10000);
});

req.on('error', (e) => {
  console.error(`❌ Request error: ${e.message}`);
  process.exit(1);
});

req.end();
