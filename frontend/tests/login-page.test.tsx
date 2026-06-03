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

const mockPush = vi.fn();
const mockSignInWithPassword = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
  }),
}));

vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: {
      signInWithPassword: mockSignInWithPassword,
    },
  }),
}));

// Import component AFTER mock registration
const { default: LoginPage } = await import("@/app/(auth)/login/page");

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: successful login
    mockSignInWithPassword.mockResolvedValue({ error: null });
  });

  it("renders the Welcome heading", () => {
    render(<LoginPage />);
    expect(screen.getByRole("heading", { name: /welcome back/i })).toBeInTheDocument();
  });

  it("renders an email input", () => {
    render(<LoginPage />);
    expect(
      screen.getByPlaceholderText(/you@example\.com/i)
    ).toBeInTheDocument();
  });

  it("renders a password input", () => {
    render(<LoginPage />);
    expect(
      screen.getByPlaceholderText(/••••••••/i)
    ).toBeInTheDocument();
  });

  it("renders the sign in button", () => {
    render(<LoginPage />);
    expect(
      screen.getByRole("button", { name: /sign in/i })
    ).toBeInTheDocument();
  });

  it("navigates to /chat on successful login", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(
      screen.getByPlaceholderText(/you@example\.com/i),
      "test@example.com"
    );
    await user.type(
      screen.getByPlaceholderText(/••••••••/i),
      "password123"
    );
    await user.click(
      screen.getByRole("button", { name: /sign in/i })
    );

    expect(mockSignInWithPassword).toHaveBeenCalledWith({
      email: "test@example.com",
      password: "password123",
    });
    expect(mockPush).toHaveBeenCalledWith("/chat");
  });

  it("shows error message when auth fails", async () => {
    mockSignInWithPassword.mockResolvedValue({
      error: { message: "Invalid credentials" },
    });

    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(
      screen.getByPlaceholderText(/you@example\.com/i),
      "bad@example.com"
    );
    await user.type(
      screen.getByPlaceholderText(/••••••••/i),
      "wrongpassword"
    );
    await user.click(
      screen.getByRole("button", { name: /sign in/i })
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      /invalid email or password/i
    );
  });

  it("does not navigate on failed auth", async () => {
    mockSignInWithPassword.mockResolvedValue({
      error: { message: "Invalid credentials" },
    });

    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(
      screen.getByPlaceholderText(/you@example\.com/i),
      "bad@example.com"
    );
    await user.type(
      screen.getByPlaceholderText(/••••••••/i),
      "wrong"
    );
    await user.click(
      screen.getByRole("button", { name: /sign in/i })
    );

    // Wait for the error to appear (confirms async flow completed).
    await screen.findByRole("alert");

    expect(mockPush).not.toHaveBeenCalled();
  });
});
