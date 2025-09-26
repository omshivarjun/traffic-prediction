import { NextRequest, NextResponse } from 'next/server';

interface TrafficPrediction {
  sensor_id: string;
  timestamp: string;
  road_name: string;
  latitude: number;
  longitude: number;
  predicted_speed: number;
  actual_speed: number;
  model_name: string;
  prediction_timestamp: string;
  confidence_score: number;
}

// Mock data for demonstration - replace with real Kafka consumer
const generateMockPredictions = (count: number = 10): TrafficPrediction[] => {
  const sensors = [
    { id: 'METR_LA_001', lat: 33.941009, lng: -118.030741, road: 'I-405 N at Culver Blvd' },
    { id: 'METR_LA_002', lat: 34.052235, lng: -118.243683, road: 'US-101 W at Wilshire Blvd' },
    { id: 'METR_LA_003', lat: 34.095, lng: -118.330, road: 'I-10 E at Santa Monica Blvd' },
    { id: 'METR_LA_004', lat: 34.070, lng: -118.200, road: 'I-110 S at Olympic Blvd' },
    { id: 'METR_LA_005', lat: 34.100, lng: -118.350, road: 'I-5 N at Sunset Blvd' },
    { id: 'METR_LA_006', lat: 34.020, lng: -118.280, road: 'I-10 W at Downtown LA' },
    { id: 'METR_LA_007', lat: 34.140, lng: -118.250, road: 'I-5 N at Burbank' }
  ];

  const models = ['sklearn_rf', 'sklearn_gbt', 'spark_rf_speed', 'spark_gbt_speed'];
  const predictions: TrafficPrediction[] = [];

  for (let i = 0; i < count; i++) {
    const sensor = sensors[Math.floor(Math.random() * sensors.length)];
    const model = models[Math.floor(Math.random() * models.length)];
    
    const actualSpeed = 15 + Math.random() * 50;
    const predictedSpeed = actualSpeed + (Math.random() - 0.5) * 10;
    
    predictions.push({
      sensor_id: sensor.id,
      timestamp: new Date(Date.now() - Math.random() * 3600000).toISOString(), // Random within last hour
      road_name: sensor.road,
      latitude: sensor.lat,
      longitude: sensor.lng,
      predicted_speed: Math.max(0, predictedSpeed),
      actual_speed: actualSpeed,
      model_name: model,
      prediction_timestamp: new Date().toISOString(),
      confidence_score: 0.8 + Math.random() * 0.2
    });
  }

  return predictions.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
};

export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const limit = parseInt(searchParams.get('limit') || '50');
    const model = searchParams.get('model');

    // TODO: Replace with real Kafka consumer or database query
    // Example: const predictions = await kafkaConsumer.getLatestPredictions(limit);
    let predictions = generateMockPredictions(limit);

    // Filter by model if specified
    if (model && model !== 'all') {
      predictions = predictions.filter(p => p.model_name === model);
    }

    // Calculate statistics
    const stats = {
      total_predictions: predictions.length,
      avg_predicted_speed: predictions.length > 0 
        ? predictions.reduce((sum, p) => sum + p.predicted_speed, 0) / predictions.length 
        : 0,
      avg_actual_speed: predictions.length > 0 
        ? predictions.reduce((sum, p) => sum + p.actual_speed, 0) / predictions.length 
        : 0,
      high_congestion_count: predictions.filter(p => p.predicted_speed < 20).length,
      model_accuracy: predictions.length > 0 
        ? predictions.reduce((sum, p) => {
            const error = Math.abs(p.predicted_speed - p.actual_speed);
            const relativeError = error / Math.max(p.actual_speed, 1);
            return sum + Math.max(0, 1 - relativeError);
          }, 0) / predictions.length 
        : 0
    };

    return NextResponse.json({
      success: true,
      data: {
        predictions,
        stats,
        timestamp: new Date().toISOString()
      }
    });

  } catch (error) {
    console.error('Error fetching predictions:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to fetch predictions' },
      { status: 500 }
    );
  }
}

// POST endpoint for receiving real-time predictions from Kafka
export async function POST(request: NextRequest) {
  try {
    const prediction: TrafficPrediction = await request.json();
    
    // TODO: Validate prediction data and store in database/cache
    // TODO: Broadcast to WebSocket clients for real-time updates
    
    console.log('Received prediction:', prediction);
    
    return NextResponse.json({
      success: true,
      message: 'Prediction received',
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error('Error processing prediction:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to process prediction' },
      { status: 500 }
    );
  }
}