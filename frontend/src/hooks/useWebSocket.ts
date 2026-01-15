/**
 * WebSocket Hook for React Components
 * Replaces Tauri listen() event system
 */

import { useState, useEffect, useRef } from 'react';
import type { WebSocketClient, WebSocketStatus } from '@/lib/websocket';

export interface UseWebSocketOptions<T> {
    /**
     * WebSocket client instance
     */
    client: WebSocketClient;

    /**
     * Event type to listen for
     * e.g., 'transcript-update', 'meeting-update'
     */
    eventType: string;

    /**
     * Auto-connect on mount
     * @default true
     */
    autoConnect?: boolean;

    /**
     * Callback when data received
     */
    onMessage?: (data: T) => void;

    /**
     * Callback on connection status change
     */
    onStatusChange?: (status: WebSocketStatus) => void;
}

export function useWebSocket<T = any>(options: UseWebSocketOptions<T>) {
    const { client, eventType, autoConnect = true, onMessage, onStatusChange } = options;

    const [data, setData] = useState<T | null>(null);
    const [status, setStatus] = useState<WebSocketStatus>('disconnected');
    const [error, setError] = useState<Error | null>(null);

    // Refs to avoid stale closures
    const onMessageRef = useRef(onMessage);
    const onStatusChangeRef = useRef(onStatusChange);

    useEffect(() => {
        onMessageRef.current = onMessage;
        onStatusChangeRef.current = onStatusChange;
    }, [onMessage, onStatusChange]);

    useEffect(() => {
        // Auto-connect if enabled
        if (autoConnect) {
            client.connect();
        }

        // Listen for status changes
        const unsubscribeStatus = client.onStatusChange((newStatus) => {
            setStatus(newStatus);
            onStatusChangeRef.current?.(newStatus);

            if (newStatus === 'error') {
                setError(new Error('WebSocket connection error'));
            } else {
                setError(null);
            }
        });

        // Listen for messages
        const unsubscribeMessage = client.on(eventType, (receivedData: T) => {
            setData(receivedData);
            onMessageRef.current?.(receivedData);
        });

        // Cleanup on unmount
        return () => {
            unsubscribeStatus();
            unsubscribeMessage();

            if (autoConnect) {
                client.disconnect();
            }
        };
    }, [client, eventType, autoConnect]);

    return {
        data,
        status,
        error,
        isConnected: status === 'connected',
        isConnecting: status === 'connecting',
    };
}

/**
 * Simplified hook for specific event types
 */

export function useTranscriptUpdates(
    client: WebSocketClient,
    onUpdate?: (data: any) => void
) {
    return useWebSocket({
        client,
        eventType: 'transcript-update',
        onMessage: onUpdate,
    });
}

export function useMeetingUpdates(
    client: WebSocketClient,
    onUpdate?: (data: any) => void
) {
    return useWebSocket({
        client,
        eventType: 'meeting-update',
        onMessage: onUpdate,
    });
}
