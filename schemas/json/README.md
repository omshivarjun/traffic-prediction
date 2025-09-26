# JSON Schema Documentation for Traffic Prediction System

## Overview
This document describes the JSON schemas used for message validation in the traffic prediction system's Kafka topics. These schemas complement the existing Avro schemas and provide validation for different message formats across the pipeline (Task 7.3).

## Schema Files

### 1. Traffic Raw Event Schema (`traffic-raw-event.json`)
**Topic:** `traffic-raw`  
**Description:** Schema for raw sensor data and traffic events from various sources.

**Key Fields:**
- `event_id`: Unique identifier for each traffic event
- `segment_id`: Road segment identifier for location-based processing
- `timestamp`: Event timestamp in epoch milliseconds
- `speed`: Average vehicle speed in km/h (optional)
- `volume`: Number of vehicles detected (optional)
- `occupancy`: Sensor occupancy percentage 0-100 (optional)
- `coordinates`: Geographic location (latitude/longitude)
- `source`: Data source type (SENSOR, CAMERA, PROBE, etc.)
- `quality_score`: Data quality score 0-1

**Usage Example:**
```json
{
  "event_id": "EVT_20250919_001",
  "segment_id": "SEG_I405_N_001",
  "timestamp": 1726750800000,
  "speed": 65.5,
  "volume": 120,
  "occupancy": 15.2,
  "coordinates": {
    "latitude": 34.0522,
    "longitude": -118.2437
  },
  "source": "SENSOR",
  "quality_score": 0.95
}
```

### 2. Traffic Processed Aggregate Schema (`traffic-processed-aggregate.json`)
**Topic:** `traffic-processed`  
**Description:** Schema for aggregated traffic data processed by stream processing components.

**Key Fields:**
- `aggregate_id`: Unique identifier for the processed aggregate
- `segment_id`: Road segment identifier
- `window_start`/`window_end`: Aggregation time window boundaries
- `avg_speed`: Average speed across the aggregation window
- `vehicle_count`: Total vehicles in the window
- `occupancy_avg`: Average occupancy percentage
- `congestion_level`: Calculated congestion level (FREE_FLOW to SEVERE)
- `quality_score`: Overall data quality score
- `processing_metadata`: Information about the aggregation process

**Congestion Levels:**
- `FREE_FLOW`: Normal traffic flow
- `LIGHT`: Light congestion
- `MODERATE`: Moderate congestion  
- `HEAVY`: Heavy congestion
- `SEVERE`: Severe congestion/gridlock

### 3. Traffic Alert Schema (`traffic-alert.json`)
**Topic:** `traffic-alerts`  
**Description:** Schema for traffic incidents, alerts, and anomalies.

**Key Fields:**
- `alert_id`: Unique identifier for the alert
- `alert_type`: Type of alert (ACCIDENT, ROADWORK, WEATHER, etc.)
- `severity`: Severity level (LOW, MEDIUM, HIGH, CRITICAL)
- `status`: Current alert status (ACTIVE, RESOLVED, INVESTIGATING, CLEARED)
- `affected_lanes`: Array of affected lane numbers
- `traffic_impact`: Impact metrics (speed reduction, delays, affected distance)
- `detection_source`: How the alert was detected
- `confidence_score`: Confidence in the alert accuracy

**Alert Types:**
- `ACCIDENT`: Traffic accidents
- `ROADWORK`: Construction or maintenance
- `WEATHER`: Weather-related impacts
- `CONGESTION`: Traffic congestion alerts
- `INCIDENT`: General traffic incidents
- `LANE_CLOSURE`: Lane closures
- `VEHICLE_BREAKDOWN`: Broken down vehicles
- `HAZARD`: Road hazards
- `SPECIAL_EVENT`: Special events affecting traffic
- `SYSTEM_ANOMALY`: System-detected anomalies

### 4. Traffic Prediction Schema (`traffic-prediction.json`)
**Topic:** `traffic-predictions`  
**Description:** Schema for ML-generated traffic predictions and forecasts.

**Key Fields:**
- `prediction_id`: Unique identifier for the prediction
- `prediction_horizon`: Prediction horizon in minutes
- `predicted_speed`/`predicted_volume`: Predicted traffic metrics
- `predicted_congestion_level`: Predicted congestion level
- `confidence_score`: Prediction confidence score
- `uncertainty_bounds`: Upper and lower bounds for predictions
- `model_version`: Version of the ML model used
- `features_used`: List of features used in the prediction
- `historical_context`: Historical data context
- `external_factors`: External factors considered

**ML Model Types:**
- `LINEAR_REGRESSION`: Linear regression models
- `RANDOM_FOREST`: Random forest models
- `NEURAL_NETWORK`: Neural network models
- `LSTM`: Long Short-Term Memory networks
- `ARIMA`: AutoRegressive Integrated Moving Average
- `ENSEMBLE`: Ensemble methods

## Schema Validation

### Integration Points
1. **Kafka Producers**: Validate messages before publishing to topics
2. **Stream Processing**: Validate incoming messages in processing pipelines
3. **API Endpoints**: Validate API request/response payloads
4. **Data Quality Checks**: Ensure data meets schema requirements

### Validation Implementation
```javascript
// Example validation using a JSON schema library
const Ajv = require('ajv');
const ajv = new Ajv();

// Load schema
const trafficEventSchema = require('./traffic-raw-event.json');
const validate = ajv.compile(trafficEventSchema);

// Validate message
function validateTrafficEvent(message) {
  const valid = validate(message);
  if (!valid) {
    console.error('Validation errors:', validate.errors);
    return false;
  }
  return true;
}
```

## Schema Evolution

### Version Management
- Schemas use semantic versioning in the `$id` field
- Backward compatibility maintained through optional fields
- New fields added as optional to prevent breaking changes
- Deprecated fields marked but maintained for compatibility

### Migration Strategy
1. Add new optional fields to existing schemas
2. Update consumers to handle new fields gracefully  
3. Update producers to include new fields
4. Mark old fields as deprecated in documentation
5. Remove deprecated fields in major version updates

## Quality Assurance

### Required Fields
All schemas define required fields that must be present in valid messages:
- Identifiers (event_id, segment_id, etc.)
- Timestamps for temporal processing
- Core data fields for business logic
- Quality scores for data validation

### Data Validation Rules
- **Coordinates**: Latitude/longitude within valid ranges
- **Timestamps**: Epoch milliseconds within reasonable bounds
- **Enums**: Restricted to predefined values
- **Ranges**: Numeric fields with minimum/maximum constraints
- **Patterns**: String fields with regex validation

### Error Handling
- Invalid messages rejected with detailed error information
- Validation errors logged for monitoring and debugging
- Fallback processing for partially valid messages
- Dead letter queues for persistent validation failures

## Performance Considerations

### Schema Optimization
- Minimal required fields to reduce message size
- Optional fields for extensibility without overhead
- Efficient data types (integers vs strings where appropriate)
- Compact enum values for frequently used fields

### Caching Strategy
- Compiled schema validators cached in memory
- Schema definitions loaded once at startup
- Validation results cached for identical messages
- Background schema reload for updates without downtime

This schema documentation ensures consistent message formats across all Kafka topics and provides a foundation for reliable data processing throughout the traffic prediction pipeline.