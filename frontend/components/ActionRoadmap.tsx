'use client';

// components/ActionRoadmap.tsx - 3 ranked improvement actions

interface Action {
  action: string;
  delta: number;
  priority: number;
}

interface ActionRoadmapProps {
  actions: Action[];
}

export default function ActionRoadmap({ actions }: ActionRoadmapProps) {
  const priorityColors: Record<number, { bg: string; text: string; icon: string }> = {
    1: { bg: 'bg-red-900/20', text: 'text-red-400', icon: '🔴' },
    2: { bg: 'bg-yellow-900/20', text: 'text-yellow-400', icon: '🟡' },
    3: { bg: 'bg-green-900/20', text: 'text-green-400', icon: '🟢' },
  };

  return (
    <div className="space-y-4">
      {actions.map((action, idx) => {
        const priority = (action.priority || idx + 1) as keyof typeof priorityColors;
        const colors = priorityColors[priority] || priorityColors[1];

        return (
          <div key={idx} className={`rounded-lg border border-slate-700 ${colors.bg} p-4`}>
            <div className="flex items-start gap-4">
              <span className="text-2xl">{colors.icon}</span>

              <div className="flex-1">
                <div className="flex items-start justify-between">
                  <div>
                    <h4 className={`font-semibold ${colors.text}`}>
                      Priority {action.priority || idx + 1}
                    </h4>
                    <p className="mt-2 text-sm text-slate-300">{action.action}</p>
                  </div>

                  {action.delta > 0 && (
                    <div className="ml-4 flex flex-col items-end">
                      <p className="text-lg font-bold text-green-400">+{action.delta}</p>
                      <p className="text-xs text-slate-400">score points</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        );
      })}

      {/* Timeline indicator */}
      <div className="mt-8 rounded-lg border border-slate-700 bg-slate-800/30 p-4 text-center">
        <p className="text-sm text-slate-400">
          Follow these actions for 3 months to potentially reach{' '}
          <span className="font-semibold text-slate-200">+{actions.reduce((sum, a) => sum + a.delta, 0)} points</span>
        </p>
      </div>
    </div>
  );
}
