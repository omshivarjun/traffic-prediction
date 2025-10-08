/**
 * Enhanced Traffic Map with ML Predictions
 * Displays both real-time traffic events and ML predictions
 */

'use client';

import { useEffect, useMemo, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, useMap, LayerGroup } from 'react-leaflet';
import type { LatLngExpression } from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { usePredictions } from '@/hooks/usePredictions';
import { PredictionMarker } from './PredictionMarker';

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

interface TrafficMapWithPredictionsProps {
  data: TrafficMapData[];
  showPredictions?: boolean;
}

// Component to update map bounds when data changes
function MapUpdater({ data, predictions }: { data: TrafficMapData[]; predictions: any[] }) {
  const map = useMap();

  useEffect(() => {
    const allPoints = [...data];
    
    if (allPoints.length > 0) {
      const bounds: LatLngExpression[] = allPoints.map(point => [point.latitude, point.longitude]);
      
      if (bounds.length > 0) {
        try {
          const latLngBounds = bounds as [number, number][];
          map.fitBounds(latLngBounds, { padding: [50, 50], maxZoom: 13 });
        } catch (error) {
          console.warn('Could not fit bounds:', error);
        }
      }
    }
  }, [data, predictions, map]);

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

// Get marker radius based on speed
function getMarkerRadius(speed: number, intensity?: number): number {
  if (intensity !== undefined) {
    return Math.max(5, Math.min(20, intensity * 2));
  }
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

export default function TrafficMapWithPredictions({ 
  data, 
  showPredictions = true 
}: TrafficMapWithPredictionsProps) {
  const { predictions, isConnected } = usePredictions({ autoConnect: showPredictions });
  const [showPredictionLayer, setShowPredictionLayer] = useState(showPredictions);

  // Create segment coordinate mapping from traffic data
  const segmentCoordinates = useMemo(() => {
    const coordMap = new Map<string, { latitude: number; longitude: number }>();
    
    // Handle optional data prop
    if (data && Array.isArray(data)) {
      data.forEach(point => {
        coordMap.set(point.sensor_id, {
          latitude: point.latitude,
          longitude: point.longitude
        });
      });
    }

    // Add LA segment coordinates for predictions
    const laSegments = [
      { id: 'LA_001', lat: 34.0522, lng: -118.2437 },
      { id: 'LA_002', lat: 34.0622, lng: -118.2537 },
      { id: 'LA_003', lat: 34.0422, lng: -118.2337 },
      { id: 'LA_004', lat: 34.0722, lng: -118.2637 },
      { id: 'LA_005', lat: 34.0322, lng: -118.2237 },
    ];

    laSegments.forEach(seg => {
      if (!coordMap.has(seg.id)) {
        coordMap.set(seg.id, { latitude: seg.lat, longitude: seg.lng });
      }
    });

    return coordMap;
  }, [data]);

  // Calculate center position
  const center: LatLngExpression = useMemo(() => {
    if (data.length > 0) {
      const avgLat = data.reduce((sum, p) => sum + p.latitude, 0) / data.length;
      const avgLng = data.reduce((sum, p) => sum + p.longitude, 0) / data.length;
      return [avgLat, avgLng];
    }
    return [34.0522, -118.2437]; // Los Angeles default
  }, [data]);

  return (
    <div className="relative">
      {/* Layer Controls */}
      <div className="absolute top-4 right-4 z-[1000] bg-white rounded-lg shadow-lg p-3">
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={showPredictionLayer}
              onChange={(e) => setShowPredictionLayer(e.target.checked)}
              className="w-4 h-4 text-blue-600 rounded"
            />
            <span className="text-sm font-medium">
              ML Predictions
              {isConnected && (
                <span className="ml-2 inline-flex items-center gap-1 text-xs text-green-600">
                  <span className="w-2 h-2 bg-green-500 rounded-full" />
                  Live
                </span>
              )}
            </span>
          </label>
          {predictions.length > 0 && (
            <span className="text-xs text-gray-500">
              ({predictions.length})
            </span>
          )}
        </div>
      </div>

      {/* Map Container */}
      <MapContainer
        center={center}
        zoom={11}
        style={{ height: '600px', width: '100%', borderRadius: '0.5rem' }}
        scrollWheelZoom={true}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        
        <MapUpdater data={data} predictions={predictions} />
        
        {/* Traffic Event Markers */}
        <LayerGroup>
          {data.map((point, index) => {
            const color = getMarkerColor(point.speed);
            const radius = getMarkerRadius(point.speed, point.intensity);
            const congestionLevel = getCongestionLevel(point.speed);
            
            return (
              <CircleMarker
                key={`traffic-${point.sensor_id}-${index}`}
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
                      
                      <div>
                        <span className="text-gray-600">Congestion:</span>
                        <div className="font-bold">
                          {congestionLevel}
                        </div>
                      </div>
                      
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
        </LayerGroup>

        {/* Prediction Markers Layer */}
        {showPredictionLayer && (
          <LayerGroup>
            {predictions.map((prediction) => {
              // Use coordinates from the prediction if available
              const coords = (prediction as any).coordinates || segmentCoordinates.get(prediction.segment_id);
              
              if (!coords || !coords.latitude || !coords.longitude) {
                return null;
              }

              return (
                <PredictionMarker
                  key={`prediction-${prediction.segment_id}-${prediction.timestamp}`}
                  prediction={prediction}
                  coordinates={coords}
                />
              );
            })}
          </LayerGroup>
        )}
      </MapContainer>

      {/* Status Bar */}
      {showPredictionLayer && (
        <div className="mt-2 text-sm text-gray-600">
          {isConnected ? (
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              {predictions.length > 0 
                ? `Showing ${predictions.length} ML prediction${predictions.length === 1 ? '' : 's'}`
                : 'Connected - waiting for predictions...'
              }
            </span>
          ) : (
            <span className="flex items-center gap-2 text-orange-600">
              <span className="w-2 h-2 bg-orange-500 rounded-full" />
              Prediction service disconnected
            </span>
          )}
        </div>
      )}
    </div>
  );
}
