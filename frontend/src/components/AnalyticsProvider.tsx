'use client';

import React, { useEffect, ReactNode, useRef, useState, createContext } from 'react';
import Analytics from '@/lib/analytics';

interface AnalyticsProviderProps {
  children: ReactNode;
}

interface AnalyticsContextType {
  isAnalyticsOptedIn: boolean;
  setIsAnalyticsOptedIn: (optedIn: boolean) => void;
}

export const AnalyticsContext = createContext<AnalyticsContextType>({
  isAnalyticsOptedIn: true,
  setIsAnalyticsOptedIn: () => { },
});

export default function AnalyticsProvider({ children }: AnalyticsProviderProps) {
  const [isAnalyticsOptedIn, setIsAnalyticsOptedIn] = useState(true);
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current) return;

    const initAnalytics = async () => {
      // Web Version: Use localStorage
      const savedOptIn = localStorage.getItem('analyticsOptedIn');
      const shouldOptIn = savedOptIn !== 'false'; // Default true

      setIsAnalyticsOptedIn(shouldOptIn);

      if (shouldOptIn) {
        initialized.current = true;
        // Basic init for web
        await Analytics.init();
        await Analytics.trackAppStarted();
      }
    };

    initAnalytics().catch(console.error);
  }, []);

  return <AnalyticsContext.Provider value={{ isAnalyticsOptedIn, setIsAnalyticsOptedIn }}>{children}</AnalyticsContext.Provider>;
} 