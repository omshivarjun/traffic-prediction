package com.trafficprediction.batch.training;

import org.apache.spark.SparkConf;
import org.apache.spark.api.java.JavaSparkContext;
import org.apache.spark.ml.Pipeline;
import org.apache.spark.ml.PipelineModel;
import org.apache.spark.ml.PipelineStage;
import org.apache.spark.ml.evaluation.RegressionEvaluator;
import org.apache.spark.ml.feature.VectorAssembler;
import org.apache.spark.ml.regression.GBTRegressor;
import org.apache.spark.ml.regression.LinearRegression;
import org.apache.spark.ml.regression.RandomForestRegressor;
import org.apache.spark.ml.tuning.CrossValidator;
import org.apache.spark.ml.tuning.CrossValidatorModel;
import org.apache.spark.ml.tuning.ParamGridBuilder;
import org.apache.spark.sql.Dataset;
import org.apache.spark.sql.Row;
import org.apache.spark.sql.SparkSession;
import org.apache.spark.sql.types.DataTypes;
import org.apache.spark.sql.types.StructField;
import org.apache.spark.sql.types.StructType;

/**
 * Spark application for training traffic prediction models.
 * This class is the main entry point for the Spark application submitted to YARN.
 */
public class SparkModelTrainer {

    public static void main(String[] args) {
        if (args.length < 3) {
            System.err.println("Usage: SparkModelTrainer <input path> <output path> <model type> [hyperparams]");
            System.exit(1);
        }

        String inputPath = args[0];
        String outputPath = args[1];
        String modelType = args[2];

        // Initialize Spark
        SparkSession spark = SparkSession.builder()
                .appName("TrafficPrediction-ModelTraining-" + modelType)
                .getOrCreate();

        try {
            // Load and prepare data
            Dataset<Row> data = loadData(spark, inputPath);
            
            // Split data into training and test sets
            Dataset<Row>[] splits = data.randomSplit(new double[]{0.8, 0.2}, 42);
            Dataset<Row> trainingData = splits[0];
            Dataset<Row> testData = splits[1];
            
            // Train model
            PipelineModel model = trainModel(trainingData, modelType);
            
            // Evaluate model
            evaluateModel(model, testData);
            
            // Save model
            model.write().overwrite().save(outputPath);
            
            System.out.println("Model training completed successfully. Model saved to: " + outputPath);
            
        } catch (Exception e) {
            System.err.println("Error training model: " + e.getMessage());
            e.printStackTrace();
            System.exit(1);
        } finally {
            spark.stop();
        }
    }

    /**
     * Loads and prepares the feature data.
     */
    private static Dataset<Row> loadData(SparkSession spark, String inputPath) {
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
                .csv(inputPath);
        
        // Extract location and time window from key
        data = data.withColumn("location", org.apache.spark.sql.functions.split(data.col("key"), "_").getItem(0))
                  .withColumn("time_window", org.apache.spark.sql.functions.split(data.col("key"), "_").getItem(1));
        
        // Assemble features into a vector
        VectorAssembler assembler = new VectorAssembler()
                .setInputCols(new String[]{"total_volume", "max_congestion", "min_speed", "speed_variance", "count"})
                .setOutputCol("features");
        
        data = assembler.transform(data);
        
        // Set target variable (we're predicting average speed)
        data = data.withColumnRenamed("avg_speed", "label");
        
        return data;
    }

    /**
     * Trains a model based on the specified model type.
     */
    private static PipelineModel trainModel(Dataset<Row> trainingData, String modelType) {
        Pipeline pipeline;
        
        switch (modelType.toLowerCase()) {
            case "random-forest":
                pipeline = createRandomForestPipeline();
                break;
            case "gradient-boosting":
                pipeline = createGradientBoostingPipeline();
                break;
            case "linear-regression":
                pipeline = createLinearRegressionPipeline();
                break;
            default:
                throw new IllegalArgumentException("Unsupported model type: " + modelType);
        }
        
        return pipeline.fit(trainingData);
    }

    /**
     * Creates a pipeline for Random Forest regression.
     */
    private static Pipeline createRandomForestPipeline() {
        RandomForestRegressor rf = new RandomForestRegressor()
                .setLabelCol("label")
                .setFeaturesCol("features")
                .setNumTrees(100)
                .setMaxDepth(10)
                .setSeed(42);
        
        return new Pipeline().setStages(new PipelineStage[]{rf});
    }

    /**
     * Creates a pipeline for Gradient Boosting regression.
     */
    private static Pipeline createGradientBoostingPipeline() {
        GBTRegressor gbt = new GBTRegressor()
                .setLabelCol("label")
                .setFeaturesCol("features")
                .setMaxIter(100)
                .setMaxDepth(5)
                .setSeed(42);
        
        return new Pipeline().setStages(new PipelineStage[]{gbt});
    }

    /**
     * Creates a pipeline for Linear Regression.
     */
    private static Pipeline createLinearRegressionPipeline() {
        LinearRegression lr = new LinearRegression()
                .setLabelCol("label")
                .setFeaturesCol("features")
                .setMaxIter(100)
                .setRegParam(0.3)
                .setElasticNetParam(0.8);
        
        return new Pipeline().setStages(new PipelineStage[]{lr});
    }

    /**
     * Evaluates the model on test data.
     */
    private static void evaluateModel(PipelineModel model, Dataset<Row> testData) {
        // Make predictions
        Dataset<Row> predictions = model.transform(testData);
        
        // Select example rows to display
        predictions.select("prediction", "label", "features").show(5);
        
        // Evaluate model
        RegressionEvaluator evaluator = new RegressionEvaluator()
                .setLabelCol("label")
                .setPredictionCol("prediction")
                .setMetricName("rmse");
        
        double rmse = evaluator.evaluate(predictions);
        System.out.println("Root Mean Squared Error (RMSE) on test data = " + rmse);
        
        evaluator.setMetricName("r2");
        double r2 = evaluator.evaluate(predictions);
        System.out.println("R2 on test data = " + r2);
    }
}