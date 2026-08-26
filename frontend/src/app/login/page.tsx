"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { API_URL } from "@/lib/api";
import { setTokens } from "@/lib/auth";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (cfg: Record<string, unknown>) => void;
          renderButton: (el: HTMLElement, cfg: Record<string, unknown>) => void;
        };
      };
    };
  }
}

export default function LoginPage() {
  const router = useRouter();
  const buttonRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
    if (!clientId) {
      setError("NEXT_PUBLIC_GOOGLE_CLIENT_ID não configurado no ambiente.");
      return;
    }

    const existing = document.querySelector('script[src="https://accounts.google.com/gsi/client"]');
    const init = () => {
      window.google?.accounts.id.initialize({
        client_id: clientId,
        callback: handleCredential,
      });
      if (buttonRef.current) {
        window.google?.accounts.id.renderButton(buttonRef.current, {
          theme: "outline",
          size: "large",
          shape: "pill",
        });
      }
    };

    const handleCredential = async (resp: { credential?: string }) => {
      const idToken = resp.credential;
      if (!idToken) return;
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API_URL}/auth/google`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id_token: idToken }),
        });
        if (!res.ok) {
          setError("Falha no login com Google.");
          return;
        }
        const data = await res.json();
        setTokens(data.access_token, data.refresh_token);
        router.push("/chat");
      } catch {
        setError("Falha de rede ao autenticar.");
      } finally {
        setLoading(false);
      }
    };

    if (existing) {
      init();
    } else {
      const script = document.createElement("script");
      script.src = "https://accounts.google.com/gsi/client";
      script.async = true;
      script.onload = init;
      document.body.appendChild(script);
    }
  }, [router]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 px-4">
      <div className="text-center">
        <h1 className="text-2xl font-semibold">Business Valuator</h1>
        <p className="mt-1 text-sm text-neutral-400">
          Análise fundamentalista de ações da B3
        </p>
      </div>

      <div className="w-full max-w-sm rounded-xl border border-neutral-800 bg-neutral-900 p-6">
        {error && <p className="mb-4 text-sm text-red-400">{error}</p>}
        {loading ? (
          <p className="text-center text-sm text-neutral-400">Autenticando…</p>
        ) : (
          <div className="flex justify-center">
            <div ref={buttonRef} />
          </div>
        )}
      </div>
    </main>
  );
}
