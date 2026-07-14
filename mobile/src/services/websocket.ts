/**
 * WebSocket chat service for real-time communication with Jarvis
 */
import { api } from './api';

type MessageHandler = (data: any) => void;

class WebSocketService {
  private ws: WebSocket | null = null;
  private url: string = 'ws://localhost:8000/ws/v1/chat';
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private isConnected: boolean = false;
  private messageHandlers: Map<string, Set<MessageHandler>> = new Map();
  private shouldReconnect: boolean = true;

  setUrl(url: string) {
    this.url = url;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    try {
      this.ws = new WebSocket(this.url);
    } catch (error) {
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.isConnected = true;
      // Send auth token
      const token = api.getAccessToken();
      if (token) {
        this.send({ type: 'auth', token });
      }
      this.emit('connected', null);
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.emit('message', data);
      } catch {
        // Ignore parse errors
      }
    };

    this.ws.onclose = () => {
      this.isConnected = false;
      this.emit('disconnected', null);
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      // onclose will be called after this
    };
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
    this.ws?.close();
    this.ws = null;
    this.isConnected = false;
  }

  private scheduleReconnect(): void {
    if (!this.shouldReconnect) return;
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);
    this.reconnectTimeout = setTimeout(() => {
      this.connect();
    }, 3000);
  }

  send(data: Record<string, any>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  sendMessage(conversationId: string, content: string): void {
    this.send({
      type: 'message',
      conversation_id: conversationId,
      content,
    });
  }

  on(event: string, handler: MessageHandler): () => void {
    if (!this.messageHandlers.has(event)) {
      this.messageHandlers.set(event, new Set());
    }
    this.messageHandlers.get(event)!.add(handler);
    return () => {
      this.messageHandlers.get(event)?.delete(handler);
    };
  }

  private emit(event: string, data: any): void {
    this.messageHandlers.get(event)?.forEach((handler) => {
      try {
        handler(data);
      } catch {
        // Ignore handler errors
      }
    });
  }
}

export const wsService = new WebSocketService();
export default wsService;