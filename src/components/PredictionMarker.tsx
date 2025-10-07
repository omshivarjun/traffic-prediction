/**
 * Prediction Marker Component
 * Displays ML predictions on the traffic map with color-coded visualization
 */

'use client';

import { CircleMarker, Popup } from 'react-leaflet';
import { TrafficPrediction } from '@/hooks/usePredictions';

interface PredictionMarkerProps {
  prediction: TrafficPrediction;
  coordinates: { latitude: number; longitude: number };
}

/**
 * Get marker color based on prediction category
 */
function getCategoryColor(category: TrafficPrediction['category']): string {
  switch (category) {
    case 'free_flow':
      return '#22c55e'; // green-500 - Free flow
    case 'moderate_traffic':
      return '#eab308'; // yellow-500 - Moderate traffic
    case 'heavy_traffic':
      return '#f97316'; // orange-500 - Heavy traffic
    case 'severe_congestion':
      return '#ef4444'; // red-500 - Severe congestion
    default:
      return '#9ca3af'; // gray-400 - Unknown
  }
}

/**
 * Get speed difference color (green for improvement, red for worsening)
 */
function getSpeedDiffColor(speedDiff: number): string {
  if (speedDiff > 5) return '#22c55e'; // Significant improvement
  if (speedDiff > 0) return '#86efac'; // Minor improvement
  if (speedDiff > -5) return '#fed7aa'; // Minor decline
  return '#ef4444'; // Significant decline
}

/**
 * Format category name for display
 */
function formatCategory(category: string): string {
  return category.replace(/_/g, ' ').replace(/\b\w/g, (l) => l.toUpperCase());
}

export function PredictionMarker({ prediction, coordinates }: PredictionMarkerProps) {
  const markerColor = getCategoryColor(prediction.category);
  const speedDiffColor = getSpeedDiffColor(prediction.speed_diff);

  // Calculate accuracy percentage (inverse of relative error)
  const relativeError = Math.abs(prediction.speed_diff) / Math.max(prediction.current_speed, 1);
  const accuracy = Math.max(0, (1 - relativeError) * 100);

  return (
    <CircleMarker
      center={[coordinates.latitude, coordinates.longitude]}
      radius={8}
      pathOptions={{
        fillColor: markerColor,
        fillOpacity: 0.7,
        color: '#ffffff',
        weight: 2,
        opacity: 0.9,
      }}
    >
      <Popup>
        <div className="p-3 min-w-[280px]">
          {/* Header */}
          <div className="mb-3 pb-2 border-b border-gray-200">
            <h3 className="font-bold text-lg text-gray-900">{prediction.segment_id}</h3>
            <p className="text-xs text-gray-500 mt-1">
              ML Prediction - {new Date(prediction.timestamp).toLocaleTimeString()}
            </p>
          </div>

          {/* Speed Information */}
          <div className="space-y-2 mb-3">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Current Speed:</span>
              <span className="font-semibold text-base">{prediction.current_speed.toFixed(1)} mph</span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Predicted Speed:</span>
              <span className="font-semibold text-base text-blue-600">
                {prediction.predicted_speed.toFixed(1)} mph
              </span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Difference:</span>
              <span
                className="font-semibold text-base"
                style={{ color: speedDiffColor }}
              >
                {prediction.speed_diff > 0 ? '+' : ''}
                {prediction.speed_diff.toFixed(1)} mph
              </span>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Volume:</span>
              <span className="font-semibold text-base">{prediction.current_volume} vehicles</span>
            </div>
          </div>

          {/* Category Badge */}
          <div className="mb-3">
            <div
              className="inline-block px-3 py-1 rounded-full text-sm font-medium text-white"
              style={{ backgroundColor: markerColor }}
            >
              {formatCategory(prediction.category)}
            </div>
          </div>

          {/* Accuracy Meter */}
          <div className="mb-2">
            <div className="flex justify-between items-center mb-1">
              <span className="text-xs text-gray-600">Prediction Accuracy:</span>
              <span className="text-xs font-semibold">{accuracy.toFixed(1)}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="h-2 rounded-full transition-all duration-300"
                style={{
                  width: `${accuracy}%`,
                  backgroundColor: accuracy > 90 ? '#22c55e' : accuracy > 70 ? '#eab308' : '#ef4444',
                }}
              />
            </div>
          </div>

          {/* Model Info */}
          <div className="mt-3 pt-2 border-t border-gray-200">
            <p className="text-xs text-gray-500">
              Model: Linear Regression | Time: {prediction.prediction_time}
            </p>
          </div>
        </div>
      </Popup>
    </CircleMarker>
  );
}

export default PredictionMarker;
