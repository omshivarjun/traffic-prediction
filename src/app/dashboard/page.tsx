'use client';

import { useEffect, useState, useRef } from 'react';
import dynamic from 'next/dynamic';

// Dynamic import for client-side only components
const Map = dynamic(() => import('../components/TrafficHeatmap'), { 
  ssr: false,
  loading: () => <div className="h-96 bg-gray-100 animate-pulse rounded-lg flex items-center justify-center">Loading Map...</div>
});

interface TrafficPrediction {
  sensor_id: string;
  segment_id?: string;
  timestamp: string;
  road_name?: string;
  predicted_speed: number;
  actual_speed?: number;
  current_speed?: number;
  model_name?: string;
  confidence_score: number;
  latitude?: number;
  longitude?: number;
  road_type?: string;
  lane_count?: number;
}

interface TrafficHeatmapData {
  latitude: number;
  longitude: number;
  speed: number;
  intensity: number;
  sensor_id: string;
  road_name?: string;
}

export default function TrafficDashboard() {
  const [predictions, setPredictions] = useState<TrafficPrediction[]>([]);
  const [heatmapData, setHeatmapData] = useState<TrafficHeatmapData[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);

  const getSpeedColor = (speed: number): string => {
    if (speed < 20) return 'text-red-600';
    if (speed < 40) return 'text-yellow-600';
    return 'text-green-600';
  };

  const generateMockPrediction = (): TrafficPrediction => {
    const sensors = [
      { id: 'METR_LA_001', road: 'I-405 N at Culver Blvd', lat: 34.0161, lng: -118.4542, type: 'highway' },
      { id: 'METR_LA_002', road: 'US-101 W at Wilshire Blvd', lat: 34.0575, lng: -118.2603, type: 'highway' },
      { id: 'METR_LA_003', road: 'I-10 E at Santa Monica Blvd', lat: 34.0426, lng: -118.2618, type: 'highway' },
      { id: 'METR_LA_004', road: 'I-110 S at Olympic Blvd', lat: 34.0347, lng: -118.2718, type: 'highway' },
      { id: 'METR_LA_005', road: 'Sunset Blvd at Vine St', lat: 34.0978, lng: -118.3267, type: 'arterial' },
      { id: 'METR_LA_006', road: 'Venice Blvd at Lincoln Blvd', lat: 34.0195, lng: -118.4531, type: 'arterial' },
      { id: 'METR_LA_007', road: 'Highland Ave at Hollywood Blvd', lat: 34.1022, lng: -118.3387, type: 'local' },
      { id: 'METR_LA_008', road: 'PCH at Malibu Canyon Rd', lat: 34.0356, lng: -118.6814, type: 'highway' }
    ];

    const models = ['sklearn_rf', 'sklearn_gbt', 'spark_rf_speed', 'spark_gbt_speed'];
    const sensor = sensors[Math.floor(Math.random() * sensors.length)];
    const model = models[Math.floor(Math.random() * models.length)];

    const actualSpeed = 15 + Math.random() * 50;
    const predictedSpeed = actualSpeed + (Math.random() - 0.5) * 10;

    return {
      sensor_id: sensor.id,
      segment_id: `seg_${sensor.id}`,
      timestamp: new Date().toISOString(),
      road_name: sensor.road,
      predicted_speed: Math.max(0, predictedSpeed),
      actual_speed: actualSpeed,
      current_speed: actualSpeed,
      model_name: model,
      confidence_score: 0.8 + Math.random() * 0.2,
      latitude: sensor.lat,
      longitude: sensor.lng,
      road_type: sensor.type,
      lane_count: sensor.type === 'highway' ? 4 : sensor.type === 'arterial' ? 3 : 2
    };
  };

  const convertToHeatmapData = (predictions: TrafficPrediction[]): TrafficHeatmapData[] => {
    return predictions
      .filter(p => p.latitude && p.longitude)
      .map(p => ({
        latitude: p.latitude!,
        longitude: p.longitude!,
        speed: p.current_speed || p.actual_speed || p.predicted_speed,
        intensity: Math.max(1, 10 - (p.current_speed || p.predicted_speed) / 10),
        sensor_id: p.sensor_id,
        road_name: p.road_name,
        road_type: p.road_type,
        lane_count: p.lane_count,
        predicted_speed: p.predicted_speed,
        confidence_score: p.confidence_score
      }));
  };

  const generateMockData = () => {
    const newPredictions = Array.from({ length: 8 }, () => generateMockPrediction());
    setPredictions(newPredictions);
    setHeatmapData(convertToHeatmapData(newPredictions));
    setLastUpdate(new Date().toLocaleTimeString());
    setIsLoading(false);
  };

  useEffect(() => {
    // Initial data load
    generateMockData();
    setIsConnected(true);

    // Update data every 5 seconds
    const interval = setInterval(() => {
      generateMockData();
    }, 5000);

    return () => clearInterval(interval);
  }, []);

  const avgSpeed = predictions.length > 0
    ? predictions.reduce((sum, p) => sum + p.predicted_speed, 0) / predictions.length
    : 0;

  const highCongestion = predictions.filter(p => p.predicted_speed < 20).length;

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">METR-LA Traffic Prediction Dashboard</h1>
              <p className="text-gray-600 mt-2">Real-time traffic predictions for Los Angeles highways</p>
            </div>
            <div className="flex items-center space-x-4">
              <div className={`flex items-center space-x-2 ${isConnected ? 'text-green-600' : 'text-red-600'}`}>
                <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
                <span className="text-sm font-medium">
                  {isConnected ? 'Live Data' : 'Disconnected'}
                </span>
              </div>
              <div className="text-sm text-gray-500">
                Last update: {lastUpdate}
              </div>
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow-md p-4">
            <div className="text-2xl font-bold text-blue-600">{predictions.length}</div>
            <div className="text-sm text-gray-600">Total Predictions</div>
          </div>
          <div className="bg-white rounded-lg shadow-md p-4">
            <div className="text-2xl font-bold text-green-600">{avgSpeed.toFixed(1)} mph</div>
            <div className="text-sm text-gray-600">Avg Predicted Speed</div>
          </div>
          <div className="bg-white rounded-lg shadow-md p-4">
            <div className="text-2xl font-bold text-red-600">{highCongestion}</div>
            <div className="text-sm text-gray-600">High Congestion Areas</div>
          </div>
          <div className="bg-white rounded-lg shadow-md p-4">
            <div className="text-2xl font-bold text-purple-600">94.2%</div>
            <div className="text-sm text-gray-600">Model Accuracy</div>
          </div>
        </div>

        {/* Traffic Heatmap */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Real-time Traffic Heatmap</h2>
          {isLoading ? (
            <div className="h-96 bg-gray-100 animate-pulse rounded-lg flex items-center justify-center">
              <div className="text-gray-500">Loading traffic data...</div>
            </div>
          ) : (
            <Map data={heatmapData} />
          )}
          <div className="mt-4 text-sm text-gray-600">
            <p>🔴 Red areas indicate heavy congestion (&lt; 25 mph)</p>
            <p>🟡 Yellow areas indicate moderate congestion (25-45 mph)</p>
            <p>🟢 Green areas indicate free-flowing traffic (&gt; 45 mph)</p>
          </div>
        </div>

        {/* Live Predictions */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Live Traffic Predictions</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {predictions.slice(-4).map((prediction, index) => (
              <div key={index} className="border rounded-lg p-4 hover:shadow-md transition-shadow">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <div className="font-medium text-sm text-gray-900">{prediction.sensor_id}</div>
                    <div className="text-xs text-gray-600">{prediction.road_name}</div>
                  </div>
                  <div className="text-right">
                    <div className={`text-lg font-bold ${getSpeedColor(prediction.predicted_speed)}`}>
                      {prediction.predicted_speed.toFixed(1)} mph
                    </div>
                    <div className="text-xs text-gray-500">
                      vs {prediction.actual_speed?.toFixed(1) || prediction.current_speed?.toFixed(1) || 'N/A'} actual
                    </div>
                  </div>
                </div>
                <div className="flex justify-between items-center text-xs text-gray-500">
                  <span>Model: {prediction.model_name}</span>
                  <span>Confidence: {(prediction.confidence_score * 100).toFixed(1)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* System Status */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">System Status</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="text-center p-3 border rounded-lg">
              <div className="text-2xl font-bold text-green-600">OK</div>
              <div className="text-sm font-medium mt-1">Kafka Producer</div>
              <div className="text-xs text-green-600 mt-1">Active</div>
            </div>
            <div className="text-center p-3 border rounded-lg">
              <div className="text-2xl font-bold text-green-600">OK</div>
              <div className="text-sm font-medium mt-1">Spark Streaming</div>
              <div className="text-xs text-green-600 mt-1">Processing</div>
            </div>
            <div className="text-center p-3 border rounded-lg">
              <div className="text-2xl font-bold text-green-600">OK</div>
              <div className="text-sm font-medium mt-1">HDFS Storage</div>
              <div className="text-xs text-green-600 mt-1">Available</div>
            </div>
            <div className="text-center p-3 border rounded-lg">
              <div className="text-2xl font-bold text-green-600">OK</div>
              <div className="text-sm font-medium mt-1">ML Models</div>
              <div className="text-xs text-green-600 mt-1">Ready</div>
            </div>
          </div>
        </div>

        {/* Data Pipeline */}
        <div className="bg-white rounded-lg shadow-md p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">METR-LA Data Pipeline</h2>
          <div className="flex items-center justify-center space-x-4 text-sm overflow-x-auto pb-2">
            <div className="bg-blue-100 px-3 py-2 rounded-lg text-blue-800 font-medium whitespace-nowrap">
              METR-LA CSV
            </div>
            <div className="text-gray-400">-&gt;</div>
            <div className="bg-green-100 px-3 py-2 rounded-lg text-green-800 font-medium whitespace-nowrap">
              Kafka Producer
            </div>
            <div className="text-gray-400">-&gt;</div>
            <div className="bg-purple-100 px-3 py-2 rounded-lg text-purple-800 font-medium whitespace-nowrap">
              Spark Streaming
            </div>
            <div className="text-gray-400">-&gt;</div>
            <div className="bg-yellow-100 px-3 py-2 rounded-lg text-yellow-800 font-medium whitespace-nowrap">
              HDFS Storage
            </div>
            <div className="text-gray-400">-&gt;</div>
            <div className="bg-red-100 px-3 py-2 rounded-lg text-red-800 font-medium whitespace-nowrap">
              ML Training
            </div>
            <div className="text-gray-400">-&gt;</div>
            <div className="bg-indigo-100 px-3 py-2 rounded-lg text-indigo-800 font-medium whitespace-nowrap">
              Predictions
            </div>
            <div className="text-gray-400">-&gt;</div>
            <div className="bg-pink-100 px-3 py-2 rounded-lg text-pink-800 font-medium whitespace-nowrap">
              Dashboard
            </div>
          </div>
          <div className="mt-4 text-center text-sm text-gray-500">
            Complete end-to-end pipeline for real-time traffic prediction and visualization
          </div>
        </div>

        {/* Instructions */}
        <div className="mt-6 bg-blue-50 border-l-4 border-blue-400 p-4">
          <div className="flex">
            <div className="ml-3">
              <p className="text-sm text-blue-700">
                <strong>Next Steps:</strong> This dashboard shows mock data. To connect to the real pipeline,
                integrate WebSocket connections to consume from Kafka predictions topic and
                add interactive Leaflet maps for geographic visualization.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

