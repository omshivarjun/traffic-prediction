# End-to-End Testing Guide

## 🎯 Quick Start

Once Docker Desktop is running:

```powershell
# Run complete end-to-end test
.\scripts\test-e2e.ps1

# Or run individual steps:
.\scripts\send-test-events.ps1 -Count 10 -DelaySeconds 3
npm run dev
```

## 🐛 Bug Discovery & Resolution

### The Issue
The streaming prediction service was producing **empty output** despite successfully receiving Kafka events.

### Root Cause
**Invalid JSON format** caused by bash `echo` command stripping quotes:
- ❌ Input: `echo '{"segment_id":"LA_001",...}'`
- ❌ Kafka message: `{segment_id:LA_001,...}` (missing quotes!)
- ❌ Result: `from_json()` failed, producing NULL values

### The Fix
✅ Use **file-based** or **PowerShell string handling** approach:
```powershell
# PowerShell properly preserves JSON quotes
$event = '{"segment_id":"LA_001","timestamp":1728400000000,"speed":62.5,"volume":380}'
docker exec kafka-broker1 bash -c "echo '$event' | kafka-console-producer ..."
```

### Verification
With properly formatted JSON, the pipeline produces complete predictions:
```json
{
  "segment_id": "LA_TEST_001",
  "timestamp": 1728400000000,
  "current_speed": 62.5,
  "predicted_speed": 50.17803491191826,
  "current_volume": 380,
  "prediction_time": "2025-10-07T04:20:35.004Z",
  "speed_diff": -12.32196508808174,
  "category": "moderate_traffic"
}
```

## 📋 Testing Checklist

### Prerequisites
- [ ] Docker Desktop running
- [ ] All containers up: `docker ps`
- [ ] Kafka brokers healthy
- [ ] Spark master accessible

### Backend Testing
- [ ] Streaming service running (check: `docker exec spark-master ps aux | grep simple_streaming`)
- [ ] Model loaded successfully (check logs: `docker exec spark-master grep "Model loaded" /tmp/predictions.log`)
- [ ] Test events sent (use `send-test-events.ps1`)
- [ ] Predictions appear in Kafka topic: 
  ```powershell
  docker exec kafka-broker1 kafka-console-consumer --bootstrap-server localhost:9092 --topic traffic-predictions --from-beginning --max-messages 5
  ```

### Frontend Testing
- [ ] Dashboard starts: `npm run dev`
- [ ] SSE connection established (check DevTools Network tab)
- [ ] Prediction markers appear on map
- [ ] Analytics panel updates
- [ ] No errors in browser console

### Performance Validation
- [ ] End-to-end latency < 5 seconds
- [ ] Dashboard handles 10+ predictions/min
- [ ] No memory leaks over 10 minutes
- [ ] Smooth real-time updates

## 🔧 Troubleshooting

### Docker Desktop 500 Error
**Symptom**: `request returned 500 Internal Server Error`

**Fix**:
1. Restart Docker Desktop
2. If persists, restart computer
3. Verify: `docker ps`

### No Predictions in Kafka
**Check**:
```powershell
# 1. Is streaming service running?
docker exec spark-master ps aux | grep simple_streaming

# 2. Are events being received?
docker exec spark-master tail -50 /tmp/predictions.log | Select-String "numInputRows"

# 3. Check for errors
docker exec spark-master tail -100 /tmp/predictions.log | Select-String "ERROR|Exception"
```

**Common Causes**:
- Service not started → Run `test-e2e.ps1` to auto-start
- Invalid JSON in events → Use PowerShell scripts, not bash echo
- Model loading failed → Check HDFS connectivity

### Dashboard Not Connecting
**Check**:
```powershell
# 1. Is Kafka broker accessible?
docker exec kafka-broker1 kafka-broker-api-versions --bootstrap-server localhost:9092

# 2. Is predictions topic populated?
docker exec kafka-broker1 kafka-console-consumer --topic traffic-predictions --from-beginning --max-messages 1

# 3. Check Next.js logs
# Look for connection errors or Kafka consumer issues
```

**Common Causes**:
- Kafka broker down → `docker-compose restart kafka-broker1`
- Port conflicts → Check 9092, 9093, 3000
- Node dependencies → `npm install`

### Empty Predictions (All NULL)
**Check**:
```powershell
# Debug with raw message viewer
docker exec kafka-broker1 kafka-console-consumer --topic traffic-events --from-beginning --max-messages 1

# Look for missing quotes in JSON
```

**Fix**: Use provided PowerShell scripts instead of manual bash commands

## 📊 Expected Output

### Streaming Service Logs
```
🚀 Starting Real-time Traffic Prediction Service
============================================================
📂 Loading model from HDFS...
✅ Model loaded! Features: 18
🔌 Connecting to Kafka...
📊 Parsing Kafka messages...
🔧 Creating features...
🤖 Applying ML model...
📤 Formatting predictions...
💡 Starting prediction stream...
✅ Prediction service running!
```

### Kafka Prediction Message
```json
{
  "segment_id": "LA_001",
  "timestamp": 1728400000000,
  "current_speed": 65.5,
  "predicted_speed": 58.32,
  "current_volume": 450,
  "prediction_time": "2025-10-07T04:20:35.004Z",
  "speed_diff": -7.18,
  "category": "moderate_traffic"
}
```

### Dashboard Console (Success)
```
✅ Connected to prediction stream
📊 Received initial predictions: 5
🔄 Prediction update: LA_001 (moderate_traffic)
📈 Stats update: 5 predictions, 92.5% avg accuracy
```

## 🎯 Success Criteria

**Backend**:
- ✅ Streaming service processes events without errors
- ✅ Predictions generated with valid JSON structure
- ✅ All 18 features calculated correctly
- ✅ Model predictions within expected range (30-70 mph)
- ✅ Category assignment matches predicted speed

**Frontend**:
- ✅ SSE connection remains stable (no disconnects)
- ✅ Markers render at correct coordinates
- ✅ Popups display all 9 data points
- ✅ Analytics metrics update in real-time
- ✅ Zero JavaScript errors

**Performance**:
- ✅ Event → Prediction latency: < 3 seconds
- ✅ Prediction → Dashboard: < 2 seconds
- ✅ Total end-to-end: < 5 seconds
- ✅ Throughput: 10+ predictions/minute
- ✅ Memory stable over 30 minutes

## 📝 Next Steps After Testing

1. **Document actual performance metrics**
2. **Update coordinate mapping** (replace hardcoded LA coordinates)
3. **Add prediction history** (timeline component)
4. **Implement filters** (by segment, category, time range)
5. **Add alerts** (severe congestion notifications)
6. **Performance optimization** (if needed)
7. **Production deployment** (containerize dashboard)

## 🔗 Related Documentation

- [Dashboard Integration](./DASHBOARD_INTEGRATION_TESTING.md)
- [ML Training System](./ML_TRAINING_SYSTEM.md)
- [Kafka Setup](./kafka-setup.md)
- [Configuration Guide](./CONFIGURATION.md)
