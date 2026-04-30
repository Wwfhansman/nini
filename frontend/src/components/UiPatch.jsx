import React from 'react';

export function UiPatchAttention({ text }) {
  if (!text) return null;
  return <div className="ui-patch-attention">{text}</div>;
}

export function UiPatchCards({ cards }) {
  const list = Array.isArray(cards) ? cards.slice(0, 6) : [];
  if (!list.length) return null;
  return (
    <div className="ui-patch-cards">
      {list.map((card, index) => (
        <div
          className={`ui-patch-card tone-${card.tone || 'neutral'}`}
          key={`${card.label || 'card'}-${index}`}
        >
          <span className="ui-patch-card-label">{card.label}</span>
          <span className="ui-patch-card-value">{card.value}</span>
        </div>
      ))}
    </div>
  );
}

export function UiPatchPhrases({ phrases }) {
  const list = Array.isArray(phrases) ? phrases.slice(0, 5) : [];
  if (!list.length) return null;
  return (
    <div className="ui-patch-phrases">
      <span className="ui-patch-phrases-label">你可以说</span>
      <div className="ui-patch-phrase-list">
        {list.map((phrase) => (
          <span key={phrase}>{phrase}</span>
        ))}
      </div>
    </div>
  );
}
