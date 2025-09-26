package com.trafficprediction.batch.training;

import java.io.IOException;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.conf.Configured;
import org.apache.hadoop.fs.FileSystem;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.util.Tool;
import org.apache.hadoop.util.ToolRunner;
import org.apache.hadoop.yarn.api.records.ApplicationId;
import org.apache.hadoop.yarn.api.records.ApplicationSubmissionContext;
import org.apache.hadoop.yarn.api.records.ContainerLaunchContext;
import org.apache.hadoop.yarn.api.records.Resource;
import org.apache.hadoop.yarn.client.api.YarnClient;
import org.apache.hadoop.yarn.client.api.YarnClientApplication;
import org.apache.hadoop.yarn.conf.YarnConfiguration;
import org.apache.hadoop.yarn.exceptions.YarnException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * YARN application for training traffic prediction models using extracted features.
 * This job submits a Spark application to YARN to train machine learning models.
 */
public class ModelTrainingJob extends Configured implements Tool {
    private static final Logger logger = LoggerFactory.getLogger(ModelTrainingJob.class);

    public static void main(String[] args) throws Exception {
        int exitCode = ToolRunner.run(new Configuration(), new ModelTrainingJob(), args);
        System.exit(exitCode);
    }

    @Override
    public int run(String[] args) throws Exception {
        if (args.length < 3) {
            System.err.println("Usage: ModelTrainingJob <input path> <output path> <model type> [hyperparams]");
            System.err.println("Model types: random-forest, gradient-boosting, linear-regression");
            return -1;
        }

        String inputPath = args[0];
        String outputPath = args[1];
        String modelType = args[2];
        
        // Parse additional hyperparameters if provided
        String hyperParams = "";
        if (args.length > 3) {
            StringBuilder sb = new StringBuilder();
            for (int i = 3; i < args.length; i++) {
                sb.append(args[i]).append(" ");
            }
            hyperParams = sb.toString().trim();
        }

        // Validate input path exists
        Configuration conf = getConf();
        FileSystem fs = FileSystem.get(conf);
        if (!fs.exists(new Path(inputPath))) {
            logger.error("Input path does not exist: {}", inputPath);
            return -1;
        }

        // Submit Spark application to YARN
        try {
            ApplicationId appId = submitSparkApplication(inputPath, outputPath, modelType, hyperParams);
            logger.info("Submitted Spark application for model training. Application ID: {}", appId);
            return 0;
        } catch (Exception e) {
            logger.error("Failed to submit Spark application", e);
            return -1;
        }
    }

    /**
     * Submits a Spark application to YARN for model training.
     */
    private ApplicationId submitSparkApplication(String inputPath, String outputPath, 
                                                String modelType, String hyperParams) 
            throws IOException, YarnException {
        
        // Create YARN client
        YarnConfiguration yarnConf = new YarnConfiguration(getConf());
        YarnClient yarnClient = YarnClient.createYarnClient();
        yarnClient.init(yarnConf);
        yarnClient.start();
        
        try {
            // Create application
            YarnClientApplication app = yarnClient.createApplication();
            ApplicationSubmissionContext appContext = app.getApplicationSubmissionContext();
            
            // Set application name
            String appName = "TrafficPrediction-ModelTraining-" + modelType;
            appContext.setApplicationName(appName);
            
            // Set up container launch context for the application master
            ContainerLaunchContext amContainer = createAMContainerContext(inputPath, outputPath, modelType, hyperParams);
            appContext.setAMContainerSpec(amContainer);
            
            // Set up resource requirements
            Resource resource = Resource.newInstance(2048, 2); // 2GB memory, 2 cores
            appContext.setResource(resource);
            
            // Submit application
            ApplicationId appId = appContext.getApplicationId();
            appContext.setApplicationId(appId);
            yarnClient.submitApplication(appContext);
            
            return appId;
        } finally {
            yarnClient.stop();
        }
    }
    
    /**
     * Creates the container launch context for the application master.
     */
    private ContainerLaunchContext createAMContainerContext(String inputPath, String outputPath, 
                                                          String modelType, String hyperParams) {
        // In a real implementation, this would set up the Spark submit command with appropriate
        // class path, environment variables, and command line arguments.
        // For simplicity, we're returning a placeholder.
        
        // This is a simplified version. In a real implementation, you would:
        // 1. Set up the correct classpath
        // 2. Set up the correct Spark submit command
        // 3. Set up the correct environment variables
        // 4. Set up the correct local resources (JARs, etc.)
        
        return ContainerLaunchContext.newInstance(null, null, null, null, null, null);
    }
}