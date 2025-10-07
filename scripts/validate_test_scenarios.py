#!/usr/bin/env python3
"""
Validate generated test scenarios using input_data_validator.py
Ensures all test data passes safety checks before pipeline testing
"""

import sys
import json
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from validation.input_data_validator import TrafficDataValidator

def flatten_metr_la_format(event: dict) -> dict:
    """
    Convert METR-LA nested format to flat format expected by validator
    
    METR-LA format has nested objects:
    - traffic_data: {speed_mph, volume_vehicles_per_hour, occupancy_percentage}
    - location: {highway, direction, lanes}
    - weather: {condition, temperature_f, precipitation}
    
    Validator expects flat fields:
    - speed, volume, occupancy, lane_count, etc.
    """
    flat = {
        "sensor_id": event.get("sensor_id"),
        "timestamp": event.get("timestamp"),
        "event_id": event.get("event_id"),
    }
    
    # Extract traffic data fields
    if "traffic_data" in event:
        traffic = event["traffic_data"]
        flat["speed"] = traffic.get("speed_mph")
        flat["volume"] = traffic.get("volume_vehicles_per_hour")
        flat["occupancy"] = traffic.get("occupancy_percentage")
    
    # Extract location fields
    if "location" in event:
        location = event["location"]
        flat["highway"] = location.get("highway")
        flat["direction"] = location.get("direction")
        flat["lane_count"] = location.get("lanes")
    
    # Extract weather fields
    if "weather" in event:
        weather = event["weather"]
        flat["weather_condition"] = weather.get("condition")
        flat["temperature"] = weather.get("temperature_f")
        flat["precipitation"] = weather.get("precipitation")
    
    # Copy other fields
    for key in ["hour", "day_of_week", "is_weekend"]:
        if key in event:
            flat[key] = event[key]
    
    return flat


def validate_scenario_file(file_path: Path) -> dict:
    """Validate all events in a scenario file"""
    validator = TrafficDataValidator()
    
    print(f"\nValidating: {file_path.name}")
    print("=" * 70)
    
    valid_count = 0
    invalid_count = 0
    errors = []
    
    with open(file_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            try:
                event = json.loads(line.strip())
                
                # Flatten METR-LA nested format to validator format
                flat_event = flatten_metr_la_format(event)
                
                # Validate the flattened event
                is_valid, validation_results, cleaned_data = validator.validate_traffic_record(flat_event)
                
                if is_valid:
                    valid_count += 1
                else:
                    invalid_count += 1
                    # Collect error messages from validation results
                    error_msgs = [vr.message for vr in validation_results if not vr.is_valid]
                    errors.append({
                        "line": line_num,
                        "event_id": event.get("event_id", "unknown"),
                        "error": "; ".join(error_msgs) if error_msgs else "Validation failed"
                    })
                    
            except json.JSONDecodeError as e:
                invalid_count += 1
                errors.append({
                    "line": line_num,
                    "event_id": "N/A",
                    "error": f"JSON decode error: {str(e)}"
                })
    
    total = valid_count + invalid_count
    pass_rate = (valid_count / total * 100) if total > 0 else 0
    
    print(f"Total events: {total}")
    print(f"Valid:   {valid_count} ({pass_rate:.1f}%)")
    print(f"Invalid: {invalid_count}")
    
    if errors:
        print(f"\n⚠️  Found {len(errors)} validation errors:")
        for error in errors[:5]:  # Show first 5 errors
            print(f"  Line {error['line']}: {error['error']}")
        if len(errors) > 5:
            print(f"  ... and {len(errors) - 5} more errors")
    else:
        print("✅ All events passed validation!")
    
    return {
        "file": file_path.name,
        "total": total,
        "valid": valid_count,
        "invalid": invalid_count,
        "pass_rate": pass_rate,
        "errors": errors
    }


def main():
    """Validate all test scenarios"""
    scenarios_dir = Path("data/test_scenarios")
    
    if not scenarios_dir.exists():
        print(f"❌ Error: {scenarios_dir} does not exist")
        print("Run generate_test_scenarios.py first")
        return 1
    
    print("=" * 70)
    print("VALIDATING TEST SCENARIOS")
    print("=" * 70)
    
    # Find all scenario files
    scenario_files = sorted(scenarios_dir.glob("scenario_*.jsonl"))
    
    if not scenario_files:
        print(f"❌ No scenario files found in {scenarios_dir}")
        return 1
    
    print(f"Found {len(scenario_files)} scenario files\n")
    
    # Validate each scenario
    results = []
    for scenario_file in scenario_files:
        result = validate_scenario_file(scenario_file)
        results.append(result)
    
    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)
    
    total_events = sum(r["total"] for r in results)
    total_valid = sum(r["valid"] for r in results)
    total_invalid = sum(r["invalid"] for r in results)
    overall_pass_rate = (total_valid / total_events * 100) if total_events > 0 else 0
    
    print(f"\nOverall Statistics:")
    print(f"  Total events: {total_events}")
    print(f"  Valid:   {total_valid} ({overall_pass_rate:.1f}%)")
    print(f"  Invalid: {total_invalid}")
    
    print(f"\nPer-Scenario Results:")
    for result in results:
        status = "✅" if result["invalid"] == 0 else "⚠️"
        print(f"  {status} {result['file']}: {result['pass_rate']:.1f}% pass rate ({result['valid']}/{result['total']})")
    
    if total_invalid == 0:
        print(f"\n✅ SUCCESS: All {total_events} test events are valid!")
        print("Ready for Kafka producer and pipeline testing")
        return 0
    else:
        print(f"\n⚠️  WARNING: {total_invalid} invalid events found")
        print("Review errors above and fix test data generation")
        return 1


if __name__ == "__main__":
    sys.exit(main())
