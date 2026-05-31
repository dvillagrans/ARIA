import Link from "next/link";
import { Bot, ArrowLeft } from "lucide-react";

export default function NotFound() {
  return (
    <main className="flex flex-col items-center justify-center min-h-screen bg-bg-root text-text-primary px-4">
      <div className="flex flex-col items-center gap-6 text-center max-w-md">
        <div className="w-20 h-20 rounded-2xl bg-accent/10 flex items-center justify-center">
          <Bot className="h-10 w-10 text-accent" />
        </div>

        <div>
          <h1 className="text-6xl font-bold text-accent mb-2">404</h1>
          <h2 className="text-xl font-semibold text-text-primary mb-2">
            Page not found
          </h2>
          <p className="text-text-secondary text-sm leading-relaxed">
            The page you&apos;re looking for doesn&apos;t exist or has been
            moved. Let&apos;s get you back on track.
          </p>
        </div>

        <Link
          href="/"
          className="flex items-center gap-2 px-5 py-2.5 bg-accent hover:bg-accent-hover text-white text-sm font-medium rounded-xl transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to ARIA
        </Link>
      </div>
    </main>
  );
}
