'use client';

import React, { useState, useCallback, useEffect, useRef } from 'react';
import AuthScreen from './AuthScreen';
import dynamic from 'next/dynamic';
import Navbar from './Navbar';
import ChatPanel from './Chat/ChatPanel';
import InputBar from './Chat/InputBar';
import SessionSidebar from './Chat/SessionSidebar';
import { useChat } from '@/hooks/useChat';
import { useAvatar } from '@/hooks/useAvatar';
import { voicePlayer } from '@/utils/voicePlayer';
import { avatarController } from './Avatar/controllers/AvatarController';

const AvatarStage = dynamic(() => import('./Avatar/AvatarStage'), {
  ssr: false,
  loading: () => (
    <div className="flex-1 flex items-center justify-center text-sm text-white/60">
      Preparing Aleena's holographic avatar…
    </div>
  ),
});

export default function AppShell() {
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [authUser, setAuthUser] = useState<{ id: number | string; email: string; name?: string | null } | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const apiUrl = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');

  useEffect(() => {
    const storedToken = window.localStorage.getItem('aleena_auth_token');
    if (!storedToken) {
      setAuthReady(true);
      return;
    }

    if (!apiUrl) {
      window.localStorage.removeItem('aleena_auth_token');
      setAuthReady(true);
      return;
    }

    fetch(`${apiUrl}/api/auth/me`, {
      headers: { Authorization: `Bearer ${storedToken}` },
    })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok || !data.user) throw new Error('Session expired');
        setAuthToken(storedToken);
        setAuthUser(data.user);
      })
      .catch(() => {
        window.localStorage.removeItem('aleena_auth_token');
        setAuthToken(null);
        setAuthUser(null);
      })
      .finally(() => setAuthReady(true));
  }, [apiUrl]);

  const handleAuthenticated = (token: string, user: { id: number | string; email: string; name?: string | null }) => {
    window.localStorage.setItem('aleena_auth_token', token);
    setAuthToken(token);
    setAuthUser(user);
  };

  const handleLogout = () => {
    window.localStorage.removeItem('aleena_auth_token');
    setAuthToken(null);
    setAuthUser(null);
  };

  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const {
    messages,
    sessions,
    currentSessionId,
    streamingText,
    isStreaming,
    sendMessage,
    switchSession,
    createSession,
    startVoice,
    stopVoice,
  } = useChat(authToken);

  const {
    emotion,
    mouthOpen,
    isSpeaking,
    isListening,
    isThinking,
    status,
    setIsListening,
    setIsSpeaking,
    setIsThinking,
  } = useAvatar();

  // Wire avatarController's speech requests to voicePlayer
  useEffect(() => {
    avatarController.onSpeechRequest = (text: string) => {
      voicePlayer.play(text);
    };
    return () => {
      avatarController.onSpeechRequest = null;
      voicePlayer.stop();
    };
  }, []);

  // Simulate speaking state when streaming
  React.useEffect(() => {
    setIsSpeaking(isStreaming);
  }, [isStreaming, setIsSpeaking]);

  const recognitionRef = useRef<any>(null);

  const handleSend = useCallback(
    (content: string) => {
      sendMessage(content);
      setIsThinking(true);
      setTimeout(() => setIsThinking(false), 1500);
    },
    [sendMessage, setIsThinking]
  );

  useEffect(() => {
    const handleVoiceResult = (event: Event) => {
      const recognizedText = (event as CustomEvent<string>).detail;
      if (recognizedText) handleSend(recognizedText);
    };

    window.addEventListener('aleena-voice-result', handleVoiceResult);
    return () => window.removeEventListener('aleena-voice-result', handleVoiceResult);
  }, [handleSend]);

  // Initialize Speech Recognition once on mount
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn("Browser Speech Recognition not supported in this browser.");
      return;
    }

    const rec = new SpeechRecognition();
    rec.continuous = false;
    rec.interimResults = false;
    rec.lang = 'en-IN'; // Supports Hinglish and Indian accents beautifully

    rec.onstart = () => {
      setIsListening(true);
    };

    rec.onerror = (event: any) => {
      console.error("Speech Recognition Error", event.error);
      setIsListening(false);
      
      // Fallback automatically to server PC mic if browser access is blocked/denied
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        console.warn("Browser mic access denied. Falling back to server mic...");
        startVoice();
        setIsListening(true);
      }
    };

    rec.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = rec;

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
    };
  }, [setIsListening]);

  // Dynamically update callback to avoid stale closures
  useEffect(() => {
    if (recognitionRef.current) {
      recognitionRef.current.onresult = (event: any) => {
        const transcript = event.results[0][0].transcript;
        if (transcript && transcript.trim()) {
          handleSend(transcript);
        }
      };
    }
  }, [handleSend]);

  const handleMicToggle = useCallback(() => {
    if (!recognitionRef.current) {
      // Fallback directly to server microphone capture
      if (isListening) {
        stopVoice();
        setIsListening(false);
      } else {
        startVoice();
        setIsListening(true);
      }
      return;
    }

    if (isListening) {
      try {
        recognitionRef.current.stop();
      } catch (e) {}
      setIsListening(false);
      stopVoice();
    } else {
      try {
        recognitionRef.current.start();
        setIsListening(true);
      } catch (err) {
        console.warn("Local browser Speech Recognition failed. Falling back to server mic:", err);
        startVoice();
        setIsListening(true);
      }
    }
  }, [isListening, setIsListening, startVoice, stopVoice]);

  const [activeTab, setActiveTab] = useState('Chat');
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showOversightModal, setShowOversightModal] = useState(false);
  const [oversightData, setOversightData] = useState<any>(null);
  const [userConvoData, setUserConvoData] = useState<any>(null);
  const [loadingOversight, setLoadingOversight] = useState(false);
  const [selectedUserEmail, setSelectedUserEmail] = useState('');

  // Automatically open Settings modal when Settings tab is clicked in Navbar
  useEffect(() => {
    if (activeTab === 'Settings') {
      setShowSettingsModal(true);
    }
  }, [activeTab]);

  const closeSettings = () => {
    setShowSettingsModal(false);
    setActiveTab('Chat');
  };

  const openOversight = async () => {
    setShowSettingsModal(false);
    setShowOversightModal(true);
    setLoadingOversight(true);
    try {
      const bridgeUrl = process.env.NEXT_PUBLIC_LOCAL_BRIDGE_URL || 'http://127.0.0.1:8766';
      const res = await fetch(`${bridgeUrl}/api/aleena/users_overview`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) throw new Error(`Oversight request failed (${res.status}).`);
      const data = await res.json();
      setOversightData(data);
    } catch (e) {
      console.error("Oversight fetch error:", e);
    } finally {
      setLoadingOversight(false);
    }
  };

  const loadUserChats = async (userEmail: string) => {
    setSelectedUserEmail(userEmail);
    setUserConvoData(null);
    try {
      const bridgeUrl = process.env.NEXT_PUBLIC_LOCAL_BRIDGE_URL || 'http://localhost:8765';
      const res = await fetch(`${bridgeUrl}/api/aleena/user_conversations?user_email=${encodeURIComponent(userEmail)}`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (!res.ok) throw new Error(`Conversation request failed (${res.status}).`);
      const data = await res.json();
      setUserConvoData(data);
    } catch (e) {
      console.error("User convo fetch error:", e);
    }
  };

  if (!authReady) {
    return <main className="min-h-screen flex items-center justify-center bg-[#050510] text-white/70">Loading secure Aleena session…</main>;
  }

  if (!authToken || !authUser) {
    return <AuthScreen onAuthenticated={handleAuthenticated} />;
  }

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-[#050510]">
      {/* Top Navbar */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onOpenSettings={() => setShowSettingsModal(true)}
        userEmail={authUser?.email}
        onLogout={handleLogout}
      />

      {/* Main holographic workspace: avatar and conversation stay on the home screen. */}
      <main className="flex-1 min-h-0 flex gap-3 p-3 max-md:gap-2 max-md:p-2">
        <div className="hidden md:flex min-h-0">
          <SessionSidebar
            sessions={sessions}
            currentSessionId={currentSessionId}
            onSwitchSession={switchSession}
            onCreateSession={createSession}
            isCollapsed={sidebarCollapsed}
            onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
          />
        </div>

        <div className="flex-1 min-w-0 min-h-0 grid grid-cols-1 grid-rows-[minmax(230px,42vh)_minmax(250px,1fr)] xl:grid-cols-[minmax(0,1.08fr)_minmax(360px,0.92fr)] xl:grid-rows-1 gap-3 max-md:gap-2">
          <section className="relative min-h-0 min-w-0 flex flex-col overflow-hidden rounded-[26px] border border-cyan-200/15 bg-[#0b1020] shadow-[0_18px_60px_rgba(0,0,0,0.35)]">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_50%_78%,rgba(45,212,191,0.17),transparent_48%),radial-gradient(ellipse_at_78%_18%,rgba(129,140,248,0.17),transparent_42%),linear-gradient(145deg,rgba(255,255,255,0.04),transparent_50%)]" />
            <div className="relative z-20 flex h-14 shrink-0 items-center justify-between gap-3 border-b border-white/[0.07] px-5 max-sm:px-3">
              <div className="min-w-0">
                <div className="font-semibold tracking-wide text-white">Aleena</div>
                <div className="text-[10px] uppercase tracking-[0.2em] text-cyan-100/50">Holographic AI companion</div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="hidden rounded-full border border-cyan-200/20 bg-cyan-200/[0.06] px-3 py-1 text-[10px] font-medium text-cyan-100/80 sm:inline-flex">Gemini 3.8 Flash</span>
                <span className="flex items-center gap-2 rounded-full border border-white/10 bg-black/20 px-3 py-1.5 text-[10px] text-white/65">
                  <span className={`h-2 w-2 rounded-full ${isSpeaking ? 'bg-emerald-300 shadow-[0_0_10px_#6ee7b7]' : isListening ? 'bg-cyan-300 shadow-[0_0_10px_#67e8f9] animate-pulse' : isThinking ? 'bg-amber-300 animate-pulse' : 'bg-white/35'}`} />
                  {isSpeaking ? 'Speaking' : isListening ? 'Listening' : isThinking ? 'Thinking' : 'Ready'}
                </span>
              </div>
            </div>
            <div className="relative z-10 flex-1 min-h-0">
              <div className="pointer-events-none absolute left-1/2 top-[54%] h-[72%] w-[68%] -translate-x-1/2 -translate-y-1/2 rounded-[50%] border border-cyan-200/10 shadow-[0_0_65px_rgba(45,212,191,0.10),inset_0_0_55px_rgba(129,140,248,0.08)]" />
              <div className="pointer-events-none absolute left-1/2 top-[54%] h-[62%] w-[58%] -translate-x-1/2 -translate-y-1/2 rounded-[50%] border border-fuchsia-200/10" />
              <AvatarStage
                emotion={emotion}
                mouthOpen={mouthOpen}
                isSpeaking={isSpeaking}
                isListening={isListening}
                isThinking={isThinking}
                status={status}
              />
            </div>
            <div className="relative z-20 flex h-9 shrink-0 items-center justify-center border-t border-white/[0.06] bg-black/10 text-[10px] tracking-[0.18em] text-cyan-100/40">
              DRAG TO LOOK AROUND · LIVE AVATAR RESPONSE
            </div>
          </section>

          <section className="min-h-0 min-w-0 flex flex-col overflow-hidden rounded-[26px] border border-white/[0.09] bg-[#0a0d18]/90 shadow-[0_18px_60px_rgba(0,0,0,0.3)]">
            <ChatPanel
              messages={messages}
              streamingText={streamingText}
              isStreaming={isStreaming}
            />
            <InputBar
              onSend={handleSend}
              isListening={isListening}
              onMicToggle={handleMicToggle}
            />
          </section>
        </div>
      </main>

      {/* ⚙️ Aleena Settings Modal */}
      {showSettingsModal && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-md z-[100] flex items-center justify-center p-4">
          <div className="bg-[#171717] border border-white/10 rounded-2xl w-full max-w-lg p-6 shadow-2xl flex flex-col gap-5">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                ⚙️ Aleena AI System Settings
              </h3>
              <button
                onClick={closeSettings}
                className="text-gray-400 hover:text-white text-xl font-bold"
              >
                &times;
              </button>
            </div>

            <div className="space-y-3">
              <div className="p-3.5 bg-white/[0.04] rounded-xl border border-white/[0.06]">
                <div className="text-xs font-semibold text-gray-300">Model Name</div>
                <div className="text-sm font-bold text-accent2">Gemini 3.8 Flash</div>
              </div>

              <div className="p-3.5 bg-white/[0.04] rounded-xl border border-white/[0.06]">
                <div className="text-xs font-semibold text-gray-300">Master Owner Account</div>
                <div className="text-sm font-semibold text-purple-300">ay670744@gmail.com (Master Admin)</div>
              </div>

              {/* 👑 Master Oversight Section inside Settings */}
              <div className="p-4 bg-purple-900/20 border border-purple-500/30 rounded-xl space-y-3">
                <div className="text-sm font-bold text-purple-200 flex items-center gap-2">
                  👑 Aura AI Master Oversight Panel
                </div>
                <p className="text-xs text-gray-400">
                  View all registered Aura AI users, signup dates, activity metrics, and inspect full user chat conversations.
                </p>
                <button
                  onClick={openOversight}
                  className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-semibold text-xs shadow-lg shadow-purple-600/30 transition-all"
                >
                  📊 Show All Aura User Data & Chat History
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 👑 Aleena Master Users Oversight Modal */}
      {showOversightModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-lg z-[110] flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-[#18181b] border border-purple-500/30 rounded-2xl w-full max-w-3xl p-6 shadow-2xl flex flex-col gap-5 max-h-[85vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <h3 className="text-lg font-bold text-purple-300 flex items-center gap-2">
                👑 Aleena Master — Aura Users Analytics & Conversations Oversight
              </h3>
              <button
                onClick={() => setShowOversightModal(false)}
                className="text-gray-400 hover:text-white text-xl font-bold"
              >
                &times;
              </button>
            </div>

            {loadingOversight ? (
              <p className="text-sm text-gray-400">Fetching user analytics across isolated databases...</p>
            ) : oversightData ? (
              <div className="space-y-4">
                {/* Stats Grid */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="p-3.5 bg-purple-950/40 border border-purple-500/20 rounded-xl text-center">
                    <div className="text-2xl font-bold text-purple-300">{oversightData.total_users}</div>
                    <div className="text-[11px] text-gray-400">Total Users</div>
                  </div>
                  <div className="p-3.5 bg-emerald-950/40 border border-emerald-500/20 rounded-xl text-center">
                    <div className="text-2xl font-bold text-emerald-300">{oversightData.total_sessions}</div>
                    <div className="text-[11px] text-gray-400">Total Sessions</div>
                  </div>
                  <div className="p-3.5 bg-blue-950/40 border border-blue-500/20 rounded-xl text-center">
                    <div className="text-2xl font-bold text-blue-300">{oversightData.total_messages}</div>
                    <div className="text-[11px] text-gray-400">Total Messages</div>
                  </div>
                </div>

                {/* Users Table */}
                <div className="border border-white/10 rounded-xl overflow-x-auto">
                  <table className="w-full text-xs text-left text-gray-300">
                    <thead className="bg-white/5 text-gray-400 font-semibold border-b border-white/10">
                      <tr>
                        <th className="p-3">User Name</th>
                        <th className="p-3">Gmail Address</th>
                        <th className="p-3">Signup Date</th>
                        <th className="p-3">Activity</th>
                        <th className="p-3">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {oversightData.users_overview?.map((u: any, idx: number) => (
                        <tr key={idx} className="hover:bg-white/[0.02]">
                          <td className="p-3 font-semibold text-white">{u.name}</td>
                          <td className="p-3 text-gray-400">{u.email}</td>
                          <td className="p-3 text-gray-400">
                            {u.created_at !== 'N/A' ? new Date(u.created_at).toLocaleString() : 'N/A'}
                          </td>
                          <td className="p-3 text-purple-300">{u.sessions_count} sessions / {u.messages_count} msgs</td>
                          <td className="p-3">
                            <button
                              onClick={() => loadUserChats(u.email)}
                              className="px-2.5 py-1 bg-purple-600 hover:bg-purple-500 text-white font-medium rounded-lg text-[11px] transition-all"
                            >
                              👁️ View Chats
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* User Conversations Display */}
                {selectedUserEmail && (
                  <div className="p-4 bg-black/40 border border-white/10 rounded-xl space-y-3">
                    <h4 className="text-sm font-bold text-purple-300">
                      Full Conversations for {selectedUserEmail}
                    </h4>

                    {!userConvoData ? (
                      <p className="text-xs text-gray-400">Loading conversation history...</p>
                    ) : userConvoData.sessions?.length === 0 ? (
                      <p className="text-xs text-gray-400">No chat history found for this user.</p>
                    ) : (
                      <div className="space-y-3 max-h-60 overflow-y-auto pr-2">
                        {userConvoData.sessions?.map((sess: any, sIdx: number) => (
                          <div key={sIdx} className="p-3 bg-white/[0.03] border border-white/5 rounded-lg space-y-1.5">
                            <div className="text-xs font-semibold text-purple-200">
                              📌 {sess.title} ({new Date(sess.created_at).toLocaleString()})
                            </div>
                            {sess.messages?.map((msg: any, mIdx: number) => (
                              <div
                                key={mIdx}
                                className={`text-[11px] p-2 rounded-md ${
                                  msg.role === 'user'
                                    ? 'bg-blue-600/10 text-blue-300'
                                    : 'bg-purple-600/10 text-purple-300'
                                }`}
                              >
                                <b>{msg.role === 'user' ? 'User' : 'Aura AI'}:</b> {msg.content}
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
