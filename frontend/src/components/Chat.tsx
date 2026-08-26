"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { clearTokens } from "@/lib/auth";
import { streamChat, type Citation } from "@/lib/api";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  question?: string;
  citations?: Citation[];
}

interface LiveAnswer {
  question: string;
  answer: string;
  citations: Citation[];
}

export default function Chat() {
  const router = useRouter();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [live, setLive] = useState<LiveAnswer | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function logout() {
    clearTokens();
    router.push("/login");
  }

  async function send() {
    const text = draft.trim();
    if (!text || streaming) return;
    setDraft("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setStreaming(true);
    setError(null);

    let acc = "";
    let cits: Citation[] = [];
    let q = "";

    const flush = () => {
      if (acc || cits.length || q) {
        setMessages((m) => [
          ...m,
          { role: "assistant", content: acc, citations: cits, question: q || undefined },
        ]);
      }
      acc = "";
      cits = [];
    };

    try {
      await streamChat(text, conversationId, {
        onQuestion: (d) => {
          flush();
          q = d.text;
          setLive({ question: d.text, answer: "", citations: [] });
        },
        onToken: (t) => {
          acc += t;
          setLive({ question: q, answer: acc, citations: cits });
        },
        onCitations: (items) => {
          cits = items;
          setLive((l) => (l ? { ...l, citations: items } : l));
        },
        onDone: (cid) => setConversationId(cid),
      });
      flush();
      setLive(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStreaming(false);
    }
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-neutral-800 px-4 py-3">
        <h1 className="text-lg font-semibold">Business Valuator</h1>
        <button
          onClick={logout}
          className="rounded-md px-3 py-1 text-sm text-neutral-400 hover:bg-neutral-800"
        >
          Sair
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        <div className="mx-auto flex max-w-2xl flex-col gap-4">
          {messages.length === 0 && !live && (
            <div className="mt-16 text-center text-neutral-400">
              <p className="text-lg font-medium text-neutral-200">
                Analise uma ação da B3
              </p>
              <p className="mt-1 text-sm">
                Digite o nome da empresa ou o ticker (ex.: Banco do Brasil ou BBAS3).
              </p>
            </div>
          )}

          {messages.map((m, i) => (
            <Bubble key={i} message={m} />
          ))}

          {live && (
            <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
              <p className="mb-2 text-sm font-medium text-neutral-300">{live.question}</p>
              <p className="whitespace-pre-wrap text-sm text-neutral-100">
                {live.answer}
                {streaming && <span className="animate-pulse">▍</span>}
              </p>
              {live.citations.length > 0 && <Citations items={live.citations} />}
            </div>
          )}

          {error && (
            <p className="rounded-lg bg-red-950/50 p-3 text-sm text-red-300">{error}</p>
          )}
        </div>
      </div>

      <footer className="border-t border-neutral-800 px-4 py-3">
        <form
          className="mx-auto flex max-w-2xl gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Nome da empresa ou ticker…"
            disabled={streaming}
            className="flex-1 rounded-lg border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm outline-none focus:border-neutral-500"
          />
          <button
            type="submit"
            disabled={streaming || !draft.trim()}
            className="rounded-lg bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-900 disabled:opacity-40"
          >
            Enviar
          </button>
        </form>
      </footer>
    </div>
  );
}

function Bubble({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <div className="self-end rounded-xl bg-neutral-100 px-4 py-2 text-sm text-neutral-900">
        {message.content}
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900 p-4">
      {message.question && (
        <p className="mb-2 text-sm font-medium text-neutral-300">{message.question}</p>
      )}
      <p className="whitespace-pre-wrap text-sm text-neutral-100">{message.content}</p>
      {message.citations && message.citations.length > 0 && (
        <Citations items={message.citations} />
      )}
    </div>
  );
}

function Citations({ items }: { items: Citation[] }) {
  return (
    <div className="mt-3 border-t border-neutral-800 pt-2">
      <p className="mb-1 text-xs text-neutral-500">Fontes:</p>
      <ul className="flex flex-col gap-1">
        {items.map((c, i) => (
          <li key={i} className="text-xs">
            <a
              href={c.url}
              target="_blank"
              rel="noreferrer"
              className="text-sky-400 underline underline-offset-2 hover:text-sky-300"
            >
              {c.source}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
