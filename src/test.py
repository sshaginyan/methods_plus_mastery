import os
import sys
import pytest
import sqlite3
import pandas as pd
from unittest.mock import Mock
from pandas.io.sql import SQLiteTable

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from main import upsert
from timezone_cluster_analyzer import TimezoneClusterAnalyzer

@pytest.fixture
def mock_connection():
    """Fixture for mocking SQLite connection"""
    conn = Mock(spec=sqlite3.Connection)
    conn.execute = Mock()
    conn.executemany = Mock()
    conn.connection = Mock()
    conn.connection.commit = Mock()
    return conn

@pytest.fixture
def sample_data():
    """Fixture for sample data"""
    return [
        {'region': 'US East', 'post_count': 100, 'centroid_hours_utc': '[1, 2, 3]'},
        {'region': 'US West', 'post_count': 200, 'centroid_hours_utc': '[4, 5, 6]'}
    ]

@pytest.fixture
def sample_df():
    """Fixture for sample DataFrame"""
    # Create a sample dataset with timezone information
    data = {
        'created_at': pd.date_range('2024-02-07', periods=48, freq='h'),
        'timezone': ['America/New_York'] * 24 + ['America/Los_Angeles'] * 24
    }
    return pd.DataFrame(data)

def test_upsert_successful(mock_connection, sample_data):
    """Test successful upsert operation"""
    mock_table = Mock(spec=SQLiteTable)
    mock_table.name = 'test_table'
    data_iter = [tuple(x.values()) for x in sample_data]
    upsert(mock_table, mock_connection, ['region', 'post_count', 'centroid_hours_utc'], data_iter)
    mock_connection.executemany.assert_called_once()
    mock_connection.connection.commit.assert_called_once()

def test_upsert_handles_error(mock_connection, sample_data):
    """Test upsert error handling"""
    mock_table = Mock(spec=SQLiteTable)
    mock_table.name = 'test_table'
    mock_connection.executemany.side_effect = Exception("Database error")
    data_iter = [tuple(x.values()) for x in sample_data]
    upsert(mock_table, mock_connection, ['region', 'post_count', 'centroid_hours_utc'], data_iter)
    mock_connection.connection.commit.assert_not_called()

def test_database_integration():
    """Integration test with actual SQLite database"""
    conn = sqlite3.connect(':memory:')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS regional_activity_clusters (
            region TEXT PRIMARY KEY,
            post_count INTEGER,
            centroid_hours_utc TEXT
        )
    ''')
    
    test_data = pd.DataFrame({
        'region': ['Test Region'],
        'post_count': [100],
        'centroid_hours_utc': ['[1, 2, 3]']
    })
    
    test_data.to_sql(
        'regional_activity_clusters',
        conn,
        if_exists='append',
        index=False,
        method=upsert
    )
    
    result = pd.read_sql('SELECT * FROM regional_activity_clusters', conn)
    assert len(result) == 1
    assert result.iloc[0]['region'] == 'Test Region'
    assert result.iloc[0]['post_count'] == 100
    conn.close()

def test_timezone_cluster_analyzer(sample_df):
    """Test TimezoneClusterAnalyzer functionality"""
    analyzer = TimezoneClusterAnalyzer()
    
    # Test the analyze method
    results = analyzer.analyze(sample_df)
    
    # Basic validation
    assert isinstance(results, pd.DataFrame)
    assert len(results) == len(sample_df)
    assert 'timezone' in results.columns
    assert 'created_at' in results.columns
    
    # Check if we have data for each timezone
    unique_timezones = sample_df['timezone'].unique()
    for timezone in unique_timezones:
        timezone_data = results[results['timezone'] == timezone]
        assert len(timezone_data) > 0
        
    # Verify that the results contain necessary analysis columns
    assert any(col.startswith('cluster') for col in results.columns)

if __name__ == '__main__':
    pytest.main([__file__])