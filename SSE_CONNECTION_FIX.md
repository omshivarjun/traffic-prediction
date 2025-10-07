# SSE Connection Error - Fixed! 🎉

## Problem Summary

The dashboard was experiencing SSE connection failures with the following errors:

```
❌ SSE connection error: {}
❌ Error starting prediction consumer: Error: Broker not connected
{"level":"ERROR","message":"The group is rebalancing, so a rejoin is needed"}
```

## Root Cause Analysis

### 1. **Wrong Kafka Broker Address**
- **Issue**: Next.js runs **outside Docker** but was trying to connect to `kafka-broker1:9092` (Docker internal hostname)
- **Solution**: Use `localhost:9092` for external access

### 2. **Session Timeout Too Short**
- **Issue**: Kafka consumer session timeout was 30 seconds, causing frequent rebalancing
- **Solution**: Increased to 60 seconds with better heartbeat configuration

### 3. **Poor Error Handling**
- **Issue**: SSE endpoint returned HTTP 500 on Kafka connection failure, causing frontend crashes
- **Solution**: Return SSE error messages instead, allowing graceful retry

## Changes Made

### 1. Created `.env.local` for Next.js
```bash
# Next.js runs OUTSIDE Docker, so use localhost ports
KAFKA_BROKERS=localhost:9092
KAFKA_SCHEMA_REGISTRY_URL=http://localhost:8081
```

### 2. Updated `predictionConsumer.ts`

**Before:**
```typescript
brokers: [
  process.env.KAFKA_BROKER_1 || 'localhost:9092',
  process.env.KAFKA_BROKER_2 || 'localhost:9093',
]
```

**After:**
```typescript
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
```

**Consumer Configuration:**
```typescript
this.consumer = this.kafka.consumer({
  groupId: 'nextjs-prediction-consumer-group',
  sessionTimeout: 60000, // Increased from 30s
  heartbeatInterval: 5000, // Increased from 3s
  rebalanceTimeout: 60000,
  retry: {
    retries: 5,
    initialRetryTime: 300,
  },
});
```

### 3. Improved SSE Error Handling (`stream/route.ts`)

**Before:**
```typescript
catch (error) {
  return new Response('Failed to connect to prediction service', { 
    status: 500 
  });
}
```

**After:**
```typescript
catch (error) {
  // Return error in SSE format instead of HTTP 500
  const stream = new ReadableStream({
    start(controller) {
      const errorMessage = `data: ${JSON.stringify({ 
        type: 'error', 
        message: 'Failed to connect to prediction service. Retrying...',
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: Date.now()
      })}\n\n`;
      controller.enqueue(encoder.encode(errorMessage));
      
      setTimeout(() => controller.close(), 1000);
    },
  });

  return new Response(stream, {
    headers: { 'Content-Type': 'text/event-stream', ... },
  });
}
```

### 4. Added Error Message Handling (`usePredictions.ts`)

```typescript
case 'error':
  // Handle error from server
  console.error('🔴 Server error:', message.message);
  setError(message.message || 'Server connection error');
  setIsConnected(false);
  setIsConnecting(false);
  
  // Attempt reconnection after delay
  if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
    reconnectAttemptsRef.current++;
    reconnectTimeoutRef.current = setTimeout(() => {
      connect();
    }, RECONNECT_DELAY);
  }
  break;
```

## Testing Instructions

### 1. Restart Next.js
```powershell
# Stop current server (Ctrl+C), then:
npm run dev
```

### 2. Verify Kafka Connection
Navigate to: **http://localhost:3000/predictions**

**Expected Console Output:**
```
🔌 Starting prediction consumer for SSE stream...
✅ Connected to Kafka for predictions
🚀 Prediction consumer started successfully
✅ Prediction consumer started for SSE stream
📊 Loaded X initial predictions
```

### 3. Send Test Events
```powershell
.\scripts\send-test-events.ps1
```

**Expected Dashboard Behavior:**
- ✅ No "Connection lost" errors
- ✅ Predictions appear in real-time
- ✅ Map markers update smoothly
- ✅ Analytics panel shows live stats

## Configuration Reference

### Kafka Access Patterns

| Service | Location | Kafka Address | Purpose |
|---------|----------|---------------|---------|
| **Next.js** | Outside Docker | `localhost:9092` | Dashboard SSE stream |
| **FastAPI** | Inside Docker | `kafka-broker1:9092` | Python prediction service |
| **Stream Processor** | Inside Docker | `kafka-broker1:9092` | Kafka Streams app |
| **Kafka Connect** | Inside Docker | `kafka-broker1:9092` | HDFS sink connector |

### Environment Files

- **`.env`**: Docker services (uses `kafka-broker1:9092`)
- **`.env.local`**: Next.js (uses `localhost:9092`)

## Success Metrics

After this fix, you should see:

1. **✅ No "Broker not connected" errors**
2. **✅ No rebalancing warnings** (or minimal, only on startup)
3. **✅ Stable SSE connection** (stays connected for hours)
4. **✅ Real-time prediction updates** (<1 second latency)
5. **✅ Graceful error handling** (displays user-friendly messages)

## Troubleshooting

### Still seeing connection errors?

**1. Check Kafka is running:**
```powershell
docker ps | Select-String "kafka"
```
Should show `kafka-broker1` with status "Up"

**2. Verify Kafka is accessible:**
```powershell
docker exec kafka-broker1 kafka-broker-api-versions --bootstrap-server localhost:9092
```
Should list API versions without errors

**3. Check Next.js environment:**
```powershell
Get-Content .env.local
```
Should show `KAFKA_BROKERS=localhost:9092`

**4. Check predictions are being produced:**
```powershell
docker exec kafka-broker1 kafka-console-consumer `
  --bootstrap-server localhost:9092 `
  --topic traffic-predictions `
  --max-messages 5
```
Should show recent predictions (run `.\scripts\send-test-events.ps1` first)

### Connection works but no predictions?

- Run `.\scripts\send-test-events.ps1` to generate test data
- Check stream processing service is running
- Verify ML prediction service is active

## Next Steps

1. ✅ Restart Next.js server
2. ✅ Test dashboard at http://localhost:3000/predictions
3. ✅ Generate test events with `.\scripts\send-test-events.ps1`
4. ✅ Verify predictions appear in real-time
5. ✅ Monitor console for any remaining errors

---

**Status**: 🟢 READY FOR TESTING

All changes have been applied. Please restart the Next.js server and test the dashboard!
