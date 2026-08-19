import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import LoginHero from "@/components/admin/LoginHero";

function LoginForm() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [pwd, setPwd] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    const r = await login(email, pwd);
    setLoading(false);
    if (r.ok && r.passwordChangeRequired) {
      nav("/auth/change-password", {
        replace: true,
        state: { changeToken: r.changeToken, email: r.email, purpose: r.purpose },
      });
      return;
    }
    if (r.ok) {
      toast.success("Signed in");
      // Route property advertisers to their dedicated workspace.
      const isAdvertiser = ["property_advertiser", "advertiser"].includes(r.user?.role);
      nav(isAdvertiser ? "/advertiser" : "/admin");
    }
    else toast.error(r.error || "Login failed");
  };

  return (
    <form onSubmit={submit} className="w-full max-w-md bg-white rounded-2xl p-8 border border-border" data-testid="login-form">
      <Link to="/" className="text-xs text-muted-foreground">← Back to site</Link>
      <h1 className="font-serif text-3xl mt-3">Staff sign in</h1>
      <p className="text-sm text-muted-foreground mt-1">Access the TREL operating system.</p>
      <div className="mt-6 space-y-3">
        <label className="block">
          <span className="text-xs uppercase tracking-widest text-muted-foreground">Email</span>
          <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} data-testid="login-email" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5" />
        </label>
        <label className="block">
          <span className="text-xs uppercase tracking-widest text-muted-foreground">Password</span>
          <input required type="password" value={pwd} onChange={(e) => setPwd(e.target.value)} data-testid="login-password" className="mt-1 w-full border border-border rounded-lg px-3 py-2.5" />
        </label>
        <button type="submit" disabled={loading} data-testid="login-submit" className="w-full py-2.5 rounded-md bg-[#0F172A] text-white hover:bg-black disabled:opacity-60">
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </div>
      <div className="mt-6 text-xs text-muted-foreground bg-sand-50 p-3 rounded-lg" data-testid="login-help">
        Having trouble signing in? Please contact your system administrator.
      </div>
    </form>
  );
}

export default function Login() {
  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-[#F3F4F6]">
      <LoginHero />
      <div className="flex items-center justify-center p-6"><LoginForm /></div>
    </div>
  );
}
