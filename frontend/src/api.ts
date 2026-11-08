export interface OptionsResponse {
  interests: { id: string; name: string; children: { id: string; name: string }[] }[];
  colleges: { id: string; name: string; majors: { id: string; name: string }[] }[];
  special_majors: { id: string; name: string }[];
  major_rules: { min: number; max: number; co_major_ids: string[]; exclusive_ids: string[] };
}
export interface ProfileRequest {
  week_start: string;
  majors: string[];
  interests: string[];
  busy?: { day: "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun"; start: string; end: string }[];
}
export interface RecommendedEvent {
  id: string;
  title: string;
  start: string;
  end: string;
  end_is_estimated: boolean;
  location: string | null;
  organizer: string | null;
  url: string | null;
  interest_tags: string[];
  match_percent: number;
  reasons: string[];
}
export interface ScheduleResponse {
  week_start: string;
  events: RecommendedEvent[];
  schedules: { label: string; event_ids: string[] }[];
}
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    const detail = error?.detail;
    const message = Array.isArray(detail)
      ? detail.map((item: { msg?: string }) => item.msg ?? "Invalid input").join("; ")
      : typeof detail === "string" ? detail : `HTTP ${response.status}`;
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
export const getOptions = () => request<OptionsResponse>("/api/options");
export const getSchedules = (profile: ProfileRequest) =>
  request<ScheduleResponse>("/api/schedules", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });