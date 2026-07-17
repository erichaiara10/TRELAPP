import React from "react";
import { usePage } from "@/lib/usePage";
import { User } from "lucide-react";

export default function About() {
  const { sections } = usePage("about");
  const hero = sections.hero || {};
  const story = sections.story || {};
  const mission = sections.mission || {};
  const vision = sections.vision || {};
  const values = sections.values || [];
  const team = sections.team || [];

  return (
    <div>
      {/* Hero */}
      <section className="relative bg-sand-50">
        {hero.image && (
          <div className="absolute inset-0 opacity-25">
            <img src={hero.image} alt="" className="w-full h-full object-cover" />
          </div>
        )}
        <div className="relative container-tight py-16 max-w-4xl">
          <div className="text-xs uppercase tracking-[0.3em] text-muted-foreground" data-testid="about-hero-kicker">{hero.kicker}</div>
          <h1 className="font-serif text-4xl sm:text-5xl mt-3" data-testid="about-hero-heading">{hero.heading}</h1>
          {hero.intro && <p className="text-lg text-ink-700 mt-4 max-w-3xl" data-testid="about-hero-intro">{hero.intro}</p>}
        </div>
      </section>

      {/* Story */}
      {story.body && (
        <section className="container-tight py-14 max-w-4xl" data-testid="about-story">
          <h2 className="font-serif text-3xl">{story.heading || "Our story"}</h2>
          <p className="mt-4 text-ink-700 leading-relaxed whitespace-pre-line">{story.body}</p>
        </section>
      )}

      {/* Mission / Vision */}
      <section className="container-tight pb-14 max-w-4xl grid md:grid-cols-2 gap-6">
        {mission.body && (
          <div className="bg-pine-500 text-white rounded-2xl p-6" data-testid="about-mission">
            <h3 className="font-serif text-2xl">{mission.heading || "Our mission"}</h3>
            <p className="mt-3 text-sand-100 whitespace-pre-line">{mission.body}</p>
          </div>
        )}
        {vision.body && (
          <div className="bg-ink-900 text-white rounded-2xl p-6" data-testid="about-vision">
            <h3 className="font-serif text-2xl">{vision.heading || "Our vision"}</h3>
            <p className="mt-3 text-sand-100 whitespace-pre-line">{vision.body}</p>
          </div>
        )}
      </section>

      {/* Values */}
      {values.length > 0 && (
        <section className="container-tight pb-14 max-w-4xl" data-testid="about-values">
          <div className="text-xs uppercase tracking-[0.25em] text-muted-foreground">What we stand for</div>
          <h2 className="font-serif text-3xl mt-2">Our values</h2>
          <div className="mt-6 grid md:grid-cols-3 gap-4">
            {values.map((v, i) => (
              <div key={i} className="bg-white rounded-2xl p-5 border border-border" data-testid={`about-value-${i}`}>
                <div className="font-serif text-xl">{v.title}</div>
                <p className="text-sm text-ink-700 mt-2 whitespace-pre-line">{v.body}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Team */}
      {team.length > 0 && (
        <section className="container-tight pb-20 max-w-5xl" data-testid="about-team">
          <div className="text-xs uppercase tracking-[0.25em] text-muted-foreground">Meet the team</div>
          <h2 className="font-serif text-3xl mt-2">The people behind TREL</h2>
          <div className="mt-6 grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {team.map((m, i) => (
              <div key={i} className="bg-white rounded-2xl p-5 border border-border" data-testid={`about-team-${i}`}>
                <div className="flex items-center gap-3">
                  <div className="w-14 h-14 rounded-full bg-sand-100 grid place-items-center overflow-hidden shrink-0">
                    {m.photo
                      ? <img src={m.photo.startsWith("http") ? m.photo : `${process.env.REACT_APP_BACKEND_URL}${m.photo}`} alt={m.name} className="w-full h-full object-cover" />
                      : <User className="w-6 h-6 text-muted-foreground" />}
                  </div>
                  <div>
                    <div className="font-serif text-lg leading-tight">{m.name}</div>
                    <div className="text-xs text-muted-foreground uppercase tracking-widest mt-0.5">{m.role}</div>
                  </div>
                </div>
                {m.bio && <p className="text-sm text-ink-700 mt-3 whitespace-pre-line">{m.bio}</p>}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
