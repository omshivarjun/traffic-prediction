# Configuration Reference - Traffic Prediction Service

This document provides comprehensive reference information for configuring the Traffic Prediction Service. All configuration options, their purposes, valid values, and examples are documented here.

## 📋 Table of Contents

- [Configuration File Structure](#configuration-file-structure)
- [Database Configuration](#database-configuration)
- [Prediction Configuration](#prediction-configuration) 
- [Spark Configuration](#spark-configuration)
- [Monitoring Configuration](#monitoring-configuration)
- [HDFS Configuration](#hdfs-configuration)
- [Logging Configuration](#logging-configuration)
- [Security Configuration](#security-configuration)
- [Environment Variables](#environment-variables)
- [Configuration Validation](#configuration-validation)
- [Examples](#examples)

## 🏗️ Configuration File Structure

The main configuration file is `src/prediction/prediction_service_config.json` and follows this structure:

```json
{
  "database": { ... },
  "prediction": { ... },
  "spark": { ... },
  "monitoring": { ... },
  "hdfs": { ... },
  "logging": { ... },
  "security": { ... }
}
```

### Configuration Loading

The configuration is loaded using the `PredictionServiceConfig` class:

```python
from src.prediction.prediction_service import PredictionServiceConfig

# Load from file
config = PredictionServiceConfig.from_file('path/to/config.json')

# Load from environment
config = PredictionServiceConfig.from_environment()

# Load with overrides
config = PredictionServiceConfig.from_file('config.json', overrides={
    'database.host': 'production-db.example.com'
})
```

## 🗄️ Database Configuration

Controls PostgreSQL database connectivity and connection management.

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `host` | string | Database server hostname | `"localhost"` |
| `port` | integer | Database port number | `5432` |
| `database` | string | Database name | `"traffic_prediction"` |
| `user` | string | Database username | `"prediction_service"` |
| `password` | string | Database password | `"secure_password"` |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `pool_size` | integer | `10` | Connection pool size |
| `max_overflow` | integer | `20` | Maximum overflow connections |
| `pool_timeout` | integer | `30` | Connection timeout (seconds) |
| `pool_recycle` | integer | `3600` | Connection recycle time (seconds) |
| `connect_timeout` | integer | `10` | Initial connection timeout |
| `command_timeout` | integer | `60` | SQL command timeout |
| `ssl_mode` | string | `"prefer"` | SSL connection mode |
| `ssl_cert` | string | `null` | SSL certificate path |
| `ssl_key` | string | `null` | SSL private key path |
| `ssl_ca` | string | `null` | SSL CA certificate path |

### SSL Modes

| Mode | Description |
|------|-------------|
| `disable` | No SSL connection |
| `allow` | SSL if available |
| `prefer` | Prefer SSL (default) |
| `require` | Require SSL |
| `verify-ca` | Require SSL + verify CA |
| `verify-full` | Require SSL + full verification |

### Example Database Configuration

```json
{
  "database": {
    "host": "localhost",
    "port": 5432,
    "database": "traffic_prediction",
    "user": "prediction_service",
    "password": "${DB_PASSWORD}",
    "pool_size": 15,
    "max_overflow": 25,
    "pool_timeout": 30,
    "pool_recycle": 3600,
    "connect_timeout": 10,
    "command_timeout": 120,
    "ssl_mode": "require",
    "ssl_cert": "/path/to/client.crt",
    "ssl_key": "/path/to/client.key",
    "ssl_ca": "/path/to/ca.crt"
  }
}
```

## 🔮 Prediction Configuration

Controls prediction generation behavior and feature processing.

### Core Prediction Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `batch_size` | integer | `5000` | Records processed per batch |
| `prediction_horizons` | array | `[15, 30, 60]` | Prediction horizons (minutes) |
| `feature_window_hours` | integer | `24` | Historical data window |
| `model_cache_size` | integer | `10` | Number of models to cache |
| `max_concurrent_predictions` | integer | `50` | Maximum concurrent prediction requests |
| `prediction_timeout` | integer | `300` | Prediction timeout (seconds) |

### Feature Engineering Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `lag_features` | array | `[1, 6, 12, 24]` | Lag periods (hours) |
| `rolling_windows` | array | `[15, 30, 60]` | Rolling window sizes (minutes) |
| `seasonal_features` | boolean | `true` | Include seasonal features |
| `weather_features` | boolean | `false` | Include weather data |
| `holiday_features` | boolean | `true` | Include holiday indicators |
| `traffic_incident_features` | boolean | `true` | Include incident data |

### Quality Control Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_data_points` | integer | `100` | Minimum data points for prediction |
| `max_missing_ratio` | float | `0.2` | Maximum ratio of missing data |
| `outlier_detection` | boolean | `true` | Enable outlier detection |
| `outlier_threshold` | float | `3.0` | Z-score threshold for outliers |
| `confidence_threshold` | float | `0.5` | Minimum confidence score |

### Example Prediction Configuration

```json
{
  "prediction": {
    "batch_size": 10000,
    "prediction_horizons": [15, 30, 60, 120],
    "feature_window_hours": 48,
    "model_cache_size": 20,
    "max_concurrent_predictions": 100,
    "prediction_timeout": 600,
    "lag_features": [1, 3, 6, 12, 24, 48],
    "rolling_windows": [5, 15, 30, 60, 120],
    "seasonal_features": true,
    "weather_features": true,
    "holiday_features": true,
    "traffic_incident_features": true,
    "min_data_points": 200,
    "max_missing_ratio": 0.15,
    "outlier_detection": true,
    "outlier_threshold": 2.5,
    "confidence_threshold": 0.6
  }
}
```

## ⚡ Spark Configuration

Controls Apache Spark cluster connectivity and job execution.

### Application Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `app_name` | string | `"traffic_prediction_service"` | Spark application name |
| `master` | string | `"yarn"` | Spark master URL |
| `deploy_mode` | string | `"client"` | Deployment mode (client/cluster) |
| `driver_memory` | string | `"2g"` | Driver memory allocation |
| `driver_cores` | integer | `2` | Driver CPU cores |

### Executor Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `executor_memory` | string | `"4g"` | Memory per executor |
| `executor_cores` | integer | `4` | CPU cores per executor |
| `num_executors` | integer | `4` | Number of executors |
| `executor_instances` | string | `"dynamic"` | Dynamic/fixed executors |
| `dynamic_allocation` | boolean | `true` | Enable dynamic allocation |
| `min_executors` | integer | `2` | Minimum executors |
| `max_executors` | integer | `20` | Maximum executors |

### Performance Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sql_shuffle_partitions` | integer | `200` | Shuffle partitions |
| `serializer` | string | `"org.apache.spark.serializer.KryoSerializer"` | Serialization |
| `checkpoint_dir` | string | `"/tmp/spark_checkpoints"` | Checkpoint directory |
| `speculation` | boolean | `true` | Enable speculation |
| `speculation_multiplier` | float | `1.5` | Speculation multiplier |
| `max_result_size` | string | `"2g"` | Maximum result size |

### Example Spark Configuration

```json
{
  "spark": {
    "app_name": "traffic_prediction_prod",
    "master": "yarn",
    "deploy_mode": "cluster",
    "driver_memory": "4g",
    "driver_cores": 4,
    "executor_memory": "8g",
    "executor_cores": 6,
    "num_executors": 10,
    "executor_instances": "dynamic",
    "dynamic_allocation": true,
    "min_executors": 5,
    "max_executors": 50,
    "sql_shuffle_partitions": 400,
    "serializer": "org.apache.spark.serializer.KryoSerializer",
    "checkpoint_dir": "hdfs://namenode:9000/spark/checkpoints",
    "speculation": true,
    "speculation_multiplier": 1.5,
    "max_result_size": "4g",
    "additional_jars": [
      "/path/to/postgresql-jdbc.jar",
      "/path/to/hadoop-aws.jar"
    ],
    "additional_conf": {
      "spark.sql.adaptive.enabled": "true",
      "spark.sql.adaptive.coalescePartitions.enabled": "true",
      "spark.sql.adaptive.skewJoin.enabled": "true"
    }
  }
}
```

## 📊 Monitoring Configuration

Controls system monitoring, metrics collection, and alerting.

### Metrics Collection

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | `true` | Enable monitoring |
| `collection_interval` | integer | `60` | Metrics collection interval (seconds) |
| `retention_days` | integer | `30` | Metrics retention period |
| `batch_size` | integer | `1000` | Metrics batch size |

### Accuracy Monitoring

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `accuracy_threshold` | float | `0.8` | Minimum acceptable accuracy |
| `accuracy_window_hours` | integer | `24` | Accuracy calculation window |
| `mae_threshold` | float | `5.0` | Maximum MAE threshold |
| `rmse_threshold` | float | `8.0` | Maximum RMSE threshold |
| `mape_threshold` | float | `0.2` | Maximum MAPE threshold |

### Performance Monitoring

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `response_time_threshold` | float | `1.0` | Max response time (seconds) |
| `throughput_threshold` | integer | `1000` | Min predictions/second |
| `error_rate_threshold` | float | `0.01` | Max error rate (1%) |
| `cpu_threshold` | float | `0.8` | Max CPU usage (80%) |
| `memory_threshold` | float | `0.85` | Max memory usage (85%) |
| `disk_threshold` | float | `0.9` | Max disk usage (90%) |

### Alerting Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `alert_email` | string | `null` | Alert email address |
| `alert_channels` | array | `["email"]` | Alert channels |
| `alert_cooldown` | integer | `300` | Cooldown between alerts (seconds) |
| `critical_alert_immediate` | boolean | `true` | Send critical alerts immediately |

### Example Monitoring Configuration

```json
{
  "monitoring": {
    "enabled": true,
    "collection_interval": 30,
    "retention_days": 90,
    "batch_size": 2000,
    "accuracy_threshold": 0.85,
    "accuracy_window_hours": 12,
    "mae_threshold": 3.0,
    "rmse_threshold": 5.0,
    "mape_threshold": 0.15,
    "response_time_threshold": 0.5,
    "throughput_threshold": 2000,
    "error_rate_threshold": 0.005,
    "cpu_threshold": 0.75,
    "memory_threshold": 0.8,
    "disk_threshold": 0.85,
    "alert_email": "ops-team@company.com",
    "alert_channels": ["email", "slack", "pagerduty"],
    "alert_cooldown": 180,
    "critical_alert_immediate": true,
    "slack_webhook": "https://hooks.slack.com/services/...",
    "pagerduty_api_key": "${PAGERDUTY_API_KEY}"
  }
}
```

## 🗃️ HDFS Configuration

Controls Hadoop HDFS connectivity and storage settings.

### Connection Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `namenode_url` | string | Required | NameNode URL |
| `namenode_port` | integer | `9000` | NameNode port |
| `user` | string | `"hadoop"` | HDFS user |
| `replication_factor` | integer | `3` | File replication factor |

### Storage Paths

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model_base_path` | string | `"/ml/models/traffic_prediction"` | Model storage path |
| `data_base_path` | string | `"/data/traffic"` | Data storage path |
| `checkpoint_path` | string | `"/checkpoints/prediction"` | Checkpoint path |
| `temp_path` | string | `"/tmp/prediction"` | Temporary files path |

### Performance Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `block_size` | integer | `134217728` | HDFS block size (128MB) |
| `buffer_size` | integer | `4096` | Buffer size |
| `compression` | string | `"snappy"` | Compression codec |
| `client_cache_size` | integer | `10` | Client cache size |

### Example HDFS Configuration

```json
{
  "hdfs": {
    "namenode_url": "hdfs://namenode1.example.com:9000",
    "namenode_port": 9000,
    "user": "prediction_service",
    "replication_factor": 3,
    "model_base_path": "/ml/models/traffic_prediction",
    "data_base_path": "/data/traffic/processed",
    "checkpoint_path": "/checkpoints/prediction_service",
    "temp_path": "/tmp/prediction_service",
    "block_size": 268435456,
    "buffer_size": 8192,
    "compression": "gzip",
    "client_cache_size": 20,
    "ha_enabled": true,
    "ha_namenodes": [
      "namenode1.example.com:9000",
      "namenode2.example.com:9000"
    ]
  }
}
```

## 📝 Logging Configuration

Controls application logging behavior and output.

### General Logging Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `level` | string | `"INFO"` | Log level |
| `format` | string | `"detailed"` | Log format |
| `enable_console` | boolean | `true` | Enable console output |
| `enable_file` | boolean | `true` | Enable file output |

### Log Levels

| Level | Description |
|-------|-------------|
| `DEBUG` | Detailed debugging information |
| `INFO` | General information messages |
| `WARNING` | Warning messages |
| `ERROR` | Error messages |
| `CRITICAL` | Critical error messages |

### File Logging Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `file_path` | string | `"logs/prediction_service.log"` | Log file path |
| `max_file_size` | string | `"100MB"` | Maximum file size |
| `backup_count` | integer | `10` | Number of backup files |
| `rotation_when` | string | `"midnight"` | Rotation schedule |

### Component-Specific Logging

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `database_level` | string | `"WARNING"` | Database logging level |
| `spark_level` | string | `"WARNING"` | Spark logging level |
| `prediction_level` | string | `"INFO"` | Prediction logging level |
| `monitoring_level` | string | `"INFO"` | Monitoring logging level |

### Example Logging Configuration

```json
{
  "logging": {
    "level": "INFO",
    "format": "detailed",
    "enable_console": true,
    "enable_file": true,
    "file_path": "/var/log/prediction_service/service.log",
    "max_file_size": "500MB",
    "backup_count": 30,
    "rotation_when": "midnight",
    "database_level": "ERROR",
    "spark_level": "WARNING",
    "prediction_level": "DEBUG",
    "monitoring_level": "INFO",
    "structured_logging": true,
    "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "date_format": "%Y-%m-%d %H:%M:%S",
    "additional_loggers": {
      "pyspark": "WARNING",
      "py4j": "ERROR",
      "urllib3": "WARNING"
    }
  }
}
```

## 🔒 Security Configuration

Controls security settings and authentication.

### Authentication Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | `false` | Enable security |
| `auth_method` | string | `"token"` | Authentication method |
| `token_expiry` | integer | `3600` | Token expiry (seconds) |
| `secret_key` | string | Required | Secret key for tokens |

### Authorization Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `require_auth` | boolean | `false` | Require authentication |
| `allowed_users` | array | `[]` | Allowed user list |
| `admin_users` | array | `[]` | Admin user list |
| `rate_limiting` | boolean | `true` | Enable rate limiting |
| `max_requests_per_minute` | integer | `1000` | Request rate limit |

### Encryption Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `encrypt_at_rest` | boolean | `false` | Encrypt stored data |
| `encrypt_in_transit` | boolean | `true` | Encrypt network traffic |
| `encryption_algorithm` | string | `"AES-256"` | Encryption algorithm |
| `key_rotation_days` | integer | `90` | Key rotation period |

### Example Security Configuration

```json
{
  "security": {
    "enabled": true,
    "auth_method": "jwt",
    "token_expiry": 7200,
    "secret_key": "${JWT_SECRET_KEY}",
    "require_auth": true,
    "allowed_users": ["prediction_user", "monitoring_user"],
    "admin_users": ["admin", "ops_team"],
    "rate_limiting": true,
    "max_requests_per_minute": 5000,
    "encrypt_at_rest": true,
    "encrypt_in_transit": true,
    "encryption_algorithm": "AES-256-GCM",
    "key_rotation_days": 30,
    "password_policy": {
      "min_length": 12,
      "require_special_chars": true,
      "require_numbers": true,
      "require_uppercase": true
    }
  }
}
```

## 🌍 Environment Variables

Environment variables can be used to override configuration values.

### Variable Naming Convention

Configuration keys are mapped to environment variables using this pattern:
- Replace dots with underscores
- Convert to uppercase
- Add `PREDICTION_` prefix

Examples:
- `database.host` → `PREDICTION_DATABASE_HOST`
- `spark.executor_memory` → `PREDICTION_SPARK_EXECUTOR_MEMORY`
- `monitoring.alert_email` → `PREDICTION_MONITORING_ALERT_EMAIL`

### Common Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `PREDICTION_DATABASE_HOST` | Database hostname | `db.example.com` |
| `PREDICTION_DATABASE_PASSWORD` | Database password | `secure_password` |
| `PREDICTION_SPARK_MASTER` | Spark master URL | `yarn` |
| `PREDICTION_HDFS_NAMENODE_URL` | HDFS NameNode URL | `hdfs://namenode:9000` |
| `PREDICTION_MONITORING_ALERT_EMAIL` | Alert email | `admin@example.com` |

### Variable Substitution in Configuration

Use `${VARIABLE_NAME}` syntax for variable substitution:

```json
{
  "database": {
    "host": "${DB_HOST}",
    "password": "${DB_PASSWORD}",
    "ssl_cert": "${SSL_CERT_PATH:-/default/path/cert.pem}"
  }
}
```

The `:-` syntax provides default values: `${VAR:-default}`.

## ✅ Configuration Validation

The system validates configuration on startup and provides detailed error messages.

### Validation Rules

#### Database Configuration
- `host` must be a valid hostname or IP address
- `port` must be between 1 and 65535
- `pool_size` must be positive integer
- `ssl_mode` must be valid SSL mode

#### Prediction Configuration
- `batch_size` must be positive integer
- `prediction_horizons` must be non-empty array of positive integers
- `feature_window_hours` must be positive integer
- Threshold values must be between 0 and 1

#### Spark Configuration
- Memory values must be valid (e.g., "4g", "512m")
- Core counts must be positive integers
- Paths must be absolute paths

### Validation Examples

```python
from src.prediction.prediction_service import PredictionServiceConfig

# This will raise validation errors
config = PredictionServiceConfig({
    "database": {
        "host": "",  # ERROR: Empty host
        "port": 70000,  # ERROR: Invalid port
        "pool_size": -1  # ERROR: Negative pool size
    },
    "prediction": {
        "batch_size": 0,  # ERROR: Zero batch size
        "prediction_horizons": []  # ERROR: Empty horizons
    }
})
```

### Configuration Testing

Test configuration validity:

```bash
# Validate configuration file
python -c "
from src.prediction.prediction_service import PredictionServiceConfig
try:
    config = PredictionServiceConfig.from_file('config.json')
    print('Configuration valid')
except Exception as e:
    print(f'Configuration error: {e}')
"
```

## 📚 Configuration Examples

### Development Configuration

```json
{
  "database": {
    "host": "localhost",
    "port": 5432,
    "database": "traffic_prediction_dev",
    "user": "dev_user",
    "password": "dev_password",
    "pool_size": 5
  },
  "prediction": {
    "batch_size": 1000,
    "prediction_horizons": [15, 30, 60],
    "feature_window_hours": 12,
    "model_cache_size": 5
  },
  "spark": {
    "app_name": "traffic_prediction_dev",
    "master": "local[*]",
    "driver_memory": "1g",
    "executor_memory": "2g",
    "executor_cores": 2,
    "num_executors": 2
  },
  "monitoring": {
    "enabled": true,
    "collection_interval": 300,
    "accuracy_threshold": 0.7,
    "alert_email": "dev@example.com"
  },
  "hdfs": {
    "namenode_url": "hdfs://localhost:9000",
    "model_base_path": "/dev/models",
    "data_base_path": "/dev/data"
  },
  "logging": {
    "level": "DEBUG",
    "file_path": "logs/dev_service.log"
  }
}
```

### Production Configuration

```json
{
  "database": {
    "host": "prod-db-cluster.example.com",
    "port": 5432,
    "database": "traffic_prediction",
    "user": "prediction_service",
    "password": "${DB_PASSWORD}",
    "pool_size": 50,
    "max_overflow": 100,
    "ssl_mode": "require",
    "ssl_cert": "/etc/ssl/certs/client.crt"
  },
  "prediction": {
    "batch_size": 20000,
    "prediction_horizons": [15, 30, 60, 120, 240],
    "feature_window_hours": 72,
    "model_cache_size": 50,
    "max_concurrent_predictions": 500
  },
  "spark": {
    "app_name": "traffic_prediction_prod",
    "master": "yarn",
    "deploy_mode": "cluster",
    "driver_memory": "8g",
    "driver_cores": 8,
    "executor_memory": "16g",
    "executor_cores": 8,
    "num_executors": 50,
    "dynamic_allocation": true,
    "min_executors": 20,
    "max_executors": 200
  },
  "monitoring": {
    "enabled": true,
    "collection_interval": 30,
    "retention_days": 365,
    "accuracy_threshold": 0.9,
    "alert_email": "ops-team@example.com",
    "alert_channels": ["email", "slack", "pagerduty"]
  },
  "hdfs": {
    "namenode_url": "hdfs://prod-namenode.example.com:9000",
    "ha_enabled": true,
    "ha_namenodes": [
      "namenode1.example.com:9000",
      "namenode2.example.com:9000"
    ],
    "replication_factor": 3
  },
  "logging": {
    "level": "INFO",
    "file_path": "/var/log/prediction_service/service.log",
    "max_file_size": "1GB",
    "backup_count": 100
  },
  "security": {
    "enabled": true,
    "auth_method": "jwt",
    "require_auth": true,
    "rate_limiting": true,
    "max_requests_per_minute": 10000,
    "encrypt_in_transit": true
  }
}
```

### High-Performance Configuration

```json
{
  "database": {
    "host": "high-perf-db.example.com",
    "port": 5432,
    "database": "traffic_prediction",
    "user": "prediction_service",
    "password": "${DB_PASSWORD}",
    "pool_size": 100,
    "max_overflow": 200,
    "pool_timeout": 10,
    "command_timeout": 30
  },
  "prediction": {
    "batch_size": 50000,
    "prediction_horizons": [15, 30, 60],
    "feature_window_hours": 24,
    "model_cache_size": 100,
    "max_concurrent_predictions": 1000,
    "prediction_timeout": 60
  },
  "spark": {
    "app_name": "traffic_prediction_highperf",
    "master": "yarn",
    "deploy_mode": "cluster",
    "driver_memory": "16g",
    "driver_cores": 16,
    "executor_memory": "32g",
    "executor_cores": 16,
    "num_executors": 100,
    "dynamic_allocation": true,
    "min_executors": 50,
    "max_executors": 500,
    "sql_shuffle_partitions": 1000,
    "additional_conf": {
      "spark.sql.adaptive.enabled": "true",
      "spark.sql.adaptive.coalescePartitions.enabled": "true",
      "spark.sql.adaptive.skewJoin.enabled": "true",
      "spark.serializer": "org.apache.spark.serializer.KryoSerializer",
      "spark.sql.execution.arrow.pyspark.enabled": "true"
    }
  },
  "monitoring": {
    "enabled": true,
    "collection_interval": 15,
    "batch_size": 5000,
    "response_time_threshold": 0.1,
    "throughput_threshold": 10000,
    "cpu_threshold": 0.9,
    "memory_threshold": 0.95
  }
}
```

## 🔧 Configuration Management Best Practices

### Environment-Specific Configurations

1. **Use environment variables** for sensitive data (passwords, API keys)
2. **Separate configuration files** per environment (dev, staging, prod)
3. **Version control** configuration templates, not actual configs
4. **Validate configurations** before deployment

### Configuration Security

1. **Never commit passwords** or secrets to version control
2. **Use encryption** for sensitive configuration data
3. **Implement access controls** for configuration files
4. **Audit configuration changes**

### Configuration Monitoring

1. **Monitor configuration drift** between environments
2. **Track configuration changes** with timestamps and users
3. **Test configuration updates** in staging before production
4. **Maintain configuration documentation**

### Troubleshooting Configuration Issues

```bash
# Check configuration syntax
python -m json.tool config.json

# Validate configuration
python -c "from src.prediction.prediction_service import PredictionServiceConfig; PredictionServiceConfig.from_file('config.json')"

# Test database connection with config
python -c "
import json
import psycopg2
with open('config.json') as f:
    config = json.load(f)
    db = config['database']
    conn = psycopg2.connect(**db)
    print('Database connection successful')
"
```

---

For additional configuration support, see the main [README](README.md) or create an issue in the project repository.