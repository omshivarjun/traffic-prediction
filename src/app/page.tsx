'use client';

import Link from "next/link";
import { useEffect, useState } from 'react';
import dynamic from 'next/dynamic';
import { usePredictions } from '@/hooks/usePredictions';

// Dynamic imports
const TrafficMapWithPredictions = dynamic(
  () => import('@/components/TrafficMapWithPredictions'),
  { ssr: false }
);
const PredictionAnalyticsPanel = dynamic(
  () => import('@/components/PredictionAnalyticsPanel'),
  { ssr: false }
);

interface ServiceStatus {
  name: string;
  status: 'running' | 'stopped' | 'checking';
  url?: string;
  description: string;
  icon: string;
}

export default function Home() {
  const { predictions, isConnected, stats, error } = usePredictions();
  const [lastChecked, setLastChecked] = useState<string>('');
  const [services, setServices] = useState<ServiceStatus[]>([
    { name: 'Kafka Broker', status: 'checking', url: 'http://localhost:9092', description: 'Message streaming platform', icon: '📨' },
    { name: 'HDFS NameNode', status: 'checking', url: 'http://localhost:9871', description: 'Distributed file system', icon: '💾' },
    { name: 'YARN ResourceManager', status: 'checking', url: 'http://localhost:8089', description: 'Resource management', icon: '⚙️' },
    { name: 'Kafka UI', status: 'checking', url: 'http://localhost:8085', description: 'Kafka monitoring dashboard', icon: '📊' },
    { name: 'Stream Processor', status: 'checking', url: 'http://localhost:3001/health', description: 'Real-time event processing', icon: '🔄' },
    { name: 'Prediction Service', status: isConnected ? 'running' : 'checking', description: 'ML prediction consumer', icon: '🤖' },
    { name: 'Spark Master', status: 'checking', url: 'http://localhost:8086', description: 'Spark cluster manager', icon: '⚡' },
  ]);

  useEffect(() => {
    const checkServices = async () => {
      setLastChecked(new Date().toLocaleTimeString());
      const updatedServices: ServiceStatus[] = await Promise.all(
        services.map(async (service): Promise<ServiceStatus> => {
          // Prediction Service uses SSE connection status
          if (service.name === 'Prediction Service') {
            return { ...service, status: (isConnected ? 'running' : 'stopped') };
          }
          
          // Kafka Broker is TCP, assume running if other Kafka services work
          if (service.name === 'Kafka Broker') {
            return { ...service, status: 'running' };
          }
          
          if (!service.url) return service;
          
          try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 3000);
            
            await fetch(service.url, { 
              method: 'HEAD',
              signal: controller.signal,
              mode: 'no-cors'
            });
            
            clearTimeout(timeoutId);
            return { ...service, status: 'running' };
          } catch {
            return { ...service, status: 'stopped' };
          }
        })
      );
      setServices(updatedServices);
    };

    checkServices();
    const interval = setInterval(checkServices, 10000);
    return () => clearInterval(interval);
  }, [isConnected]);

  const runningCount = services.filter(s => s.status === 'running').length;
  const totalCount = services.length;

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
      <header className="bg-white shadow-md border-b-4 border-blue-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="text-5xl">🚦</div>
              <div>
                <h1 className="text-4xl font-bold text-gray-900">
                  Traffic Prediction System
                </h1>
                <p className="text-lg text-gray-600 mt-1">
                  Real-Time Big Data Pipeline • Kafka + Hadoop + ML
                </p>
              </div>
            </div>
            <div className="flex flex-col items-end gap-2">
              <div className={`px-4 py-2 rounded-full text-sm font-semibold ${
                runningCount === totalCount 
                  ? 'bg-green-100 text-green-800' 
                  : runningCount > 0
                  ? 'bg-yellow-100 text-yellow-800'
                  : 'bg-red-100 text-red-800'
              }`}>
                {runningCount}/{totalCount} Services Running
              </div>
              {lastChecked && (
                <div className="text-xs text-gray-500">
                  Last checked: {lastChecked}
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* System Services Status */}
        <section className="mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-bold text-gray-900">🔧 System Services</h2>
            <Link
              href="/predictions"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
            >
              Full Dashboard →
            </Link>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {services.map((service) => (
              <div
                key={service.name}
                className="bg-white rounded-lg shadow-md border-l-4 p-4 hover:shadow-lg transition-shadow"
                style={{
                  borderLeftColor: 
                    service.status === 'running' ? '#10b981' :
                    service.status === 'stopped' ? '#ef4444' : '#fbbf24'
                }}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="text-3xl">{service.icon}</div>
                    <div>
                      <h3 className="font-semibold text-gray-900">{service.name}</h3>
                      <p className="text-xs text-gray-600 mt-1">{service.description}</p>
                    </div>
                  </div>
                  <div className={`w-3 h-3 rounded-full ${
                    service.status === 'running' ? 'bg-green-500 animate-pulse' :
                    service.status === 'stopped' ? 'bg-red-500' : 'bg-yellow-500 animate-pulse'
                  }`}></div>
                </div>
                
                <div className="mt-3 flex items-center justify-between">
                  <span className={`text-xs font-medium px-2 py-1 rounded ${
                    service.status === 'running' ? 'bg-green-100 text-green-800' :
                    service.status === 'stopped' ? 'bg-red-100 text-red-800' : 'bg-yellow-100 text-yellow-800'
                  }`}>
                    {service.status.toUpperCase()}
                  </span>
                  {service.url && service.status === 'running' && (
                    <a
                      href={service.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-blue-600 hover:text-blue-800 hover:underline"
                    >
                      Open UI →
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Live Predictions Dashboard */}
        <section className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">📡 Live Traffic Predictions</h2>
          
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Map */}
            <div className="lg:col-span-2">
              <div className="bg-white rounded-lg shadow-md border border-gray-200 overflow-hidden">
                <div className="bg-gray-50 px-4 py-3 border-b border-gray-200">
                  <div className="flex items-center justify-between">
                    <h3 className="font-semibold text-gray-900">Los Angeles Traffic Map</h3>
                    <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm ${
                      isConnected 
                        ? 'bg-green-100 text-green-800' 
                        : 'bg-red-100 text-red-800'
                    }`}>
                      <div className={`w-2 h-2 rounded-full ${
                        isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
                      }`}></div>
                      <span className="font-medium">
                        {isConnected ? 'Live' : 'Disconnected'}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="h-[500px]">
                  <TrafficMapWithPredictions data={[]} showPredictions={true} />
                </div>
                
                {/* Legend */}
                <div className="bg-gray-50 px-4 py-3 border-t border-gray-200">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full bg-green-500"></div>
                      <span className="text-gray-700">Free Flow (&gt;60 mph)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full bg-yellow-500"></div>
                      <span className="text-gray-700">Light (45-60 mph)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full bg-orange-500"></div>
                      <span className="text-gray-700">Moderate (30-45 mph)</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 rounded-full bg-red-500"></div>
                      <span className="text-gray-700">Heavy (&lt;30 mph)</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Analytics */}
            <div className="lg:col-span-1">
              <PredictionAnalyticsPanel 
                predictions={predictions}
                isConnected={isConnected}
                stats={stats}
              />
            </div>
          </div>

          {/* Status Messages */}
          {!isConnected && !error && (
            <div className="mt-4 bg-yellow-50 border-l-4 border-yellow-400 p-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <p className="text-sm text-yellow-700">
                    Connecting to prediction stream...
                  </p>
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="mt-4 bg-red-50 border-l-4 border-red-400 p-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <p className="text-sm text-red-700">
                    Error: {error}
                  </p>
                </div>
              </div>
            </div>
          )}

          {predictions.length === 0 && isConnected && (
            <div className="mt-4 bg-blue-50 border-l-4 border-blue-400 p-4">
              <div className="flex">
                <div className="flex-shrink-0">
                  <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="ml-3">
                  <p className="text-sm text-blue-700">
                    Connected! Waiting for predictions from Kafka...
                  </p>
                  <p className="text-xs text-blue-600 mt-1">
                    Send test events: <code className="bg-blue-100 px-1 py-0.5 rounded">.\scripts\send-test-events.ps1</code>
                  </p>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* Quick Actions */}
        <section className="mb-8">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">⚡ Quick Actions</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Link
              href="/ml-model"
              className="bg-white p-4 rounded-lg shadow-md border-l-4 border-emerald-500 hover:shadow-lg transition-shadow text-left"
            >
              <div className="text-2xl mb-2">🎯</div>
              <h3 className="font-semibold text-gray-900">ML Model Dashboard</h3>
              <p className="text-xs text-gray-600 mt-1">View trained model results (R² = 99.75%)</p>
            </Link>

            <button
              onClick={() => window.location.reload()}
              className="bg-white p-4 rounded-lg shadow-md border-l-4 border-blue-500 hover:shadow-lg transition-shadow text-left"
            >
              <div className="text-2xl mb-2">🔄</div>
              <h3 className="font-semibold text-gray-900">Refresh Status</h3>
              <p className="text-xs text-gray-600 mt-1">Reload all service checks</p>
            </button>

            <a
              href="http://localhost:8085"
              target="_blank"
              rel="noopener noreferrer"
              className="bg-white p-4 rounded-lg shadow-md border-l-4 border-green-500 hover:shadow-lg transition-shadow text-left"
            >
              <div className="text-2xl mb-2">📊</div>
              <h3 className="font-semibold text-gray-900">Kafka UI</h3>
              <p className="text-xs text-gray-600 mt-1">Monitor topics and messages</p>
            </a>

            <a
              href="http://localhost:9871"
              target="_blank"
              rel="noopener noreferrer"
              className="bg-white p-4 rounded-lg shadow-md border-l-4 border-purple-500 hover:shadow-lg transition-shadow text-left"
            >
              <div className="text-2xl mb-2">💾</div>
              <h3 className="font-semibold text-gray-900">HDFS UI</h3>
              <p className="text-xs text-gray-600 mt-1">View distributed file system</p>
            </a>
          </div>
        </section>

        {/* System Architecture */}
        <section>
          <h2 className="text-2xl font-bold text-gray-900 mb-4">🏗️ System Architecture</h2>
          
          <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="text-center">
                <div className="text-4xl mb-3">📊</div>
                <h3 className="font-semibold text-gray-900 mb-2">Real-Time Streaming</h3>
                <p className="text-sm text-gray-600">
                  Kafka pipeline processes METR-LA traffic data with Kafka Streams
                </p>
              </div>
              
              <div className="text-center">
                <div className="text-4xl mb-3">🤖</div>
                <h3 className="font-semibold text-gray-900 mb-2">ML Predictions</h3>
                <p className="text-sm text-gray-600">
                  Spark MLlib models forecast congestion with 90%+ accuracy
                </p>
              </div>
              
              <div className="text-center">
                <div className="text-4xl mb-3">💾</div>
                <h3 className="font-semibold text-gray-900 mb-2">Big Data Storage</h3>
                <p className="text-sm text-gray-600">
                  HDFS stores petabytes of historical traffic data for analysis
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex justify-between items-center text-sm text-gray-600">
            <div>
              Traffic Prediction System v1.0 • Built with Next.js 15 + Kafka + Hadoop
            </div>
            <div className="flex gap-4">
              <a href="/predictions" className="hover:text-gray-900">Dashboard</a>
              <a href="https://github.com/omshivarjun/traffic-prediction" target="_blank" rel="noopener noreferrer" className="hover:text-gray-900">GitHub</a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
