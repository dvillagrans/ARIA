/**
 * API routes — Cache-Control header tests.
 *
 * Verifies that read-only proxy routes return proper cache headers
 * so the browser can avoid redundant requests.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockGetUser = vi.fn();

vi.mock("@/lib/supabase/server", () => ({
  createClient: () =>
    Promise.resolve({
      auth: { getUser: mockGetUser },
    }),
}));

// Mock global fetch for FastAPI calls
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

// ---------------------------------------------------------------------------
// Imports (after mocks)
// ---------------------------------------------------------------------------

const { GET: briefingGET } = await import("@/app/api/briefing/route");
const { GET: remindersDueGET } = await import("@/app/api/reminders/due/route");

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("API cache headers", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetUser.mockResolvedValue({
      data: { user: { id: "user-123" } },
      error: null,
    });
  });

  describe("GET /api/briefing", () => {
    it("returns Cache-Control with 5-minute max-age", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            content: "Good morning",
            cached: true,
            stale: false,
            date: "2026-01-01",
            generated_at: "2026-01-01T08:00:00Z",
          }),
      });

      const response = await briefingGET();
      const cacheHeader = response.headers.get("Cache-Control");

      expect(cacheHeader).toBeTruthy();
      expect(cacheHeader).toContain("max-age=300");
      expect(cacheHeader).toContain("private");
    });

    it("returns stale-while-revalidate for background refresh", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: () =>
          Promise.resolve({
            content: "Good morning",
            cached: false,
            stale: false,
            date: "2026-01-01",
            generated_at: "2026-01-01T08:00:00Z",
          }),
      });

      const response = await briefingGET();
      const cacheHeader = response.headers.get("Cache-Control");

      expect(cacheHeader).toContain("stale-while-revalidate");
    });
  });

  describe("GET /api/reminders/due", () => {
    it("returns Cache-Control with 30-second max-age", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve([]),
      });

      const response = await remindersDueGET();
      const cacheHeader = response.headers.get("Cache-Control");

      expect(cacheHeader).toBeTruthy();
      expect(cacheHeader).toContain("max-age=30");
      expect(cacheHeader).toContain("private");
    });

    it("returns stale-while-revalidate for background refresh", async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        status: 200,
        json: () => Promise.resolve([]),
      });

      const response = await remindersDueGET();
      const cacheHeader = response.headers.get("Cache-Control");

      expect(cacheHeader).toContain("stale-while-revalidate");
    });
  });

  describe("auth handling", () => {
    it("returns 401 for unauthenticated briefing request", async () => {
      mockGetUser.mockResolvedValue({
        data: { user: null },
        error: { message: "Not authenticated" },
      });

      const response = await briefingGET();
      expect(response.status).toBe(401);
    });

    it("returns 401 for unauthenticated reminders/due request", async () => {
      mockGetUser.mockResolvedValue({
        data: { user: null },
        error: { message: "Not authenticated" },
      });

      const response = await remindersDueGET();
      expect(response.status).toBe(401);
    });

    it("returns 503 when FastAPI is unreachable (briefing)", async () => {
      mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));

      const response = await briefingGET();
      expect(response.status).toBe(503);
    });

    it("returns 503 when FastAPI is unreachable (reminders/due)", async () => {
      mockFetch.mockRejectedValue(new Error("ECONNREFUSED"));

      const response = await remindersDueGET();
      expect(response.status).toBe(503);
    });
  });
});
