package com.trafficprediction.batch;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.util.ToolRunner;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import com.trafficprediction.batch.feature.FeatureExtractionJob;
import com.trafficprediction.batch.training.ModelTrainingJob;
import com.trafficprediction.batch.evaluation.ModelEvaluationJob;
import com.trafficprediction.batch.export.ModelExportJob;

/**
 * Main entry point for batch processing jobs.
 */
public class Main {
    private static final Logger logger = LoggerFactory.getLogger(Main.class);

    public static void main(String[] args) {
        if (args.length < 1) {
            printUsage();
            System.exit(1);
        }

        String jobType = args[0];
        String[] jobArgs = new String[args.length - 1];
        System.arraycopy(args, 1, jobArgs, 0, jobArgs.length);

        try {
            Configuration conf = new Configuration();
            int exitCode = 0;

            switch (jobType) {
                case "feature-extraction":
                    logger.info("Starting feature extraction job");
                    exitCode = ToolRunner.run(conf, new FeatureExtractionJob(), jobArgs);
                    break;
                case "model-training":
                    logger.info("Starting model training job");
                    exitCode = ToolRunner.run(conf, new ModelTrainingJob(), jobArgs);
                    break;
                case "model-evaluation":
                    logger.info("Starting model evaluation job");
                    exitCode = ToolRunner.run(conf, new ModelEvaluationJob(), jobArgs);
                    break;
                case "model-export":
                    logger.info("Starting model export job");
                    exitCode = ToolRunner.run(conf, new ModelExportJob(), jobArgs);
                    break;
                default:
                    logger.error("Unknown job type: {}", jobType);
                    printUsage();
                    System.exit(1);
            }

            logger.info("Job completed with exit code: {}", exitCode);
            System.exit(exitCode);
        } catch (Exception e) {
            logger.error("Job failed with exception", e);
            System.exit(1);
        }
    }

    private static void printUsage() {
        System.out.println("Usage: java -jar batch-processing.jar <job-type> [job-specific-args]\n");
        System.out.println("Job Types:");
        System.out.println("  feature-extraction  - Extract features from raw traffic data");
        System.out.println("  model-training      - Train prediction models using extracted features");
        System.out.println("  model-evaluation    - Evaluate trained models against test data");
        System.out.println("  model-export        - Export trained models for deployment");
    }
}