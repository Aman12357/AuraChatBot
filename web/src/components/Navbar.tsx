'use client';

import React, { useState } from 'react';
import {
  MessageSquare,
  Brain,
  ListTodo,
  Settings,
  Volume2,
  VolumeX,
  Maximize

} from 'lucide-react';

const navItems = [
  { icon: MessageSquare, label: 'Chat' },
  { icon: Brain, label: 'Memory' },
  { icon: ListTodo, label: 'Tasks' },
  { icon: Settings, label: 'Settings' },
];

interface NavbarProps {
  activeTab?: string;
  setActiveTab?: (tab: string) => void;
  onOpenSettings?: () => void;
  userEmail?: string;
  onLogout?: () => void;
}

export default function Navbar({ activeTab = 'Chat', setActiveTab, onOpenSettings, userEmail, onLogout }: NavbarProps) {
  const [isMuted, setIsMuted] = useState(false);

  const handleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  };

  const handleTabClick = (label: string) => {
    if (setActiveTab) setActiveTab(label);
    if (label === 'Settings' && onOpenSettings) {
      onOpenSettings();
    }
  };

  return (
    <nav className="h-[60px] flex items-center justify-between px-5 backdrop-blur-2xl bg-black/[0.4] border-b border-white/[0.06] relative z-50">
      {/* Left: Brand */}
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-accent to-neon-blue flex items-center justify-center shadow-[0_0_20px_rgba(124,58,237,0.3)]">
          <span className="text-white font-bold text-sm">A</span>
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-text-main leading-tight">Aleena AI</span>
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-neon-green shadow-[0_0_6px_#00ffaa]" />
            <span className="text-[10px] text-text-dim">Master AI Companion</span>
          </div>
        </div>
      </div>

      {/* Center: Navigation Pills */}
      <div className="flex items-center gap-1 bg-white/[0.03] rounded-full p-1 border border-white/[0.06]">
        {navItems.map(({ icon: Icon, label }) => (
          <button
            key={label}
            onClick={() => handleTabClick(label)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200
              ${
                activeTab === label
                  ? 'bg-accent/20 text-accent2 shadow-[0_0_12px_rgba(124,58,237,0.15)]'
                  : 'text-text-dim hover:text-text-main hover:bg-white/[0.05]'
              }`}
          >
            <Icon size={14} />
            <span className="hidden sm:inline">{label}</span>
          </button>
        ))}
      </div>

      {/* Right: Account & Controls */}
      <div className="flex items-center gap-3">
        {userEmail && <span className="hidden max-w-[180px] truncate text-[11px] text-text-dim md:inline">{userEmail}</span>}
        {onLogout && (
          <button
            onClick={onLogout}
            className="rounded-lg border border-white/[0.08] bg-white/[0.05] px-3 py-1.5 text-xs text-text-dim transition-colors hover:text-text-main"
            title="Sign out"
          >
            Sign out
          </button>
        )}
        <button
          onClick={onOpenSettings}
          className="px-3 py-1.5 rounded-xl bg-purple-600/20 border border-purple-500/30 text-purple-300 text-xs font-medium hover:bg-purple-600/30 transition-all flex items-center gap-1.5"
          title="Open Aleena Master Settings"
        >
          <Settings size={14} />
          <span>⚙️ Settings</span>
        </button>

        <button
          onClick={() => setIsMuted(!isMuted)}
          className="w-8 h-8 rounded-lg bg-white/[0.05] border border-white/[0.08] flex items-center justify-center text-text-dim hover:text-text-main transition-colors"
        >
          {isMuted ? <VolumeX size={15} /> : <Volume2 size={15} />}
        </button>
        <button
          onClick={handleFullscreen}
          className="w-8 h-8 rounded-lg bg-white/[0.05] border border-white/[0.08] flex items-center justify-center text-text-dim hover:text-text-main transition-colors"
        >
          <Maximize size={15} />
        </button>
      </div>
    </nav>
  );
}
