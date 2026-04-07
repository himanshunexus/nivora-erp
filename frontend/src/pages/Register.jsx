import React from 'react';
import { Input } from '../components/Input';
import { Button } from '../components/Button';

export function Register({ onSwitchToLogin }) {
  return (
    <div className="relative w-full max-w-md mx-auto z-10 animate-fade-in">
      <div className="relative p-8 rounded-2xl bg-white/5 backdrop-blur-xl border border-white/10 shadow-2xl overflow-hidden group">
        
        {/* Soft glowing accent */}
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-32 bg-purple-500/20 rounded-full blur-[80px] -z-10 group-hover:bg-blue-500/20 transition-colors duration-700"></div>

        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold tracking-tight text-white mb-2">Create workspace</h1>
          <p className="text-white/60 text-sm">Start managing your operations</p>
        </div>

        <form className="space-y-6" onSubmit={(e) => e.preventDefault()}>
          <div className="space-y-4">
            <Input
              type="text"
              placeholder="Jane Doe"
              label="Full Name"
            />
            <Input
              type="email"
              placeholder="name@example.com"
              label="Email"
            />
            <Input
              type="password"
              placeholder="Create a strong password"
              label="Password"
            />
            <Input
              type="text"
              placeholder="Acme Corp"
              label="Workspace Name"
            />
          </div>

          <Button type="submit">
            Get Started
          </Button>
        </form>

        <div className="mt-8 text-center text-sm">
          <span className="text-white/60">Already have an account? </span>
          <button 
            type="button" 
            onClick={onSwitchToLogin}
            className="text-white hover:text-purple-400 font-medium transition-colors"
          >
            Sign in
          </button>
        </div>
      </div>
    </div>
  );
}
