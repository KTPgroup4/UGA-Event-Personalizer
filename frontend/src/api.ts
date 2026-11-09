export interface Interest {
  id: string;
  name: string;
  children: {
    id: string;
    name: string;
  }[];
}

export interface Major {
  id: string;
  name: string;
}

export interface College {
  id: string;
  name: string;
  majors: Major[];
}

export interface OptionsResponse {
  interests: Interest[];
  colleges: College[];
  special_majors: Major[];
  major_rules: {
    min: number;
    max: number;
    co_major_ids: string[];
    exclusive_ids: string[];
  };
}

export interface BusyBlock {
  day: "mon" | "tue" | "wed" | "thu" |
       "fri" | "sat" | "sun";
  start: string;
  end: string;
}

export interface ProfileRequest {
  week_start: string;
  majors: string[];
  interests: string[];
  busy?: BusyBlock[];
}

export interface RecommendedEvent {
  id: string;
  title: string;
  description: string | null;
  start: string;
  end: string;
  end_is_estimated: boolean;
  location: string | null;
  organizer: string | null;
  url: string | null;
  interest_tags: string[];

  // New backend matching fields
  reason: string;
  match_kind: string;
  conflicts_with: string[];
}

export interface ScheduleResponse {
  week_start: string;

  // Supports the potential deck field names
  events?: RecommendedEvent[];
  deck?: RecommendedEvent[];
  cards?: RecommendedEvent[];

  target_picks: number;
}

// An error from the backend. `status` is the HTTP status (401 = not logged in, 409 = email taken...).
export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function apiRequest<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(path, options);

  if (!response.ok) {
    const error = await response.json().catch(() => null);

    let message = `HTTP ${response.status}`;

    if (Array.isArray(error?.detail)) {
      message = error.detail
        .map((item: { msg?: string }) =>
          item.msg ?? "Invalid input"
        )
        .join("; ");
    } else if (typeof error?.detail === "string") {
      message = error.detail;
    }

    throw new ApiError(message, response.status);
  }

  return response.json() as Promise<T>;
}

export function getOptions(): Promise<OptionsResponse> {
  return apiRequest<OptionsResponse>("/api/options");
}

export function getSchedules(
  profile: ProfileRequest
): Promise<ScheduleResponse> {
  return apiRequest<ScheduleResponse>("/api/schedules", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(profile),
  });
}

// ---------------------------------------------------------------- accounts

// What an account remembers (the questionnaire answers; the week is chosen each time).
export interface SavedPreferences {
  name: string;
  majors: string[];
  interests: string[];
  busy: BusyBlock[];
}

// An event the student added by hand ("end_time" is "" when there is no end).
export interface SavedPersonalEvent {
  id: string;
  title: string;
  date: string; // YYYY-MM-DD
  time: string; // HH:MM
  end_time: string;
}

// The calendar an account remembers. "saved" are cards from /api/schedules kept as received.
export interface SavedCalendar {
  saved: RecommendedEvent[];
  personal: SavedPersonalEvent[];
}

export interface AccountUser {
  email: string;
  preferences: SavedPreferences | null;
  calendar: SavedCalendar | null;
}

export interface AuthResponse {
  token: string;
  user: AccountUser;
}

function postJson(body: unknown, token?: string): RequestInit {
  return {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  };
}

export function signUp(
  email: string,
  password: string
): Promise<AuthResponse> {
  return apiRequest<AuthResponse>(
    "/api/auth/signup",
    postJson({ email, password })
  );
}

export function logIn(
  email: string,
  password: string
): Promise<AuthResponse> {
  return apiRequest<AuthResponse>(
    "/api/auth/login",
    postJson({ email, password })
  );
}

export function logOut(token: string): Promise<{ ok: boolean }> {
  return apiRequest<{ ok: boolean }>("/api/auth/logout", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function getMe(token: string): Promise<{ user: AccountUser }> {
  return apiRequest<{ user: AccountUser }>("/api/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function savePreferences(
  token: string,
  preferences: SavedPreferences
): Promise<{ preferences: SavedPreferences }> {
  return apiRequest<{ preferences: SavedPreferences }>(
    "/api/me/preferences",
    { ...postJson(preferences, token), method: "PUT" }
  );
}

// Sends the WHOLE calendar; the backend replaces the one it had.
export function saveCalendar(
  token: string,
  calendar: SavedCalendar
): Promise<{ calendar: SavedCalendar }> {
  return apiRequest<{ calendar: SavedCalendar }>(
    "/api/me/calendar",
    { ...postJson(calendar, token), method: "PUT" }
  );
}
