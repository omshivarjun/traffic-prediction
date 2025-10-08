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
  const fs = require('fs');
  const logPath = 'c:\\traffic-prediction\\sse-route-debug.log';
  const log = (msg: string) => {
    const timestamp = new Date().toISOString();
    fs.appendFileSync(logPath, `[${timestamp}] ${msg}\n`);
    console.log(msg);
  };

  log(`📥 SSE route GET called - PID: ${process.pid}`);
  
  const encoder = new TextEncoder();
  const consumer = getPredictionConsumer();

  log(`🔍 Consumer isRunning: ${consumer.isRunning()}`);
  
  // Start consumer if not already running
  // Multiple SSE connections will share the same consumer instance
  if (!consumer.isRunning()) {
    try {
      log('🔌 Starting prediction consumer for SSE stream...');
      await consumer.start();
      log('✅ Prediction consumer started for SSE stream');
    } catch (error) {
      log(`❌ Failed to start prediction consumer: ${error}`);
      
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
      console.log('🌊 SSE stream started');
      
      // Send initial connection message
      const initialMessage = `data: ${JSON.stringify({ 
        type: 'connected', 
        message: 'Prediction stream connected',
        timestamp: Date.now()
      })}\n\n`;
      controller.enqueue(encoder.encode(initialMessage));
      console.log('✅ Sent "connected" message to client');

      // Send current predictions
      const currentPredictions = consumer.getAllPredictions();
      console.log(`📊 Current predictions in cache: ${currentPredictions.length}`);
      if (currentPredictions.length > 0) {
        const predictionMessage = `data: ${JSON.stringify({
          type: 'initial',
          predictions: currentPredictions,
          count: currentPredictions.length
        })}\n\n`;
        controller.enqueue(encoder.encode(predictionMessage));
        console.log(`✅ Sent ${currentPredictions.length} initial predictions to client`);
      } else {
        console.log('⚠️ No predictions in cache yet, waiting for Kafka messages...');
      }

      // Subscribe to new predictions
      console.log('🔔 Registering onPrediction callback');
      let predictionCount = 0;
      const unsubscribe = consumer.onPrediction((prediction: TrafficPrediction) => {
        try {
          console.log(`🚀 SSE callback triggered for segment: ${prediction.segment_id}`);
          const message = `data: ${JSON.stringify({
            type: 'prediction',
            data: prediction
          })}\n\n`;
          controller.enqueue(encoder.encode(message));
          console.log(`✅ Sent prediction via SSE: ${prediction.segment_id}`);
          
          // Send updated stats every 10 predictions (for real-time analytics updates)
          predictionCount++;
          if (predictionCount % 10 === 0) {
            const stats = consumer.getStats();
            const statsMessage = `data: ${JSON.stringify({
              type: 'stats',
              data: stats
            })}\n\n`;
            controller.enqueue(encoder.encode(statsMessage));
            console.log(`📊 Sent updated stats (after ${predictionCount} predictions)`);
          }
        } catch (error) {
          console.error('❌ Error sending prediction via SSE:', error);
        }
      });
      console.log('✅ onPrediction callback registered');

      // Send stats every 2 seconds for real-time updates
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
      }, 2000); // Updated from 10000 to 2000 (2 seconds)

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
