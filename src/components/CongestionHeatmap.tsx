'use client';

import { useState, useEffect, useRef } from 'react';

interface HotspotData {
  sensor_id: string;
  location_name: string;
  current_speed: number;
  congestion_level: string;
  severity_score: number;
  coordinates: {
    latitude: number;
    longitude: number;
  };
}

interface TrafficStats {
  active_sensors: number;
  average_speed: number;
  congested_sensors: number;
  free_flow_sensors: number;
}

export default function CongestionHeatmap() {
  const [hotspots, setHotspots] = useState<HotspotData[]>([]);
  const [stats, setStats] = useState<TrafficStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedHotspot, setSelectedHotspot] = useState<HotspotData | null>(null);
  const mapRef = useRef<HTMLDivElement>(null);

  // Fetch hotspots and statistics
  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        
        // Fetch hotspots
        const hotspotsResponse = await fetch('http://localhost:8000/api/ml/hotspots?num_hotspots=15');
        const hotspotsData = await hotspotsResponse.json();
        
        // Fetch statistics  
        const statsResponse = await fetch('http://localhost:8000/api/ml/statistics');
        const statsData = await statsResponse.json();
        
        setHotspots(hotspotsData.hotspots || []);
        setStats(statsData);
        setError(null);
        
      } catch (err) {
        console.error('Error fetching data:', err);
        setError('Failed to load traffic data');
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
    
    // Refresh data every 30 seconds
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const getSeverityColor = (level: string, score: number) => {
    switch (level) {
      case 'severe':
        return 'bg-red-600 border-red-700';
      case 'heavy':
        return 'bg-orange-500 border-orange-600';
      case 'moderate':
        return 'bg-yellow-500 border-yellow-600';
      default:
        return 'bg-green-500 border-green-600';
    }
  };

  const getSeverityIcon = (level: string) => {
    switch (level) {
      case 'severe':
        return '🔴';
      case 'heavy':
        return '🟠';
      case 'moderate':
        return '🟡';
      default:
        return '🟢';
    }
  };

  if (isLoading) {
    return (
      <div className="w-full h-96 bg-gray-100 rounded-lg flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading real-time traffic data...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full h-96 bg-red-50 rounded-lg flex items-center justify-center border border-red-200">
        <div className="text-center">
          <div className="text-4xl mb-4">⚠️</div>
          <p className="text-red-600 font-medium">{error}</p>
          <p className="text-red-500 text-sm mt-2">Check if the API server is running</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full space-y-6">
      {/* Header with Statistics */}
      <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-blue-500">
        <h2 className="text-xl font-semibold text-gray-800 mb-4">
          Los Angeles Traffic Congestion - Live Data
        </h2>
        
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div className="bg-blue-50 p-3 rounded">
              <div className="text-2xl font-bold text-blue-600">{stats.active_sensors}</div>
              <div className="text-sm text-blue-800">Active Sensors</div>
            </div>
            <div className="bg-green-50 p-3 rounded">
              <div className="text-2xl font-bold text-green-600">{stats.average_speed?.toFixed(1)} mph</div>
              <div className="text-sm text-green-800">Avg Speed</div>
            </div>
            <div className="bg-red-50 p-3 rounded">
              <div className="text-2xl font-bold text-red-600">{stats.congested_sensors}</div>
              <div className="text-sm text-red-800">Congested Areas</div>
            </div>
            <div className="bg-purple-50 p-3 rounded">
              <div className="text-2xl font-bold text-purple-600">{stats.free_flow_sensors}</div>
              <div className="text-sm text-purple-800">Free Flow</div>
            </div>
          </div>
        )}
      </div>

      {/* Interactive Map Container */}
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <div className="p-4 bg-gray-50 border-b">
          <h3 className="text-lg font-semibold text-gray-800">Real-Time Congestion Heatmap</h3>
          <p className="text-sm text-gray-600">METR-LA Highway Network - Los Angeles County</p>
        </div>
        
        <div className="relative">
          {/* Map visualization area */}
          <div 
            ref={mapRef}
            className="h-96 bg-gradient-to-br from-blue-100 to-blue-200 relative overflow-hidden"
          >
            {/* Background map representation */}
            <div className="absolute inset-0 opacity-20">
              <div className="absolute top-4 left-4 w-16 h-1 bg-gray-600 transform rotate-45"></div>
              <div className="absolute top-8 left-8 w-20 h-1 bg-gray-600 transform -rotate-12"></div>
              <div className="absolute top-12 left-12 w-24 h-1 bg-gray-600 transform rotate-12"></div>
              <div className="absolute top-16 left-6 w-18 h-1 bg-gray-600 transform rotate-45"></div>
              <div className="absolute top-20 left-16 w-16 h-1 bg-gray-600 transform -rotate-45"></div>
              
              {/* More highway lines */}
              <div className="absolute bottom-20 right-8 w-20 h-1 bg-gray-600 transform rotate-45"></div>
              <div className="absolute bottom-16 right-16 w-24 h-1 bg-gray-600 transform -rotate-12"></div>
              <div className="absolute bottom-12 right-4 w-16 h-1 bg-gray-600 transform rotate-12"></div>
            </div>

            {/* Hotspot markers */}
            {hotspots.map((hotspot, index) => {
              const x = 20 + (index % 6) * 60; // Distribute across width
              const y = 30 + Math.floor(index / 6) * 60; // Stack vertically
              
              return (
                <div
                  key={hotspot.sensor_id}
                  className={`absolute cursor-pointer transform -translate-x-1/2 -translate-y-1/2 
                    ${getSeverityColor(hotspot.congestion_level, hotspot.severity_score)} 
                    rounded-full p-2 border-2 shadow-lg hover:scale-110 transition-all duration-200
                    ${selectedHotspot?.sensor_id === hotspot.sensor_id ? 'ring-4 ring-blue-400' : ''}`}
                  style={{ left: `${x}%`, top: `${y}%` }}
                  onClick={() => setSelectedHotspot(hotspot)}
                  title={hotspot.location_name}
                >
                  <div className="text-white text-xs font-bold">
                    {getSeverityIcon(hotspot.congestion_level)}
                  </div>
                  
                  {/* Pulse animation for severe congestion */}
                  {hotspot.congestion_level === 'severe' && (
                    <div className="absolute inset-0 rounded-full bg-red-400 animate-ping opacity-30"></div>
                  )}
                </div>
              );
            })}

            {/* Legend */}
            <div className="absolute bottom-4 left-4 bg-white/90 p-3 rounded-lg shadow">
              <h4 className="text-xs font-semibold mb-2">Congestion Level</h4>
              <div className="space-y-1 text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-red-600 rounded-full"></div>
                  <span>Severe (&lt; 25 mph)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-orange-500 rounded-full"></div>
                  <span>Heavy (25-40 mph)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-yellow-500 rounded-full"></div>
                  <span>Moderate (40-55 mph)</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                  <span>Free Flow (&gt; 55 mph)</span>
                </div>
              </div>
            </div>

            {/* Data source badge */}
            <div className="absolute top-4 right-4 bg-black/70 text-white px-3 py-1 rounded-full text-xs">
              METR-LA Dataset
            </div>
          </div>

          {/* Hotspot Details Panel */}
          {selectedHotspot && (
            <div className="absolute top-4 left-4 bg-white p-4 rounded-lg shadow-lg border max-w-xs z-10">
              <button
                onClick={() => setSelectedHotspot(null)}
                className="absolute top-2 right-2 text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
              
              <h4 className="font-semibold text-gray-800 mb-2 pr-6">
                {selectedHotspot.location_name}
              </h4>
              
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Current Speed:</span>
                  <span className="font-medium">{selectedHotspot.current_speed.toFixed(1)} mph</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-gray-600">Congestion:</span>
                  <span className={`font-medium capitalize
                    ${selectedHotspot.congestion_level === 'severe' ? 'text-red-600' :
                      selectedHotspot.congestion_level === 'heavy' ? 'text-orange-600' :
                      selectedHotspot.congestion_level === 'moderate' ? 'text-yellow-600' :
                      'text-green-600'}`}>
                    {selectedHotspot.congestion_level}
                  </span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-gray-600">Severity Score:</span>
                  <span className="font-medium">{(selectedHotspot.severity_score * 100).toFixed(0)}%</span>
                </div>
                
                <div className="flex justify-between">
                  <span className="text-gray-600">Sensor ID:</span>
                  <span className="font-mono text-xs">{selectedHotspot.sensor_id}</span>
                </div>
              </div>
              
              <div className="mt-3 pt-3 border-t text-xs text-gray-500">
                Click anywhere on the map to close
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Hotspots List */}
      <div className="bg-white rounded-lg shadow-md overflow-hidden">
        <div className="p-4 bg-gray-50 border-b">
          <h3 className="text-lg font-semibold text-gray-800">Current Congestion Hotspots</h3>
          <p className="text-sm text-gray-600">Top {hotspots.length} most congested areas</p>
        </div>
        
        <div className="divide-y divide-gray-200 max-h-64 overflow-y-auto">
          {hotspots.length === 0 ? (
            <div className="p-4 text-center text-gray-500">
              No congestion hotspots detected
            </div>
          ) : (
            hotspots.map((hotspot, index) => (
              <div
                key={hotspot.sensor_id}
                className={`p-4 hover:bg-gray-50 cursor-pointer transition-colors
                  ${selectedHotspot?.sensor_id === hotspot.sensor_id ? 'bg-blue-50' : ''}`}
                onClick={() => setSelectedHotspot(hotspot)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="text-lg">
                      {getSeverityIcon(hotspot.congestion_level)}
                    </div>
                    <div>
                      <div className="font-medium text-gray-800">
                        {hotspot.location_name}
                      </div>
                      <div className="text-sm text-gray-600">
                        Speed: {hotspot.current_speed.toFixed(1)} mph
                      </div>
                    </div>
                  </div>
                  
                  <div className="text-right">
                    <div className={`px-2 py-1 rounded-full text-xs font-medium
                      ${hotspot.congestion_level === 'severe' ? 'bg-red-100 text-red-800' :
                        hotspot.congestion_level === 'heavy' ? 'bg-orange-100 text-orange-800' :
                        hotspot.congestion_level === 'moderate' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-green-100 text-green-800'}`}>
                      {hotspot.congestion_level.toUpperCase()}
                    </div>
                    <div className="text-xs text-gray-500 mt-1">
                      {(hotspot.severity_score * 100).toFixed(0)}% severity
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}