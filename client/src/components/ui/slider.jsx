import React from 'react';

const Slider = ({ value = [0], onValueChange, max = 100, min = 0, step = 1, className = '', ...props }) => {
  const handleChange = (e) => {
    const newValue = parseInt(e.target.value);
    onValueChange([newValue]);
  };

  const percentage = ((value[0] - min) / (max - min)) * 100;

  return (
    <div className={`relative w-full ${className}`} {...props}>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value[0]}
        onChange={handleChange}
        className="sr-only"
        id="slider-input"
      />
      
      {/* Track */}
      <div className="relative h-2 w-full rounded-full bg-gray-200">
        {/* Progress */}
        <div 
          className="absolute left-0 top-0 h-full rounded-full bg-blue-600 transition-all duration-150"
          style={{ width: `${percentage}%` }}
        />
        
        {/* Thumb */}
        <div
          className="absolute top-1/2 h-4 w-4 rounded-full bg-white border-2 border-blue-600 shadow-sm transform -translate-y-1/2 cursor-pointer transition-transform hover:scale-110"
          style={{ left: `calc(${percentage}% - 8px)` }}
          onMouseDown={(e) => {
            const slider = e.currentTarget.parentElement.parentElement;
            const rect = slider.getBoundingClientRect();
            
            const handleMouseMove = (moveEvent) => {
              const x = moveEvent.clientX - rect.left;
              const percentage = Math.max(0, Math.min(100, (x / rect.width) * 100));
              const newValue = Math.round(((percentage / 100) * (max - min) + min) / step) * step;
              onValueChange([Math.max(min, Math.min(max, newValue))]);
            };
            
            const handleMouseUp = () => {
              document.removeEventListener('mousemove', handleMouseMove);
              document.removeEventListener('mouseup', handleMouseUp);
            };
            
            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
          }}
        />
      </div>
      
      {/* Click handler for track */}
      <div
        className="absolute inset-0 cursor-pointer"
        onClick={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const x = e.clientX - rect.left;
          const percentage = (x / rect.width) * 100;
          const newValue = Math.round(((percentage / 100) * (max - min) + min) / step) * step;
          onValueChange([Math.max(min, Math.min(max, newValue))]);
        }}
      />
    </div>
  );
};

export { Slider }; 