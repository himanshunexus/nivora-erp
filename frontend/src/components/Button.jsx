import React from 'react';

export function Button({ children, onClick, type = 'button', fullWidth = true, ...props }) {
  return (
    <button
      type={type}
      onClick={onClick}
      className={`
        relative overflow-hidden group font-medium text-white px-6 py-3 rounded-xl
        bg-gradient-to-r from-blue-600 to-purple-600
        hover:from-blue-500 hover:to-purple-500
        active:scale-[0.98] transition-all duration-300
        shadow-[0_0_20px_rgba(59,130,246,0.3)]
        hover:shadow-[0_0_30px_rgba(147,51,234,0.5)]
        ${fullWidth ? 'w-full' : ''}
      `}
      {...props}
    >
      <div className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300 ease-in-out"></div>
      <span className="relative z-10">{children}</span>
    </button>
  );
}
