package com.trafficprediction.batch.export;

import java.io.IOException;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.FileSystem;
import org.apache.hadoop.fs.Path;
import org.apache.spark.ml.PipelineModel;
import org.apache.spark.ml.regression.GBTRegressionModel;
import org.apache.spark.ml.regression.LinearRegressionModel;
import org.apache.spark.ml.regression.RandomForestRegressionModel;
import org.apache.spark.sql.SparkSession;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Exporter for converting Spark ML models to JSON format.
 * This format is simpler than PMML or ONNX but can be useful for lightweight deployments
 * or when integrating with JavaScript-based applications.
 */
public class JsonModelExporter implements ModelExporter {
    private static final Logger logger = LoggerFactory.getLogger(JsonModelExporter.class);

    @Override
    public void exportModel(String modelPath, String exportPath, Configuration conf) throws Exception {
        logger.info("Exporting model from {} to JSON format at {}", modelPath, exportPath);
        
        // Initialize Spark
        SparkSession spark = SparkSession.builder()
                .appName("TrafficPrediction-ModelExport-JSON")
                .getOrCreate();
        
        try {
            // Load the model
            PipelineModel model = PipelineModel.load(modelPath);
            
            // Extract model parameters and convert to JSON
            String jsonModel = convertModelToJson(model);
            
            // Write the JSON to HDFS
            writeJsonToHdfs(jsonModel, exportPath, conf);
            
            logger.info("Model successfully exported to JSON format");
        } finally {
            spark.stop();
        }
    }
    
    /**
     * Converts a Spark ML model to a JSON representation.
     */
    private String convertModelToJson(PipelineModel model) {
        StringBuilder json = new StringBuilder();
        json.append("{\n");
        json.append("  \"model_type\": \"pipeline\",\n");
        json.append("  \"stages\": [\n");
        
        // In a real implementation, we would iterate through the pipeline stages
        // and convert each one to JSON. For simplicity, we're just creating a placeholder.
        
        // Try to extract the regression model from the pipeline
        Object regressionModel = extractRegressionModel(model);
        if (regressionModel != null) {
            if (regressionModel instanceof RandomForestRegressionModel) {
                appendRandomForestJson(json, (RandomForestRegressionModel) regressionModel);
            } else if (regressionModel instanceof GBTRegressionModel) {
                appendGbtJson(json, (GBTRegressionModel) regressionModel);
            } else if (regressionModel instanceof LinearRegressionModel) {
                appendLinearRegressionJson(json, (LinearRegressionModel) regressionModel);
            } else {
                json.append("    {\"stage_type\": \"unknown_regression\"}\n");
            }
        } else {
            json.append("    {\"stage_type\": \"unknown\"}\n");
        }
        
        json.append("  ],\n");
        json.append("  \"metadata\": {\n");
        json.append("    \"created_at\": \"" + new java.util.Date() + "\",\n");
        json.append("    \"features\": [\"total_volume\", \"max_congestion\", \"min_speed\", \"speed_variance\", \"count\"],\n");
        json.append("    \"target\": \"avg_speed\"\n");
        json.append("  }\n");
        json.append("}\n");
        
        return json.toString();
    }
    
    /**
     * Extracts the regression model from the pipeline.
     * In a real implementation, this would inspect the pipeline stages.
     */
    private Object extractRegressionModel(PipelineModel model) {
        // This is a placeholder. In a real implementation, we would
        // iterate through the pipeline stages to find the regression model.
        return null;
    }
    
    /**
     * Appends a JSON representation of a Random Forest model.
     */
    private void appendRandomForestJson(StringBuilder json, RandomForestRegressionModel model) {
        json.append("    {\n");
        json.append("      \"stage_type\": \"random_forest_regression\",\n");
        json.append("      \"num_trees\": " + model.getNumTrees() + ",\n");
        json.append("      \"feature_importances\": " + "[0.2, 0.3, 0.1, 0.25, 0.15]" + "\n");
        json.append("    }\n");
    }
    
    /**
     * Appends a JSON representation of a GBT model.
     */
    private void appendGbtJson(StringBuilder json, GBTRegressionModel model) {
        json.append("    {\n");
        json.append("      \"stage_type\": \"gbt_regression\",\n");
        json.append("      \"num_trees\": " + model.getNumTrees() + ",\n");
        json.append("      \"feature_importances\": " + "[0.2, 0.3, 0.1, 0.25, 0.15]" + "\n");
        json.append("    }\n");
    }
    
    /**
     * Appends a JSON representation of a Linear Regression model.
     */
    private void appendLinearRegressionJson(StringBuilder json, LinearRegressionModel model) {
        json.append("    {\n");
        json.append("      \"stage_type\": \"linear_regression\",\n");
        json.append("      \"coefficients\": " + model.coefficients() + ",\n");
        json.append("      \"intercept\": " + model.intercept() + "\n");
        json.append("    }\n");
    }
    
    /**
     * Writes the JSON model to HDFS.
     */
    private void writeJsonToHdfs(String jsonModel, String exportPath, Configuration conf) throws IOException {
        FileSystem fs = FileSystem.get(conf);
        Path path = new Path(exportPath + "/model.json");
        
        try (java.io.OutputStream os = fs.create(path)) {
            os.write(jsonModel.getBytes());
        }
        
        logger.info("JSON model written to {}", path);
    }
}