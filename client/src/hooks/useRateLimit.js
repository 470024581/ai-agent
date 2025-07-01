import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';

/**
 * Rate limiting hook for controlling API access frequency
 * @param {string} key - Key for localStorage
 * @param {number} maxClicks - Maximum clicks allowed per hour
 * @param {number} windowMs - Time window in milliseconds, defaults to 1 hour
 */
const useRateLimit = (key = 'analysis_clicks', maxClicks = 10, windowMs = 60 * 60 * 1000) => {
  const { t } = useTranslation();
  const [isLimited, setIsLimited] = useState(false);
  const [remainingClicks, setRemainingClicks] = useState(maxClicks);
  const [nextResetTime, setNextResetTime] = useState(null);

  // Clean up expired clicks
  const cleanupExpiredClicks = useCallback((clicks) => {
    const now = Date.now();
    return clicks.filter(timestamp => now - timestamp < windowMs);
  }, [windowMs]);

  // Check current rate limit status
  const checkStatus = useCallback(() => {
    try {
      const storedClicks = localStorage.getItem(key);
      const clicks = storedClicks ? JSON.parse(storedClicks) : [];
      
      // Clean up expired data
      const validClicks = cleanupExpiredClicks(clicks);
      
      // Update localStorage (remove expired data)
      if (validClicks.length !== clicks.length) {
        localStorage.setItem(key, JSON.stringify(validClicks));
      }
      
      const remaining = Math.max(0, maxClicks - validClicks.length);
      const limited = validClicks.length >= maxClicks;
      
      setRemainingClicks(remaining);
      setIsLimited(limited);
      
      // Calculate next reset time (earliest click time + window)
      if (validClicks.length > 0) {
        const earliestClick = Math.min(...validClicks);
        setNextResetTime(earliestClick + windowMs);
      } else {
        setNextResetTime(null);
      }
      
      return {
        isLimited: limited,
        remainingClicks: remaining,
        totalClicks: validClicks.length,
        nextResetTime: validClicks.length > 0 ? earliestClick + windowMs : null
      };
    } catch (error) {
      console.error('Error checking rate limit status:', error);
      return {
        isLimited: false,
        remainingClicks: maxClicks,
        totalClicks: 0,
        nextResetTime: null
      };
    }
  }, [key, maxClicks, windowMs, cleanupExpiredClicks]);

  // Record a click attempt
  const recordClick = useCallback(() => {
    try {
      const now = Date.now();
      const storedClicks = localStorage.getItem(key);
      const clicks = storedClicks ? JSON.parse(storedClicks) : [];
      
      // Clean up expired data
      const validClicks = cleanupExpiredClicks(clicks);
      
      // Check if limit exceeded
      if (validClicks.length >= maxClicks) {
        return false; // Limit exceeded, reject recording
      }
      
      // Add new click record
      validClicks.push(now);
      localStorage.setItem(key, JSON.stringify(validClicks));
      
      // Update status
      checkStatus();
      
      return true; // Successfully recorded
    } catch (error) {
      console.error('Error recording click:', error);
      return false;
    }
  }, [key, maxClicks, cleanupExpiredClicks, checkStatus]);

  // Reset all records (for debugging or admin functions only)
  const resetClicks = useCallback(() => {
    try {
      localStorage.removeItem(key);
      setIsLimited(false);
      setRemainingClicks(maxClicks);
      setNextResetTime(null);
    } catch (error) {
      console.error('Error resetting clicks:', error);
    }
  }, [key, maxClicks]);

  // Get friendly time display
  const getTimeUntilReset = useCallback(() => {
    if (!nextResetTime) return null;
    
    const now = Date.now();
    const diff = nextResetTime - now;
    
    if (diff <= 0) {
      // Time expired, trigger status check
      setTimeout(checkStatus, 100);
      return null;
    }
    
    const hours = Math.floor(diff / (60 * 60 * 1000));
    const minutes = Math.floor((diff % (60 * 60 * 1000)) / (60 * 1000));
    
    const timeFormat = {
      zh: {
        hours: '小时',
        minutes: '分钟',
        format: (h, m) => h > 0 ? `${h}${timeFormat.zh.hours}${m}${timeFormat.zh.minutes}` : `${m}${timeFormat.zh.minutes}`
      },
      en: {
        hours: 'h',
        minutes: 'm',
        format: (h, m) => h > 0 ? `${h}${timeFormat.en.hours} ${m}${timeFormat.en.minutes}` : `${m}${timeFormat.en.minutes}`
      }
    };

    const currentLang = localStorage.getItem('i18nextLng')?.split('-')[0] || 'en';
    return timeFormat[currentLang]?.format(hours, minutes) || timeFormat.en.format(hours, minutes);
  }, [nextResetTime, checkStatus, t]);

  // Check status on component mount
  useEffect(() => {
    checkStatus();
  }, [checkStatus]);

  // Periodically check status (every minute)
  useEffect(() => {
    const interval = setInterval(() => {
      checkStatus();
    }, 60 * 1000);

    return () => clearInterval(interval);
  }, [checkStatus]);

  return {
    isLimited,           // Whether rate limited
    remainingClicks,     // Remaining click count
    recordClick,         // Function to record click
    resetClicks,         // Reset function (for debugging)
    checkStatus,         // Manual status check
    nextResetTime,       // Next reset timestamp
    getTimeUntilReset,   // Get time until reset
    maxClicks,           // Maximum clicks allowed
    windowMs             // Time window
  };
};

export default useRateLimit; 