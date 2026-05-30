/**
 * Login page — render tests.
 *
 * Tests verify the static render shape and interaction behavior without
 * exercising the real Supabase Auth flow (network-free).
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, describe, it, expect, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Module-level mock factory — every test shares the same mock instance
// ---------------------------------------------------------------------------
const mockSignInWithOtp = vi.fn();

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      signInWithOtp: mockSignInWithOtp,
    },
  }),
}));

// Import component AFTER mock registration
const { default: LoginPage } = await import("@/app/(auth)/login/page");

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: successful OTP send
    mockSignInWithOtp.mockResolvedValue({ error: null });
  });

  it("renders the ARIA heading", () => {
    render(<LoginPage />);
    expect(screen.getByRole("heading", { name: /aria/i })).toBeInTheDocument();
  });

  it("renders an email input", () => {
    render(<LoginPage />);
    expect(
      screen.getByPlaceholderText(/you@example\.com/i)
    ).toBeInTheDocument();
  });

  it("renders the submit button", () => {
    render(<LoginPage />);
    expect(
      screen.getByRole("button", { name: /send magic link/i })
    ).toBeInTheDocument();
  });

  it("shows success message after valid submission", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(
      screen.getByPlaceholderText(/you@example\.com/i),
      "test@example.com"
    );
    await user.click(
      screen.getByRole("button", { name: /send magic link/i })
    );

    expect(await screen.findByRole("status")).toHaveTextContent(
      /check your inbox/i
    );
  });

  it("shows error message when auth fails", async () => {
    mockSignInWithOtp.mockResolvedValue({
      error: { message: "Rate limit exceeded" },
    });

    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(
      screen.getByPlaceholderText(/you@example\.com/i),
      "test@example.com"
    );
    await user.click(
      screen.getByRole("button", { name: /send magic link/i })
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /rate limit exceeded/i
    );
  });
});
