# Hadoop Ecosystem Setup for Traffic Prediction System

This document provides instructions for setting up the Hadoop ecosystem in pseudo-distributed mode for local development of the Traffic Prediction System.

## Components

The setup includes the following components:

- **HDFS** (Hadoop Distributed File System) - For storing large datasets
- **YARN** (Yet Another Resource Negotiator) - For resource management
- **HBase** - For real-time lookups and NoSQL storage
- **Hive** - For SQL analytics on Hadoop data
- **ZooKeeper** - For distributed coordination

## Prerequisites

- Docker Desktop installed and running
- Docker Compose installed
- At least 8GB of RAM allocated to Docker
- At least 20GB of free disk space

## Setup Instructions

1. **Clone the Repository**

   If you haven't already, clone the Traffic Prediction System repository.

2. **Start the Hadoop Ecosystem**

   Run the PowerShell script to start all services:

   ```powershell
   ./start-hadoop.ps1
   ```

   This script will:
   - Start all the necessary Docker containers
   - Wait for services to be ready
   - Verify that all services are running

3. **Verify the Setup**

   Run the verification script to ensure everything is working properly:

   ```powershell
   ./verify-hadoop.ps1
   ```

   This script will test HDFS, YARN, HBase, and Hive functionality.

4. **Stop the Hadoop Ecosystem**

   When you're done, you can stop all services with:

   ```powershell
   ./stop-hadoop.ps1
   ```

## Web Interfaces

Once the services are running, you can access the following web interfaces:

- HDFS NameNode: http://localhost:9870
- YARN ResourceManager: http://localhost:8088
- HBase Master: http://localhost:16010
- Hive Web Interface: http://localhost:10002

## Troubleshooting

### Common Issues

1. **Not enough memory**

   If containers are crashing, you may need to allocate more memory to Docker. Go to Docker Desktop settings and increase the memory allocation.

2. **Port conflicts**

   If you have other services using the same ports, you'll need to modify the `docker-compose.yml` file to use different ports.

3. **Slow startup**

   The Hadoop ecosystem can take a few minutes to start up completely. Be patient and check the logs if services aren't coming up.

### Checking Logs

To view logs for a specific service:

```powershell
docker-compose logs [service-name]
```

For example, to check HDFS NameNode logs:

```powershell
docker-compose logs namenode
```

## Data Persistence

The setup uses Docker volumes to persist data. This means your data will be preserved even if you stop and restart the containers. The following volumes are used:

- `hadoop_namenode` - HDFS NameNode data
- `hadoop_datanode` - HDFS DataNode data
- `hadoop_historyserver` - YARN history data
- `hive_metastore_postgresql` - Hive metastore data
- `zookeeper_data` - ZooKeeper data
- `zookeeper_datalog` - ZooKeeper logs

## Next Steps

After setting up the Hadoop ecosystem, you can proceed with:

1. Configuring Kafka for data streaming
2. Implementing data models
3. Creating stream processing pipelines
4. Developing batch processing jobs

## References

- [Hadoop Documentation](https://hadoop.apache.org/docs/)
- [HBase Documentation](https://hbase.apache.org/book.html)
- [Hive Documentation](https://cwiki.apache.org/confluence/display/Hive/GettingStarted)
- [Docker Compose Documentation](https://docs.docker.com/compose/)