import { Menu } from 'lucide-react';

interface HeaderProps {
  onToggleSidebar: () => void;
}

export function Header({ onToggleSidebar }: HeaderProps) {
  return (
    <header className="bg-transparent px-6 py-3 flex items-start gap-3 shrink-0">
      <button
        onClick={onToggleSidebar}
        className="p-1.5 rounded-lg hover:bg-warm-tan transition-colors cursor-pointer"
      >
        <Menu className="w-5 h-5 text-primary-text" />
      </button>
      <div className="flex flex-col pt-[5.1px]">
        <h1 className="text-lg font-normal text-primary-text leading-tight">
          Research Orchestration
        </h1>
        <div className="flex items-center gap-1 self-end mr-[1.2px]">
          <span className="text-[10px] text-secondary-text">powered by</span>
          <img
            src="/elastic-logo.png"
            alt="Elastic"
            className="h-3.5 object-contain"
          />
        </div>
      </div>
    </header>
  );
}
