import { NextRequest, NextResponse } from 'next/server';
import { getPredictionConsumer, TrafficPrediction } from '@/lib/kafka/predictionConsumer';

export const dynamic = 'force-dynamic';

/**
 * GET /api/predictions
 * Returns the latest predictions from Kafka consumer
 */
export async function GET(request: NextRequest) {
  try {
    const consumer = getPredictionConsumer();

    // Start consumer if not running
    if (!consumer.isRunning()) {
      console.log('🚀 Starting prediction consumer...');
      await consumer.start();
    }

    const predictions = consumer.getAllPredictions();
    const stats = consumer.getStats();

    // Calculate additional statistics
    const enhancedStats = {
      ...stats,
      avg_predicted_speed: predictions.length > 0
        ? predictions.reduce((sum, p) => sum + p.predicted_speed, 0) / predictions.length
        : 0,
      avg_current_speed: predictions.length > 0
        ? predictions.reduce((sum, p) => sum + p.current_speed, 0) / predictions.length
        : 0,
      high_congestion_count: predictions.filter(p => p.category === 'severe_congestion').length,
      moderate_congestion_count: predictions.filter(p => p.category === 'heavy_traffic').length,
    };

    return NextResponse.json({
      success: true,
      data: {
        predictions,
        stats: enhancedStats,
        timestamp: new Date().toISOString()
      }
    });

  } catch (error) {
    console.error('❌ Error fetching predictions:', error);
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