import React from 'react';

function memoryText(m) {
  const v = m?.value_json;
  if (!v) return '';
  if (typeof v === 'string') return v;
  return v.text || v.value || JSON.stringify(v);
}

export default function PlanningView({ state, memories, inventory, onControl, loading }) {
  const recipe = state?.recipe || null;
  const dishName = state?.dish_name || recipe?.dish_name || '尚未生成菜品';
  const servings = recipe?.servings || '—';
  const minutes = recipe?.estimated_minutes;
  const ingredients = recipe?.ingredients || [];
  const reasoning =
    recipe?.reasoning_summary ||
    '说一句你今晚想吃什么、家里有什么、谁不吃什么，妮妮会基于家庭记忆为你生成一道适合的菜。';
  const adjustments = state?.active_adjustments || recipe?.adjustments || [];

  const inventoryByName = Object.fromEntries(
    (inventory || []).map((it) => [it.name, it]),
  );

  const tags = [];
  for (const m of memories) {
    const t = memoryText(m);
    if (!t) continue;
    if (m.subject === 'mother' && /辣/.test(t)) tags.push('妈妈不吃辣');
    else if (m.subject === 'user' && /减脂|低脂/.test(t)) tags.push('适合减脂');
    else if (m.subject === 'user' && /酸/.test(t)) tags.push('降低酸度');
  }
  if (ingredients.length) tags.push('使用现有食材');
  if (Number.isFinite(minutes)) tags.push(`${minutes} 分钟`);

  return (
    <div className="view-wrap">
      <div className="view-header">
        <div className="view-eyebrow">
          妮妮推荐方案 · 基于家庭记忆与当前库存生成
        </div>
      </div>

      <div className="feature-block">
        <div className="feature-left">
          <div className="recipe-name">{dishName}</div>
          <div className="recipe-meta">
            {Number.isFinite(minutes) ? (
              <span className="meta-item">⏱ {minutes} 分钟</span>
            ) : null}
            {servings && servings !== '—' ? (
              <span className="meta-item">👥 {servings}</span>
            ) : null}
            {adjustments?.length ? (
              <span className="meta-item">✦ {adjustments.length} 项调整</span>
            ) : null}
          </div>
          {tags.length ? (
            <div className="tag-row">
              {Array.from(new Set(tags)).map((t) => (
                <span key={t} className="tag">
                  {t}
                </span>
              ))}
            </div>
          ) : null}
          <div className="reason-text">{reasoning}</div>

          <div className="plan-actions">
            <button
              type="button"
              className="btn-primary"
              disabled={loading}
              onClick={() => onControl('start')}
            >
              开始做这道
            </button>
            <button
              type="button"
              className="btn-secondary"
              disabled={loading}
              onClick={() => onControl('reset')}
              title="重新规划一道菜"
            >
              换一道
            </button>
          </div>
        </div>

        <div className="feature-right">
          <div className="info-block">
            <div className="info-title">食材匹配</div>
            {ingredients.length === 0 ? (
              <div className="mem-empty">尚无食材清单</div>
            ) : (
              ingredients.map((name) => {
                const inv = inventoryByName[name];
                const amount = inv?.amount;
                const cls = !inv ? 'warn' : 'ok';
                return (
                  <div key={name} className="info-row">
                    <span className="info-key">{name}</span>
                    <span className={`info-val ${cls}`}>
                      {amount || (inv ? '已有' : '待确认')}
                    </span>
                  </div>
                );
              })
            )}
          </div>

          <div className="info-block">
            <div className="info-title">家庭记忆命中</div>
            {memories.length === 0 ? (
              <div className="mem-empty">暂无家庭记忆，先在左侧输入约束</div>
            ) : (
              memories.slice(0, 6).map((m) => (
                <div key={m.id} className="mem-row">
                  <span className="dash">—</span>
                  <span>{memoryText(m)}</span>
                </div>
              ))
            )}
          </div>

          {adjustments?.length ? (
            <div className="info-block">
              <div className="info-title">已应用调整</div>
              {adjustments.map((a, i) => (
                <div key={i} className="mem-row">
                  <span className="dash">✦</span>
                  <span>{a}</span>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
