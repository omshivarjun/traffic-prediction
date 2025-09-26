"""
API endpoints for traffic congestion prediction using ML models
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Dict, List, Any, Optional
import logging
from datetime import datetime
import sys
import os

# Add parent directories to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from src.ml.congestion_predictor import TrafficCongestionPredictor
    from src.data.metr_la_processor import MetrLAProcessor
    ML_AVAILABLE = True
except ImportError as e:
    ML_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"ML modules not available: {e}")

router = APIRouter(prefix="/api/ml", tags=["Machine Learning"])

# Global instances
predictor = None
metr_processor = None

if ML_AVAILABLE:
    predictor = TrafficCongestionPredictor()
    metr_processor = MetrLAProcessor()

@router.get("/health")
async def ml_health_check():
    """Check ML service health"""
    return {
        "status": "healthy" if ML_AVAILABLE else "degraded",
        "ml_libraries_available": ML_AVAILABLE,
        "predictor_loaded": predictor is not None and predictor.model is not None,
        "metr_data_available": metr_processor is not None and metr_processor.traffic_data is not None,
        "timestamp": datetime.now().isoformat()
    }

@router.post("/predict/congestion")
async def predict_congestion(features: Dict[str, Any]):
    """
    Predict traffic congestion level for given features
    
    Expected features:
    - hour: Hour of day (0-23)
    - day_of_week: Day of week (0-6, Monday=0)
    - current_speed: Current speed in mph
    - current_volume: Current traffic volume
    - sensor_id: Traffic sensor identifier
    """
    if not ML_AVAILABLE or predictor is None:
        raise HTTPException(
            status_code=503, 
            detail="ML prediction service not available"
        )
    
    try:
        prediction = predictor.predict_congestion(features)
        return {
            "success": True,
            "prediction": prediction,
            "input_features": features
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Prediction failed: {str(e)}"
        )

@router.post("/train")
async def train_model(background_tasks: BackgroundTasks, model_type: str = "random_forest"):
    """
    Train the congestion prediction model using METR-LA data
    """
    if not ML_AVAILABLE or predictor is None or metr_processor is None:
        raise HTTPException(
            status_code=503,
            detail="ML training service not available"
        )
    
    try:
        # Load METR-LA data if not already loaded
        if metr_processor.traffic_data is None:
            data_loaded = metr_processor.load_metr_la_data()
            if not data_loaded:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to load METR-LA dataset"
                )
        
        # Prepare training data
        features, targets = predictor.prepare_training_data(metr_processor.traffic_data)
        
        if len(features) == 0:
            raise HTTPException(
                status_code=500,
                detail="No training data available"
            )
        
        # Train model in background
        def train_in_background():
            result = predictor.train_model(features, targets, model_type)
            if result["status"] == "success":
                predictor.save_model(f"congestion_model_{model_type}.pkl")
                logging.info(f"Model training completed: {result}")
            else:
                logging.error(f"Model training failed: {result}")
        
        background_tasks.add_task(train_in_background)
        
        return {
            "success": True,
            "message": f"Training {model_type} model started in background",
            "training_samples": len(features),
            "features_count": len(features.columns),
            "model_type": model_type
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Training initiation failed: {str(e)}"
        )

@router.get("/model/info")
async def get_model_info():
    """Get information about the current ML model"""
    if not ML_AVAILABLE or predictor is None:
        return {
            "status": "unavailable",
            "message": "ML service not available",
            "ml_libraries_available": False
        }
    
    return predictor.get_model_info()

@router.post("/model/load")
async def load_model(filename: str = "congestion_model.pkl"):
    """Load a trained model from disk"""
    if not ML_AVAILABLE or predictor is None:
        raise HTTPException(
            status_code=503,
            detail="ML service not available"
        )
    
    try:
        success = predictor.load_model(filename)
        if success:
            return {
                "success": True,
                "message": f"Model {filename} loaded successfully",
                "model_info": predictor.get_model_info()
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Model file {filename} not found or failed to load"
            )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Model loading failed: {str(e)}"
        )

@router.get("/hotspots")
async def get_congestion_hotspots(num_hotspots: int = 10):
    """Get current congestion hotspots from METR-LA data"""
    if not ML_AVAILABLE or metr_processor is None:
        # Return mock data if ML not available
        return {
            "hotspots": [
                {
                    "sensor_id": "mock_001",
                    "location_name": "I-405 Northbound (Mock)",
                    "current_speed": 15.2,
                    "congestion_level": "severe",
                    "severity_score": 0.85,
                    "coordinates": {"latitude": 34.0522, "longitude": -118.2437}
                },
                {
                    "sensor_id": "mock_002",
                    "location_name": "US-101 Downtown (Mock)",
                    "current_speed": 22.8,
                    "congestion_level": "heavy",
                    "severity_score": 0.77,
                    "coordinates": {"latitude": 34.0522, "longitude": -118.2437}
                }
            ],
            "total_count": 2,
            "data_source": "mock",
            "timestamp": datetime.now().isoformat()
        }
    
    try:
        # Load data if needed
        if metr_processor.traffic_data is None:
            data_loaded = metr_processor.load_metr_la_data()
            if not data_loaded:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to load traffic data"
                )
        
        hotspots = metr_processor.generate_congestion_hotspots(num_hotspots)
        
        return {
            "hotspots": hotspots,
            "total_count": len(hotspots),
            "data_source": "METR-LA",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate hotspots: {str(e)}"
        )

@router.get("/statistics")
async def get_traffic_statistics():
    """Get overall traffic statistics from METR-LA dataset"""
    if not ML_AVAILABLE or metr_processor is None:
        # Return mock statistics
        return {
            "active_sensors": 207,
            "average_speed": 42.3,
            "congested_sensors": 45,
            "free_flow_sensors": 89,
            "total_data_points": 34272,
            "time_range": {
                "start": "2012-03-01T00:00:00",
                "end": "2012-06-30T23:55:00"
            },
            "data_source": "mock"
        }
    
    try:
        # Load data if needed
        if metr_processor.traffic_data is None:
            data_loaded = metr_processor.load_metr_la_data()
            if not data_loaded:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to load traffic data"
                )
        
        stats = metr_processor.get_traffic_statistics()
        stats["data_source"] = "METR-LA"
        
        return stats
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get statistics: {str(e)}"
        )

@router.post("/simulate/stream")
async def simulate_data_stream(
    background_tasks: BackgroundTasks,
    num_records: int = 100,
    delay_ms: int = 100
):
    """
    Simulate streaming METR-LA data to Kafka (for demo purposes)
    """
    if not ML_AVAILABLE or metr_processor is None:
        raise HTTPException(
            status_code=503,
            detail="Data streaming service not available"
        )
    
    try:
        # Load data if needed
        if metr_processor.traffic_data is None:
            data_loaded = metr_processor.load_metr_la_data()
            if not data_loaded:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to load METR-LA dataset"
                )
        
        # Start streaming in background
        def stream_in_background():
            try:
                metr_processor.stream_historical_data(
                    start_idx=0,
                    max_records=num_records,
                    delay_ms=delay_ms
                )
                logging.info(f"Completed streaming {num_records} records")
            except Exception as e:
                logging.error(f"Streaming failed: {e}")
        
        background_tasks.add_task(stream_in_background)
        
        return {
            "success": True,
            "message": f"Started streaming {num_records} records to Kafka",
            "delay_ms": delay_ms,
            "estimated_duration_seconds": (num_records * delay_ms) / 1000
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start streaming: {str(e)}"
        )