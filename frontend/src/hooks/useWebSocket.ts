import { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';

interface WebSocketMessage {
  type: string;
  data?: any;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  lastMessage: WebSocketMessage | null;
  sendMessage: (message: WebSocketMessage) => void;
  subscribe: (callback: (message: WebSocketMessage) => void) => () => void;
}

export const useWebSocket = (url: string): UseWebSocketReturn => {
  const { session } = useAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const ws = useRef<WebSocket | null>(null);
  const subscribers = useRef<((message: WebSocketMessage) => void)[]>([]);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;
  const reconnectDelay = useRef(1000);

  const connect = useCallback(() => {
    if (!session?.access_token) {
      console.log('No access token available for WebSocket connection');
      return;
    }

    try {
      ws.current = new WebSocket(url);

      ws.current.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        reconnectAttempts.current = 0;
        reconnectDelay.current = 1000;

        // Authenticate immediately after connection
        if (ws.current && session?.access_token) {
          const authMessage = {
            type: 'authenticate',
            data: {
              token: session.access_token
            }
          };
          ws.current.send(JSON.stringify(authMessage));
        }
      };

      ws.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          console.log('WebSocket message received:', message);
          setLastMessage(message);

          // Notify all subscribers
          subscribers.current.forEach(callback => callback(message));

          // Handle specific events
          switch (message.type) {
            case 'connection_confirmed':
              console.log('WebSocket authentication confirmed');
              // Subscribe to conversations after authentication
              if (ws.current) {
                const subscribeMessage = {
                  type: 'subscribe_conversations',
                  data: {}
                };
                ws.current.send(JSON.stringify(subscribeMessage));
              }
              break;
            case 'subscription_updated':
              console.log('Subscription updated:', message.data);
              break;
            case 'new_message':
              console.log('New message received:', message.data);
              break;
            default:
              console.log('Unknown message type:', message.type);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      ws.current.onclose = (event) => {
        console.log('WebSocket disconnected:', event.code, event.reason);
        setIsConnected(false);

        // Attempt to reconnect if it wasn't a manual close
        if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current++;
          console.log(`Attempting to reconnect (${reconnectAttempts.current}/${maxReconnectAttempts})...`);
          
          setTimeout(() => {
            connect();
          }, reconnectDelay.current);
          
          // Exponential backoff
          reconnectDelay.current = Math.min(reconnectDelay.current * 2, 30000);
        }
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

    } catch (error) {
      console.error('Error creating WebSocket connection:', error);
    }
  }, [url, session?.access_token]);

  const disconnect = useCallback(() => {
    if (ws.current) {
      ws.current.close(1000, 'Manual disconnect');
      ws.current = null;
    }
  }, []);

  const sendMessage = useCallback((message: WebSocketMessage) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected. Message not sent:', message);
    }
  }, []);

  const subscribe = useCallback((callback: (message: WebSocketMessage) => void) => {
    subscribers.current.push(callback);
    
    return () => {
      subscribers.current = subscribers.current.filter(sub => sub !== callback);
    };
  }, []);

  // Setup ping interval to keep connection alive
  useEffect(() => {
    let pingInterval: NodeJS.Timeout;

    if (isConnected) {
      pingInterval = setInterval(() => {
        sendMessage({ type: 'ping' });
      }, 30000); // Ping every 30 seconds
    }

    return () => {
      if (pingInterval) {
        clearInterval(pingInterval);
      }
    };
  }, [isConnected, sendMessage]);

  // Connect on mount and when session changes
  useEffect(() => {
    if (session?.access_token) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [connect, disconnect, session?.access_token]);

  return {
    isConnected,
    lastMessage,
    sendMessage,
    subscribe
  };
};
