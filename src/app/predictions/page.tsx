'use client';

import dynamic from 'next/dynamic';
import { usePredictions } from '@/hooks/usePredictions';
import PredictionAnalyticsPanel from '@/components/PredictionAnalyticsPanel';

// Dynamic import to avoid SSR issues with Leaflet
const TrafficMapWithPredictions = dynamic(
  () => import('@/components/TrafficMapWithPredictions'),
  { ssr: false }
);

export default function PredictionsPage() {
  const { predictions, isConnected, stats, error } = usePredictions();

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">
                LA Traffic Predictions
              </h1>
              <p className="mt-1 text-sm text-gray-600">
                Real-time machine learning predictions from Kafka stream
              </p>
            </div>
            <div className="flex items-center space-x-3">
              <div className={`flex items-center space-x-2 px-3 py-1 rounded-full ${
                isConnected 
                  ? 'bg-green-100 text-green-800' 
                  : 'bg-red-100 text-red-800'
              }`}>
                <div className={`w-2 h-2 rounded-full ${
                  isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
                }`}></div>
                <span className="text-sm font-medium">
                  {isConnected ? 'Live' : 'Disconnected'}
                </span>
              </div>
              {error && (
                <div className="text-sm text-red-600 bg-red-50 px-3 py-1 rounded-full">
                  Connection Error
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Map - Takes 2 columns on large screens */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
              <div className="h-[600px]">
                <TrafficMapWithPredictions data={[]} showPredictions={true} />
              </div>
            </div>
            
            {/* Legend */}
            <div className="mt-4 bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <h3 className="text-sm font-semibold text-gray-900 mb-3">
                Traffic Speed Legend
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                <div className="flex items-center space-x-2">
                  <div className="w-4 h-4 rounded-full bg-green-500"></div>
                  <span className="text-gray-700">Free Flow (&gt;60 mph)</span>
                </div>
                <div className="flex items-center space-x-2">
                  <div className="w-4 h-4 rounded-full bg-yellow-500"></div>
                  <span className="text-gray-700">Light (45-60 mph)</span>
                </div>
                <div className="flex items-center space-x-2">
                  <div className="w-4 h-4 rounded-full bg-orange-500"></div>
                  <span className="text-gray-700">Moderate (30-45 mph)</span>
                </div>
                <div className="flex items-center space-x-2">
                  <div className="w-4 h-4 rounded-full bg-red-500"></div>
                  <span className="text-gray-700">Heavy (&lt;30 mph)</span>
                </div>
              </div>
            </div>
          </div>

          {/* Analytics Panel - Takes 1 column */}
          <div className="lg:col-span-1">
            <PredictionAnalyticsPanel 
              predictions={predictions}
              isConnected={isConnected}
              stats={stats}
            />
          </div>
        </div>

        {/* Connection Status */}
        {!isConnected && !error && (
          <div className="mt-6 bg-yellow-50 border-l-4 border-yellow-400 p-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-yellow-700">
                  Connecting to prediction stream...
                </p>
              </div>
            </div>
          </div>
        )}

        {error && (
          <div className="mt-6 bg-red-50 border-l-4 border-red-400 p-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-red-700">
                  Error connecting to prediction stream: {error}
                </p>
                <p className="text-xs text-red-600 mt-1">
                  Check that the Next.js server and Kafka consumer are running.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Instructions */}
        {predictions.length === 0 && isConnected && (
          <div className="mt-6 bg-blue-50 border-l-4 border-blue-400 p-4">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-blue-700">
                  Connected! Waiting for predictions from Kafka...
                </p>
                <p className="text-xs text-blue-600 mt-1">
                  Send test events: <code className="bg-blue-100 px-1 py-0.5 rounded">.\scripts\send-test-events.ps1</code>
                </p>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
