/**
 * Debug endpoint to check consumer state
 */
import { NextResponse } from 'next/server';
import { getPredictionConsumer } from '@/lib/kafka/predictionConsumer';

export const dynamic = 'force-dynamic';

export async function GET() {
  const consumer = getPredictionConsumer();
  
  const status = {
    isRunning: consumer.isRunning(),
    predictionCount: consumer.getAllPredictions().length,
    predictions: consumer.getAllPredictions(),
    stats: consumer.getStats(),
  };
  
  return NextResponse.json(status, { status: 200 });
}
