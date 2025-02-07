import json
import sqlite3
import pandas as pd
from loguru import logger
from pandas.io.sql import SQLiteTable
from sqlite3 import Connection, Cursor
from typing import List, Dict, Any, Tuple, Union
from datasets import load_dataset, Dataset, DatasetDict

from timezone_cluster_analyzer import TimezoneClusterAnalyzer

logger.add(
    "output/file.log",  # Save logs to a file named 'file.log'
    format="{time:YYYY-MM-DD at HH:mm:ss} - {level} - {message} ({file}:{line})",  # Custom log format
    level="INFO"
)

def upsert(
    table: SQLiteTable,
    conn: Union[Connection, Cursor],
    keys: List[str],
    data_iter: Any
) -> None:
    """
    Performs an upsert (insert or update) operation on a SQLite database table.
    
    This function handles the insertion of new records and updates existing ones
    based on a conflict with the primary key (region). If a record with the same
    region exists, it updates the centroid_hours_utc and post_count values.
    
    Args:
        table (SQLiteTable): The pandas SQLite table object containing table information
        conn (Union[Connection, Cursor]): SQLite database connection or cursor object
        keys (List[str]): List of column names in the table
        data_iter (Any): Iterator containing the data to be inserted/updated
        
    Returns:
        None
        
    Raises:
        Exception: Any database-related errors during the upsert operation
    """
    data: List[Dict[str, Any]] = [dict(zip(keys, row)) for row in data_iter]
    
    # Use table.name instead of table object
    table_name: str = table.name if hasattr(table, 'name') else str(table)
    
    query: str = f"""
    INSERT INTO {table_name} (region, post_count, centroid_hours_utc) 
    VALUES (?, ?, ?)
    ON CONFLICT(region) DO UPDATE SET
        centroid_hours_utc = excluded.centroid_hours_utc,
        post_count = excluded.post_count
    """
    
    try:
        conn.executemany(query, [tuple(x.values()) for x in data])
        conn.connection.commit()
        logger.info(f"Data upserted successfully into {table_name}.")
    except Exception as e:
        logger.error(f"Error while upserting data: {e}")


if __name__ == "__main__":
    logger.info("Starting the dataset loading process.")
    ds: DatasetDict = load_dataset("alpindale/two-million-bluesky-posts")
    df: pd.DataFrame = ds['train'].to_pandas()
    logger.info("Dataset loaded successfully and converted to pandas DataFrame.")
    
    logger.info("Starting analysis using TimezoneClusterAnalyzer.")
    analyzer: TimezoneClusterAnalyzer = TimezoneClusterAnalyzer()
    results: pd.DataFrame = analyzer.analyze(df)
    logger.info("Analysis completed.")

    cluster_stats: pd.DataFrame = (
        results.groupby('cluster')
        .agg({
            'cluster_hour': 'first',
            'likely_region': 'first',
            'created_at': 'count'
        })
        .rename(columns={
            'created_at': 'post_count',
            'likely_region': 'region'
        })
    )
    
    # Then summarize by region with hours as JSON list
    logger.info("Summarizing results by region.")
    insights: pd.DataFrame = (
        cluster_stats.groupby('region')
        .agg({
            'post_count': 'sum',
            'cluster_hour': lambda x: json.dumps(list(x))
        })
        .rename(columns={
            'cluster_hour': 'centroid_hours_utc'
        })
        .sort_values('post_count', ascending=False)
    )

    conn: sqlite3.Connection = sqlite3.connect('output/methods_plus_mastery.db')
    logger.info("Database connection established.")
    
    insights.to_sql(
        name='regional_activity_clusters', # table name
        con=conn,                          # database connection
        if_exists='append',                # if table exists append data
        index=True,                        # include index as a column
        dtype={                            # specify column types
            'region': 'TEXT PRIMARY KEY',
            'centroid_hours_utc': 'TEXT',
            'post_count': 'INTEGER'
            
        },
        method=upsert
    )
    
    logger.info("Data processing and upserting completed. Check 'file.log' for more details.")