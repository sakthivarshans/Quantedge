import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import GradientHero from "../components/GradientHero";
import GoogleSignInButton from "../components/GoogleSignInButton";

export default function Login() {
  const { login, register, loginWithGoogle } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mode === "login") await login(email, password);
      else await register(email, password);
      navigate("/paper-trading");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleCredential = useCallback(
    async (idToken: string) => {
      setError(null);
      try {
        await loginWithGoogle(idToken);
        navigate("/paper-trading");
      } catch (err: any) {
        setError(err?.response?.data?.detail || "Google Sign-In failed");
      }
    },
    [loginWithGoogle, navigate]
  );

  return (
    <GradientHero className="min-h-screen flex flex-col">
      <div className="flex-1 flex flex-col lg:flex-row items-center lg:items-end justify-between max-w-6xl mx-auto w-full px-6 sm:px-10 pt-20 pb-14 gap-12">
        {/* Left: bold hero headline, matching the reference's oversized two-line treatment */}
        <div className="max-w-xl">
          <div className="text-blue-400 text-sm font-medium tracking-wide mb-4">QUANTEDGE</div>
          <h1 className="text-white font-semibold leading-[1.05] tracking-tight text-5xl sm:text-6xl lg:text-7xl">
            Statistical
            <br />
            arbitrage,
            <br />
            simplified.
          </h1>
          <p className="text-gray-400 text-base sm:text-lg mt-6 max-w-md">
            Real cointegration testing, backtesting, and risk analytics for pairs
            trading research — sign in to run your own strategies.
          </p>
        </div>

        {/* Right: auth card, glassy over the glow */}
        <div className="w-full max-w-sm bg-[#0d1017]/80 backdrop-blur-xl border border-white/10 rounded-2xl p-7 shadow-2xl shadow-black/40">
          <div className="mb-6">
            <div className="text-lg font-semibold text-white">
              {mode === "login" ? "Welcome back" : "Create your account"}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {mode === "login" ? "Sign in to continue" : "Start researching in minutes"}
            </div>
          </div>

          <GoogleSignInButton onCredential={handleGoogleCredential} />

          <div className="flex items-center gap-3 my-5">
            <div className="h-px bg-white/10 flex-1" />
            <span className="text-xs text-gray-500">or</span>
            <div className="h-px bg-white/10 flex-1" />
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-xs text-gray-500 block mb-1">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">Password</label>
              <input
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-black/30 border border-white/10 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-blue-500"
              />
            </div>

            {error && <div className="text-red-400 text-xs">{error}</div>}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium py-2.5 rounded-lg transition-colors"
            >
              {loading ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>

          <div className="text-center mt-5 text-xs text-gray-500">
            {mode === "login" ? (
              <>
                No account?{" "}
                <button onClick={() => setMode("register")} className="text-blue-400 hover:underline">
                  Register
                </button>
              </>
            ) : (
              <>
                Already have an account?{" "}
                <button onClick={() => setMode("login")} className="text-blue-400 hover:underline">
                  Sign in
                </button>
              </>
            )}
          </div>
        </div>
      </div>
    </GradientHero>
  );
}
