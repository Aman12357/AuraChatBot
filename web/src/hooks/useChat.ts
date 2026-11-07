'use client';

import {
  useState,
  useCallback,
  useEffect,
  useRef,
} from 'react';

import type {
  Message,
  Session,
} from '@/types';

import { useWebSocket } from './useWebSocket';

import { avatarController } from '@/components/Avatar/controllers/AvatarController';

import { voicePlayer } from '@/utils/voicePlayer';

/* =========================================================
   TYPES
   ========================================================= */

interface ApiChatResponse {
  status?: string;
  response?: string;
  content?: string;
  emotion?: string;
  session_id?: string;
  error?: string;
}

/* =========================================================
   HOOK
   ========================================================= */

export function useChat(token: string | null = null) {
  const [
    messages,
    setMessages,
  ] = useState<Message[]>([]);

  const [
    sessions,
    setSessions,
  ] = useState<Session[]>([]);

  const [
    currentSessionId,
    setCurrentSessionId,
  ] = useState<string>('');

  const [
    streamingText,
    setStreamingText,
  ] = useState<string>('');

  const [
    isStreaming,
    setIsStreaming,
  ] = useState<boolean>(false);

  const streamRef =
    useRef<ReturnType<
      typeof setInterval
    > | null>(null);

  const {
    send,
    lastMessage,
    isConnected,
  } = useWebSocket(undefined, token);

  /* =======================================================
     API URL
     ======================================================= */

  const getApiUrl =
    useCallback(() => {
      const value =
        process.env
          .NEXT_PUBLIC_API_URL;

      if (!value) {
        return '';
      }

      return value.replace(
        /\/$/,
        ''
      );
    }, []);

  useEffect(() => {
    setMessages([]);
    setSessions([]);
    setCurrentSessionId('');
    setStreamingText('');
    setIsStreaming(false);
  }, [token]);

  /* =======================================================
     LOAD DATA AFTER SOCKET CONNECTION
     ======================================================= */

  useEffect(() => {
    if (!isConnected) {
      return;
    }

    send({
      type:
        'session.list',
      data: {},
    });

    send({
      type:
        'history.get',
      data: {
        session_id:
          currentSessionId,
      },
    });

    avatarController.onSpeechRequest =
      (text: string) => {
        voicePlayer.play(text);
      };

    return () => {
      avatarController.onSpeechRequest =
        null;

      voicePlayer.stop();
    };
  }, [
    isConnected,
    send,
    currentSessionId,
  ]);

  /* =======================================================
     WEBSOCKET MESSAGE HANDLER
     ======================================================= */

  useEffect(() => {
    if (!lastMessage) {
      return;
    }

    const type =
      lastMessage.type;

    const data =
      lastMessage.data ||
      lastMessage.payload ||
      {};

    switch (type) {
      case 'chat.stream': {
        setIsStreaming(true);

        setStreamingText(
          (previous) =>
            previous +
            (data.token ||
              '')
        );

        break;
      }

      case 'chat.done': {
        const finalText =
          data.full_response ||
          data.content ||
          '';

        setIsStreaming(
          false
        );

        if (data.session_id) {
          setCurrentSessionId(data.session_id);
        }

        if (finalText) {
          const newMessage: Message =
            {
              id:
                typeof crypto !==
                  'undefined' &&
                crypto.randomUUID
                  ? crypto.randomUUID()
                  : String(
                      Date.now()
                    ),
              role:
                'assistant',
              content:
                finalText,
              timestamp:
                Date.now(),
              emotion:
                data.emotion,
            };

          setMessages(
            (previous) => [
              ...previous,
              newMessage,
            ]
          );

          setStreamingText(
            ''
          );

          /*
           Browser TTS
          */

          try {
            voicePlayer.play(
              finalText
            );
          } catch (
            error
          ) {
            console.warn(
              'TTS playback failed:',
              error
            );
          }
        }

        break;
      }

      case 'session.list': {
        if (
          Array.isArray(
            data.sessions
          )
        ) {
          const mapped =
            data.sessions.map(
              (session: any) => ({
                id:
                  session.session_id,

                title:
                  session.title,

                created_at:
                  new Date(
                    session.created_at
                  ).getTime(),

                message_count:
                  session.message_count,
              })
            );

          setSessions(
            mapped
          );
        }

        if (
          data.active_session_id
        ) {
          setCurrentSessionId(
            data.active_session_id
          );
        }

        break;
      }

      case 'session.created': {
        const newSession: Session =
          {
            id:
              data.session_id,

            title:
              data.title,

            created_at:
              new Date(
                data.created_at
              ).getTime(),

            message_count:
              0,
          };

        setSessions(
          (previous) => [
            newSession,
            ...previous,
          ]
        );

        setCurrentSessionId(
          newSession.id
        );

        setMessages([]);

        setStreamingText('');

        break;
      }

      case 'session.switched': {
        const sessionId =
          data.session_id;

        setCurrentSessionId(
          sessionId
        );

        setMessages([]);

        send({
          type:
            'history.get',
          data: {
            session_id:
              sessionId,
          },
        });

        break;
      }

      case 'history.data': {
        if (data.session_id) {
          setCurrentSessionId(data.session_id);
        }

        if (
          Array.isArray(
            data.messages
          )
        ) {
          const mapped =
            data.messages.map(
              (message: any) => ({
                id: String(
                  message.id
                ),

                role:
                  message.role,

                content:
                  message.content,

                timestamp:
                  new Date(
                    message.timestamp
                  ).getTime(),

                emotion:
                  message.emotion,
              })
            );

          setMessages(
            mapped
          );
        }

        break;
      }

      case 'status.update': {
        if (
          data.status
        ) {
          window.dispatchEvent(
            new CustomEvent(
              'avatar-status-update',
              {
                detail:
                  data.status,
              }
            )
          );
        }

        break;
      }

      default:
        break;
    }
  }, [
    lastMessage,
    send,
  ]);

  /* =======================================================
     SEND MESSAGE
     ======================================================= */

  const sendMessage =
    useCallback(
      async (
        content: string
      ) => {
        const trimmed =
          content.trim();

        if (!token || !trimmed) {
          return;
        }

        const userMessage: Message =
          {
            id:
              typeof crypto !==
                'undefined' &&
              crypto.randomUUID
                ? crypto.randomUUID()
                : String(
                    Date.now()
                  ),

            role:
              'user',

            content:
              trimmed,

            timestamp:
              Date.now(),
          };

        setMessages(
          (previous) => [
            ...previous,
            userMessage,
          ]
        );

        /*
         WebSocket path
        */

        if (isConnected) {
          setIsStreaming(
            true
          );

          setStreamingText(
            ''
          );

          send({
            type:
              'chat.send',

            data: {
              text:
                trimmed,

              session_id:
                currentSessionId,
            },
          });

          return;
        }

        /*
         REST fallback
        */

        const apiUrl =
          getApiUrl();

        if (!apiUrl) {
          setIsStreaming(
            false
          );

          const fallback: Message =
            {
              id:
                String(
                  Date.now() +
                    1
                ),

              role:
                'assistant',

              content:
                'Aleena backend URL is not configured. Please set NEXT_PUBLIC_API_URL in Render.',

              timestamp:
                Date.now(),
            };

          setMessages(
            (previous) => [
              ...previous,
              fallback,
            ]
          );

          return;
        }

        try {
          setIsStreaming(
            true
          );

          const response =
            await fetch(
              `${apiUrl}/api/chat`,
              {
                method:
                  'POST',

                headers: {
                  'Content-Type':
                    'application/json',
                  Authorization: `Bearer ${token}`,
                },

                body: JSON.stringify({
                  message:
                    trimmed,

                  session_id:
                    currentSessionId,
                }),
              }
            );

          const data: ApiChatResponse =
            await response.json();

          if (!response.ok) {
            throw new Error(
              data.error ||
                `API request failed with status ${response.status}`
            );
          }

          const aiText =
            data.response ||
            data.content;

          if (!aiText) {
            throw new Error(
              'The backend returned an empty AI response.'
            );
          }

          const aiMessage: Message =
            {
              id:
                typeof crypto !==
                  'undefined' &&
                crypto.randomUUID
                  ? crypto.randomUUID()
                  : String(
                      Date.now()
                    ),

              role:
                'assistant',

              content:
                aiText,

              timestamp:
                Date.now(),

              emotion:
                data.emotion,
            };

          setMessages(
            (previous) => [
              ...previous,
              aiMessage,
            ]
          );

          if (
            data.session_id
          ) {
            setCurrentSessionId(
              data.session_id
            );
          }

          setStreamingText(
            ''
          );

          try {
            voicePlayer.play(
              aiText
            );
          } catch (
            error
          ) {
            console.warn(
              'Browser TTS failed:',
              error
            );
          }
        } catch (error) {
          console.error(
            'REST chat error:',
            error
          );

          const errorMessage: Message =
            {
              id:
                String(
                  Date.now() +
                    2
                ),

              role:
                'assistant',

              content:
                `I could not connect to the Aleena AI backend. ${
                  error instanceof Error
                    ? error.message
                    : ''
                }`,

              timestamp:
                Date.now(),

              emotion:
                'sad',
            };

          setMessages(
            (previous) => [
              ...previous,
              errorMessage,
            ]
          );
        } finally {
          setIsStreaming(
            false
          );

          setStreamingText(
            ''
          );
        }
      },
      [
        currentSessionId,
        getApiUrl,
        isConnected,
        token,
        send,
      ]
    );

  /* =======================================================
     SESSION SWITCH
     ======================================================= */

  const switchSession =
    useCallback(
      (
        sessionId: string
      ) => {
        if (
          isConnected
        ) {
          send({
            type:
              'session.switch',

            data: {
              session_id:
                sessionId,
            },
          });
        } else {
          setCurrentSessionId(
            sessionId
          );

          setMessages([]);

          setStreamingText('');
        }
      },
      [
        isConnected,
        send,
      ]
    );

  /* =======================================================
     CREATE SESSION
     ======================================================= */

  const createSession =
    useCallback(() => {
      if (
        isConnected
      ) {
        send({
          type:
            'session.create',

          data: {},
        });

        return;
      }

      const newSession: Session =
        {
          id:
            `session-${Date.now()}`,

          title:
            `New Chat ${
              sessions.length +
              1
            }`,

          created_at:
            Date.now(),

          message_count:
            0,
        };

      setSessions(
        (previous) => [
          newSession,
          ...previous,
        ]
      );

      setCurrentSessionId(
        newSession.id
      );

      setMessages([]);

      setStreamingText('');
    }, [
      isConnected,
      send,
      sessions.length,
    ]);

  /* =======================================================
     VOICE
     ======================================================= */

  const startVoice =
    useCallback(() => {
      if (
        isConnected
      ) {
        send({
          type:
            'voice.start',

          data: {},
        });
      }
    }, [
      isConnected,
      send,
    ]);

  const stopVoice =
    useCallback(() => {
      if (
        isConnected
      ) {
        send({
          type:
            'voice.stop',

          data: {},
        });
      }
    }, [
      isConnected,
      send,
    ]);

  /* =======================================================
     CLEANUP
     ======================================================= */

  useEffect(() => {
    return () => {
      if (
        streamRef.current
      ) {
        clearInterval(
          streamRef.current
        );
      }
    };
  }, []);

  /* =======================================================
     RETURN
     ======================================================= */

  return {
    messages,
    sessions,
    currentSessionId,
    streamingText,
    isStreaming,
    isConnected,
    sendMessage,
    switchSession,
    createSession,
    startVoice,
    stopVoice,
  };
}
