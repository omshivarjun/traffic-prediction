/**
 * Server-Sent Events (SSE) endpoint for real-time predictions
 * Streams predictions from Kafka to connected clients
 */

import { NextRequest } from 'next/server';
import { getPredictionConsumer, TrafficPrediction } from '@/lib/kafka/predictionConsumer';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

/**
 * GET /api/predictions/stream
 * Server-Sent Events endpoint for real-time prediction updates
 */
export async function GET(request: NextRequest) {
  const encoder = new TextEncoder();
  const consumer = getPredictionConsumer();

  // Start consumer if not already running
  // Multiple SSE connections will share the same consumer instance
  if (!consumer.isRunning()) {
    try {
      console.log('🔌 Starting prediction consumer for SSE stream...');
      await consumer.start();
      console.log('✅ Prediction consumer started for SSE stream');
    } catch (error) {
      console.error('❌ Failed to start prediction consumer:', error);
      
      // Return error in SSE format instead of HTTP 500
      const stream = new ReadableStream({
        start(controller) {
          const errorMessage = `data: ${JSON.stringify({ 
            type: 'error', 
            message: 'Failed to connect to prediction service. Retrying...',
            error: error instanceof Error ? error.message : 'Unknown error',
            timestamp: Date.now()
          })}\n\n`;
          controller.enqueue(encoder.encode(errorMessage));
          
          // Close after 1 second
          setTimeout(() => {
            controller.close();
          }, 1000);
        },
      });

      return new Response(stream, {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache, no-transform',
          'Connection': 'keep-alive',
          'X-Accel-Buffering': 'no',
        },
      });
    }
  } else {
    console.log('♻️ Reusing existing prediction consumer for new SSE connection');
  }

  // Create SSE stream
  const stream = new ReadableStream({
    start(controller) {
      // Send initial connection message
      const initialMessage = `data: ${JSON.stringify({ 
        type: 'connected', 
        message: 'Prediction stream connected',
        timestamp: Date.now()
      })}\n\n`;
      controller.enqueue(encoder.encode(initialMessage));

      // Send current predictions
      const currentPredictions = consumer.getAllPredictions();
      if (currentPredictions.length > 0) {
        const predictionMessage = `data: ${JSON.stringify({
          type: 'initial',
          predictions: currentPredictions,
          count: currentPredictions.length
        })}\n\n`;
        controller.enqueue(encoder.encode(predictionMessage));
      }

      // Subscribe to new predictions
      const unsubscribe = consumer.onPrediction((prediction: TrafficPrediction) => {
        try {
          const message = `data: ${JSON.stringify({
            type: 'prediction',
            data: prediction
          })}\n\n`;
          controller.enqueue(encoder.encode(message));
        } catch (error) {
          console.error('❌ Error sending prediction via SSE:', error);
        }
      });

      // Send stats every 10 seconds
      const statsInterval = setInterval(() => {
        try {
          const stats = consumer.getStats();
          const statsMessage = `data: ${JSON.stringify({
            type: 'stats',
            data: stats
          })}\n\n`;
          controller.enqueue(encoder.encode(statsMessage));
        } catch (error) {
          console.error('❌ Error sending stats via SSE:', error);
        }
      }, 10000);

      // Cleanup on close
      request.signal.addEventListener('abort', () => {
        unsubscribe();
        clearInterval(statsInterval);
        console.log('📡 Client disconnected from prediction stream');
      });
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
}
