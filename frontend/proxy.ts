import { type NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";

export async function proxy(request: NextRequest) {
  return await updateSession(request);
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization)
     * - favicon.ico and public assets with file extensions
     * - /login (auth page — no session needed)
     * - /manifest.webmanifest (static PWA manifest)
     * - /icons/* (PWA icons)
     */
    "/((?!_next/static|_next/image|favicon.ico|login|manifest\\.webmanifest|icons|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
