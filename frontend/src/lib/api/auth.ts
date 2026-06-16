const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

export interface UserInfo {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
  role: "admin" | "user";
}

// POST /api/v1/auth/login — form-encoded; "username" field holds the email value
export async function loginApi(email: string, password: string): Promise<UserInfo> {
  const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: email, password }).toString(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { detail?: string };
    throw new Error(err.detail ?? "Login failed");
  }
  const data = await res.json() as { access_token: string; token_type: string; user: UserInfo };
  localStorage.setItem("token", data.access_token);
  return data.user;
}

// POST /api/v1/auth/register
export async function registerApi(
  username: string,
  email: string,
  password: string,
): Promise<UserInfo> {
  const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { detail?: string };
    throw new Error(err.detail ?? "Registration failed");
  }
  return res.json() as Promise<UserInfo>;
}

// Clear local session — no server call needed with stateless JWT
export function logoutApi(): void {
  localStorage.removeItem("token");
  localStorage.removeItem("user");
}
