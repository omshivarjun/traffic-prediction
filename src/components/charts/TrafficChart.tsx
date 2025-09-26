"use client";

import React from 'react';

interface TrafficChartProps {
  data: any[];
  type: 'volume' | 'speed' | 'congestion';
  title?: string;
  height?: number;
}

export default function TrafficChart({
  data,
  type,
  title = 'Traffic Data',
  height = 300,
}: TrafficChartProps) {
  return (
    <div className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow">
      <h3 className="text-lg font-semibold mb-4">{title}</h3>
      <div className="flex items-center justify-center" style={{ height }}>
        <div className="text-center">
          <div className="text-4xl mb-2"></div>
          <p className="text-gray-600">
            {type.charAt(0).toUpperCase() + type.slice(1)} Chart
          </p>
          <p className="text-sm text-gray-500 mt-2">
            {data?.length || 0} data points
          </p>
        </div>
      </div>
    </div>
  );
}
