package com.trafficprediction.batch.export;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Factory class for creating model exporters based on the requested format.
 */
public class ModelExporterFactory {
    private static final Logger logger = LoggerFactory.getLogger(ModelExporterFactory.class);
    
    /**
     * Creates a model exporter for the specified format.
     * 
     * @param format The export format (pmml, onnx, json)
     * @return A ModelExporter instance for the specified format
     * @throws IllegalArgumentException if the format is not supported
     */
    public static ModelExporter createExporter(String format) {
        logger.info("Creating model exporter for format: {}", format);
        
        if (format == null || format.isEmpty()) {
            throw new IllegalArgumentException("Export format cannot be null or empty");
        }
        
        switch (format.toLowerCase()) {
            case "pmml":
                return new PmmlModelExporter();
            case "onnx":
                return new OnnxModelExporter();
            case "json":
                return new JsonModelExporter();
            default:
                throw new IllegalArgumentException("Unsupported export format: " + format);
        }
    }
}