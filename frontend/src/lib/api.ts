/**
 * API Client for Web Version
 * Replaces Tauri invoke() commands with HTTP requests
 */

import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:5167';

export const apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 30000,
});

// Types
export interface Meeting {
    id: string;
    title: string;
    created_at: number;
    duration?: number;
    summary?: string;
}

export interface Transcript {
    id: string;
    meeting_id: string;
    transcript: string;
    timestamp: string;
    speaker?: string;
    audio_start_time?: number;
    audio_end_time?: number;
}

export interface TranscriptUpdate {
    text: string;
    speaker?: string;
    timestamp: string;
    sequence_id: number;
    audio_start_time: number;
    audio_end_time: number;
    duration: number;
    confidence: number;
    is_provisional: boolean;
}

// ============================================================================
// Meeting API
// ============================================================================

export const meetingsAPI = {
    /**
     * Get all meetings
     * Replaces: invoke('get_meetings')
     */
    getAll: async (): Promise<Meeting[]> => {
        const response = await apiClient.get('/get-meetings');
        return response.data;
    },

    /**
     * Get single meeting by ID
     * Replaces: invoke('get_meeting', { meetingId: id })
     */
    getById: async (id: string): Promise<Meeting> => {
        const response = await apiClient.get(`/get-meeting/${id}`);
        return response.data;
    },

    /**
     * Create new meeting
     * Replaces: invoke('create_meeting', { title })
     */
    create: async (data: { title: string }): Promise<Meeting> => {
        const response = await apiClient.post('/create-meeting', data);
        return response.data;
    },

    /**
     * Update meeting
     * Replaces: invoke('update_meeting', { meetingId, title })
     */
    update: async (id: string, data: Partial<Meeting>): Promise<Meeting> => {
        const response = await apiClient.put(`/update-meeting/${id}`, data);
        return response.data;
    },

    /**
     * Delete meeting
     * Replaces: invoke('delete_meeting', { meetingId })
     */
    delete: async (id: string): Promise<void> => {
        await apiClient.delete(`/delete-meeting/${id}`);
    },

    /**
     * Get meeting transcripts
     * Replaces: invoke('get_transcripts', { meetingId })
     */
    getTranscripts: async (meetingId: string): Promise<Transcript[]> => {
        const response = await apiClient.get(`/get-transcripts/${meetingId}`);
        return response.data;
    },
};

// ============================================================================
// Audio API
// ============================================================================

export const audioAPI = {
    /**
     * Upload complete audio file
     */
    upload: async (file: File | Blob, meetingId: string): Promise<any> => {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('meeting_id', meetingId);

        const response = await apiClient.post('/api/audio/upload', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    },

    /**
     * Upload audio chunk for streaming
     */
    uploadChunk: async (chunk: Blob, meetingId: string): Promise<TranscriptUpdate> => {
        const formData = new FormData();
        formData.append('file', chunk);
        formData.append('meeting_id', meetingId);

        const response = await apiClient.post('/api/audio/chunk', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    },

    /**
     * Trigger transcription
     */
    transcribe: async (audioData: Blob): Promise<any> => {
        const formData = new FormData();
        formData.append('file', audioData);

        const response = await apiClient.post('/api/audio/transcribe', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    },
};

// ============================================================================
// Diarization API
// ============================================================================

export const diarizationAPI = {
    /**
     * Process audio for speaker detection
     */
    process: async (audioData: Blob): Promise<{ speaker: string; score: number }> => {
        const formData = new FormData();
        formData.append('file', audioData);

        const response = await apiClient.post('/api/diarization/process', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        return response.data;
    },
};

// ============================================================================
// Recording API (NEW - replaces Tauri recording commands)
// ============================================================================

export const recordingAPI = {
    /**
     * Start recording session
     * Replaces: invoke('start_recording')
     */
    start: async (meetingId: string): Promise<{ status: string }> => {
        const response = await apiClient.post('/api/recording/start', { meeting_id: meetingId });
        return response.data;
    },

    /**
     * Stop recording session
     * Replaces: invoke('stop_recording')
     */
    stop: async (meetingId: string): Promise<{ status: string }> => {
        const response = await apiClient.post('/api/recording/stop', { meeting_id: meetingId });
        return response.data;
    },
};

export const summaryAPI = {
    /**
     * Get available templates
     */
    getTemplates: async (): Promise<Array<{ id: string; name: string; description: string }>> => {
        const response = await apiClient.get('/api/summary/templates');
        return response.data;
    },

    /**
     * Generate summary
     */
    generate: async (data: {
        transcript: string;
        template_id: string;
        provider?: string;
        model?: string;
        api_key?: string;
        custom_prompt?: string;
        meeting_id?: string;
    }): Promise<{ summary: any; raw_summary?: string; model: string; markdown?: string; summary_json?: any[] }> => {
        const response = await apiClient.post('/api/summary/generate', data);
        return response.data;
    },
};

// ============================================================================
// Export
// ============================================================================

export default apiClient;
