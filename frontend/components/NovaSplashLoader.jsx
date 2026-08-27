import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';

/**
 * NovaSplashLoader - Premium Website Opening/Loading Animation Component
 * 
 * @param {Object} props
 * @param {Function} [props.onComplete] - Callback fired when splash unmounts & dashboard is revealed
 * @param {boolean} [props.forcePlay] - Force animation playback (overrides sessionStorage)
 * @param {React.RefObject} [props.targetRef] - Optional DOM ref to top-left navbar logo for dynamic morph positioning
 */
export default function NovaSplashLoader({ onComplete, forcePlay = false, targetRef = null }) {
  const [isLoading, setIsLoading] = useState(true);
  const [targetOffset, setTargetOffset] = useState({ x: 0, y: 0 });
  const shouldReduceMotion = useReducedMotion();

  // 1. Persistence & Controls Setup
  useEffect(() => {
    // Check URL parameters for developer bypass (e.g., ?splash=true)
    const urlParams = new URLSearchParams(window.location.search);
    const splashParam = urlParams.get('splash');
    const isSplashForced = forcePlay || splashParam === 'true' || splashParam === '1' || splashParam === 'force';

    // Check session storage
    const hasPlayed = sessionStorage.getItem('nova_splash_played');

    if (hasPlayed && !isSplashForced) {
      setIsLoading(false);
      if (onComplete) onComplete();
      return;
    }

    // Prevent background scrolling while splash screen is active
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    // Calculate dynamic target coordinates for Step 5 morph transition
    const updateTargetCoordinates = () => {
      if (targetRef && targetRef.current) {
        const rect = targetRef.current.getBoundingClientRect();
        const centerX = window.innerWidth / 2;
        const centerY = window.innerHeight / 2;
        const targetCenterX = rect.left + rect.width / 2;
        const targetCenterY = rect.top + rect.height / 2;

        setTargetOffset({
          x: targetCenterX - centerX,
          y: targetCenterY - centerY,
        });
      } else {
        // Fallback offset targeting standard top-left navbar/sidebar logo area
        setTargetOffset({
          x: -window.innerWidth / 2 + 110,
          y: -window.innerHeight / 2 + 40,
        });
      }
    };

    updateTargetCoordinates();
    window.addEventListener('resize', updateTargetCoordinates);

    // Developer Keyboard Shortcut: Ctrl + Shift + S (or Cmd + Shift + S) to force replay
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.code === 'KeyS') {
        e.preventDefault();
        sessionStorage.removeItem('nova_splash_played');
        window.location.reload();
      }
    };
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.style.overflow = originalOverflow || 'unset';
      window.removeEventListener('resize', updateTargetCoordinates);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [forcePlay, onComplete, targetRef]);

  // Handle animation lifecycle completion
  const handleAnimationComplete = () => {
    sessionStorage.setItem('nova_splash_played', 'true');
    setIsLoading(false);
    document.body.style.overflow = 'unset';
    if (onComplete) onComplete();
  };

  // Simplified Reduced-Motion Sequence Specs
  if (shouldReduceMotion) {
    return (
      <AnimatePresence onExitComplete={handleAnimationComplete}>
        {isLoading && (
          <motion.div
            role="region"
            aria-label="Nova Credit AI Loading Screen"
            className="fixed inset-0 z-50 flex items-center justify-center bg-[#07090E] select-none"
            initial={{ opacity: 1 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.6, ease: 'easeInOut' }}
          >
            <div className="flex flex-col items-center text-center px-4">
              <div className="w-20 h-20 mb-6 relative flex items-center justify-center">
                <svg viewBox="0 0 80 80" fill="none" className="w-full h-full">
                  <path
                    d="M40 4L72 16V38C72 56 58 70 40 76C22 70 8 56 8 38V16L40 4Z"
                    stroke="#00F0FF"
                    strokeWidth="2.5"
                  />
                  <rect x="24" y="42" width="6" height="16" rx="1.5" fill="#00F0FF" />
                  <rect x="37" y="32" width="6" height="26" rx="1.5" fill="#00F0FF" />
                  <rect x="50" y="22" width="6" height="36" rx="1.5" fill="#00F0FF" />
                </svg>
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold tracking-[0.25em] text-white font-sans mb-2">
                NOVA
              </h1>
              <span className="text-xs sm:text-sm font-medium tracking-[0.2em] text-[#00F0FF]/90 uppercase mb-1">
                CREDIT AI
              </span>
              <span className="text-[11px] sm:text-xs text-slate-400 font-light tracking-wide">
                AI Powered Financial Intelligence
              </span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    );
  }

  return (
    <AnimatePresence>
      {isLoading && (
        <motion.div
          role="region"
          aria-label="Nova Credit AI Loading Screen"
          className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-[#07090E] select-none overflow-hidden"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          onAnimationComplete={handleAnimationComplete}
        >
          {/* Ambient Glow Background */}
          <div 
            className="absolute w-[500px] h-[500px] rounded-full pointer-events-none opacity-20 blur-[120px]"
            style={{
              background: 'radial-gradient(circle, rgba(0,240,255,0.4) 0%, rgba(7,9,14,0) 70%)'
            }}
          />

          {/* Main Content Container with Step 5 Morph Transition */}
          <motion.div
            className="relative z-10 flex flex-col items-center text-center px-4"
            initial={{ scale: 1, x: 0, y: 0, opacity: 1 }}
            animate={{
              scale: [1, 1, 1, 0.32],
              x: [0, 0, 0, targetOffset.x],
              y: [0, 0, 0, targetOffset.y],
              opacity: [1, 1, 1, 0]
            }}
            transition={{
              times: [0, 0.72, 0.82, 1],
              duration: 2.1,
              ease: [0.25, 1, 0.5, 1]
            }}
          >
            {/* Step 1 & 2: Nova Shield SVG & Growth Bars */}
            <div className="relative w-20 h-20 sm:w-24 sm:h-24 mb-6 flex items-center justify-center">
              <svg
                viewBox="0 0 80 80"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                className="w-full h-full overflow-visible drop-shadow-[0_0_15px_rgba(0,240,255,0.35)]"
              >
                {/* Step 1: Shield Outline Path Stroke Drawing */}
                <motion.path
                  d="M40 4L72 16V38C72 56 58 70 40 76C22 70 8 56 8 38V16L40 4Z"
                  stroke="#00F0FF"
                  strokeWidth="2.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  initial={{ pathLength: 0, opacity: 0 }}
                  animate={{ pathLength: 1, opacity: 1 }}
                  transition={{ duration: 0.6, ease: [0.65, 0, 0.35, 1] }}
                />

                {/* Step 2: Financial Growth Bars Scaling Up from Bottom */}
                <g>
                  <motion.rect
                    x="24"
                    y="42"
                    width="6"
                    height="16"
                    rx="1.5"
                    fill="#00F0FF"
                    initial={{ scaleY: 0, opacity: 0 }}
                    animate={{ scaleY: 1, opacity: 1 }}
                    style={{ transformOrigin: 'bottom' }}
                    transition={{ delay: 0.38, duration: 0.28, ease: [0.34, 1.56, 0.64, 1] }}
                  />
                  <motion.rect
                    x="37"
                    y="32"
                    width="6"
                    height="26"
                    rx="1.5"
                    fill="#00F0FF"
                    initial={{ scaleY: 0, opacity: 0 }}
                    animate={{ scaleY: 1, opacity: 1 }}
                    style={{ transformOrigin: 'bottom' }}
                    transition={{ delay: 0.48, duration: 0.28, ease: [0.34, 1.56, 0.64, 1] }}
                  />
                  <motion.rect
                    x="50"
                    y="22"
                    width="6"
                    height="36"
                    rx="1.5"
                    fill="#00F0FF"
                    initial={{ scaleY: 0, opacity: 0 }}
                    animate={{ scaleY: 1, opacity: 1 }}
                    style={{ transformOrigin: 'bottom' }}
                    transition={{ delay: 0.58, duration: 0.28, ease: [0.34, 1.56, 0.64, 1] }}
                  />
                </g>
              </svg>

              {/* Step 4: Subtle Light Sweep Gradient Effect */}
              <motion.div
                className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent pointer-events-none rounded-full blur-[1px]"
                initial={{ x: '-120%', opacity: 0 }}
                animate={{ x: '220%', opacity: [0, 1, 0] }}
                transition={{ delay: 1.15, duration: 0.45, ease: 'easeInOut' }}
              />
            </div>

            {/* Step 3: Wordmark & Tagline Slide & Fade */}
            <motion.h1
              className="text-2xl sm:text-3xl font-extrabold tracking-[0.28em] text-white font-sans mb-1.5 drop-shadow-[0_2px_10px_rgba(255,255,255,0.15)]"
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.72, duration: 0.38, ease: [0.22, 1, 0.36, 1] }}
            >
              NOVA
            </motion.h1>

            <motion.div
              className="flex flex-col items-center space-y-1"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.88, duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
            >
              <span className="text-xs sm:text-sm font-semibold tracking-[0.24em] text-[#00F0FF] uppercase drop-shadow-[0_0_8px_rgba(0,240,255,0.5)]">
                CREDIT AI
              </span>
              <span className="text-[11px] sm:text-xs text-slate-400 font-normal tracking-wider">
                AI Powered Financial Intelligence
              </span>
            </motion.div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
