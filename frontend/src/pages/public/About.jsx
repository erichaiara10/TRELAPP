import React, { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function About() {
  const [about, setAbout] = useState({ heading: "About Triumph Real Estate Limited", body: "" });
  const [why, setWhy] = useState({ heading: "Why choose us", items: [] });
  useEffect(() => {
    api.get("/content/about").then((r) => r.data?.value && setAbout(r.data.value));
    api.get("/content/why").then((r) => r.data?.value && setWhy(r.data.value));
  }, []);
  return (
    <div className="container-tight py-14">
      <div className="max-w-3xl">
        <div className="text-xs uppercase tracking-[0.3em] text-muted-foreground">About</div>
        <h1 className="font-serif text-5xl mt-3">{about.heading}</h1>
        <p className="text-lg text-ink-700 leading-relaxed mt-6 whitespace-pre-line">{about.body}</p>
      </div>
      <div className="mt-16">
        <h2 className="font-serif text-3xl">{why.heading}</h2>
        <div className="mt-6 grid md:grid-cols-3 gap-6">
          {(why.items || []).map((i, k) => (
            <div key={k} className="bg-white rounded-2xl p-6 border border-border">
              <div className="font-serif text-xl">{i.title}</div>
              <p className="text-sm text-ink-700 mt-2">{i.body}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
