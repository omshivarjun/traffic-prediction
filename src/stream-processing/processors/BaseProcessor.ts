import { KafkaStreams, KStream } from 'kafka-streams';

/**
 * Base class for all stream processors
 */
export abstract class BaseProcessor {
  protected kafkaStreams: KafkaStreams;
  protected config: Record<string, string>;
  protected streams: KStream[] = [];
  
  /**
   * Constructor for BaseProcessor
   * @param kafkaStreams KafkaStreams instance
   * @param config Configuration object
   */
  constructor(kafkaStreams: KafkaStreams, config: Record<string, string>) {
    this.kafkaStreams = kafkaStreams;
    this.config = config;
  }
  
  /**
   * Start the processor
   */
  public async start(): Promise<void> {
    try {
      // Build the topology
      await this.buildTopology();
      
      // Start all streams
      for (const stream of this.streams) {
        await stream.start();
      }
      
      console.log(`${this.constructor.name} started successfully`);
    } catch (error) {
      console.error(`Error starting ${this.constructor.name}:`, error);
      throw error;
    }
  }
  
  /**
   * Stop the processor
   */
  public async stop(): Promise<void> {
    try {
      // Stop all streams
      for (const stream of this.streams) {
        await stream.close();
      }
      
      console.log(`${this.constructor.name} stopped successfully`);
    } catch (error) {
      console.error(`Error stopping ${this.constructor.name}:`, error);
      throw error;
    }
  }
  
  /**
   * Build the processing topology
   * This method should be implemented by subclasses
   */
  protected abstract buildTopology(): Promise<void>;
  
  /**
   * Get a topic name from configuration
   * @param key Configuration key for the topic
   * @returns Topic name
   */
  protected getTopic(key: string): string {
    const topic = this.config[key];
    if (!topic) {
      throw new Error(`Topic configuration not found for key: ${key}`);
    }
    return topic;
  }
  
  /**
   * Create a consumer stream for a topic
   * @param topicKey Configuration key for the topic
   * @param streamName Name of the stream
   * @returns KStream instance
   */
  protected createConsumerStream(topicKey: string, streamName: string): KStream {
    const topic = this.getTopic(topicKey);
    const stream = this.kafkaStreams.getKStream(topic);
    stream.setName(streamName);
    this.streams.push(stream);
    return stream;
  }
  
  /**
   * Create a producer stream for a topic
   * @param topicKey Configuration key for the topic
   * @param streamName Name of the stream
   * @returns KStream instance
   */
  protected createProducerStream(topicKey: string, streamName: string): KStream {
    const topic = this.getTopic(topicKey);
    const stream = this.kafkaStreams.getKStream(null);
    stream.setName(streamName);
    stream.to(topic);
    this.streams.push(stream);
    return stream;
  }
}