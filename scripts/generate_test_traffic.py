#!/usr/bin/env python3
"""
Generate sample traffic events for testing real-time predictions
"""

import json
import time
from kafka import KafkaProducer
from datetime import datetime
import random

def create_producer():
    return KafkaProducer(
        bootstrap_servers=['localhost:9092', 'localhost:9093'],
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )

def generate_traffic_event(segment_id):
    """Generate a realistic traffic event"""
    hour = datetime.now().hour
    
    # Rush hour logic
    if 7 <= hour <= 9 or 16 <= hour <= 18:
        base_speed = random.uniform(35, 55)
        base_volume = random.randint(600, 900)
    elif 0 <= hour <= 5:
        base_speed = random.uniform(65, 75)
        base_volume = random.randint(50, 150)
    else:
        base_speed = random.uniform(55, 70)
        base_volume = random.randint(300, 500)
    
    return {
        "segment_id": segment_id,
        "timestamp": int(time.time() * 1000),
        "speed": round(base_speed + random.uniform(-5, 5), 1),
        "volume": int(base_volume + random.randint(-50, 50))
    }

def main():
    print("\n" + "="*60)
    print("📡 Traffic Event Generator for ML Predictions")
    print("="*60 + "\n")
    
    producer = create_producer()
    print("✅ Connected to Kafka\n")
    
    segments = ["LA_001", "LA_002", "LA_003", "LA_004", "LA_005"]
    
    print("🚗 Generating traffic events...")
    print("Press Ctrl+C to stop\n")
    
    count = 0
    try:
        while True:
            for segment in segments:
                event = generate_traffic_event(segment)
                producer.send('traffic-events', value=event)
                count += 1
                
                print(f"✅ #{count} - {segment}: {event['speed']} mph, {event['volume']} vehicles")
            
            producer.flush()
            time.sleep(2)  # Send batch every 2 seconds
            
    except KeyboardInterrupt:
        print(f"\n\n📊 Total events sent: {count}")
        print("✅ Generator stopped")
    finally:
        producer.close()

if __name__ == "__main__":
    main()
