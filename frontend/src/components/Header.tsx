export function Header({ onHome }: { onHome: () => void }) {
  return (
    <header className="border-b border-ink/10 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <button
          onClick={onHome}
          className="flex items-baseline gap-3 text-left"
          aria-label="Go to projects"
        >
          <span className="text-sm font-bold uppercase tracking-[0.2em] text-ink">
            Sustainable Finishes
          </span>
          <span className="hidden h-4 w-px bg-ink/20 sm:inline-block" />
          <span className="text-base font-semibold text-amber">EnergyModeler</span>
        </button>
        <span className="text-xs text-ink/40">window-film energy savings</span>
      </div>
    </header>
  );
}
