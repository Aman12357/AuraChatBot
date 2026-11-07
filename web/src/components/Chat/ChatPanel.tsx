'use client';

import React, { useRef, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';
import ChatBubble, { MessageContent } from './ChatBubble';
import type { Message } from '@/types';

interface ChatPanelProps {
  messages: Message[];
  streamingText: string;
  isStreaming: boolean;
}

export default function ChatPanel({ messages, streamingText, isStreaming }: ChatPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamingText]);

  return (
    <div className="flex min-h-0 flex-1 flex-col bg-black/[0.28] backdrop-blur-xl">
      <div className="flex h-12 flex-shrink-0 items-center justify-between border-b border-white/[0.06] px-4">
        <div className="flex items-center gap-2 text-sm font-medium text-slate-100">
          <Sparkles size={15} className="text-cyan-200" />
          <span>Chat with Aleena</span>
        </div>
        <span className="rounded-full border border-white/[0.07] bg-white/[0.04] px-2.5 py-1 text-[10px] text-slate-400">
          {messages.length} messages
        </span>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-5 overflow-y-auto px-3 py-5 sm:px-5">
        {messages.map((msg, i) => (
          <ChatBubble key={msg.id} message={msg} index={i} />
        ))}

        {isStreaming && streamingText && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex w-full gap-3"
          >
            <div className="mt-1 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl border border-cyan-300/20 bg-cyan-300/10 text-cyan-200">
              <Sparkles size={15} />
            </div>
            <div className="min-w-0 max-w-[min(88%,48rem)] rounded-2xl rounded-bl-md border border-white/[0.09] bg-[#111827]/75 px-4 py-3 text-slate-100 shadow-[0_8px_28px_rgba(0,0,0,0.12)] sm:px-5 sm:py-4">
              <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-cyan-200/75">
                Aleena
              </div>
              <MessageContent content={streamingText} />
              <span className="ml-1 inline-block h-4 w-[2px] animate-pulse bg-cyan-200 align-middle" />
            </div>
          </motion.div>
        )}

        {isStreaming && !streamingText && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex gap-3"
          >
            <div className="mt-1 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl border border-cyan-300/20 bg-cyan-300/10 text-cyan-200">
              <Sparkles size={15} />
            </div>
            <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-md border border-white/[0.09] bg-[#111827]/75 px-4 py-3">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan-200/70" style={{ animationDelay: '0ms' }} />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan-200/70" style={{ animationDelay: '150ms' }} />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-cyan-200/70" style={{ animationDelay: '300ms' }} />
              <span className="ml-1 text-xs text-slate-400">Aleena is thinking</span>
            </div>
          </motion.div>
        )}
      </div>
    </div>
  );
}
