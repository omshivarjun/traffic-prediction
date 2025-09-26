'use client';

import { useState, useEffect } from 'react';

interface PredictionData {
  sensor_id: string;
  location: string;
  current_conditions: {
    speed: number;
    volume: number;
    congestion_level: string;
  };
  predictions: {
    next_15_min: string;
    next_30_min: string;
    next_60_min: string;
  };
  confidence: number;
}

interface TrafficAlert {
  id: string;
  type: string;
  location: string;
  severity: string;
  description: string;
  estimated_duration: string;
  recommended_actions: string[];
}

interface AnalyticsData {
  peak_hours: number[];
  congestion_patterns: {
    weekday_avg: number;
    weekend_avg: number;
  };
  improvement_suggestions: string[];
}

export default function CityPlannerDashboard() {
  const [predictions, setPredictions] = useState<PredictionData[]>([]);
  const [alerts, setAlerts] = useState<TrafficAlert[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [selectedTimeframe, setSelectedTimeframe] = useState<'15min' | '30min' | '60min'>('30min');
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'predictions' | 'alerts' | 'analytics'>('overview');

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true);
        
        // Mock data for demonstration - in real implementation, these would be API calls
        setPredictions([
          {
            sensor_id: '001',
            location: 'I-405 Northbound at Wilshire Blvd',
            current_conditions: { speed: 18.5, volume: 1850, congestion_level: 'severe' },
            predictions: { next_15_min: 'severe', next_30_min: 'heavy', next_60_min: 'moderate' },
            confidence: 0.94
          },
          {
            sensor_id: '002', 
            location: 'US-101 Downtown at 4th Street',
            current_conditions: { speed: 28.2, volume: 1420, congestion_level: 'heavy' },
            predictions: { next_15_min: 'heavy', next_30_min: 'moderate', next_60_min: 'light' },
            confidence: 0.87
          },
          {
            sensor_id: '003',
            location: 'I-10 Westbound at La Brea Ave',
            current_conditions: { speed: 42.1, volume: 980, congestion_level: 'moderate' },
            predictions: { next_15_min: 'moderate', next_30_min: 'light', next_60_min: 'free_flow' },
            confidence: 0.91
          }
        ]);

        setAlerts([
          {
            id: 'alert_001',
            type: 'Accident',
            location: 'I-405 Northbound Mile Marker 45',
            severity: 'high',
            description: 'Multi-vehicle accident blocking 2 lanes',
            estimated_duration: '45-60 minutes',
            recommended_actions: ['Deploy traffic control units', 'Activate alternate route signs', 'Issue traffic advisory']
          },
          {
            id: 'alert_002',
            type: 'Construction',
            location: 'US-101 Southbound between Exits 12-15',
            severity: 'medium',
            description: 'Scheduled lane closure for bridge maintenance',
            estimated_duration: '2-3 hours',
            recommended_actions: ['Monitor traffic flow', 'Adjust signal timing', 'Coordinate with construction crew']
          }
        ]);

        setAnalytics({
          peak_hours: [7, 8, 17, 18, 19],
          congestion_patterns: {
            weekday_avg: 65,
            weekend_avg: 35
          },
          improvement_suggestions: [
            'Implement adaptive signal control at major intersections',
            'Consider HOV lane expansion on I-405 corridor',
            'Deploy dynamic message signs for real-time route guidance',
            'Optimize signal timing during peak hours'
          ]
        });

      } catch (error) {
        console.error('Error fetching dashboard data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, []);

  const getSeverityColor = (level: string) => {
    switch (level) {
      case 'severe': return 'text-red-600 bg-red-100';
      case 'heavy': return 'text-orange-600 bg-orange-100';
      case 'moderate': return 'text-yellow-600 bg-yellow-100';
      case 'light': return 'text-green-600 bg-green-100';
      case 'free_flow': return 'text-blue-600 bg-blue-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const getAlertColor = (severity: string) => {
    switch (severity) {
      case 'high': return 'border-red-500 bg-red-50';
      case 'medium': return 'border-orange-500 bg-orange-50';
      case 'low': return 'border-yellow-500 bg-yellow-50';
      default: return 'border-gray-500 bg-gray-50';
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="animate-pulse">
            <div className="h-8 bg-gray-300 rounded mb-4"></div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-24 bg-gray-300 rounded"></div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">City Traffic Management Center</h1>
              <p className="text-lg text-gray-600 mt-1">Real-Time Congestion Prediction & Analytics</p>
            </div>
            <div className="flex items-center space-x-4">
              <div className="text-sm text-gray-500">
                Last Updated: {new Date().toLocaleTimeString()}
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-sm font-medium text-green-600">Live Data</span>
              </div>
            </div>
          </div>

          {/* Navigation Tabs */}
          <div className="mt-6 border-b border-gray-200">
            <nav className="-mb-px flex space-x-8">
              {[
                { id: 'overview', label: 'Overview', icon: '📊' },
                { id: 'predictions', label: 'Predictions', icon: '🔮' },
                { id: 'alerts', label: 'Active Alerts', icon: '🚨' },
                { id: 'analytics', label: 'Analytics', icon: '📈' }
              ].map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${
                    activeTab === tab.id
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <span>{tab.icon}</span>
                  <span>{tab.label}</span>
                  {tab.id === 'alerts' && alerts.length > 0 && (
                    <span className="bg-red-100 text-red-800 text-xs font-medium px-2 py-1 rounded-full">
                      {alerts.length}
                    </span>
                  )}
                </button>
              ))}
            </nav>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-8 py-6">
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Key Metrics */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-blue-500">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Network Status</p>
                    <p className="text-2xl font-bold text-blue-600">Operational</p>
                  </div>
                  <div className="text-3xl">🟢</div>
                </div>
              </div>

              <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-green-500">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Active Sensors</p>
                    <p className="text-2xl font-bold text-green-600">207</p>
                  </div>
                  <div className="text-3xl">📡</div>
                </div>
              </div>

              <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-orange-500">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Congested Areas</p>
                    <p className="text-2xl font-bold text-orange-600">{predictions.filter(p => p.current_conditions.congestion_level === 'severe' || p.current_conditions.congestion_level === 'heavy').length}</p>
                  </div>
                  <div className="text-3xl">🚗</div>
                </div>
              </div>

              <div className="bg-white p-6 rounded-lg shadow-md border-l-4 border-red-500">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-gray-600">Active Incidents</p>
                    <p className="text-2xl font-bold text-red-600">{alerts.length}</p>
                  </div>
                  <div className="text-3xl">⚠️</div>
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="bg-white p-6 rounded-lg shadow-md">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">Quick Actions</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <button className="p-4 bg-blue-50 hover:bg-blue-100 rounded-lg border border-blue-200 transition-colors text-left">
                  <div className="text-2xl mb-2">🚦</div>
                  <h4 className="font-semibold text-blue-800">Signal Control</h4>
                  <p className="text-sm text-blue-600">Adjust traffic signals</p>
                </button>

                <button className="p-4 bg-green-50 hover:bg-green-100 rounded-lg border border-green-200 transition-colors text-left">
                  <div className="text-2xl mb-2">📱</div>
                  <h4 className="font-semibold text-green-800">Send Advisory</h4>
                  <p className="text-sm text-green-600">Issue traffic alerts</p>
                </button>

                <button className="p-4 bg-yellow-50 hover:bg-yellow-100 rounded-lg border border-yellow-200 transition-colors text-left">
                  <div className="text-2xl mb-2">🛣️</div>
                  <h4 className="font-semibold text-yellow-800">Route Guidance</h4>
                  <p className="text-sm text-yellow-600">Update dynamic signs</p>
                </button>

                <button className="p-4 bg-purple-50 hover:bg-purple-100 rounded-lg border border-purple-200 transition-colors text-left">
                  <div className="text-2xl mb-2">📊</div>
                  <h4 className="font-semibold text-purple-800">Generate Report</h4>
                  <p className="text-sm text-purple-600">Create traffic report</p>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Predictions Tab */}
        {activeTab === 'predictions' && (
          <div className="space-y-6">
            <div className="bg-white p-6 rounded-lg shadow-md">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-800">Traffic Predictions</h3>
                <div className="flex items-center space-x-4">
                  <label className="text-sm text-gray-600">Prediction Horizon:</label>
                  <select
                    value={selectedTimeframe}
                    onChange={(e) => setSelectedTimeframe(e.target.value as any)}
                    className="border border-gray-300 rounded px-3 py-1 text-sm"
                  >
                    <option value="15min">15 Minutes</option>
                    <option value="30min">30 Minutes</option>
                    <option value="60min">60 Minutes</option>
                  </select>
                </div>
              </div>

              <div className="space-y-4">
                {predictions.map((prediction) => (
                  <div key={prediction.sensor_id} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h4 className="font-semibold text-gray-800">{prediction.location}</h4>
                        <p className="text-sm text-gray-600 mb-3">Sensor ID: {prediction.sensor_id}</p>
                        
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                          <div>
                            <p className="text-xs text-gray-500">Current Speed</p>
                            <p className="text-lg font-semibold">{prediction.current_conditions.speed} mph</p>
                          </div>
                          <div>
                            <p className="text-xs text-gray-500">Current Volume</p>
                            <p className="text-lg font-semibold">{prediction.current_conditions.volume} vph</p>
                          </div>
                          <div>
                            <p className="text-xs text-gray-500">Current Status</p>
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSeverityColor(prediction.current_conditions.congestion_level)}`}>
                              {prediction.current_conditions.congestion_level.toUpperCase()}
                            </span>
                          </div>
                          <div>
                            <p className="text-xs text-gray-500">Confidence</p>
                            <p className="text-lg font-semibold text-green-600">{(prediction.confidence * 100).toFixed(0)}%</p>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="mt-4 pt-4 border-t border-gray-100">
                      <h5 className="text-sm font-semibold text-gray-700 mb-2">Predictions</h5>
                      <div className="flex space-x-6">
                        <div className="text-center">
                          <p className="text-xs text-gray-500">15 min</p>
                          <span className={`px-3 py-1 rounded-full text-xs font-medium ${getSeverityColor(prediction.predictions.next_15_min)}`}>
                            {prediction.predictions.next_15_min.toUpperCase()}
                          </span>
                        </div>
                        <div className="text-center">
                          <p className="text-xs text-gray-500">30 min</p>
                          <span className={`px-3 py-1 rounded-full text-xs font-medium ${getSeverityColor(prediction.predictions.next_30_min)}`}>
                            {prediction.predictions.next_30_min.toUpperCase()}
                          </span>
                        </div>
                        <div className="text-center">
                          <p className="text-xs text-gray-500">60 min</p>
                          <span className={`px-3 py-1 rounded-full text-xs font-medium ${getSeverityColor(prediction.predictions.next_60_min)}`}>
                            {prediction.predictions.next_60_min.toUpperCase()}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Alerts Tab */}
        {activeTab === 'alerts' && (
          <div className="space-y-6">
            <div className="bg-white p-6 rounded-lg shadow-md">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">Active Traffic Alerts</h3>
              
              {alerts.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  <div className="text-4xl mb-4">✅</div>
                  <p>No active alerts. All traffic systems operating normally.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {alerts.map((alert) => (
                    <div key={alert.id} className={`border-l-4 p-4 rounded-lg ${getAlertColor(alert.severity)}`}>
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-2 mb-2">
                            <span className="text-lg">
                              {alert.type === 'Accident' ? '🚗💥' : alert.type === 'Construction' ? '🚧' : '⚠️'}
                            </span>
                            <h4 className="font-semibold text-gray-800">{alert.type}</h4>
                            <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                              alert.severity === 'high' ? 'bg-red-100 text-red-800' :
                              alert.severity === 'medium' ? 'bg-orange-100 text-orange-800' :
                              'bg-yellow-100 text-yellow-800'
                            }`}>
                              {alert.severity.toUpperCase()}
                            </span>
                          </div>
                          
                          <p className="text-sm font-medium text-gray-700 mb-1">{alert.location}</p>
                          <p className="text-sm text-gray-600 mb-3">{alert.description}</p>
                          
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div>
                              <p className="text-xs text-gray-500 mb-1">Estimated Duration</p>
                              <p className="text-sm font-medium">{alert.estimated_duration}</p>
                            </div>
                            <div>
                              <p className="text-xs text-gray-500 mb-1">Recommended Actions</p>
                              <ul className="text-sm space-y-1">
                                {alert.recommended_actions.map((action, index) => (
                                  <li key={index} className="flex items-start space-x-2">
                                    <span className="text-xs mt-1">•</span>
                                    <span>{action}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          </div>
                        </div>
                        
                        <button className="ml-4 px-4 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700">
                          Take Action
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Analytics Tab */}
        {activeTab === 'analytics' && analytics && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-white p-6 rounded-lg shadow-md">
                <h3 className="text-lg font-semibold text-gray-800 mb-4">Peak Traffic Hours</h3>
                <div className="space-y-3">
                  {Array.from({ length: 24 }, (_, i) => (
                    <div key={i} className="flex items-center space-x-3">
                      <span className="text-sm font-mono w-12">{i}:00</span>
                      <div className="flex-1 bg-gray-200 rounded-full h-6 relative">
                        <div
                          className={`h-6 rounded-full transition-all duration-300 ${
                            analytics.peak_hours.includes(i) ? 'bg-red-500' : 'bg-green-400'
                          }`}
                          style={{ width: `${analytics.peak_hours.includes(i) ? 90 : 20}%` }}
                        />
                        <span className="absolute inset-0 flex items-center justify-center text-xs font-medium text-white">
                          {analytics.peak_hours.includes(i) ? 'Peak' : 'Normal'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-white p-6 rounded-lg shadow-md">
                <h3 className="text-lg font-semibold text-gray-800 mb-4">Congestion Patterns</h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-blue-50 rounded-lg">
                    <div>
                      <p className="font-medium text-blue-800">Weekday Average</p>
                      <p className="text-sm text-blue-600">Monday - Friday</p>
                    </div>
                    <div className="text-2xl font-bold text-blue-600">
                      {analytics.congestion_patterns.weekday_avg}%
                    </div>
                  </div>
                  
                  <div className="flex items-center justify-between p-4 bg-green-50 rounded-lg">
                    <div>
                      <p className="font-medium text-green-800">Weekend Average</p>
                      <p className="text-sm text-green-600">Saturday - Sunday</p>
                    </div>
                    <div className="text-2xl font-bold text-green-600">
                      {analytics.congestion_patterns.weekend_avg}%
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white p-6 rounded-lg shadow-md">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">AI-Powered Improvement Suggestions</h3>
              <div className="space-y-3">
                {analytics.improvement_suggestions.map((suggestion, index) => (
                  <div key={index} className="flex items-start space-x-3 p-3 bg-gray-50 rounded-lg">
                    <div className="text-blue-600 font-bold text-lg">{index + 1}</div>
                    <div className="flex-1">
                      <p className="text-gray-800">{suggestion}</p>
                    </div>
                    <button className="px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700">
                      Review
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}