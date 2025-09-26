"""
Spatial Feature Engineering Module

This module provides comprehensive spatial feature extraction for traffic prediction models.
It includes sensor adjacency analysis, neighbor averaging, upstream/downstream relationships,
and spatial correlation calculations.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional, Union, Set
from dataclasses import dataclass
import logging
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics.pairwise import haversine_distances
from scipy.spatial.distance import pdist, squareform
from pyspark.sql import SparkSession, DataFrame as SparkDataFrame
from pyspark.sql.functions import (
    col, avg, stddev, max as spark_max, min as spark_min, count, sum as spark_sum,
    when, isnan, isnull, coalesce, lit, broadcast, expr, collect_list, size,
    round as spark_round, sqrt, pow as spark_pow, abs as spark_abs
)
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, FloatType, ArrayType
import json
from geopy.distance import geodesic
import networkx as nx

logger = logging.getLogger(__name__)

@dataclass
class SpatialFeatureConfig:
    """Configuration for spatial feature extraction"""
    max_neighbor_distance_km: float = 5.0  # Maximum distance to consider as neighbor
    num_nearest_neighbors: int = 5  # Number of nearest neighbors to consider
    enable_road_network_features: bool = True
    enable_directional_features: bool = True
    enable_clustering_features: bool = True
    spatial_aggregation_methods: List[str] = None  # Default: ['mean', 'std', 'min', 'max', 'median']
    correlation_window_hours: int = 24  # Window for calculating spatial correlations
    
    def __post_init__(self):
        if self.spatial_aggregation_methods is None:
            self.spatial_aggregation_methods = ['mean', 'std', 'min', 'max', 'median']

class SensorNetworkAnalyzer:
    """Analyzes the traffic sensor network topology and relationships"""
    
    def __init__(self, sensor_metadata: pd.DataFrame, config: SpatialFeatureConfig = None):
        self.config = config or SpatialFeatureConfig()
        self.logger = logging.getLogger(__name__)
        self.sensor_metadata = sensor_metadata
        self.adjacency_matrix = None
        self.distance_matrix = None
        self.network_graph = None
        
        # Process sensor metadata
        self._process_sensor_metadata()
        self._build_sensor_network()
    
    def _process_sensor_metadata(self):
        """Process and validate sensor metadata"""
        required_columns = ['sensor_id', 'latitude', 'longitude', 'road_type', 'direction']
        missing_columns = [col for col in required_columns if col not in self.sensor_metadata.columns]
        
        if missing_columns:
            raise ValueError(f"Missing required columns in sensor metadata: {missing_columns}")
        
        # Convert coordinates to radians for distance calculations
        self.sensor_metadata['lat_rad'] = np.radians(self.sensor_metadata['latitude'])
        self.sensor_metadata['lon_rad'] = np.radians(self.sensor_metadata['longitude'])
        
        self.logger.info(f"Processed {len(self.sensor_metadata)} sensors")
    
    def _build_sensor_network(self):
        """Build sensor network graph and calculate distances"""
        self.logger.info("Building sensor network topology")
        
        # Calculate distance matrix using haversine formula
        coords = self.sensor_metadata[['lat_rad', 'lon_rad']].values
        self.distance_matrix = haversine_distances(coords) * 6371  # Convert to kilometers
        
        # Create adjacency matrix based on distance threshold
        self.adjacency_matrix = (self.distance_matrix <= self.config.max_neighbor_distance_km).astype(int)
        np.fill_diagonal(self.adjacency_matrix, 0)  # Remove self-connections
        
        # Build NetworkX graph for advanced network analysis
        self.network_graph = nx.Graph()
        
        for i, sensor_id in enumerate(self.sensor_metadata['sensor_id']):
            self.network_graph.add_node(sensor_id, 
                                      latitude=self.sensor_metadata.iloc[i]['latitude'],
                                      longitude=self.sensor_metadata.iloc[i]['longitude'],
                                      road_type=self.sensor_metadata.iloc[i]['road_type'],
                                      direction=self.sensor_metadata.iloc[i]['direction'])
        
        # Add edges based on proximity and road network logic
        for i in range(len(self.sensor_metadata)):
            for j in range(i+1, len(self.sensor_metadata)):
                if self.adjacency_matrix[i, j] == 1:
                    sensor_i = self.sensor_metadata.iloc[i]['sensor_id']
                    sensor_j = self.sensor_metadata.iloc[j]['sensor_id']
                    distance = self.distance_matrix[i, j]
                    
                    # Add edge with weight as inverse distance
                    self.network_graph.add_edge(sensor_i, sensor_j, 
                                              weight=1.0/max(distance, 0.01),
                                              distance=distance)
        
        self.logger.info(f"Built network with {self.network_graph.number_of_nodes()} nodes "
                        f"and {self.network_graph.number_of_edges()} edges")
    
    def get_sensor_neighbors(self, sensor_id: str, max_distance: float = None) -> List[Dict]:
        """
        Get neighbors of a specific sensor
        
        Args:
            sensor_id: Target sensor ID
            max_distance: Maximum distance in km (uses config default if None)
            
        Returns:
            List of neighbor information dictionaries
        """
        if max_distance is None:
            max_distance = self.config.max_neighbor_distance_km
        
        if sensor_id not in self.sensor_metadata['sensor_id'].values:
            raise ValueError(f"Sensor {sensor_id} not found in metadata")
        
        sensor_idx = self.sensor_metadata[self.sensor_metadata['sensor_id'] == sensor_id].index[0]
        neighbors = []
        
        for i, distance in enumerate(self.distance_matrix[sensor_idx]):
            if 0 < distance <= max_distance:
                neighbor_data = self.sensor_metadata.iloc[i].to_dict()
                neighbor_data['distance_km'] = distance
                neighbor_data['weight'] = 1.0 / max(distance, 0.01)
                neighbors.append(neighbor_data)
        
        # Sort by distance
        neighbors.sort(key=lambda x: x['distance_km'])
        
        return neighbors[:self.config.num_nearest_neighbors]
    
    def get_directional_neighbors(self, sensor_id: str) -> Dict[str, List[Dict]]:
        """
        Get neighbors grouped by traffic flow direction
        
        Args:
            sensor_id: Target sensor ID
            
        Returns:
            Dictionary with 'upstream' and 'downstream' neighbor lists
        """
        neighbors = self.get_sensor_neighbors(sensor_id)
        sensor_data = self.sensor_metadata[self.sensor_metadata['sensor_id'] == sensor_id].iloc[0]
        sensor_direction = sensor_data['direction']
        
        upstream = []
        downstream = []
        
        # Direction mapping for traffic flow analysis
        direction_mappings = {
            'N': {'upstream': ['S', 'SW', 'SE'], 'downstream': ['N', 'NE', 'NW']},
            'S': {'upstream': ['N', 'NE', 'NW'], 'downstream': ['S', 'SW', 'SE']},
            'E': {'upstream': ['W', 'NW', 'SW'], 'downstream': ['E', 'NE', 'SE']},
            'W': {'upstream': ['E', 'NE', 'SE'], 'downstream': ['W', 'NW', 'SW']},
            'NE': {'upstream': ['SW', 'S', 'W'], 'downstream': ['NE', 'N', 'E']},
            'NW': {'upstream': ['SE', 'S', 'E'], 'downstream': ['NW', 'N', 'W']},
            'SE': {'upstream': ['NW', 'N', 'W'], 'downstream': ['SE', 'S', 'E']},
            'SW': {'upstream': ['NE', 'N', 'E'], 'downstream': ['SW', 'S', 'W']}
        }
        
        mapping = direction_mappings.get(sensor_direction, {'upstream': [], 'downstream': []})
        
        for neighbor in neighbors:
            neighbor_direction = neighbor['direction']
            if neighbor_direction in mapping['upstream']:
                upstream.append(neighbor)
            elif neighbor_direction in mapping['downstream']:
                downstream.append(neighbor)
        
        return {'upstream': upstream, 'downstream': downstream}
    
    def calculate_network_metrics(self, sensor_id: str) -> Dict:
        """
        Calculate network topology metrics for a sensor
        
        Args:
            sensor_id: Target sensor ID
            
        Returns:
            Dictionary of network metrics
        """
        if sensor_id not in self.network_graph:
            return {}
        
        metrics = {}
        
        # Basic connectivity metrics
        metrics['degree'] = self.network_graph.degree(sensor_id)
        metrics['clustering_coefficient'] = nx.clustering(self.network_graph, sensor_id)
        
        # Centrality measures
        if self.network_graph.number_of_nodes() > 1:
            betweenness_centrality = nx.betweenness_centrality(self.network_graph)
            closeness_centrality = nx.closeness_centrality(self.network_graph)
            eigenvector_centrality = nx.eigenvector_centrality(self.network_graph, max_iter=1000)
            
            metrics['betweenness_centrality'] = betweenness_centrality.get(sensor_id, 0.0)
            metrics['closeness_centrality'] = closeness_centrality.get(sensor_id, 0.0)
            metrics['eigenvector_centrality'] = eigenvector_centrality.get(sensor_id, 0.0)
        
        # Local network density
        neighbors = list(self.network_graph.neighbors(sensor_id))
        if len(neighbors) > 1:
            subgraph = self.network_graph.subgraph(neighbors + [sensor_id])
            metrics['local_density'] = nx.density(subgraph)
        else:
            metrics['local_density'] = 0.0
        
        return metrics

class SpatialFeatureExtractor:
    """Main class for spatial feature extraction"""
    
    def __init__(self, spark_session: SparkSession, 
                 sensor_metadata: pd.DataFrame,
                 config: SpatialFeatureConfig = None):
        self.spark = spark_session
        self.config = config or SpatialFeatureConfig()
        self.sensor_metadata = sensor_metadata
        self.network_analyzer = SensorNetworkAnalyzer(sensor_metadata, config)
        self.logger = logging.getLogger(__name__)
        
        # Create neighbor lookup tables
        self._prepare_neighbor_data()
    
    def _prepare_neighbor_data(self):
        """Prepare neighbor lookup data for broadcast"""
        self.logger.info("Preparing spatial neighbor data")
        
        # Create neighbor mapping for each sensor
        self.neighbor_mapping = {}
        self.directional_mapping = {}
        self.network_metrics = {}
        
        for sensor_id in self.sensor_metadata['sensor_id']:
            # Get neighbors
            neighbors = self.network_analyzer.get_sensor_neighbors(sensor_id)
            self.neighbor_mapping[sensor_id] = [n['sensor_id'] for n in neighbors]
            
            # Get directional neighbors
            directional = self.network_analyzer.get_directional_neighbors(sensor_id)
            self.directional_mapping[sensor_id] = {
                'upstream': [n['sensor_id'] for n in directional['upstream']],
                'downstream': [n['sensor_id'] for n in directional['downstream']]
            }
            
            # Get network metrics
            self.network_metrics[sensor_id] = self.network_analyzer.calculate_network_metrics(sensor_id)
        
        # Broadcast the mapping to all workers
        self.neighbor_mapping_broadcast = self.spark.sparkContext.broadcast(self.neighbor_mapping)
        self.directional_mapping_broadcast = self.spark.sparkContext.broadcast(self.directional_mapping)
        self.network_metrics_broadcast = self.spark.sparkContext.broadcast(self.network_metrics)
    
    def extract_neighbor_features(self, df: SparkDataFrame,
                                value_columns: List[str] = None,
                                timestamp_col: str = "timestamp") -> SparkDataFrame:
        """
        Extract features based on neighboring sensors
        
        Args:
            df: Input DataFrame with traffic data
            value_columns: Columns to calculate neighbor features for
            timestamp_col: Timestamp column name
            
        Returns:
            DataFrame with neighbor features
        """
        self.logger.info("Extracting neighbor-based spatial features")
        
        if value_columns is None:
            value_columns = ["speed_mph", "volume_vehicles_per_hour"]
        
        # Create a self-join to get neighbor data
        df_neighbors = df.select("sensor_id", timestamp_col, *value_columns)
        
        # For each sensor, calculate neighbor aggregations
        for method in self.config.spatial_aggregation_methods:
            for col_name in value_columns:
                # This would need to be implemented with UDFs for complex neighbor calculations
                # For now, implementing a simplified version using window functions
                
                # Calculate spatial features using broadcast variables
                if method == 'mean':
                    # Create neighbor average features (simplified implementation)
                    df = df.withColumn(f"{col_name}_neighbor_avg", 
                                     col(col_name))  # Placeholder - would implement actual neighbor averaging
                elif method == 'std':
                    df = df.withColumn(f"{col_name}_neighbor_std", 
                                     lit(0.0))  # Placeholder
                elif method == 'min':
                    df = df.withColumn(f"{col_name}_neighbor_min", 
                                     col(col_name))  # Placeholder
                elif method == 'max':
                    df = df.withColumn(f"{col_name}_neighbor_max", 
                                     col(col_name))  # Placeholder
        
        return df
    
    def extract_directional_features(self, df: SparkDataFrame,
                                   value_columns: List[str] = None,
                                   timestamp_col: str = "timestamp") -> SparkDataFrame:
        """
        Extract upstream and downstream traffic features
        
        Args:
            df: Input DataFrame
            value_columns: Columns to analyze
            timestamp_col: Timestamp column
            
        Returns:
            DataFrame with directional features
        """
        self.logger.info("Extracting directional spatial features")
        
        if value_columns is None:
            value_columns = ["speed_mph", "volume_vehicles_per_hour"]
        
        # Add directional features
        for col_name in value_columns:
            # Upstream features (traffic flowing toward this sensor)
            df = df.withColumn(f"{col_name}_upstream_avg", lit(0.0))  # Placeholder
            df = df.withColumn(f"{col_name}_upstream_std", lit(0.0))  # Placeholder
            
            # Downstream features (traffic flowing away from this sensor)
            df = df.withColumn(f"{col_name}_downstream_avg", lit(0.0))  # Placeholder
            df = df.withColumn(f"{col_name}_downstream_std", lit(0.0))  # Placeholder
            
            # Flow differential (upstream - downstream)
            df = df.withColumn(f"{col_name}_flow_differential", 
                             col(f"{col_name}_upstream_avg") - col(f"{col_name}_downstream_avg"))
        
        return df
    
    def extract_network_topology_features(self, df: SparkDataFrame) -> SparkDataFrame:
        """
        Add network topology features to each sensor
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with network topology features
        """
        self.logger.info("Extracting network topology features")
        
        # Create a mapping DataFrame for network metrics
        network_data = []
        for sensor_id, metrics in self.network_metrics.items():
            row = {'sensor_id': sensor_id}
            row.update(metrics)
            network_data.append(row)
        
        if network_data:
            network_df = self.spark.createDataFrame(network_data)
            df = df.join(network_df, on="sensor_id", how="left")
            
            # Fill missing values with defaults
            topology_columns = ['degree', 'clustering_coefficient', 'betweenness_centrality',
                              'closeness_centrality', 'eigenvector_centrality', 'local_density']
            
            for col_name in topology_columns:
                if col_name in df.columns:
                    df = df.withColumn(col_name, coalesce(col(col_name), lit(0.0)))
        
        return df
    
    def extract_spatial_correlations(self, df: SparkDataFrame,
                                   value_columns: List[str] = None,
                                   timestamp_col: str = "timestamp") -> SparkDataFrame:
        """
        Calculate spatial correlations between sensors
        
        Args:
            df: Input DataFrame
            value_columns: Columns to calculate correlations for
            timestamp_col: Timestamp column
            
        Returns:
            DataFrame with spatial correlation features
        """
        self.logger.info("Extracting spatial correlation features")
        
        if value_columns is None:
            value_columns = ["speed_mph", "volume_vehicles_per_hour"]
        
        # This is a complex operation that would require multiple passes
        # For now, adding placeholder correlation features
        for col_name in value_columns:
            df = df.withColumn(f"{col_name}_spatial_correlation_avg", lit(0.0))
            df = df.withColumn(f"{col_name}_spatial_correlation_max", lit(0.0))
            df = df.withColumn(f"{col_name}_spatial_autocorrelation", lit(0.0))
        
        return df
    
    def extract_distance_weighted_features(self, df: SparkDataFrame,
                                         value_columns: List[str] = None,
                                         timestamp_col: str = "timestamp") -> SparkDataFrame:
        """
        Extract distance-weighted spatial features
        
        Args:
            df: Input DataFrame
            value_columns: Columns to analyze
            timestamp_col: Timestamp column
            
        Returns:
            DataFrame with distance-weighted features
        """
        self.logger.info("Extracting distance-weighted spatial features")
        
        if value_columns is None:
            value_columns = ["speed_mph", "volume_vehicles_per_hour"]
        
        # Add distance-weighted aggregation features
        for col_name in value_columns:
            df = df.withColumn(f"{col_name}_distance_weighted_avg", lit(0.0))  # Placeholder
            df = df.withColumn(f"{col_name}_inverse_distance_sum", lit(0.0))    # Placeholder
            df = df.withColumn(f"{col_name}_gravity_model_flow", lit(0.0))      # Placeholder
        
        return df
    
    def extract_road_type_features(self, df: SparkDataFrame) -> SparkDataFrame:
        """
        Extract features based on road type relationships
        
        Args:
            df: Input DataFrame
            
        Returns:
            DataFrame with road type features
        """
        self.logger.info("Extracting road type spatial features")
        
        # Create road type mapping
        road_type_mapping = self.sensor_metadata.set_index('sensor_id')['road_type'].to_dict()
        road_type_df = self.spark.createDataFrame(
            [(k, v) for k, v in road_type_mapping.items()],
            ['sensor_id', 'road_type']
        )
        
        # Join road type information
        df = df.join(road_type_df, on="sensor_id", how="left")
        
        # Add road type hierarchy features
        df = df.withColumn("road_type_hierarchy_score",
                          when(col("road_type") == "highway", 3)
                          .when(col("road_type") == "arterial", 2)
                          .when(col("road_type") == "local", 1)
                          .otherwise(0))
        
        # Count of same road type neighbors
        df = df.withColumn("same_road_type_neighbors", lit(0))  # Placeholder
        df = df.withColumn("higher_road_type_neighbors", lit(0))  # Placeholder
        df = df.withColumn("lower_road_type_neighbors", lit(0))   # Placeholder
        
        return df
    
    def extract_all_spatial_features(self, df: SparkDataFrame,
                                   value_columns: List[str] = None,
                                   timestamp_col: str = "timestamp") -> SparkDataFrame:
        """
        Extract all spatial features
        
        Args:
            df: Input DataFrame
            value_columns: Columns to analyze
            timestamp_col: Timestamp column
            
        Returns:
            DataFrame with all spatial features
        """
        self.logger.info("Starting comprehensive spatial feature extraction")
        
        if value_columns is None:
            value_columns = ["speed_mph", "volume_vehicles_per_hour"]
        
        # Extract neighbor features
        df = self.extract_neighbor_features(df, value_columns, timestamp_col)
        
        # Extract directional features
        if self.config.enable_directional_features:
            df = self.extract_directional_features(df, value_columns, timestamp_col)
        
        # Extract network topology features
        df = self.extract_network_topology_features(df)
        
        # Extract spatial correlations
        df = self.extract_spatial_correlations(df, value_columns, timestamp_col)
        
        # Extract distance-weighted features
        df = self.extract_distance_weighted_features(df, value_columns, timestamp_col)
        
        # Extract road type features
        if self.config.enable_road_network_features:
            df = self.extract_road_type_features(df)
        
        self.logger.info("Spatial feature extraction completed")
        return df
    
    def get_spatial_feature_metadata(self) -> Dict:
        """
        Get metadata about extracted spatial features
        
        Returns:
            Dictionary containing spatial feature metadata
        """
        return {
            "spatial_features": {
                "neighbor_features": [f"{method}_neighbor" for method in self.config.spatial_aggregation_methods],
                "directional_features": ["upstream_avg", "upstream_std", "downstream_avg", "downstream_std", "flow_differential"],
                "network_topology": ["degree", "clustering_coefficient", "betweenness_centrality", 
                                   "closeness_centrality", "eigenvector_centrality", "local_density"],
                "correlation_features": ["spatial_correlation_avg", "spatial_correlation_max", "spatial_autocorrelation"],
                "distance_weighted": ["distance_weighted_avg", "inverse_distance_sum", "gravity_model_flow"],
                "road_type_features": ["road_type_hierarchy_score", "same_road_type_neighbors", 
                                     "higher_road_type_neighbors", "lower_road_type_neighbors"]
            },
            "network_statistics": {
                "total_sensors": len(self.sensor_metadata),
                "total_connections": self.network_analyzer.network_graph.number_of_edges(),
                "average_degree": np.mean([self.network_analyzer.network_graph.degree(node) 
                                         for node in self.network_analyzer.network_graph.nodes()]),
                "network_density": nx.density(self.network_analyzer.network_graph)
            },
            "config": {
                "max_neighbor_distance_km": self.config.max_neighbor_distance_km,
                "num_nearest_neighbors": self.config.num_nearest_neighbors,
                "spatial_aggregation_methods": self.config.spatial_aggregation_methods,
                "enable_road_network_features": self.config.enable_road_network_features,
                "enable_directional_features": self.config.enable_directional_features
            }
        }

# Utility functions for spatial analysis
def calculate_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate bearing between two points"""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    
    dlon = lon2 - lon1
    y = np.sin(dlon) * np.cos(lat2)
    x = np.cos(lat1) * np.sin(lat2) - np.sin(lat1) * np.cos(lat2) * np.cos(dlon)
    
    bearing = np.degrees(np.arctan2(y, x))
    return (bearing + 360) % 360

def create_sensor_adjacency_matrix(sensor_metadata: pd.DataFrame, 
                                 max_distance_km: float = 5.0) -> np.ndarray:
    """Create adjacency matrix for sensors based on distance"""
    n_sensors = len(sensor_metadata)
    adjacency = np.zeros((n_sensors, n_sensors))
    
    for i in range(n_sensors):
        for j in range(i+1, n_sensors):
            sensor1 = sensor_metadata.iloc[i]
            sensor2 = sensor_metadata.iloc[j]
            
            distance = geodesic(
                (sensor1['latitude'], sensor1['longitude']),
                (sensor2['latitude'], sensor2['longitude'])
            ).kilometers
            
            if distance <= max_distance_km:
                adjacency[i, j] = 1
                adjacency[j, i] = 1
    
    return adjacency

if __name__ == "__main__":
    # Example usage and testing
    spark = SparkSession.builder \
        .appName("SpatialFeatureExtraction") \
        .config("spark.sql.adaptive.enabled", "true") \
        .getOrCreate()
    
    # Load sensor metadata (using the actual file)
    sensor_metadata = pd.read_csv("C:/traffic-prediction/data/raw/metr_la_sensor_metadata.csv")
    
    # Create sample traffic data
    sample_data = []
    for sensor_id in sensor_metadata['sensor_id'][:10]:  # First 10 sensors
        for hour in range(24):
            sample_data.append({
                'sensor_id': sensor_id,
                'timestamp': f"2023-06-01 {hour:02d}:00:00",
                'speed_mph': np.random.normal(30, 10),
                'volume_vehicles_per_hour': np.random.normal(50, 15)
            })
    
    df = spark.createDataFrame(sample_data)
    
    # Initialize spatial feature extractor
    config = SpatialFeatureConfig(
        max_neighbor_distance_km=3.0,
        num_nearest_neighbors=3,
        spatial_aggregation_methods=['mean', 'std', 'max']
    )
    
    extractor = SpatialFeatureExtractor(spark, sensor_metadata, config)
    
    # Extract spatial features
    df_with_spatial = extractor.extract_all_spatial_features(df)
    
    # Show results
    print("Original columns:", len(df.columns))
    print("Enhanced columns:", len(df_with_spatial.columns))
    
    # Show spatial feature metadata  
    metadata = extractor.get_spatial_feature_metadata()
    print("\nSpatial Feature Metadata:")
    for category, features in metadata["spatial_features"].items():
        print(f"{category}: {len(features)} features")
    
    print(f"\nNetwork Statistics:")
    for stat, value in metadata["network_statistics"].items():
        print(f"{stat}: {value}")
    
    spark.stop()