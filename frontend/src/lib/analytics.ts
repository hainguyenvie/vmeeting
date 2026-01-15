// Web version of Analytics - removes Tauri dependencies and uses local storage/console logging

export interface AnalyticsProperties {
  [key: string]: string;
}

export interface DeviceInfo {
  platform: string;
  os_version: string;
  architecture: string;
}

export interface UserSession {
  session_id: string;
  user_id: string;
  start_time: string;
  last_heartbeat: string;
  is_active: boolean;
}

export default class Analytics {
  private static initialized = false;
  private static currentUserId: string | null = null;
  private static initializationPromise: Promise<void> | null = null;
  private static sessionStartTime: number | null = null;
  private static meetingsInSession: number = 0;
  private static deviceInfo: DeviceInfo | null = null;

  static async init(): Promise<void> {
    if (this.initialized) return;
    this.initialized = true;
    console.log('[Web Analytics] Analytics initialized successfully');
  }

  static async disable(): Promise<void> {
    this.initialized = false;
    this.currentUserId = null;
    console.log('[Web Analytics] Analytics disabled successfully');
  }

  static async isEnabled(): Promise<boolean> {
    return true; // Always enabled for now in web preview
  }

  static async track(eventName: string, properties?: AnalyticsProperties): Promise<void> {
    if (!this.initialized) {
      console.warn('[Web Analytics] Analytics not initialized');
      return;
    }
    console.log(`[Web Analytics] Tracking event: ${eventName}`, properties);
  }

  static async identify(userId: string, properties?: AnalyticsProperties): Promise<void> {
    if (!this.initialized) return;
    this.currentUserId = userId;
    console.log(`[Web Analytics] Identify user: ${userId}`, properties);
  }

  // Enhanced user tracking methods
  static async startSession(userId: string): Promise<string | null> {
    this.currentUserId = userId;
    const sessionId = `session_${Date.now()}`;
    console.log(`[Web Analytics] Session started for user ${userId}, session ID: ${sessionId}`);
    return sessionId;
  }

  static async endSession(): Promise<void> {
    console.log('[Web Analytics] Session ended');
  }

  static async trackDailyActiveUser(): Promise<void> {
    console.log('[Web Analytics] Track daily active user');
  }

  static async trackUserFirstLaunch(): Promise<void> {
    console.log('[Web Analytics] Track user first launch');
  }

  static async isSessionActive(): Promise<boolean> {
    return true;
  }

  // User ID management with persistent storage (using localStorage for web)
  static async getPersistentUserId(): Promise<string> {
    try {
      if (typeof window === 'undefined') return 'server-side-user';

      let userId = localStorage.getItem('meetily_user_id');
      if (!userId) {
        userId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        localStorage.setItem('meetily_user_id', userId);
        localStorage.setItem('is_first_launch', 'true');
      }
      return userId;
    } catch (error) {
      console.error('[Web Analytics] Failed to get persistent user ID:', error);
      return 'unknown-user';
    }
  }

  static async checkAndTrackFirstLaunch(): Promise<void> {
    if (typeof window === 'undefined') return;
    const isFirstLaunch = localStorage.getItem('is_first_launch') === 'true';
    if (isFirstLaunch) {
      await this.trackUserFirstLaunch();
      localStorage.removeItem('is_first_launch');
    }
  }

  static async checkAndTrackDailyUsage(): Promise<void> {
    if (typeof window === 'undefined') return;
    const today = new Date().toISOString().split('T')[0];
    const lastTracked = localStorage.getItem('last_daily_tracked');
    if (lastTracked !== today) {
      await this.trackDailyActiveUser();
      localStorage.setItem('last_daily_tracked', today);
    }
  }

  static getCurrentUserId(): string | null {
    return this.currentUserId;
  }

  // Platform/Device detection methods
  static async getPlatform(): Promise<string> {
    if (typeof navigator === 'undefined') return 'unknown';
    const userAgent = navigator.userAgent.toLowerCase();
    if (userAgent.includes('mac')) return 'macOS';
    if (userAgent.includes('win')) return 'Windows';
    if (userAgent.includes('linux')) return 'Linux';
    return 'Web';
  }

  static async getOSVersion(): Promise<string> {
    if (typeof navigator === 'undefined') return 'unknown';
    return navigator.userAgent;
  }

  static async getDeviceInfo(): Promise<DeviceInfo> {
    if (this.deviceInfo) return this.deviceInfo;
    const platform = await this.getPlatform();
    const osVersion = await this.getOSVersion();
    this.deviceInfo = {
      platform,
      os_version: osVersion,
      architecture: 'web-client'
    };
    return this.deviceInfo;
  }

  // Helper methods
  static async calculateDaysSince(dateKey: string): Promise<number | null> {
    if (typeof window === 'undefined') return null;
    const dateStr = localStorage.getItem(dateKey);
    if (!dateStr) return null;
    const diffMs = Date.now() - new Date(dateStr).getTime();
    return Math.floor(diffMs / (1000 * 60 * 60 * 24));
  }

  static async updateMeetingCount(): Promise<void> {
    if (typeof window === 'undefined') return;

    const totalMeetings = parseInt(localStorage.getItem('total_meetings') || '0') + 1;
    localStorage.setItem('total_meetings', totalMeetings.toString());
    localStorage.setItem('last_meeting_date', new Date().toISOString());

    // Daily count
    const today = new Date().toISOString().split('T')[0];
    const dailyCounts = JSON.parse(localStorage.getItem('daily_meeting_counts') || '{}');
    dailyCounts[today] = (dailyCounts[today] || 0) + 1;
    localStorage.setItem('daily_meeting_counts', JSON.stringify(dailyCounts));
  }

  static async getMeetingsCountToday(): Promise<number> {
    if (typeof window === 'undefined') return 0;
    const today = new Date().toISOString().split('T')[0];
    const dailyCounts = JSON.parse(localStorage.getItem('daily_meeting_counts') || '{}');
    return dailyCounts[today] || 0;
  }

  static async hasUsedFeatureBefore(featureName: string): Promise<boolean> {
    if (typeof window === 'undefined') return false;
    const features = JSON.parse(localStorage.getItem('features_used') || '{}');
    return !!features[featureName];
  }

  static async markFeatureUsed(featureName: string): Promise<void> {
    if (typeof window === 'undefined') return;
    const features = JSON.parse(localStorage.getItem('features_used') || '{}');
    if (!features[featureName]) {
      features[featureName] = { first_used: new Date().toISOString(), use_count: 1 };
    } else {
      features[featureName].use_count++;
    }
    localStorage.setItem('features_used', JSON.stringify(features));
  }

  // Events
  static async trackSessionStarted(sessionId: string): Promise<void> {
    await this.track('session_started', { session_id: sessionId });
  }

  static async trackSessionEnded(sessionId: string): Promise<void> {
    await this.track('session_ended', { session_id: sessionId });
  }

  static async trackMeetingCompleted(meetingId: string, metrics: any): Promise<void> {
    await this.track('meeting_completed', { meeting_id: meetingId, ...metrics });
    this.meetingsInSession++;
  }

  static async trackFeatureUsedEnhanced(featureName: string, properties?: any): Promise<void> {
    await this.markFeatureUsed(featureName);
    await this.track('feature_used', { feature_name: featureName, ...properties });
  }

  static async trackCopy(copyType: string, properties?: any): Promise<void> {
    await this.track(`${copyType}_copied`, properties);
  }

  static async trackMeetingStarted(meetingId: string, meetingTitle: string): Promise<void> {
    await this.track('meeting_started', { meetingId, meetingTitle });
  }

  static async trackRecordingStarted(meetingId: string): Promise<void> {
    await this.track('recording_started', { meetingId });
  }

  static async trackRecordingStopped(meetingId: string, durationSeconds?: number): Promise<void> {
    await this.track('recording_stopped', { meetingId, durationSeconds: durationSeconds?.toString() || '' });
  }

  static async trackMeetingDeleted(meetingId: string): Promise<void> {
    await this.track('meeting_deleted', { meetingId });
  }

  static async trackSettingsChanged(settingType: string, newValue: string): Promise<void> {
    await this.track('settings_changed', { settingType, newValue });
  }

  static async trackFeatureUsed(featureName: string): Promise<void> {
    await this.track('feature_used_simple', { featureName });
  }

  static async trackPageView(pageName: string): Promise<void> {
    await this.track(`page_view_${pageName}`, { page: pageName });
  }

  static async trackButtonClick(buttonName: string, location?: string): Promise<void> {
    await this.track(`button_click_${buttonName}`, { location: location || '' });
  }

  static async trackError(errorType: string, errorMessage: string): Promise<void> {
    await this.track('error', { error_type: errorType, error_message: errorMessage });
  }

  static async trackAppStarted(): Promise<void> {
    await this.track('app_started', { timestamp: new Date().toISOString() });
  }

  static async cleanup(): Promise<void> {
    await this.endSession();
  }

  static reset(): void {
    this.initialized = false;
  }

  static async waitForInitialization(timeout: number = 5000): Promise<boolean> {
    if (!this.initialized) {
      await this.init();
    }
    return true;
  }

  static async trackBackendConnection(success: boolean, error?: string) {
    await this.track('backend_connection', { success: success.toString(), error: error || '' });
  }

  static async trackTranscriptionError(errorMessage: string) {
    await this.track('transcription_error', { error: errorMessage });
  }

  static async trackTranscriptionSuccess(duration?: number) {
    await this.track('transcription_success', { duration: duration?.toString() || '' });
  }

  static async trackSummaryGenerationStarted(modelProvider: string, modelName: string, transcriptLength: number, timeSince?: number) {
    await this.track('summary_generation_started', { modelProvider, modelName, transcriptLength: transcriptLength.toString() });
  }

  static async trackSummaryGenerationCompleted(modelProvider: string, modelName: string, success: boolean, duration?: number, error?: string) {
    await this.track('summary_generation_completed', { modelProvider, modelName, success: success.toString(), duration: duration?.toString() || '', error: error || '' });
  }

  static async trackSummaryRegenerated(modelProvider: string, modelName: string) {
    await this.track('summary_regenerated', { modelProvider, modelName });
  }

  static async trackModelChanged(oldProvider: string, oldModel: string, newProvider: string, newModel: string) {
    console.log('Model changed event tracked successfully');
  }

  static async trackCustomPromptUsed(promptLength: number) {
    await this.track('custom_prompt_used', { prompt_length: promptLength.toString() });
  }
} 