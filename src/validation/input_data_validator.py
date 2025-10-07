"""
SAFETY-CRITICAL: Input Data Validation System
==============================================
Validates incoming traffic sensor data BEFORE it enters the ML prediction pipeline.
This prevents garbage data from producing dangerous false predictions.

CRITICAL: All sensor data must pass validation before being used for predictions.
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationSeverity(Enum):
    """Severity levels for validation failures"""
    CRITICAL = "CRITICAL"  # Data must be rejected
    WARNING = "WARNING"    # Data flagged but usable
    INFO = "INFO"         # Informational only


@dataclass
class ValidationResult:
    """Result of data validation"""
    is_valid: bool
    severity: ValidationSeverity
    field: str
    message: str
    original_value: Any
    corrected_value: Optional[Any] = None
    
    def __str__(self):
        return f"[{self.severity.value}] {self.field}: {self.message}"


class TrafficDataValidator:
    """
    SAFETY-CRITICAL: Validates traffic sensor data for realistic values
    
    Prevents invalid sensor data from entering the ML pipeline and
    producing false predictions that could cause accidents.
    """
    
    # Physical constraints for traffic sensor data
    MIN_SPEED = 0.0  # mph - minimum possible speed
    MAX_SPEED = 120.0  # mph - maximum realistic highway speed
    
    MIN_VOLUME = 0  # vehicles per time period
    MAX_VOLUME = 15000  # vehicles per hour (extremely busy highway)
    
    MIN_OCCUPANCY = 0.0  # percent
    MAX_OCCUPANCY = 100.0  # percent
    
    MIN_SPEED_LIMIT = 5.0  # mph - school zones
    MAX_SPEED_LIMIT = 85.0  # mph - highest US speed limit
    
    MIN_LANE_COUNT = 1
    MAX_LANE_COUNT = 8  # maximum realistic lanes per direction
    
    # Temperature ranges (Celsius)
    MIN_TEMP_C = -40.0  # extreme cold
    MAX_TEMP_C = 60.0   # extreme heat
    
    # Humidity ranges
    MIN_HUMIDITY = 0.0
    MAX_HUMIDITY = 100.0
    
    # Quality score ranges
    MIN_QUALITY = 0.0
    MAX_QUALITY = 1.0
    
    # Time constraints
    MAX_FUTURE_TIME = timedelta(minutes=5)  # Allow small clock skew
    MAX_PAST_TIME = timedelta(days=7)  # Ignore very old data
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize traffic data validator
        
        Args:
            config: Optional configuration dict for custom bounds
        """
        self.config = config or {}
        self.validation_stats = {
            'total_validated': 0,
            'total_rejected': 0,
            'total_corrected': 0,
            'rejection_reasons': {}
        }
        
        logger.info("TrafficDataValidator initialized")
    
    def validate_traffic_record(self, record: Dict) -> Tuple[bool, List[ValidationResult], Dict]:
        """
        Validate a single traffic sensor record
        
        Args:
            record: Traffic data record dict
        
        Returns:
            Tuple of:
            - is_valid: Whether record is safe to use
            - validation_results: List of validation issues found
            - corrected_record: Record with corrections applied
        
        CRITICAL: Always call this before using sensor data for predictions
        """
        results = []
        corrected = record.copy()
        is_valid = True
        
        self.validation_stats['total_validated'] += 1
        
        # 1. Validate required fields exist
        required_fields = ['sensor_id', 'timestamp', 'speed', 'volume']
        for field in required_fields:
            if field not in record or record[field] is None:
                results.append(ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.CRITICAL,
                    field=field,
                    message=f"Required field missing or null",
                    original_value=record.get(field)
                ))
                is_valid = False
                self._record_rejection(f"missing_{field}")
        
        if not is_valid:
            self.validation_stats['total_rejected'] += 1
            return False, results, corrected
        
        # 2. Validate timestamp
        timestamp_result = self._validate_timestamp(record.get('timestamp'))
        if timestamp_result:
            results.append(timestamp_result)
            if timestamp_result.severity == ValidationSeverity.CRITICAL:
                is_valid = False
                self._record_rejection('invalid_timestamp')
        
        # 3. Validate speed
        if 'speed' in record:
            speed_result, corrected_speed = self._validate_speed(
                record['speed'], 
                record.get('speed_limit')
            )
            if speed_result:
                results.append(speed_result)
                if speed_result.corrected_value is not None:
                    corrected['speed'] = speed_result.corrected_value
                    self.validation_stats['total_corrected'] += 1
                elif speed_result.severity == ValidationSeverity.CRITICAL:
                    is_valid = False
                    self._record_rejection('invalid_speed')
        
        # 4. Validate volume
        if 'volume' in record:
            volume_result = self._validate_volume(record['volume'])
            if volume_result:
                results.append(volume_result)
                if volume_result.corrected_value is not None:
                    corrected['volume'] = volume_result.corrected_value
                    self.validation_stats['total_corrected'] += 1
                elif volume_result.severity == ValidationSeverity.CRITICAL:
                    is_valid = False
                    self._record_rejection('invalid_volume')
        
        # 5. Validate occupancy
        if 'occupancy' in record and record['occupancy'] is not None:
            occ_result = self._validate_occupancy(record['occupancy'])
            if occ_result:
                results.append(occ_result)
                if occ_result.corrected_value is not None:
                    corrected['occupancy'] = occ_result.corrected_value
                elif occ_result.severity == ValidationSeverity.CRITICAL:
                    is_valid = False
                    self._record_rejection('invalid_occupancy')
        
        # 6. Validate speed limit
        if 'speed_limit' in record and record['speed_limit'] is not None:
            limit_result = self._validate_speed_limit(record['speed_limit'])
            if limit_result:
                results.append(limit_result)
                if limit_result.severity == ValidationSeverity.CRITICAL:
                    is_valid = False
                    self._record_rejection('invalid_speed_limit')
        
        # 7. Validate lane count
        if 'lane_count' in record and record['lane_count'] is not None:
            lane_result = self._validate_lane_count(record['lane_count'])
            if lane_result:
                results.append(lane_result)
                if lane_result.corrected_value is not None:
                    corrected['lane_count'] = lane_result.corrected_value
        
        # 8. Validate temperature
        if 'temperature_c' in record and record['temperature_c'] is not None:
            temp_result = self._validate_temperature(record['temperature_c'])
            if temp_result:
                results.append(temp_result)
                if temp_result.corrected_value is not None:
                    corrected['temperature_c'] = temp_result.corrected_value
        
        # 9. Validate humidity
        if 'humidity_percent' in record and record['humidity_percent'] is not None:
            hum_result = self._validate_humidity(record['humidity_percent'])
            if hum_result:
                results.append(hum_result)
                if hum_result.corrected_value is not None:
                    corrected['humidity_percent'] = hum_result.corrected_value
        
        # 10. Validate quality score
        if 'quality_score' in record and record['quality_score'] is not None:
            qual_result = self._validate_quality_score(record['quality_score'])
            if qual_result:
                results.append(qual_result)
                if qual_result.severity == ValidationSeverity.CRITICAL:
                    is_valid = False
                    self._record_rejection('low_quality_score')
        
        # 11. Validate sensor ID format
        if 'sensor_id' in record:
            sensor_result = self._validate_sensor_id(record['sensor_id'])
            if sensor_result and sensor_result.severity == ValidationSeverity.CRITICAL:
                results.append(sensor_result)
                is_valid = False
                self._record_rejection('invalid_sensor_id')
        
        # 12. Cross-field validation (consistency checks)
        consistency_results = self._validate_consistency(corrected)
        results.extend(consistency_results)
        
        if not is_valid:
            self.validation_stats['total_rejected'] += 1
        
        # Add validation metadata
        corrected['validation_passed'] = is_valid
        corrected['validation_issues'] = len(results)
        corrected['validation_timestamp'] = datetime.now().isoformat()
        
        return is_valid, results, corrected
    
    def _validate_timestamp(self, timestamp: Any) -> Optional[ValidationResult]:
        """Validate timestamp is recent and not in future"""
        try:
            if isinstance(timestamp, str):
                ts = pd.to_datetime(timestamp)
            elif isinstance(timestamp, (pd.Timestamp, datetime)):
                ts = pd.to_datetime(timestamp)
            else:
                return ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.CRITICAL,
                    field='timestamp',
                    message=f"Invalid timestamp type: {type(timestamp)}",
                    original_value=timestamp
                )
            
            now = pd.Timestamp.now()
            
            # Check if too far in future
            if ts > now + self.MAX_FUTURE_TIME:
                return ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.CRITICAL,
                    field='timestamp',
                    message=f"Timestamp in future: {ts}",
                    original_value=timestamp
                )
            
            # Check if too old
            if ts < now - self.MAX_PAST_TIME:
                return ValidationResult(
                    is_valid=False,
                    severity=ValidationSeverity.WARNING,
                    field='timestamp',
                    message=f"Timestamp very old: {ts}",
                    original_value=timestamp
                )
            
            return None
            
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.CRITICAL,
                field='timestamp',
                message=f"Cannot parse timestamp: {str(e)}",
                original_value=timestamp
            )
    
    def _validate_speed(self, speed: Any, speed_limit: Optional[float] = None) -> Tuple[Optional[ValidationResult], Optional[float]]:
        """Validate speed is realistic"""
        # Check for invalid types
        if speed is None or (isinstance(speed, float) and (np.isnan(speed) or np.isinf(speed))):
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.CRITICAL,
                field='speed',
                message=f"Invalid speed value: {speed}",
                original_value=speed
            ), None
        
        try:
            speed_val = float(speed)
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.CRITICAL,
                field='speed',
                message=f"Cannot convert speed to number: {speed}",
                original_value=speed
            ), None
        
        # Check bounds
        if speed_val < self.MIN_SPEED:
            return ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.WARNING,
                field='speed',
                message=f"Speed below minimum: {speed_val} mph",
                original_value=speed_val,
                corrected_value=self.MIN_SPEED
            ), self.MIN_SPEED
        
        if speed_val > self.MAX_SPEED:
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.CRITICAL,
                field='speed',
                message=f"Speed exceeds maximum: {speed_val} mph (max {self.MAX_SPEED})",
                original_value=speed_val,
                corrected_value=self.MAX_SPEED
            ), self.MAX_SPEED
        
        # Warning if significantly over speed limit
        if speed_limit and speed_val > speed_limit * 1.5:
            return ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.WARNING,
                field='speed',
                message=f"Speed {speed_val} mph significantly exceeds limit {speed_limit} mph",
                original_value=speed_val
            ), None
        
        return None, None
    
    def _validate_volume(self, volume: Any) -> Optional[ValidationResult]:
        """Validate traffic volume is realistic"""
        if volume is None or (isinstance(volume, float) and (np.isnan(volume) or np.isinf(volume))):
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.CRITICAL,
                field='volume',
                message=f"Invalid volume value: {volume}",
                original_value=volume
            )
        
        try:
            vol_val = int(volume)
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.CRITICAL,
                field='volume',
                message=f"Cannot convert volume to number: {volume}",
                original_value=volume
            )
        
        if vol_val < self.MIN_VOLUME:
            return ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.WARNING,
                field='volume',
                message=f"Volume below minimum: {vol_val}",
                original_value=vol_val,
                corrected_value=self.MIN_VOLUME
            )
        
        if vol_val > self.MAX_VOLUME:
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.CRITICAL,
                field='volume',
                message=f"Volume exceeds maximum: {vol_val} (max {self.MAX_VOLUME})",
                original_value=vol_val,
                corrected_value=self.MAX_VOLUME
            )
        
        return None
    
    def _validate_occupancy(self, occupancy: Any) -> Optional[ValidationResult]:
        """Validate occupancy percentage"""
        if np.isnan(occupancy) or np.isinf(occupancy):
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.CRITICAL,
                field='occupancy',
                message=f"Invalid occupancy: {occupancy}",
                original_value=occupancy
            )
        
        occ_val = float(occupancy)
        
        if occ_val < self.MIN_OCCUPANCY:
            return ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.WARNING,
                field='occupancy',
                message=f"Occupancy below 0%: {occ_val}",
                original_value=occ_val,
                corrected_value=self.MIN_OCCUPANCY
            )
        
        if occ_val > self.MAX_OCCUPANCY:
            return ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.WARNING,
                field='occupancy',
                message=f"Occupancy above 100%: {occ_val}",
                original_value=occ_val,
                corrected_value=self.MAX_OCCUPANCY
            )
        
        return None
    
    def _validate_speed_limit(self, speed_limit: Any) -> Optional[ValidationResult]:
        """Validate speed limit is realistic"""
        try:
            limit_val = float(speed_limit)
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.CRITICAL,
                field='speed_limit',
                message=f"Invalid speed limit: {speed_limit}",
                original_value=speed_limit
            )
        
        if limit_val < self.MIN_SPEED_LIMIT or limit_val > self.MAX_SPEED_LIMIT:
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.CRITICAL,
                field='speed_limit',
                message=f"Speed limit out of range: {limit_val} (range {self.MIN_SPEED_LIMIT}-{self.MAX_SPEED_LIMIT})",
                original_value=limit_val
            )
        
        return None
    
    def _validate_lane_count(self, lane_count: Any) -> Optional[ValidationResult]:
        """Validate lane count is realistic"""
        try:
            lanes = int(lane_count)
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.WARNING,
                field='lane_count',
                message=f"Invalid lane count: {lane_count}",
                original_value=lane_count,
                corrected_value=2  # Default to 2 lanes
            )
        
        if lanes < self.MIN_LANE_COUNT:
            return ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.WARNING,
                field='lane_count',
                message=f"Lane count too low: {lanes}",
                original_value=lanes,
                corrected_value=1
            )
        
        if lanes > self.MAX_LANE_COUNT:
            return ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.WARNING,
                field='lane_count',
                message=f"Lane count very high: {lanes}",
                original_value=lanes
            )
        
        return None
    
    def _validate_temperature(self, temp: Any) -> Optional[ValidationResult]:
        """Validate temperature is realistic"""
        try:
            temp_val = float(temp)
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.INFO,
                field='temperature_c',
                message=f"Invalid temperature: {temp}",
                original_value=temp,
                corrected_value=None
            )
        
        if temp_val < self.MIN_TEMP_C or temp_val > self.MAX_TEMP_C:
            return ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.WARNING,
                field='temperature_c',
                message=f"Temperature extreme: {temp_val}°C",
                original_value=temp_val,
                corrected_value=np.clip(temp_val, self.MIN_TEMP_C, self.MAX_TEMP_C)
            )
        
        return None
    
    def _validate_humidity(self, humidity: Any) -> Optional[ValidationResult]:
        """Validate humidity percentage"""
        try:
            hum_val = float(humidity)
        except (ValueError, TypeError):
            return None
        
        if hum_val < self.MIN_HUMIDITY or hum_val > self.MAX_HUMIDITY:
            return ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.WARNING,
                field='humidity_percent',
                message=f"Humidity out of range: {hum_val}%",
                original_value=hum_val,
                corrected_value=np.clip(hum_val, self.MIN_HUMIDITY, self.MAX_HUMIDITY)
            )
        
        return None
    
    def _validate_quality_score(self, quality: Any) -> Optional[ValidationResult]:
        """Validate data quality score"""
        try:
            qual_val = float(quality)
        except (ValueError, TypeError):
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.CRITICAL,
                field='quality_score',
                message=f"Invalid quality score: {quality}",
                original_value=quality
            )
        
        if qual_val < 0.5:  # Low quality threshold
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.CRITICAL,
                field='quality_score',
                message=f"Quality score too low: {qual_val}",
                original_value=qual_val
            )
        
        return None
    
    def _validate_sensor_id(self, sensor_id: Any) -> Optional[ValidationResult]:
        """Validate sensor ID format"""
        if not sensor_id or (isinstance(sensor_id, str) and len(sensor_id.strip()) == 0):
            return ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.CRITICAL,
                field='sensor_id',
                message="Empty sensor ID",
                original_value=sensor_id
            )
        
        return None
    
    def _validate_consistency(self, record: Dict) -> List[ValidationResult]:
        """Cross-field consistency validation"""
        results = []
        
        # Check: High volume but very low occupancy is suspicious
        if ('volume' in record and 'occupancy' in record and 
            record['volume'] is not None and record['occupancy'] is not None):
            
            vol = record['volume']
            occ = record['occupancy']
            
            if vol > 2000 and occ < 10:  # High volume, low occupancy
                results.append(ValidationResult(
                    is_valid=True,
                    severity=ValidationSeverity.WARNING,
                    field='volume_occupancy',
                    message=f"Inconsistent: high volume ({vol}) but low occupancy ({occ}%)",
                    original_value=(vol, occ)
                ))
        
        # Check: Zero speed but non-zero volume is suspicious
        if ('speed' in record and 'volume' in record and 
            record['speed'] is not None and record['volume'] is not None):
            
            speed = record['speed']
            vol = record['volume']
            
            if speed == 0 and vol > 100:
                results.append(ValidationResult(
                    is_valid=True,
                    severity=ValidationSeverity.WARNING,
                    field='speed_volume',
                    message=f"Inconsistent: zero speed but volume={vol}",
                    original_value=(speed, vol)
                ))
        
        return results
    
    def _record_rejection(self, reason: str):
        """Track rejection reasons for reporting"""
        if reason not in self.validation_stats['rejection_reasons']:
            self.validation_stats['rejection_reasons'][reason] = 0
        self.validation_stats['rejection_reasons'][reason] += 1
    
    def validate_batch(self, records: List[Dict]) -> Tuple[List[Dict], List[Dict], Dict]:
        """
        Validate a batch of traffic records
        
        Args:
            records: List of traffic data records
        
        Returns:
            Tuple of:
            - valid_records: Records that passed validation
            - invalid_records: Records that failed validation
            - summary: Validation summary statistics
        """
        valid_records = []
        invalid_records = []
        all_issues = []
        
        for record in records:
            is_valid, issues, corrected = self.validate_traffic_record(record)
            
            if is_valid:
                valid_records.append(corrected)
            else:
                invalid_records.append({
                    'original': record,
                    'issues': [str(issue) for issue in issues]
                })
            
            all_issues.extend(issues)
        
        summary = {
            'total': len(records),
            'valid': len(valid_records),
            'invalid': len(invalid_records),
            'validation_rate': (len(valid_records) / len(records) * 100) if records else 0,
            'critical_issues': sum(1 for issue in all_issues if issue.severity == ValidationSeverity.CRITICAL),
            'warnings': sum(1 for issue in all_issues if issue.severity == ValidationSeverity.WARNING),
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(
            f"Batch validation: {summary['valid']}/{summary['total']} valid "
            f"({summary['validation_rate']:.1f}%), "
            f"{summary['critical_issues']} critical issues, "
            f"{summary['warnings']} warnings"
        )
        
        return valid_records, invalid_records, summary
    
    def get_validation_stats(self) -> Dict:
        """Get validation statistics"""
        return self.validation_stats.copy()
    
    def reset_stats(self):
        """Reset validation statistics"""
        self.validation_stats = {
            'total_validated': 0,
            'total_rejected': 0,
            'total_corrected': 0,
            'rejection_reasons': {}
        }


def validate_traffic_data_safe(data: List[Dict]) -> Tuple[List[Dict], Dict]:
    """
    Convenience function to validate traffic data
    
    CRITICAL: Always call this before using sensor data for predictions
    
    Args:
        data: List of traffic sensor records
    
    Returns:
        Tuple of (valid_records, validation_summary)
    """
    validator = TrafficDataValidator()
    valid, invalid, summary = validator.validate_batch(data)
    return valid, summary
