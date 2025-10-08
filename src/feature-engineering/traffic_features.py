"""
Traffic Feature Extraction Module

Extracts traffic-specific features that capture road conditions.
CRITICAL: Includes traffic_efficiency feature (81% importance in Random Forest).

Task 3.3: Traffic Feature Extraction (MOST IMPORTANT)
"""

from pyspark.sql import DataFrame
from pyspark.sql.functions import (
    col, when, coalesce, lit, greatest
)


class TrafficFeatureExtractor:
    """
    Extract traffic condition features from real-time traffic data.
    
    CRITICAL FEATURE:
    - traffic_efficiency: Ratio of current speed to free-flow speed (0-1 scale)
      This is the MOST IMPORTANT feature with ~81% importance in Random Forest model.
      
      Interpretation:
      - traffic_efficiency = 1.0: Free-flowing traffic (current speed = free-flow speed)
      - traffic_efficiency = 0.5: Congested (current speed is 50% of free-flow)
      - traffic_efficiency = 0.2: Heavily congested (current speed is 20% of free-flow)
    
    Additional features:
    - speed_normalized: Current speed / max highway speed (0-1 scale)
    - volume_normalized: Traffic volume / capacity estimate
    - congestion_index: Combined measure of congestion level
    """
    
    # Free-flow speed assumptions by highway type (mph)
    FREE_FLOW_SPEEDS = {
        "I-5": 70,
        "I-10": 70,
        "I-110": 65,
        "I-405": 65,
        "US-101": 65,
        "default": 65
    }
    
    # Max volume assumptions (vehicles/hour/lane)
    MAX_VOLUME_PER_LANE = 2000
    
    def __init__(self,
                 speed_col: str = "speed",
                 volume_col: str = "volume",
                 occupancy_col: str = "occupancy",
                 highway_col: str = "highway",
                 num_lanes_col: str = "num_lanes"):
        """
        Initialize the traffic feature extractor.
        
        Args:
            speed_col: Name of speed column (mph)
            volume_col: Name of volume column (vehicles/hour)
            occupancy_col: Name of occupancy column (0-1 or 0-100)
            highway_col: Name of highway identifier column
            num_lanes_col: Name of number of lanes column
        """
        self.speed_col = speed_col
        self.volume_col = volume_col
        self.occupancy_col = occupancy_col
        self.highway_col = highway_col
        self.num_lanes_col = num_lanes_col
        
    def extract_features(self, df: DataFrame) -> DataFrame:
        """
        Extract traffic features from the DataFrame.
        
        Args:
            df: Spark DataFrame with traffic measurements
            
        Returns:
            DataFrame with additional traffic feature columns
            
        CRITICAL:
        - traffic_efficiency = speed / free_flow_speed
          This feature should have ~81% importance in the Random Forest model!
        """
        # Calculate free-flow speed based on highway type
        df = df.withColumn(
            "free_flow_speed",
            when(col(self.highway_col) == "I-5", lit(self.FREE_FLOW_SPEEDS["I-5"]))
            .when(col(self.highway_col) == "I-10", lit(self.FREE_FLOW_SPEEDS["I-10"]))
            .when(col(self.highway_col) == "I-110", lit(self.FREE_FLOW_SPEEDS["I-110"]))
            .when(col(self.highway_col) == "I-405", lit(self.FREE_FLOW_SPEEDS["I-405"]))
            .when(col(self.highway_col) == "US-101", lit(self.FREE_FLOW_SPEEDS["US-101"]))
            .otherwise(lit(self.FREE_FLOW_SPEEDS["default"]))
        )
        
        # CRITICAL: traffic_efficiency = speed / free_flow_speed
        # This is the MOST IMPORTANT feature for prediction accuracy
        # Bounded to [0, 1] range
        df = df.withColumn(
            "traffic_efficiency",
            when(
                col(self.speed_col).isNull() | (col(self.speed_col) <= 0),
                lit(0.0)
            ).otherwise(
                # Ensure we don't exceed 1.0 (speed can occasionally exceed free-flow)
                when(
                    col(self.speed_col) / col("free_flow_speed") > 1.0,
                    lit(1.0)
                ).otherwise(
                    col(self.speed_col) / col("free_flow_speed")
                )
            )
        )
        
        # Normalize speed (0-1 scale based on highway max speed)
        df = df.withColumn(
            "speed_normalized",
            when(
                col(self.speed_col).isNull() | (col(self.speed_col) <= 0),
                lit(0.0)
            ).otherwise(
                when(
                    col(self.speed_col) / col("free_flow_speed") > 1.0,
                    lit(1.0)
                ).otherwise(
                    col(self.speed_col) / col("free_flow_speed")
                )
            )
        )
        
        # Calculate capacity based on number of lanes
        df = df.withColumn(
            "lane_capacity",
            coalesce(col(self.num_lanes_col), lit(3)) * lit(self.MAX_VOLUME_PER_LANE)
        )
        
        # Normalize volume (0-1 scale)
        df = df.withColumn(
            "volume_normalized",
            when(
                col(self.volume_col).isNull() | (col(self.volume_col) <= 0),
                lit(0.0)
            ).otherwise(
                when(
                    col(self.volume_col) / col("lane_capacity") > 1.0,
                    lit(1.0)
                ).otherwise(
                    col(self.volume_col) / col("lane_capacity")
                )
            )
        )
        
        # Congestion index: Weighted combination of traffic factors
        # Higher values = more congested
        # Formula: 0.7 * (1 - traffic_efficiency) + 0.2 * volume_normalized + 0.1 * occupancy
        
        # Normalize occupancy if it's in 0-100 range
        df = df.withColumn(
            "occupancy_norm",
            when(
                col(self.occupancy_col).isNull(),
                lit(0.0)
            ).when(
                col(self.occupancy_col) > 1.0,  # Assume 0-100 scale
                col(self.occupancy_col) / 100.0
            ).otherwise(
                col(self.occupancy_col)
            )
        )
        
        df = df.withColumn(
            "congestion_index",
            (lit(0.7) * (lit(1.0) - col("traffic_efficiency"))) +
            (lit(0.2) * col("volume_normalized")) +
            (lit(0.1) * col("occupancy_norm"))
        )
        
        # Drop intermediate columns
        df = df.drop("free_flow_speed", "lane_capacity", "occupancy_norm")
        
        return df
    
    def get_feature_names(self) -> list:
        """
        Get the list of feature names generated by this extractor.
        
        Returns:
            List of feature column names
        """
        return [
            "traffic_efficiency",  # CRITICAL: 81% importance
            "speed_normalized",
            "volume_normalized",
            "congestion_index"
        ]


# Example usage
if __name__ == "__main__":
    from pyspark.sql import SparkSession
    from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType
    
    # Create Spark session
    spark = SparkSession.builder \
        .appName("TrafficFeatureExtractorTest") \
        .getOrCreate()
    
    # Create sample data
    schema = StructType([
        StructField("segment_id", StringType(), False),
        StructField("highway", StringType(), False),
        StructField("speed", DoubleType(), False),
        StructField("volume", DoubleType(), False),
        StructField("occupancy", DoubleType(), False),
        StructField("num_lanes", IntegerType(), True)
    ])
    
    data = [
        # Free-flowing traffic
        ("LA_001", "I-5", 68.0, 1200, 0.30, 4),
        # Moderate congestion
        ("LA_002", "I-10", 45.0, 1800, 0.55, 3),
        # Heavy congestion
        ("LA_003", "I-110", 22.0, 1950, 0.85, 3),
        # Light congestion
        ("LA_004", "I-405", 55.0, 1500, 0.45, 4),
        # Very heavy congestion
        ("LA_005", "US-101", 15.0, 1980, 0.92, 3),
    ]
    
    df = spark.createDataFrame(data, schema)
    
    # Extract features
    extractor = TrafficFeatureExtractor()
    df_with_features = extractor.extract_features(df)
    
    # Show results
    print("\nTraffic Features Extracted:")
    print("=" * 100)
    df_with_features.select(
        "segment_id", "highway", "speed",
        "traffic_efficiency",
        "speed_normalized",
        "volume_normalized",
        "congestion_index"
    ).show(truncate=False)
    
    print("\nFeature Names:")
    print(extractor.get_feature_names())
    
    print("\nCRITICAL: traffic_efficiency feature")
    print("This feature should have ~81% importance in the Random Forest model!")
    print("\nInterpretation:")
    print("  1.0 = Free-flowing (speed = free-flow speed)")
    print("  0.7 = Light congestion (speed = 70% of free-flow)")
    print("  0.5 = Moderate congestion (speed = 50% of free-flow)")
    print("  0.3 = Heavy congestion (speed = 30% of free-flow)")
    print("  0.2 = Severe congestion (speed = 20% of free-flow)")
    
    spark.stop()
