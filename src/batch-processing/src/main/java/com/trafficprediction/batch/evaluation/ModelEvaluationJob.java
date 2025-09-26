package com.trafficprediction.batch.evaluation;

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
 * Job for evaluating trained models against test datasets.
 * This job loads a trained model and evaluates its performance on test data.
 */
public class ModelEvaluationJob extends Configured implements Tool {
    private static final Logger logger = LoggerFactory.getLogger(ModelEvaluationJob.class);

    public static void main(String[] args) throws Exception {
        int exitCode = ToolRunner.run(new Configuration(), new ModelEvaluationJob(), args);
        System.exit(exitCode);
    }

    @Override
    public int run(String[] args) throws Exception {
        if (args.length < 3) {
            System.err.println("Usage: ModelEvaluationJob <model path> <test data path> <output path>");
            return -1;
        }

        String modelPath = args[0];
        String testDataPath = args[1];
        String outputPath = args[2];

        // Validate paths
        Configuration conf = getConf();
        FileSystem fs = FileSystem.get(conf);
        
        if (!fs.exists(new Path(modelPath))) {
            logger.error("Model path does not exist: {}", modelPath);
            return -1;
        }
        
        if (!fs.exists(new Path(testDataPath))) {
            logger.error("Test data path does not exist: {}", testDataPath);
            return -1;
        }

        // Run Spark job for model evaluation
        try {
            logger.info("Starting model evaluation with model: {}, test data: {}, output: {}", 
                    modelPath, testDataPath, outputPath);
            
            // In a real implementation, this would submit a Spark job to evaluate the model
            // For simplicity, we're just calling the SparkModelEvaluator directly
            String[] sparkArgs = new String[] {modelPath, testDataPath, outputPath};
            SparkModelEvaluator.main(sparkArgs);
            
            logger.info("Model evaluation completed successfully");
            return 0;
        } catch (Exception e) {
            logger.error("Model evaluation failed", e);
            return -1;
        }
    }
}