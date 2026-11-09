'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';
import type { Message } from '@/types';

interface ChatBubbleProps {
  message: Message;
  index: number;
}

export function MessageContent({ content }: { content: string }) {
  return (
    <div className="assistant-markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}

export default function ChatBubble({ message, index }: ChatBubbleProps) {
  const isUser = message.role === 'user';
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  const time = mounted
    ? new Date(message.timestamp).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      })
    : '';

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, delay: Math.min(index * 0.035, 0.2) }}
      className={`flex w-full gap-3 ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      {!isUser && (
        <div className="mt-1 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-xl border border-cyan-300/20 bg-cyan-300/10 text-cyan-200">
          <Sparkles size={15} aria-label="Aleena" />
        </div>
      )}

      <div
        className={`min-w-0 max-w-[min(88%,48rem)] rounded-2xl px-4 py-3 sm:px-5 sm:py-4 ${
          isUser
            ? 'rounded-br-md border border-violet-300/20 bg-violet-500/15 text-white'
            : 'rounded-bl-md border border-white/[0.09] bg-[#111827]/75 text-slate-100 shadow-[0_8px_28px_rgba(0,0,0,0.12)]'
        }`}
      >
        {!isUser && (
          <div className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-cyan-200/75">
            Aleena
          </div>
        )}

        {isUser ? (
          <div className="whitespace-pre-wrap break-words text-sm leading-7 text-slate-100">
            {message.content}
          </div>
        ) : (
          <MessageContent content={message.content} />
        )}

        <div className={`mt-3 flex items-center gap-2 ${isUser ? 'justify-end' : 'justify-start'}`}>
          {mounted && <span className="text-[10px] text-slate-400/80">{time}</span>}
          {message.emotion && (
            <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[10px] text-slate-400">
              {message.emotion}
            </span>
          )}
          {message.model && (
            <span className="rounded-full border border-cyan-300/15 bg-cyan-300/[0.05] px-2 py-0.5 text-[10px] text-cyan-100/75">
              {message.model}
              {message.thinkingLevel ? ` · ${message.thinkingLevel}` : ''}
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}
