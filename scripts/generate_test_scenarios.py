#!/usr/bin/env python3
"""
Generate realistic traffic test scenarios for end-to-end testing.

Creates 5 scenario types:
1. Normal Traffic - Typical midday conditions (50-65 mph)
2. Morning Rush - Heavy congestion (15-35 mph)
3. Evening Rush - Peak traffic (20-40 mph)
4. Accident Scenario - Severe slowdown (5-15 mph)
5. Weather Impact - Reduced visibility/speeds (30-50 mph)

Output: JSONL files matching METR-LA nested structure
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

# Configure output directory
OUTPUT_DIR = Path("data/test_scenarios")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# LA highway configurations
HIGHWAYS = [
    {"name": "I-405", "lanes": 4, "direction": "N"},
    {"name": "I-405", "lanes": 4, "direction": "S"},
    {"name": "I-10", "lanes": 5, "direction": "E"},
    {"name": "I-10", "lanes": 5, "direction": "W"},
    {"name": "US-101", "lanes": 4, "direction": "N"},
    {"name": "US-101", "lanes": 4, "direction": "S"},
]

WEATHER_CONDITIONS = ["clear", "cloudy", "rain", "fog", "drizzle"]


def generate_sensor_id(highway: str, direction: str, index: int) -> str:
    """Generate consistent sensor ID"""
    hwy_code = highway.replace("-", "").replace("US", "")
    return f"LA_{hwy_code}_{direction}_{index:03d}"


def create_traffic_event(
    sensor_id: str,
    timestamp: datetime,
    highway_info: Dict[str, Any],
    speed: float,
    volume: int,
    occupancy: float,
    weather: str = "clear",
    temp: float = 70.0,
    precipitation: bool = False
) -> Dict[str, Any]:
    """Create traffic event matching METR-LA nested structure"""
    
    # Calculate congestion level from speed
    if speed >= 60:
        congestion_level = 1  # Free flow
    elif speed >= 45:
        congestion_level = 2  # Light traffic
    elif speed >= 30:
        congestion_level = 3  # Moderate
    elif speed >= 15:
        congestion_level = 4  # Heavy
    else:
        congestion_level = 5  # Severe
    
    return {
        "event_id": str(uuid.uuid4()),
        "sensor_id": sensor_id,
        "timestamp": timestamp.isoformat(),
        "location": {
            "highway": highway_info["name"],
            "direction": highway_info["direction"],
            "lanes": highway_info["lanes"]
        },
        "traffic_data": {
            "speed_mph": round(speed, 1),
            "volume_vehicles_per_hour": volume,
            "occupancy_percentage": round(occupancy, 1),
            "congestion_level": congestion_level
        },
        "weather": {
            "condition": weather,
            "temperature_f": round(temp, 1),
            "precipitation": precipitation
        },
        "hour": timestamp.hour,
        "day_of_week": timestamp.weekday(),
        "is_weekend": timestamp.weekday() >= 5
    }


def generate_normal_traffic(num_records: int = 1000) -> List[Dict[str, Any]]:
    """
    Scenario 1: Normal Traffic
    Typical midday conditions - free flowing traffic
    Speed: 50-65 mph, Volume: 800-1200 veh/hr, Occupancy: 15-25%
    Time: 11 AM - 2 PM (YESTERDAY to avoid future timestamp errors)
    """
    print("Generating Normal Traffic scenario...")
    events = []
    # Use yesterday to avoid future timestamp validation errors
    yesterday = datetime.now() - timedelta(days=1)
    base_time = datetime(yesterday.year, yesterday.month, yesterday.day, 11, 0, 0)  # 11 AM yesterday
    
    for i in range(num_records):
        highway = random.choice(HIGHWAYS)
        sensor_id = generate_sensor_id(highway["name"], highway["direction"], i % 50)
        timestamp = base_time + timedelta(minutes=i)
        
        # Normal traffic parameters with some variance
        speed = random.uniform(50, 65)
        volume = random.randint(800, 1200)
        occupancy = random.uniform(15, 25)
        temp = random.uniform(68, 75)
        
        events.append(create_traffic_event(
            sensor_id, timestamp, highway, speed, volume, occupancy,
            weather="clear", temp=temp, precipitation=False
        ))
    
    return events


def generate_morning_rush(num_records: int = 1000) -> List[Dict[str, Any]]:
    """
    Scenario 2: Morning Rush Hour
    Heavy congestion, slow speeds, high volume
    Speed: 15-35 mph, Volume: 2500-3500 veh/hr, Occupancy: 65-85%
    Time: 7-9 AM (TODAY - already in past since it's currently after 9 AM)
    """
    print("Generating Morning Rush Hour scenario...")
    events = []
    # Use today's morning (already passed)
    today = datetime.now()
    base_time = datetime(today.year, today.month, today.day, 7, 0, 0)  # 7 AM today
    
    for i in range(num_records):
        highway = random.choice(HIGHWAYS)
        sensor_id = generate_sensor_id(highway["name"], highway["direction"], i % 50)
        timestamp = base_time + timedelta(minutes=i * 0.12)  # 2 hours spread
        
        # Rush hour parameters
        # Gradual slowdown from 7-8 AM, worst at 8-8:30, slight recovery 8:30-9
        hour_progress = (timestamp.hour - 7) + (timestamp.minute / 60)
        if hour_progress < 1.0:  # 7-8 AM: building congestion
            speed = random.uniform(25, 35)
            volume = random.randint(2000, 2800)
            occupancy = random.uniform(60, 75)
        elif hour_progress < 1.5:  # 8-8:30 AM: peak congestion
            speed = random.uniform(15, 25)
            volume = random.randint(2800, 3500)
            occupancy = random.uniform(75, 85)
        else:  # 8:30-9 AM: slight recovery
            speed = random.uniform(20, 30)
            volume = random.randint(2500, 3000)
            occupancy = random.uniform(70, 80)
        
        temp = random.uniform(62, 68)
        
        events.append(create_traffic_event(
            sensor_id, timestamp, highway, speed, volume, occupancy,
            weather=random.choice(["clear", "cloudy"]), temp=temp, precipitation=False
        ))
    
    return events


def generate_evening_rush(num_records: int = 1000) -> List[Dict[str, Any]]:
    """
    Scenario 3: Evening Rush Hour
    Peak traffic, sustained high volume
    Speed: 20-40 mph, Volume: 3000-4000 veh/hr, Occupancy: 70-90%
    Time: 4-6 PM (YESTERDAY to avoid future timestamp errors)
    """
    print("Generating Evening Rush Hour scenario...")
    events = []
    # Use yesterday to avoid future timestamp validation errors
    yesterday = datetime.now() - timedelta(days=1)
    base_time = datetime(yesterday.year, yesterday.month, yesterday.day, 16, 0, 0)  # 4 PM yesterday
    
    for i in range(num_records):
        highway = random.choice(HIGHWAYS)
        sensor_id = generate_sensor_id(highway["name"], highway["direction"], i % 50)
        timestamp = base_time + timedelta(minutes=i * 0.12)  # 2 hours spread
        
        # Evening rush parameters
        # Gradual buildup from 4-5 PM, peak 5-5:30, sustained 5:30-6
        hour_progress = (timestamp.hour - 16) + (timestamp.minute / 60)
        if hour_progress < 1.0:  # 4-5 PM: building
            speed = random.uniform(30, 40)
            volume = random.randint(2500, 3200)
            occupancy = random.uniform(65, 75)
        elif hour_progress < 1.5:  # 5-5:30 PM: peak
            speed = random.uniform(20, 30)
            volume = random.randint(3200, 4000)
            occupancy = random.uniform(80, 90)
        else:  # 5:30-6 PM: sustained heavy
            speed = random.uniform(25, 35)
            volume = random.randint(3000, 3800)
            occupancy = random.uniform(75, 85)
        
        temp = random.uniform(70, 78)
        
        events.append(create_traffic_event(
            sensor_id, timestamp, highway, speed, volume, occupancy,
            weather=random.choice(["clear", "cloudy"]), temp=temp, precipitation=False
        ))
    
    return events


def generate_accident_scenario(num_records: int = 500) -> List[Dict[str, Any]]:
    """
    Scenario 4: Accident Impact
    Severe slowdown, lane closure simulation
    Speed: 5-15 mph, Volume: 500-1000 veh/hr, Occupancy: 90-100%
    Time: Random throughout day (YESTERDAY to avoid future timestamp errors)
    """
    print("Generating Accident Scenario...")
    events = []
    
    # Simulate accident on I-405 Northbound at 10:30 AM YESTERDAY
    accident_highway = {"name": "I-405", "lanes": 4, "direction": "N"}
    yesterday = datetime.now() - timedelta(days=1)
    base_time = datetime(yesterday.year, yesterday.month, yesterday.day, 10, 30, 0)
    
    # Sensors upstream (before accident) and downstream (after accident)
    upstream_sensors = [f"LA_405_N_{i:03d}" for i in range(10, 20)]
    accident_sensors = [f"LA_405_N_{i:03d}" for i in range(20, 25)]  # Affected area
    downstream_sensors = [f"LA_405_N_{i:03d}" for i in range(25, 35)]
    
    for i in range(num_records):
        timestamp = base_time + timedelta(minutes=i * 0.06)  # 30 minutes spread
        minutes_since_accident = (timestamp - base_time).total_seconds() / 60
        
        # Rotate through sensor groups
        if i % 3 == 0:
            sensor_id = random.choice(upstream_sensors)
            # Upstream: building backup
            speed = random.uniform(10, 20) if minutes_since_accident > 5 else random.uniform(25, 35)
            volume = random.randint(800, 1200)
            occupancy = random.uniform(70, 85)
        elif i % 3 == 1:
            sensor_id = random.choice(accident_sensors)
            # At accident: severe congestion
            speed = random.uniform(5, 15)
            volume = random.randint(500, 800)
            occupancy = random.uniform(90, 100)
        else:
            sensor_id = random.choice(downstream_sensors)
            # Downstream: recovering flow
            speed = random.uniform(30, 45)
            volume = random.randint(1200, 1800)
            occupancy = random.uniform(40, 55)
        
        temp = random.uniform(68, 74)
        
        events.append(create_traffic_event(
            sensor_id, timestamp, accident_highway, speed, volume, occupancy,
            weather="clear", temp=temp, precipitation=False
        ))
    
    return events


def generate_weather_impact(num_records: int = 500) -> List[Dict[str, Any]]:
    """
    Scenario 5: Weather Impact
    Reduced visibility and speeds due to rain/fog
    Speed: 30-50 mph, Volume: 1000-1500 veh/hr, Occupancy: 40-60%
    Time: Random, various weather conditions (YESTERDAY to avoid future timestamp errors)
    """
    print("Generating Weather Impact scenario...")
    events = []
    # Use yesterday to avoid future timestamp validation errors
    yesterday = datetime.now() - timedelta(days=1)
    base_time = datetime(yesterday.year, yesterday.month, yesterday.day, 14, 0, 0)  # 2 PM yesterday
    
    for i in range(num_records):
        highway = random.choice(HIGHWAYS)
        sensor_id = generate_sensor_id(highway["name"], highway["direction"], i % 50)
        timestamp = base_time + timedelta(minutes=i * 0.06)  # 30 minutes spread
        
        # Weather conditions affect speed
        weather = random.choice(["rain", "fog", "drizzle", "rain", "fog"])
        
        if weather == "fog":
            speed = random.uniform(30, 40)
            volume = random.randint(900, 1200)
            occupancy = random.uniform(45, 60)
            temp = random.uniform(55, 62)
        elif weather == "rain":
            speed = random.uniform(35, 50)
            volume = random.randint(1000, 1400)
            occupancy = random.uniform(40, 55)
            temp = random.uniform(58, 65)
        else:  # drizzle
            speed = random.uniform(40, 50)
            volume = random.randint(1100, 1500)
            occupancy = random.uniform(35, 50)
            temp = random.uniform(60, 68)
        
        events.append(create_traffic_event(
            sensor_id, timestamp, highway, speed, volume, occupancy,
            weather=weather, temp=temp, precipitation=True
        ))
    
    return events


def save_scenario(scenario_name: str, events: List[Dict[str, Any]]) -> Path:
    """Save scenario to JSONL file"""
    output_file = OUTPUT_DIR / f"{scenario_name}.jsonl"
    
    with open(output_file, 'w') as f:
        for event in events:
            f.write(json.dumps(event) + '\n')
    
    print(f"✓ Saved {len(events)} events to {output_file}")
    
    # Print sample statistics
    speeds = [e["traffic_data"]["speed_mph"] for e in events]
    volumes = [e["traffic_data"]["volume_vehicles_per_hour"] for e in events]
    occupancies = [e["traffic_data"]["occupancy_percentage"] for e in events]
    
    print(f"  Speed range: {min(speeds):.1f} - {max(speeds):.1f} mph (avg: {sum(speeds)/len(speeds):.1f})")
    print(f"  Volume range: {min(volumes)} - {max(volumes)} veh/hr (avg: {sum(volumes)//len(volumes)})")
    print(f"  Occupancy range: {min(occupancies):.1f}% - {max(occupancies):.1f}% (avg: {sum(occupancies)/len(occupancies):.1f}%)")
    
    return output_file


def main():
    """Generate all test scenarios"""
    print("=" * 70)
    print("GENERATING TEST SCENARIOS FOR END-TO-END TESTING")
    print("=" * 70)
    print()
    
    scenarios = {
        "scenario_1_normal_traffic": generate_normal_traffic(1000),
        "scenario_2_morning_rush": generate_morning_rush(1000),
        "scenario_3_evening_rush": generate_evening_rush(1000),
        "scenario_4_accident": generate_accident_scenario(500),
        "scenario_5_weather_impact": generate_weather_impact(500),
    }
    
    print()
    print("=" * 70)
    print("SAVING SCENARIOS")
    print("=" * 70)
    print()
    
    output_files = []
    for scenario_name, events in scenarios.items():
        output_file = save_scenario(scenario_name, events)
        output_files.append(output_file)
        print()
    
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    total_events = sum(len(events) for events in scenarios.values())
    print(f"Total events generated: {total_events}")
    print(f"Output directory: {OUTPUT_DIR.absolute()}")
    print(f"Files created: {len(output_files)}")
    print()
    print("✓ All test scenarios generated successfully!")
    print()
    print("Next steps:")
    print("1. Run input validation on all scenarios")
    print("2. Start Kafka producers with these files")
    print("3. Execute end-to-end pipeline test")
    print("=" * 70)


if __name__ == "__main__":
    main()
