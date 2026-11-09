export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  emotion?: string;
  model?: string;
  thinkingLevel?: string;
}

export interface Session {
  id: string;
  title: string;
  created_at: number;
  message_count?: number;
}

export interface WebSocketMessage {
  type: string;
  payload?: any;
  data?: any;
}

export interface AvatarState {
  emotion: string;
  mouthOpen: number;
  isSpeaking: boolean;
  isListening: boolean;
  isThinking: boolean;
}

export type AppStatus = 'ready' | 'listening' | 'thinking' | 'speaking' | 'error';
