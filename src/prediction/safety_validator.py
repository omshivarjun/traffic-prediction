"""
Safety Validation Layer for Traffic Predictions
Ensures predictions are physically realistic and safe for public use

CRITICAL: This module prevents false predictions that could lead to accidents
"""
import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class PredictionSafetyValidator:
    """
    Validates traffic predictions against safety bounds and realistic constraints
    
    SAFETY-CRITICAL: All predictions must pass validation before being displayed
    to drivers, navigation systems, or emergency services.
    """
    
    # Physical constraints for traffic predictions
    ABSOLUTE_MIN_SPEED = 0.0  # mph - cannot have negative speed
    ABSOLUTE_MAX_SPEED = 100.0  # mph - reasonable highway maximum
    
    # Realistic travel time bounds (seconds per mile)
    MIN_TRAVEL_TIME_PER_MILE = 36  # 100 mph = 36 seconds/mile
    MAX_TRAVEL_TIME_PER_MILE = 3600  # 1 mph = 3600 seconds/mile (extreme congestion)
    
    # Volume constraints (vehicles per hour)
    MIN_VOLUME = 0
    MAX_VOLUME = 10000  # Maximum realistic hourly volume
    
    # Occupancy constraints (percentage)
    MIN_OCCUPANCY = 0.0
    MAX_OCCUPANCY = 100.0
    
    # Confidence thresholds
    MIN_CONFIDENCE_FOR_DISPLAY = 0.3  # Below this, mark as "uncertain"
    MIN_CONFIDENCE_FOR_ROUTING = 0.6  # Below this, don't use for navigation
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize safety validator with optional custom bounds
        
        Args:
            config: Optional dict with custom safety bounds
        """
        self.config = config or {}
        
        # Allow configuration overrides (but enforce minimums)
        self.min_speed = max(self.ABSOLUTE_MIN_SPEED, 
                            self.config.get('min_speed', self.ABSOLUTE_MIN_SPEED))
        self.max_speed = min(self.ABSOLUTE_MAX_SPEED,
                            self.config.get('max_speed', self.ABSOLUTE_MAX_SPEED))
        
        logger.info(f"Safety Validator initialized: Speed range [{self.min_speed}, {self.max_speed}] mph")
    
    def validate_prediction(self, prediction: Dict) -> Tuple[bool, Dict, List[str]]:
        """
        Validate a single prediction against safety bounds
        
        Args:
            prediction: Prediction dict with predicted_speed, predicted_volume, etc.
        
        Returns:
            Tuple of:
            - is_valid: Boolean indicating if prediction is safe
            - corrected_prediction: Prediction with bounds applied
            - warnings: List of validation warnings
        
        CRITICAL: Always call this before displaying predictions to users
        """
        warnings = []
        corrected = prediction.copy()
        is_valid = True
        
        # Validate predicted speed
        if 'predicted_speed' in prediction and prediction['predicted_speed'] is not None:
            original_speed = prediction['predicted_speed']
            
            # Check for invalid values
            if np.isnan(original_speed) or np.isinf(original_speed):
                warnings.append(f"CRITICAL: NaN/Infinity speed detected: {original_speed}")
                corrected['predicted_speed'] = None
                corrected['validation_status'] = 'INVALID_VALUE'
                is_valid = False
            else:
                # Apply safety bounds
                bounded_speed = np.clip(original_speed, self.min_speed, self.max_speed)
                
                if bounded_speed != original_speed:
                    warnings.append(
                        f"Speed out of bounds: {original_speed:.1f} mph → "
                        f"clipped to {bounded_speed:.1f} mph"
                    )
                    logger.warning(
                        f"Sensor {prediction.get('sensor_id', 'unknown')}: "
                        f"Unsafe speed {original_speed:.1f} bounded to {bounded_speed:.1f}"
                    )
                
                corrected['predicted_speed'] = float(bounded_speed)
                corrected['original_predicted_speed'] = float(original_speed)
                corrected['speed_was_bounded'] = (bounded_speed != original_speed)
        
        # Validate against speed limit if available
        if ('predicted_speed' in corrected and corrected['predicted_speed'] is not None and
            'speed_limit' in prediction and prediction.get('speed_limit')):
            
            speed_limit = prediction['speed_limit']
            predicted = corrected['predicted_speed']
            
            # Flag if prediction significantly exceeds speed limit
            if predicted > speed_limit * 1.3:  # 30% over speed limit
                warnings.append(
                    f"Predicted speed {predicted:.1f} mph exceeds speed limit "
                    f"{speed_limit:.1f} mph by {((predicted/speed_limit - 1) * 100):.0f}%"
                )
                # Don't clip to speed limit (traffic can exceed it), but flag it
                corrected['exceeds_speed_limit'] = True
        
        # Validate predicted volume
        if 'predicted_volume' in prediction and prediction['predicted_volume'] is not None:
            original_volume = prediction['predicted_volume']
            
            if np.isnan(original_volume) or np.isinf(original_volume):
                warnings.append(f"CRITICAL: NaN/Infinity volume detected: {original_volume}")
                corrected['predicted_volume'] = None
                is_valid = False
            else:
                bounded_volume = np.clip(original_volume, self.MIN_VOLUME, self.MAX_VOLUME)
                
                if bounded_volume != original_volume:
                    warnings.append(
                        f"Volume out of bounds: {original_volume:.0f} → "
                        f"clipped to {bounded_volume:.0f}"
                    )
                
                corrected['predicted_volume'] = float(bounded_volume)
        
        # Validate travel time consistency
        if ('predicted_speed' in corrected and corrected['predicted_speed'] is not None and
            corrected['predicted_speed'] > 0):
            
            # Recalculate travel time with validated speed
            validated_speed = corrected['predicted_speed']
            travel_time = int((1.0 / validated_speed) * 3600)  # seconds per mile
            
            # Apply travel time bounds
            travel_time = np.clip(travel_time, 
                                 self.MIN_TRAVEL_TIME_PER_MILE,
                                 self.MAX_TRAVEL_TIME_PER_MILE)
            
            corrected['predicted_travel_time'] = travel_time
        
        # Validate confidence score
        if 'confidence_score' in prediction:
            confidence = prediction['confidence_score']
            
            if confidence < self.MIN_CONFIDENCE_FOR_DISPLAY:
                warnings.append(f"Very low confidence: {confidence:.2f}")
                corrected['display_warning'] = 'LOW_CONFIDENCE'
            
            if confidence < self.MIN_CONFIDENCE_FOR_ROUTING:
                corrected['suitable_for_routing'] = False
            else:
                corrected['suitable_for_routing'] = True
        
        # Add validation metadata
        corrected['validation_timestamp'] = datetime.now().isoformat()
        corrected['validation_warnings'] = warnings
        corrected['passed_safety_validation'] = is_valid and len(warnings) == 0
        
        return is_valid, corrected, warnings
    
    def validate_batch(self, predictions: List[Dict]) -> Tuple[List[Dict], Dict]:
        """
        Validate a batch of predictions
        
        Args:
            predictions: List of prediction dicts
        
        Returns:
            Tuple of:
            - corrected_predictions: List of validated predictions
            - summary: Dict with validation statistics
        """
        if not predictions:
            return [], {'total': 0, 'valid': 0, 'warnings': 0, 'invalid': 0}
        
        corrected_predictions = []
        total_warnings = 0
        invalid_count = 0
        
        for pred in predictions:
            is_valid, corrected, warnings = self.validate_prediction(pred)
            
            corrected_predictions.append(corrected)
            total_warnings += len(warnings)
            
            if not is_valid:
                invalid_count += 1
        
        summary = {
            'total': len(predictions),
            'valid': len(predictions) - invalid_count,
            'invalid': invalid_count,
            'warnings': total_warnings,
            'validation_rate': (len(predictions) - invalid_count) / len(predictions) * 100,
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(
            f"Batch validation: {summary['valid']}/{summary['total']} valid, "
            f"{summary['warnings']} warnings, {summary['invalid']} invalid"
        )
        
        return corrected_predictions, summary
    
    def check_prediction_consistency(self, predictions: List[Dict]) -> List[str]:
        """
        Check for inconsistencies across multiple predictions
        
        Args:
            predictions: List of predictions for the same sensor over time
        
        Returns:
            List of consistency warnings
        """
        warnings = []
        
        if len(predictions) < 2:
            return warnings
        
        # Group by sensor_id
        by_sensor = {}
        for pred in predictions:
            sensor_id = pred.get('sensor_id')
            if sensor_id:
                if sensor_id not in by_sensor:
                    by_sensor[sensor_id] = []
                by_sensor[sensor_id].append(pred)
        
        # Check each sensor's predictions for sudden changes
        for sensor_id, sensor_preds in by_sensor.items():
            if len(sensor_preds) < 2:
                continue
            
            speeds = [p.get('predicted_speed') for p in sensor_preds 
                     if p.get('predicted_speed') is not None]
            
            if len(speeds) < 2:
                continue
            
            # Check for unrealistic speed changes
            for i in range(len(speeds) - 1):
                speed_change = abs(speeds[i+1] - speeds[i])
                
                # Flag if speed changes >40 mph between consecutive predictions
                if speed_change > 40:
                    warnings.append(
                        f"Sensor {sensor_id}: Unrealistic speed change "
                        f"{speeds[i]:.1f} → {speeds[i+1]:.1f} mph "
                        f"(Δ{speed_change:.1f} mph)"
                    )
        
        return warnings
    
    def get_safety_summary(self) -> Dict:
        """Get summary of safety validation configuration"""
        return {
            'speed_range_mph': [self.min_speed, self.max_speed],
            'volume_range': [self.MIN_VOLUME, self.MAX_VOLUME],
            'occupancy_range_percent': [self.MIN_OCCUPANCY, self.MAX_OCCUPANCY],
            'min_confidence_display': self.MIN_CONFIDENCE_FOR_DISPLAY,
            'min_confidence_routing': self.MIN_CONFIDENCE_FOR_ROUTING,
            'validation_active': True
        }


def validate_predictions_safe(predictions: List[Dict], 
                              config: Optional[Dict] = None) -> Tuple[List[Dict], Dict]:
    """
    Convenience function to validate predictions with safety bounds
    
    CRITICAL: Always call this before displaying predictions to users
    
    Args:
        predictions: List of raw predictions from ML model
        config: Optional custom safety configuration
    
    Returns:
        Tuple of (validated_predictions, validation_summary)
    """
    validator = PredictionSafetyValidator(config)
    return validator.validate_batch(predictions)
