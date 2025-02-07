import numpy as np
import pandas as pd
from loguru import logger
from sklearn.cluster import KMeans
from typing import Dict, List, Tuple, Any
from sklearn.preprocessing import StandardScaler

class TimezoneClusterAnalyzer:
    """
    Analyzes temporal patterns in UTC timestamps to identify likely geographical regions
    based on activity hours using K-means clustering.
    """
    def __init__(self, n_clusters: int = 24) -> None:  # 24 clusters for 24 hour cycle
        """
        Initialize the analyzer with specified number of clusters.

        Args:
            n_clusters (int, optional): Number of time-based clusters. Defaults to 24 for hourly analysis.
        """
        self.kmeans: KMeans = KMeans(n_clusters=n_clusters, random_state=42)
        self.scaler: StandardScaler = StandardScaler()
        logger.info("Initialized TimezoneClusterAnalyzer with {} clusters.", n_clusters)

        
    def _extract_features(self, df: pd.DataFrame) -> np.ndarray:
        """
        Extract cyclical time features from UTC timestamps.

        Args:
            df (pd.DataFrame): DataFrame containing 'created_at' column in UTC format

        Returns:
            np.ndarray: Scaled feature matrix of sine and cosine components
        """
        # Convert timestamps to datetime if they aren't already
        df['datetime'] = pd.to_datetime(df['created_at'], format="ISO8601", utc=True)
        logger.info("Converted 'created_at' to datetime.")

        
        # Extract hour and convert to cyclical features to handle day wraparound
        hours: pd.Series = df['datetime'].dt.hour
        
        # Convert hours to cyclical features using sine and cosine
        # This handles the wraparound at midnight (hour 0 and hour 23 are close)
        hour_sin: np.ndarray = np.sin(2 * np.pi * hours/24)
        hour_cos: np.ndarray = np.cos(2 * np.pi * hours/24)
        
        # Stack features
        features: np.ndarray = np.column_stack([hour_sin, hour_cos])
        logger.info("Extracted and transformed cyclical time features.")
        
        # Scale features
        logger.info("Features scaled.")
        return self.scaler.fit_transform(features)
    
    def analyze(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Analyze timestamps to identify likely geographical regions based on activity patterns.

        Args:
            df (pd.DataFrame): DataFrame with 'created_at' column in UTC format

        Returns:
            pd.DataFrame: Original DataFrame with added columns:
                - cluster: Cluster assignment
                - cluster_hour: Center hour of the cluster in UTC
                - likely_region: Most probable geographical region
                - confidence: Confidence score of the region prediction
                - alternative_regions: List of next most likely regions
        """
        df = df.copy()
        logger.info("Starting analysis on dataframe with {} records.", len(df))

        
        # Extract features and perform clustering
        features: np.ndarray = self._extract_features(df)
        cluster_labels: np.ndarray = self.kmeans.fit_predict(features)
        logger.info("Clustering complete. {} clusters formed.", len(set(cluster_labels)))

        
        # Get cluster centers and convert back to hours
        centers: np.ndarray = self.kmeans.cluster_centers_
        cluster_hours: np.ndarray = np.arctan2(centers[:, 0], centers[:, 1])
        cluster_hours = (24 / (2 * np.pi) * cluster_hours) % 24
        logger.info("Cluster centers converted back to hours.")

        
        # Map clusters to likely regions based on center hours
        def interpret_cluster(cluster_idx: int) -> Tuple[str, float, List[str]]:
            """
            Maps a cluster's center hour to the most likely geographical region based on typical working hours.

            Args:
                cluster_idx (int): Index of the cluster to interpret

            Returns:
                Tuple[str, float, List[str]]: A tuple containing:
                    - main_region (str): Most likely geographical region for this cluster
                    - confidence (float): Confidence score (0.2-1.0) for the region prediction
                    - alt_regions (List[str]): List of two alternative regions with next closest activity hours
            """
            center_hour = cluster_hours[cluster_idx]
            
            # Map UTC hours to likely regions
            regions: Dict[str, Dict[str, Any]] = {
                # North America
                'US Pacific': {'offset': -8, 'active_hours': (1, 9)},      # 9AM-5PM PT = 17-01 UTC
                'US Mountain': {'offset': -7, 'active_hours': (2, 10)},    # 9AM-5PM MT = 16-00 UTC
                'US Central': {'offset': -6, 'active_hours': (3, 11)},     # 9AM-5PM CT = 15-23 UTC
                'US Eastern': {'offset': -5, 'active_hours': (4, 12)},     # 9AM-5PM ET = 14-22 UTC
                'Canada Atlantic': {'offset': -4, 'active_hours': (5, 13)}, # 9AM-5PM AT = 13-21 UTC
                
                # South America
                'Brazil East': {'offset': -3, 'active_hours': (6, 14)},    # 9AM-5PM BRT
                'Argentina': {'offset': -3, 'active_hours': (6, 14)},      # 9AM-5PM ART
                'Chile': {'offset': -4, 'active_hours': (5, 13)},          # 9AM-5PM CLT
                
                # Europe
                'UK': {'offset': 0, 'active_hours': (9, 17)},              # 9AM-5PM GMT/UTC
                'Ireland': {'offset': 0, 'active_hours': (9, 17)},         # 9AM-5PM IST
                'Central Europe': {'offset': 1, 'active_hours': (8, 16)},  # 9AM-5PM CET (Germany, France, Italy, etc.)
                'Eastern Europe': {'offset': 2, 'active_hours': (7, 15)},  # 9AM-5PM EET (Finland, Greece, etc.)
                'Moscow': {'offset': 3, 'active_hours': (6, 14)},          # 9AM-5PM MSK
                
                # Asia
                'Turkey': {'offset': 3, 'active_hours': (6, 14)},          # 9AM-5PM TRT
                'UAE': {'offset': 4, 'active_hours': (5, 13)},             # 9AM-5PM GST
                'Pakistan': {'offset': 5, 'active_hours': (4, 12)},        # 9AM-5PM PKT
                'India': {'offset': 5.5, 'active_hours': (3.5, 11.5)},     # 9AM-5PM IST
                'Bangladesh': {'offset': 6, 'active_hours': (3, 11)},      # 9AM-5PM BST
                'Thailand': {'offset': 7, 'active_hours': (2, 10)},        # 9AM-5PM ICT
                'Singapore': {'offset': 8, 'active_hours': (1, 9)},        # 9AM-5PM SGT
                'China': {'offset': 8, 'active_hours': (1, 9)},            # 9AM-5PM CST
                'Taiwan': {'offset': 8, 'active_hours': (1, 9)},           # 9AM-5PM CST
                'Japan': {'offset': 9, 'active_hours': (0, 8)},            # 9AM-5PM JST
                'Korea': {'offset': 9, 'active_hours': (0, 8)},            # 9AM-5PM KST
                
                # Oceania
                'Australia Western': {'offset': 8, 'active_hours': (1, 9)},      # 9AM-5PM AWST
                'Australia Central': {'offset': 9.5, 'active_hours': (23.5, 7.5)}, # 9AM-5PM ACST
                'Australia Eastern': {'offset': 10, 'active_hours': (23, 7)},    # 9AM-5PM AEST
                'New Zealand': {'offset': 12, 'active_hours': (21, 5)},          # 9AM-5PM NZST
            }
            
            # Find closest matching region based on cluster center hour
            region_scores: List[Tuple[str, float]] = []
            for region, info in regions.items():
                start_hour, end_hour = info['active_hours']
                # Check if cluster center falls within region's active hours
                if start_hour <= center_hour <= end_hour:
                    distance = 0  # Perfect match

                else:
                    # Calculate minimum distance to active hours
                    dist_to_start = min((center_hour - start_hour) % 24, (start_hour - center_hour) % 24)
                    dist_to_end = min((center_hour - end_hour) % 24, (end_hour - center_hour) % 24)
                    distance = min(dist_to_start, dist_to_end)

                region_scores.append((region, distance))
            
            # Sort by distance (closest first)
            region_scores.sort(key=lambda x: x[1])
            main_region: str = region_scores[0][0]
            alt_regions: List[str] = [r[0] for r in region_scores[1:3]]  # Next 2 closest regions
            
            # Calculate confidence based on distance
            confidence: float = max(0.2, 1 - (region_scores[0][1] / 12))  # Normalize by half day
            
            return main_region, confidence, alt_regions
        
        # Add cluster interpretations to DataFrame
        df['cluster'] = cluster_labels
        df['cluster_hour'] = df['cluster'].map(lambda x: cluster_hours[x])
        
        # Add region predictions
        interpretations: List[Tuple[str, float, List[str]]] = [interpret_cluster(c) for c in df['cluster']]
        df['likely_region'] = [i[0] for i in interpretations]
        df['confidence'] = [i[1] for i in interpretations]
        df['alternative_regions'] = [i[2] for i in interpretations]
        
        return df