import { useEffect, useRef, useState } from "react";

declare global {
  interface Window {
    google?: any;
  }
}

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

let scriptLoadPromise: Promise<void> | null = null;
function loadGoogleScript(): Promise<void> {
  if (scriptLoadPromise) return scriptLoadPromise;
  scriptLoadPromise = new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) return resolve();
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Failed to load Google Identity Services"));
    document.head.appendChild(script);
  });
  return scriptLoadPromise;
}

export default function GoogleSignInButton({ onCredential }: { onCredential: (idToken: string) => void }) {
  const buttonRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) {
      if (import.meta.env.DEV) {
        console.warn(
          "[GoogleSignInButton] VITE_GOOGLE_CLIENT_ID is not set — the Google button won't render. See DEPLOYMENT.md step 9."
        );
      }
      return;
    }
    let cancelled = false;

    loadGoogleScript()
      .then(() => {
        if (cancelled || !window.google || !buttonRef.current) return;
        window.google.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (response: { credential: string }) => onCredential(response.credential),
        });
        window.google.accounts.id.renderButton(buttonRef.current, {
          theme: "filled_black",
          size: "large",
          width: 320,
          shape: "pill",
          text: "continue_with",
        });
      })
      .catch(() => setError("Could not load Google Sign-In. Check your connection and try again."));

    return () => { cancelled = true; };
  }, [onCredential]);

  if (!GOOGLE_CLIENT_ID) {
    // Not configured. In dev, show a clear hint instead of silently vanishing --
    // this used to just return null, which looked like a bug rather than an
    // unfinished setup step. In production, stay silent (a real user doesn't need
    // to see internal setup instructions).
    if (import.meta.env.DEV) {
      return (
        <div className="border border-dashed border-amber-500/40 bg-amber-500/5 rounded-lg px-4 py-3 text-center">
          <div className="text-amber-400 text-xs font-medium">Google Sign-In not configured</div>
          <div className="text-gray-500 text-[11px] mt-1">
            Set <code className="text-gray-400">VITE_GOOGLE_CLIENT_ID</code> in{" "}
            <code className="text-gray-400">frontend/.env</code> — see DEPLOYMENT.md step 9.
          </div>
        </div>
      );
    }
    return null;
  }

  return (
    <div>
      <div ref={buttonRef} className="flex justify-center" />
      {error && <div className="text-red-400 text-xs mt-2 text-center">{error}</div>}
    </div>
  );
}
