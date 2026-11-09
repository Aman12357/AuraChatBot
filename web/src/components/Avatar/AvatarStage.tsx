'use client';

import React, { Suspense, useEffect, useState, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Environment, Html } from '@react-three/drei';
import * as THREE from 'three';
import { DigitalHuman } from './DigitalHuman';
import { avatarController } from './controllers/AvatarController';
import { Room3D } from './Room3D';
import { RoomLighting } from './RoomLighting';
import ContextMenu from './ContextMenu';
import { CityView } from './CityView';
import { useCinematicCamera } from './hooks/useCinematicCamera';

interface EmojiParticle {
  id: string;
  emoji: string;
  pos: [number, number, number];
  speed: number;
  wobbleSpeed: number;
  wobbleRange: number;
  phase: number;
  scale: number;
  life: number;
  decay: number;
}

const EMOJI_MAP: Record<string, string[]> = {
  neutral: ['✨'],
  happy: ['😊', '😄', '✨', '🌸', '💖'],
  excited: ['🎉', '✨', '⭐', '🎊', '🤩'],
  thinking: ['🤔', '💭', '❓', '💡', '🧠'],
  curious: ['👀', '❓', '🔍', '💡'],
  listening: ['🎧', '🎵', '🎶', '🔵'],
  talking: ['💬', '🔊', '✨'],
  sleeping: ['😴', '💤', '🌙', '⭐'],
  waiting: ['⏳', '💤', '⏰'],
  confused: ['😵', '❓', '🌀'],
  sad: ['🌧️', '💧', '☁️', '😔'],
  angry: ['😤', '💢', '🔥', '⚡'],
  shy: ['😊', '🌸', '💖', '🫣'],
  love: ['❤️', '💕', '💞', '🌹', '✨'],
  celebration: ['🎉', '✨', '⭐', '🎊', '🥳']
};

function EmojiParticles({ emotion }: { emotion: string }) {
  const [particles, setParticles] = useState<EmojiParticle[]>([]);
  const lastEmotion = useRef(emotion);

  useEffect(() => {
    if (emotion && emotion !== lastEmotion.current) {
      lastEmotion.current = emotion;
      
      const emojiPool = EMOJI_MAP[emotion] || EMOJI_MAP.neutral;
      const newParticles: EmojiParticle[] = [];
      const count = 12;
      
      for (let i = 0; i < count; i++) {
        const emoji = emojiPool[Math.floor(Math.random() * emojiPool.length)];
        newParticles.push({
          id: `${Date.now()}-${i}-${Math.random()}`,
          emoji,
          pos: [
            (Math.random() - 0.5) * 1.2,
            -0.3 + Math.random() * 0.6,
            -0.4
          ],
          speed: 0.35 + Math.random() * 0.45,
          wobbleSpeed: 1.5 + Math.random() * 2.0,
          wobbleRange: 0.08 + Math.random() * 0.12,
          phase: Math.random() * 100,
          scale: 0.6 + Math.random() * 0.6,
          life: 1.0,
          decay: 0.18 + Math.random() * 0.12
        });
      }
      
      setParticles((prev) => [...prev, ...newParticles].slice(-40));
    }
  }, [emotion]);

  useFrame((state, delta) => {
    setParticles((prev) => {
      return prev
        .map((p) => {
          const wobble = Math.sin(state.clock.elapsedTime * p.wobbleSpeed + p.phase) * p.wobbleRange * delta;
          return {
            ...p,
            pos: [p.pos[0] + wobble, p.pos[1] + p.speed * delta, p.pos[2]] as [number, number, number],
            life: p.life - p.decay * delta
          };
        })
        .filter((p) => p.life > 0);
    });
  });

  return (
    <>
      {particles.map((p) => (
        <Html
          key={p.id}
          position={p.pos}
          center
          distanceFactor={1.2}
          style={{
            pointerEvents: 'none',
            userSelect: 'none',
            fontSize: '24px',
            transform: `scale(${p.scale})`,
            opacity: p.life,
            transition: 'opacity 0.1s ease',
            filter: 'drop-shadow(0 4px 6px rgba(0,0,0,0.15))'
          }}
        >
          {p.emoji}
        </Html>
      ))}
    </>
  );
}

function BackgroundParticles({ emotion }: { emotion: string }) {
  const pointsRef = useRef<any>();
  const count = 120;
  
  const positions = React.useMemo(() => {
    const pos = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      pos[i * 3] = (Math.random() - 0.5) * 6;
      pos[i * 3 + 1] = Math.random() * 4 - 2;
      pos[i * 3 + 2] = (Math.random() - 0.5) * 5 - 2;
    }
    return pos;
  }, [emotion]);

  useFrame((state, delta) => {
    if (!pointsRef.current) return;
    const positionsArray = pointsRef.current.geometry.attributes.position.array;
    const time = state.clock.getElapsedTime();

    for (let i = 0; i < count; i++) {
      const i3 = i * 3;
      if (emotion === 'sad') {
        positionsArray[i3 + 1] -= delta * 3.5;
        if (positionsArray[i3 + 1] < -2) {
          positionsArray[i3 + 1] = 2;
          positionsArray[i3] = (Math.random() - 0.5) * 6;
        }
      } else if (emotion === 'sleeping') {
        positionsArray[i3 + 1] += Math.sin(time * 0.15 + i) * 0.0006;
        positionsArray[i3] += Math.cos(time * 0.1 + i) * 0.0006;
      } else if (emotion === 'excited' || emotion === 'celebration') {
        positionsArray[i3 + 1] += delta * 1.8;
        if (positionsArray[i3 + 1] > 2) {
          positionsArray[i3 + 1] = -2;
          positionsArray[i3] = (Math.random() - 0.5) * 6;
        }
      } else {
        positionsArray[i3 + 1] += delta * 0.2;
        if (positionsArray[i3 + 1] > 2) {
          positionsArray[i3 + 1] = -2;
          positionsArray[i3] = (Math.random() - 0.5) * 6;
        }
      }
    }
    pointsRef.current.geometry.attributes.position.needsUpdate = true;
  });

  let color = '#7c3aed';
  if (emotion === 'happy') color = '#ff85a2';
  if (emotion === 'thinking') color = '#00f2ff';
  if (emotion === 'sad') color = '#0066ff';
  if (emotion === 'sleeping') color = '#ffea00';
  if (emotion === 'excited' || emotion === 'celebration') color = '#ff0077';
  if (emotion === 'love') color = '#ff0055';
  if (emotion === 'curious') color = '#ffae00';
  if (emotion === 'listening') color = '#00f2ff';
  if (emotion === 'talking') color = '#00ffaa';
  if (emotion === 'waiting') color = '#ffaa00';
  if (emotion === 'confused') color = '#d946ef';
  if (emotion === 'angry') color = '#ef4444';
  if (emotion === 'shy') color = '#fda4af';

  return (
    <points ref={pointsRef}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
      </bufferGeometry>
      <pointsMaterial
        size={0.07}
        color={color}
        transparent
        opacity={0.65}
        sizeAttenuation
      />
    </points>
  );
}

function SceneDirector() {
  useCinematicCamera();
  return null;
}

interface AvatarStageProps {
  emotion: string;
  mouthOpen: number;
  isSpeaking: boolean;
  isListening: boolean;
  isThinking: boolean;
  status: string;
}

export default function AvatarStage({
  emotion,
  mouthOpen,
  isSpeaking,
  isListening,
  isThinking,
  status,
}: AvatarStageProps) {
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; target: string } | null>(null);
  
  // Synchronize React state hooks with the AvatarController singleton
  useEffect(() => {
    avatarController.setEmotion(emotion || 'neutral');
    avatarController.talking = isSpeaking;
    avatarController.listening = isListening;
    
    if (isThinking) {
      avatarController.thinking = true;
      avatarController.navigateTo('desk', 'sitting');
      avatarController.inactivityTime = 0;
    } else {
      avatarController.thinking = false;
      // Return to center when done thinking and greeting/listening/speaking
      if ((avatarController.isSitting || avatarController.isLyingDown) && !isThinking) {
        avatarController.navigateTo('center');
      }
    }
  }, [emotion, isSpeaking, isListening, isThinking]);

  // Handle real-time mouth opening lip-sync
  useEffect(() => {
    if (isSpeaking) {
      avatarController.setViseme('aa', mouthOpen);
    } else {
      avatarController.setViseme('aa', 0);
    }
  }, [mouthOpen, isSpeaking]);

  // Dynamic lighting color map
  const getLighting = (emo: string) => {
    switch (emo) {
      case 'happy':
      case 'shy':
        return { ambient: '#ffe6eb', key: '#fff0f3', rim: '#ffccd5', intensity: 1.6 };
      case 'excited':
      case 'celebration':
        return { ambient: '#ffffff', key: '#ffffff', rim: '#ffffcc', intensity: 2.0 };
      case 'thinking':
      case 'confused':
        return { ambient: '#e6f7ff', key: '#e6f7ff', rim: '#91d5ff', intensity: 1.3 };
      case 'love':
        return { ambient: '#ffe6f0', key: '#ffb3d9', rim: '#ff007f', intensity: 1.7 };
      case 'sleeping':
        return { ambient: '#0a0a20', key: '#1a1a50', rim: '#3b3bff', intensity: 0.5 };
      case 'sad':
        return { ambient: '#e6f0ff', key: '#b3d1ff', rim: '#3385ff', intensity: 0.8 };
      case 'angry':
        return { ambient: '#ffe6e6', key: '#ffb3b3', rim: '#ff3333', intensity: 1.8 };
      default:
        return { ambient: '#ebdcfc', key: '#f5f0ff', rim: '#b08fff', intensity: 1.5 };
    }
  };

  return (
    <div className="absolute inset-0 flex flex-col">
      {/* Three.js Canvas */}
      <div className="absolute inset-0">
        <Canvas
          camera={{ position: [0, 1.2, 2.5], fov: 50 }}
          shadows
          gl={{ antialias: true, alpha: true, preserveDrawingBuffer: true }}
        >
          {/* Dynamic Lighting & Environment */}
          <RoomLighting emotion={emotion || 'neutral'} />
          {/*
          <Room3D 
            emotion={emotion || 'neutral'} 
            onObjectClick={(target, x, y) => {
              setContextMenu({ x, y, target });
            }}
          />
          <CityView />
          */}
          
          {/* Cinematic Camera Controller */}
          <SceneDirector />

          {/* Emoji Particles overlay */}
          <EmojiParticles emotion={emotion || 'neutral'} />

          {/* VRM model component */}
          <Suspense
            fallback={
              <Html center>
                <div className="flex flex-col items-center gap-3">
                  <div className="w-10 h-10 rounded-full border-2 border-accent/30 border-t-accent animate-spin" />
                  <span className="text-xs text-text-dim">Loading 3D Digital Human...</span>
                </div>
              </Html>
            }
          >
            <DigitalHuman />
          </Suspense>
        </Canvas>
      </div>

      {/* Floating Emotion Overlay (Top Right) */}
      <div className="absolute top-4 right-4 z-10 pointer-events-none">
        <div className="backdrop-blur-xl bg-white/[0.04] border border-white/[0.08] px-4 py-2.5 rounded-2xl flex items-center gap-3 shadow-[0_8px_24px_rgba(0,0,0,0.4)]">
          <span
            className="text-2xl animate-bounce"
            style={{ animationDuration: '2s' }}
          >
            {(EMOJI_MAP[emotion || 'neutral'] || EMOJI_MAP.neutral)[0]}
          </span>
          <div className="flex flex-col">
            <span className="text-[11px] font-bold tracking-wider uppercase text-white/80">
              {emotion || 'neutral'}
            </span>
            <span className="text-[9px] text-white/40 capitalize">
              {isSpeaking ? 'Speaking...' : isListening ? 'Listening...' : isThinking ? 'Thinking...' : 'Idle'}
            </span>
          </div>
        </div>
      </div>

      {/* Context Menu Action Overlay */}
      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          target={contextMenu.target}
          onClose={() => setContextMenu(null)}
          onSelectAction={(action, arg) => {
            if (action === 'sit') {
              avatarController.sit(arg || 'chair');
            } else if (action === 'sleep') {
              avatarController.sleep();
            } else if (action === 'walk') {
              avatarController.moveTo(arg || 'center');
            } else if (action === 'readBook') {
              avatarController.interact('book');
            } else if (action === 'lookOutside') {
              avatarController.lookOutside();
            } else if (action === 'pickUpMug') {
              avatarController.interact('mug');
            } else if (action === 'putMugBack') {
              avatarController.interact(null);
            } else if (action === 'openWindow') {
              avatarController.interact('window');
            } else if (action === 'closeCurtains') {
              avatarController.interact('curtains');
            }
          }}
        />
      )}
    </div>
  );
}
