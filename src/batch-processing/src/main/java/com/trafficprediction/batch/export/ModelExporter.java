package com.trafficprediction.batch.export;

import org.apache.hadoop.conf.Configuration;

/**
 * Interface for model exporters that convert Spark ML models to different formats.
 */
public interface ModelExporter {
    
    /**
     * Exports a model from the source path to the destination path in a specific format.
     * 
     * @param modelPath Path to the Spark ML model
     * @param exportPath Path where the exported model should be saved
     * @param conf Hadoop configuration
     * @throws Exception if the export fails
     */
    void exportModel(String modelPath, String exportPath, Configuration conf) throws Exception;
}