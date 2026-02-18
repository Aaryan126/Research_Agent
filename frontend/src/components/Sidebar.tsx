import { X, Plus, MessageSquare } from 'lucide-react';

interface Conversation {
  id: string;
  title: string;
}

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  onNewChat: () => void;
  conversations: Conversation[];
}

export function Sidebar({ isOpen, onClose, onNewChat, conversations }: SidebarProps) {
  return (
    <>
      {/* Backdrop overlay for mobile */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar panel */}
      <div
        className={`fixed top-0 left-0 h-full w-72 bg-warm-tan text-primary-text z-50
                     flex flex-col transition-transform duration-300 ease-in-out border-r border-gray-200
                     ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        {/* Top bar */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
          <button
            onClick={() => {
              onNewChat();
              onClose();
            }}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium
                       hover:bg-cream transition-colors cursor-pointer"
          >
            <Plus className="w-4 h-4" />
            New chat
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-cream transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Conversation list */}
        <div className="flex-1 overflow-y-auto px-2 py-3 space-y-1">
          {conversations.length === 0 ? (
            <p className="px-3 py-2 text-sm text-secondary-text">No conversations yet</p>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-sm
                           text-primary-text hover:bg-cream transition-colors cursor-pointer truncate"
              >
                <MessageSquare className="w-4 h-4 shrink-0 text-secondary-text" />
                <span className="truncate">{conv.title}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </>
  );
}
