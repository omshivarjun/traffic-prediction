"""
Test Suite for Safety Validation Layer

CRITICAL: Verifies prediction safety bounds prevent accidents
"""
import pytest
import numpy as np
from datetime import datetime
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.prediction.safety_validator import PredictionSafetyValidator, validate_predictions_safe


class TestSafetyValidator:
    """Test prediction safety validation"""
    
    def setup_method(self):
        """Initialize validator for each test"""
        self.validator = PredictionSafetyValidator()
    
    def test_normal_speed_prediction_passes(self):
        """Test that normal speed predictions pass validation"""
        prediction = {
            'sensor_id': 'sensor_001',
            'predicted_speed': 55.0,
            'predicted_volume': 1500,
            'confidence_score': 0.85
        }
        
        is_valid, corrected, warnings = self.validator.validate_prediction(prediction)
        
        assert is_valid is True
        assert corrected['predicted_speed'] == 55.0
        assert len(warnings) == 0
        assert corrected['passed_safety_validation'] is True
    
    def test_excessive_speed_is_bounded(self):
        """CRITICAL: Test that impossibly high speeds are bounded"""
        prediction = {
            'sensor_id': 'sensor_002',
            'predicted_speed': 500.0,  # Impossible speed
            'confidence_score': 0.8
        }
        
        is_valid, corrected, warnings = self.validator.validate_prediction(prediction)
        
        # Should be valid but corrected
        assert corrected['predicted_speed'] == 100.0  # Clipped to max
        assert corrected['original_predicted_speed'] == 500.0
        assert corrected['speed_was_bounded'] == True  # Use == instead of is
        assert len(warnings) > 0
        assert 'out of bounds' in warnings[0]
    
    def test_negative_speed_is_bounded(self):
        """CRITICAL: Test that negative speeds are bounded to zero"""
        prediction = {
            'sensor_id': 'sensor_003',
            'predicted_speed': -50.0,  # Impossible negative speed
            'confidence_score': 0.7
        }
        
        is_valid, corrected, warnings = self.validator.validate_prediction(prediction)
        
        assert corrected['predicted_speed'] == 0.0  # Clipped to min
        assert corrected['original_predicted_speed'] == -50.0
        assert corrected['speed_was_bounded'] == True  # Use == instead of is
        assert len(warnings) > 0
    
    def test_nan_speed_is_invalidated(self):
        """CRITICAL: Test that NaN speeds are rejected"""
        prediction = {
            'sensor_id': 'sensor_004',
            'predicted_speed': np.nan,
            'confidence_score': 0.6
        }
        
        is_valid, corrected, warnings = self.validator.validate_prediction(prediction)
        
        assert is_valid is False
        assert corrected['predicted_speed'] is None
        assert corrected['validation_status'] == 'INVALID_VALUE'
        assert any('NaN' in w for w in warnings)
    
    def test_infinity_speed_is_invalidated(self):
        """CRITICAL: Test that Infinity speeds are rejected"""
        prediction = {
            'sensor_id': 'sensor_005',
            'predicted_speed': np.inf,
            'confidence_score': 0.6
        }
        
        is_valid, corrected, warnings = self.validator.validate_prediction(prediction)
        
        assert is_valid is False
        assert corrected['predicted_speed'] is None
        assert any('Infinity' in w for w in warnings)
    
    def test_speed_limit_warning(self):
        """Test that predictions exceeding speed limit are flagged"""
        prediction = {
            'sensor_id': 'sensor_006',
            'predicted_speed': 75.0,
            'speed_limit': 45.0,  # 30mph residential zone
            'confidence_score': 0.8
        }
        
        is_valid, corrected, warnings = self.validator.validate_prediction(prediction)
        
        # Should be valid but flagged (traffic can exceed speed limit)
        assert is_valid is True
        assert corrected['predicted_speed'] == 75.0  # Not clipped to speed limit
        assert corrected['exceeds_speed_limit'] is True
        assert any('exceeds speed limit' in w for w in warnings)
    
    def test_volume_bounds(self):
        """Test that traffic volume is bounded"""
        prediction = {
            'sensor_id': 'sensor_007',
            'predicted_speed': 50.0,
            'predicted_volume': 50000,  # Unrealistically high
            'confidence_score': 0.7
        }
        
        is_valid, corrected, warnings = self.validator.validate_prediction(prediction)
        
        assert corrected['predicted_volume'] == 10000  # Clipped to max
        assert len(warnings) > 0
    
    def test_low_confidence_warning(self):
        """Test that low confidence predictions are flagged"""
        prediction = {
            'sensor_id': 'sensor_008',
            'predicted_speed': 55.0,
            'confidence_score': 0.2  # Very low confidence
        }
        
        is_valid, corrected, warnings = self.validator.validate_prediction(prediction)
        
        assert is_valid is True
        assert corrected['display_warning'] == 'LOW_CONFIDENCE'
        assert corrected['suitable_for_routing'] is False
        assert any('low confidence' in w.lower() for w in warnings)
    
    def test_travel_time_calculation(self):
        """Test that travel time is calculated with validated speed"""
        prediction = {
            'sensor_id': 'sensor_009',
            'predicted_speed': 60.0,
            'confidence_score': 0.8
        }
        
        is_valid, corrected, warnings = self.validator.validate_prediction(prediction)
        
        # Travel time = (1 mile / 60 mph) * 3600 seconds = 60 seconds
        assert corrected['predicted_travel_time'] == 60
    
    def test_batch_validation(self):
        """Test batch validation of multiple predictions"""
        predictions = [
            {'sensor_id': 'S1', 'predicted_speed': 55.0, 'confidence_score': 0.8},
            {'sensor_id': 'S2', 'predicted_speed': 500.0, 'confidence_score': 0.7},  # Will be bounded
            {'sensor_id': 'S3', 'predicted_speed': np.nan, 'confidence_score': 0.6},  # Invalid
            {'sensor_id': 'S4', 'predicted_speed': 45.0, 'confidence_score': 0.9},
        ]
        
        corrected, summary = self.validator.validate_batch(predictions)
        
        assert summary['total'] == 4
        assert summary['valid'] == 3  # 3 valid (NaN is invalid)
        assert summary['invalid'] == 1
        assert summary['warnings'] > 0
        
        # Check specific corrections
        assert corrected[0]['predicted_speed'] == 55.0  # Unchanged
        assert corrected[1]['predicted_speed'] == 100.0  # Bounded
        assert corrected[2]['predicted_speed'] is None  # Invalid
        assert corrected[3]['predicted_speed'] == 45.0  # Unchanged
    
    def test_consistency_check(self):
        """Test consistency checking across multiple predictions"""
        predictions = [
            {'sensor_id': 'S1', 'predicted_speed': 50.0},
            {'sensor_id': 'S1', 'predicted_speed': 55.0},  # Small change OK
            {'sensor_id': 'S1', 'predicted_speed': 10.0},  # Large drop 55→10 = 45mph change
        ]
        
        warnings = self.validator.check_prediction_consistency(predictions)
        
        # Should warn about unrealistic speed change 55→10 (45 mph drop)
        assert len(warnings) > 0, f"Expected warnings for large speed change, got: {warnings}"
        assert any('Unrealistic' in w for w in warnings)
    
    def test_safety_summary(self):
        """Test that safety configuration is accessible"""
        summary = self.validator.get_safety_summary()
        
        assert 'speed_range_mph' in summary
        assert summary['speed_range_mph'] == [0.0, 100.0]
        assert summary['validation_active'] is True
    
    def test_custom_config(self):
        """Test custom safety configuration"""
        custom_config = {
            'min_speed': 5.0,
            'max_speed': 80.0
        }
        
        validator = PredictionSafetyValidator(custom_config)
        
        prediction = {'sensor_id': 'S1', 'predicted_speed': 90.0, 'confidence_score': 0.8}
        is_valid, corrected, warnings = validator.validate_prediction(prediction)
        
        # Should be bounded to custom max of 80
        assert corrected['predicted_speed'] == 80.0


class TestConvenienceFunction:
    """Test the convenience function"""
    
    def test_validate_predictions_safe(self):
        """Test convenience function for batch validation"""
        predictions = [
            {'sensor_id': 'S1', 'predicted_speed': 55.0, 'confidence_score': 0.8},
            {'sensor_id': 'S2', 'predicted_speed': 200.0, 'confidence_score': 0.7},
        ]
        
        corrected, summary = validate_predictions_safe(predictions)
        
        assert len(corrected) == 2
        assert corrected[0]['predicted_speed'] == 55.0
        assert corrected[1]['predicted_speed'] == 100.0  # Bounded
        assert summary['total'] == 2
        assert summary['valid'] == 2


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v', '--tb=short'])
