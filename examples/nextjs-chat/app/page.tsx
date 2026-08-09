"use client";

import { useState, type SyntheticEvent } from "react";

export default function Page() {
  const [message, setMessage] = useState("");
  const [answer, setAnswer] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event: SyntheticEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setAnswer("");
    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ message }),
      });
      const payload = (await response.json()) as { answer?: string; error?: string };
      setAnswer(payload.answer ?? payload.error ?? "Yanıt alınamadı");
    } finally {
      setPending(false);
    }
  }

  return (
    <main>
      <p className="eyebrow">Yerel örnek</p>
      <h1>Hushmark üzerinden sohbet</h1>
      <p>İstek, yapılandırılmış yerel gateway üzerinden sağlayıcıya iletilir.</p>
      <form onSubmit={(event) => void submit(event)}>
        <label htmlFor="message">Mesaj</label>
        <textarea
          id="message"
          required
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          placeholder="TCKN içeren bir destek mesajı yazın"
        />
        <button disabled={pending} type="submit">
          {pending ? "Gönderiliyor…" : "Gönder"}
        </button>
      </form>
      <output aria-live="polite">{answer}</output>
    </main>
  );
}
