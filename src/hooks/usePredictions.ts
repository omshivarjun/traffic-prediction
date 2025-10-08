/**
 * React hook for consuming real-time traffic predictions
 * Connects to SSE endpoint and manages prediction state
 */

import { useEffect, useState, useCallback, useRef } from 'react';

export interface TrafficPrediction {
  segment_id: string;
  timestamp: number;
  current_speed: number;
  predicted_speed: number;
  current_volume: number;
  prediction_time: string;
  speed_diff: number;
  category: 'free_flow' | 'moderate_traffic' | 'heavy_traffic' | 'severe_congestion';
  coordinates?: {
    latitude: number;
    longitude: number;
  };
}

export interface PredictionStats {
  total: number;
  categories: {
    free_flow: number;
    moderate_traffic: number;
    heavy_traffic: number;
    severe_congestion: number;
  };
  avgSpeedDiff: number;
}

interface SSEMessage {
  type: 'connected' | 'initial' | 'prediction' | 'stats' | 'error';
  message?: string;
  error?: string;
  predictions?: TrafficPrediction[];
  data?: TrafficPrediction | PredictionStats;
  count?: number;
  timestamp?: number;
}

interface UsePredictionsOptions {
  maxPredictions?: number;
  autoConnect?: boolean;
}

export function usePredictions(options: UsePredictionsOptions = {}) {
  const { maxPredictions = 100, autoConnect = true } = options;

  const [predictions, setPredictions] = useState<Map<string, TrafficPrediction>>(new Map());
  const [stats, setStats] = useState<PredictionStats>({
    total: 0,
    categories: {
      free_flow: 0,
      moderate_traffic: 0,
      heavy_traffic: 0,
      severe_congestion: 0,
    },
    avgSpeedDiff: 0,
  });
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);

  const MAX_RECONNECT_ATTEMPTS = 5;
  const RECONNECT_DELAY = 3000;

  /**
   * Connect to SSE stream
   */
  const connect = useCallback(() => {
    if (eventSourceRef.current) {
      console.warn('⚠️ Already connected to prediction stream');
      return;
    }

    setIsConnecting(true);
    setError(null);

    try {
      const eventSource = new EventSource('/api/predictions/stream');
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        console.log('✅ Connected to prediction stream');
        setIsConnected(true);
        setIsConnecting(false);
        reconnectAttemptsRef.current = 0;
      };

      eventSource.onmessage = (event) => {
        try {
          const message: SSEMessage = JSON.parse(event.data);

          switch (message.type) {
            case 'connected':
              console.log('📡 Prediction stream ready:', message.message);
              break;

            case 'initial':
              // Load initial predictions
              if (message.predictions) {
                const newPredictions = new Map<string, TrafficPrediction>();
                message.predictions.forEach((pred) => {
                  newPredictions.set(pred.segment_id, pred);
                });
                setPredictions(newPredictions);
                console.log(`📊 Loaded ${message.count} initial predictions`);
              }
              break;

            case 'prediction':
              // Add new prediction
              if (message.data) {
                const pred = message.data as TrafficPrediction;
                setPredictions((prev) => {
                  const updated = new Map(prev);
                  updated.set(pred.segment_id, pred);

                  // Limit size
                  if (updated.size > maxPredictions) {
                    const firstKey = updated.keys().next().value;
                    if (firstKey !== undefined) {
                      updated.delete(firstKey);
                    }
                  }

                  return updated;
                });
                console.log(
                  `🚦 Prediction: ${pred.segment_id} - ${pred.current_speed.toFixed(1)} → ${pred.predicted_speed.toFixed(1)} mph [${pred.category}]`
                );
              }
              break;

            case 'stats':
              // Update stats
              if (message.data) {
                setStats(message.data as PredictionStats);
              }
              break;

            case 'error':
              // Handle error from server
              console.error('🔴 Server error:', message.message);
              setError(message.message || 'Server connection error');
              setIsConnected(false);
              setIsConnecting(false);
              
              // Attempt reconnection after delay
              if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttemptsRef.current++;
                console.log(
                  `🔄 Reconnecting after server error... (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`
                );
                reconnectTimeoutRef.current = setTimeout(() => {
                  connect();
                }, RECONNECT_DELAY);
              }
              break;

            default:
              console.warn('⚠️ Unknown message type:', message.type);
          }
        } catch (error) {
          console.error('❌ Error parsing SSE message:', error);
        }
      };

      eventSource.onerror = (error) => {
        console.error('❌ SSE connection error:', error);
        setIsConnected(false);
        setIsConnecting(false);
        setError('Connection lost. Attempting to reconnect...');

        eventSource.close();
        eventSourceRef.current = null;

        // Attempt reconnection
        if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current++;
          console.log(
            `🔄 Reconnecting... (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`
          );

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, RECONNECT_DELAY);
        } else {
          setError('Failed to connect after multiple attempts. Please refresh the page.');
        }
      };
    } catch (error) {
      console.error('❌ Error creating EventSource:', error);
      setIsConnecting(false);
      setError('Failed to connect to prediction service');
    }
  }, [maxPredictions]);

  /**
   * Disconnect from SSE stream
   */
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      setIsConnected(false);
      console.log('📡 Disconnected from prediction stream');
    }
  }, []);

  /**
   * Get predictions as array
   */
  const getPredictionsArray = useCallback((): TrafficPrediction[] => {
    return Array.from(predictions.values());
  }, [predictions]);

  /**
   * Get prediction for specific segment
   */
  const getPrediction = useCallback(
    (segmentId: string): TrafficPrediction | undefined => {
      return predictions.get(segmentId);
    },
    [predictions]
  );

  /**
   * Clear all predictions
   */
  const clearPredictions = useCallback(() => {
    setPredictions(new Map());
  }, []);

  // Auto-connect on mount
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  return {
    predictions: getPredictionsArray(),
    predictionMap: predictions,
    stats,
    isConnected,
    isConnecting,
    error,
    connect,
    disconnect,
    getPrediction,
    clearPredictions,
  };
}

export default usePredictions;
