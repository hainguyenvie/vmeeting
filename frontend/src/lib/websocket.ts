/**
 * WebSocket Client for Real-time Updates
 * Replaces Tauri event system
 */

export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface WebSocketMessage<T = any> {
    type: string;
    data: T;
    timestamp: number;
}

export class WebSocketClient {
    private ws: WebSocket | null = null;
    private url: string;
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectDelay = 1000;
    private listeners: Map<string, Set<(data: any) => void>> = new Map();
    private statusCallbacks: Set<(status: WebSocketStatus) => void> = new Set();

    constructor(url: string) {
        this.url = url;
    }

    /**
     * Connect to WebSocket server
     */
    connect(): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            console.log('WebSocket already connected');
            return;
        }

        this.updateStatus('connecting');

        try {
            this.ws = new WebSocket(this.url);

            this.ws.onopen = () => {
                console.log('WebSocket connected:', this.url);
                this.updateStatus('connected');
                this.reconnectAttempts = 0;
            };

            this.ws.onmessage = (event) => {
                try {
                    const message: WebSocketMessage = JSON.parse(event.data);
                    this.emit(message.type, message.data);
                } catch (error) {
                    console.error('Failed to parse WebSocket message:', error);
                }
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.updateStatus('error');
            };

            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.updateStatus('disconnected');
                this.attemptReconnect();
            };
        } catch (error) {
            console.error('Failed to create WebSocket:', error);
            this.updateStatus('error');
        }
    }

    /**
     * Disconnect from WebSocket server
     */
    disconnect(): void {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    /**
     * Send message to server
     */
    send(type: string, data: any): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            const message: WebSocketMessage = {
                type,
                data,
                timestamp: Date.now(),
            };
            this.ws.send(JSON.stringify(message));
        } else {
            console.warn('WebSocket not connected, cannot send message');
        }
    }

    /**
     * Send raw binary data (for audio streaming)
     */
    sendBinary(data: ArrayBuffer): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(data);
        } else {
            console.warn('WebSocket not connected, cannot send binary data');
        }
    }

    /**
     * Listen to specific event type
     * Replaces: listen('transcript-update', callback)
     */
    on(eventType: string, callback: (data: any) => void): () => void {
        if (!this.listeners.has(eventType)) {
            this.listeners.set(eventType, new Set());
        }
        this.listeners.get(eventType)!.add(callback);

        // Return unsubscribe function
        return () => {
            this.listeners.get(eventType)?.delete(callback);
        };
    }

    /**
     * Remove listener
     */
    off(eventType: string, callback: (data: any) => void): void {
        this.listeners.get(eventType)?.delete(callback);
    }

    /**
     * Listen to connection status changes
     */
    onStatusChange(callback: (status: WebSocketStatus) => void): () => void {
        this.statusCallbacks.add(callback);
        return () => {
            this.statusCallbacks.delete(callback);
        };
    }

    /**
     * Emit event to all listeners
     */
    private emit(eventType: string, data: any): void {
        this.listeners.get(eventType)?.forEach((callback) => {
            try {
                callback(data);
            } catch (error) {
                console.error(`Error in listener for ${eventType}:`, error);
            }
        });
    }

    /**
     * Update connection status
     */
    private updateStatus(status: WebSocketStatus): void {
        this.statusCallbacks.forEach((callback) => {
            try {
                callback(status);
            } catch (error) {
                console.error('Error in status callback:', error);
            }
        });
    }

    /**
     * Attempt to reconnect
     */
    private attemptReconnect(): void {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('Max reconnect attempts reached');
            return;
        }

        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

        setTimeout(() => {
            this.connect();
        }, delay);
    }

    /**
     * Get current connection status
     */
    getStatus(): WebSocketStatus {
        if (!this.ws) return 'disconnected';

        switch (this.ws.readyState) {
            case WebSocket.CONNECTING:
                return 'connecting';
            case WebSocket.OPEN:
                return 'connected';
            case WebSocket.CLOSING:
            case WebSocket.CLOSED:
                return 'disconnected';
            default:
                return 'error';
        }
    }
}

// ============================================================================
// Create singleton instances for common connections
// ============================================================================

const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:5167';

/**
 * Transcription WebSocket - for real-time transcript updates
 * Replaces Tauri 'transcript-update' event
 */
export const transcriptionWS = new WebSocketClient(`${WS_BASE_URL}/ws/transcripts`);

/**
 * Meeting WebSocket - for meeting status updates
 */
export const meetingWS = new WebSocketClient(`${WS_BASE_URL}/ws/meetings`);

/**
 * Create audio streaming WebSocket for specific meeting
 */
export function createAudioStreamWS(meetingId: string): WebSocketClient {
    return new WebSocketClient(`${WS_BASE_URL}/ws/audio/${meetingId}`);
}
