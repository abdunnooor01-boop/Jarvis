/**
 * Voice Input Service
 * Provides speech-to-text functionality using react-native-voice
 */
import Voice, { SpeechResultsEvent, SpeechErrorEvent } from 'react-native-voice';

type VoiceStateListener = {
  onResult?: (text: string) => void;
  onError?: (error: string) => void;
  onStart?: () => void;
  onEnd?: () => void;
  onPartialResult?: (text: string) => void;
};

class VoiceService {
  private isListening: boolean = false;
  private listeners: Set<VoiceStateListener> = new Set();
  private _isAvailable: boolean | null = null;

  constructor() {
    this._init();
  }

  private _init() {
    Voice.onSpeechStart = () => {
      this.isListening = true;
      this.listeners.forEach((l) => l.onStart?.());
    };

    Voice.onSpeechEnd = () => {
      this.isListening = false;
      this.listeners.forEach((l) => l.onEnd?.());
    };

    Voice.onSpeechResults = (e: SpeechResultsEvent) => {
      const text = e.value?.[0] || '';
      if (text) {
        this.listeners.forEach((l) => l.onResult?.(text));
      }
    };

    Voice.onSpeechPartialResults = (e: SpeechResultsEvent) => {
      const text = e.value?.[0] || '';
      if (text) {
        this.listeners.forEach((l) => l.onPartialResult?.(text));
      }
    };

    Voice.onSpeechError = (e: SpeechErrorEvent) => {
      this.isListening = false;
      const error = e.error?.message || 'Speech recognition error';
      this.listeners.forEach((l) => l.onError?.(error));
    };
  }

  async checkAvailability(): Promise<boolean> {
    if (this._isAvailable !== null) return this._isAvailable;
    try {
      const available = await Voice.isAvailable();
      this._isAvailable = available;
      return available;
    } catch {
      this._isAvailable = false;
      return false;
    }
  }

  async startListening(locale: string = 'en-US'): Promise<boolean> {
    try {
      const available = await this.checkAvailability();
      if (!available) {
        this.listeners.forEach((l) => l.onError?.('Speech recognition not available'));
        return false;
      }
      await Voice.start(locale);
      return true;
    } catch (err: any) {
      this.listeners.forEach((l) => l.onError?.(err.message || 'Failed to start listening'));
      return false;
    }
  }

  async stopListening(): Promise<void> {
    try {
      await Voice.stop();
      this.isListening = false;
    } catch {
      // Ignore stop errors
    }
  }

  async cancel(): Promise<void> {
    try {
      await Voice.cancel();
      this.isListening = false;
    } catch {
      // Ignore cancel errors
    }
  }

  async destroy(): Promise<void> {
    try {
      await Voice.destroy();
      this.isListening = false;
    } catch {
      // Ignore destroy errors
    }
  }

  subscribe(listener: VoiceStateListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  getIsListening(): boolean {
    return this.isListening;
  }
}

// Singleton
export const voiceService = new VoiceService();
export default voiceService;