import React, { useCallback, useEffect, useImperativeHandle, forwardRef, useState } from "react";
import { RefreshCw, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";

/**
 * Reusable "I'm not a robot" verification.
 * - Server issues a signed alphanumeric CAPTCHA (JWT with the code + expiry).
 * - Case-insensitive; excludes confusable chars (0/O, 1/I/l).
 * - Includes a hidden honeypot field (bots that fill every field will be caught).
 *
 * Usage:
 *   const captchaRef = useRef(null);
 *   <HumanVerification ref={captchaRef} />
 *   const v = captchaRef.current?.getPayload();
 *   captchaRef.current?.refresh();
 */
const HumanVerification = forwardRef(function HumanVerification(props, ref) {
  const [challenge, setChallenge] = useState({ question: "", token: "" });
  const [answer, setAnswer] = useState("");
  const [hp, setHp] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/public/challenge");
      setChallenge({ question: data.question, token: data.token });
      setAnswer("");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  useImperativeHandle(ref, () => ({
    getPayload: () => ({
      verification_token: challenge.token,
      verification_answer: answer,
      hp_website: hp,
    }),
    isValid: () => Boolean(answer && challenge.token),
    refresh: load,
  }), [challenge.token, answer, hp, load]);

  // Server returns "Type these letters/numbers: XXXXX". Split so we can style the code.
  const [prompt, code] = (() => {
    const q = challenge.question || "";
    const idx = q.lastIndexOf(":");
    return idx > 0 ? [q.slice(0, idx).trim(), q.slice(idx + 1).trim()] : ["", q];
  })();

  return (
    <div className="rounded-lg border border-border bg-sand-50 p-3" data-testid="human-verification">
      {/* honeypot: hidden from users, tab-index -1, off-screen */}
      <input
        type="text"
        name="hp_website"
        tabIndex={-1}
        autoComplete="off"
        value={hp}
        onChange={(e) => setHp(e.target.value)}
        aria-hidden="true"
        data-testid="hp-website"
        style={{ position: "absolute", left: "-10000px", width: "1px", height: "1px", opacity: 0 }}
      />
      <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-muted-foreground">
        <ShieldCheck className="w-3.5 h-3.5 text-pine-500" />
        Human verification
      </div>
      <div className="mt-2 flex items-center gap-2">
        <div className="flex-1 flex items-center gap-2" data-testid="captcha-question">
          {loading ? (
            <span className="text-sm text-muted-foreground">Loading…</span>
          ) : code ? (
            <>
              <span className="text-xs text-muted-foreground">{prompt || "Type this code"}:</span>
              <span
                className="select-none font-mono text-lg font-bold tracking-[0.35em] text-ink-900 bg-white border border-border rounded px-3 py-1"
                style={{ fontFamily: "'Courier New', ui-monospace, monospace", textDecoration: "line-through", textDecorationStyle: "wavy", textDecorationColor: "rgba(0,0,0,0.2)" }}
                aria-label={`Verification code ${code.split("").join(" ")}`}
              >
                {code}
              </span>
            </>
          ) : (
            <span className="text-sm text-ink-900">—</span>
          )}
        </div>
        <button type="button" onClick={load} data-testid="captcha-refresh"
          className="p-1.5 rounded-md text-muted-foreground hover:bg-white" aria-label="New challenge">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
        </button>
      </div>
      <input
        type="text"
        autoCapitalize="characters"
        autoComplete="off"
        spellCheck={false}
        placeholder="Enter the code above (not case-sensitive)"
        value={answer}
        onChange={(e) => setAnswer(e.target.value)}
        data-testid="captcha-answer"
        className="mt-2 w-full border border-border rounded px-3 py-2 bg-white font-mono tracking-widest uppercase"
        required
      />
    </div>
  );
});

export default HumanVerification;
