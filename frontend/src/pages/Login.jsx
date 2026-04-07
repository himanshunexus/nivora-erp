import React from 'react';
import { Input } from '../components/Input';
import { Button } from '../components/Button';

export function Login({ onSwitchToRegister }) {
  return (
    <div className="relative w-full max-w-md mx-auto z-10 animate-fade-in">
      <div className="relative p-8 rounded-2xl bg-white/5 backdrop-blur-xl border border-white/10 shadow-2xl overflow-hidden group">
        
        {/* Soft glowing accent */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-32 bg-blue-500/20 rounded-full blur-[80px] -z-10 group-hover:bg-purple-500/20 transition-colors duration-700"></div>

        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-white mb-2">Welcome back</h1>
          <p className="text-white/60 text-sm">Enter your details to continue</p>
        </div>

        <form className="space-y-6" onSubmit={(e) => e.preventDefault()}>
          <div className="space-y-4">
            <Input 
              type="email" 
              placeholder="name@example.com" 
              label="Email" 
            />
            <Input
              type="password"
              placeholder="Enter your password"
              label="Password"
            />
          </div>

          <Button type="submit">
            Continue
          </Button>
        </form>

        <div className="mt-8 text-center text-sm">
          <span className="text-white/60">New here? </span>
          <button 
            type="button" 
            onClick={onSwitchToRegister}
            className="text-white hover:text-blue-400 font-medium transition-colors"
          >
            Create account
          </button>
        </div>
      </div>
    </div>
  );
}
