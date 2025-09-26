package com.trafficprediction.batch.feature;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Reducer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Reducer for feature extraction from traffic data.
 * 
 * Input:
 * Key: location_id_timewindow (e.g., "L123_20230415_1430")
 * Values: List of [speed,volume,congestion_level]
 * 
 * Output:
 * Key: location_id_timewindow
 * Value: avg_speed,total_volume,max_congestion,min_speed,speed_variance,count
 */
public class FeatureExtractionReducer extends Reducer<Text, Text, Text, Text> {
    private static final Logger logger = LoggerFactory.getLogger(FeatureExtractionReducer.class);
    private Text outputValue = new Text();
    
    @Override
    public void reduce(Text key, Iterable<Text> values, Context context) throws IOException, InterruptedException {
        double totalSpeed = 0.0;
        double totalVolume = 0.0;
        int maxCongestion = 0;
        double minSpeed = Double.MAX_VALUE;
        List<Double> speeds = new ArrayList<>();
        int count = 0;
        
        // Process all values for this key (location and time window)
        for (Text value : values) {
            String[] fields = value.toString().split(",");
            if (fields.length >= 3) {
                try {
                    double speed = Double.parseDouble(fields[0]);
                    double volume = Double.parseDouble(fields[1]);
                    int congestion = Integer.parseInt(fields[2]);
                    
                    // Accumulate values
                    totalSpeed += speed;
                    totalVolume += volume;
                    maxCongestion = Math.max(maxCongestion, congestion);
                    minSpeed = Math.min(minSpeed, speed);
                    speeds.add(speed);
                    count++;
                } catch (NumberFormatException e) {
                    logger.warn("Invalid numeric value in record: {}", value.toString());
                }
            }
        }
        
        // Calculate aggregate features
        if (count > 0) {
            double avgSpeed = totalSpeed / count;
            double speedVariance = calculateVariance(speeds, avgSpeed);
            
            // If no valid speed was found, set minSpeed to 0
            if (minSpeed == Double.MAX_VALUE) {
                minSpeed = 0.0;
            }
            
            // Format output: avg_speed,total_volume,max_congestion,min_speed,speed_variance,count
            String outputString = String.format("%.2f,%.0f,%d,%.2f,%.2f,%d", 
                    avgSpeed, totalVolume, maxCongestion, minSpeed, speedVariance, count);
            
            outputValue.set(outputString);
            context.write(key, outputValue);
        }
    }
    
    /**
     * Calculates the variance of a list of speed values.
     */
    private double calculateVariance(List<Double> speeds, double mean) {
        if (speeds.size() <= 1) {
            return 0.0;
        }
        
        double sumSquaredDiff = 0.0;
        for (Double speed : speeds) {
            double diff = speed - mean;
            sumSquaredDiff += diff * diff;
        }
        
        return sumSquaredDiff / (speeds.size() - 1);
    }
}