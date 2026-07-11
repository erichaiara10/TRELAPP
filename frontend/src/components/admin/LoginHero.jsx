import React from "react";

export default function LoginHero() {
  return (
    <div className="hidden lg:block relative">
      <img src="https://images.pexels.com/photos/12081268/pexels-photo-12081268.jpeg" alt="" className="absolute inset-0 w-full h-full object-cover" />
      <div className="absolute inset-0 bg-gradient-to-t from-[#0F172A] to-transparent" />
      <div className="absolute bottom-10 left-10 right-10 text-white">
        <div className="text-xs uppercase tracking-[0.3em] text-white/60">PNG Realty · Operations</div>
        <div className="font-serif text-4xl mt-2">The engine behind every enquiry.</div>
      </div>
    </div>
  );
}
