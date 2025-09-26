package com.trafficprediction.batch.training;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.FileSystem;
import org.apache.hadoop.fs.Path;

/**
 * Configuration utility for model training jobs.
 * This class handles loading and parsing configuration parameters for model training.
 */
public class ModelTrainingConfig {
    
    // Default configuration values
    private static final Map<String, String> DEFAULT_CONFIG = new HashMap<>();
    static {
        // Random Forest defaults
        DEFAULT_CONFIG.put("random-forest.numTrees", "100");
        DEFAULT_CONFIG.put("random-forest.maxDepth", "10");
        DEFAULT_CONFIG.put("random-forest.minInstancesPerNode", "1");
        
        // Gradient Boosting defaults
        DEFAULT_CONFIG.put("gradient-boosting.maxIter", "100");
        DEFAULT_CONFIG.put("gradient-boosting.maxDepth", "5");
        DEFAULT_CONFIG.put("gradient-boosting.stepSize", "0.1");
        
        // Linear Regression defaults
        DEFAULT_CONFIG.put("linear-regression.maxIter", "100");
        DEFAULT_CONFIG.put("linear-regression.regParam", "0.3");
        DEFAULT_CONFIG.put("linear-regression.elasticNetParam", "0.8");
        
        // Training defaults
        DEFAULT_CONFIG.put("training.trainTestSplit", "0.8");
        DEFAULT_CONFIG.put("training.seed", "42");
        DEFAULT_CONFIG.put("training.crossValidation", "false");
        DEFAULT_CONFIG.put("training.crossValidationFolds", "3");
    }
    
    private final Map<String, String> config;
    
    /**
     * Creates a new configuration with default values.
     */
    public ModelTrainingConfig() {
        this.config = new HashMap<>(DEFAULT_CONFIG);
    }
    
    /**
     * Loads configuration from a file in HDFS.
     * 
     * @param conf Hadoop configuration
     * @param configPath Path to the configuration file
     * @return ModelTrainingConfig with values loaded from the file
     * @throws IOException if the file cannot be read
     */
    public static ModelTrainingConfig loadFromHdfs(Configuration conf, String configPath) throws IOException {
        ModelTrainingConfig config = new ModelTrainingConfig();
        
        FileSystem fs = FileSystem.get(conf);
        Path path = new Path(configPath);
        
        if (fs.exists(path)) {
            // In a real implementation, this would parse the configuration file
            // and update the config map with values from the file.
            // For simplicity, we're just returning the default config.
        }
        
        return config;
    }
    
    /**
     * Updates configuration with values from command line arguments.
     * 
     * @param args Command line arguments in the format "key=value"
     * @return this configuration instance for chaining
     */
    public ModelTrainingConfig updateFromArgs(String[] args) {
        for (String arg : args) {
            String[] parts = arg.split("=", 2);
            if (parts.length == 2) {
                config.put(parts[0], parts[1]);
            }
        }
        return this;
    }
    
    /**
     * Gets a configuration value as a string.
     * 
     * @param key Configuration key
     * @return Configuration value, or null if not found
     */
    public String getString(String key) {
        return config.get(key);
    }
    
    /**
     * Gets a configuration value as an integer.
     * 
     * @param key Configuration key
     * @param defaultValue Default value to return if the key is not found or the value is not a valid integer
     * @return Configuration value as an integer
     */
    public int getInt(String key, int defaultValue) {
        String value = config.get(key);
        if (value == null) {
            return defaultValue;
        }
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }
    
    /**
     * Gets a configuration value as a double.
     * 
     * @param key Configuration key
     * @param defaultValue Default value to return if the key is not found or the value is not a valid double
     * @return Configuration value as a double
     */
    public double getDouble(String key, double defaultValue) {
        String value = config.get(key);
        if (value == null) {
            return defaultValue;
        }
        try {
            return Double.parseDouble(value);
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }
    
    /**
     * Gets a configuration value as a boolean.
     * 
     * @param key Configuration key
     * @param defaultValue Default value to return if the key is not found
     * @return Configuration value as a boolean
     */
    public boolean getBoolean(String key, boolean defaultValue) {
        String value = config.get(key);
        if (value == null) {
            return defaultValue;
        }
        return Boolean.parseBoolean(value);
    }
    
    /**
     * Sets a configuration value.
     * 
     * @param key Configuration key
     * @param value Configuration value
     * @return this configuration instance for chaining
     */
    public ModelTrainingConfig set(String key, String value) {
        config.put(key, value);
        return this;
    }
    
    /**
     * Gets all configuration values as a map.
     * 
     * @return Map of configuration values
     */
    public Map<String, String> getAll() {
        return new HashMap<>(config);
    }
}