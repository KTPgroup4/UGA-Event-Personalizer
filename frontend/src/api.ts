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

    throw new Error(message);
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