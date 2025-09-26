import { NextResponse } from 'next/server';

interface SystemService {
  name: string;
  status: 'active' | 'inactive' | 'error' | 'starting';
  uptime?: string;
  last_check: string;
  health_details?: any;
}

interface SystemStatus {
  overall_status: 'healthy' | 'degraded' | 'down';
  services: SystemService[];
  timestamp: string;
  pipeline_status: {
    data_flow_active: boolean;
    last_prediction: string;
    predictions_per_minute: number;
  };
}

// Mock function to check service health - replace with real health checks
const checkServiceHealth = async (serviceName: string): Promise<SystemService> => {
  // TODO: Implement real health checks
  // Example: const health = await fetch(`http://localhost:8080/health/${serviceName}`);
  
  const mockHealthData = {
    kafka_producer: {
      status: 'active' as const,
      uptime: '2h 45m',
      health_details: {
        messages_sent: 1250,
        last_message: new Date(Date.now() - 30000).toISOString()
      }
    },
    spark_streaming: {
      status: 'active' as const,
      uptime: '2h 30m',
      health_details: {
        processed_records: 5430,
        processing_rate: '~25 records/sec'
      }
    },
    hdfs_storage: {
      status: 'active' as const,
      uptime: '3h 12m',
      health_details: {
        storage_used: '2.3GB',
        available_space: '45.7GB'
      }
    },
    ml_models: {
      status: 'active' as const,
      uptime: '1h 55m',
      health_details: {
        loaded_models: 4,
        last_training: new Date(Date.now() - 1800000).toISOString()
      }
    },
    prediction_service: {
      status: 'active' as const,
      uptime: '1h 45m',
      health_details: {
        predictions_generated: 890,
        avg_prediction_time: '45ms'
      }
    }
  };

  const serviceData = mockHealthData[serviceName as keyof typeof mockHealthData];
  
  return {
    name: serviceName,
    status: serviceData?.status || 'inactive',
    uptime: serviceData?.uptime,
    last_check: new Date().toISOString(),
    health_details: serviceData?.health_details
  };
};

export async function GET() {
  try {
    const services = [
      'kafka_producer',
      'spark_streaming', 
      'hdfs_storage',
      'ml_models',
      'prediction_service'
    ];

    // Check health of all services
    const servicePromises = services.map(service => checkServiceHealth(service));
    const serviceStatuses = await Promise.all(servicePromises);

    // Determine overall system status
    const activeServices = serviceStatuses.filter(s => s.status === 'active').length;
    const totalServices = serviceStatuses.length;
    
    let overallStatus: 'healthy' | 'degraded' | 'down';
    if (activeServices === totalServices) {
      overallStatus = 'healthy';
    } else if (activeServices > totalServices / 2) {
      overallStatus = 'degraded';
    } else {
      overallStatus = 'down';
    }

    // Mock pipeline status - replace with real metrics
    const pipelineStatus = {
      data_flow_active: activeServices >= 3, // Need at least Kafka, Spark, and HDFS
      last_prediction: new Date(Date.now() - Math.random() * 60000).toISOString(),
      predictions_per_minute: Math.floor(15 + Math.random() * 10) // Mock: 15-25 predictions/min
    };

    const systemStatus: SystemStatus = {
      overall_status: overallStatus,
      services: serviceStatuses,
      timestamp: new Date().toISOString(),
      pipeline_status: pipelineStatus
    };

    return NextResponse.json({
      success: true,
      data: systemStatus
    });

  } catch (error) {
    console.error('Error checking system status:', error);
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to check system status',
        data: {
          overall_status: 'down',
          services: [],
          timestamp: new Date().toISOString(),
          pipeline_status: {
            data_flow_active: false,
            last_prediction: '',
            predictions_per_minute: 0
          }
        }
      },
      { status: 500 }
    );
  }
}

// POST endpoint for services to report their status
export async function POST(request: Request) {
  try {
    const { service_name, status, health_details } = await request.json();
    
    // TODO: Store service status in database/cache
    // TODO: Update monitoring dashboard
    
    console.log(`Service ${service_name} reported status: ${status}`, health_details);
    
    return NextResponse.json({
      success: true,
      message: 'Status updated',
      timestamp: new Date().toISOString()
    });

  } catch (error) {
    console.error('Error updating service status:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to update status' },
      { status: 500 }
    );
  }
}