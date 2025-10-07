"""
Tests for SAFETY-CRITICAL Input Data Validator
================================================
Verifies that invalid/dangerous sensor data is rejected BEFORE ML processing.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from validation.input_data_validator import (
    TrafficDataValidator,
    ValidationSeverity,
    validate_traffic_data_safe
)


class TestTrafficDataValidator:
    """Test input data validation"""
    
    def test_valid_traffic_record_passes(self):
        """Normal traffic data should pass validation"""
        validator = TrafficDataValidator()
        
        record = {
            'sensor_id': 'SENSOR_001',
            'timestamp': datetime.now().isoformat(),
            'speed': 55.0,
            'volume': 1200,
            'occupancy': 35.5,
            'speed_limit': 65.0,
            'lane_count': 3
        }
        
        is_valid, issues, corrected = validator.validate_traffic_record(record)
        
        assert is_valid == True
        assert corrected['validation_passed'] == True
        assert corrected['speed'] == 55.0
    
    def test_missing_required_field_rejected(self):
        """Records missing required fields should be rejected"""
        validator = TrafficDataValidator()
        
        record = {
            'sensor_id': 'SENSOR_001',
            'timestamp': datetime.now().isoformat(),
            # Missing 'speed' - REQUIRED
            'volume': 1200
        }
        
        is_valid, issues, corrected = validator.validate_traffic_record(record)
        
        assert is_valid == False
        assert any('speed' in str(issue) and issue.severity == ValidationSeverity.CRITICAL for issue in issues)
        assert validator.validation_stats['total_rejected'] == 1
    
    def test_excessive_speed_bounded(self):
        """Speeds over 120 mph should be bounded (corrected to max)"""
        validator = TrafficDataValidator()
        
        record = {
            'sensor_id': 'SENSOR_001',
            'timestamp': datetime.now().isoformat(),
            'speed': 250.0,  # Impossible highway speed
            'volume': 500
        }
        
        is_valid, issues, corrected = validator.validate_traffic_record(record)
        
        # Should be corrected to MAX_SPEED (120 mph)
        assert corrected['speed'] == 120.0
        assert any('speed' in issue.field for issue in issues)
        assert validator.validation_stats['total_corrected'] >= 1
    
    def test_negative_speed_bounded(self):
        """Negative speeds should be bounded to 0"""
        validator = TrafficDataValidator()
        
        record = {
            'sensor_id': 'SENSOR_001',
            'timestamp': datetime.now().isoformat(),
            'speed': -25.0,  # Impossible negative speed
            'volume': 800
        }
        
        is_valid, issues, corrected = validator.validate_traffic_record(record)
        
        assert corrected['speed'] == 0.0
        assert any('speed' in issue.field for issue in issues)
    
    def test_nan_speed_rejected(self):
        """NaN speeds should be rejected as CRITICAL"""
        validator = TrafficDataValidator()
        
        record = {
            'sensor_id': 'SENSOR_001',
            'timestamp': datetime.now().isoformat(),
            'speed': np.nan,  # Invalid value
            'volume': 1000
        }
        
        is_valid, issues, corrected = validator.validate_traffic_record(record)
        
        assert is_valid == False
        assert any(issue.severity == ValidationSeverity.CRITICAL and 'speed' in issue.field for issue in issues)
    
    def test_infinity_speed_rejected(self):
        """Infinity speeds should be rejected as CRITICAL"""
        validator = TrafficDataValidator()
        
        record = {
            'sensor_id': 'SENSOR_001',
            'timestamp': datetime.now().isoformat(),
            'speed': np.inf,
            'volume': 500
        }
        
        is_valid, issues, corrected = validator.validate_traffic_record(record)
        
        assert is_valid == False
        assert any(issue.severity == ValidationSeverity.CRITICAL for issue in issues)
    
    def test_excessive_volume_bounded(self):
        """Volumes over 15000 should be bounded"""
        validator = TrafficDataValidator()
        
        record = {
            'sensor_id': 'SENSOR_001',
            'timestamp': datetime.now().isoformat(),
            'speed': 45.0,
            'volume': 50000  # Unrealistically high
        }
        
        is_valid, issues, corrected = validator.validate_traffic_record(record)
        
        assert corrected['volume'] == 15000
        assert any('volume' in issue.field for issue in issues)
    
    def test_negative_volume_bounded(self):
        """Negative volumes should be bounded to 0"""
        validator = TrafficDataValidator()
        
        record = {
            'sensor_id': 'SENSOR_001',
            'timestamp': datetime.now().isoformat(),
            'speed': 55.0,
            'volume': -500
        }
        
        is_valid, issues, corrected = validator.validate_traffic_record(record)
        
        assert corrected['volume'] == 0
    
    def test_occupancy_over_100_bounded(self):
        """Occupancy over 100% should be bounded"""
        validator = TrafficDataValidator()
        
        record = {
            'sensor_id': 'SENSOR_001',
            'timestamp': datetime.now().isoformat(),
            'speed': 30.0,
            'volume': 2000,
            'occupancy': 150.0  # Impossible >100%
        }
        
        is_valid, issues, corrected = validator.validate_traffic_record(record)
        
        assert corrected['occupancy'] == 100.0
        assert any('occupancy' in issue.field for issue in issues)
    
    def test_future_timestamp_rejected(self):
        """Timestamps in the future should be rejected"""
        validator = TrafficDataValidator()
        
        future_time = datetime.now() + timedelta(hours=2)
        
        record = {
            'sensor_id': 'SENSOR_001',
            'timestamp': future_time.isoformat(),
            'speed': 55.0,
            'volume': 1000
        }
        
        is_valid, issues, corrected = validator.validate_traffic_record(record)
        
        assert is_valid == False
        assert any('timestamp' in issue.field and issue.severity == ValidationSeverity.CRITICAL for issue in issues)
    
    def test_very_old_timestamp_warned(self):
        """Very old timestamps should generate warning"""
        validator = TrafficDataValidator()
        
        old_time = datetime.now() - timedelta(days=10)
        
        record = {
            'sensor_id': 'SENSOR_001',
            'timestamp': old_time.isoformat(),
            'speed': 55.0,
            'volume': 1000
        }
        
        is_valid, issues, corrected = validator.validate_traffic_record(record)
        
        assert any('timestamp' in issue.field and issue.severity == ValidationSeverity.WARNING for issue in issues)
    
    def test_invalid_speed_limit_rejected(self):
        """Speed limits outside realistic range (5-85 mph) should be rejected"""
        validator = TrafficDataValidator()
        
        record = {
            'sensor_id': 'SENSOR_001',
            'timestamp': datetime.now().isoformat(),
            'speed': 55.0,
            'volume': 1000,
            'speed_limit': 200.0  # Invalid speed limit
        }
        
        is_valid, issues, corrected = validator.validate_traffic_record(record)
        
        assert is_valid == False
        assert any('speed_limit' in issue.field for issue in issues)
    
    def test_low_quality_score_rejected(self):
        """Quality scores below 0.5 should be rejected"""
        validator = TrafficDataValidator()
        
        record = {
            'sensor_id': 'SENSOR_001',
            'timestamp': datetime.now().isoformat(),
            'speed': 55.0,
            'volume': 1000,
            'quality_score': 0.2  # Low quality
        }
        
        is_valid, issues, corrected = validator.validate_traffic_record(record)
        
        assert is_valid == False
        assert any('quality' in issue.field and issue.severity == ValidationSeverity.CRITICAL for issue in issues)
    
    def test_empty_sensor_id_rejected(self):
        """Empty sensor IDs should be rejected"""
        validator = TrafficDataValidator()
        
        record = {
            'sensor_id': '',  # Empty
            'timestamp': datetime.now().isoformat(),
            'speed': 55.0,
            'volume': 1000
        }
        
        is_valid, issues, corrected = validator.validate_traffic_record(record)
        
        assert is_valid == False
        assert any('sensor_id' in issue.field for issue in issues)
    
    def test_high_volume_low_occupancy_warning(self):
        """High volume but low occupancy should generate warning (inconsistent)"""
        validator = TrafficDataValidator()
        
        record = {
            'sensor_id': 'SENSOR_001',
            'timestamp': datetime.now().isoformat(),
            'speed': 55.0,
            'volume': 3000,  # High volume
            'occupancy': 5.0  # Low occupancy - inconsistent
        }
        
        is_valid, issues, corrected = validator.validate_traffic_record(record)
        
        # Should still be valid, but with warning
        assert is_valid == True
        assert any(issue.severity == ValidationSeverity.WARNING for issue in issues)
    
    def test_zero_speed_high_volume_warning(self):
        """Zero speed but high volume should generate warning"""
        validator = TrafficDataValidator()
        
        record = {
            'sensor_id': 'SENSOR_001',
            'timestamp': datetime.now().isoformat(),
            'speed': 0.0,  # Stopped traffic
            'volume': 500  # But significant volume - inconsistent
        }
        
        is_valid, issues, corrected = validator.validate_traffic_record(record)
        
        assert is_valid == True
        assert any('speed_volume' in issue.field for issue in issues)
    
    def test_batch_validation(self):
        """Test batch validation of multiple records"""
        validator = TrafficDataValidator()
        
        records = [
            {  # Valid
                'sensor_id': 'SENSOR_001',
                'timestamp': datetime.now().isoformat(),
                'speed': 55.0,
                'volume': 1200
            },
            {  # Valid
                'sensor_id': 'SENSOR_002',
                'timestamp': datetime.now().isoformat(),
                'speed': 45.0,
                'volume': 1500
            },
            {  # Invalid - NaN speed
                'sensor_id': 'SENSOR_003',
                'timestamp': datetime.now().isoformat(),
                'speed': np.nan,
                'volume': 1000
            },
            {  # Invalid - missing required field
                'sensor_id': 'SENSOR_004',
                'timestamp': datetime.now().isoformat(),
                # Missing 'speed'
                'volume': 800
            }
        ]
        
        valid, invalid, summary = validator.validate_batch(records)
        
        assert summary['total'] == 4
        assert summary['valid'] == 2
        assert summary['invalid'] == 2
        assert summary['validation_rate'] == 50.0
    
    def test_validation_stats_tracking(self):
        """Test that validation statistics are tracked correctly"""
        validator = TrafficDataValidator()
        
        # Valid record
        validator.validate_traffic_record({
            'sensor_id': 'SENSOR_001',
            'timestamp': datetime.now().isoformat(),
            'speed': 55.0,
            'volume': 1200
        })
        
        # Invalid record (NaN)
        validator.validate_traffic_record({
            'sensor_id': 'SENSOR_002',
            'timestamp': datetime.now().isoformat(),
            'speed': np.nan,
            'volume': 1000
        })
        
        # Invalid record (excessive speed - corrected)
        validator.validate_traffic_record({
            'sensor_id': 'SENSOR_003',
            'timestamp': datetime.now().isoformat(),
            'speed': 250.0,
            'volume': 500
        })
        
        stats = validator.get_validation_stats()
        
        assert stats['total_validated'] == 3
        assert stats['total_rejected'] >= 1  # NaN rejection
        assert stats['total_corrected'] >= 1  # Speed bounded
        assert 'invalid_speed' in stats['rejection_reasons']


class TestConvenienceFunction:
    """Test convenience function"""
    
    def test_validate_traffic_data_safe(self):
        """Test convenience function for batch validation"""
        data = [
            {
                'sensor_id': 'SENSOR_001',
                'timestamp': datetime.now().isoformat(),
                'speed': 55.0,
                'volume': 1200
            },
            {
                'sensor_id': 'SENSOR_002',
                'timestamp': datetime.now().isoformat(),
                'speed': np.nan,  # Invalid
                'volume': 1000
            }
        ]
        
        valid, summary = validate_traffic_data_safe(data)
        
        assert len(valid) == 1  # Only first record valid
        assert summary['total'] == 2
        assert summary['valid'] == 1
        assert summary['invalid'] == 1


class TestExtremeCases:
    """Test extreme edge cases"""
    
    def test_all_fields_null(self):
        """Record with all null values should be rejected"""
        validator = TrafficDataValidator()
        
        record = {
            'sensor_id': None,
            'timestamp': None,
            'speed': None,
            'volume': None
        }
        
        is_valid, issues, corrected = validator.validate_traffic_record(record)
        
        assert is_valid == False
        assert len(issues) >= 4  # All required fields failed
    
    def test_extreme_temperature(self):
        """Extreme temperatures should be bounded"""
        validator = TrafficDataValidator()
        
        record = {
            'sensor_id': 'SENSOR_001',
            'timestamp': datetime.now().isoformat(),
            'speed': 55.0,
            'volume': 1200,
            'temperature_c': 100.0  # Extremely hot
        }
        
        is_valid, issues, corrected = validator.validate_traffic_record(record)
        
        assert corrected['temperature_c'] == 60.0  # Bounded to MAX_TEMP_C
    
    def test_invalid_timestamp_string(self):
        """Invalid timestamp string should be rejected"""
        validator = TrafficDataValidator()
        
        record = {
            'sensor_id': 'SENSOR_001',
            'timestamp': 'not-a-timestamp',
            'speed': 55.0,
            'volume': 1200
        }
        
        is_valid, issues, corrected = validator.validate_traffic_record(record)
        
        assert is_valid == False
        assert any('timestamp' in issue.field for issue in issues)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
