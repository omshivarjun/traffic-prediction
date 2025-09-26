package com.trafficprediction.batch.evaluation;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

import org.apache.spark.ml.PipelineModel;
import org.apache.spark.ml.evaluation.RegressionEvaluator;
import org.apache.spark.sql.Dataset;
import org.apache.spark.sql.Row;
import org.apache.spark.sql.SparkSession;
import org.apache.spark.sql.types.DataTypes;
import org.apache.spark.sql.types.StructField;
import org.apache.spark.sql.types.StructType;

/**
 * Spark application for evaluating trained traffic prediction models.
 * This class loads a trained model and evaluates its performance on test data.
 */
public class SparkModelEvaluator {

    public static void main(String[] args) {
        if (args.length < 3) {
            System.err.println("Usage: SparkModelEvaluator <model path> <test data path> <output path>");
            System.exit(1);
        }

        String modelPath = args[0];
        String testDataPath = args[1];
        String outputPath = args[2];

        // Initialize Spark
        SparkSession spark = SparkSession.builder()
                .appName("TrafficPrediction-ModelEvaluation")
                .getOrCreate();

        try {
            // Load model
            PipelineModel model = PipelineModel.load(modelPath);
            
            // Load test data
            Dataset<Row> testData = loadData(spark, testDataPath);
            
            // Evaluate model
            Map<String, Double> metrics = evaluateModel(model, testData);
            
            // Save evaluation results
            saveEvaluationResults(spark, metrics, outputPath);
            
            System.out.println("Model evaluation completed successfully. Results saved to: " + outputPath);
            
        } catch (Exception e) {
            System.err.println("Error evaluating model: " + e.getMessage());
            e.printStackTrace();
            System.exit(1);
        } finally {
            spark.stop();
        }
    }

    /**
     * Loads and prepares the test data.
     */
    private static Dataset<Row> loadData(SparkSession spark, String testDataPath) {
        // Define schema for the feature data
        // Format: location_id_timewindow,avg_speed,total_volume,max_congestion,min_speed,speed_variance,count
        StructType schema = DataTypes.createStructType(new StructField[] {
            DataTypes.createStructField("key", DataTypes.StringType, false),
            DataTypes.createStructField("avg_speed", DataTypes.DoubleType, false),
            DataTypes.createStructField("total_volume", DataTypes.DoubleType, false),
            DataTypes.createStructField("max_congestion", DataTypes.IntegerType, false),
            DataTypes.createStructField("min_speed", DataTypes.DoubleType, false),
            DataTypes.createStructField("speed_variance", DataTypes.DoubleType, false),
            DataTypes.createStructField("count", DataTypes.IntegerType, false)
        });
        
        // Load CSV data
        Dataset<Row> data = spark.read()
                .schema(schema)
                .option("header", "false")
                .option("delimiter", ",")
                .csv(testDataPath);
        
        // Extract location and time window from key
        data = data.withColumn("location", org.apache.spark.sql.functions.split(data.col("key"), "_").getItem(0))
                  .withColumn("time_window", org.apache.spark.sql.functions.split(data.col("key"), "_").getItem(1));
        
        // Assemble features into a vector (same as in training)
        org.apache.spark.ml.feature.VectorAssembler assembler = new org.apache.spark.ml.feature.VectorAssembler()
                .setInputCols(new String[]{"total_volume", "max_congestion", "min_speed", "speed_variance", "count"})
                .setOutputCol("features");
        
        data = assembler.transform(data);
        
        // Set target variable (we're predicting average speed)
        data = data.withColumnRenamed("avg_speed", "label");
        
        return data;
    }

    /**
     * Evaluates the model on test data and returns evaluation metrics.
     */
    private static Map<String, Double> evaluateModel(PipelineModel model, Dataset<Row> testData) {
        // Make predictions
        Dataset<Row> predictions = model.transform(testData);
        
        // Select example rows to display
        predictions.select("prediction", "label", "features").show(5);
        
        // Calculate evaluation metrics
        Map<String, Double> metrics = new HashMap<>();
        
        RegressionEvaluator evaluator = new RegressionEvaluator()
                .setLabelCol("label")
                .setPredictionCol("prediction");
        
        // Root Mean Squared Error
        evaluator.setMetricName("rmse");
        double rmse = evaluator.evaluate(predictions);
        metrics.put("rmse", rmse);
        System.out.println("Root Mean Squared Error (RMSE) = " + rmse);
        
        // Mean Absolute Error
        evaluator.setMetricName("mae");
        double mae = evaluator.evaluate(predictions);
        metrics.put("mae", mae);
        System.out.println("Mean Absolute Error (MAE) = " + mae);
        
        // R-squared
        evaluator.setMetricName("r2");
        double r2 = evaluator.evaluate(predictions);
        metrics.put("r2", r2);
        System.out.println("R2 = " + r2);
        
        // Mean Squared Error
        evaluator.setMetricName("mse");
        double mse = evaluator.evaluate(predictions);
        metrics.put("mse", mse);
        System.out.println("Mean Squared Error (MSE) = " + mse);
        
        return metrics;
    }

    /**
     * Saves evaluation results to HDFS.
     */
    private static void saveEvaluationResults(SparkSession spark, Map<String, Double> metrics, String outputPath) throws IOException {
        // Convert metrics to a dataset
        Dataset<Row> metricsDF = spark.createDataFrame(
                metrics.entrySet().stream()
                        .map(entry -> new MetricRow(entry.getKey(), entry.getValue()))
                        .collect(java.util.stream.Collectors.toList()),
                MetricRow.class);
        
        // Save metrics as CSV
        metricsDF.coalesce(1).write()
                .option("header", "true")
                .mode("overwrite")
                .csv(outputPath + "/metrics");
        
        // In a real implementation, you might also save visualizations, confusion matrices, etc.
    }

    /**
     * Helper class for creating a dataset from metrics.
     */
    public static class MetricRow {
        private String metricName;
        private Double metricValue;
        
        public MetricRow(String metricName, Double metricValue) {
            this.metricName = metricName;
            this.metricValue = metricValue;
        }
        
        public String getMetricName() {
            return metricName;
        }
        
        public Double getMetricValue() {
            return metricValue;
        }
    }
}