/**
 * Prediction Layer Component
 * Renders all traffic predictions on the map
 */

'use client';

import { LayerGroup } from 'react-leaflet';
import { PredictionMarker } from './PredictionMarker';
import { TrafficPrediction } from '@/hooks/usePredictions';

interface PredictionLayerProps {
  predictions: TrafficPrediction[];
  segmentCoordinates: Map<string, { latitude: number; longitude: number }>;
}

/**
 * Layer that displays all active traffic predictions
 */
export function PredictionLayer({ predictions, segmentCoordinates }: PredictionLayerProps) {
  if (predictions.length === 0) {
    return null;
  }

  return (
    <LayerGroup>
      {predictions.map((prediction) => {
        // Get coordinates for this segment
        const coords = segmentCoordinates.get(prediction.segment_id);
        
        if (!coords) {
          // Skip predictions without coordinates
          console.warn(`No coordinates found for segment: ${prediction.segment_id}`);
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
  );
}

export default PredictionLayer;
