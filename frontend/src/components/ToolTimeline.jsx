import React from 'react';

const EVENT_LABELS = {
  memory_write: { label: '写入家庭记忆', tool: 'memory_write' },
  inventory_update: { label: '更新当前库存', tool: 'inventory_update' },
  recipe_plan: { label: '生成晚餐方案', tool: 'recipe_plan' },
  recipe_adjust: { label: '修正菜谱步骤', tool: 'recipe_adjust' },
  vision_observe: { label: '分析食材照片', tool: 'vision_observe' },
  speech_tts: { label: '生成语音播报', tool: 'speech_tts' },
  speech_asr: { label: '识别语音输入', tool: 'speech_asr' },
  provider_call: { label: '调用任务模型', tool: 'provider_call' },
  provider_error: { label: 'Provider 回退', tool: 'provider_error' },
  vision_provider_fallback: {
    label: 'Vision 回退到 Mock',
    tool: 'vision_fallback',
  },
  recipe_knowledge_import: {
    label: '导入家庭菜谱',
    tool: 'recipe_knowledge',
  },
  start: { label: '本地状态机：开始', tool: 'state_machine', local: true },
  next_step: { label: '本地状态机：下一步', tool: 'state_machine', local: true },
  previous_step: {
    label: '本地状态机：上一步',
    tool: 'state_machine',
    local: true,
  },
  pause: { label: '本地状态机：暂停', tool: 'state_machine', local: true },
  resume: { label: '本地状态机：继续', tool: 'state_machine', local: true },
  finish: { label: '本地状态机：完成', tool: 'state_machine', local: true },
  reset: { label: '本地状态机：重置', tool: 'state_machine', local: true },
};

function describe(event) {
  const map = EVENT_LABELS[event.name] || {
    label: event.name || '未知事件',
    tool: event.name || 'event',
  };
  const isLocal =
    map.local ||
    event.event_type === 'local_control' ||
    (event.output_json || event.output)?.model_called === false;
  return { ...map, local: isLocal };
}

export default function ToolTimeline({ events }) {
  const list = (events || []).slice(-12);
  const lastIdx = list.length - 1;

  return (
    <div className="rp-section" style={{ flex: '0 0 auto' }}>
      <div className="rp-head">
        <span className="section-label">Agent 任务编排</span>
        {list.length ? (
          <span className="rp-aux live">
            <span className="dot">●</span> 实时流
          </span>
        ) : (
          <span className="rp-aux">idle</span>
        )}
      </div>

      <div className="timeline">
        {list.length === 0 ? (
          <div className="timeline-empty">
            等待 Agent 与状态机事件… 触发对话或控制后，这里会出现实时编排。
          </div>
        ) : (
          list.map((event, i) => {
            const meta = describe(event);
            const out = event.output || event.output_json || {};
            const status = event.status || 'success';
            const isError = status === 'fallback' || status === 'error';
            const isRecent = i === lastIdx;
            const cls = isError
              ? 'error'
              : isRecent
              ? 'running'
              : 'done';
            const desc = (() => {
              if (event.name === 'recipe_plan') return out.dish_name;
              if (event.name === 'recipe_adjust' && out.adjustments?.length)
                return out.adjustments.slice(0, 2).join('；');
              if (event.name === 'vision_observe')
                return out.observation?.ingredients
                  ?.slice(0, 3)
                  .map((it) => `${it.name}${it.amount}`)
                  .join('、');
              if (event.name === 'memory_write' && out.memories?.length)
                return `${out.memories.length} 条记忆`;
              if (event.name === 'inventory_update' && out.items?.length)
                return `${out.items.length} 项库存`;
              if (event.name === 'provider_call' && out.latency_ms)
                return `latency ${out.latency_ms}ms`;
              if (event.name === 'provider_error')
                return (out.error || '').slice(0, 60);
              return null;
            })();
            return (
              <div
                key={event.id || `${event.name}-${i}`}
                className={`timeline-row ${cls}`}
              >
                <span className="timeline-icon">
                  {isError ? '!' : isRecent ? '●' : '✓'}
                </span>
                <div className="timeline-body">
                  <div className="timeline-label">
                    {String(i + 1).padStart(2, '0')} · {meta.label}
                  </div>
                  {desc ? <div className="timeline-meta">{desc}</div> : null}
                  <div className="timeline-tags">
                    {meta.local ? (
                      <span className="tag-mini local">
                        LOCAL · 未调用模型
                      </span>
                    ) : (
                      <span className="tag-mini tool">{meta.tool}</span>
                    )}
                    <span className={`tag-mini ${isError ? 'fallback' : 'status'}`}>
                      {status}
                    </span>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
