/**
 * Middleware (proxy.ts + updateSession) — performance optimization tests.
 *
 * Verifies that:
 * 1. API routes skip the expensive getUser() call entirely.
 * 2. Non-API routes still call getUser() for session refresh.
 * 3. Unauthenticated users are redirected away from protected page routes.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import type { NextRequest } from "next/server";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockGetUser = vi.fn();

vi.mock("@supabase/ssr", () => ({
  createServerClient: () => ({
    auth: { getUser: mockGetUser },
  }),
}));

// Mock NextResponse.next and NextResponse.redirect so we don't need real
// request headers (Next.js 16's internals require a full Headers instance).
const mockNextResponse = {
  cookies: { set: vi.fn() },
  headers: new Headers(),
  status: 200,
};

vi.mock("next/server", async () => {
  const actual = await vi.importActual<typeof import("next/server")>("next/server");
  return {
    ...actual,
    NextResponse: {
      ...actual.NextResponse,
      next: vi.fn(() => mockNextResponse),
      redirect: vi.fn((url: URL) => ({
        status: 307,
        headers: new Headers({ location: url.toString() }),
      })),
    },
  };
});

// Import after mocks are registered.
const { updateSession } = await import("@/lib/supabase/middleware");
const { NextResponse } = await import("next/server");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeRequest(pathname: string) {
  const url = new URL(`http://localhost:3000${pathname}`);
  return {
    nextUrl: { ...url, clone: () => new URL(url.toString()), pathname: url.pathname },
    cookies: { getAll: () => [], set: vi.fn() },
  } as unknown as NextRequest;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("updateSession", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --- API routes: skip getUser() entirely ---

  it("skips getUser() for /api/chat", async () => {
    await updateSession(makeRequest("/api/chat"));
    expect(mockGetUser).not.toHaveBeenCalled();
  });

  it("skips getUser() for /api/briefing", async () => {
    await updateSession(makeRequest("/api/briefing"));
    expect(mockGetUser).not.toHaveBeenCalled();
  });

  it("skips getUser() for /api/reminders/due", async () => {
    await updateSession(makeRequest("/api/reminders/due"));
    expect(mockGetUser).not.toHaveBeenCalled();
  });

  it("skips getUser() for /api/projects", async () => {
    await updateSession(makeRequest("/api/projects"));
    expect(mockGetUser).not.toHaveBeenCalled();
  });

  it("skips getUser() for nested API routes like /api/projects/123", async () => {
    await updateSession(makeRequest("/api/projects/abc-123"));
    expect(mockGetUser).not.toHaveBeenCalled();
  });

  it("returns NextResponse.next() for API routes (no redirect)", async () => {
    const response = await updateSession(makeRequest("/api/chat"));
    expect(NextResponse.next).toHaveBeenCalled();
    expect(response).toBe(mockNextResponse);
  });

  // --- Non-API routes: getUser() is called ---

  it("calls getUser() for /chat (protected page)", async () => {
    mockGetUser.mockResolvedValue({
      data: { user: { id: "user-1" } },
    });

    await updateSession(makeRequest("/chat"));

    expect(mockGetUser).toHaveBeenCalledTimes(1);
  });

  it("calls getUser() for /profile (protected page)", async () => {
    mockGetUser.mockResolvedValue({
      data: { user: { id: "user-1" } },
    });

    await updateSession(makeRequest("/profile"));

    expect(mockGetUser).toHaveBeenCalledTimes(1);
  });

  it("calls getUser() for / (root)", async () => {
    mockGetUser.mockResolvedValue({
      data: { user: { id: "user-1" } },
    });

    await updateSession(makeRequest("/"));

    expect(mockGetUser).toHaveBeenCalledTimes(1);
  });

  // --- Redirect behavior for page routes ---

  it("redirects unauthenticated user to /login from /chat", async () => {
    mockGetUser.mockResolvedValue({
      data: { user: null },
    });

    await updateSession(makeRequest("/chat"));

    expect(NextResponse.redirect).toHaveBeenCalled();
    const redirectUrl = (NextResponse.redirect as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as URL;
    expect(redirectUrl.pathname).toBe("/login");
  });

  it("does NOT redirect from /login even if unauthenticated", async () => {
    mockGetUser.mockResolvedValue({
      data: { user: null },
    });

    await updateSession(makeRequest("/login"));

    expect(NextResponse.redirect).not.toHaveBeenCalled();
  });

  it("does NOT redirect authenticated user from /chat", async () => {
    mockGetUser.mockResolvedValue({
      data: { user: { id: "user-1" } },
    });

    await updateSession(makeRequest("/chat"));

    expect(NextResponse.redirect).not.toHaveBeenCalled();
  });
});
