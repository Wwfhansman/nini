import React from 'react';

const EVENT_LABELS = {
  memory_write: { label: '记住家庭偏好', tool: '家庭记忆' },
  inventory_update: { label: '更新食材库存', tool: '食材库存' },
  recipe_plan: { label: '生成晚餐方案', tool: '晚餐方案' },
  recipe_adjust: { label: '调整烹饪方案', tool: '烹饪方案' },
  vision_observe: { label: '识别食材画面', tool: '终端视觉' },
  speech_tts: { label: '生成语音回复', tool: '语音播报' },
  speech_asr: { label: '理解语音输入', tool: '语音理解' },
  provider_call: { label: '智能服务响应', tool: '智能服务' },
  provider_error: { label: '启用本地兜底', tool: '本地兜底' },
  vision_provider_fallback: {
    label: '视觉服务兜底',
    tool: '本地兜底',
  },
  recipe_knowledge_import: {
    label: '导入家庭菜谱',
    tool: '家庭菜谱',
  },
  start_vision: { label: '准备查看食材', tool: '终端视觉', local: true },
  start: { label: '开始烹饪', tool: '本地即时响应', local: true },
  next_step: { label: '进入下一步', tool: '本地即时响应', local: true },
  previous_step: {
    label: '回到上一步',
    tool: '本地即时响应',
    local: true,
  },
  pause: { label: '暂停烹饪', tool: '本地即时响应', local: true },
  resume: { label: '继续烹饪', tool: '本地即时响应', local: true },
  finish: { label: '完成复盘', tool: '本地即时响应', local: true },
  reset: { label: '重新规划', tool: '本地即时响应', local: true },
  repeat_current_step: { label: '重复当前步骤', tool: '本地即时响应', local: true },
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

function statusText(status, isError) {
  if (status === 'success') return '已完成';
  if (status === 'fallback') return '本地兜底';
  if (status === 'error') return '需要处理';
  return isError ? '需要处理' : status;
}

export default function ToolTimeline({ events }) {
  const list = (events || []).slice(-12);
  const lastIdx = list.length - 1;

  return (
    <div className="rp-section" style={{ flex: '0 0 auto' }}>
      <div className="rp-head">
        <span className="section-label">任务进程</span>
        {list.length ? (
          <span className="rp-aux live">
            <span className="dot">●</span> 实时更新
          </span>
        ) : (
          <span className="rp-aux">待命</span>
        )}
      </div>

      <div className="timeline">
        {list.length === 0 ? (
          <div className="timeline-empty">
            等待语音、视觉或烹饪动作。触发后，这里会显示妮妮的处理进程。
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
                return `响应 ${out.latency_ms}ms`;
              if (event.name === 'provider_error')
                return '已用本地方案继续';
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
                        本地即时响应
                      </span>
                    ) : (
                      <span className="tag-mini tool">{meta.tool}</span>
                    )}
                    <span className={`tag-mini ${isError ? 'fallback' : 'status'}`}>
                      {statusText(status, isError)}
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
