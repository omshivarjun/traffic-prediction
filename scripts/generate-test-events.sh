#!/bin/bash
# Test Traffic Event Generator
# Generates continuous traffic events for testing the ML prediction pipeline

echo "🚀 Starting Traffic Event Generator..."
echo "📊 Generating events every 5 seconds"
echo "Press Ctrl+C to stop"
echo ""

count=0
while true; do
  # Generate random segment (LA_001 to LA_005)
  SEGMENT_ID="LA_00$((1 + RANDOM % 5))"
  
  # Generate random speed (50-70 mph for varied conditions)
  SPEED=$((50 + RANDOM % 21))
  
  # Generate random volume (300-500 vehicles)
  VOLUME=$((300 + RANDOM % 201))
  
  # Get current timestamp in milliseconds
  TIMESTAMP=$(date +%s)000
  
  # Create JSON event
  EVENT="{\"segment_id\":\"$SEGMENT_ID\",\"timestamp\":$TIMESTAMP,\"speed\":$SPEED.5,\"volume\":$VOLUME}"
  
  # Send to Kafka
  echo "$EVENT" | kafka-console-producer --bootstrap-server localhost:9092 --topic traffic-events 2>/dev/null
  
  count=$((count + 1))
  echo "[$count] ✅ Sent: $SEGMENT_ID - Speed: ${SPEED}mph, Volume: $VOLUME vehicles"
  
  sleep 5
done
