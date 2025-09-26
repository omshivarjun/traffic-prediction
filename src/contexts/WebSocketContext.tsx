'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';

interface WebSocketContextType {
  trafficEvents: any[];
  trafficAggregates: any[];
  trafficPredictions: any[];
  isConnected: boolean;
  connectionError: string | null;
}

const WebSocketContext = createContext<WebSocketContextType>({
  trafficEvents: [],
  trafficAggregates: [],
  trafficPredictions: [],
  isConnected: false,
  connectionError: null
});

export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<WebSocketContextType>({
    trafficEvents: [],
    trafficAggregates: [],
    trafficPredictions: [],
    isConnected: false,
    connectionError: null
  });

  useEffect(() => {
    // Mock data for development
    setState(prev => ({
      ...prev,
      trafficEvents: [
        { event_id: '1', segment_id: 'seg-1', volume: 1200, speed: 45, timestamp: new Date() },
        { event_id: '2', segment_id: 'seg-2', volume: 800, speed: 55, timestamp: new Date() }
      ],
      isConnected: true
    }));
  }, []);

  return (
    <WebSocketContext.Provider value={state}>
      {children}
    </WebSocketContext.Provider>
  );
}

export const useWebSocket = () => useContext(WebSocketContext);
