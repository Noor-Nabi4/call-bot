type WaveformProps = {
  className?: string;
  bars?: number;
};

/** Decorative voice waveform bars. */
export function Waveform({ className = "", bars = 28 }: WaveformProps) {
  const heights = [
    28, 46, 34, 62, 40, 72, 38, 58, 44, 68, 36, 54, 48, 70, 42, 60, 32, 66, 50,
    74, 40, 56, 34, 64, 46, 58, 30, 52,
  ];

  return (
    <div
      className={`flex h-10 items-end gap-[3px] ${className}`}
      aria-hidden="true"
    >
      {Array.from({ length: bars }, (_, index) => (
        <span
          key={index}
          className="w-[3px] rounded-full bg-gradient-to-t from-teal to-teal-bright opacity-80"
          style={{ height: `${heights[index % heights.length]}%` }}
        />
      ))}
    </div>
  );
}
