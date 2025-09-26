package com.trafficprediction.batch.feature;

import java.io.IOException;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.Calendar;
import java.util.Date;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Mapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Mapper for feature extraction from traffic data.
 * 
 * Input format (CSV):
 * timestamp,location_id,speed,volume,congestion_level
 * 
 * Output format:
 * Key: location_id_timewindow (e.g., "L123_20230415_1430")
 * Value: speed,volume,congestion_level
 */
public class FeatureExtractionMapper extends Mapper<LongWritable, Text, Text, Text> {
    private static final Logger logger = LoggerFactory.getLogger(FeatureExtractionMapper.class);
    private static final SimpleDateFormat INPUT_DATE_FORMAT = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
    private static final SimpleDateFormat OUTPUT_DATE_FORMAT = new SimpleDateFormat("yyyyMMdd_HHmm");
    
    private Text outputKey = new Text();
    private Text outputValue = new Text();
    private int timeWindowMinutes;
    
    @Override
    protected void setup(Context context) {
        Configuration conf = context.getConfiguration();
        timeWindowMinutes = conf.getInt("feature.extraction.time.window", 15);
        logger.info("Using time window of {} minutes for aggregation", timeWindowMinutes);
    }
    
    @Override
    public void map(LongWritable key, Text value, Context context) throws IOException, InterruptedException {
        // Skip header if present
        if (key.get() == 0 && value.toString().startsWith("timestamp")) {
            return;
        }
        
        String line = value.toString();
        String[] fields = line.split(",");
        
        if (fields.length < 5) {
            logger.warn("Invalid input record: {}", line);
            return;
        }
        
        try {
            // Parse input fields
            String timestamp = fields[0];
            String locationId = fields[1];
            String speed = fields[2];
            String volume = fields[3];
            String congestionLevel = fields[4];
            
            // Normalize timestamp to time window
            String timeWindow = normalizeTimestamp(timestamp);
            
            // Create composite key: location_id_timewindow
            String compositeKey = locationId + "_" + timeWindow;
            outputKey.set(compositeKey);
            
            // Create feature value
            String featureValue = speed + "," + volume + "," + congestionLevel;
            outputValue.set(featureValue);
            
            context.write(outputKey, outputValue);
            
        } catch (Exception e) {
            logger.error("Error processing record: {}", line, e);
        }
    }
    
    /**
     * Normalizes a timestamp to a time window.
     * For example, if time window is 15 minutes, 14:37 will be normalized to 14:30.
     */
    private String normalizeTimestamp(String timestamp) throws ParseException {
        Date date = INPUT_DATE_FORMAT.parse(timestamp);
        Calendar calendar = Calendar.getInstance();
        calendar.setTime(date);
        
        // Normalize minutes to the time window
        int minutes = calendar.get(Calendar.MINUTE);
        int normalizedMinutes = (minutes / timeWindowMinutes) * timeWindowMinutes;
        calendar.set(Calendar.MINUTE, normalizedMinutes);
        calendar.set(Calendar.SECOND, 0);
        calendar.set(Calendar.MILLISECOND, 0);
        
        return OUTPUT_DATE_FORMAT.format(calendar.getTime());
    }
}