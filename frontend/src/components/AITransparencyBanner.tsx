interface AITransparencyBannerProps {
  className?: string;
}

export function AITransparencyBanner({ className = "" }: AITransparencyBannerProps) {
  return (
    <div
      className={`bg-amber-50 border border-amber-200 rounded-lg px-4 py-2.5 text-xs text-amber-800 leading-snug ${className}`}
      role="alert"
      aria-label="AI transparency notice"
    >
      <span className="font-semibold">AI Notice:</span> CivicAI is an AI assistant, not a human.
      Responses are for guidance only. Complaints are{" "}
      <span className="font-semibold">simulated</span> and are{" "}
      <span className="font-semibold">not sent to any real authority</span>.
      Always verify critical information with official sources.
    </div>
  );
}
