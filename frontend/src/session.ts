// Remembers the login token in this browser so a student stays logged in after
// closing the tab. (localStorage can be blocked in private windows, so every
// call is wrapped: if it fails, the student simply has to log in again next time.)

const KEY = "dawgmatch-token"

export function loadToken(): string {
  try {
    return localStorage.getItem(KEY) ?? ""
  } catch {
    return ""
  }
}

export function saveToken(token: string) {
  try {
    localStorage.setItem(KEY, token)
  } catch {
    // ignore: the student stays logged in until they close the tab
  }
}

export function clearToken() {
  try {
    localStorage.removeItem(KEY)
  } catch {
    // ignore
  }
}
