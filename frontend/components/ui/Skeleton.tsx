"use client";

interface SkeletonProps {
  className?: string;
  style?: React.CSSProperties;
}

export function Skeleton({ className = "", style }: SkeletonProps) {
  return <div className={`animate-shimmer rounded-lg ${className}`} style={style} />;
}

export function SkeletonText({ lines = 1, className = "" }: { lines?: number; className?: string }) {
  return (
    <div className={`space-y-2 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          className={i === lines - 1 && lines > 1 ? "h-3 w-3/4" : "h-3 w-full"}
        />
      ))}
    </div>
  );
}

export function SkeletonCard({ className = "" }: { className?: string }) {
  return <Skeleton className={`h-24 w-full ${className}`} />;
}

export function SkeletonCircle({ size = 10, className = "" }: { size?: number; className?: string }) {
  return (
    <Skeleton
      className={`rounded-full ${className}`}
      style={{ width: size * 4, height: size * 4 }}
    />
  );
}
