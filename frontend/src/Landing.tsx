import "./landing.css"

type LandingProps = {
  // Called when the student chooses "Continue as guest".
  onGuest: () => void
  // Called by the "Log in" button in the corner.
  onLogin: () => void
  // Called by the "Sign up" button on the red card.
  onSignUp: () => void
}

export default function Landing({ onGuest, onLogin, onSignUp }: LandingProps) {
  return (
    <main className="landing">
      <header className="landing-top">
        <button className="landing-login" type="button" onClick={onLogin}>
          Log in
        </button>
      </header>

      <div className="landing-inner">
        <section className="landing-about">
          <img
            className="landing-logo"
            src="/dawg-match-logo.png"
            alt="Dawg Match logo: a paw print with a heart inside a red circle"
          />

          <p className="landing-lead">
            <span className="landing-name">Dawg Match</span> helps UGA
            students find campus events that fit them.
          </p>

          <p className="landing-text">
            Tell us your interests, major and busy times, then swipe through
            events picked for you and save your favorites to a weekly
            calendar.
          </p>
        </section>

        <section className="landing-card" aria-labelledby="landing-title">
          <h1 id="landing-title">Find events that fit your week.</h1>

          <p className="landing-sub">
            Create an account to save your answers, or jump right in as a
            guest.
          </p>

          <div className="landing-actions">
            <button
              className="landing-primary"
              type="button"
              onClick={onSignUp}
            >
              Sign up
            </button>

            <button
              className="landing-secondary"
              type="button"
              onClick={onGuest}
            >
              Continue as guest
            </button>
          </div>
        </section>
      </div>
    </main>
  )
}
