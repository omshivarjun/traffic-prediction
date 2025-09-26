# Batch Processing for Traffic Prediction Model Training

This module contains batch processing jobs for training traffic prediction models using Hadoop and YARN.

## Overview

The batch processing module is responsible for:

1. Extracting features from historical traffic data stored in HDFS
2. Training machine learning models for traffic prediction
3. Evaluating model performance
4. Exporting trained models for use in the stream processing pipeline

## Components

- **Feature Extraction**: MapReduce jobs to process raw traffic data and extract relevant features
- **Model Training**: YARN applications for training prediction models
- **Model Evaluation**: Jobs to evaluate model performance against test datasets
- **Model Export**: Utilities to export trained models for deployment

## Usage

### Prerequisites

- Hadoop ecosystem running (HDFS, YARN, etc.)
- Historical traffic data loaded into HDFS
- Java Development Kit (JDK) 8 or later
- Maven for building the project

### Building

```bash
mvn clean package
```

### Running Jobs

Use the provided scripts to run the batch processing jobs:

```bash
./run-feature-extraction.ps1
./run-model-training.ps1
./run-model-evaluation.ps1
```

## Configuration

Configuration files are located in the `config` directory. Modify these files to adjust job parameters, input/output paths, and model hyperparameters.