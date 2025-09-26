package com.trafficprediction.batch.feature;

import java.io.IOException;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.conf.Configured;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Job;
import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
import org.apache.hadoop.mapreduce.lib.input.TextInputFormat;
import org.apache.hadoop.mapreduce.lib.output.FileOutputFormat;
import org.apache.hadoop.mapreduce.lib.output.TextOutputFormat;
import org.apache.hadoop.util.Tool;
import org.apache.hadoop.util.ToolRunner;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * MapReduce job for extracting features from historical traffic data.
 * This job processes raw traffic event data and extracts relevant features
 * for model training, such as traffic volume, average speed, and congestion levels
 * aggregated by location and time windows.
 */
public class FeatureExtractionJob extends Configured implements Tool {
    private static final Logger logger = LoggerFactory.getLogger(FeatureExtractionJob.class);

    public static void main(String[] args) throws Exception {
        int exitCode = ToolRunner.run(new Configuration(), new FeatureExtractionJob(), args);
        System.exit(exitCode);
    }

    @Override
    public int run(String[] args) throws Exception {
        if (args.length != 2) {
            System.err.println("Usage: FeatureExtractionJob <input path> <output path>");
            return -1;
        }

        String inputPath = args[0];
        String outputPath = args[1];

        Configuration conf = getConf();
        // Set any additional configuration parameters
        conf.set("mapreduce.job.queuename", "default");
        
        // Configure time window for aggregation (in minutes)
        conf.setInt("feature.extraction.time.window", 15);

        Job job = Job.getInstance(conf, "Traffic Feature Extraction");
        job.setJarByClass(FeatureExtractionJob.class);

        // Set mapper and reducer classes
        job.setMapperClass(FeatureExtractionMapper.class);
        job.setReducerClass(FeatureExtractionReducer.class);

        // Set combiner for local aggregation to improve performance
        job.setCombinerClass(FeatureExtractionReducer.class);

        // Define input/output formats
        job.setInputFormatClass(TextInputFormat.class);
        job.setOutputFormatClass(TextOutputFormat.class);

        // Define output key/value types
        job.setOutputKeyClass(Text.class);  // LocationTimeKey
        job.setOutputValueClass(Text.class); // FeatureVector

        // Set input and output paths
        FileInputFormat.addInputPath(job, new Path(inputPath));
        FileOutputFormat.setOutputPath(job, new Path(outputPath));

        logger.info("Starting feature extraction job with input: {} and output: {}", inputPath, outputPath);
        
        boolean success = job.waitForCompletion(true);
        return success ? 0 : 1;
    }
}