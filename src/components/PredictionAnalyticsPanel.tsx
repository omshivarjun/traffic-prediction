/**
 * Prediction Analytics Panel
 * Displays real-time metrics and statistics for ML predictions
 */

'use client';

import { TrafficPrediction, PredictionStats } from '@/hooks/usePredictions';
import { useMemo } from 'react';

interface PredictionAnalyticsPanelProps {
  predictions: TrafficPrediction[];
  stats: PredictionStats;
  isConnected: boolean;
}

/**
 * Calculate prediction rate (predictions per minute)
 */
function calculatePredictionRate(predictions: TrafficPrediction[]): number {
  if (predictions.length < 2) return 0;

  const timestamps = predictions.map((p) => p.timestamp).sort((a, b) => a - b);
  const timeSpan = timestamps[timestamps.length - 1] - timestamps[0];
  
  if (timeSpan === 0) return 0;

  // Convert to predictions per minute
  return (predictions.length / (timeSpan / 1000)) * 60;
}

/**
 * Calculate average accuracy
 */
function calculateAvgAccuracy(predictions: TrafficPrediction[]): number {
  if (predictions.length === 0) return 0;

  const accuracies = predictions.map((p) => {
    const relativeError = Math.abs(p.speed_diff) / Math.max(p.current_speed, 1);
    return Math.max(0, (1 - relativeError) * 100);
  });

  return accuracies.reduce((sum, acc) => sum + acc, 0) / accuracies.length;
}

/**
 * Get category display info
 */
function getCategoryInfo(category: string) {
  switch (category) {
    case 'free_flow':
      return { label: 'Free Flow', color: '#22c55e', icon: '🟢' };
    case 'moderate_traffic':
      return { label: 'Moderate Traffic', color: '#eab308', icon: '🟡' };
    case 'heavy_traffic':
      return { label: 'Heavy Traffic', color: '#f97316', icon: '🟠' };
    case 'severe_congestion':
      return { label: 'Severe Congestion', color: '#ef4444', icon: '🔴' };
    default:
      return { label: 'Unknown', color: '#9ca3af', icon: '⚪' };
  }
}

export function PredictionAnalyticsPanel({
  predictions,
  stats,
  isConnected,
}: PredictionAnalyticsPanelProps) {
  const predictionRate = useMemo(
    () => calculatePredictionRate(predictions),
    [predictions]
  );

  const avgAccuracy = useMemo(
    () => calculateAvgAccuracy(predictions),
    [predictions]
  );

  const categoryEntries = Object.entries(stats.categories).filter(([_, count]) => count > 0);
  const totalCategorized = Object.values(stats.categories).reduce((sum, count) => sum + count, 0);

  return (
    <div className="bg-white rounded-lg shadow-lg p-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <h2 className="text-2xl font-bold text-gray-900">Prediction Analytics</h2>
        <div
          className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${
            isConnected
              ? 'bg-green-100 text-green-700'
              : 'bg-red-100 text-red-700'
          }`}
        >
          <div
            className={`w-2 h-2 rounded-full ${
              isConnected ? 'bg-green-500' : 'bg-red-500'
            }`}
          />
          {isConnected ? 'Live' : 'Disconnected'}
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {/* Total Predictions */}
        <div className="bg-gradient-to-br from-blue-50 to-blue-100 rounded-lg p-4">
          <p className="text-xs text-blue-600 font-medium mb-1">Total Predictions</p>
          <p className="text-3xl font-bold text-blue-900">{stats.total}</p>
        </div>

        {/* Prediction Rate */}
        <div className="bg-gradient-to-br from-purple-50 to-purple-100 rounded-lg p-4">
          <p className="text-xs text-purple-600 font-medium mb-1">Predictions/Min</p>
          <p className="text-3xl font-bold text-purple-900">{predictionRate.toFixed(1)}</p>
        </div>

        {/* Average Accuracy */}
        <div className="bg-gradient-to-br from-green-50 to-green-100 rounded-lg p-4">
          <p className="text-xs text-green-600 font-medium mb-1">Avg Accuracy</p>
          <p className="text-3xl font-bold text-green-900">{avgAccuracy.toFixed(1)}%</p>
        </div>

        {/* Avg Speed Diff */}
        <div className="bg-gradient-to-br from-orange-50 to-orange-100 rounded-lg p-4">
          <p className="text-xs text-orange-600 font-medium mb-1">Avg Speed Diff</p>
          <p
            className={`text-3xl font-bold ${
              stats.avgSpeedDiff > 0 ? 'text-green-900' : 'text-red-900'
            }`}
          >
            {stats.avgSpeedDiff > 0 ? '+' : ''}
            {stats.avgSpeedDiff.toFixed(1)}
          </p>
        </div>
      </div>

      {/* Category Distribution */}
      <div className="mb-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-3">Traffic Conditions</h3>
        
        {categoryEntries.length === 0 ? (
          <p className="text-gray-500 text-sm">No predictions yet...</p>
        ) : (
          <div className="space-y-3">
            {categoryEntries.map(([category, count]) => {
              const info = getCategoryInfo(category);
              const percentage = totalCategorized > 0 ? (count / totalCategorized) * 100 : 0;

              return (
                <div key={category}>
                  <div className="flex justify-between items-center mb-1">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{info.icon}</span>
                      <span className="text-sm font-medium text-gray-700">{info.label}</span>
                    </div>
                    <span className="text-sm font-semibold text-gray-900">
                      {count} ({percentage.toFixed(1)}%)
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className="h-2 rounded-full transition-all duration-300"
                      style={{
                        width: `${percentage}%`,
                        backgroundColor: info.color,
                      }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Model Information */}
      <div className="pt-4 border-t border-gray-200">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="text-gray-600">Model Type</p>
            <p className="font-semibold text-gray-900">Linear Regression</p>
          </div>
          <div>
            <p className="text-gray-600">Model Accuracy</p>
            <p className="font-semibold text-gray-900">99.99% (R² = 0.9999)</p>
          </div>
          <div>
            <p className="text-gray-600">Features</p>
            <p className="font-semibold text-gray-900">18 Features</p>
          </div>
          <div>
            <p className="text-gray-600">RMSE</p>
            <p className="font-semibold text-gray-900">0.44 mph</p>
          </div>
        </div>
      </div>

      {/* Status Messages */}
      {!isConnected && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-700">
            ⚠️ Prediction stream disconnected. Attempting to reconnect...
          </p>
        </div>
      )}

      {isConnected && predictions.length === 0 && (
        <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-sm text-blue-700">
            📡 Connected to prediction service. Waiting for traffic data...
          </p>
        </div>
      )}
    </div>
  );
}

export default PredictionAnalyticsPanel;
