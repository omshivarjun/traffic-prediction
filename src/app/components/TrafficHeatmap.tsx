'use client';

import { useEffect, useRef, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

interface TrafficHeatmapData {
  latitude: number;
  longitude: number;
  speed: number;
  intensity: number;
  sensor_id: string;
  road_name?: string;
  road_type?: string;
  lane_count?: number;
  predicted_speed?: number;
  confidence_score?: number;
}

interface TrafficHeatmapProps {
  data: TrafficHeatmapData[];
  center?: [number, number];
  zoom?: number;
}

// Speed color mapping for heatmap visualization
const getSpeedColor = (speed: number): string => {
  if (speed < 10) return '#d32f2f'; // Red - Heavy congestion
  if (speed < 25) return '#f57c00'; // Orange - Moderate congestion
  if (speed < 45) return '#fbc02d'; // Yellow - Light congestion
  if (speed < 60) return '#689f38'; // Light green - Good flow
  return '#388e3c'; // Green - Free flow
};

const getSpeedOpacity = (speed: number, intensity: number): number => {
  // Higher opacity for slower speeds (more congested areas)
  const speedFactor = Math.max(0.2, 1 - (speed / 80));
  const intensityFactor = Math.min(1, intensity / 10);
  return Math.min(0.9, speedFactor * intensityFactor + 0.3);
};

const getMarkerRadius = (speed: number, intensity: number): number => {
  // Larger markers for more congested areas
  const baseRadius = 8;
  const congestionFactor = Math.max(0.5, 1 - (speed / 80));
  const intensityFactor = Math.min(2, intensity / 5);
  return Math.min(20, baseRadius * congestionFactor * intensityFactor);
};

const TrafficMarker: React.FC<{ point: TrafficHeatmapData }> = ({ point }) => {
  const color = getSpeedColor(point.speed);
  const opacity = getSpeedOpacity(point.speed, point.intensity);
  const radius = getMarkerRadius(point.speed, point.intensity);

  return (
    <CircleMarker
      center={[point.latitude, point.longitude]}
      radius={radius}
      fillColor={color}
      color={color}
      weight={2}
      opacity={opacity}
      fillOpacity={opacity * 0.7}
    >
      <Popup>
        <div className="text-sm">
          <div className="font-semibold text-gray-800">
            {point.road_name || `Sensor ${point.sensor_id}`}
          </div>
          <div className="mt-2 space-y-1">
            <div className="flex justify-between">
              <span className="text-gray-600">Current Speed:</span>
              <span className={`font-medium ${
                point.speed < 25 ? 'text-red-600' : 
                point.speed < 45 ? 'text-yellow-600' : 'text-green-600'
              }`}>
                {point.speed.toFixed(1)} mph
              </span>
            </div>
            {point.predicted_speed && (
              <div className="flex justify-between">
                <span className="text-gray-600">Predicted:</span>
                <span className="font-medium text-blue-600">
                  {point.predicted_speed.toFixed(1)} mph
                </span>
              </div>
            )}
            {point.confidence_score && (
              <div className="flex justify-between">
                <span className="text-gray-600">Confidence:</span>
                <span className="font-medium text-gray-800">
                  {(point.confidence_score * 100).toFixed(0)}%
                </span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-gray-600">Road Type:</span>
              <span className="font-medium text-gray-800 capitalize">
                {point.road_type || 'Unknown'}
              </span>
            </div>
            {point.lane_count && (
              <div className="flex justify-between">
                <span className="text-gray-600">Lanes:</span>
                <span className="font-medium text-gray-800">
                  {point.lane_count}
                </span>
              </div>
            )}
            <div className="flex justify-between">
              <span className="text-gray-600">Sensor ID:</span>
              <span className="font-mono text-xs text-gray-600">
                {point.sensor_id}
              </span>
            </div>
          </div>
        </div>
      </Popup>
    </CircleMarker>
  );
};

const HeatmapLegend: React.FC = () => {
  return (
    <div className="absolute top-4 right-4 bg-white p-4 rounded-lg shadow-lg z-[1000] max-w-xs">
      <h3 className="font-semibold text-gray-800 mb-3">Traffic Speed Legend</h3>
      <div className="space-y-2">
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 rounded-full" style={{ backgroundColor: '#d32f2f' }}></div>
          <span className="text-sm text-gray-700">&lt; 10 mph - Heavy Congestion</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 rounded-full" style={{ backgroundColor: '#f57c00' }}></div>
          <span className="text-sm text-gray-700">10-25 mph - Moderate Congestion</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 rounded-full" style={{ backgroundColor: '#fbc02d' }}></div>
          <span className="text-sm text-gray-700">25-45 mph - Light Congestion</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 rounded-full" style={{ backgroundColor: '#689f38' }}></div>
          <span className="text-sm text-gray-700">45-60 mph - Good Flow</span>
        </div>
        <div className="flex items-center space-x-2">
          <div className="w-4 h-4 rounded-full" style={{ backgroundColor: '#388e3c' }}></div>
          <span className="text-sm text-gray-700">60+ mph - Free Flow</span>
        </div>
      </div>
      <div className="mt-3 pt-3 border-t border-gray-200">
        <p className="text-xs text-gray-600">
          Marker size indicates traffic intensity. Click markers for details.
        </p>
      </div>
    </div>
  );
};

const TrafficStats: React.FC<{ data: TrafficHeatmapData[] }> = ({ data }) => {
  const avgSpeed = data.length > 0 ? data.reduce((sum, point) => sum + point.speed, 0) / data.length : 0;
  const congestedCount = data.filter(point => point.speed < 25).length;
  const freeFlowCount = data.filter(point => point.speed > 45).length;
  
  return (
    <div className="absolute bottom-4 left-4 bg-white p-4 rounded-lg shadow-lg z-[1000]">
      <h3 className="font-semibold text-gray-800 mb-2">Traffic Statistics</h3>
      <div className="space-y-1 text-sm">
        <div className="flex justify-between space-x-4">
          <span className="text-gray-600">Average Speed:</span>
          <span className="font-medium">{avgSpeed.toFixed(1)} mph</span>
        </div>
        <div className="flex justify-between space-x-4">
          <span className="text-gray-600">Total Sensors:</span>
          <span className="font-medium">{data.length}</span>
        </div>
        <div className="flex justify-between space-x-4">
          <span className="text-red-600">Congested:</span>
          <span className="font-medium">{congestedCount}</span>
        </div>
        <div className="flex justify-between space-x-4">
          <span className="text-green-600">Free Flow:</span>
          <span className="font-medium">{freeFlowCount}</span>
        </div>
      </div>
    </div>
  );
};

const TrafficHeatmap: React.FC<TrafficHeatmapProps> = ({ 
  data, 
  center = [34.0522, -118.2437], // Los Angeles default
  zoom = 11 
}) => {
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  if (!isClient) {
    return (
      <div className="h-96 bg-gray-100 animate-pulse rounded-lg flex items-center justify-center">
        Loading Traffic Heatmap...
      </div>
    );
  }

  return (
    <div className="relative h-96 w-full rounded-lg overflow-hidden">
      <MapContainer 
        center={center} 
        zoom={zoom} 
        style={{ height: '100%', width: '100%' }}
        zoomControl={true}
        scrollWheelZoom={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        
        {data.map((point, index) => (
          <TrafficMarker key={`${point.sensor_id}-${index}`} point={point} />
        ))}
      </MapContainer>
      
      <HeatmapLegend />
      <TrafficStats data={data} />
    </div>
  );
};

export default TrafficHeatmap;