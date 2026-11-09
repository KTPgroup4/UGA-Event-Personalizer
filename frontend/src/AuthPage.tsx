import { useState, type FormEvent } from "react"
import { ApiError, logIn, signUp, type AuthResponse } from "./api"
import "./auth.css"

export type AuthMode = "login" | "signup"

type AuthPageProps = {
  mode: AuthMode
  // Called when the student switches between "Sign up" and "Log in".
  onModeChange: (mode: AuthMode) => void
  // Called when the student closes the screen without finishing.
  onClose: () => void
  // Called after a successful sign up or log in.
  onSuccess: (result: AuthResponse, mode: AuthMode) => void
}

const MIN_PASSWORD = 8
const looksLikeEmail = (value: string) =>
  /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(value.trim())

export default function AuthPage({
  mode,
  onModeChange,
  onClose,
  onSuccess,
}: AuthPageProps) {
  // Signing up has two steps (email, then password). Logging in is one page.
  const [step, setStep] = useState<"email" | "password">("email")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState("")
  const [busy, setBusy] = useState(false)

  const signingUp = mode === "signup"
  const showEmailField = !signingUp || step === "email"
  const showPasswordField = !signingUp || step === "password"

  const canSubmit = signingUp
    ? step === "email"
      ? looksLikeEmail(email)
      : password.length >= MIN_PASSWORD
    : looksLikeEmail(email) && password.length > 0

  function switchMode(next: AuthMode) {
    setStep("email")
    setPassword("")
    setShowPassword(false)
    setError("")
    onModeChange(next)
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy || !canSubmit) return

    setError("")

    // Sign up, step 1: the email is only checked here; nothing is sent yet.
    if (signingUp && step === "email") {
      setStep("password")
      return
    }

    setBusy(true)

    try {
      const result = signingUp
        ? await signUp(email.trim(), password)
        : await logIn(email.trim(), password)

      onSuccess(result, mode)
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Can't reach the server. Check your connection and try again."
      )
      setBusy(false)
    }
  }

  const title = !signingUp
    ? "Welcome back"
    : step === "email"
      ? "What's your email?"
      : "Create a password"

  const subtitle = !signingUp
    ? "Log in to get your saved preferences."
    : step === "email"
      ? "You'll use it to log in, and we'll save your preferences to it."
      : `At least ${MIN_PASSWORD} characters. Pick one you don't use on other sites.`

  const buttonLabel = !signingUp
    ? busy
      ? "Logging in..."
      : "Log in"
    : step === "email"
      ? "Next"
      : busy
        ? "Creating account..."
        : "Sign up"

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-title">
        {signingUp && step === "password" && (
          <button
            className="auth-back"
            type="button"
            aria-label="Back to email"
            onClick={() => {
              setError("")
              setStep("email")
            }}
          >
            ‹ Back
          </button>
        )}

        <button
          className="auth-close"
          type="button"
          aria-label="Close"
          onClick={onClose}
        >
          ×
        </button>

        <img
          className="auth-logo"
          src="/dawg-match-logo.png"
          alt="Dawg Match logo"
        />

        <h1 id="auth-title">{title}</h1>
        <p className="auth-sub">{subtitle}</p>

        <form className="auth-form" onSubmit={submit} noValidate>
          {showEmailField && (
            <div className="auth-field">
              <label htmlFor="auth-email">Email</label>
              <input
                id="auth-email"
                type="email"
                inputMode="email"
                autoComplete="email"
                placeholder="name@uga.edu"
                value={email}
                autoFocus
                onChange={event => setEmail(event.target.value)}
              />
            </div>
          )}

          {signingUp && step === "password" && (
            <p className="auth-email-line">
              Signing up as <strong>{email.trim()}</strong>
            </p>
          )}

          {showPasswordField && (
            <div className="auth-field">
              <label htmlFor="auth-password">
                {signingUp ? "New password" : "Password"}
              </label>

              <div className="auth-password">
                <input
                  id="auth-password"
                  type={showPassword ? "text" : "password"}
                  autoComplete={
                    signingUp ? "new-password" : "current-password"
                  }
                  placeholder={
                    signingUp
                      ? `At least ${MIN_PASSWORD} characters`
                      : "Your password"
                  }
                  value={password}
                  autoFocus={signingUp}
                  onChange={event => setPassword(event.target.value)}
                />

                <button
                  className="auth-toggle"
                  type="button"
                  aria-pressed={showPassword}
                  onClick={() => setShowPassword(shown => !shown)}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </div>
          )}

          <p className="auth-error" role="alert">
            {error}
          </p>

          <button
            className="auth-submit"
            type="submit"
            disabled={busy || !canSubmit}
          >
            {buttonLabel}
          </button>
        </form>

        <p className="auth-switch">
          {signingUp ? "Already have an account?" : "New here?"}{" "}
          <button
            type="button"
            onClick={() => switchMode(signingUp ? "login" : "signup")}
          >
            {signingUp ? "Log in" : "Sign up"}
          </button>
        </p>
      </section>
    </main>
  )
}
