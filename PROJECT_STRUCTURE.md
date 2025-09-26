# Traffic Analytics Project Structure

This directory contains the source code and configuration files for the Traffic Analytics system.

## Directory Structure

```
C:\traffic-prediction\
├── data/
│   ├── raw/                 # Original METR-LA traffic dataset
│   └── processed/           # Cleaned and processed datasets
├── src/
│   ├── kafka/              # Kafka producer and consumer services
│   ├── spark/              # Spark streaming and batch processing jobs
│   ├── ml/                 # Machine learning models and training scripts
│   ├── api/                # FastAPI backend services
│   └── frontend/           # React.js dashboard components
├── scripts/                # Setup and management scripts
├── logs/                   # Application and system logs
├── traffic_env/            # Python virtual environment (3.11 target)
└── config/                 # Configuration files
```

## Environment Setup

Run the environment setup script to configure all necessary variables:
```powershell
.\scripts\setup-environment.ps1
```

## Development Guidelines

1. Always activate the Python virtual environment before development
2. Use Java 8 for Hadoop/Spark compatibility
3. Follow the data flow: Kafka → Spark → HDFS → ML → API → Frontend