"""
Connectivity Tests Package

This package contains comprehensive connectivity tests validating
all component connections in the traffic prediction system.

Test Categories:
1. Kafka ↔ Spark Connectivity
2. Spark ↔ Hadoop/HDFS Integration  
3. Hadoop ↔ Postgres Data Sync
4. Backend ↔ Kafka (Producer/Consumer)
5. Backend ↔ Postgres (Read/Write)
6. Backend ↔ Frontend (API/WebSocket)
7. Frontend ↔ User (Real-time Updates)
8. ML Pipeline: Kafka → Spark MLlib
9. Spark → Model Export
10. Model → Predictions
11. HDFS Storage Pipeline
12. Stream ↔ Batch Processing Coordination
"""

__version__ = "1.0.0"
