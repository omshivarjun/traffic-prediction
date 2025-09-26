# Traffic Prediction Stream Processing

This module contains the stream processing pipeline for the Traffic Prediction system. It uses Kafka Streams to process traffic data in real-time and generate predictions.

## Components

- **TrafficEventProcessor**: Processes raw traffic events and generates aggregated traffic data
- **TrafficIncidentProcessor**: Processes traffic incidents and correlates them with traffic data
- **TrafficPredictionProcessor**: Generates traffic predictions based on processed traffic data

## Architecture

The stream processing pipeline follows these steps:

1. Consume raw traffic events from Kafka topics
2. Process and aggregate traffic data using windowed operations
3. Join traffic data with incident data to enrich the context
4. Generate predictions using trained models
5. Publish processed data and predictions to Kafka topics
6. Sink data to HDFS for long-term storage and batch processing

## Configuration

The stream processing application can be configured using the `application.properties` file. Key configurations include:

- Kafka broker addresses
- Input and output topic names
- Window sizes for aggregation
- Processing parameters

## Running the Application

To run the stream processing application:

```bash
# Build the application
npm run build:stream

# Run the application
npm run start:stream
```