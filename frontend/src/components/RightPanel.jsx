import React, { useEffect, useState } from 'react';
import ToolTimeline from './ToolTimeline.jsx';
import MemoryPanel from './MemoryPanel.jsx';
import InventoryPanel from './InventoryPanel.jsx';

export default function RightPanel({
  events,
  memories,
  state,
  inventory,
  providerLogs,
  health,
  highlightTrigger,
}) {
  const [highlight, setHighlight] = useState(false);
  useEffect(() => {
    if (!highlightTrigger) return undefined;
    setHighlight(true);
    const t = setTimeout(() => setHighlight(false), 3000);
    return () => clearTimeout(t);
  }, [highlightTrigger]);

  return (
    <div className="rightpanel">
      <ToolTimeline events={events} />
      <MemoryPanel
        memories={memories}
        highlight={highlight}
        pendingAction={state?.pending_action}
      />
      <InventoryPanel
        inventory={inventory}
        providerLogs={providerLogs}
        health={health}
      />
    </div>
  );
}
