import React from 'react';
import PlanningView from './PlanningView.jsx';
import VisionView from './VisionView.jsx';
import CookingView from './CookingView.jsx';
import ReviewView from './ReviewView.jsx';

export default function CenterPanel({
  uiMode,
  state,
  memories,
  inventory,
  providerLogs,
  recipeDocuments,
  visionPreview,
  lastObservation,
  recentEvents = [],
  memoryMarkdown,
  onControl,
  onPickImage,
  onUploadVision,
  onExportMemory,
  loading,
}) {
  return (
    <div className="centerpanel">
      <div className="center-stage state-enter" key={uiMode}>
        {uiMode === 'planning' && (
          <PlanningView
            state={state}
            memories={memories}
            inventory={inventory}
            onControl={onControl}
            loading={loading}
          />
        )}
        {uiMode === 'vision' && (
          <VisionView
            state={state}
            visionPreview={visionPreview}
            lastObservation={lastObservation}
            onPickImage={onPickImage}
            onUploadVision={onUploadVision}
            loading={loading}
            recentEvents={recentEvents}
          />
        )}
        {uiMode === 'cooking' && (
          <CookingView
            state={state}
            onControl={onControl}
            loading={loading}
          />
        )}
        {uiMode === 'review' && (
          <ReviewView
            state={state}
            memories={memories}
            inventory={inventory}
            memoryMarkdown={memoryMarkdown}
            onExportMemory={onExportMemory}
            onControl={onControl}
            loading={loading}
          />
        )}
      </div>
    </div>
  );
}
