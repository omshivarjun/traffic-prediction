package com.trafficprediction.batch.export;

import java.io.IOException;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.conf.Configured;
import org.apache.hadoop.fs.FileSystem;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.util.Tool;
import org.apache.hadoop.util.ToolRunner;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Job for exporting trained models for deployment in the stream processing pipeline.
 * This job converts Spark ML models to a format that can be used by the stream processing system.
 */
public class ModelExportJob extends Configured implements Tool {
    private static final Logger logger = LoggerFactory.getLogger(ModelExportJob.class);

    public static void main(String[] args) throws Exception {
        int exitCode = ToolRunner.run(new Configuration(), new ModelExportJob(), args);
        System.exit(exitCode);
    }

    @Override
    public int run(String[] args) throws Exception {
        if (args.length < 3) {
            System.err.println("Usage: ModelExportJob <model path> <export path> <model format>");
            System.err.println("Model formats: pmml, onnx, json");
            return -1;
        }

        String modelPath = args[0];
        String exportPath = args[1];
        String modelFormat = args[2];

        // Validate model path exists
        Configuration conf = getConf();
        FileSystem fs = FileSystem.get(conf);
        
        if (!fs.exists(new Path(modelPath))) {
            logger.error("Model path does not exist: {}", modelPath);
            return -1;
        }

        // Export model
        try {
            logger.info("Starting model export from {} to {} in {} format", 
                    modelPath, exportPath, modelFormat);
            
            ModelExporter exporter = createExporter(modelFormat);
            exporter.exportModel(modelPath, exportPath, conf);
            
            logger.info("Model export completed successfully");
            return 0;
        } catch (Exception e) {
            logger.error("Model export failed", e);
            return -1;
        }
    }

    /**
     * Creates an appropriate model exporter based on the requested format.
     */
    private ModelExporter createExporter(String modelFormat) {
        switch (modelFormat.toLowerCase()) {
            case "pmml":
                return new PmmlModelExporter();
            case "onnx":
                return new OnnxModelExporter();
            case "json":
                return new JsonModelExporter();
            default:
                throw new IllegalArgumentException("Unsupported model format: " + modelFormat);
        }
    }
}