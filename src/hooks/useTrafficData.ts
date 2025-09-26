'use client';

import { useState, useCallback } from 'react';

export function useTrafficData() {
  const [loading, setLoading] = useState(false);

  const refreshData = useCallback(async () => {
    setLoading(true);
    // Mock refresh
    await new Promise(resolve => setTimeout(resolve, 1000));
    setLoading(false);
  }, []);

  return {
    loading,
    refreshData
  };
}
