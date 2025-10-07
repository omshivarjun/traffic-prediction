'use client';

import { useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from 'react-leaflet';
import type { LatLngBounds, LatLngExpression } from 'leaflet';
import 'leaflet/dist/leaflet.css';

interface TrafficMapData {
  latitude: number;
  longitude: number;
  speed: number;
  intensity?: number;
  sensor_id: string;
  predicted_speed?: number;
  confidence_score?: number;
  road_name?: string;
  road_type?: string;
  lane_count?: number;
}

interface InteractiveTrafficMapProps {
  data: TrafficMapData[];
}

// Component to update map bounds when data changes
function MapUpdater({ data }: { data: TrafficMapData[] }) {
  const map = useMap();

  useEffect(() => {
    if (data.length > 0) {
      // Calculate bounds from all data points
      const bounds: LatLngExpression[] = data.map(point => [point.latitude, point.longitude]);
      
      // Only update bounds if we have valid data
      if (bounds.length > 0) {
        try {
          const latLngBounds = bounds as [number, number][];
          map.fitBounds(latLngBounds, { padding: [50, 50], maxZoom: 13 });
        } catch (error) {
          console.warn('Could not fit bounds:', error);
        }
      }
    }
  }, [data, map]);

  return null;
}

// Get marker color based on speed
function getMarkerColor(speed: number): string {
  if (speed < 15) return '#dc2626'; // red-600 - Severe congestion
  if (speed < 30) return '#ea580c'; // orange-600 - Heavy congestion
  if (speed < 45) return '#f59e0b'; // amber-500 - Moderate congestion
  if (speed < 60) return '#84cc16'; // lime-500 - Light congestion
  return '#22c55e'; // green-500 - Free flow
}

// Get marker radius based on intensity or speed
function getMarkerRadius(speed: number, intensity?: number): number {
  if (intensity !== undefined) {
    return Math.max(5, Math.min(20, intensity * 2));
  }
  // Base radius on congestion level
  if (speed < 20) return 12;
  if (speed < 40) return 10;
  return 8;
}

// Get congestion level text
function getCongestionLevel(speed: number): string {
  if (speed < 15) return 'SEVERE';
  if (speed < 30) return 'HEAVY';
  if (speed < 45) return 'MODERATE';
  if (speed < 60) return 'LIGHT';
  return 'FREE_FLOW';
}

export default function InteractiveTrafficMap({ data }: InteractiveTrafficMapProps) {
  // Calculate center position from data or use LA default
  const center: LatLngExpression = useMemo(() => {
    if (data.length > 0) {
      const avgLat = data.reduce((sum, p) => sum + p.latitude, 0) / data.length;
      const avgLng = data.reduce((sum, p) => sum + p.longitude, 0) / data.length;
      return [avgLat, avgLng];
    }
    return [34.0522, -118.2437]; // Los Angeles default
  }, [data]);

  return (
    <MapContainer
      center={center}
      zoom={11}
      style={{ height: '400px', width: '100%', borderRadius: '0.5rem' }}
      scrollWheelZoom={true}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      
      <MapUpdater data={data} />
      
      {data.map((point, index) => {
        const color = getMarkerColor(point.speed);
        const radius = getMarkerRadius(point.speed, point.intensity);
        const congestionLevel = getCongestionLevel(point.speed);
        
        return (
          <CircleMarker
            key={`${point.sensor_id}-${index}`}
            center={[point.latitude, point.longitude]}
            radius={radius}
            fillColor={color}
            color={color}
            weight={2}
            opacity={0.8}
            fillOpacity={0.6}
          >
            <Popup>
              <div className="text-sm">
                <div className="font-bold text-gray-900 mb-2">
                  {point.sensor_id}
                </div>
                
                {point.road_name && (
                  <div className="text-xs text-gray-600 mb-2">
                    {point.road_name}
                  </div>
                )}
                
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span className="text-gray-600">Speed:</span>
                    <div className="font-bold" style={{ color }}>
                      {point.speed.toFixed(1)} mph
                    </div>
                  </div>
                  
                  {point.predicted_speed && (
                    <div>
                      <span className="text-gray-600">Predicted:</span>
                      <div className="font-bold">
                        {point.predicted_speed.toFixed(1)} mph
                      </div>
                    </div>
                  )}
                  
                  <div>
                    <span className="text-gray-600">Congestion:</span>
                    <div className="font-bold">
                      {congestionLevel}
                    </div>
                  </div>
                  
                  {point.confidence_score && (
                    <div>
                      <span className="text-gray-600">Confidence:</span>
                      <div className="font-bold">
                        {(point.confidence_score * 100).toFixed(1)}%
                      </div>
                    </div>
                  )}
                  
                  {point.road_type && (
                    <div>
                      <span className="text-gray-600">Type:</span>
                      <div className="font-bold capitalize">
                        {point.road_type}
                      </div>
                    </div>
                  )}
                  
                  {point.lane_count && (
                    <div>
                      <span className="text-gray-600">Lanes:</span>
                      <div className="font-bold">
                        {point.lane_count}
                      </div>
                    </div>
                  )}
                </div>
                
                <div className="text-xs text-gray-500 mt-2">
                  {point.latitude.toFixed(4)}, {point.longitude.toFixed(4)}
                </div>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
