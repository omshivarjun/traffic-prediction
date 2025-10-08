'use client';

import { useEffect, useState } from 'react';

interface ModelMetadata {
  r2_score: number;
  rmse: number;
  mae: number;
  training_samples: number;
  test_samples: number;
  total_features: number;
  algorithm: string;
  model_configuration: {
    max_depth: number;
    max_iter: number;
    step_size: number;
    feature_subset_strategy: string;
    min_instances_per_node: number;
  };
  model_path: string;
  trained_at: string;
  verified_at: string;
  performance_category: string;
  pipeline_stages: string[];
}

interface Prediction {
  sensor_id: number;
  location: string;
  latitude: number;
  longitude: number;
  actual_speed: number;
  predicted_speed: number;
  prediction_error: number;
  confidence: number;
  speed_category: string;
  congestion_level: string;
}

interface FeatureImportance {
  feature: string;
  importance: number;
  rank: number;
}

interface ModelResults {
  model: ModelMetadata;
  predictions: Prediction[];
  feature_importance: FeatureImportance[];
  summary: {
    total_predictions: number;
    avg_prediction_error: number;
    max_confidence: number;
    min_confidence: number;
  };
}

export default function MLModelDashboard() {
  const [results, setResults] = useState<ModelResults | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchModelResults();
  }, []);

  const fetchModelResults = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/model-results');
      const data = await response.json();
      
      if (data.success) {
        setResults(data);
        setError(null);
      } else {
        setError(data.error || 'Failed to fetch model results');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-400 mx-auto"></div>
          <p className="mt-4 text-blue-300 text-lg">Loading ML Model Results...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gradient-to-br from-slate-900 via-red-900 to-slate-900">
        <div className="bg-red-500/10 border border-red-500 rounded-lg p-8 max-w-md">
          <h2 className="text-2xl font-bold text-red-400 mb-4">❌ Error</h2>
          <p className="text-red-300">{error}</p>
          <button
            onClick={fetchModelResults}
            className="mt-4 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!results) return null;

  const { model, predictions, feature_importance, summary } = results;

  // Calculate performance grade
  const getPerformanceGrade = (r2: number) => {
    if (r2 >= 0.995) return { grade: 'A+', color: 'text-green-400', bg: 'bg-green-500/20' };
    if (r2 >= 0.99) return { grade: 'A', color: 'text-green-400', bg: 'bg-green-500/20' };
    if (r2 >= 0.98) return { grade: 'B+', color: 'text-blue-400', bg: 'bg-blue-500/20' };
    if (r2 >= 0.95) return { grade: 'B', color: 'text-blue-400', bg: 'bg-blue-500/20' };
    return { grade: 'C', color: 'text-yellow-400', bg: 'bg-yellow-500/20' };
  };

  const performanceGrade = getPerformanceGrade(model.r2_score);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-blue-900 to-slate-900 p-8">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8 text-center">
          <h1 className="text-5xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400 mb-4">
            🎯 ML Model Dashboard
          </h1>
          <p className="text-blue-300 text-xl">
            Traffic Speed Prediction System - METR-LA Dataset
          </p>
          <div className="mt-4 inline-flex items-center gap-2 px-6 py-3 bg-green-500/20 border border-green-500 rounded-full">
            <span className="text-3xl">✅</span>
            <span className="text-green-300 font-semibold text-lg">Model Deployed & Verified</span>
          </div>
        </div>

        {/* Performance Overview */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          {/* R² Score */}
          <div className={`${performanceGrade.bg} border ${performanceGrade.color.replace('text', 'border')} rounded-xl p-6`}>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-gray-400 text-sm font-medium">R² Score</h3>
              <span className={`text-2xl font-bold ${performanceGrade.color}`}>{performanceGrade.grade}</span>
            </div>
            <p className={`text-4xl font-bold ${performanceGrade.color}`}>
              {(model.r2_score * 100).toFixed(2)}%
            </p>
            <p className="text-gray-400 text-xs mt-2">
              Variance explained (Target: 99.96%)
            </p>
          </div>

          {/* RMSE */}
          <div className="bg-blue-500/10 border border-blue-500 rounded-xl p-6">
            <h3 className="text-gray-400 text-sm font-medium mb-2">RMSE</h3>
            <p className="text-4xl font-bold text-blue-400">
              {model.rmse.toFixed(2)}
            </p>
            <p className="text-gray-400 text-xs mt-2">mph error</p>
          </div>

          {/* MAE */}
          <div className="bg-purple-500/10 border border-purple-500 rounded-xl p-6">
            <h3 className="text-gray-400 text-sm font-medium mb-2">MAE</h3>
            <p className="text-4xl font-bold text-purple-400">
              {model.mae.toFixed(2)}
            </p>
            <p className="text-gray-400 text-xs mt-2">mph avg error</p>
          </div>

          {/* Confidence */}
          <div className="bg-emerald-500/10 border border-emerald-500 rounded-xl p-6">
            <h3 className="text-gray-400 text-sm font-medium mb-2">Avg Confidence</h3>
            <p className="text-4xl font-bold text-emerald-400">
              {((summary.max_confidence + summary.min_confidence) / 2 * 100).toFixed(1)}%
            </p>
            <p className="text-gray-400 text-xs mt-2">prediction confidence</p>
          </div>
        </div>

        {/* Model Details */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* Model Configuration */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h2 className="text-2xl font-bold text-blue-400 mb-4 flex items-center gap-2">
              <span>⚙️</span> Model Configuration
            </h2>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-400">Algorithm:</span>
                <span className="text-white font-semibold">{model.algorithm}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Training Samples:</span>
                <span className="text-white font-semibold">{model.training_samples.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Test Samples:</span>
                <span className="text-white font-semibold">{model.test_samples.toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Features:</span>
                <span className="text-white font-semibold">{model.total_features}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Max Depth:</span>
                <span className="text-white font-semibold">{model.model_configuration.max_depth}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Iterations:</span>
                <span className="text-white font-semibold">{model.model_configuration.max_iter}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Step Size:</span>
                <span className="text-white font-semibold">{model.model_configuration.step_size}</span>
              </div>
            </div>
          </div>

          {/* Pipeline Stages */}
          <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
            <h2 className="text-2xl font-bold text-purple-400 mb-4 flex items-center gap-2">
              <span>🔄</span> Pipeline Stages
            </h2>
            <div className="space-y-4">
              {model.pipeline_stages.map((stage, index) => (
                <div key={index} className="flex items-start gap-4">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-purple-500/20 border border-purple-500 flex items-center justify-center">
                    <span className="text-purple-400 font-bold">{index + 1}</span>
                  </div>
                  <div className="flex-1">
                    <p className="text-white font-medium">{stage}</p>
                  </div>
                </div>
              ))}
              <div className="mt-4 pt-4 border-t border-slate-700">
                <div className="text-xs text-gray-400">
                  <p>📍 Model Location:</p>
                  <p className="text-gray-500 mt-1 font-mono text-[10px] break-all">
                    {model.model_path}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Feature Importance */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6 mb-8">
          <h2 className="text-2xl font-bold text-emerald-400 mb-6 flex items-center gap-2">
            <span>📊</span> Top Features by Importance
          </h2>
          <div className="space-y-3">
            {feature_importance.map((feature) => (
              <div key={feature.rank} className="flex items-center gap-4">
                <div className="w-8 h-8 rounded-full bg-emerald-500/20 border border-emerald-500 flex items-center justify-center flex-shrink-0">
                  <span className="text-emerald-400 font-bold text-sm">{feature.rank}</span>
                </div>
                <div className="flex-1">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-white font-medium">{feature.feature}</span>
                    <span className="text-emerald-400 font-semibold">
                      {(feature.importance * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="w-full bg-slate-700 rounded-full h-2">
                    <div
                      className="bg-gradient-to-r from-emerald-500 to-blue-500 h-2 rounded-full transition-all duration-500"
                      style={{ width: `${feature.importance * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Sample Predictions */}
        <div className="bg-slate-800/50 border border-slate-700 rounded-xl p-6">
          <h2 className="text-2xl font-bold text-blue-400 mb-6 flex items-center gap-2">
            <span>🚗</span> Sample Predictions
          </h2>
          <div className="space-y-4">
            {predictions.map((pred) => (
              <div
                key={pred.sensor_id}
                className="bg-slate-900/50 border border-slate-600 rounded-lg p-5"
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="text-white font-bold text-lg">{pred.location}</h3>
                    <p className="text-gray-400 text-sm">Sensor ID: {pred.sensor_id}</p>
                  </div>
                  <div className={`px-3 py-1 rounded-full text-xs font-semibold ${
                    pred.congestion_level === 'none' ? 'bg-green-500/20 text-green-400 border border-green-500' :
                    pred.congestion_level === 'light' ? 'bg-blue-500/20 text-blue-400 border border-blue-500' :
                    pred.congestion_level === 'moderate' ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500' :
                    'bg-red-500/20 text-red-400 border border-red-500'
                  }`}>
                    {pred.congestion_level.toUpperCase()}
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <p className="text-gray-400 text-xs mb-1">Actual Speed</p>
                    <p className="text-white text-2xl font-bold">{pred.actual_speed.toFixed(1)}</p>
                    <p className="text-gray-500 text-xs">mph</p>
                  </div>
                  <div>
                    <p className="text-gray-400 text-xs mb-1">Predicted Speed</p>
                    <p className="text-blue-400 text-2xl font-bold">{pred.predicted_speed.toFixed(1)}</p>
                    <p className="text-gray-500 text-xs">mph</p>
                  </div>
                  <div>
                    <p className="text-gray-400 text-xs mb-1">Error</p>
                    <p className={`text-2xl font-bold ${Math.abs(pred.prediction_error) < 1 ? 'text-green-400' : 'text-yellow-400'}`}>
                      {Math.abs(pred.prediction_error).toFixed(1)}
                    </p>
                    <p className="text-gray-500 text-xs">mph</p>
                  </div>
                  <div>
                    <p className="text-gray-400 text-xs mb-1">Confidence</p>
                    <p className="text-emerald-400 text-2xl font-bold">
                      {(pred.confidence * 100).toFixed(0)}%
                    </p>
                    <p className="text-gray-500 text-xs">accuracy</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer Stats */}
        <div className="mt-8 text-center">
          <div className="inline-flex items-center gap-8 px-8 py-4 bg-slate-800/50 border border-slate-700 rounded-xl">
            <div>
              <p className="text-gray-400 text-sm">Total Predictions</p>
              <p className="text-white text-2xl font-bold">{summary.total_predictions}</p>
            </div>
            <div className="h-12 w-px bg-slate-700"></div>
            <div>
              <p className="text-gray-400 text-sm">Avg Error</p>
              <p className="text-blue-400 text-2xl font-bold">{summary.avg_prediction_error.toFixed(2)} mph</p>
            </div>
            <div className="h-12 w-px bg-slate-700"></div>
            <div>
              <p className="text-gray-400 text-sm">Status</p>
              <p className="text-green-400 text-2xl font-bold">{model.performance_category}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
