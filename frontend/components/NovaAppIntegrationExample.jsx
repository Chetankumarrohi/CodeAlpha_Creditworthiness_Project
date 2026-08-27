import React, { useRef, useState } from 'react';
import NovaSplashLoader from './NovaSplashLoader';

export default function NovaAppIntegrationExample() {
  const brandLogoRef = useRef(null);
  const [isSplashComplete, setIsSplashComplete] = useState(false);

  return (
    <div className="min-h-screen bg-[#07090E] text-slate-100 font-sans selection:bg-[#00F0FF]/20 selection:text-[#00F0FF]">
      {/* 1. Splash Screen Overlay Component */}
      <NovaSplashLoader 
        targetRef={brandLogoRef} 
        onComplete={() => setIsSplashComplete(true)} 
      />

      {/* 2. Main Dashboard Layout (Fades in / Revealed underneath) */}
      <div 
        className={`transition-opacity duration-700 ease-out flex ${
          isSplashComplete ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
      >
        {/* Sidebar */}
        <aside className="w-64 border-r border-slate-800 bg-[#0B0E17] p-6 flex flex-col min-h-screen">
          {/* Target Logo Anchor for Step 5 Morph */}
          <div ref={brandLogoRef} className="flex items-center space-x-3 mb-10">
            <div className="w-9 h-9 rounded-lg bg-[#00F0FF]/10 border border-[#00F0FF]/30 flex items-center justify-center">
              <svg viewBox="0 0 80 80" fill="none" className="w-6 h-6">
                <path d="M40 4L72 16V38C72 56 58 70 40 76C22 70 8 56 8 38V16L40 4Z" stroke="#00F0FF" strokeWidth="3" />
                <rect x="24" y="42" width="6" height="16" rx="1.5" fill="#00F0FF" />
                <rect x="37" y="32" width="6" height="26" rx="1.5" fill="#00F0FF" />
                <rect x="50" y="22" width="6" height="36" rx="1.5" fill="#00F0FF" />
              </svg>
            </div>
            <div>
              <div className="font-extrabold text-sm tracking-wider text-white">NOVA CREDIT</div>
              <div className="text-[10px] text-[#00F0FF] font-mono uppercase tracking-widest">v2.2 AI ENGINE</div>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="space-y-2 flex-1">
            <a href="#overview" className="flex items-center px-4 py-2.5 rounded-lg bg-[#00F0FF]/10 text-[#00F0FF] font-medium text-sm">
              Financial Overview
            </a>
            <a href="#assessment" className="flex items-center px-4 py-2.5 rounded-lg text-slate-400 hover:bg-slate-800/50 hover:text-white transition-colors text-sm">
              Credit Assessment
            </a>
            <a href="#portfolio" className="flex items-center px-4 py-2.5 rounded-lg text-slate-400 hover:bg-slate-800/50 hover:text-white transition-colors text-sm">
              Risk Analytics
            </a>
          </nav>

          {/* Developer Testing Shortcut Info */}
          <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 text-xs text-slate-400">
            <span className="text-[#00F0FF] font-mono font-semibold">Tip:</span> Press <kbd className="px-1.5 py-0.5 bg-slate-800 text-slate-200 rounded font-mono text-[10px]">Ctrl + Shift + S</kbd> to replay splash animation.
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 p-8">
          <header className="flex items-center justify-between pb-6 mb-8 border-b border-slate-800">
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">Institutional Underwriting Workspace</h1>
              <p className="text-sm text-slate-400 mt-1">Real-time credit risk decisioning and financial analytics engine.</p>
            </div>
            <div className="flex items-center space-x-3">
              <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                ● Live AI Engine
              </span>
            </div>
          </header>

          {/* Dashboard Stats Mockup */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div className="p-6 rounded-xl bg-[#0B0E17] border border-slate-800">
              <div className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">Total Underwritten</div>
              <div className="text-2xl font-bold text-white font-mono">₹48,250,000</div>
            </div>
            <div className="p-6 rounded-xl bg-[#0B0E17] border border-slate-800">
              <div className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">Avg Risk Score</div>
              <div className="text-2xl font-bold text-[#00F0FF] font-mono">742 / 900</div>
            </div>
            <div className="p-6 rounded-xl bg-[#0B0E17] border border-slate-800">
              <div className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">Approval Rate</div>
              <div className="text-2xl font-bold text-emerald-400 font-mono">68.4%</div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}
